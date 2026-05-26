<template>
  <div class="mindmap-container" ref="container"></div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'

const props = defineProps({ content: String })
const container = ref(null)

function renderMindMap(markdown) {
  if (!container.value || !markdown) return

  // Parse markdown headings into a tree
  const lines = markdown.split('\n').filter(l => l.trim())
  let html = '<ul>'
  let depth = 0

  for (const line of lines) {
    const match = line.match(/^(#{1,6})\s+(.+)$/)
    if (match) {
      const newDepth = match[1].length
      const text = match[2].trim()
      while (depth < newDepth) { html += '<ul>'; depth++ }
      while (depth > newDepth) { html += '</ul>'; depth-- }
      html += `<li>${escapeHtml(text)}</li>`
    }
  }
  while (depth > 0) { html += '</ul>'; depth-- }

  container.value.innerHTML = html
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

watch(() => props.content, (val) => { nextTick(() => renderMindMap(val)) })
onMounted(() => { if (props.content) renderMindMap(props.content) })
</script>

<style scoped>
.mindmap-container {
  padding: 16px 0;
  overflow-x: auto;
}
.mindmap-container :deep(ul) {
  list-style: none;
  padding-left: 20px;
  border-left: 2px solid rgba(102, 126, 234, 0.3);
  margin: 4px 0;
}
.mindmap-container :deep(ul:first-child) {
  border-left: none;
  padding-left: 0;
}
.mindmap-container :deep(li) {
  position: relative;
  padding: 6px 0 6px 16px;
  color: #ccccee;
  font-size: 0.9rem;
  line-height: 1.5;
}
.mindmap-container :deep(li)::before {
  content: '';
  position: absolute;
  left: -2px;
  top: 50%;
  width: 14px;
  height: 2px;
  background: rgba(102, 126, 234, 0.3);
}
.mindmap-container :deep(ul:first-child > li)::before {
  display: none;
}
.mindmap-container :deep(li:first-child) {
  font-weight: 600;
  color: #e8e8f0;
  font-size: 1rem;
}
</style>
