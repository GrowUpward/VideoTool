<template>
  <div class="card ai-summary-card">
    <div class="summary-header">
      <span class="label">AI 视频总结</span>
      <div class="format-tabs">
        <n-button
          v-for="tab in tabs"
          :key="tab.value"
          :type="activeTab === tab.value ? 'primary' : 'default'"
          size="small"
          quaternary
          @click="switchTab(tab.value)"
        >
          {{ tab.label }}
        </n-button>
      </div>
    </div>

    <!-- Loading state (only for initial load, not streaming) -->
    <div v-if="loading && !result?.summary && activeTab !== 'qa'" class="loading-state">
      <n-spin size="medium" />
      <span class="loading-text">{{ loadingText }}</span>
    </div>

    <!-- Error state -->
    <div v-else-if="error && activeTab !== 'qa'" class="error-state">
      <span>{{ error }}</span>
      <n-button size="small" @click="retry" quaternary type="error">重试</n-button>
    </div>

    <!-- Summary / Key Points / Mind Map content -->
    <div v-if="result && activeTab !== 'qa'" class="summary-content">
      <div v-if="result.cached" class="cached-badge">
        <n-tag size="tiny" type="info" round>缓存</n-tag>
      </div>

      <!-- Mind Map -->
      <div v-if="activeTab === 'mind_map'" class="mindmap-wrapper">
        <MindMap :content="result.summary" />
      </div>

      <!-- Other formats: render as markdown -->
      <div v-else class="text-content" v-html="renderMarkdown(result.summary)"></div>

      <!-- Streaming indicator -->
      <div v-if="loading && result.summary" class="streaming-indicator">
        <span class="pulse-dot"></span>
        <span>AI 正在生成...</span>
      </div>

      <!-- Subtitle toggle -->
      <div class="transcript-toggle">
        <n-button size="tiny" quaternary @click="showTranscript = !showTranscript">
          {{ showTranscript ? '隐藏字幕' : '查看字幕详情' }}
        </n-button>
        <span v-if="subtitleData.has_subtitle" class="subtitle-meta">
          <n-tag size="tiny" type="success" round>{{ subtitleData.language }}</n-tag>
          <n-tag size="tiny" :type="subtitleData.subtitle_type === 'manual' ? 'warning' : 'info'" round>
            {{ subtitleData.subtitle_type === 'manual' ? '人工字幕' : '自动字幕' }}
          </n-tag>
          <span class="segment-count">{{ subtitleData.segments?.length || 0 }} 条</span>
        </span>
      </div>
      <transition name="fade">
        <div v-if="showTranscript" class="transcript-box">
          <!-- Structured segments view -->
          <div v-if="subtitleData.segments?.length > 0" class="subtitle-segments">
            <div v-for="(seg, idx) in subtitleData.segments" :key="idx" class="segment-row">
              <span class="seg-time">{{ formatTime(seg.start) }}</span>
              <span class="seg-text">{{ seg.text }}</span>
            </div>
          </div>
          <!-- Fallback: flat transcript -->
          <pre v-else>{{ result.transcript }}</pre>
        </div>
      </transition>
    </div>

    <!-- Q&A Chat Tab -->
    <div v-if="activeTab === 'qa'" class="chat-container">
      <div ref="chatMessagesEl" class="chat-messages">
        <div v-if="chatMessages.length === 0" class="chat-empty">
          <div class="chat-empty-icon">💬</div>
          <p>基于视频内容向 AI 提问</p>
          <p class="chat-hint">例如：这个视频讲了什么？核心观点是什么？</p>
        </div>
        <div v-for="(msg, idx) in chatMessages" :key="idx" :class="['chat-message', msg.role]">
          <div class="message-bubble">
            <div v-if="msg.role === 'assistant'" class="message-content" v-html="renderMarkdown(msg.content)"></div>
            <div v-else class="message-content">{{ msg.content }}</div>
            <div v-if="msg.loading" class="typing-indicator">
              <span class="pulse-dot"></span>
            </div>
          </div>
        </div>
      </div>
      <div class="chat-input-area">
        <input
          v-model="chatInput"
          class="chat-input"
          placeholder="输入你的问题..."
          @keyup.enter="sendQuestion"
          :disabled="chatLoading"
        />
        <n-button
          type="primary"
          size="small"
          :disabled="!chatInput.trim() || chatLoading"
          @click="sendQuestion"
        >
          发送
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { NButton, NTag, NSpin } from 'naive-ui'
import MindMap from './MindMap.vue'
import { summarizeVideo, chatWithVideo } from '../api.js'

const props = defineProps({ url: String })

const tabs = [
  { label: '摘要', value: 'summary' },
  { label: '要点', value: 'key_points' },
  { label: '思维导图', value: 'mind_map' },
  { label: 'Q&A', value: 'qa' },
]

const activeTab = ref('summary')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const showTranscript = ref(false)
const cache = ref({})  // format -> result
const subtitleData = ref({ has_subtitle: false, language: '', subtitle_type: 'none', segments: [], full_text: '' })

