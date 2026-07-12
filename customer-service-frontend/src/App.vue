<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  createAvatar,
  TYAvatarType,
  TYVoiceChatMode,
  IAvatarAudioFormat,
  IRequestToRespondType,
} from 'lm-avatar-chat-sdk'

// 数字人对话模式开关:
//   true  = "复刻文本" 模式 (推荐): 用 avatar.requestToRespond(transcript, text)
//           让灵眸服务端 TTS + 唇形一条龙渲染, 前端不推 PCM, 也不本地播放.
//           适用于实例类型是 "2D对话" / 普通云渲项目.
//   false = "音频驱动" 模式: 前端 CosyVoice TTS + pushAudioData 驱动唇形.
//           只对实例类型是 "2D云渲音频驱动" 的灵眸项目有效, SDK 文档明确说明.
const USE_TRANSCRIPT_MODE = true

const senderId = ref('u1001')
const draftMessage = ref('')
const isSending = ref(false)
const errorMessage = ref('')
const messages = ref([])
const messagesContainer = ref(null)
const loadedHistoryCount = ref(0)
const currentPageDividerInserted = ref(false)

const orders = ref([])
const products = ref([])
const isLoadingSidebar = ref(false)
const sidebarError = ref('')
const activeTab = ref('orders')

// Copy state
const copyState = ref({})

// ── 数字人(云渲染-音频驱动) ────────────────────────────────────────────
const avatarState = ref('idle') // idle | waiting-gesture | connecting | ready | error
const avatarErrorMessage = ref('')
const wsState = ref('idle') // idle | connecting | open | closed | error
let avatarInstance = null
let avatarSessionData = null
let avatarReady = false // onReadyToSpeech 后才允许 pushAudioData
let avatarReadyPromise = null
let avatarReadyResolve = null
let chatSocket = null
let pendingTurn = null // { messageId, resolve, reject, audioChunks }
let pendingSetupAfterGesture = false

// SDK pushAudioData 缓冲 (仅在 USE_TRANSCRIPT_MODE=false 时使用)
const SDK_PUSH_BATCH_SAMPLES = 16000 // 1s @ 16kHz
let pendingPushChunks = []
let pendingPushSamples = 0

// transcript 模式: bot_text 拿到后塞队列, 监听数字人状态, 处于 Idle/Listening 才能调 requestToRespond
let transcriptQueue = []
let transcriptInFlight = false
let transcriptSawActiveState = false
let avatarState_TY = '' // 来自 onStateChanged 回调, "StandBy" | "Idle" | "Listening" | "Thinking" | "Responding"

function clearTranscriptQueue() {
  transcriptQueue = []
  transcriptInFlight = false
  transcriptSawActiveState = false
}

function flushTranscriptQueue() {
  if (!USE_TRANSCRIPT_MODE) return
  if (!avatarInstance || !avatarReady) return
  if (transcriptInFlight) return
  // 数字人只有 Idle 或 Listening 状态接受 requestToRespond
  if (avatarState_TY !== 'Idle' && avatarState_TY !== 'Listening') return
  if (transcriptQueue.length === 0) return
  const text = transcriptQueue[0]
  transcriptInFlight = true
  transcriptSawActiveState = false
  try {
    avatarInstance.requestToRespond(IRequestToRespondType.transcript, text)
    transcriptQueue.shift()
    console.log('[avatar] requestToRespond transcript:', text.slice(0, 30))
  } catch (e) {
    transcriptInFlight = false
    transcriptSawActiveState = false
    console.warn('[avatar] requestToRespond failed:', e)
  }
}

function clearPendingPush() {
  pendingPushChunks = []
  pendingPushSamples = 0
}

function takeInt16FromQueue(queue, n) {
  const out = new Int16Array(n)
  let filled = 0
  while (filled < n && queue.length > 0) {
    const head = queue[0]
    const need = n - filled
    if (head.length <= need) {
      out.set(head, filled)
      filled += head.length
      queue.shift()
    } else {
      out.set(head.subarray(0, need), filled)
      queue[0] = head.subarray(need)
      filled += need
    }
  }
  return out
}

function concatAllInt16(queue, totalSamples) {
  const out = new Int16Array(totalSamples)
  let off = 0
  for (const c of queue) {
    out.set(c, off)
    off += c.length
  }
  return out
}

// ── 浏览器端 PCM 流式播放器 (SDK 的 pushAudioData 只驱动口型, 不放音) ─────
class PcmStreamPlayer {
  constructor() {
    this.ctx = null
    this.nextTime = 0
    this.sources = new Set()
  }
  ensureCtx() {
    if (!this.ctx) {
      const Ctor = window.AudioContext || window.webkitAudioContext
      this.ctx = new Ctor()
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {})
    }
    if (this.nextTime < this.ctx.currentTime) {
      this.nextTime = this.ctx.currentTime + 0.02 // 留一点点缓冲
    }
  }
  push(int16, sampleRate) {
    if (!int16 || !int16.length) return
    this.ensureCtx()
    const ctx = this.ctx
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) {
      const v = int16[i]
      float32[i] = v < 0 ? v / 0x8000 : v / 0x7fff
    }
    const buf = ctx.createBuffer(1, float32.length, sampleRate)
    buf.copyToChannel(float32, 0)
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    src.start(this.nextTime)
    this.sources.add(src)
    src.onended = () => this.sources.delete(src)
    this.nextTime += buf.duration
  }
  stop() {
    for (const src of this.sources) {
      try { src.stop() } catch (_) { /* ignore */ }
    }
    this.sources.clear()
    if (this.ctx) this.nextTime = this.ctx.currentTime
  }
}
const pcmPlayer = new PcmStreamPlayer()

// ── Canvas 粒子背景系统 ──────────────────────────────────────────────
const bgCanvas = ref(null)
let animFrameId = null
let bgParticles = []
const BG_PARTICLE_COUNT = 80
const BG_CONNECT_DIST = 150
const BG_MOUSE_RADIUS = 180
const bgMouse = { x: null, y: null }

function createBgParticles(w, h) {
  const palette = [
    [13, 148, 136], [20, 184, 166], [245, 158, 11],
    [217, 119, 6], [2, 132, 199], [56, 189, 248],
  ]
  bgParticles = Array.from({ length: BG_PARTICLE_COUNT }, () => {
    const color = palette[Math.floor(Math.random() * palette.length)]
    return {
      x: Math.random() * w, y: Math.random() * h,
      size: Math.random() * 2.5 + 1,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      color, opacity: Math.random() * 0.45 + 0.12,
      phase: Math.random() * Math.PI * 2,
      pulse: Math.random() * 0.015 + 0.005,
    }
  })
}

function animateBg(ctx, w, h, time) {
  ctx.clearRect(0, 0, w, h)

  for (const p of bgParticles) {
    p.x += p.vx + Math.sin(time * 0.001 + p.phase) * 0.25
    p.y += p.vy + Math.cos(time * 0.001 + p.phase + 1) * 0.25

    if (bgMouse.x !== null) {
      const dx = p.x - bgMouse.x, dy = p.y - bgMouse.y
      const dist = Math.hypot(dx, dy)
      if (dist < BG_MOUSE_RADIUS) {
        const force = (BG_MOUSE_RADIUS - dist) / BG_MOUSE_RADIUS
        p.x += (dx / dist) * force * 0.7
        p.y += (dy / dist) * force * 0.7
      }
    }

    if (p.x < -20) p.x = w + 20; if (p.x > w + 20) p.x = -20
    if (p.y < -20) p.y = h + 20; if (p.y > h + 20) p.y = -20
  }

  // 连线
  ctx.lineWidth = 0.5
  for (let i = 0; i < bgParticles.length; i++) {
    for (let j = i + 1; j < bgParticles.length; j++) {
      const dx = bgParticles[i].x - bgParticles[j].x
      const dy = bgParticles[i].y - bgParticles[j].y
      const dist = Math.hypot(dx, dy)
      if (dist < BG_CONNECT_DIST) {
        const alpha = (1 - dist / BG_CONNECT_DIST) * 0.1
        ctx.strokeStyle = `rgba(13,148,136,${alpha})`
        ctx.beginPath()
        ctx.moveTo(bgParticles[i].x, bgParticles[i].y)
        ctx.lineTo(bgParticles[j].x, bgParticles[j].y)
        ctx.stroke()
      }
    }
  }

  // 粒子光晕
  for (const p of bgParticles) {
    const pulse = 1 + Math.sin(time * p.pulse + p.phase) * 0.25
    const r = p.size * pulse
    const [cr, cg, cb] = p.color

    ctx.beginPath()
    ctx.arc(p.x, p.y, r * 2.5, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${cr},${cg},${cb},${p.opacity * 0.08})`
    ctx.fill()

    ctx.beginPath()
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${cr},${cg},${cb},${p.opacity * 0.7})`
    ctx.fill()
  }
}

