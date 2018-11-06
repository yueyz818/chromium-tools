# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Output the list of files to be generated by GRIT from an input.
"""

import getopt
import os

from grit import grd_reader
from grit.node import structure
from grit.tool import interface

class DetermineBuildInfo(interface.Tool):
  """Determine what files will be read and output by GRIT."""

  def __init__(self):
    pass

  def ShortDescription(self):
    """Describes this tool for the usage message."""
    return ('Determine what files will be needed and\n'
            'output by GRIT with a given input.')

  def Run(self, opts, args):
    """Main method for the buildinfo tool.  Outputs the list
       of generated files and inputs used to stdout."""
    self.output_directory = '.'
    (own_opts, args) = getopt.getopt(args, 'o:')
    for (key, val) in own_opts:
      if key == '-o':
        self.output_directory = val
    if len(args) > 0:
      print 'This tool takes exactly one argument: the output directory via -o'
      return 2
    self.SetOptions(opts)

    res_tree = grd_reader.Parse(opts.input, debug=opts.extra_verbose)

    langs = {}
    for output in res_tree.GetOutputFiles():
      if output.attrs['lang']:
        langs[output.attrs['lang']] = os.path.dirname(output.GetFilename())

    for lang, dirname in langs.iteritems():
      old_output_language = res_tree.output_language
      res_tree.SetOutputLanguage(lang)
      for node in res_tree.ActiveDescendants():
        with node:
          if (isinstance(node, structure.StructureNode) and
              node.HasFileForLanguage()):
            path = node.FileForLanguage(lang, dirname, create_file=False,
                                        return_if_not_generated=False)
            if path:
              path = os.path.join(self.output_directory, path)
              path = os.path.normpath(path)
              print '%s|%s' % ('rc_all', path)
      res_tree.SetOutputLanguage(old_output_language)

    for output in res_tree.GetOutputFiles():
      path = os.path.join(self.output_directory, output.GetFilename())
      path = os.path.normpath(path)
      print '%s|%s' % (output.GetType(), path)

    for infile in res_tree.GetInputFiles():
      print 'input|%s' % os.path.normpath(infile)