// Chat state
const chatMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatMessagesEl = ref(null)

const loadingText = ref('正在生成摘要...')

// ── Subtitle data is shared across all formats ──
let currentSubtitleData = null

async function fetchSummary(format) {
  if (!props.url) return

  // Check local cache first
  if (cache.value[format]) {
    result.value = { ...cache.value[format] }
    if (currentSubtitleData) {
      subtitleData.value = currentSubtitleData
    }
    return
  }

  loading.value = true
  error.value = ''
  result.value = { transcript: '', summary: '', format, cached: false }

  const texts = {
    summary: '正在生成摘要...',
    key_points: '正在提取要点...',
    mind_map: '正在生成思维导图...',
    qa: '正在生成问答...',
  }
  loadingText.value = texts[format] || '正在生成...'

  try {
    await summarizeVideo(props.url, format, false, {
      subtitle: (data) => {
        try {
          const parsed = JSON.parse(data)
          subtitleData.value = parsed
          currentSubtitleData = parsed
          result.value.transcript = parsed.full_text || ''
        } catch { /* ignore */ }
      },
      summary: (data) => {
        try {
          result.value.summary += JSON.parse(data)
        } catch {
          result.value.summary += data
        }
      },
      done: () => {
        loading.value = false
        result.value.cached = false
        cache.value[format] = { ...result.value }
      },
      error: (data) => {
        loading.value = false
        try {
          const parsed = JSON.parse(data)
          error.value = parsed.message || '总结失败'
        } catch {
          error.value = data || '总结失败'
        }
      },
    })
  } catch (e) {
    loading.value = false
    error.value = e.message
  }
}

function switchTab(tab) {
  activeTab.value = tab
  error.value = ''
  if (tab === 'qa') {
    return  // Chat tab has its own state
  }
  result.value = cache.value[tab] ? { ...cache.value[tab] } : null
  if (!result.value) {
    fetchSummary(tab)
  }
}

function retry() {
  if (activeTab.value === 'qa') return
  // Clear cache for this format to force re-fetch
  delete cache.value[activeTab.value]
  fetchSummary(activeTab.value)
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── Markdown rendering (hand-written, no external dependency) ──
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h5>$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')

  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

  // Code blocks
  html = html.replace(/```[\s\S]*?```/g, (match) => {
    const code = match.replace(/```\w*\n?/g, '').replace(/```$/g, '')
    return `<pre class="code-block"><code>${code}</code></pre>`
  })

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // Numbered lists
  html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<div class="list-item"><span class="num">$1.</span> $2</div>')

  // Bullet lists
  html = html.replace(/^[-*]\s+(.+)$/gm, '<div class="list-item"><span class="bullet">·</span> $1</div>')

  // Horizontal rule
  html = html.replace(/^---+$/gm, '<hr class="divider">')

  // Line breaks (but not inside block elements)
  html = html.replace(/\n/g, '<br>')

  // Clean up consecutive <br> after block elements
  html = html.replace(/<\/h[2-5]><br>/g, '</h2>')
  html = html.replace(/<\/div><br>/g, '</div>')
  html = html.replace(/<hr[^>]*><br>/g, '<hr>')

  return html
}

// ── Chat Q&A ──
async function sendQuestion() {
  const question = chatInput.value.trim()
  if (!question || chatLoading.value) return

  // Add user message
  chatMessages.value.push({ role: 'user', content: question })
  chatInput.value = ''

  // Add placeholder assistant message
  const assistantIdx = chatMessages.value.length
  chatMessages.value.push({ role: 'assistant', content: '', loading: true })
  chatLoading.value = true

  await nextTick()
  scrollChatToBottom()

  try {
    await chatWithVideo(props.url, question, subtitleData.value.full_text || '', {
      answer: (data) => {
        try {
          chatMessages.value[assistantIdx].content += JSON.parse(data)
        } catch {
          chatMessages.value[assistantIdx].content += data
        }
        scrollChatToBottom()
      },
      done: () => {
        chatMessages.value[assistantIdx].loading = false
        chatLoading.value = false
      },
      error: (data) => {
        chatMessages.value[assistantIdx].loading = false
        chatLoading.value = false
        try {
          const parsed = JSON.parse(data)
          chatMessages.value[assistantIdx].content = `错误：${parsed.message || '回答失败'}`
        } catch {
          chatMessages.value[assistantIdx].content = `错误：${data || '回答失败'}`
        }
      },
    })
  } catch (e) {
    chatMessages.value[assistantIdx].loading = false
    chatMessages.value[assistantIdx].content = `错误：${e.message}`
    chatLoading.value = false
  }
}

function scrollChatToBottom() {
  nextTick(() => {
    if (chatMessagesEl.value) {
      chatMessagesEl.value.scrollTop = chatMessagesEl.value.scrollHeight
    }
  })
}

// Auto-fetch on mount
fetchSummary(activeTab.value)
</script>

