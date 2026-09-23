<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import TopNav from './components/TopNav.vue'
import LandingView from './components/LandingView.vue'
import ChatConfig from './components/ChatConfig.vue'
import ChatView from './components/ChatView.vue'
import KnowledgeView from './components/KnowledgeView.vue'
import PlansView from './components/PlansView.vue'
import InsightsView from './components/InsightsView.vue'
import ModelSquare from './components/ModelSquare.vue'
import AccountView from './components/AccountView.vue'
import AuthModal from './components/AuthModal.vue'
import { getConversations, getConversation, deleteConversation, streamChat, createPlan, getKbDocuments, getMemories, getMe, onUnauthorized } from './api'

/* 视图元信息：顶栏标题 / 徽标 / 占位页页头
   2026-09-20 二次改版：「对话」与「智能体」合并为「智能对话」——
   先选智能体（选择页）再进入对话；导航收敛为 4 项 */
const VIEWS = {
  chat: {
    title: '智能对话', badge: '调度智能体在线',
    kicker: '01 — Smart Chat', en: 'Pick An Agent · Start Chatting',
    desc: '选择一位领域智能体开始专属对话；复合任务由调度智能体自动拆解，多位智能体协作完成。'
  },
  knowledge: {
    title: '知识库', badge: '知识库',
    kicker: '02 — Knowledge Base', en: 'Upload · Parse · Chunk · Embed',
    desc: '上传课程资料、竞赛信息等文档，自动解析、分块并向量化入库；对话时检索相关片段，回答附带来源引用。'
  },
  plans: {
    title: '任务计划', badge: '任务计划',
    kicker: '03 — Task Plans', en: 'From Chat To Action',
    desc: '把对话中产生的规划一键转入任务清单：步骤勾选、进度跟踪、截止日管理，让建议真正落地执行。'
  },
  insights: {
    title: '学习足迹', badge: '学习足迹',
    kicker: '04 — Learning Insights', en: 'Trend · Distribution · Citations',
    desc: '回看你的使用轨迹：对话趋势、智能体分布与知识库引用命中，平台如何服务你，数据说话。'
  },
  models: {
    title: '模型广场', badge: '模型广场',
    kicker: '05 — Model Square', en: 'Models In Action',
    desc: '平台已接入的三家大模型供应商：规格、接入状态与实测延迟一览；设为默认立即生效，密钥集中在个人中心管理。'
  },
  account: {
    title: '个人中心', badge: '个人中心',
    kicker: 'ME — Account', en: 'Persona · Memory · Stats · Settings',
    desc: '系统认识你的一切，集中在这里：画像、长期记忆、使用统计与平台设置，完全透明、可编辑。'
  }
}

const view = ref('chat')
/* 「智能对话」当前智能体（2026-09-20 甲方案：顶部胶囊条替代选择页），
   'session' 表示正在回放历史会话（胶囊条无高亮）；
   选中态持久化到 localStorage，刷新后不丢（如停留在竞赛指导） */
const pickedAgent = ref((() => {
  const saved = localStorage.getItem('ark_agent')
  return ['study', 'competition', 'research', 'career', 'life'].includes(saved) ? saved : 'study'
})())
/* 记住当前智能体（回放态 'session' 不记录，保持上次选中） */
function rememberAgent(key) {
  if (key && key !== 'session') localStorage.setItem('ark_agent', key)
}
const provider = ref('deepseek')
/* 会话与消息状态（前置声明：刷新时 applyHashView 在 setup 同步段恢复会话，
   需先于 hash 路由逻辑初始化，避免 TDZ） */
const conversations = ref([])
const activeId = ref(null)
const messages = ref([])
const streaming = ref(false)
const citationJump = ref(null)  // 引用溯源跳转（里程碑 7）：{docId, snippet}
const pendingQuestion = ref('')  // 知识库检索试验台「去对话页追问」预填的问题文本
let abortCtl = null
/* 账号门禁（2026-09-20）：落地页所有入口统一走「未登录弹登录框，已登录直进」。
   token + 用户存 localStorage（ark_user），刷新保持登录态 */
