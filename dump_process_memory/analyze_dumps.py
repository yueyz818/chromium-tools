#!/usr/bin/python
#
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""From a dump generated by dump_process.cc dump, prints statistics about
its content.
"""

import argparse
import array
import collections
import hashlib
import logging
import os
import zlib


PAGE_SIZE = 1 << 12


# These are typically only populated with DCHECK() on.
FREED_PATTERNS = {
    0xcccccccc: 'V8',
    0xcdcdcdcd: 'PartitionAlloc zapped',
    0xabababab: 'PartitionAlloc uninitialized',
    0xdeadbeef: 'V8 zapped',
    0x0baddeaf: 'V8 zapped handles',
    0x0baffedf: 'V8 zapped global handles',
    0x0beefdaf: 'V8 zapped from space',
    0xbeefdeef: 'V8 zapped slots',
    0xbadbaddb: 'V8 debug zapped',
    0xfeed1eaf: 'V8 zapped freelist'
}


def _ReadPage(f):
  """Reads a page of data from a file.

  Args:
    f: (file) An opened file to read from.

  Returns:
    An array.array() of unsigned int with the page content.
  """
  result = array.array('I')
  result.fromfile(f, PAGE_SIZE / result.itemsize)
  return result


def _PrettyPrintSize(x):
  """Pretty print sizes in bytes, e.g. 123456 -> 123.45kB.

  Args:
    x: (int) size

  Returns:
    (str) Pretty printed version, 2 decimal places.
  """
  if x < 1e3:
    return '%dB' % x
  elif 1e3 <= x < 1e6:
    return '%.2fkB' % (x / 1e3)
  elif 1e6 <= x < 1e9:
    return '%.2fMB' % (x / 1e6)
  else:
    return '%.2fGB' % (x / 1e9)


class MappingStats(object):
  """Statistics about a mapping, from a dump.

  Slots:
    filename: (str) Dump filename.
    start: (int) Start address of the mapping.
    end: (int) End address of the mapping.
    pages: (int) Sizs of the mapping in pages.
    is_zero: ([bool]) For each page, whether it's a zero page.
    is_present: ([bool]) For each page, whether it's present.
    is_swapped: ([bool]) For each page, whether it has been swapped out.
    compressed_size: ([int]) If a page is not zero, its compressed size.
    hashes: ([str]) If a page is not zero, its SHA1 hash.
    freed: ({'description (str)': size (int)}) Size of freed data, per type.
  """
  __slots__ = ('filename', 'start', 'end', 'pages', 'is_zero', 'is_present',
               'is_swapped', 'compressed_size', 'hashes', 'freed')

  def __init__(self, filename, start, end):
    """Init.

    Args:
      filename: (str) Dump filename.
      start: (int) Start address.
      end: (int) End address
    """
    self.filename = filename
    self.start = start
    self.end = end
    self.pages = (end - start) / PAGE_SIZE
    self.is_zero = [False for _ in range(self.pages)]
    self.is_present = [False for _ in range(self.pages)]
    self.is_swapped = [False for _ in range(self.pages)]
    self.compressed_size = [0 for _ in range(self.pages)]
    self.hashes = [None for _ in range(self.pages)]
    self.freed = collections.defaultdict(int)


def _GetStatsFromFileDump(filename):
  """Computes per-dump statistics.

  Args:
    filename: (str) Path to the dump.

  Returns:
    MappingStats for the mapping.
  """
  # Dump integrity checks.
  metadata_filename = filename + '.metadata'
  pid_start_end = os.path.basename(filename)[:-len('.dump')]
  (_, start, end) = [int(x, 10) for x in pid_start_end.split('-')]
  file_stat = os.stat(filename)
  assert start % PAGE_SIZE == 0
  assert end % PAGE_SIZE == 0
  assert file_stat.st_size == (end - start)
  metadata_file_stat = os.stat(metadata_filename)
  result = MappingStats(filename, start, end)
  # each line is [01]{2}\n, eg '10\n', 1 line per page.
  assert metadata_file_stat.st_size == 3 * result.pages

  with open(filename, 'r') as f, open(metadata_filename, 'r') as metadata_f:
    for i in range(result.pages):
      page = _ReadPage(f)
      assert len(page) == 1024
      for x in page:
        if x in FREED_PATTERNS:
          result.freed[FREED_PATTERNS[x]] += 4
      is_zero = max(page) == 0
      present, swapped = (bool(int(x)) for x in metadata_f.readline().strip())
      # Not present, not swapped private anonymous == lazily initialized zero
      # page.
      if not present and not swapped:
        assert is_zero
      result.is_zero[i] = is_zero
      result.is_present[i] = present
      result.is_swapped[i] = swapped
      if not is_zero:
        sha1 = hashlib.sha1()
        sha1.update(page)
        page_hash = sha1.digest()
        result.hashes[i] = page_hash
        compressed = zlib.compress(page, 1)
        result.compressed_size[i] = len(compressed)
  return result


def _FindPageFromHash(mappings, page_hash):
  """Returns a page with a given hash from a list of mappings.

  Args:
    mappings: ([MappingStats]) List of mappings.
    page_hash: (str) Page hash to look for,

  Returns:
    array.array(uint32_t) with the page content
  """
  for mapping in mappings:
    for i in range(mapping.pages):
      if mapping.hashes[i] == page_hash:
        with open(mapping.filename, 'r') as f:
          f.seek(i * PAGE_SIZE)
          page = _ReadPage(f)
          sha1 = hashlib.sha1()
          sha1.update(page)
          assert page_hash == sha1.digest()
          return page


def _PrintPage(page):
  """Prints the content of a page."""
  for i, x in enumerate(page):
    print '{:08x}'.format(x),
    if i % 16 == 15:
      print


AggregateStats = collections.namedtuple(
    'AggregateStats', ('content_to_count', 'pages', 'zero_pages',
                       'compressed_size', 'swapped_pages',
                       'not_present_pages', 'present_zero_pages', 'freed'))


def _AggregateStats(dump_stats):
  """Aggreates statistics across dumps.

  Args:
    dump_stats: ([MappingStats]) Stats from all mappings.

  Returns:
    An instance of AggregateStats.
  """
  content_to_count = collections.defaultdict(int)
  total_pages = sum(stats.pages for stats in dump_stats)
  total_zero_pages = sum(sum(stats.is_zero) for stats in dump_stats)
  total_compressed_size = sum(sum(stats.compressed_size)
                              for stats in dump_stats)
  total_swapped_pages = sum(sum(stats.is_swapped) for stats in dump_stats)
  total_not_present_pages = sum(stats.pages - sum(stats.is_present)
                                for stats in dump_stats)
  total_present_zero_pages = sum(
      sum(x == (True, True) for x in zip(stats.is_zero, stats.is_present))
      for stats in dump_stats)
  total_freed_space = {x: 0 for x in FREED_PATTERNS.values()}
  for dump in dump_stats:
    for (freed_data_type, value) in dump.freed.items():
      total_freed_space[freed_data_type] += value

  content_to_count = collections.defaultdict(int)
  for stats in dump_stats:
    for page_hash in stats.hashes:
      if page_hash:
        content_to_count[page_hash] += 1

  return AggregateStats(
      content_to_count=content_to_count, pages=total_pages,
      zero_pages=total_zero_pages, compressed_size=total_compressed_size,
      swapped_pages=total_swapped_pages,
      not_present_pages=total_not_present_pages,
      present_zero_pages=total_present_zero_pages,
      freed=total_freed_space)


def PrintStats(dumps, verbose):
  """Logs statistics about a process mappings dump.

  Args:
    dumps: ([str]) List of dumps.
    verbose: (bool) Verbose output.
  """
  dump_stats = [_GetStatsFromFileDump(filename) for filename in dumps]
  total = _AggregateStats(dump_stats)
  duplicated_pages = sum(x - 1 for x in total.content_to_count.values())
  count_and_hashes = sorted(((v, k) for k, v in total.content_to_count.items()),
                            reverse=True)
  max_common_pages = count_and_hashes[0][0] - 1
  total_size_non_zero_pages = (total.pages - total.zero_pages) * PAGE_SIZE

  print 'Total pages = %d (%s)' % (total.pages,
                                   _PrettyPrintSize(total.pages * PAGE_SIZE))
  print 'Total zero pages = %d (%.02f%%)' % (
      total.zero_pages, (100. * total.zero_pages) / total.pages)
  print 'Total present zero pages = %d (%s)' % (
      total.present_zero_pages,
      _PrettyPrintSize(total.present_zero_pages * PAGE_SIZE))
  print 'Total size of non-zero pages = %d (%s)' % (
      total_size_non_zero_pages, _PrettyPrintSize(total_size_non_zero_pages))
  print 'Total compressed size = %d (%.02f%%)' % (
      total.compressed_size,
      (100. * total.compressed_size) / total_size_non_zero_pages)
  print 'Duplicated non-zero pages = %d' % duplicated_pages
  print 'Max non-zero pages with the same content = %d' % max_common_pages
  print 'Swapped pages = %d (%s)' % (
      total.swapped_pages, _PrettyPrintSize(total.swapped_pages * PAGE_SIZE))
  print 'Non-present pages = %d (%s)' % (
      total.not_present_pages,
      _PrettyPrintSize(total.not_present_pages * PAGE_SIZE))
  print 'Freed: '
  for k in total.freed:
    print '  %s = %d (%s)' % (
        k, total.freed[k], _PrettyPrintSize(total.freed[k]))

  if verbose:
    print 'Top Duplicated Pages:'
    for i in range(10):
      count, page_hash = count_and_hashes[i]
      print '%d common pages' % count
      page = _FindPageFromHash(dump_stats, page_hash)
      _PrintPage(page)
      print


def _CreateArgumentParser():
  parser = argparse.ArgumentParser()
  parser.add_argument('--directory', type=str, required=True,
                      help='Dumps directory')
  parser.add_argument('--verbose', action='store_true', help='Dumps directory')
  return parser


def main():
  logging.basicConfig(level=logging.INFO)
  parser = _CreateArgumentParser()
  args = parser.parse_args()

  dumps = []
  for f in os.listdir(args.directory):
    if f.endswith('.dump'):
      dumps.append(os.path.join(args.directory, f))

  PrintStats(dumps, args.verbose)


if __name__ == '__main__':
  main()
