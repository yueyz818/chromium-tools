# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from core import perf_benchmark
from telemetry import benchmark
from telemetry.timeline import chrome_trace_config
from telemetry.timeline import chrome_trace_category_filter
from telemetry.web_perf import timeline_based_measurement
import page_sets


# See tr.v.Numeric.getSummarizedScalarNumericsWithNames()
# https://github.com/catapult-project/catapult/blob/master/tracing/tracing/value/numeric.html#L323
_IGNORED_MEMORY_STATS_RE = re.compile(r'_(std|count|min|sum|pct_\d{4}(_\d+)?)$')

# Track only the high-level GC stats to reduce the data load on dashboard.
_IGNORED_V8_STATS_RE = re.compile(
    r'_(idle_deadline_overrun|percentage_idle|outside_idle)')
_V8_GC_HIGH_LEVEL_STATS_RE = re.compile(r'^v8-gc-('
    r'full-mark-compactor_|'
    r'incremental-finalize_|'
    r'incremental-step_|'
    r'latency-mark-compactor_|'
    r'memory-mark-compactor_|'
    r'scavenger_|'
    r'total_)')


class _v8BrowsingBenchmarkBaseClass(perf_benchmark.PerfBenchmark):
  """Base class for all v8 browsing benchmarks."""
  def CreateStorySet(self, options):
    return page_sets.SystemHealthStorySet(platform=self.PLATFORM, case='browse')

  def GetExpectations(self):
    if self.PLATFORM is 'desktop':
      return page_sets.V8BrowsingDesktopExpecations()
    if self.PLATFORM is 'mobile':
      return page_sets.V8BrowsingMobileExpecations()
    raise NotImplementedError, ('Only have expectations for mobile and desktop '
                                'platforms for v8_browsing tests.')


class _V8BrowsingBenchmark(_v8BrowsingBenchmarkBaseClass):
  """Base class for V8 browsing benchmarks.
  This benchmark measures memory usage with periodic memory dumps and v8 times.
  See browsing_stories._BrowsingStory for workload description.
  """

  def CreateCoreTimelineBasedMeasurementOptions(self):
    categories = [
      # Disable all categories by default.
      '-*',
      # Memory categories.
      'disabled-by-default-memory-infra',
      # EQT categories.
      'blink.user_timing',
      'loading',
      'navigation',
      'toplevel',
      # V8 categories.
      'blink.console',
      'disabled-by-default-v8.compile',
      'disabled-by-default-v8.gc',
      'renderer.scheduler',
      'v8',
      'webkit.console',
      # TODO(crbug.com/616441, primiano): Remove this temporary workaround,
      # which enables memory-infra V8 code stats in V8 code size benchmarks
      # only (to not slow down detailed memory dumps in other benchmarks).
      'disabled-by-default-memory-infra.v8.code_stats',
    ]
    options = timeline_based_measurement.Options(
        chrome_trace_category_filter.ChromeTraceCategoryFilter(
            ','.join(categories)))
    options.config.enable_android_graphics_memtrack = True
    # Trigger periodic light memory dumps every 1000 ms.
    memory_dump_config = chrome_trace_config.MemoryDumpConfig()
    memory_dump_config.AddTrigger('light', 1000)
    options.config.chrome_trace_config.SetMemoryDumpConfig(memory_dump_config)
    options.SetTimelineBasedMetrics([
      'expectedQueueingTimeMetric', 'v8AndMemoryMetrics'])
    return options

  @classmethod
  def ValueCanBeAddedPredicate(cls, value, is_first_result):
    # TODO(crbug.com/610962): Remove this stopgap when the perf dashboard
    # is able to cope with the data load generated by TBMv2 metrics.
    if 'memory:chrome' in value.name:
      return ('renderer_processes' in value.name and
              not _IGNORED_MEMORY_STATS_RE.search(value.name))
    if 'v8-gc' in value.name:
      return (_V8_GC_HIGH_LEVEL_STATS_RE.search(value.name) and
              not _IGNORED_V8_STATS_RE.search(value.name))
    # Allow all other metrics.
    return True


class _V8RuntimeStatsBrowsingBenchmark(_v8BrowsingBenchmarkBaseClass):
  """Base class for V8 browsing benchmarks that measure RuntimeStats.
  RuntimeStats measure the time spent by v8 in different phases like
  compile, JS execute, runtime etc.,
  See browsing_stories._BrowsingStory for workload description.
  """

  def CreateCoreTimelineBasedMeasurementOptions(self):
    categories = [
      # Disable all categories by default.
      '-*',
      # Memory categories.
      'disabled-by-default-memory-infra',
      # UE categories requred by runtimeStatsTotalMetric to bucket
      # runtimeStats by UE.
      'rail',
      # EQT categories.
      'blink.user_timing',
      'loading',
      'navigation',
      'toplevel',
      # V8 categories.
      'blink.console',
      'disabled-by-default-v8.gc',
      'disabled-by-default-v8.compile',
      'renderer.scheduler',
      'v8',
      'webkit.console',
      'disabled-by-default-v8.runtime_stats',
      # TODO(crbug.com/616441, primiano): Remove this temporary workaround,
      # which enables memory-infra V8 code stats in V8 code size benchmarks
      # only (to not slow down detailed memory dumps in other benchmarks).
      'disabled-by-default-memory-infra.v8.code_stats',
    ]
    options = timeline_based_measurement.Options(
        chrome_trace_category_filter.ChromeTraceCategoryFilter(
            ','.join(categories)))
    options.config.enable_android_graphics_memtrack = True
    # Trigger periodic light memory dumps every 1000 ms.
    memory_dump_config = chrome_trace_config.MemoryDumpConfig()
    memory_dump_config.AddTrigger('light', 1000)
    options.config.chrome_trace_config.SetMemoryDumpConfig(memory_dump_config)

    options.SetTimelineBasedMetrics([
      'expectedQueueingTimeMetric', 'runtimeStatsTotalMetric', 'gcMetric',
      'memoryMetric'])
    return options


@benchmark.Owner(emails=['ulan@chromium.org'])
@benchmark.Disabled('android')
class V8DesktopBrowsingBenchmark(_V8BrowsingBenchmark):
  PLATFORM = 'desktop'

  @classmethod
  def Name(cls):
    return 'v8.browsing_desktop'


@benchmark.Owner(emails=['ulan@chromium.org'])
@benchmark.Enabled('android')
class V8MobileBrowsingBenchmark(_V8BrowsingBenchmark):
  PLATFORM = 'mobile'

  @classmethod
  def Name(cls):
    return 'v8.browsing_mobile'


@benchmark.Disabled('android')
@benchmark.Owner(emails=['mythria@chromium.org'])
class V8RuntimeStatsDesktopBrowsingBenchmark(
    _V8RuntimeStatsBrowsingBenchmark):
  PLATFORM = 'desktop'

  @classmethod
  def Name(cls):
    return 'v8.runtimestats.browsing_desktop'


@benchmark.Enabled('android')
@benchmark.Owner(emails=['mythria@chromium.org'])
class V8RuntimeStatsMobileBrowsingBenchmark(
    _V8RuntimeStatsBrowsingBenchmark):
  PLATFORM = 'mobile'

  @classmethod
  def Name(cls):
    return 'v8.runtimestats.browsing_mobile'