const user = ref(JSON.parse(localStorage.getItem('ark_user') || 'null'))
const showAuth = ref(false)

/* 401 全局响应式处理（防刷屏改版 2026-09-23）：
   api 层确认「带 token 却被拒」（token 过期/失效）时回调到这里——
   清账号态、回落地页并弹登录框，全程无整页刷新，杜绝 401→reload 死循环 */
onUnauthorized(() => {
  user.value = null
  entered.value = false
  showAuth.value = true
  ElMessage.warning('登录已过期，请重新登录')
  history.replaceState(null, '', window.location.pathname + window.location.search)
})

/* 落地页门禁：hash 路由管理（#/app=主界面，无 hash=落地页），
   浏览器后退/前进可正常在两者间切换，刷新也保持状态；
   未登录时即使 hash 是 #/app 也拦回落地页并弹登录框 */
const entered = ref(window.location.hash.startsWith('#/app') && !!user.value)
const accountTab = ref('profile')  // 个人中心当前 Tab（hash 二级路径驱动，参与回退历史）
/* 视图切换写入 hash 历史：浏览器「返回」逐级回退
   （个人中心 -> 智能对话 -> 落地页），而不是一次跳回落地页 */
function setView(key, convId) {
  /* 支持二级路径（如 account/settings）：一级驱动视图，二级同步个人中心 Tab */
  const [main, sub] = String(key).split('/')
  view.value = main
  /* 会话 id 编入 hash（#/app/<id>）：刷新、后退、前进均可恢复当前会话回放 */
  const target = '#/app' + (main === 'chat' ? (convId != null ? `/${convId}` : '') : `/${key}`)
  if (entered.value && window.location.hash !== target) {
    window.location.hash = target  // 触发 hashchange，历史栈逐条入栈
  }
  if (main === 'account' && sub && ['profile', 'memory', 'stats', 'settings'].includes(sub)) {
    accountTab.value = sub
  }
}
/* 从 hash 恢复视图（返回/前进/刷新）：无子路径时回落到智能对话；
   支持二级路径 #/app/account/<tab>（个人中心内 Tab 也参与回退历史）；
   #/app/<纯数字> 识别为会话 id，恢复该会话的历史回放 */
function applyHashView() {
  const segs = window.location.hash.slice(5).split('/').filter(Boolean)
  const key = segs[0] || ''
  if (key && /^\d+$/.test(key)) {
    view.value = 'chat'
    const id = Number(key)
    if (id !== activeId.value) {
      abortStream()
      activeId.value = id
      pickedAgent.value = 'session'  // 历史回放态：胶囊条无高亮
      loadConversationData(id)
    }
    return
  }
  view.value = key && VIEWS[key] ? key : 'chat'
  if (view.value === 'account') {
    const t = segs[1]
    // 无二级路径的 #/app/account 一律回落画像 Tab，保证回退「每按一次有一步」
    accountTab.value = t && ['profile', 'memory', 'stats', 'settings'].includes(t) ? t : 'profile'
  }
}
/* 个人中心 Tab 入栈：#/app/account/<tab>，浏览器返回可在 Tab 间逐级回退 */
function setAccountTab(t) {
  accountTab.value = t
  const target = `#/app/account/${t}`
  if (entered.value && window.location.hash !== target) window.location.hash = target
}
function enterApp(_target) {
  // 每次点击入口固定落在「01 智能对话」；主界面内的返回走顶栏 logo 旁的「返回首页」
  view.value = 'chat'
  if (!user.value) {
    showAuth.value = true
    return
  }
  window.location.hash = '#/app'
}
function onHashChange() {
  const toApp = window.location.hash.startsWith('#/app')
  if (toApp && !user.value) {
    // 直接输入 /#/app 的未登录访客：拦回落地页并弹登录
    showAuth.value = true
    history.replaceState(null, '', window.location.pathname + window.location.search)
    entered.value = false
    return
  }
  entered.value = toApp
  if (toApp) applyHashView()  // 返回键回主界面时恢复对应视图
}
if (entered.value) applyHashView()  // 刷新 #/app/<view> 直接恢复视图
/* 头像更新（个人中心画像页上传）：同步本地账号态，全站头像即时生效 */
function onAvatarUpdated(avatar) {
  user.value = { ...user.value, avatar }
  localStorage.setItem('ark_user', JSON.stringify(user.value))
}

