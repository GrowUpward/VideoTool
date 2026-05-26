<template>
  <transition name="fade">
    <div v-if="history.length > 0" class="card history-card">
      <div class="history-header">
        <span class="label">下载记录</span>
        <n-tag size="small" round>{{ history.length }}</n-tag>
      </div>
      <div class="history-list">
        <div v-for="(item, i) in history" :key="i" class="history-item">
          <div class="item-info">
            <span class="item-title">{{ item.title || '未知视频' }}</span>
            <span class="item-status">
              <n-tag :type="item.status === 'completed' ? 'success' : 'error'" size="tiny" round>
                {{ item.status === 'completed' ? '已完成' : '失败' }}
              </n-tag>
            </span>
          </div>
          <div class="item-actions">
            <n-button
              v-if="item.status === 'completed' && item.downloadUrl"
              size="tiny"
              tag="a"
              :href="item.downloadUrl"
              download
              quaternary
              type="primary"
            >
              保存
            </n-button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { NTag, NButton } from 'naive-ui'

defineProps({ history: Array })
</script>

<style scoped>
.history-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.history-header .label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #aaaacc;
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
}
.item-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: 0.85rem;
  color: #ccccee;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-actions {
  flex-shrink: 0;
  margin-left: 12px;
}
</style>
