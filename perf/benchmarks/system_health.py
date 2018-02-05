# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from benchmarks import loading_metrics_category

from core import perf_benchmark

from telemetry import benchmark
from telemetry import story
from telemetry.timeline import chrome_trace_category_filter
from telemetry.timeline import chrome_trace_config
from telemetry.web_perf import timeline_based_measurement
import page_sets


# Regex to filter out a few names of statistics supported by
# Histogram.getStatisticScalar(), see:
#   https://github.com/catapult-project/catapult/blob/d4179a05/tracing/tracing/value/histogram.html#L645  pylint: disable=line-too-long
_IGNORED_STATS_RE = re.compile(r'_(std|count|max|min|sum|pct_\d{4}(_\d+)?)$')


class _CommonSystemHealthBenchmark(perf_benchmark.PerfBenchmark):
  """Chrome Common System Health Benchmark.

  This test suite contains system health benchmarks that can be collected
  together due to the low overhead of the tracing agents required. If a
  benchmark does have significant overhead, it should either:

    1) Be rearchitected such that it doesn't. This is the most preferred option.
    2) Be run in a separate test suite (e.g. memory).

  https://goo.gl/Jek2NL.
  """

  def CreateCoreTimelineBasedMeasurementOptions(self):
    cat_filter = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        filter_string='rail,toplevel')
    cat_filter.AddIncludedCategory('accessibility')

    options = timeline_based_measurement.Options(cat_filter)
    options.config.enable_battor_trace = True
    options.config.enable_chrome_trace = True
    options.config.enable_cpu_trace = True
    options.SetTimelineBasedMetrics([
        'clockSyncLatencyMetric',
        'cpuTimeMetric',
        'powerMetric',
        'tracingMetric',
        'accessibilityMetric',
        'limitedCpuTimeMetric'
    ])
    loading_metrics_category.AugmentOptionsForLoadingMetrics(options)
    # The EQT metric depends on the same categories as the loading metric.
    options.AddTimelineBasedMetric('expectedQueueingTimeMetric')
    return options

  def CreateStorySet(self, options):
    return page_sets.SystemHealthStorySet(platform=self.PLATFORM)


@benchmark.Owner(emails=['charliea@chromium.org', 'nednguyen@chromium.org'])
class DesktopCommonSystemHealth(_CommonSystemHealthBenchmark):
  """Desktop Chrome Energy System Health Benchmark."""
  PLATFORM = 'desktop'
  SUPPORTED_PLATFORMS = [story.expectations.ALL_DESKTOP]

  @classmethod
  def Name(cls):
    return 'system_health.common_desktop'


@benchmark.Owner(emails=['charliea@chromium.org', 'nednguyen@chromium.org'])
class MobileCommonSystemHealth(_CommonSystemHealthBenchmark):
  """Mobile Chrome Energy System Health Benchmark."""
  PLATFORM = 'mobile'
  SUPPORTED_PLATFORMS = [story.expectations.ALL_MOBILE]

  @classmethod
  def Name(cls):
    return 'system_health.common_mobile'


class _MemorySystemHealthBenchmark(perf_benchmark.PerfBenchmark):
  """Chrome Memory System Health Benchmark.

  This test suite is run separately from the common one due to the high overhead
  of memory tracing.

  https://goo.gl/Jek2NL.
  """
  options = {'pageset_repeat': 3}

  def CreateCoreTimelineBasedMeasurementOptions(self):
    options = timeline_based_measurement.Options(
        chrome_trace_category_filter.ChromeTraceCategoryFilter(
            '-*,disabled-by-default-memory-infra'))
    options.config.enable_android_graphics_memtrack = True
    options.SetTimelineBasedMetrics(['memoryMetric'])
    # Setting an empty memory dump config disables periodic dumps.
    options.config.chrome_trace_config.SetMemoryDumpConfig(
        chrome_trace_config.MemoryDumpConfig())
    return options

  def CreateStorySet(self, options):
    return page_sets.SystemHealthStorySet(platform=self.PLATFORM,
                                          take_memory_measurement=True)

  @classmethod
  def ShouldAddValue(cls, name, from_first_story_run):
    del from_first_story_run # unused
    # TODO(crbug.com/610962): Remove this stopgap when the perf dashboard
    # is able to cope with the data load generated by TBMv2 metrics.
    return not _IGNORED_STATS_RE.search(name)


@benchmark.Owner(emails=['perezju@chromium.org'])
class DesktopMemorySystemHealth(_MemorySystemHealthBenchmark):
  """Desktop Chrome Memory System Health Benchmark."""
  PLATFORM = 'desktop'
  SUPPORTED_PLATFORMS = [story.expectations.ALL_DESKTOP]

  @classmethod
  def Name(cls):
    return 'system_health.memory_desktop'

  def SetExtraBrowserOptions(self, options):
    super(DesktopMemorySystemHealth, self).SetExtraBrowserOptions(
          options)
    # Heap profiling is disabled because of crbug.com/757847.
    #options.AppendExtraBrowserArgs([
    #  '--enable-heap-profiling=native',
    #])


@benchmark.Owner(emails=['perezju@chromium.org'])
class MobileMemorySystemHealth(_MemorySystemHealthBenchmark):
  """Mobile Chrome Memory System Health Benchmark."""
  PLATFORM = 'mobile'
  SUPPORTED_PLATFORMS = [story.expectations.ALL_MOBILE]

  def SetExtraBrowserOptions(self, options):
    # Just before we measure memory we flush the system caches
    # unfortunately this doesn't immediately take effect, instead
    # the next story run is effected. Due to this the first story run
    # has anomalous results. This option causes us to flush caches
    # each time before Chrome starts so we effect even the first story
    # - avoiding the bug.
    options.clear_sytem_cache_for_browser_and_profile_on_start = True

  @classmethod
  def Name(cls):
    return 'system_health.memory_mobile'


@benchmark.Owner(emails=['perezju@chromium.org', 'torne@chromium.org'])
class WebviewStartupSystemHealthBenchmark(perf_benchmark.PerfBenchmark):
  """Webview startup time benchmark

  Benchmark that measures how long WebView takes to start up
  and load a blank page. Since thie metric only requires the trace
  markers recorded in atrace, Chrome tracing is not enabled for this
  benchmark.
  """
  options = {'pageset_repeat': 20}
  SUPPORTED_PLATFORMS = [story.expectations.ANDROID_WEBVIEW]

  def CreateStorySet(self, options):
    return page_sets.SystemHealthBlankStorySet()

  def CreateCoreTimelineBasedMeasurementOptions(self):
    options = timeline_based_measurement.Options()
    options.SetTimelineBasedMetrics(['webviewStartupMetric'])
    options.config.enable_atrace_trace = True
    options.config.enable_chrome_trace = False
    options.config.atrace_config.app_name = 'org.chromium.webview_shell'
    return options

  @classmethod
  def Name(cls):
    return 'system_health.webview_startup'