/* 登录 / 注册成功：落盘用户信息，关闭弹窗，进入主界面（固定落在智能对话） */
function authSuccess(u) {
  user.value = u
  localStorage.setItem('ark_user', JSON.stringify(u))
  showAuth.value = false
  loadUserData()  // 登录后补拉会话/知识库/记忆（未登录期间不预取）
  enterApp()
}
/* 退出登录：清账号态并回落地页 */
function logout() {
  user.value = null
  localStorage.removeItem('ark_user')
  entered.value = false
  history.replaceState(null, '', window.location.pathname + window.location.search)
}

/* 返回首页：顶栏 logo 旁的入口，回落地页（入栈历史，浏览器前进可回主界面） */
function goHome() {
  abortStream?.()
  entered.value = false
  if (window.location.hash) {
    history.pushState(null, '', window.location.pathname + window.location.search)
  }
}

/* 切换登录：登出当前账号并直接弹出登录框，换号无需多点一步 */
function switchAccount() {
  logout()
  showAuth.value = true
}

/* 知识库菜单（输入框左下角）：useKb 检索开关；kbDocIds 勾选的检索范围（null=全部） */
const useKb = ref(true)
const kbDocIds = ref(null)
const kbDocs = ref([])  // 知识库文档列表 [{id, title, filename}]
const useMemory = ref(true)  // 长期记忆运用开关（关闭后回答不注入画像与记忆）
const memCount = ref(0)      // 记忆条数（开关胶囊展示）

const viewMeta = computed(() => VIEWS[view.value] || VIEWS.chat)

/* 模型清单（自原 Topbar 迁入）：左栏 ChatConfig 切换，顶栏仅展示当前模型简写 */
const MODELS = [
  { value: 'deepseek', name: 'DeepSeek', label: 'DEEPSEEK-V3' },
  { value: 'qwen', name: '通义千问', label: 'QWEN-PLUS' },
  { value: 'glm', name: '智谱清言', label: 'GLM-4' }
]
/* 当前会话标题：左栏会话卡与右舞台标题条共用 */
const activeTitle = computed(
  () => (conversations.value.find(c => c.id === activeId.value) || {}).title || ''
)

function abortStream() {
  if (abortCtl) {
    abortCtl.abort()
    abortCtl = null
  }
  streaming.value = false
}

function upsertConversation(id, title, lastMessage) {
  if (id == null) return
  const idx = conversations.value.findIndex(c => c.id === id)
  if (idx >= 0) {
    if (title) conversations.value[idx].title = title
    if (lastMessage) conversations.value[idx].last_message = lastMessage
  } else {
    conversations.value.unshift({
      id,
      title: title || '新对话',
      last_message: lastMessage || null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    })
  }
}

async function loadConversations(retried = false) {
  try {
    const list = await getConversations()
    conversations.value = Array.isArray(list) ? list : []
  } catch (e) {
    /* 首次失败静默重试一次：后端冷启动/服务切换窗口的瞬时失败不打扰用户；
       认证类 401 不重试不报错（登录框已弹出，重试只会重复打扰） */
    if (!retried && !e?.auth) {
      setTimeout(() => loadConversations(true), 1200)
      return
    }
    if (!e?.auth) ElMessage.error(e?.message || '加载历史会话失败')
  }
}

