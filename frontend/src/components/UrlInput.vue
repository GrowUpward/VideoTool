<template>
  <div class="card url-input-card">
    <div class="input-row">
      <n-input
        v-model:value="url"
        placeholder="粘贴视频链接... (YouTube / B站 / 抖音 / 1800+ 平台)"
        size="large"
        :loading="loading"
        clearable
        @keyup.enter="handleParse"
        @paste="handlePaste"
        class="url-input"
      >
        <template #prefix>
          <n-icon size="20"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></n-icon>
        </template>
      </n-input>
      <n-button
        type="primary"
        size="large"
        :loading="loading"
        :disabled="!url.trim()"
        @click="handleParse"
        class="parse-btn"
      >
        解析
      </n-button>
    </div>
    <div class="supported-platforms">
      <span class="platform-tag">YouTube</span>
      <span class="platform-tag">B站</span>
      <span class="platform-tag">抖音</span>
      <span class="platform-tag">Twitter/X</span>
      <span class="platform-tag">Instagram</span>
      <span class="platform-tag">TikTok</span>
      <span class="platform-tag">+ 1800 更多</span>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { NInput, NButton, NIcon } from 'naive-ui'

const props = defineProps({ loading: Boolean })
const emit = defineEmits(['parsed'])
const url = ref('')

/**
 * 从分享文本中提取 URL（如 B 站 App 分享格式：'【标题】 https://b23.tv/xxx'）
 */
function extractUrl(text) {
  const trimmed = text.trim()
  // 尝试匹配 http/https 链接
  const match = trimmed.match(/https?:\/\/[^\s"'】）)]+/)
  return match ? match[0] : trimmed
}

function handleParse() {
  if (url.value.trim()) {
    emit('parsed', extractUrl(url.value))
  }
}

function handlePaste(e) {
  nextTick(() => {
    const pasted = e.target.value || url.value
    // 提取 URL 并回填到输入框
    const extracted = extractUrl(pasted)
    if (extracted !== pasted.trim()) {
      url.value = extracted
    }
    if (extracted && extracted.startsWith('http')) {
      // Auto-parse on paste
      setTimeout(() => emit('parsed', extracted), 300)
    }
  })
}
</script>

<style scoped>
.url-input-card {
  padding: 28px;
}
.input-row {
  display: flex;
  gap: 12px;
}
.url-input {
  flex: 1;
}
.parse-btn {
  min-width: 100px;
  font-weight: 600;
}
.supported-platforms {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.platform-tag {
  font-size: 0.75rem;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(102, 126, 234, 0.15);
  color: #8899cc;
  border: 1px solid rgba(102, 126, 234, 0.2);
}
</style>