<style scoped>
.ai-summary-card {
  padding: 20px 24px;
}
.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.summary-header .label {
  font-size: 0.95rem;
  font-weight: 600;
  color: #aaaacc;
}
.format-tabs {
  display: flex;
  gap: 4px;
}
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: #8888aa;
}
.loading-text {
  font-size: 0.9rem;
}
.error-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(248, 113, 113, 0.1);
  border-radius: 8px;
  color: #f87171;
  font-size: 0.85rem;
}
.summary-content {
  position: relative;
}
.cached-badge {
  position: absolute;
  top: 0;
  right: 0;
}

/* ── Streaming indicator ── */
.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  color: #8888aa;
  font-size: 0.8rem;
}
.pulse-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #667eea;
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

/* ── Text content (markdown rendered) ── */
.text-content {
  font-size: 0.9rem;
  line-height: 1.8;
  color: #ccccee;
  padding: 4px 0;
}
.text-content :deep(h2) {
  font-size: 1.1rem;
  color: #e8e8f0;
  margin: 16px 0 8px;
}
.text-content :deep(h3) {
  font-size: 1rem;
  color: #ddddee;
  margin: 14px 0 6px;
}
.text-content :deep(h4),
.text-content :deep(h5) {
  font-size: 0.95rem;
  color: #ccccee;
  margin: 10px 0 4px;
}
.text-content :deep(.list-item) {
  padding: 2px 0;
}
.text-content :deep(.num) {
  color: #667eea;
  font-weight: 600;
  margin-right: 4px;
}
.text-content :deep(.bullet) {
  color: #667eea;
  font-weight: 600;
  margin-right: 6px;
}
.text-content :deep(.code-block) {
  background: rgba(0,0,0,0.3);
  border-radius: 6px;
  padding: 12px;
  margin: 8px 0;
  overflow-x: auto;
  font-size: 0.8rem;
}
.text-content :deep(.inline-code) {
  background: rgba(0,0,0,0.3);
  border-radius: 3px;
  padding: 1px 5px;
  font-size: 0.85rem;
}
.text-content :deep(.divider) {
  border: none;
  border-top: 1px solid rgba(255,255,255,0.1);
  margin: 12px 0;
}

/* ── Mind map ── */
.mindmap-wrapper {
  max-height: 500px;
  overflow-y: auto;
}

/* ── Transcript section ── */
.transcript-toggle {
  margin-top: 16px;
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.subtitle-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.segment-count {
  font-size: 0.75rem;
  color: #888;
}
.transcript-box {
  margin-top: 10px;
  max-height: 300px;
  overflow-y: auto;
  background: rgba(0,0,0,0.3);
  border-radius: 8px;
  padding: 12px;
}
.transcript-box pre {
  font-size: 0.8rem;
  line-height: 1.6;
  color: #999;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

/* ── Subtitle segments ── */
.subtitle-segments {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.segment-row {
  display: flex;
  gap: 12px;
  padding: 3px 0;
  font-size: 0.8rem;
  line-height: 1.5;
}
.seg-time {
  color: #667eea;
  font-family: monospace;
  min-width: 45px;
  flex-shrink: 0;
}
.seg-text {
  color: #bbb;
}

/* ── Chat Q&A ── */
.chat-container {
  display: flex;
  flex-direction: column;
  height: 450px;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
  text-align: center;
}
.chat-empty-icon {
  font-size: 2rem;
  margin-bottom: 8px;
}
.chat-hint {
  font-size: 0.8rem;
  color: #555;
  margin-top: 4px;
}
.chat-message {
  display: flex;
  max-width: 85%;
}
.chat-message.user {
  align-self: flex-end;
}
.chat-message.assistant {
  align-self: flex-start;
}
.message-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 0.85rem;
  line-height: 1.6;
}
.chat-message.user .message-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.chat-message.assistant .message-bubble {
  background: rgba(255,255,255,0.06);
  color: #ccccee;
  border-bottom-left-radius: 4px;
}
.message-content :deep(h2) {
  font-size: 1rem;
  margin: 8px 0 4px;
  color: #e8e8f0;
}
.message-content :deep(h3) {
  font-size: 0.95rem;
  margin: 6px 0 3px;
  color: #ddddee;
}
.message-content :deep(.list-item) {
  padding: 1px 0;
}
.message-content :deep(.num) {
  color: #667eea;
  font-weight: 600;
  margin-right: 4px;
}
.message-content :deep(.bullet) {
  color: #667eea;
  font-weight: 600;
  margin-right: 4px;
}
.message-content :deep(strong) {
  color: #e8e8f0;
}
.message-content :deep(.inline-code) {
  background: rgba(0,0,0,0.3);
  border-radius: 3px;
  padding: 1px 4px;
  font-size: 0.8rem;
}
.typing-indicator {
  display: inline-flex;
  padding: 4px 0 0;
}
.chat-input-area {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.chat-input {
  flex: 1;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 8px 12px;
  color: #ccccee;
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.2s;
}
.chat-input:focus {
  border-color: #667eea;
}
.chat-input::placeholder {
  color: #666;
}
.chat-input:disabled {
  opacity: 0.5;
}

/* ── Transition ── */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