async function selectConversation(id) {
  if (id === activeId.value && view.value === 'chat') return
  abortStream()
  activeId.value = id
  pickedAgent.value = 'session'  // 历史回放：跳过智能体选择页（未知 key 回落默认欢迎）
  setView('chat', id)  // 会话 id 入 hash（可后退切换会话），走 hash 同步
  loadConversationData(id)
}

/* 拉取会话消息并回放（左栏选择与 hash 恢复共用）；
   竞态保护：响应返回时用户已切走（activeId 变化）则丢弃本次结果 */
async function loadConversationData(id) {
  try {
      const data = await getConversation(id)
      if (activeId.value !== id) return
      activeId.value = data.id
      messages.value = (data.messages || []).map(m => {
        const msg = {
          ...m,
          role: m.role === 'user' ? 'user' : 'assistant',
          agent: m.agent || '智学方舟',
          streaming: false
        }
        // 里程碑 7：澄清追问轮回放（plan.action === 'clarify'）
        if (m.plan?.action === 'clarify') {
          msg.agent = '调度智能体'
          msg.reason = m.plan.reason || '需要澄清'
          msg.clarify = { questions: m.plan.questions || [] }
          msg.steps = [
            { key: 'route', label: '调度智能体 · 识别意图', status: 'done' },
            { key: 'clarify', label: '调度智能体 · 澄清追问', status: 'done' }
          ]
        }
        // 里程碑 6：用 plan 列回放任务规划与分段回答（含工具步骤）
        else if (m.plan?.segments?.length) {
          msg.reason = m.plan.reason || ''
          msg.segments = m.plan.segments.map(s => ({ agent: s.label, label: s.label, content: s.content }))
          const labelMap = { kb_search: '知识检索', python_calc: '计算工具' }
          const tools = m.plan.tools || []
          const steps = [{ key: 'route', label: '调度智能体 · 识别意图', status: 'done' }]
          ;(m.plan.tasks || []).forEach((t, i) => {
            tools.filter(x => x.index === i).forEach(x => steps.push({
              key: `tool-r${i}-${x.name}`, label: `${labelMap[x.name] || x.name} · ${x.summary}`, status: 'done'
            }))
            steps.push({
              key: `task-${i}`,
              label: `${t.label}${t.objective ? ' · ' + t.objective : ''}`,
              status: 'done'
            })
          })
          if (m.plan.segments.length > (m.plan.tasks || []).length) {
            steps.push({ key: 'synth', label: '调度智能体 · 汇总整合', status: 'done' })
          }
          msg.steps = steps
        }
        return msg
      })
      upsertConversation(data.id, data.title)
    } catch (e) {
      ElMessage.error(e?.message || '加载会话失败')
    }
}

function newChat() {
  abortStream()
  activeId.value = null
  messages.value = []
  // 新建=回到当前智能体的专属欢迎页；从历史回放进入则默认学习助手
  if (pickedAgent.value === 'session') { pickedAgent.value = 'study'; rememberAgent('study') }
  setView('chat')  // 走 hash 同步，防与视图脱钩
}

async function removeConversation(id) {
  try {
    await deleteConversation(id)
    if (activeId.value === id) newChat()
    conversations.value = conversations.value.filter(c => c.id !== id)
  } catch (e) {
    ElMessage.error(e?.message || '删除会话失败')
  }
}

