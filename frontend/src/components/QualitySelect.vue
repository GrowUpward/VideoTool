<template>
  <div class="card quality-card">
    <div class="quality-header">
      <span class="label">选择画质</span>
    </div>
    <n-radio-group v-model:value="modelValue" class="quality-options">
      <n-radio-button
        v-for="fmt in formats"
        :key="fmt.value"
        :value="fmt.value"
        :label="fmt.label"
      >
        {{ fmt.label }}
      </n-radio-button>
    </n-radio-group>
    <n-button
      type="primary"
      size="large"
      block
      :loading="downloading"
      :disabled="!modelValue"
      @click="$emit('download')"
      class="download-btn"
    >
      <template #icon>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      </template>
      {{ downloading ? '下载中...' : '开始下载' }}
    </n-button>
  </div>
</template>

<script setup>
import { NRadioGroup, NRadioButton, NButton } from 'naive-ui'

defineProps({
  formats: Array,
  downloading: Boolean,
})
const modelValue = defineModel('modelValue')
defineEmits(['download'])
</script>

<style scoped>
.quality-header {
  margin-bottom: 12px;
}
.quality-header .label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #aaaacc;
}
.quality-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  margin-bottom: 16px;
}
.download-btn {
  margin-top: 8px;
  font-weight: 600;
  height: 48px;
  font-size: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}
.download-btn:hover {
  opacity: 0.9;
}
</style>
