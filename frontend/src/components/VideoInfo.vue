<template>
  <div class="card video-info-card">
    <div class="video-layout">
      <div class="thumbnail-wrapper">
        <img
          v-if="info.thumbnail"
          :src="info.thumbnail"
          :alt="info.title"
          class="thumbnail"
          @error="onImgError"
        />
        <div v-else class="thumbnail-placeholder">No Image</div>
        <span v-if="info.duration_str" class="duration-badge">{{ info.duration_str }}</span>
      </div>
      <div class="video-meta">
        <h3 class="video-title">{{ info.title }}</h3>
        <div class="meta-row">
          <span v-if="info.uploader" class="meta-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            {{ info.uploader }}
          </span>
          <span v-if="info.view_count" class="meta-item">
            {{ formatViews(info.view_count) }} 次播放
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ info: Object })

function formatViews(n) {
  if (!n) return ''
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function onImgError(e) {
  e.target.style.display = 'none'
}
</script>

<style scoped>
.video-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.thumbnail-wrapper {
  position: relative;
  flex-shrink: 0;
  width: 280px;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0,0,0,0.3);
}
.thumbnail {
  width: 100%;
  height: auto;
  display: block;
}
.thumbnail-placeholder {
  width: 280px;
  height: 158px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
}
.duration-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0,0,0,0.8);
  color: #fff;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
}
.video-meta {
  flex: 1;
  min-width: 0;
}
.video-title {
  font-size: 1.15rem;
  font-weight: 600;
  color: #e8e8f0;
  margin-bottom: 10px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  color: #8888aa;
}

@media (max-width: 640px) {
  .video-layout { flex-direction: column; }
  .thumbnail-wrapper { width: 100%; }
}
</style>
