# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import glob
import heapq
import logging
import os
import subprocess as subprocess
import shutil
import sys
import tempfile
import time

from telemetry.core import util
from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import chrome_browser_backend

class DesktopBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  """The backend for controlling a locally-executed browser instance, on Linux,
  Mac or Windows.
  """
  def __init__(self, options, executable, flash_path, is_content_shell,
               browser_directory, delete_profile_dir_after_run=True):
    super(DesktopBrowserBackend, self).__init__(
        is_content_shell=is_content_shell,
        supports_extensions=not is_content_shell,
        options=options)

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._proc = None
    self._tmp_profile_dir = None
    self._tmp_output_file = None

    self._executable = executable
    if not self._executable:
      raise Exception('Cannot create browser, no executable found!')

    self._flash_path = flash_path
    if self._flash_path and not os.path.exists(self._flash_path):
      logging.warning(('Could not find flash at %s. Running without flash.\n\n'
                       'To fix this see http://go/read-src-internal') %
                      self._flash_path)
      self._flash_path = None

    if len(options.extensions_to_load) > 0 and is_content_shell:
      raise browser_backend.ExtensionsNotSupportedException(
          'Content shell does not support extensions.')

    self._browser_directory = browser_directory
    self._port = util.GetAvailableLocalPort()
    self._profile_dir = None
    self._supports_net_benchmarking = True
    self._delete_profile_dir_after_run = delete_profile_dir_after_run
    self._tmp_minidump_dir = tempfile.mkdtemp()

    self._SetupProfile()

  def _SetupProfile(self):
    if not self.options.dont_override_profile:
      self._tmp_profile_dir = tempfile.mkdtemp()
      profile_dir = self._profile_dir or self.options.profile_dir
      if profile_dir:
        if self.is_content_shell:
          logging.critical('Profiles cannot be used with content shell')
          sys.exit(1)
        shutil.rmtree(self._tmp_profile_dir)
        shutil.copytree(profile_dir, self._tmp_profile_dir)

  def _LaunchBrowser(self):
    args = [self._executable]
    args.extend(self.GetBrowserStartupArgs())
    env = os.environ.copy()
    env['CHROME_HEADLESS'] = '1'  # Don't upload minidumps.
    env['BREAKPAD_DUMP_LOCATION'] = self._tmp_minidump_dir
    if not self.options.show_stdout:
      self._tmp_output_file = tempfile.NamedTemporaryFile('w', 0)
      self._proc = subprocess.Popen(
          args, stdout=self._tmp_output_file, stderr=subprocess.STDOUT, env=env)
    else:
      self._proc = subprocess.Popen(args, env=env)

    try:
      self._WaitForBrowserToComeUp()
      self._PostBrowserStartupInitialization()
    except:
      self.Close()
      raise

  def GetBrowserStartupArgs(self):
    args = super(DesktopBrowserBackend, self).GetBrowserStartupArgs()
    args.append('--remote-debugging-port=%i' % self._port)
    args.append('--enable-crash-reporter-for-testing')
    if not self.is_content_shell:
      args.append('--window-size=1280,1024')
      if self._flash_path:
        args.append('--ppapi-flash-path=%s' % self._flash_path)
      if self._supports_net_benchmarking:
        args.append('--enable-net-benchmarking')
      else:
        args.append('--enable-benchmarking')
      if not self.options.dont_override_profile:
        args.append('--user-data-dir=%s' % self._tmp_profile_dir)
    return args

  def SetProfileDirectory(self, profile_dir):
    # Make sure _profile_dir hasn't already been set.
    assert self._profile_dir is None

    if self.is_content_shell:
      logging.critical('Profile creation cannot be used with content shell')
      sys.exit(1)

    self._profile_dir = profile_dir

  def Start(self):
    self._LaunchBrowser()

    # For old chrome versions, might have to relaunch to have the
    # correct net_benchmarking switch.
    if self._chrome_branch_number < 1418:
      self.Close()
      self._supports_net_benchmarking = False
      self._LaunchBrowser()

  @property
  def pid(self):
    if self._proc:
      return self._proc.pid
    return None

  @property
  def browser_directory(self):
    return self._browser_directory

  @property
  def profile_directory(self):
    return self._tmp_profile_dir

  def IsBrowserRunning(self):
    return self._proc.poll() == None

  def GetStandardOutput(self):
    assert self._tmp_output_file, "Can't get standard output with show_stdout"
    self._tmp_output_file.flush()
    try:
      with open(self._tmp_output_file.name) as f:
        return f.read()
    except IOError:
      return ''

  def GetStackTrace(self):
    executable_dir = os.path.dirname(self._executable)
    stackwalk = os.path.join(executable_dir, 'minidump_stackwalk')
    if not os.path.exists(stackwalk):
      logging.warning('minidump_stackwalk binary not found. Must build it to '
                      'symbolize crash dumps. Returning browser stdout.')
      return self.GetStandardOutput()

    dumps = glob.glob(os.path.join(self._tmp_minidump_dir, '*.dmp'))
    if not dumps:
      logging.warning('No crash dump found. Returning browser stdout.')
      return self.GetStandardOutput()
    most_recent_dump = heapq.nlargest(1, dumps, os.path.getmtime)[0]
    if os.path.getmtime(most_recent_dump) < (time.time() - (5 * 60)):
      logging.warn('Crash dump is older than 5 minutes. May not be correct.')

    minidump = most_recent_dump + '.stripped'
    with open(most_recent_dump, 'rb') as infile:
      with open(minidump, 'wb') as outfile:
        outfile.write(''.join(infile.read().partition('MDMP')[1:]))

    symbols = glob.glob(os.path.join(executable_dir, 'chrome.breakpad.*'))[0]
    if not symbols:
      logging.warning('No breakpad symbols found. Returning browser stdout.')
      return self.GetStandardOutput()

    symbols_path = os.path.join(self._tmp_minidump_dir, 'symbols')
    with open(symbols, 'r') as f:
      _, _, _, sha, binary = f.readline().split()
    symbol_path = os.path.join(symbols_path, binary, sha)
    os.makedirs(symbol_path)
    shutil.copyfile(symbols, os.path.join(symbol_path, binary + '.sym'))

    error = tempfile.NamedTemporaryFile('w', 0)
    return subprocess.Popen(
        [stackwalk, minidump, symbols_path],
        stdout=subprocess.PIPE, stderr=error).communicate()[0]

  def __del__(self):
    self.Close()

  def Close(self):
    super(DesktopBrowserBackend, self).Close()

    if self._proc:

      def IsClosed():
        if not self._proc:
          return True
        return self._proc.poll() != None

      # Try to politely shutdown, first.
      self._proc.terminate()
      try:
        util.WaitFor(IsClosed, timeout=1)
        self._proc = None
      except util.TimeoutException:
        pass

      # Kill it.
      if not IsClosed():
        self._proc.kill()
        try:
          util.WaitFor(IsClosed, timeout=5)
          self._proc = None
        except util.TimeoutException:
          self._proc = None
          raise Exception('Could not shutdown the browser.')

    if self._delete_profile_dir_after_run and \
        self._tmp_profile_dir and os.path.exists(self._tmp_profile_dir):
      shutil.rmtree(self._tmp_profile_dir, ignore_errors=True)
      self._tmp_profile_dir = None

    if self._tmp_output_file:
      self._tmp_output_file.close()
      self._tmp_output_file = None

  def CreateForwarder(self, *port_pairs):
    return browser_backend.DoNothingForwarder(*port_pairs)
