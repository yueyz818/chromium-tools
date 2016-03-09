// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "tools/ipc_fuzzer/message_replay/replay_process.h"

#include <limits.h>
#include <string>

#include "base/bind.h"
#include "base/command_line.h"
#include "base/files/file_path.h"
#include "base/logging.h"
#include "base/posix/global_descriptors.h"
#include "build/build_config.h"
#include "chrome/common/chrome_switches.h"
#include "content/public/common/content_switches.h"
#include "content/public/common/mojo_channel_switches.h"
#include "ipc/ipc_descriptors.h"
#include "ipc/ipc_switches.h"
#include "ipc/mojo/ipc_channel_mojo.h"
#include "mojo/edk/embedder/embedder.h"
#include "mojo/edk/embedder/platform_channel_pair.h"

#if defined(OS_POSIX)
#include "content/public/common/content_descriptors.h"
#endif

namespace ipc_fuzzer {

void InitializeMojo() {
  mojo::edk::SetMaxMessageSize(64 * 1024 * 1024);
  mojo::edk::Init();
}

void InitializeMojoIPCChannel() {
  mojo::edk::ScopedPlatformHandle platform_channel;
#if defined(OS_WIN)
  platform_channel =
      mojo::edk::PlatformChannelPair::PassClientHandleFromParentProcess(
          *base::CommandLine::ForCurrentProcess());
#elif defined(OS_POSIX)
  platform_channel.reset(mojo::edk::PlatformHandle(
      base::GlobalDescriptors::GetInstance()->Get(kMojoIPCChannel)));
#endif
  CHECK(platform_channel.is_valid());
  mojo::edk::SetParentPipeHandle(std::move(platform_channel));
}

ReplayProcess::ReplayProcess()
    : io_thread_("Chrome_ChildIOThread"),
      shutdown_event_(true, false),
      message_index_(0) {
}

ReplayProcess::~ReplayProcess() {
  channel_.reset();

  // Signal this event before shutting down the service process. That way all
  // background threads can cleanup.
  shutdown_event_.Signal();
  io_thread_.Stop();
}

bool ReplayProcess::Initialize(int argc, const char** argv) {
  base::CommandLine::Init(argc, argv);

  if (!base::CommandLine::ForCurrentProcess()->HasSwitch(
          switches::kIpcFuzzerTestcase)) {
    LOG(ERROR) << "This binary shouldn't be executed directly, "
               << "please use tools/ipc_fuzzer/scripts/play_testcase.py";
    return false;
  }

  // Log to both stderr and file destinations.
  logging::SetMinLogLevel(logging::LOG_ERROR);
  logging::LoggingSettings settings;
  settings.logging_dest = logging::LOG_TO_ALL;
  settings.log_file = FILE_PATH_LITERAL("ipc_replay.log");
  logging::InitLogging(settings);

  // Make sure to initialize Mojo before starting the IO thread.
  InitializeMojo();

  io_thread_.StartWithOptions(
      base::Thread::Options(base::MessageLoop::TYPE_IO, 0));

#if defined(OS_POSIX)
  base::GlobalDescriptors* g_fds = base::GlobalDescriptors::GetInstance();
  g_fds->Set(kPrimaryIPCChannel,
             kPrimaryIPCChannel + base::GlobalDescriptors::kBaseDescriptor);
  g_fds->Set(kMojoIPCChannel,
             kMojoIPCChannel + base::GlobalDescriptors::kBaseDescriptor);
#endif

  mojo_ipc_support_.reset(new IPC::ScopedIPCSupport(io_thread_.task_runner()));
  InitializeMojoIPCChannel();

  return true;
}

void ReplayProcess::OpenChannel() {
  // TODO(morrita): As the adoption of ChannelMojo spreads, this
  // criteria has to be updated.
  std::string process_type =
      base::CommandLine::ForCurrentProcess()->GetSwitchValueASCII(
          switches::kProcessType);
  bool should_use_mojo = process_type == switches::kRendererProcess &&
                         content::ShouldUseMojoChannel();
  if (should_use_mojo) {
    std::string token =
        base::CommandLine::ForCurrentProcess()->GetSwitchValueASCII(
            switches::kMojoChannelToken);
    channel_ = IPC::ChannelProxy::Create(
        IPC::ChannelMojo::CreateClientFactory(token), this,
        io_thread_.task_runner());
  } else {
    std::string channel_name =
        base::CommandLine::ForCurrentProcess()->GetSwitchValueASCII(
            switches::kProcessChannelID);
    channel_ =
        IPC::ChannelProxy::Create(channel_name, IPC::Channel::MODE_CLIENT, this,
                                  io_thread_.task_runner());
  }
}

bool ReplayProcess::OpenTestcase() {
  base::FilePath path =
      base::CommandLine::ForCurrentProcess()->GetSwitchValuePath(
          switches::kIpcFuzzerTestcase);
  return MessageFile::Read(path, &messages_);
}

void ReplayProcess::SendNextMessage() {
  if (message_index_ >= messages_.size()) {
    base::MessageLoop::current()->QuitWhenIdle();
    return;
  }

  // Take next message and release it from vector.
  IPC::Message* message = messages_[message_index_];
  messages_[message_index_++] = NULL;

  if (!channel_->Send(message)) {
    LOG(ERROR) << "ChannelProxy::Send() failed after "
               << message_index_ << " messages";
    base::MessageLoop::current()->QuitWhenIdle();
  }
}

void ReplayProcess::Run() {
  timer_.reset(new base::Timer(false, true));
  timer_->Start(FROM_HERE,
                base::TimeDelta::FromMilliseconds(1),
                base::Bind(&ReplayProcess::SendNextMessage,
                           base::Unretained(this)));
  base::MessageLoop::current()->Run();
}

bool ReplayProcess::OnMessageReceived(const IPC::Message& msg) {
  return true;
}

void ReplayProcess::OnChannelError() {
  LOG(ERROR) << "Channel error, quitting after "
             << message_index_ << " messages";
  base::MessageLoop::current()->QuitWhenIdle();
}

}  // namespace ipc_fuzzer