async function sendMessage(text) {
  const t = (text || '').trim()
  if (!t || streaming.value) return

  abortCtl = new AbortController()
  streaming.value = true

  messages.value.push({
    id: null, role: 'user', agent: '', content: t,
    model: '', created_at: new Date().toISOString()
  })
  const aiMsg = {
    id: null, role: 'assistant', agent: '智学方舟', content: '',
    model: provider.value, created_at: new Date().toISOString(), streaming: true,
    // 调度流水线：随 SSE 帧推进，用于协作过程可视化（里程碑 5）
    steps: [{ key: 'route', label: '调度智能体 · 识别意图', status: 'active' }],
    // 分段回答（里程碑 6）：多智能体协作时按任务分段渲染
    segments: []
  }
  messages.value.push(aiMsg)

  try {
    await streamChat(
      { conversation_id: activeId.value, message: t, provider: provider.value,
        use_kb: useKb.value, kb_doc_ids: kbDocIds.value, use_memory: useMemory.value },
      (ev) => {
        if (ev.type === 'meta') {
          if (ev.conversation_id != null) {
            activeId.value = ev.conversation_id
            upsertConversation(ev.conversation_id, ev.title, ev.last_message)
            /* 首条消息定下会话 id：replaceState 静默写入 hash（不入历史栈），
               此刻刷新也能恢复本会话 */
            const target = '#/app/' + ev.conversation_id
            if (window.location.hash !== target) history.replaceState(null, '', target)
          }
        } else if (ev.type === 'plan') {
          // 任务规划（里程碑 6）：构建任务链时间线；存 tasks 供「转为计划」按钮（任务计划中心）
          aiMsg.plan = { tasks: ev.tasks || [] }
          aiMsg.agent = (ev.tasks?.length > 1) ? '多智能体协作' : (ev.tasks?.[0]?.label || '智学方舟')
          aiMsg.reason = ev.reason || ''
          const route = aiMsg.steps.find(s => s.key === 'route')
          if (route) route.status = 'done'
          aiMsg.steps = aiMsg.steps.filter(s => s.key !== 'gen')
          ;(ev.tasks || []).forEach((task, i) => aiMsg.steps.push({
            key: `task-${i}`,
            label: `${task.label}${task.objective ? ' · ' + task.objective : ''}`,
            status: i === 0 ? 'active' : 'pending'
          }))
          if (ev.tasks?.length > 1) {
            aiMsg.steps.push({ key: 'synth', label: '调度智能体 · 汇总整合', status: 'pending' })
          }
        } else if (ev.type === 'status') {
          // 兜底切换等系统提示：作为时间线步骤展示，不产生正文
          aiMsg.steps.push({ key: `status-${aiMsg.steps.length}`, label: ev.message || '系统提示', status: 'done' })
        } else if (ev.type === 'agent_start') {
          // 任务开始：推进时间线并建分段
          const idx = ev.index ?? 0
          const act = aiMsg.steps.find(s => s.status === 'active')
          if (act) act.status = 'done'
          const step = aiMsg.steps.find(s => s.key === `task-${idx}` || s.key === 'synth')
          if (step) step.status = 'active'
          while (aiMsg.segments.length <= idx) aiMsg.segments.push({ agent: '', label: '', content: '' })
          aiMsg.segments[idx] = { agent: ev.agent, label: ev.agent, content: '' }
        } else if (ev.type === 'tool') {
          // 工具调用（里程碑 6）：在当前任务步骤前插入工具步骤
          const labelMap = { kb_search: '知识检索', python_calc: '计算工具' }
          const step = { key: `tool-${aiMsg.steps.length}-${ev.name}`, label: `${labelMap[ev.name] || ev.name} · ${ev.summary || '执行完成'}`, status: 'done' }
          const ai = aiMsg.steps.findIndex(s => s.status === 'active')
          if (ai >= 0) aiMsg.steps.splice(ai, 0, step)
          else aiMsg.steps.push(step)
        } else if (ev.type === 'clarify') {
          // 澄清追问（里程碑 7）：调度智能体反问，无任务规划与分段
          aiMsg.agent = '调度智能体'
          aiMsg.reason = ev.reason || '需要澄清'
          aiMsg.clarify = { questions: ev.questions || [] }
          const route = aiMsg.steps.find(s => s.key === 'route')
          if (route) route.status = 'done'
          aiMsg.steps.push({ key: 'clarify', label: '调度智能体 · 澄清追问', status: 'done' })
        } else if (ev.type === 'citations') {
          // RAG 命中：挂到当前助手消息上展示引用角标（时间线步骤由 tool 帧负责）
          aiMsg.citations = ev.items || []
        } else if (ev.type === 'delta') {
          if (ev.index != null && aiMsg.segments[ev.index]) {
            aiMsg.segments[ev.index].content += ev.content || ''
          }
          aiMsg.content += ev.content || ''
        } else if (ev.type === 'done') {
          aiMsg.id = ev.message_id
          aiMsg.streaming = false
          aiMsg.steps.forEach(s => { if (s.status === 'active' || s.status === 'pending') s.status = 'done' })
        } else if (ev.type === 'error') {
          aiMsg.streaming = false
          aiMsg.steps.forEach(s => { if (s.status === 'active') s.status = 'fail' })
          if (ev.kind === 'rate_limit') {
            /* 限流：气泡内渲染「换模型重试」错误卡，不弹 toast */
            aiMsg.error_kind = 'rate_limit'
            aiMsg.content = (ev.message || '当前模型限流，请稍后重试').replace(/^模型调用失败：/, '')
          } else {
            if (!aiMsg.content) aiMsg.content = `抱歉，本次请求出现问题：${ev.message || '未知错误'}`
            ElMessage.error(ev.message || '服务异常')
          }
        }
      },
      abortCtl.signal
    )
  } catch (e) {
    if (!abortCtl?.signal?.aborted && e?.name !== 'AbortError') {
      aiMsg.streaming = false
      aiMsg.steps.forEach(s => { if (s.status === 'active') s.status = 'fail' })
      if (!aiMsg.content) aiMsg.content = '抱歉，本次请求出现问题：网络异常，请稍后重试'
      ElMessage.error(e?.message || '网络错误')
    }
  } finally {
    aiMsg.streaming = false
    streaming.value = false
    abortCtl = null
  }
}

