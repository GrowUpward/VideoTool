const API_BASE = '/api'

export async function parseUrl(url) {
  const res = await fetch(`${API_BASE}/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(err.detail || '解析失败')
  }
  return res.json()
}

export async function startDownload(url, quality) {
  const res = await fetch(`${API_BASE}/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, quality }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(err.detail || '下载失败')
  }
  return res.json()
}

export function subscribeProgress(taskId, onUpdate, onComplete, onError) {
  const eventSource = new EventSource(`${API_BASE}/progress/${taskId}`)

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.status === 'completed') {
        onUpdate(data)
        onComplete(data)
        eventSource.close()
      } else if (data.status === 'failed') {
        onError(data.error || '下载失败')
        eventSource.close()
      } else if (data.status === 'not_found') {
        onError('任务不存在')
        eventSource.close()
      } else {
        onUpdate(data)
      }
    } catch (e) {
      onError('数据解析错误')
      eventSource.close()
    }
  }

  eventSource.onerror = () => {
    onError('连接中断')
    eventSource.close()
  }

  return eventSource
}

export function getDownloadUrl(taskId) {
  return `${API_BASE}/file/${taskId}`
}

/**
 * Parse SSE stream from a fetch response and dispatch events to callbacks.
 * @param {Response} response - fetch response with ReadableStream
 * @param {Object} callbacks - map of event name to handler function
 *   e.g. { subtitle: (data) => {}, summary: (data) => {}, done: () => {}, error: (data) => {} }
 */
export async function handleSSEStream(response, callbacks = {}) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''
  let eventData = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const rawLine of lines) {
        const line = rawLine.replace(/\r$/, '')  // strip trailing \r (CRLF support)

        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          eventData = line.slice(5).trim()
        } else if (line.trim() === '' && eventType) {
          // Empty line = dispatch event
          const handler = callbacks[eventType]
          if (handler) {
            if (eventType === 'done') {
              handler()
            } else {
              handler(eventData)
            }
          }
          eventType = ''
          eventData = ''
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  // Handle any remaining buffered event
  if (eventType) {
    const handler = callbacks[eventType]
    if (handler) {
      if (eventType === 'done') {
        handler()
      } else {
        handler(eventData)
      }
    }
  }
}

/**
 * Stream AI summary via SSE. Calls callbacks for each event type.
 * @param {string} url - video URL
 * @param {string} format - summary format (summary, key_points, mind_map, qa)
 * @param {boolean} force - force re-generate
 * @param {Object} callbacks - { subtitle, summary, done, error }
 */
export async function summarizeVideo(url, format = 'summary', force = false, callbacks = {}) {
  const res = await fetch(`${API_BASE}/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, format, force }),
  })
  if (!res.ok) {
    throw new Error(`请求失败: ${res.status}`)
  }
  await handleSSEStream(res, callbacks)
}

/**
 * Stream chat Q&A via SSE.
 * @param {string} url - video URL
 * @param {string} question - user question
 * @param {string} subtitleText - already-extracted subtitle text (avoids re-extraction)
 * @param {Object} callbacks - { answer, done, error }
 */
export async function chatWithVideo(url, question, subtitleText = '', callbacks = {}) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, question, subtitle_text: subtitleText }),
  })
  if (!res.ok) {
    throw new Error(`请求失败: ${res.status}`)
  }
  await handleSSEStream(res, callbacks)
}