function initBg() {
  const canvas = bgCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')

  const resize = () => {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    createBgParticles(canvas.width, canvas.height)
  }
  resize()
  window.addEventListener('resize', resize)

  const onMouseMove = (e) => { bgMouse.x = e.clientX; bgMouse.y = e.clientY }
  const onMouseLeave = () => { bgMouse.x = null; bgMouse.y = null }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseleave', onMouseLeave)

  const loop = (time) => {
    animateBg(ctx, canvas.width, canvas.height, time)
    animFrameId = requestAnimationFrame(loop)
  }
  animFrameId = requestAnimationFrame(loop)

  canvas._cleanup = () => {
    cancelAnimationFrame(animFrameId)
    window.removeEventListener('resize', resize)
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseleave', onMouseLeave)
  }
}
// ── 粒子背景系统结束 ──────────────────────────────────────────────────

// 客服数字人配置
const customerService = {
  name: '小雨',
  title: '金牌客服',
  avatar: 'https://1234study.oss-cn-shenzhen.aliyuncs.com/%E5%AE%A2%E6%9C%8D.png',
  status: '在线'
}

// 用户配置
const userProfile = {
  name: '你',
  avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=user&backgroundColor=c0aede'
}

// 将消息分组为 Turn 结构
const turns = computed(() => {
  const result = []
  let currentTurn = null
  let turnIndex = 0

  for (const message of messages.value) {
    if (message.type === 'divider') {
      if (currentTurn) {
        result.push(currentTurn)
        currentTurn = null
      }
      result.push({
        type: 'divider',
        text: message.text
      })
      continue
    }

    if (message.role === 'user') {
      // 如果有待处理的当前 turn，先保存
      if (currentTurn) {
        result.push(currentTurn)
      }
      // 创建新的 turn
      turnIndex++
      currentTurn = {
        type: 'turn',
        id: `turn-${turnIndex}`,
        index: turnIndex,
        userMessage: message,
        botMessages: []
      }
    } else if (message.role === 'bot') {
      if (!currentTurn) {
        // 如果没有当前 turn，创建一个（可能是因为历史消息）
        turnIndex++
        currentTurn = {
          type: 'turn',
          id: `turn-${turnIndex}`,
          index: turnIndex,
          userMessage: null,
          botMessages: []
        }
      }
      currentTurn.botMessages.push(message)
    }
  }

  if (currentTurn) {
    result.push(currentTurn)
  }

  return result
})

const chatEndpoint = computed(() => '/api/chat')
const chatHistoryEndpoint = computed(
  () => `/api/chat/history?sender_id=${encodeURIComponent(senderId.value.trim())}`
)
const commerceOrdersEndpoint = computed(
  () => `/commerce/users/${encodeURIComponent(senderId.value.trim())}/orders`
)
const commerceProductsEndpoint = computed(
  () => `/commerce/users/${encodeURIComponent(senderId.value.trim())}/products`
)

function createBaseMessage(role) {
  return {
    id: crypto.randomUUID(),
    role,
    buttons: [],
  }
}

function insertCurrentPageDividerIfNeeded() {
  if (currentPageDividerInserted.value || loadedHistoryCount.value === 0) {
    return
  }

  appendMessage('divider', { text: '以上为历史消息' })
  currentPageDividerInserted.value = true
}

function appendUserText(text) {
  insertCurrentPageDividerIfNeeded()
  messages.value.push({
    ...createBaseMessage('user'),
    type: 'text',
    text,
  })
}

function appendUserObject(objectType, payload) {
  insertCurrentPageDividerIfNeeded()
  messages.value.push({
    ...createBaseMessage('user'),
    type: 'object',
    objectType,
    payload,
  })
}

function appendBotMessages(botMessages) {
  for (const message of botMessages) {
    appendMessage('bot', message)
  }
}

function appendMessage(role, message) {
  if (role === 'divider') {
    messages.value.push({
      ...createBaseMessage('divider'),
      type: 'divider',
      text: message.text ?? '以上为历史消息',
    })
    return
  }

  if (message.object) {
    messages.value.push({
      ...createBaseMessage(role),
      type: 'object',
      objectType: message.object.type,
      payload: message.object,
    })
  } else {
    messages.value.push({
      ...createBaseMessage(role),
      type: 'text',
      text: message.text ?? '',
      suggestions: message.suggestions ?? null,
    })
  }
}

function setHistoryMessages(historyMessages) {
  messages.value = []
  currentPageDividerInserted.value = false
  for (const message of historyMessages) {
    if (message.role === 'divider') {
      continue
    }
    const role = ['user', 'bot'].includes(message.role) ? message.role : 'bot'
    appendMessage(role, message)
  }
  loadedHistoryCount.value = messages.value.length
}

async function scrollToBottom() {
  await nextTick()
  const container = messagesContainer.value
  if (!container) {
    return
  }
  container.scrollTop = container.scrollHeight
}

watch(
  () => messages.value.length,
  async () => {
    await scrollToBottom()
  }
)

function resetConversation() {
  messages.value = []
  loadedHistoryCount.value = 0
  currentPageDividerInserted.value = false
  errorMessage.value = ''
}

function formatAmount(amount) {
  const numericAmount = Number(amount)
  if (Number.isNaN(numericAmount)) {
    return '￥0.00'
  }
  return `￥${numericAmount.toFixed(2)}`
}

function formatOrderSummary(order) {
  return order.status ? `订单状态：${order.status}` : '订单'
}

const ORDER_STATUS_CLASS = {
  '待发货': 'status-warning',
  '待揽收': 'status-warning',
  '运输中': 'status-info',
  '派送中': 'status-info',
  '已完成': 'status-success',
  '已签收': 'status-success',
  '已取消': 'status-muted',
  '退款中': 'status-danger',
  '已退款': 'status-muted',
}

function getStatusClass(status) {
  return ORDER_STATUS_CLASS[status] || 'status-muted'
}

function formatProductSummary(product) {
  if (product.description) {
    return product.description
  }
  if (product.attributes?.price) {
    return `商品价格：${formatAmount(product.attributes.price)}`
  }
  return '商品信息'
}

function getObjectTitle(message) {
  const payload = message.payload ?? {}
  if (payload.title) {
    return payload.title
  }
  return message.objectType === 'order' ? '订单对象' : '商品对象'
}

function getObjectIdentifier(message) {
  const payload = message.payload ?? {}
  const id = payload.order_id ?? payload.product_id ?? payload.id
  const label = message.objectType === 'order' ? '订单号' : '商品号'
  return id ? `${label}：${id}` : label
}

function getObjectSummary(message) {
  const payload = message.payload ?? {}
  if (message.objectType === 'order') {
    const status = payload.status ?? payload.attributes?.status
    return status ? `订单状态：${status}` : '订单'
  }
  return formatProductSummary(payload)
}

function getObjectAmount(message) {
  const payload = message.payload ?? {}
  const amount = message.objectType === 'order'
    ? payload.amount ?? payload.attributes?.amount
    : payload.price ?? payload.attributes?.price
  return formatAmount(amount)
}

async function fetchSidebarData() {
  const currentSenderId = senderId.value.trim()
  orders.value = []
  products.value = []
  sidebarError.value = ''

  if (!currentSenderId) {
    return
  }

  isLoadingSidebar.value = true
  try {
    const [ordersResponse, productsResponse] = await Promise.all([
      fetch(commerceOrdersEndpoint.value),
      fetch(commerceProductsEndpoint.value),
    ])

    const [ordersPayload, productsPayload] = await Promise.all([
      ordersResponse.json(),
      productsResponse.json(),
    ])

    if (!ordersResponse.ok) {
      throw new Error(ordersPayload.detail || '加载订单列表失败。')
    }
    if (!productsResponse.ok) {
      throw new Error(productsPayload.detail || '加载商品列表失败。')
    }

    orders.value = Array.isArray(ordersPayload?.data?.orders) ? ordersPayload.data.orders : []
    products.value = Array.isArray(productsPayload?.data?.products) ? productsPayload.data.products : []
  } catch (error) {
    sidebarError.value = error instanceof Error ? error.message : '加载右侧列表失败。'
  } finally {
    isLoadingSidebar.value = false
  }
}

async function fetchChatHistory() {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    messages.value = []
    return
  }

  try {
    const response = await fetch(chatHistoryEndpoint.value)
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || '加载历史消息失败。')
    }
    if (currentSenderId === senderId.value.trim()) {
      setHistoryMessages(Array.isArray(data?.messages) ? data.messages : [])
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载历史消息失败。'
  }
}

async function sendPayload(payload) {
  if (isSending.value) {
    return
  }

  errorMessage.value = ''
  isSending.value = true

  try {
    // 纯文本走 WS, 配合数字人音频驱动; object 类型仍走 HTTP
    if (payload && payload.text && !payload.object) {
      if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        // 数字人未就绪时, 优雅退回 HTTP, 至少保证文字回复可用
        await sendPayloadHttp(payload)
      } else {
        const messageId = crypto.randomUUID()
        await sendOverSocket(payload.text, messageId)
      }
    } else {
      await sendPayloadHttp(payload)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败。'
  } finally {
    isSending.value = false
  }
}

