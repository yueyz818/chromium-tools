# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from core import perf_benchmark
from core import perf_data_generator
from core.perf_data_generator import BenchmarkMetadata

from telemetry import benchmark
from telemetry import decorators

import mock


class PerfDataGeneratorTest(unittest.TestCase):
  def setUp(self):
    # Test config can be big, so set maxDiff to None to see the full comparision
    # diff when assertEquals fails.
    self.maxDiff = None

  def testVerifyAllTestsInBenchmarkCsvPassesWithCorrectInput(self):
    tests = {
        'AAAAA1 AUTOGENERATED': {},
        'Android Nexus5 Perf (2)': {
            'scripts': [
                {'name': 'benchmark_name_1'},
                {'name': 'benchmark_name_2'}
            ]
        },
        'Linux Perf': {
            'isolated_scripts': [
                {'name': 'benchmark_name_2.reference'},
                {'name': 'benchmark_name_3'}
            ]
        }
    }
    benchmarks = {
        'benchmark_name_1': BenchmarkMetadata('foo@bar.com', None, False),
        'benchmark_name_2': BenchmarkMetadata(None, None, False),
        'benchmark_name_3': BenchmarkMetadata('neo@matrix.org', None, False)
    }

    # Mock out content of unowned_benchmarks.txt
    with mock.patch('__builtin__.open',
                    mock.mock_open(read_data="benchmark_name_2")):
      perf_data_generator.verify_all_tests_in_benchmark_csv(tests, benchmarks)


  def testVerifyAllTestsInBenchmarkCsvCatchesMismatchedTests(self):
    tests = {
        'Android Nexus5 Perf (2)': {
            'scripts': [
                {'name': 'benchmark_name_1'},
                {'name': 'benchmark_name_2'}
            ]
        }
    }
    benchmarks = {
        'benchmark_name_2': BenchmarkMetadata(None, None, False),
        'benchmark_name_3': BenchmarkMetadata(None, None, False),
    }

    with self.assertRaises(AssertionError) as context:
      perf_data_generator.verify_all_tests_in_benchmark_csv(tests, benchmarks)
    exception = context.exception.message
    self.assertTrue('Add benchmark_name_1' in exception)
    self.assertTrue('Remove benchmark_name_3' in exception)


  def testVerifyAllTestsInBenchmarkCsvFindsFakeTest(self):
    tests = {'Random fake test': {}}
    benchmarks = {
        'benchmark_name_1': BenchmarkMetadata(None, None, False)
    }

    with self.assertRaises(AssertionError) as context:
      perf_data_generator.verify_all_tests_in_benchmark_csv(tests, benchmarks)
    self.assertTrue('Unknown test' in context.exception.message)

  def testGenerateTelemetryTestForNonReferenceBuild(self):
    swarming_dimensions = [{'os': 'SkyNet', 'id': 'T-850', 'pool': 'T-RIP'}]
    test = perf_data_generator.generate_telemetry_test(
        swarming_dimensions, 'speedometer', 'release')
    expected_generated_test = {
        'override_compile_targets': ['telemetry_perf_tests'],
        'args': ['speedometer', '-v', '--upload-results',
                 '--output-format=chartjson', '--browser=release'],
        'swarming': {
          'ignore_task_failure': False,
          'dimension_sets': [{'os': 'SkyNet', 'id': 'T-850', 'pool': 'T-RIP'}],
          'hard_timeout': 10800,
          'can_use_on_swarming_builders': True,
          'expiration': 36000,
          'io_timeout': 3600,
        },
        'name': 'speedometer',
        'isolate_name': 'telemetry_perf_tests',
      }
    self.assertEquals(test, expected_generated_test)

  def testGenerateTelemetryTestForReferenceBuild(self):
    swarming_dimensions = [{'os': 'SkyNet', 'id': 'T-850', 'pool': 'T-RIP'}]
    test = perf_data_generator.generate_telemetry_test(
        swarming_dimensions, 'speedometer', 'reference')
    expected_generated_test = {
        'override_compile_targets': ['telemetry_perf_tests'],
        'args': ['speedometer', '-v', '--upload-results',
                 '--output-format=chartjson', '--browser=reference',
                 '--output-trace-tag=_ref'],
        'swarming': {
          'ignore_task_failure': True,
          'dimension_sets': [{'os': 'SkyNet', 'id': 'T-850', 'pool': 'T-RIP'}],
          'hard_timeout': 10800,
          'can_use_on_swarming_builders': True,
          'expiration': 36000,
          'io_timeout': 3600,
        },
        'name': 'speedometer.reference',
        'isolate_name': 'telemetry_perf_tests',
      }
    self.assertEquals(test, expected_generated_test)

  def testGenerateTelemetryTestsWebView(self):
    class RegularBenchmark(benchmark.Benchmark):
      @classmethod
      def Name(cls):
        return 'regular'

    swarming_dimensions = [
        {'os': 'SkyNet', 'id': 'T-850', 'pool': 'T-RIP', 'device_ids': ['a']}
    ]
    test_config = {
        'platform': 'android',
        'swarming_dimensions': swarming_dimensions,
        'replace_system_webview': True,
    }
    sharding_map = {'fake': {'regular': 'a'}}
    benchmarks = [RegularBenchmark]
    tests = perf_data_generator.generate_telemetry_tests(
        'fake', test_config, benchmarks, sharding_map, ['blacklisted'])

    self.assertEqual(len(tests), 1)
    test = tests[0]
    self.assertEquals(test['args'], [
        'regular', '-v', '--upload-results', '--output-format=chartjson',
        '--browser=android-webview',
        '--webview-embedder-apk=../../out/Release/apks/SystemWebViewShell.apk'])
    self.assertEquals(test['isolate_name'], 'telemetry_perf_webview_tests')

  def testGenerateTelemetryTestsBlacklistedReferenceBuildTest(self):
    class BlacklistedBenchmark(benchmark.Benchmark):
      @classmethod
      def Name(cls):
        return 'blacklisted'

    class NotBlacklistedBenchmark(benchmark.Benchmark):
      @classmethod
      def Name(cls):
        return 'not_blacklisted'

    swarming_dimensions = [
        {'os': 'SkyNet', 'id': 'T-850', 'pool': 'T-RIP', 'device_ids': ['a']}
    ]
    test_config = {
        'platform': 'android',
        'swarming_dimensions': swarming_dimensions,
    }
    sharding_map = {'fake': {'blacklisted': 'a', 'not_blacklisted': 'a'}}
    benchmarks = [BlacklistedBenchmark, NotBlacklistedBenchmark]
    tests = perf_data_generator.generate_telemetry_tests(
        'fake', test_config, benchmarks, sharding_map, ['blacklisted'])

    generated_test_names = set(t['name'] for t in tests)
    self.assertEquals(
        generated_test_names,
        {'blacklisted', 'not_blacklisted', 'not_blacklisted.reference'})

  def testShouldBenchmarkBeScheduledNormal(self):
    class bench(perf_benchmark.PerfBenchmark):
      pass

    self.assertEqual(
        perf_data_generator.ShouldBenchmarkBeScheduled(bench(), 'win'),
        True)

  def testShouldBenchmarkBeScheduledDisabledAll(self):
    @decorators.Disabled('all')
    class bench(perf_benchmark.PerfBenchmark):
      pass

    self.assertEqual(
        perf_data_generator.ShouldBenchmarkBeScheduled(bench(), 'win'),
        False)

  def testShouldBenchmarkBeScheduledOnDesktopMobileTest(self):
    @decorators.Enabled('android')
    class bench(perf_benchmark.PerfBenchmark):
      pass

    self.assertEqual(
        perf_data_generator.ShouldBenchmarkBeScheduled(bench(), 'win'),
        False)

  def testShouldBenchmarkBeScheduledOnMobileMobileTest(self):
    @decorators.Enabled('android')
    class bench(perf_benchmark.PerfBenchmark):
      pass

    self.assertEqual(
        perf_data_generator.ShouldBenchmarkBeScheduled(bench(), 'android'),
        True)

  def testShouldBenchmarkBeScheduledOnMobileMobileTestDisabled(self):
    @decorators.Disabled('android')
    class bench(perf_benchmark.PerfBenchmark):
      pass

    self.assertEqual(
        perf_data_generator.ShouldBenchmarkBeScheduled(bench(), 'android'),
        False)

  def testRemoveBlacklistedTestsNoop(self):
    tests = [{
        'swarming': {
            'dimension_sets': [{
                'id': 'build1-b1',
            }]
        },
        'name': 'test',
    }]
    self.assertEqual(
        perf_data_generator.remove_blacklisted_device_tests(tests, []), (
            tests, {}))

  def testRemoveBlacklistedTestsShouldRemove(self):
    tests = [{
        'swarming': {
            'dimension_sets': [{
                'id': 'build1-b1',
            }]
        },
        'name': 'test',
    }]
    self.assertEqual(
        perf_data_generator.remove_blacklisted_device_tests(
            tests, ['build1-b1']), ([], {'build1-b1': ['test']}))

  def testRemoveBlacklistedTestsShouldRemoveMultiple(self):
    tests = [{
        'swarming': {
            'dimension_sets': [{
                'id': 'build1-b1',
            }]
        },
        'name': 'test',
    }, {
        'swarming': {
            'dimension_sets': [{
                'id': 'build2-b1',
            }]
        },
        'name': 'other_test',
    }, {
        'swarming': {
            'dimension_sets': [{
                'id': 'build2-b1',
            }]
        },
        'name': 'test',
    }]
    self.assertEqual(
        perf_data_generator.remove_blacklisted_device_tests(
            tests, ['build1-b1', 'build2-b1']), ([], {
                'build1-b1': ['test'],
                'build2-b1': ['other_test', 'test'],
            }))
