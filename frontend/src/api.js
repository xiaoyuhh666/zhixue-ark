/* 后端 API 封装：REST + SSE（fetch + ReadableStream 手动解析） */

/* 后端基地址：开发/本地部署留空走同域；GitHub Pages 等分离部署时
   通过构建环境变量 VITE_API_BASE 指向后端（如 https://xxx.onrender.com） */
const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(url, options = {}) {
  const res = await fetch(API_BASE + url, withAuth(options))
  if (res.status === 401) return handle401() // 登录过期：清态回落地页重登
  if (!res.ok) {
    // 优先透出后端 HTTPException 的 detail（如「用户名或密码错误」）
    let msg = `请求失败（HTTP ${res.status}）`
    try {
      const data = await res.json()
      if (typeof data?.detail === 'string') msg = data.detail
    } catch { /* 保留默认文案 */ }
    throw new Error(msg)
  }
  return res.json()
}

/* ---- 登录态注入：所有业务请求统一携带 Bearer token ---- */

function getToken() {
  const saved = JSON.parse(localStorage.getItem('ark_user') || 'null')
  return saved?.token || ''
}

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/* 给 fetch/XHR options 注入鉴权头（headers 为 undefined 或普通对象均可） */
function withAuth(options = {}) {
  return { ...options, headers: { ...(options.headers || {}), ...authHeaders() } }
}

/* 401 统一处理：清掉失效登录态并回到落地页，用户重新登录 */
function handle401() {
  localStorage.removeItem('ark_user')
  location.reload()
  throw new Error('登录已过期，请重新登录')
}

/* ---- 账号认证（登录 / 注册）---- */
export function registerUser(data) {
  return request('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
}

export function loginUser(data) {
  return request('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
}

/* 当前登录账号本人资料（昵称/专业/年级），Bearer token 鉴权 */
export function getMe() {
  const saved = JSON.parse(localStorage.getItem('ark_user') || 'null')
  return request('/api/auth/me', {
    headers: saved?.token ? { Authorization: `Bearer ${saved.token}` } : {}
  }).then(d => d.user)
}

export function getConversations() {
  return request('/api/conversations')
}

export function getConversation(id) {
  return request(`/api/conversations/${id}`)
}

export function createConversation(title) {
  return request('/api/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  })
}

export function deleteConversation(id) {
  return request(`/api/conversations/${id}`, { method: 'DELETE' })
}

/* ---- 画像与记忆（里程碑 3）---- */

export function getProfile() {
  return request('/api/profile')
}

export function updateProfile(data) {
  return request('/api/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
}

/* 从最近对话+长期记忆提炼画像候选（画像改版 2026-09-20） */
export function extractProfile() {
  return request('/api/profile/extract', { method: 'POST' })
}

export function getMemories(q = '') {
  return request(`/api/memories${q ? `?q=${encodeURIComponent(q)}` : ''}`)
}

export function createMemory(content, tag) {
  return request('/api/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, tag })
  })
}

export function deleteMemory(id) {
  return request(`/api/memories/${id}`, { method: 'DELETE' })
}

/* ---- 智能体目录（里程碑 5）---- */

export function getAgents() {
  return request('/api/agents')
}

export function getStats() {
  return request('/api/stats')
}

/* ---- 知识库 RAG（里程碑 4）---- */

export function getKbDocuments() {
  return request('/api/kb/documents')
}

/* 文档全文（里程碑 7 引用溯源）：向量块按序拼接还原原文 */
export function getKbDocContent(id) {
  return request(`/api/kb/documents/${id}/content`)
}

/* 检索试验台：输入问题实时看 Top-K 命中片段与相似度 */
export function searchKb(q, k = 3) {
  return request(`/api/kb/search?q=${encodeURIComponent(q)}&k=${k}`)
}

/* 分块可视化：取回该文档全部分块（按块序） */
export function getKbChunks(id) {
  return request(`/api/kb/documents/${id}/chunks`)
}

/* XHR 上传以获取进度回调（fetch 的 upload 进度不可读），onProgress 入参 0~1 */
export function uploadKbDoc(file, onProgress, category = 'general') {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/api/kb/upload`)
    xhr.responseType = 'json'
    const auth = authHeaders()
    if (auth.Authorization) xhr.setRequestHeader('Authorization', auth.Authorization)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve(xhr.response)
        : reject(new Error(`请求失败（HTTP ${xhr.status}）`))
    xhr.onerror = () => reject(new Error('网络错误，请稍后重试'))
    const fd = new FormData()
    fd.append('file', file)
    fd.append('category', category) // 归属智能体域：学习/竞赛/科研/求职/生活/通用
    xhr.send(fd)
  })
}

export function deleteKbDoc(id) {
  return request(`/api/kb/documents/${id}`, { method: 'DELETE' })
}

/* ---- 任务计划中心（2026-09-20）---- */

export function getPlans() {
  return request('/api/plans')
}

export function createPlan(data) {
  return request('/api/plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
}

export function updatePlan(id, data) {
  return request(`/api/plans/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
}

export function deletePlan(id) {
  return request(`/api/plans/${id}`, { method: 'DELETE' })
}

/* ---- 学习足迹（2026-09-20）---- */

export function getInsights() {
  return request('/api/insights')
}

/* ---- 设置（2026-09-20，个人中心 Tab）---- */

export function getSettings() {
  return request('/api/settings')
}

// 模型广场：目录元数据 + 各家实时接入状态（已配置/演示/最近实测延迟）
export function getModelSquare() {
  return request('/api/settings/models')
}

export function updateSettings(data) {
  return request('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
}

// 连通性测试：用当前生效 Key 发最小请求，验证 Key 真实可用
export function testSettingsKey(provider) {
  return request('/api/settings/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider })
  })
}

export function exportData() {
  return request('/api/settings/export')
}

export function clearDemoData() {
  return request('/api/settings/demo-data', { method: 'DELETE' })
}

/**
 * POST /api/chat SSE 流式对话。
 * 帧格式 `data: {json}\n\n`，逐帧回调 onEvent。
 */
export async function streamChat(payload, onEvent, signal) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
    signal
  })
  if (res.status === 401) return handle401() // 登录过期：清态回落地页重登
  if (!res.ok) throw new Error(`请求失败（HTTP ${res.status}）`)
  if (!res.body) throw new Error('当前浏览器不支持流式响应')

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let frame = null // 当前帧累积的 data 负载

  const dispatch = (raw) => {
    const s = raw.trim()
    if (!s || s === '[DONE]') return
    try {
      onEvent(JSON.parse(s))
    } catch {
      /* 忽略无法解析的帧 */
    }
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let nl
    while ((nl = buffer.indexOf('\n')) >= 0) {
      let line = buffer.slice(0, nl)
      buffer = buffer.slice(nl + 1)
      if (line.endsWith('\r')) line = line.slice(0, -1)
      if (line === '') {
        if (frame !== null) { dispatch(frame); frame = null }
      } else if (line.startsWith('data:')) {
        const part = line.slice(5)
        frame = frame === null ? part : frame + '\n' + part
      }
      /* 其余字段行（event:/id:/注释）忽略 */
    }
  }
  if (frame !== null) dispatch(frame)
}