async function sendPayloadHttp(payload) {
  const response = await fetch(chatEndpoint.value, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      sender_id: senderId.value.trim(),
      ...payload,
    }),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || '请求失败。')
  }

  appendBotMessages(data.messages ?? [])
}

async function sendSuggestion(text) {
  appendUserText(text)
  await sendPayload({ text })
}

async function sendQuickText(text) {
  draftMessage.value = text
  await sendTextMessage()
}
async function sendTextMessage() {
  const text = draftMessage.value.trim()
  const currentSenderId = senderId.value.trim()

  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }
  if (!text) {
    return
  }

  draftMessage.value = ''
  appendUserText(text)
  await sendPayload({ text })
}

async function sendOrder(order) {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }

  appendUserObject('order', { ...order })
  await sendPayload({
    object: {
      type: 'order',
      id: order.order_id,
      title: order.title,
      attributes: {
        status: order.status,
        amount: order.amount,
        created_at: order.created_at,
        cover_url: order.cover_url,
      },
    },
  })
}

async function sendProduct(product) {
  const currentSenderId = senderId.value.trim()
  if (!currentSenderId) {
    errorMessage.value = '请先输入 sender_id。'
    return
  }

  appendUserObject('product', { ...product })
  await sendPayload({
    object: {
      type: 'product',
      id: product.product_id,
      title: product.title,
      attributes: {
        price: product.price,
        cover_url: product.cover_url,
        description: product.description,
      },
    },
  })
}

watch(
  () => senderId.value.trim(),
  async (value, previousValue) => {
    if (value === previousValue) {
      return
    }

    // 注意: sender_id 切换故意 *不* 重建数字人。原因:
    //   1) 数字人代表客服角色 "小雨", 与终端用户身份无关, 不该因换用户而重连
    //   2) 阿里 RTC engine 是 singleton 且有 85s 自动重连机制, avatar.exit() 后
    //      引擎仍在尝试重连旧频道, 立即建新会话会 "cannot set channel profile in call"
    //      表现为 "会话已被管理员关闭" / "连接失败"
    //   3) WS 也不绑定 sender_id, 每条 user_text 消息自带 sender_id, 复用即可
    // 所以切换 sender_id 只刷历史 + 侧边栏, 数字人和 WS 都保持不动.
    resetConversation()
    if (!value) {
      orders.value = []
      products.value = []
      return
    }
    await Promise.all([fetchSidebarData(), fetchChatHistory()])
  }
)

function handleBeforeUnload() {
  // 浏览器刷新/关闭时同步释放数字人会话, 防止公共实例并发位被吃光
  if (avatarInstance) {
    try { avatarInstance.exit() } catch (_) { /* ignore */ }
  }
  const releaseSid = avatarSessionData && avatarSessionData.deviceId
  if (releaseSid) {
    releaseAvatarSession(releaseSid, { keepalive: true })
  }
}

// 浏览器自动播放策略: 必须在用户手势(click/keydown)之后才能起音频
function hasUserActivation() {
  if (typeof navigator === 'undefined') return true
  if (!navigator.userActivation) return false
  return navigator.userActivation.hasBeenActive === true
}

function ensureSetupAfterGesture() {
  if (avatarInstance || pendingSetupAfterGesture) return
  if (hasUserActivation()) {
    setupAvatar()
    return
  }
  pendingSetupAfterGesture = true
  avatarState.value = 'waiting-gesture'

  const trigger = () => {
    if (!pendingSetupAfterGesture) return
    pendingSetupAfterGesture = false
    window.removeEventListener('pointerdown', trigger, true)
    window.removeEventListener('keydown', trigger, true)
    setupAvatar()
  }
  window.addEventListener('pointerdown', trigger, true)
  window.addEventListener('keydown', trigger, true)
}

onMounted(async () => {
  initBg()
  window.addEventListener('beforeunload', handleBeforeUnload)
  ensureSetupAfterGesture()
  await Promise.all([fetchSidebarData(), fetchChatHistory()])
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  if (bgCanvas.value?._cleanup) bgCanvas.value._cleanup()
  // 组件卸载: 不 await release, 让 fetch keepalive 把 DELETE 送出去就行
  teardownAvatar({ awaitRelease: false })
})

async function fetchAvatarSession(sid) {
  // 解析后端返回, 兼容非 JSON 错误体 (如 500 的 "Internal Server Error")
  const url = `/api/avatar/session?sender_id=${encodeURIComponent(sid)}`
  const response = await fetch(url)
  const text = await response.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch (_) { /* keep null */ }
  if (!response.ok) {
    const msg = (data && (data.detail || data.message)) || text || `HTTP ${response.status}`
    const e = new Error(msg)
    e.status = response.status
    throw e
  }
  return data
}

async function setupAvatar() {
  if (avatarInstance) return
  const sid = senderId.value.trim()
  if (!sid) return

  avatarState.value = 'connecting'
  avatarErrorMessage.value = ''
  try {
    let data
    try {
      data = await fetchAvatarSession(sid)
    } catch (e) {
      // 并发超限/挂起会话占满时, 主动调用清扫接口再重试一次
      const concurrent = /并发|HA1511|concurrency/i.test(e.message || '')
      if (concurrent || e.status >= 500) {
        console.warn('[avatar] first attempt failed, cleaning up & retrying:', e.message)
        try { await fetch('/api/avatar/sessions/cleanup', { method: 'POST' }) } catch (_) { /* ignore */ }
        data = await fetchAvatarSession(sid)
      } else {
        throw e
      }
    }
    // 记下创建该 session 时用的 device_id (sender_id), 卸载时拿这个值去 DELETE,
    // 而不是 senderId.value, 否则 sender_id 切换之后 DELETE 找不到对应缓存项, 旧 session 会泄漏
    avatarSessionData = { ...data, deviceId: sid }
    avatarReady = false
    avatarReadyPromise = new Promise((resolve) => { avatarReadyResolve = resolve })

    const avatar = createAvatar(TYAvatarType.cloudAvatar, {
      rootContainer: '#cloudAvatarContainer',
      ...data.rtcParams,
      sessionId: data.sessionId,
      ignoreAudioInput: true,
    })
    avatarInstance = avatar
    // 关键: 告诉 SDK 我们用 s16 PCM + 16kHz, 否则 pushAudioData 推进来的 PCM 不会被识别
    avatar.start({
      mode: TYVoiceChatMode.tap2talk,
      avatarAudioFormat: IAvatarAudioFormat.s16,
      outboundSampleRate: 16000,
    })

    avatar.onFirstFrameReceived(() => {
      avatarState.value = 'ready'
      console.log('[avatar] first frame received')
    })
    avatar.onReadyToSpeech(() => {
      avatarReady = true
      if (avatarReadyResolve) {
        avatarReadyResolve()
        avatarReadyResolve = null
      }
      console.log('[avatar] ready to speech (dataChannel up)')
    })
    avatar.onStateChanged((state) => {
      console.log('[avatar] state:', state)
      avatarState_TY = state
      if (state === 'Thinking' || state === 'Responding') {
        transcriptSawActiveState = true
      }
      if ((state === 'Idle' || state === 'Listening') && transcriptInFlight && transcriptSawActiveState) {
        transcriptInFlight = false
        transcriptSawActiveState = false
      }
      // 状态切回 Idle/Listening 时尝试把 transcript 队列里堆积的下一条推给 SDK
      flushTranscriptQueue()
    })
    avatar.onErrorReceived((err) => {
      console.error('[avatar] error:', err)
      avatarErrorMessage.value = err?.message || '数字人异常'
      if (err?.terminate) {
        teardownAvatar()
        avatarState.value = 'error'
      }
    })

    openChatSocket()
  } catch (e) {
    console.error('setupAvatar failed:', e)
    avatarState.value = 'error'
    avatarErrorMessage.value = e instanceof Error ? e.message : String(e)
  }
}

async function teardownAvatar({ awaitRelease = false } = {}) {
  closeChatSocket()
  pcmPlayer.stop()
  clearPendingPush()
  clearTranscriptQueue()
  avatarState_TY = ''
  if (avatarInstance) {
    try {
      avatarInstance.exit()
    } catch (e) {
      console.warn('avatar.exit() failed:', e)
    }
    avatarInstance = null
  }
  // 通知后端释放并发位 (会话缓存). 必须用 setup 时绑定的 deviceId, 不是当前 senderId.value
  const previousSession = avatarSessionData
  avatarSessionData = null
  avatarState.value = 'idle'
  const releaseSid = previousSession && previousSession.deviceId
  if (releaseSid) {
    const p = releaseAvatarSession(releaseSid, { keepalive: !awaitRelease })
    if (awaitRelease) {
      // 等到 DELETE 完成才返回, 给灵眸服务端时间真正释放并发位
      try { await p } catch (_) { /* best effort */ }
    }
  }
}

function releaseAvatarSession(sid, { keepalive = false } = {}) {
  const url = `/api/avatar/session?sender_id=${encodeURIComponent(sid)}`
  // keepalive=true: 浏览器卸载/刷新场景, 让请求即使页面关闭也能发出
  // keepalive=false + 返回 Promise: 用于在切换 sender_id 这种 in-app 场景下 await 释放
  return fetch(url, { method: 'DELETE', keepalive }).catch((e) => {
    console.warn('releaseAvatarSession failed:', e)
  })
}