/* 限流救场：切换供应商并重发原问题。
   失败的 assistant 消息未落库（error 帧前不存储），直接移除气泡即可 */
function retryWith(p) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role !== 'user' && last.error_kind) messages.value.pop()
  const lastUser = [...messages.value].reverse().find(m => m.role === 'user')
  if (!lastUser) return
  provider.value = p
  sendMessage(lastUser.content)
}

/* 「智能对话」导航：pickedAgent 恒有选中态（初始学习助手），直接进对话页；
   已有进行中的会话则带会话 id（从其他视图切回时恢复当前会话） */
function onNav(v) {
  setView(v, v === 'chat' && activeId.value != null ? activeId.value : undefined)
}

/* 顶部胶囊条切换智能体：换人即开新会话（旧会话留在左栏历史）；
   重复点当前空会话的选中项不动作 */
function pickAgent(key) {
  if (key === pickedAgent.value && !activeId.value && messages.value.length === 0) return
  abortStream()
  activeId.value = null
  messages.value = []
  pickedAgent.value = key
  rememberAgent(key)
  setView('chat')  // 走 hash 同步，防与视图脱钩
}

// 引用角标点击（里程碑 7）：切到知识库页并打开原文高亮弹层
function jumpCitation(c) {
  if (!c || c.doc_id == null) {
    ElMessage.info('该引用未关联知识库文档')
    return
  }
  citationJump.value = { docId: c.doc_id, snippet: c.snippet || '' }
  setView('knowledge')
}

// 对话规划一键转计划（任务计划中心）：任务 objective 变为步骤清单
async function makePlan(msg) {
  const tasks = msg?.plan?.tasks || []
  if (!tasks.length) return
  try {
    await createPlan({
      title: msg.reason || (tasks.length > 1 ? '多线规划' : tasks[0]?.label || '来自对话的规划'),
      items: tasks.map(t => ({ content: `${t.label || ''}${t.objective ? '：' + t.objective : ''}`.trim() })),
      source_message_id: msg.id
    })
    ElMessage.success('已转入任务计划中心，可勾选推进')
    setView('plans')
  } catch (e) {
    ElMessage.error(e?.message || '转入失败')
  }
}

