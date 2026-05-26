<template>
  <div class="card progress-card">
    <div class="progress-header">
      <span class="title">{{ task.title || '正在下载...' }}</span>
      <n-tag :type="statusType" size="small" round>{{ statusText }}</n-tag>
    </div>

    <n-progress
      v-if="task.status === 'downloading'"
      type="line"
      :percentage="Math.round(task.percent || 0)"
      :processing="task.status === 'downloading'"
      :stroke-width="14"
      class="progress-bar"
    />

    <div v-if="task.status === 'downloading'" class="progress-stats">
      <span>{{ (task.percent || 0).toFixed(1) }}%</span>
      <span v-if="task.speed">{{ task.speed }}</span>
      <span v-if="task.eta">剩余 {{ task.eta }}</span>
    </div>

    <div v-if="task.status === 'completed'" class="complete-actions">
      <n-button type="success" tag="a" :href="downloadUrl" download strong>
        保存文件
      </n-button>
    </div>

    <div v-if="task.status === 'failed'" class="error-msg">
      下载失败: {{ task.error || '未知错误' }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NProgress, NTag, NButton } from 'naive-ui'
import { getDownloadUrl } from '../api.js'

const props = defineProps({ task: Object })

const downloadUrl = computed(() => getDownloadUrl(props.task.task_id))

const statusType = computed(() => {
  const s = props.task.status
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'error'
  return 'info'
})

const statusText = computed(() => {
  const s = props.task.status
  if (s === 'downloading') return '下载中'
  if (s === 'completed') return '已完成'
  if (s === 'failed') return '失败'
  return s
})
</script>

<style scoped>
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.progress-header .title {
  font-size: 0.95rem;
  font-weight: 500;
  color: #ccccee;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 12px;
}
.progress-bar {
  margin-bottom: 10px;
}
.progress-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #8888aa;
}
.complete-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}
.error-msg {
  color: #f87171;
  font-size: 0.85rem;
  margin-top: 8px;
}
</style>
