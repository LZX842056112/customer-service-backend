<script setup lang="ts">
import { ref } from 'vue'
import {
  createAvatar,
  EventTypes,
  TYAvatarType,
  TYVoiceChatMessage,
  TYVoiceChatMessageType,
  TYVoiceChatState,
  TYVoiceChatMode,
  TYVolumeSourceType,
  TYError,
  TYVolume,
  TYPerformanceInfo,
  type CloudAvatar,
  type LocalAvatar,
} from 'lm-avatar-chat-sdk'
import { message, Form, Input, Button } from 'ant-design-vue'
import InputEditor from './components/InputEditor.vue'

enum IChatState {
  online = 'online',
  offline = 'offline',
}

const chatInitInfo = ref<{
  renderType: string
  chatMode: string
  sessionId: string
  rtcParams: any
  avatarAssets: any
  license: string
}>({
  renderType: 'cloudAvatar',
  chatMode: 'tap2talk',
  sessionId: '',
  rtcParams: {},
  avatarAssets: {},
  license: '',
})

const chatState = ref(IChatState.offline)
const chatAvatar = ref<CloudAvatar | LocalAvatar | undefined>(undefined)
const chatLocalMute = ref(false)

const handleJsonUpdate = (data: any) => {
  const { renderType, chatMode, jsonData, license } = data
  const { sessionId, rtcParams, avatarAssets } = jsonData
  chatInitInfo.value.renderType = renderType
  chatInitInfo.value.chatMode = chatMode
  chatInitInfo.value.sessionId = sessionId
  chatInitInfo.value.rtcParams = rtcParams
  chatInitInfo.value.avatarAssets = avatarAssets
  chatInitInfo.value.license = license
}

const startChat = () => {
  const { renderType, chatMode, sessionId, rtcParams, avatarAssets, license } =
    chatInitInfo.value
  if (!rtcParams) {
    chatState.value = IChatState.offline
    message.error('rtc初始化数据缺失')
    return false
  }

  const dialogParams = {
    mode: chatMode as TYVoiceChatMode,
  }
  const avatarInitParams = Object.assign(
    {},
    {
      rootContainer:
        renderType === TYAvatarType.cloudAvatar
          ? '#cloudPreviewer'
          : '#localPreviewer',
    },
    {
      ...rtcParams,
      sessionId,
    },
  )

  let avatar
  if (renderType === TYAvatarType.cloudAvatar) {
    avatar = createAvatar(renderType as TYAvatarType, avatarInitParams)
  } else {
    avatar = createAvatar(renderType as TYAvatarType, avatarInitParams, {
      ...avatarAssets,
      license,
    })
  }

  chatAvatar.value = avatar

  avatar.start(dialogParams)

  // 重要事件监听
  avatar.onFirstFrameReceived(() => {
    console.log('数字人渲染完成')
    chatState.value = IChatState.online
  })
  avatar.onReadyToSpeech(() => {
    console.log('可以开始对话了')
  })
  avatar.onStateChanged((tyState: TYVoiceChatState) => {
    console.log('数字人状态变化', tyState)
  })

  avatar.on(EventTypes.SpeakStarted, () => {
    console.log('用户开始说话了')
  })
  avatar.on(EventTypes.SpeakEnded, () => {
    console.log('用户结束说话了')
  })
  avatar.on(EventTypes.ResponseStarted, () => {
    console.log('数字人开始回复了')
  })
  avatar.on(EventTypes.ResponseEnded, () => {
    console.log('数字人结束回复了')
  })

  avatar.onMessageReceived((msg: TYVoiceChatMessage) => {
    if (msg.type === TYVoiceChatMessageType.speaking) {
      console.log('用户的提问', msg)
    } else {
      console.log('数字人的回复', msg)
    }
  })

  avatar.onVolumeChanged((data: TYVolume) => {
    if (data.source === TYVolumeSourceType.mic) {
      console.log('用户音量:' + data.volume)
    } else {
      console.log('数字人音量:' + data.volume)
    }
  })

  avatar.onErrorReceived((error: TYError) => {
    console.error('接收到对话错误:', error.message)
    message.error(error.message)
    if (error.terminate) {
      exitChat()
      chatState.value = IChatState.offline
    }
  })
  avatar.onPerformanceInfoTrack((info: TYPerformanceInfo) => {
    const { type, data } = info
    console.log('性能信息:', type, data)
  })
}

const exitChat = () => {
  if (chatAvatar.value) {
    chatAvatar.value.exit()
  }
  chatState.value = IChatState.offline
}

const interruptChat = () => {
  if (chatAvatar.value) {
    chatAvatar.value.interrupt()
  }
}

const toggleChatMute = () => {
  chatLocalMute.value = !chatLocalMute.value
  if (chatAvatar.value) {
    chatAvatar.value.muteLocalMic(chatLocalMute.value)
  }
}
</script>

<template>
  <div class="app-container">
    <span class="title">
      {{
        `灵眸数字人sdk调试demo${chatState === IChatState.online ? '（对话中）' : '（离线）'}`
      }}
    </span>

    <InputEditor @update:json="handleJsonUpdate" />
    <div class="chat-btn-container">
      <Button @click="startChat" type="primary"> 开始对话 </Button>
      <Button @click="exitChat" type="primary"> 结束对话 </Button>
      <Button @click="interruptChat">打断</Button>
      <Button @click="toggleChatMute">
        {{ chatLocalMute ? '取消静音' : '静音' }}
      </Button>
    </div>

    <video
      v-if="chatInitInfo.renderType === TYAvatarType.cloudAvatar"
      class="chat-video-container"
      id="cloudPreviewer"
      muted
    />
    <div v-else class="chat-local-render-container" id="localPreviewer"></div>
  </div>
</template>

<style lang="less" scoped>
.app-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 20px;
  .title {
    font-size: 20px;
    margin-bottom: 20px;
  }
  .chat-btn-container {
    display: flex;
    margin: 10px 0;
    button {
      margin: 0 10px;
    }
  }
  .chat-video-container,
  .chat-local-render-container {
    width: 500px;
    height: 500px;
    margin-top: 20px;
    object-fit: contain;
  }
}
</style>
