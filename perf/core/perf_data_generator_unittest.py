# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from core import perf_data_generator
from core.perf_data_generator import BenchmarkMetadata

from telemetry import benchmark


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
        'benchmark_name_1': BenchmarkMetadata(None, None),
        'benchmark_name_2': BenchmarkMetadata(None, None),
        'benchmark_name_3': BenchmarkMetadata(None, None)
    }

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
        'benchmark_name_2': BenchmarkMetadata(None, None),
        'benchmark_name_3': BenchmarkMetadata(None, None),
    }

    with self.assertRaises(AssertionError) as context:
      perf_data_generator.verify_all_tests_in_benchmark_csv(tests, benchmarks)
    exception = context.exception.message
    self.assertTrue('Add benchmark_name_1' in exception)
    self.assertTrue('Remove benchmark_name_3' in exception)


  def testVerifyAllTestsInBenchmarkCsvFindsFakeTest(self):
    tests = {'Random fake test': {}}
    benchmarks = {
        'benchmark_name_1': BenchmarkMetadata(None, None)
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
          'hard_timeout': 7200,
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
          'hard_timeout': 7200,
          'can_use_on_swarming_builders': True,
          'expiration': 36000,
          'io_timeout': 3600,
        },
        'name': 'speedometer.reference',
        'isolate_name': 'telemetry_perf_tests',
      }
    self.assertEquals(test, expected_generated_test)

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
    benchmarks = [BlacklistedBenchmark, NotBlacklistedBenchmark]
    tests = perf_data_generator.generate_telemetry_tests(
        test_config, benchmarks, None, False, ['blacklisted'])

    generated_test_names = set(t['name'] for t in tests)
    self.assertEquals(
        generated_test_names,
        {'blacklisted', 'not_blacklisted', 'not_blacklisted.reference'})