/* 登录后才拉取的基础数据：会话列表 / 知识库文档 / 记忆条数。
   未登录一律不发——曾因 onMounted 无条件请求导致「401→reload→401」刷屏死循环 */
function loadUserData() {
  if (!user.value) return
  loadConversations()
  getKbDocuments().then(d => { kbDocs.value = d || [] }).catch(() => {})
  getMemories().then(m => { memCount.value = (m || []).length }).catch(() => {})
}

onMounted(() => {
  window.addEventListener('hashchange', onHashChange)
  loadUserData()
  // 已登录会话补拉本人资料：让旧 localStorage 账号也能拿到新字段（如头像）
  if (user.value) {
    getMe().then(u => {
      user.value = { ...user.value, ...u }
      localStorage.setItem('ark_user', JSON.stringify(user.value))
    }).catch(() => {})
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('hashchange', onHashChange)
})
</script>

<template>
  <!-- 滚动式落地页：展示平台服务与功能，点击按钮进入主界面 -->
  <LandingView v-if="!entered" :user="user" @enter="enterApp" @logout="logout" @switch="switchAccount" />
  <div v-else class="app-shell">
    <!-- 顶部横向导航（DiceBear Playground 风格）：5 工作面 + 用户下拉卡 -->
    <TopNav :view="view" :user="user" @switch="onNav" @open-account="setView('account')" @logout="logout" @home="goHome" />
    <div class="app-body">
      <!-- 智能对话双栏：左配置面板 + 右舞台（顶部胶囊条常驻选智能体） -->
      <template v-if="view === 'chat'">
        <ChatConfig
          :conversations="conversations"
          :active-id="activeId"
          @select="selectConversation"
          @delete="removeConversation"
          @new-chat="newChat"
          @navigate="setView"
        />
        <ChatView
          :agent="pickedAgent"
          :messages="messages"
          :streaming="streaming"
          :session-title="activeTitle"
          :user="user"
          :models="MODELS"
          :kb-docs="kbDocs"
          :mem-count="memCount"
          :draft-seed="pendingQuestion"
          v-model:provider="provider"
          v-model:use-kb="useKb"
          v-model:use-memory="useMemory"
          v-model:kb-doc-ids="kbDocIds"
          @send="sendMessage"
          @stop="abortStream"
          @regenerate="sendMessage"
          @retry-with="retryWith"
          @new-chat="newChat"
          @jump-citation="jumpCitation"
          @make-plan="makePlan"
          @pick-agent="pickAgent"
          @seed-consumed="pendingQuestion = ''"
        />
      </template>
      <!-- 其余视图：顶栏下全宽 -->
      <main v-else class="main">
        <KnowledgeView
          v-if="view === 'knowledge'"
          :meta="viewMeta"
          :citation-jump="citationJump"
          @ask="(t) => { pendingQuestion = t; setView('chat') }"
        />
        <PlansView v-else-if="view === 'plans'" :meta="viewMeta" />
        <InsightsView v-else-if="view === 'insights'" :meta="viewMeta" />
        <ModelSquare v-else-if="view === 'models'" :meta="viewMeta" @navigate="setView" />
        <AccountView
          v-else-if="view === 'account'"
          :meta="viewMeta"
          :user="user"
          :tab="accountTab"
          @tab="setAccountTab"
          @navigate="setView"
          @logout="logout"
          @avatar-updated="onAvatarUpdated"
        />
      </main>
    </div>
  </div>
  <!-- 登录 / 注册弹窗：未登录点击任何进入平台的入口时弹出 -->
  <AuthModal v-if="showAuth" @close="showAuth = false" @success="authSuccess" />
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
}
.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>
