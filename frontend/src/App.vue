<template>
  <n-config-provider :theme="darkTheme">
    <n-message-provider>
      <div class="app">
        <header class="app-header">
          <h1>万能视频下载器</h1>
          <p class="subtitle">支持 B站、YouTube、抖音等 1800+ 平台 · 一键解析下载</p>
        </header>

        <UrlInput @parsed="onVideoParsed" :loading="parsing" />

        <transition name="fade">
          <VideoInfo v-if="videoInfo" :info="videoInfo" />
        </transition>

        <transition name="fade">
          <QualitySelect
            v-if="videoInfo"
            :formats="videoInfo.formats"
            v-model="selectedQuality"
            @download="startDownloadVideo"
            :downloading="downloading"
          />
        </transition>

        <transition name="fade">
          <DownloadProgress
            v-if="currentTask"
            :task="currentTask"
            :url="currentUrl"
          />
        </transition>

        <DownloadHistory :history="history" />

        <!-- AI Summary Button -->
        <transition name="fade">
          <div v-if="videoInfo && !showSummary" class="card ai-trigger-card">
            <n-button
              type="primary"
              ghost
              block
              size="large"
              @click="showSummary = true"
            >
              AI 视频总结
            </n-button>
          </div>
        </transition>

        <!-- AI Summary Panel -->
        <transition name="fade">
          <AiSummary v-if="showSummary && currentUrl" :url="currentUrl" />
        </transition>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref } from 'vue'
import { NConfigProvider, NMessageProvider, NButton, darkTheme } from 'naive-ui'
import UrlInput from './components/UrlInput.vue'
import VideoInfo from './components/VideoInfo.vue'
import QualitySelect from './components/QualitySelect.vue'
import DownloadProgress from './components/DownloadProgress.vue'
import DownloadHistory from './components/DownloadHistory.vue'
import AiSummary from './components/AiSummary.vue'
import { parseUrl, startDownload, subscribeProgress, getDownloadUrl } from './api.js'

const videoInfo = ref(null)
const selectedQuality = ref('')
const parsing = ref(false)
const downloading = ref(false)
const currentTask = ref(null)
const currentUrl = ref('')
const history = ref([])
const showSummary = ref(false)

async function onVideoParsed(url) {
  parsing.value = true
  videoInfo.value = null
  currentTask.value = null
  showSummary.value = false
  currentUrl.value = url
  try {
    const info = await parseUrl(url)
    videoInfo.value = info
    if (info.formats.length > 0) {
      selectedQuality.value = info.formats[0].value
    }
  } catch (e) {
    console.error(e)
    alert(e.message)
  } finally {
    parsing.value = false
  }
}

async function startDownloadVideo() {
  if (!videoInfo.value || !selectedQuality.value) return
  downloading.value = true
  try {
    const { task_id } = await startDownload(currentUrl.value, selectedQuality.value)
    const task = {
      task_id,
      status: 'downloading',
      percent: 0,
      speed: '',
      eta: '',
      title: videoInfo.value.title,
      thumbnail: videoInfo.value.thumbnail,
    }
    currentTask.value = task

    subscribeProgress(
      task_id,
      (data) => {
        currentTask.value = { ...currentTask.value, ...data }
      },
      (data) => {
        currentTask.value = { ...currentTask.value, ...data, status: 'completed' }
        history.value.unshift({
          ...currentTask.value,
          downloadUrl: getDownloadUrl(task_id),
        })
        downloading.value = false
      },
      (err) => {
        currentTask.value = { ...currentTask.value, status: 'failed', error: err }
        downloading.value = false
      }
    )
  } catch (e) {
    console.error(e)
    alert(e.message)
    downloading.value = false
  }
}
</script>

<style scoped>
.ai-trigger-card {
  padding: 16px 24px;
  text-align: center;
}
</style>