// ── 聊天 WebSocket: 文本回复 + PCM 音频帧 ──────────────────────────────
function openChatSocket() {
  if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)) {
    return
  }
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${window.location.host}/ws/avatar/chat`
  wsState.value = 'connecting'

  let socket
  try {
    socket = new WebSocket(url)
  } catch (e) {
    console.error('open chat socket failed:', e)
    wsState.value = 'error'
    return
  }
  socket.binaryType = 'arraybuffer'
  chatSocket = socket

  socket.addEventListener('open', () => {
    wsState.value = 'open'
    console.log('[chat-ws] opened')
  })
  socket.addEventListener('message', (event) => {
    if (typeof event.data === 'string') {
      handleSocketJson(event.data)
    } else {
      handleSocketBinary(event.data)
    }
  })
  socket.addEventListener('error', (e) => {
    console.error('[chat-ws] error:', e)
    wsState.value = 'error'
  })
  socket.addEventListener('close', () => {
    wsState.value = 'closed'
    console.log('[chat-ws] closed')
    rejectPendingTurn(new Error('connection closed'))
    chatSocket = null
  })
}

function closeChatSocket() {
  rejectPendingTurn(new Error('socket closing'))
  if (chatSocket) {
    try { chatSocket.close() } catch (_) { /* ignore */ }
    chatSocket = null
  }
  wsState.value = 'idle'
}

function rejectPendingTurn(err) {
  if (pendingTurn) {
    try { pendingTurn.reject(err) } catch (_) { /* ignore */ }
    pendingTurn = null
  }
}

function handleSocketJson(raw) {
  let payload
  try {
    payload = JSON.parse(raw)
  } catch (e) {
    console.warn('ws JSON parse failed:', raw)
    return
  }
  switch (payload.type) {
    case 'user_ack':
      break
    case 'bot_text':
      appendBotMessages([
        {
          text: payload.text || '',
          object: payload.object || null,
        },
      ])
      // 把文本塞给数字人复刻播报 (服务端 TTS + 唇形). 队列 + 状态门控由 flush 处理.
      if (USE_TRANSCRIPT_MODE && payload.text) {
        transcriptQueue.push(payload.text)
        flushTranscriptQueue()
      }
      break
    case 'audio_start':
      // 标记开始接收本段 PCM, 记录采样率
      if (pendingTurn) {
        pendingTurn.audioSampleRate = payload.sample_rate || 16000
        pendingTurn.audioChunks = 0
        pendingTurn.audioBytes = 0
      }
      clearPendingPush()
      break
    case 'audio_end':
      finalizePendingAudio()
      break
    case 'turn_end':
      if (pendingTurn) {
        const turn = pendingTurn
        pendingTurn = null
        turn.resolve()
      }
      break
    case 'interrupt':
      pcmPlayer.stop()
      clearPendingPush()
      clearTranscriptQueue()
      if (avatarInstance) {
        try { avatarInstance.interrupt() } catch (_) { /* ignore */ }
      }
      break
    case 'error':
      errorMessage.value = payload.message || '数字人对话出错'
      rejectPendingTurn(new Error(payload.message || 'server error'))
      break
    default:
      console.debug('unknown ws message:', payload)
  }
}

function handleSocketBinary(buffer) {
  if (!pendingTurn || pendingTurn.audioChunks === undefined) return
  if (!buffer || buffer.byteLength === 0) return

  // transcript 模式: 后端推过来的 PCM 不需要本地播放, 也不推给 SDK.
  // 数字人声音直接走 RTC 视频流的音轨, 灵眸服务端 TTS 出声. 这里只统计字节数用于日志.
  if (USE_TRANSCRIPT_MODE) {
    pendingTurn.audioChunks = (pendingTurn.audioChunks || 0) + 1
    pendingTurn.audioBytes = (pendingTurn.audioBytes || 0) + buffer.byteLength
    return
  }

  const int16 = new Int16Array(buffer)
  const sampleRate = pendingTurn.audioSampleRate || 16000

  // 1) 立刻播音 (SDK 的 pushAudioData 只驱动口型, 不放音, 必须我们自己播)
  pcmPlayer.push(int16, sampleRate)

  // 2) 累积到 1s 一批推给 SDK 驱动嘴形 (SDK 内部按 1s 切段, 我们对齐它减少 batch 碎片)
  if (avatarInstance && avatarReady) {
    pendingPushChunks.push(int16)
    pendingPushSamples += int16.length
    while (pendingPushSamples >= SDK_PUSH_BATCH_SAMPLES) {
      const batch = takeInt16FromQueue(pendingPushChunks, SDK_PUSH_BATCH_SAMPLES)
      pendingPushSamples -= SDK_PUSH_BATCH_SAMPLES
      try {
        avatarInstance.pushAudioData(batch, false)
      } catch (e) {
        console.warn('[avatar] pushAudioData batch failed:', e)
      }
    }
  }

  pendingTurn.audioChunks = (pendingTurn.audioChunks || 0) + 1
  pendingTurn.audioBytes = (pendingTurn.audioBytes || 0) + buffer.byteLength
}

function finalizePendingAudio() {
  if (!pendingTurn) return
  const chunks = pendingTurn.audioChunks || 0
  const bytes = pendingTurn.audioBytes || 0
  console.log(`[avatar] segment finished chunks=${chunks} bytes=${bytes} tail_samples=${pendingPushSamples}`)
  pendingTurn.audioChunks = undefined
  pendingTurn.audioBytes = 0

  if (USE_TRANSCRIPT_MODE) {
    // transcript 模式: 不需要给 SDK 推任何 PCM, 唇形由服务端驱动
    return
  }

  if (avatarInstance && avatarReady) {
    try {
      // 关键: end=true 必须挂在带数据的推送上, 否则 SDK 在 length===0 时直接 return
      // 这里把剩余 (< 1s) 累积全部推完并标记 endOfBatch, 服务端才会渲染口型
      if (pendingPushSamples > 0) {
        const tail = concatAllInt16(pendingPushChunks, pendingPushSamples)
        avatarInstance.pushAudioData(tail, true)
      } else {
        // 刚好对齐到 1s 整批, 上一帧已经推过了, 这里需要至少 1 个样本触发 endOfBatch
        avatarInstance.pushAudioData(new Int16Array([0]), true)
      }
    } catch (e) {
      console.warn('[avatar] pushAudioData(end) failed:', e)
    }
    clearPendingPush()
  }
}

function sendOverSocket(text, messageId) {
  return new Promise((resolve, reject) => {
    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
      reject(new Error('数字人通道未连接'))
      return
    }
    // 新消息前: 打断上一段播报 + 通知服务端
    pcmPlayer.stop()
    clearPendingPush()
    clearTranscriptQueue()
    if (avatarInstance) {
      try { avatarInstance.interrupt() } catch (_) { /* ignore */ }
    }
    if (pendingTurn) {
      // 上一轮还没完, 直接丢弃
      try { pendingTurn.reject(new Error('superseded')) } catch (_) { /* ignore */ }
      pendingTurn = null
    }
    pendingTurn = { messageId, resolve, reject, expectingAudio: false }
    try {
      chatSocket.send(
        JSON.stringify({
          type: 'user_text',
          sender_id: senderId.value.trim(),
          text,
          message_id: messageId,
        }),
      )
    } catch (e) {
      pendingTurn = null
      reject(e)
    }
  })
}

async function copyText(text, key) {
  if (!text || !key) return
  try {
    await navigator.clipboard.writeText(text)
    copyState.value[key] = true
    setTimeout(() => { copyState.value[key] = false }, 1800)
  } catch (error) {
    console.error('Copy failed:', error)
  }
}
</script>

<template>
  <div class="app-shell">
    <canvas ref="bgCanvas" class="bg-canvas"></canvas>
    <div class="workspace">
      <div class="chat-card">
        <header class="chat-header">
          <div class="header-content">
            <div class="header-info">
              <h1>电商客服系统</h1>
              <div class="service-info">
                <div class="service-avatar-wrapper">
                  <img :src="customerService.avatar" class="service-avatar" />
                  <span class="status-indicator"></span>
                </div>
                <div class="service-details">
                  <span class="service-name">{{ customerService.name }}</span>
                  <span class="service-status">{{ customerService.status }}</span>
                </div>
              </div>
            </div>
            <button type="button" class="clear-button" title="清空对话" @click="resetConversation">
              <span>🔄</span>
              <span>新对话</span>
            </button>
          </div>
        </header>

        <div class="chat-body">
          <aside class="chat-aside">
        <section class="controls">
          <label class="field">
            <span>sender_id</span>
            <div class="field-row">
              <input v-model="senderId" type="text" placeholder="u1001" />
              <button
                type="button"
                class="secondary-button"
                :disabled="isLoadingSidebar"
                @click="fetchSidebarData"
              >
                {{ isLoadingSidebar ? '加载中...' : '刷新对象列表' }}
              </button>
            </div>
          </label>
        </section>

        <section class="avatar-stage">
          <div class="avatar-stage-header">
            <span class="avatar-stage-title">数字人</span>
            <span class="avatar-stage-status" :class="`avatar-status-${avatarState}`">
              <template v-if="avatarState === 'ready'">画面已就绪</template>
              <template v-else-if="avatarState === 'connecting'">连接中…</template>
              <template v-else-if="avatarState === 'waiting-gesture'">待启用</template>
              <template v-else-if="avatarState === 'error'">连接失败</template>
              <template v-else>离线</template>
            </span>
            <span class="avatar-stage-status" :class="`avatar-status-${wsState === 'open' ? 'ready' : (wsState === 'connecting' ? 'connecting' : 'error')}`">
              <template v-if="wsState === 'open'">语音通道在线</template>
              <template v-else-if="wsState === 'connecting'">语音通道连接中…</template>
              <template v-else-if="wsState === 'error'">语音通道异常</template>
              <template v-else>语音通道未连</template>
            </span>
          </div>
          <div class="avatar-stage-frame">
            <video
              id="cloudAvatarContainer"
              class="avatar-video"
              muted
              playsinline
            ></video>
            <div v-if="avatarState !== 'ready'" class="avatar-placeholder">
              <template v-if="avatarState === 'waiting-gesture'">
                <button type="button" class="gesture-button" @click="setupAvatar">
                  点击启用数字人语音
                </button>
                <p class="gesture-hint">浏览器要求用户先与页面交互才能播放音频</p>
              </template>
              <p v-else-if="avatarState === 'idle'">等待连接</p>
              <p v-else-if="avatarState === 'connecting'">正在拉取数字人画面…</p>
              <p v-else-if="avatarState === 'error'">{{ avatarErrorMessage || '数字人不可用' }}</p>
            </div>
          </div>
        </section>
          </aside>

          <main class="chat-main">
        <section ref="messagesContainer" class="messages">
          <div v-if="turns.length === 0" class="welcome">
            <div class="welcome-card">
              <div class="welcome-glow"></div>
              <div class="welcome-avatar-wrapper">
                <img :src="customerService.avatar" class="welcome-avatar" alt="小雨" />
                <span class="welcome-status-pulse"></span>
              </div>
              <h2 class="welcome-greeting">Hi，我是 {{ customerService.name }}</h2>
              <p class="welcome-subtitle">你的专属电商客服，随时为你服务</p>
              <div class="welcome-chips">
                <button
                  v-for="chip in ['我要退款', '查订单状态', '商品推荐', '退换货政策']"
                  :key="chip"
                  type="button"
                  class="welcome-chip"
                  :disabled="isSending"
                  @click="sendQuickText(chip)"
                >{{ chip }}</button>
              </div>
              <p class="welcome-features">
                <span>💬 文字对话</span>
                <span>🔊 语音播报</span>
                <span>📦 订单查询</span>
                <span>🛍️ 商品咨询</span>
              </p>
            </div>
          </div>

          <!-- Turn 结构展示 -->
          <template v-for="(item, index) in turns" :key="item.id || index">
            <!-- 分隔线 -->
            <div v-if="item.type === 'divider'" class="history-divider">
              <span>{{ item.text }}</span>
            </div>

            <!-- Turn 卡片 -->
            <div v-else class="turn-card" :class="{ 'has-user-message': item.userMessage }">
              <!-- Turn 标识 -->
              <div class="turn-header">
                <span class="turn-badge">Turn {{ item.index }}</span>
                <span class="turn-label">对话轮次</span>
              </div>

              <!-- 用户消息区域 -->
              <div v-if="item.userMessage" class="turn-section user-section">
                <div class="section-header">
                  <div class="avatar-wrapper user-avatar">
                    <img :src="userProfile.avatar" class="avatar" />
                  </div>
                  <div class="agent-info">
                    <span class="agent-name">{{ userProfile.name }}</span>
                    <span class="agent-label">用户</span>
                  </div>
                </div>
                <div class="turn-bubble user-bubble">
                  <template v-if="item.userMessage.type === 'object'">
                    <div class="object-card" :class="`object-card-${item.userMessage.objectType}`">
                      <div class="object-card-badge">
                        {{ item.userMessage.objectType === 'order' ? '订单对象' : '商品对象' }}
                      </div>
                      <img
                        v-if="item.userMessage.type === 'object' && item.userMessage.payload.cover_url"
                        :src="item.userMessage.payload.cover_url"
                        :alt="getObjectTitle(item.userMessage)"
                        class="object-card-image"
                        @error="$event.target.style.display='none'"
                      />
                      <div class="object-card-title">{{ getObjectTitle(item.userMessage) }}</div>
                      <div class="object-card-meta">{{ getObjectIdentifier(item.userMessage) }}</div>
                      <div class="object-card-meta">
                        <span v-if="item.userMessage.objectType === 'order' && item.userMessage.payload.status" class="status-badge" :class="getStatusClass(item.userMessage.payload.status)">{{ item.userMessage.payload.status }}</span>
                        <span v-else>{{ getObjectSummary(item.userMessage) }}</span>
                      </div>
                      <div class="object-card-price">{{ getObjectAmount(item.userMessage) }}</div>
                    </div>
                  </template>
                  <template v-else>
                    <div class="user-text-row">
                      <p>{{ item.userMessage.text }}</p>
                      <div class="user-actions">
                        <button type="button" class="copy-button copy-button-on-accent"
                          :class="{ 'copy-done': copyState[`${item.id}-user`] }"
                          :title="copyState[`${item.id}-user`] ? '已复制' : '复制文字'"
                          @click.stop="copyText(item.userMessage.text, `${item.id}-user`)">
                          <span v-if="copyState[`${item.id}-user`]">✓</span>
                          <span v-else>📋</span>
                        </button>
                      </div>
                    </div>
                  </template>
                </div>
              </div>

              <!-- 客服回复区域 -->
              <div v-if="item.botMessages.length > 0" class="turn-section bot-section">
                <div class="section-header">
                  <div class="avatar-wrapper service-avatar">
                    <img :src="customerService.avatar" class="avatar" />
                    <span class="status-dot"></span>
                  </div>
                  <div class="agent-info">
                    <span class="agent-name">{{ customerService.name }}</span>
                    <span class="agent-label">{{ customerService.title }}</span>
                  </div>
                </div>
                <div class="bot-messages">
                  <div
                    v-for="(botMsg, msgIndex) in item.botMessages"
                    :key="msgIndex"
                    class="turn-bubble bot-bubble"
                  >
                    <template v-if="botMsg.type === 'object'">
                      <div class="object-card" :class="`object-card-${botMsg.objectType}`">
                        <div class="object-card-badge">
                          {{ botMsg.objectType === 'order' ? '订单对象' : '商品对象' }}
                        </div>
                        <img
                          v-if="botMsg.type === 'object' && botMsg.payload.cover_url"
                          :src="botMsg.payload.cover_url"
                          :alt="getObjectTitle(botMsg)"
                          class="object-card-image"
                          @error="$event.target.style.display='none'"
                        />
                        <div class="object-card-title">{{ getObjectTitle(botMsg) }}</div>
                        <div class="object-card-meta">{{ getObjectIdentifier(botMsg) }}</div>
                        <div class="object-card-meta">
                          <span v-if="botMsg.objectType === 'order' && botMsg.payload.status" class="status-badge" :class="getStatusClass(botMsg.payload.status)">{{ botMsg.payload.status }}</span>
                          <span v-else>{{ getObjectSummary(botMsg) }}</span>
                        </div>
                        <div class="object-card-price">{{ getObjectAmount(botMsg) }}</div>
                      </div>
                    </template>
                    <template v-else>
                      <div class="bot-text-row">
                        <p>{{ botMsg.text }}</p>
                      </div>
                    </template>
                    <div v-if="botMsg.suggestions && botMsg.suggestions.length > 0" class="suggestion-chips">
                      <button
                        v-for="sug in botMsg.suggestions"
                        :key="sug"
                        type="button"
                        class="suggestion-chip"
                        :disabled="isSending"
                        @click.stop="sendSuggestion(sug)"
                      >{{ sug }}</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </section>

        <div v-if="isSending" class="typing-indicator">
          <div class="typing-avatar">
            <img :src="customerService.avatar" class="avatar-small" alt="小雨" />
          </div>
          <div class="typing-bubble">
            <span class="typing-dots">
              <span></span><span></span><span></span>
            </span>
            <span class="typing-label">小雨正在输入...</span>
          </div>
        </div>

        <p v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </p>

        <form class="composer" @submit.prevent="sendTextMessage">
          <input
            v-model="draftMessage"
            type="text"
            placeholder="请输入咨询内容..."
            :disabled="isSending"
          />
          <button type="submit" :disabled="isSending || !draftMessage.trim()">
            {{ isSending ? '发送中...' : '发送' }}
          </button>
        </form>
          </main>
        </div>
      </div>

      <aside class="sidebar">
        <div class="sidebar-header">
          <h2>业务对象</h2>
        </div>

        <div class="tabs">
          <button
            type="button"
            class="tab-button"
            :class="{ active: activeTab === 'orders' }"
            @click="activeTab = 'orders'"
          >
            订单
          </button>
          <button
            type="button"
            class="tab-button"
            :class="{ active: activeTab === 'products' }"
            @click="activeTab = 'products'"
          >
            商品
          </button>
        </div>

        <p v-if="sidebarError" class="sidebar-error">{{ sidebarError }}</p>

        <div v-if="activeTab === 'orders'" class="sidebar-list">
          <div v-if="!orders.length && !isLoadingSidebar" class="sidebar-empty">
            暂无订单数据
          </div>

          <article v-for="order in orders" :key="order.order_id" class="sidebar-card">
            <div class="card-image-wrapper">
              <img
                v-if="order.cover_url"
                :src="order.cover_url"
                :alt="order.title"
                class="card-image"
                @error="$event.target.style.display='none'"
              />
              <div v-else class="card-image-placeholder">📦</div>
            </div>
            <div class="card-top">
              <div class="card-title">{{ order.title }}</div>
              <div class="card-amount">{{ formatAmount(order.amount) }}</div>
            </div>
            <div class="card-meta">订单号：{{ order.order_id }}</div>
            <div class="card-meta">
              <span class="status-badge" :class="getStatusClass(order.status)">{{ order.status }}</span>
            </div>
            <button
              type="button"
              class="secondary-button full-width"
              :disabled="isSending"
              @click="sendOrder(order)"
            >
              发送订单
            </button>
          </article>
        </div>

        <div v-else class="sidebar-list">
          <div v-if="!products.length && !isLoadingSidebar" class="sidebar-empty">
            暂无商品数据
          </div>

          <article v-for="product in products" :key="product.product_id" class="sidebar-card">
            <div class="card-image-wrapper">
              <img
                v-if="product.cover_url"
                :src="product.cover_url"
                :alt="product.title"
                class="card-image"
                @error="$event.target.style.display='none'"
              />
              <div v-else class="card-image-placeholder">🛍️</div>
            </div>
            <div class="card-top">
              <div class="card-title">{{ product.title }}</div>
              <div class="card-amount">{{ formatAmount(product.price) }}</div>
            </div>
            <div class="card-meta">商品号：{{ product.product_id }}</div>
            <div class="card-meta">商品信息：最近浏览 / 购买商品</div>
            <button
              type="button"
              class="secondary-button full-width"
              :disabled="isSending"
              @click="sendProduct(product)"
            >
              发送商品
            </button>
          </article>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300..700&family=Zen+Maru+Gothic:wght@400;500;700&display=swap');

:global(*) {
  box-sizing: border-box;
}

:global(:root) {
  /* ── Palette ── */
  --color-bg-deep: #070a14;
  --color-bg-mid: #0c1024;
  --color-bg-surface: #11162b;
  /* Dark frosted glass — emerges from background, doesn't sit on top */
  --color-surface: rgba(14, 16, 30, 0.78);
  --color-surface-hover: rgba(20, 22, 38, 0.86);
  --color-surface-dim: rgba(14, 16, 30, 0.60);
  --color-surface-raised: rgba(24, 26, 44, 0.70);
  --color-surface-field: rgba(10, 12, 22, 0.62);
  /* Light text on dark surfaces */
  --color-text-primary: #e6e3dc;
  --color-text-secondary: #9b9790;
  --color-text-muted: #726f68;
  --color-text-inverse: #18171c;
  /* Accent — teal */
  --color-accent: #2dd4bf;
  --color-accent-strong: #14b8a6;
  --color-accent-soft: rgba(45, 212, 191, 0.10);
  --color-accent-glow: rgba(45, 212, 191, 0.20);
  --color-accent-soft-bg: rgba(45, 212, 191, 0.06);
  /* Warm — amber */
  --color-warm: #f59e0b;
  --color-warm-strong: #d97706;
  --color-warm-soft: rgba(245, 158, 11, 0.10);
  --color-warm-glow: rgba(245, 158, 11, 0.18);
  --color-warm-soft-bg: rgba(245, 158, 11, 0.05);
  /* Semantic */
  --color-success: #34d399;
  --color-success-soft: rgba(52, 211, 153, 0.12);
  --color-info: #38bdf8;
  --color-info-soft: rgba(56, 189, 248, 0.10);
  --color-danger: #fb7185;
  --color-danger-soft: rgba(251, 113, 133, 0.10);
  /* Borders — subtle light lines on dark glass */
  --color-border: rgba(255, 255, 255, 0.08);
  --color-border-light: rgba(255, 255, 255, 0.05);
  --color-border-strong: rgba(255, 255, 255, 0.13);
  /* ── Radii ── */
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --radius-xl: 28px;
  --radius-full: 9999px;
  /* 数字人视频取景框缩放: 1.0=全身 1.5=半身 1.7=头肩 2.0=大头 */
  --avatar-zoom: 1.7;
  /* ── Shadows (glow-based for dark theme) ── */
  --shadow-xs: 0 1px 3px rgba(0, 0, 0, 0.18);
  --shadow-sm: 0 4px 14px rgba(0, 0, 0, 0.22);
  --shadow-md: 0 8px 32px rgba(0, 0, 0, 0.28);
  --shadow-lg: 0 20px 56px rgba(0, 0, 0, 0.35);
  --shadow-glow-teal: 0 0 60px rgba(45, 212, 191, 0.10), 0 0 120px rgba(45, 212, 191, 0.04);
  --shadow-glow-amber: 0 0 50px rgba(245, 158, 11, 0.08), 0 0 100px rgba(245, 158, 11, 0.03);
  --shadow-inner-glow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  /* ── Transitions ── */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-out-back: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --duration-fast: 150ms;
  --duration-base: 250ms;
  --duration-slow: 400ms;
}

:global(body) {
  margin: 0;
  font-family: "Outfit", "Zen Maru Gothic", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--color-bg-deep);
  color: var(--color-text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

:global(button),
:global(input) {
  font: inherit;
}

:global(#app) {
  min-height: 100vh;
}

.app-shell {
  min-height: 100vh;
  padding: 24px;
  position: relative;
  overflow: hidden;
  background: linear-gradient(165deg, #070a14 0%, #0c1024 25%, #0a0f1f 50%, #0c1024 75%, #080d1c 100%);
  background-size: 400% 400%;
  animation: bgShift 24s ease-in-out infinite;
}
/* Subtle grain texture overlay */
.app-shell::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.028;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

.bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.app-shell::after {
  content: "";
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
}
/* Teal orb — top left */
.app-shell::after {
  width: 820px; height: 820px;
  background: radial-gradient(circle, rgba(13, 148, 136, 0.18) 0%, rgba(20, 184, 166, 0.06) 35%, transparent 70%);
  top: -320px; left: -280px;
  animation: orb1 20s ease-in-out infinite;
}
/* Amber orb — bottom right */
.workspace::before {
  content: "";
  position: fixed;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
  width: 640px; height: 640px;
  background: radial-gradient(circle, rgba(217, 119, 6, 0.13) 0%, rgba(245, 158, 11, 0.05) 40%, transparent 70%);
  bottom: -280px; right: -220px;
  animation: orb2 24s ease-in-out infinite;
}

@keyframes bgShift {
  0%, 100% { background-position: 0% 0%; }
  25% { background-position: 100% 0%; }
  50% { background-position: 100% 100%; }
  75% { background-position: 0% 100%; }
}
@keyframes orb1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(140px, 90px) scale(1.22); }
  66% { transform: translate(-50px, 150px) scale(0.82); }
}
@keyframes orb2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-110px, -70px) scale(1.18); }
  66% { transform: translate(70px, -130px) scale(0.88); }
}

.workspace {
  width: min(1760px, 100%);
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 370px;
  gap: 22px;
  position: relative;
  z-index: 1;
}

.chat-card,
.sidebar {
  min-height: calc(100vh - 48px);
  height: calc(100vh - 48px);
  background: var(--color-surface);
  backdrop-filter: blur(32px) saturate(1.2);
  -webkit-backdrop-filter: blur(32px) saturate(1.2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color var(--duration-slow) var(--ease-in-out), box-shadow var(--duration-slow) var(--ease-in-out);
}
.chat-card {
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-glow-teal), var(--shadow-lg), var(--shadow-inner-glow);
}
.chat-card:hover {
  border-color: rgba(45, 212, 191, 0.15);
}

/* chat-card 内部三段式: header + body(左数字人栏 + 右对话栏) */
.chat-body {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: stretch;
}
.chat-aside {
  flex-shrink: 0;
  width: 380px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--color-border-light);
  background: var(--color-surface-dim);
  overflow-y: auto;
}
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.sidebar {
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-glow-amber), var(--shadow-lg), var(--shadow-inner-glow);
}
.sidebar:hover {
  border-color: rgba(245, 158, 11, 0.15);
}

.chat-header,
.sidebar-header {
  padding: 24px 24px 16px;
  border-bottom: 1px solid var(--color-border-light);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.chat-header h1,
.sidebar-header h2 {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #f0ede6 0%, var(--color-accent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sidebar-header h2 {
  font-size: 22px;
  background: linear-gradient(135deg, #f0ede6 0%, var(--color-warm) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.chat-header p,
.sidebar-header p {
  margin: 10px 0 0;
  color: var(--color-text-secondary);
}

/* 客服信息 */
.service-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.service-avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.service-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
  padding: 3px;
  background: conic-gradient(var(--color-success), var(--color-accent), var(--color-warm), var(--color-success));
  animation: avatarSpin 4s linear infinite;
  box-shadow: 0 0 20px var(--color-accent-glow), 0 4px 12px var(--color-success-soft);
}
@keyframes avatarSpin {
  to { transform: rotate(360deg); }
}

.status-indicator {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 14px;
  height: 14px;
  background: var(--color-success);
  border: 3px solid #ffffff;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.service-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.service-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.service-status {
  font-size: 12px;
  color: var(--color-success);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
}

.service-status::before {
  content: '';
  width: 6px;
  height: 6px;
  background: var(--color-success);
  border-radius: 50%;
}

.clear-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out-expo);
  white-space: nowrap;
}
.clear-button:hover {
  background: rgba(251, 113, 133, 0.10);
  border-color: var(--color-danger);
  color: var(--color-danger);
  transform: translateY(-1px);
  box-shadow: 0 4px 18px var(--color-danger-soft);
}

.controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--color-border-light);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field span {
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
}

.field-row {
  display: flex;
  gap: 12px;
}

.field input,
.composer input {
  width: 100%;
  min-width: 0;
  min-height: 46px;
  padding: 11px 14px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface-field);
  color: var(--color-text-primary);
  font-size: 15px;
  line-height: 1.4;
  transition: border-color var(--duration-fast) var(--ease-in-out), box-shadow var(--duration-fast) var(--ease-in-out);
}
.field input::placeholder,
.composer input::placeholder {
  color: var(--color-text-muted);
}
.field input:focus,
.composer input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}

/* 数字人云渲染舞台 */
.avatar-stage {
  padding: 14px 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: stretch;
}
.avatar-stage-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  width: 100%;
}
.avatar-stage-header .avatar-stage-title {
  margin-right: auto;
}
.avatar-stage-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-secondary);
  letter-spacing: 0.04em;
}
.avatar-stage-status {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: rgba(148, 163, 184, 0.18);
  color: var(--color-text-secondary);
}
.avatar-status-ready {
  background: rgba(16, 185, 129, 0.18);
  color: #10b981;
}
.avatar-status-connecting {
  background: rgba(245, 158, 11, 0.18);
  color: #f59e0b;
}
.avatar-status-error {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}
.avatar-stage-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: var(--radius-lg);
  overflow: hidden;
  /* 简洁的舞台背景, 衬托抠像后的数字人 */
  background:
    radial-gradient(120% 80% at 50% 100%, rgba(13, 148, 136, 0.18), transparent 60%),
    linear-gradient(180deg, #0c1024 0%, #060812 100%);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-md);
}
.avatar-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center top;
  /* CSS 虚拟取景框: 把数字人头肩放大成近景, 多余的腰/腿部分被容器 overflow 裁掉 */
  transform: scale(var(--avatar-zoom, 1.7));
  transform-origin: 50% 18%;
  transition: transform 280ms ease;
  background: transparent;
}
.avatar-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--color-text-muted);
  font-size: 13px;
  background: rgba(7, 10, 20, 0.7);
  backdrop-filter: blur(4px);
  padding: 16px;
  text-align: center;
}
.gesture-button {
  padding: 10px 22px;
  border-radius: var(--radius-full);
  border: 0;
  background: linear-gradient(135deg, var(--color-accent), #0d9488);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(13, 148, 136, 0.35);
  transition: transform var(--duration-fast) var(--ease-in-out),
              box-shadow var(--duration-fast) var(--ease-in-out);
}
.gesture-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(13, 148, 136, 0.45);
}
.gesture-hint {
  color: var(--color-text-secondary);
  font-size: 12px;
  margin: 0;
}
/* "待启用" 状态的徽章 */
.avatar-status-waiting-gesture {
  background: rgba(56, 189, 248, 0.18);
  color: #38bdf8;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Turn 卡片样式 */
.turn-card {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: all var(--duration-base) var(--ease-out-expo);
  position: relative;
  overflow: hidden;
  animation: msgEnter 0.4s var(--ease-out-back) both;
}
@keyframes msgEnter {
  from { opacity: 0; transform: translateY(24px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.turn-card::before {
  content: "";
  position: absolute;
  top: 0; left: -100%;
  width: 100%; height: 100%;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.04) 50%, transparent 60%);
  transition: left 0.5s ease;
  pointer-events: none;
  z-index: 2;
}
.turn-card:hover::before {
  left: 100%;
}
.turn-card:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-md), 0 0 40px rgba(45, 212, 191, 0.04);
  transform: translateY(-2px);
}

.turn-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--color-border);
}

.turn-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  background: linear-gradient(135deg, var(--color-accent), #0d9488);
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 12px var(--color-accent-glow);
}

.turn-label {
  font-size: 12px;
  color: var(--color-text-muted);
  font-weight: 500;
}

.turn-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  font-weight: 600;
}

/* 头像样式 */
.avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #e5e7eb;
  background: #f3f4f6;
  transition: all var(--duration-base) var(--ease-out-expo);
}

.user-avatar .avatar {
  border: 3px solid transparent;
  background: linear-gradient(#ffffff, #ffffff) padding-box,
              linear-gradient(135deg, var(--color-info), var(--color-accent)) border-box;
  box-shadow: 0 2px 14px var(--color-info-soft);
}

.service-avatar .avatar {
  border-color: var(--color-success);
  box-shadow: 0 2px 10px var(--color-success-soft);
}

.status-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  background: var(--color-success);
  border: 2px solid #ffffff;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.65;
    transform: scale(1.12);
  }
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.agent-label {
  font-size: 12px;
  color: var(--color-text-muted);
  font-weight: 500;
}

.user-section .agent-name {
  color: var(--color-info);
}

.bot-section .agent-name {
  color: var(--color-success);
}

.role-icon {
  font-size: 16px;
}

.role-label {
  color: var(--color-text-secondary);
}

.user-section .role-label {
  color: var(--color-info);
}

.bot-section .role-label {
  color: var(--color-success);
}

.turn-bubble {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  max-width: 100%;
}

.user-bubble {
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-strong));
  border: 1px solid transparent;
  color: #ffffff;
  box-shadow: 0 4px 18px var(--color-accent-glow);
  margin-left: auto;
  max-width: 85%;
}

.bot-bubble {
  background: var(--color-surface-field);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
  box-shadow: var(--shadow-xs);
}

.bot-messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.turn-bubble p {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.user-bubble p {
  color: #ffffff;
}

/* 历史消息分隔线 */
.history-divider {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--color-text-muted);
  font-size: 13px;
  padding: 8px 0;
}

.history-divider::before,
.history-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--color-border-strong);
}

.history-divider span {
  padding: 6px 14px;
  border-radius: var(--radius-full);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  font-size: 12px;
}

.welcome {
  flex-shrink: 0;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.welcome-card {
  position: relative;
  max-width: 480px;
  width: 100%;
  padding: 44px 40px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  text-align: center;
  box-shadow: var(--shadow-glow-teal), var(--shadow-lg);
  overflow: hidden;
  animation: welcomeFloat 0.6s var(--ease-out-back);
}
@keyframes welcomeFloat {
  from { opacity: 0; transform: translateY(36px) scale(0.94); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.welcome-glow {
  position: absolute;
  top: -100px; left: 50%; transform: translateX(-50%);
  width: 350px; height: 350px;
  background: radial-gradient(circle, rgba(45,212,191,0.08) 0%, rgba(45,212,191,0.02) 45%, transparent 70%);
  pointer-events: none;
}
.welcome-avatar-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: 20px;
}
.welcome-avatar {
  width: 88px; height: 88px;
  border-radius: 50%;
  padding: 4px;
  background: conic-gradient(var(--color-success), var(--color-accent), var(--color-warm), var(--color-success));
  animation: avatarSpin 4s linear infinite;
  box-shadow: 0 0 36px var(--color-accent-glow);
}
.welcome-status-pulse {
  position: absolute;
  bottom: 6px; right: 6px;
  width: 18px; height: 18px;
  background: var(--color-success);
  border: 3px solid var(--color-bg-mid);
  border-radius: 50%;
  animation: pulse 2s infinite;
  box-shadow: 0 0 16px rgba(52, 211, 153, 0.4);
}
.welcome-greeting {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 700;
  background: linear-gradient(135deg, #f0ede6, var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.welcome-subtitle {
  margin: 0 0 28px;
  color: var(--color-text-secondary);
  font-size: 15px;
}
.welcome-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-bottom: 28px;
}
.welcome-chip {
  padding: 10px 20px;
  border: 1px solid rgba(45, 212, 191, 0.16);
  border-radius: var(--radius-full);
  background: var(--color-accent-soft-bg);
  color: var(--color-accent);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out-expo);
}
.welcome-chip:hover:not(:disabled) {
  background: var(--color-accent-soft);
  border-color: var(--color-accent);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px var(--color-accent-glow);
}
.welcome-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.welcome-features {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.sidebar-empty {
  margin: auto;
  max-width: 420px;
  color: var(--color-text-muted);
  text-align: center;
  line-height: 1.7;
}

.typing-indicator {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 0 20px;
  animation: msgEnter 0.3s var(--ease-out-expo);
}
.avatar-small {
  width: 34px; height: 34px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--color-success);
  box-shadow: 0 0 12px rgba(52, 211, 153, 0.25);
}
.typing-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: 20px 20px 20px 6px;
  box-shadow: var(--shadow-sm);
}
.typing-dots {
  display: flex;
  gap: 4px;
  align-items: center;
}
.typing-dots span {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: dotBounce 1.2s ease-in-out infinite;
}
.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-8px); opacity: 1; }
}
.typing-label {
  font-size: 13px;
  color: var(--color-text-muted);
}

.object-card-price {
  font-size: 15px;
  font-weight: 600;
}

/* ── 状态徽章 ────────────────────────────────────────────── */
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.status-warning {
  background: var(--color-warm-soft);
  color: var(--color-warm-strong);
  border: 1px solid rgba(245, 158, 11, 0.25);
}
.status-info {
  background: var(--color-info-soft);
  color: var(--color-info);
  border: 1px solid rgba(56, 189, 248, 0.25);
}
.status-success {
  background: var(--color-success-soft);
  color: var(--color-success);
  border: 1px solid rgba(52, 211, 153, 0.25);
}
.status-muted {
  background: rgba(113, 111, 104, 0.12);
  color: var(--color-text-muted);
  border: 1px solid rgba(113, 111, 104, 0.18);
}
.status-danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
  border: 1px solid rgba(251, 113, 133, 0.25);
}

/* ── 商品图片（侧边栏） ────────────────────────────────────── */
.card-image-wrapper {
  width: 100%;
  height: 140px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-surface-field);
  border: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--duration-base) var(--ease-out-expo);
}
.sidebar-card:hover .card-image {
  transform: scale(1.05);
}
.card-image-placeholder {
  font-size: 40px;
  opacity: 0.5;
}

/* ── 对象卡片图片（聊天区） ─────────────────────────────────── */
.object-card-image {
  width: 100%;
  height: 150px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  border: 1px solid var(--color-border-light);
  background: var(--color-surface-field);
}

/* Turn 卡片中的对象卡片样式调整 */
.turn-bubble .object-card {
  min-width: 200px;
}

.user-bubble .object-card-badge {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

.composer button,
.secondary-button,
.tab-button {
  min-height: 42px;
  padding: 9px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text-primary);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
  transition:
    transform var(--duration-fast) var(--ease-out-expo),
    box-shadow var(--duration-fast) var(--ease-out-expo),
    background var(--duration-fast) var(--ease-in-out),
    border-color var(--duration-fast) var(--ease-in-out);
}

.composer button:hover:not(:disabled),
.secondary-button:hover:not(:disabled),
.tab-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.composer button:active:not(:disabled),
.secondary-button:active:not(:disabled),
.tab-button:active:not(:disabled) {
  transform: translateY(0);
}

.composer button:disabled,
.secondary-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.error-message,
.sidebar-error {
  margin: 0;
  padding: 0 24px 14px;
  color: var(--color-danger);
  font-size: 13px;
  font-weight: 500;
}

.composer {
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-surface-dim);
}

.composer button {
  min-width: 96px;
  padding-inline: 20px;
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-strong));
  border-color: transparent;
  color: #f0fdfa;
  box-shadow: 0 14px 28px var(--color-accent-glow);
}
.composer button:hover:not(:disabled) {
  box-shadow: 0 18px 36px var(--color-accent-glow);
  transform: translateY(-2px);
}

.sidebar {
  display: flex;
  flex-direction: column;
}

.tabs {
  display: flex;
  gap: 8px;
  padding: 16px 24px 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.tab-button {
  min-width: 80px;
}

.tab-button.active {
  background: linear-gradient(135deg, var(--color-accent-strong), var(--color-accent));
  border-color: transparent;
  color: #f0fdfa;
  box-shadow: 0 4px 14px var(--color-accent-glow);
}

.sidebar-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sidebar-card {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all var(--duration-base) var(--ease-out-expo);
}
.sidebar-card:hover {
  background: var(--color-surface-hover);
  border-color: rgba(245, 158, 11, 0.18);
  transform: translateY(-3px);
  box-shadow: var(--shadow-md), var(--shadow-glow-amber);
}

.card-top {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: flex-start;
}

.card-title {
  font-size: 15px;
  line-height: 1.5;
  color: var(--color-text-primary);
  font-weight: 600;
}

.card-amount {
  flex-shrink: 0;
  color: var(--color-warm-strong);
  font-weight: 700;
}

.card-meta {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.bot-text-row { display: flex; align-items: flex-start; gap: 8px; }
.bot-text-row p { flex: 1; margin: 0; }
.user-text-row { display: flex; align-items: flex-start; gap: 8px; }
.user-text-row p { flex: 1; margin: 0; }
.user-actions {
  display: flex; gap: 6px; flex-shrink: 0; align-items: center;
}
.copy-button {
  flex-shrink: 0; width: 28px; height: 28px; padding: 0;
  border: 1px solid var(--color-border-light); border-radius: 8px;
  background: var(--color-surface); cursor: pointer;
  font-size: 13px; display: inline-flex; align-items: center; justify-content: center;
  transition: all var(--duration-base) var(--ease-out-expo); color: var(--color-text-muted);
}
.copy-button:hover:not(:disabled) {
  background: var(--color-accent-soft); border-color: var(--color-accent); color: var(--color-accent-strong);
  transform: scale(1.1);
}
.copy-button:disabled { cursor: not-allowed; opacity: 0.65; }
.copy-button.copy-done {
  background: var(--color-success-soft);
  border-color: var(--color-success);
  color: var(--color-success);
}
.copy-button.copy-button-on-accent {
  background: rgba(255, 255, 255, 0.18);
  border-color: rgba(255, 255, 255, 0.32);
  color: #ffffff;
  backdrop-filter: blur(2px);
}
.copy-button.copy-button-on-accent:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.32);
  border-color: #ffffff;
  color: #ffffff;
}
.copy-button.copy-button-on-accent.copy-done {
  background: rgba(255, 255, 255, 0.92);
  border-color: #ffffff;
  color: var(--color-success);
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border-light);
}
.suggestion-chip {
  padding: 6px 14px;
  border: 1px solid rgba(45, 212, 191, 0.14);
  border-radius: var(--radius-full);
  background: var(--color-accent-soft-bg);
  color: var(--color-accent);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out-expo);
}
.suggestion-chip:hover:not(:disabled) {
  background: var(--color-accent-soft);
  border-color: var(--color-accent);
  transform: translateY(-1px);
}
.suggestion-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.full-width {
  width: 100%;
}

.sidebar .secondary-button.full-width {
  min-height: 42px;
}

.sidebar-empty {
  margin: auto;
  max-width: 420px;
  color: var(--color-text-muted);
  text-align: center;
  line-height: 1.7;
}

/* Turn 卡片中的对象卡片样式调整 */
.turn-bubble .object-card {
  min-width: 200px;
}

.user-bubble .object-card-badge {
  background: rgba(255, 255, 255, 0.2);
  color: #ffffff;
}

@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .chat-header {
    flex-direction: column;
  }

  .sidebar {
    min-height: auto;
    height: auto;
  }
}

/* 中屏: aside 收窄 */
@media (max-width: 960px) {
  .chat-aside {
    width: 320px;
  }
}

/* 小屏: 数字人栏折叠到顶部, 变横向紧凑视图 */
@media (max-width: 720px) {
  .app-shell {
    padding: 0;
  }

  .workspace {
    gap: 0;
  }

  .chat-card,
  .sidebar {
    min-height: auto;
    height: auto;
    border-radius: 0;
    border-left: none;
    border-right: none;
  }

  .chat-card {
    min-height: 100vh;
  }

  .chat-body {
    flex-direction: column;
  }
  .chat-aside {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--color-border-light);
    flex-direction: row;
    align-items: stretch;
    overflow-x: auto;
    overflow-y: hidden;
  }
  .chat-aside .controls {
    flex: 1;
    border-bottom: none;
    border-right: 1px solid var(--color-border-light);
    padding: 14px 16px;
  }
  .chat-aside .avatar-stage {
    flex-shrink: 0;
    width: 180px;
    padding: 10px 14px;
  }
  .chat-aside .avatar-stage-header {
    display: none;
  }

  .message {
    max-width: 100%;
  }

  .composer,
  .field-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
