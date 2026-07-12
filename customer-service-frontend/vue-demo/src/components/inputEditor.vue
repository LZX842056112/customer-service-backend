<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, basicSetup } from 'codemirror'
import { json } from '@codemirror/lang-json'
import { defineProps, defineEmits } from 'vue'

// 类型定义
interface InitData {
  renderType: string
  chatMode: string
  jsonData: {
    sessionId: string
    rtcParams: any
    avatarAssets?: any
  }
  license?: string
}

// const props = defineProps<{
//   getJson: (data: InitData) => void
// }>()

const emit = defineEmits<{
  (e: 'update:json', data: InitData): void
}>()

// 状态管理
const editorRef = ref<HTMLDivElement | null>(null)
const viewRef = ref<EditorView | null>(null)

const renderType = ref<string>('cloudAvatar')
const chatMode = ref<string>('tap2talk')
const jsonData = ref<string>('{\n  "sessionId": "",\n  "rtcParams": {} \n}')
const license = ref<string>('')
const showLicense = ref<boolean>(false)
const error = ref<string>('')

// 初始化编辑器
onMounted(() => {
  const state = EditorState.create({
    doc: jsonData.value,
    extensions: [
      basicSetup,
      json(),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const newContent = viewRef.value?.state.doc.toString()
          if (newContent) {
            jsonData.value = newContent
          }
        }
      }),
    ],
  })

  const view = new EditorView({
    state,
    parent: editorRef.value!,
  })

  viewRef.value = view

  onBeforeUnmount(() => {
    view.destroy()
  })
})

// 监听 renderType 变化，控制是否显示 License
watch(
  renderType,
  (value) => {
    showLicense.value = value === 'localAvatar'
    let content = ''
    if (value === 'cloudAvatar') {
      content = '{\n  "sessionId": "",\n  "rtcParams": {} \n}'
    } else {
      content =
        '{\n  "sessionId": "",\n  "rtcParams": {},\n  "avatarAssets": {} \n}'
    }
    if (viewRef.value) {
      viewRef.value.dispatch({
        changes: {
          from: 0,
          to: viewRef.value.state.doc.length,
          insert: content,
        },
      })
    }
  },
  { immediate: true },
)

// 当 renderType、chatMode、jsonData、license 发生变化时解析并返回数据
watch(
  () => [renderType.value, chatMode.value, jsonData.value, license.value],
  () => {
    try {
      error.value = ''
      const parseJson = JSON.parse(jsonData.value)
      const result: InitData = {
        renderType: renderType.value,
        chatMode: chatMode.value,
        jsonData: parseJson,
        license: license.value || undefined,
      }
      emit('update:json', result)
    } catch (err: any) {
      console.error(err)
      error.value = 'JSON 格式错误'
    }
  },
  { deep: true, immediate: true },
)

// 渲染方式切换
const onRenderTypeChange = (value: string) => {
  renderType.value = value
}
</script>

<template>
  <div class="json-editor-container">
    <a-form layout="vertical">
      <a-form-item label="渲染方式:" class="form-item render-type-item">
        <a-radio-group
          :options="[
            { label: '云渲染', value: 'cloudAvatar' },
            { label: '端渲染', value: 'localAvatar' },
          ]"
          :value="renderType"
          optionType="button"
          buttonStyle="solid"
          @change="(e) => onRenderTypeChange(e.target.value)"
        />
      </a-form-item>

      <a-form-item label="对话模式:" class="form-item chat-mode-item">
        <a-radio-group
          :options="[
            { label: 'tap2talk', value: 'tap2talk' },
            { label: 'duplex', value: 'duplex' },
          ]"
          :value="chatMode"
          optionType="button"
          buttonStyle="solid"
          @change="(e) => (chatMode = e.target.value)"
        />
      </a-form-item>

      <a-form-item label="对话初始化参数:" class="form-item json-item">
        <div
          ref="editorRef"
          class="editor-wrapper"
          :class="{ 'has-error': error }"
        ></div>
        <span class="error-msg">{{ error }}</span>
      </a-form-item>

      <a-form-item
        v-if="showLicense"
        label="License:"
        class="form-item license-item"
      >
        <a-input
          placeholder="请输入 license"
          v-model:value="license"
          allow-clear
        />
      </a-form-item>
    </a-form>
  </div>
</template>

<style lang="less" scoped>
.json-editor-container {
  min-width: 400px;
  .form-item {
    width: 80%;
  }
  .json-item {
    .editor-wrapper {
      border: 1px solid #d9d9d9;
      border-radius: 6px;
      overflow: hidden;
      transition: all 0.3s;
      &:hover {
        border-color: #40a9ff;
      }
    }
    .has-error {
      border-color: #ff4d4f;
    }
    .error-msg {
      margin-top: 10px;
      color: red;
    }
  }
}
</style>
