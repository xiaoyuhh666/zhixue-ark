<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  streaming: { type: Boolean, default: false },
  sessionTitle: { type: String, default: '' },
  models: { type: Array, default: () => [] },
  // 「智能对话」两段式：选定的智能体 key（study/competition/.../collab），未知值回落调度欢迎
  agent: { type: String, default: '' },
  // 知识库文档列表 [{id, title|filename}]（左下角 KB 菜单展示与勾选）
  kbDocs: { type: Array, default: () => [] },
  // 知识库检索试验台「去对话页追问」：预填到输入框的问题文本
  draftSeed: { type: String, default: '' },
  // 长期记忆条数（左下角记忆开关胶囊展示）
  memCount: { type: Number, default: 0 },
  // 登录账号（用户消息头像展示自定义图片/昵称首字，替代硬编码首字）
  user: { type: Object, default: null }
})

// provider / useKb / kbDocIds / useMemory 双向绑定（工具栏左侧知识库+记忆，右侧模型+发送）
const provider = defineModel('provider', { type: String, default: 'deepseek' })
const useKb = defineModel('useKb', { type: Boolean, default: true })
const kbDocIds = defineModel('kbDocIds', { type: Array, default: null }) // null=全部
const useMemory = defineModel('useMemory', { type: Boolean, default: true })

const emit = defineEmits(['send', 'new-chat', 'jump-citation', 'make-plan', 'pick-agent', 'seed-consumed', 'stop', 'regenerate', 'retry-with'])

/* 用户消息头像：自定义图片 > 昵称首字 > 「我」 */
const userInitial = computed(
  () => (props.user?.nickname || props.user?.username || '我')[0] || '我'
)

const draft = ref('')
const scrollEl = ref(null)
const inputEl = ref(null)

/* 模型选择弹出菜单（输入框右下角胶囊，向上展开） */
const menuOpen = ref(false)
const modelSel = ref(null)
const currentLabel = computed(
  () => (props.models.find(m => m.value === provider.value) || {}).label || provider.value
)

function selectModel(v) {
  provider.value = v
  menuOpen.value = false
}

/* 顶部智能体胶囊条（2026-09-20 甲方案：胶囊条替代选择页）——常驻可切换 */
const AGENTS = [
  { key: 'study', label: '学习助手', icon: '📚' },
  { key: 'competition', label: '竞赛指导', icon: '🏆' },
  { key: 'research', label: '科研助手', icon: '🔬' },
  { key: 'career', label: '求职指导', icon: '💼' },
  { key: 'life', label: '生活服务', icon: '🏫' }
]

/* 快捷示例（自 ChatConfig 迁入）：作为调度智能体默认欢迎的 chips */
const PRESETS = [
  { text: '生成《数据结构》复习计划' },
  { text: '竞赛+考试双线安排（多智能体协作）', highlight: true },
  { text: '这道二叉树题帮我讲讲' }
]

/* 专属欢迎页（智能对话两段式）：每个智能体的欢迎语与示例问题；collab 为协作场景 */
const AGENT_WELCOME = {
  study: {
    tag: '学习助手', router: false,
    text: '课程复习、知识点答疑、学习方法规划是你的主场；遇到跨领域需求，我会请其他智能体协作。',
    chips: ['帮我制定数据结构期末两周复习计划', '这道二叉树题帮我讲讲', '我的专业方向该怎么规划？']
  },
  competition: {
    tag: '竞赛指导', router: false,
    text: '赛程规划、备赛策略、团队分工与作品打磨，我来帮你把比赛节奏理清楚。',
    chips: ['大三下学期参加数学建模国赛，现在该怎么准备？', '蓝桥杯和 ACM 该怎么选？', '竞赛获奖对保研有多大帮助？']
  },
  research: {
    tag: '科研助手', router: false,
    text: '从选题、文献综述到研究方法，陪你走完本科科研的第一步。',
    chips: ['本科生怎么开始做第一个科研项目？', '帮我梳理论文选题方向', '文献综述该怎么写？']
  },
  career: {
    tag: '求职指导', router: false,
    text: '简历打磨、实习选择、秋招节奏，帮你把求职这条路走稳。',
    chips: ['Java 后端实习简历应该怎么写？', '大三暑期实习和秋招怎么平衡？', '面试自我介绍怎么准备？']
  },
  life: {
    tag: '生活服务', router: false,
    text: '作息调节、压力疏解、校园生活琐事，都可以放心交给我。',
    chips: ['期末周压力很大，怎么调节作息？', '社团和学习时间冲突了怎么办？', '怎样快速适应大学生活？']
  },
  collab: {
    tag: '多智能体协作', router: true,
    text: '这是调度智能体主导的协作场景：复合任务自动拆解给多位领域智能体，顺序执行、汇总整合。',
    chips: ['竞赛+考试双线安排（多智能体协作）', '我下周既要备战数学建模国赛，又要复习数据结构期末考，帮我做一份双线规划']
  }
}
const welcome = computed(() => AGENT_WELCOME[props.agent] || {
  tag: '调度智能体', router: true,
  text: '会自动识别你的需求并调度合适的领域智能体来回答。你可以直接提问，也可以试试下方的快捷示例。',
  chips: PRESETS.map(p => p.text)
})

/* 知识库菜单（输入框左下角胶囊，向上展开）：检索开关 + 按文档勾选检索范围 */
const kbOpen = ref(false)
const kbSel = ref(null)

/* 勾选集合：null=全部；基于有效集合做 toggle，全选回 null 态 */
const allDocIds = computed(() => props.kbDocs.map(d => d.id))
function isDocSelected(id) {
  return !Array.isArray(kbDocIds.value) || kbDocIds.value.includes(id)
}
function toggleDoc(id) {
  const base = Array.isArray(kbDocIds.value) ? [...kbDocIds.value] : [...allDocIds.value]
  const i = base.indexOf(id)
  i >= 0 ? base.splice(i, 1) : base.push(id)
  kbDocIds.value = base.length === allDocIds.value ? null : base
}
function selectAllDocs() {
  kbDocIds.value = null
}
/* 胶囊摘要文案：篇数 or 已选比例 */
const kbSummary = computed(() => {
  const total = props.kbDocs.length
  if (!Array.isArray(kbDocIds.value)) return `${total} 篇`
  return `已选 ${kbDocIds.value.length}/${total}`
})

function onDocClick(e) {
  if (menuOpen.value && modelSel.value && !modelSel.value.contains(e.target)) menuOpen.value = false
  if (kbOpen.value && kbSel.value && !kbSel.value.contains(e.target)) kbOpen.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

/* 导出当前对话为 Markdown 文件（前端 Blob 下载，含智能体署名与分段全文） */
function exportMd() {
  const lines = props.messages.map(m =>
    m.role === 'user'
      ? `## 我\n\n${m.content}`
      : `## ${m.agent || '智学方舟'}\n\n${m.content}`
  )
  const md = `# ${props.sessionTitle || '智学方舟对话'}\n\n${lines.join('\n\n---\n\n')}`
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(blob),
    download: `${(props.sessionTitle || '智学方舟对话').slice(0, 30)}.md`
  })
  a.click()
  URL.revokeObjectURL(a.href)
}

const canSend = computed(() => !props.streaming && draft.value.trim().length > 0)

/* ===== 消息操作条（复制 / 重新生成 / 点赞点踩，仅助手消息非流式中展示） ===== */

/* 复制回答全文到剪贴板 */
async function copyMsg(m) {
  try {
    await navigator.clipboard.writeText(m.content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择文本复制')
  }
}

/* 重新生成：把该回答对应的用户问题作为新一轮重新发送 */
function regenMsg(m) {
  if (props.streaming) return
  const i = props.messages.indexOf(m)
  for (let j = i - 1; j >= 0; j--) {
    if (props.messages[j].role === 'user') {
      emit('regenerate', props.messages[j].content)
      return
    }
  }
}

/* 点赞点踩：按 message_id 存 localStorage，刷新/回放后仍保留 */
const fbMap = ref(readFb())
function readFb() {
  try { return JSON.parse(localStorage.getItem('ark_feedback') || '{}') } catch { return {} }
}
function fbOf(m) { return m.id ? (fbMap.value[m.id] || null) : null }
function setFb(m, v) {
  if (!m.id) { ElMessage.info('该消息未保存到会话，暂不能评价'); return }
  /* 再次点击同一评价 = 取消；切换评价 = 直接覆盖 */
  fbMap.value[m.id] = fbMap.value[m.id] === v ? null : v
  localStorage.setItem('ark_feedback', JSON.stringify(fbMap.value))
}

function doSend(text) {
  const t = (text ?? draft.value).trim()
  if (!t || props.streaming) return
  emit('send', t)
  draft.value = ''
  nextTick(resize)
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    if (e.isComposing) return // 中文输入法选词回车不发送
    e.preventDefault()
    doSend()
  }
}

function resize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function scrollToBottom() {
  const el = scrollEl.value
  if (el) el.scrollTop = el.scrollHeight
}

/* 消息数量或末条消息内容变化时自动滚动到底部（流式逐字追加） */
watch(
  () => {
    const last = props.messages[props.messages.length - 1]
    return `${props.messages.length}:${last ? last.content.length : 0}`
  },
  () => nextTick(scrollToBottom)
)

/* 知识库试验台跳转预填：seed 非空时填入输入框并聚焦，随后通知父组件清空 */
watch(
  () => props.draftSeed,
  (v) => {
    if (v) {
      draft.value = v
      emit('seed-consumed')
      nextTick(() => inputEl.value && inputEl.value.focus())
    }
  },
  { immediate: true }
)
</script>

<template>
  <section class="chat-view">
    <!-- 舞台操作条：会话标题 + 流式状态 + 新建/导出 -->
    <div class="stage-bar">
      <div class="stage-left">
        <span class="stage-dot" :class="{ live: streaming }"></span>
        <span class="stage-title">{{ sessionTitle || '新会话' }}</span>
        <span class="stage-status">{{ streaming ? 'STREAMING…' : 'READY' }}</span>
      </div>
      <div class="stage-actions">
        <button class="btn-ghost" @click="exportMd">导出对话</button>
      </div>
    </div>

    <!-- 顶部智能体胶囊条（甲方案）：常驻选择器，点谁切谁的欢迎页；历史回放时无高亮 -->
    <div class="agent-bar">
      <span class="agent-bar-label">智能体 1/5：</span>
      <button
        v-for="a in AGENTS"
        :key="a.key"
        class="agent-pill"
        :class="{ active: agent === a.key }"
        :disabled="streaming"
        @click="emit('pick-agent', a.key)"
      ><span class="ic">{{ a.icon }}</span>{{ a.label }}</button>
      <button
        class="agent-pill collab"
        :class="{ active: agent === 'collab' }"
        :disabled="streaming"
        @click="emit('pick-agent', 'collab')"
      ><span class="ic">✦</span>多智能体协作</button>
    </div>

    <div ref="scrollEl" class="chat-scroll">
      <div class="chat-wrap">
        <!-- 空状态专属欢迎页：按选定智能体展示欢迎语与示例问题 -->
        <div v-if="messages.length === 0" class="msg">
          <div class="msg-avatar avatar-ai">智</div>
          <div class="msg-body">
            <div class="msg-meta">ZHIXUE ARK <span class="msg-agent-tag" :class="{ router: welcome.router }">{{ welcome.tag }}</span></div>
            <div class="bubble">
              <p>你好，我是<b>{{ welcome.tag }}</b>。</p>
              <p>{{ welcome.text }}</p>
            </div>
            <!-- 示例问题：点击直接发送 -->
            <div class="welcome-chips">
              <button
                v-for="(q, qi) in welcome.chips"
                :key="qi"
                class="welcome-chip"
                :disabled="streaming"
                @click="doSend(q)"
              >{{ q }}</button>
            </div>
          </div>
        </div>

        <!-- 消息流 -->
        <div
          v-for="(m, i) in messages"
          :key="m.id ?? `${i}-${m.created_at}`"
          class="msg"
          :class="{ user: m.role === 'user' }"
        >
          <div class="msg-avatar" :class="m.role === 'user' ? 'avatar-user' : 'avatar-ai'">
            <img v-if="m.role === 'user' && user?.avatar" :src="user.avatar" alt="头像" />
            <template v-else>{{ m.role === 'user' ? userInitial : '智' }}</template>
          </div>
          <div class="msg-body">
            <div class="msg-meta">
              <template v-if="m.role === 'user'">YOU</template>
              <template v-else>
                ZHIXUE ARK
                <span class="msg-agent-tag">{{ m.agent || '智学方舟' }}</span>
                <span v-if="m.reason" class="msg-agent-tag router">{{ m.reason }}</span>
                <span v-if="m.model" class="msg-model">{{ m.model }}</span>
              </template>
            </div>
            <!-- 多智能体协作流水线（里程碑 5）：随 SSE 帧推进 -->
            <div v-if="m.role !== 'user' && m.steps && m.steps.length" class="pipe-row">
              <template v-for="(s, si) in m.steps" :key="s.key">
                <span v-if="si > 0" class="pipe-arrow">→</span>
                <span class="pipe-step" :class="s.status"><i class="pipe-dot"></i>{{ s.label }}</span>
              </template>
            </div>
            <!-- 限流错误卡：替代普通气泡，一键换模型重试（免费档高峰 429 救场） -->
            <div v-if="m.role !== 'user' && m.error_kind === 'rate_limit'" class="err-card">
              <div class="err-kicker">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                MODEL RATE LIMITED
              </div>
              <div class="err-title">当前模型限流，回复未能生成</div>
              <div class="err-text">{{ m.content }}</div>
              <div class="err-actions">
                <button class="err-retry" @click="emit('retry-with', 'deepseek')">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                  切换 DeepSeek 重试
                </button>
                <button class="err-retry alt" @click="emit('retry-with', 'qwen')">换千问重试</button>
              </div>
            </div>
            <div v-else class="bubble">
              <!-- 里程碑 6：多智能体协作时按任务分段渲染 -->
              <template v-if="m.role !== 'user' && m.segments && m.segments.length">
                <div v-for="(seg, si) in m.segments" :key="si" class="seg">
                  <span v-if="m.segments.length > 1" class="seg-tag">{{ seg.label || seg.agent }}</span>
                  <div class="seg-text">{{ seg.content }}<span v-if="m.streaming && si === m.segments.length - 1" class="caret"></span></div>
                </div>
              </template>
              <template v-else>{{ m.content }}<span v-if="m.streaming" class="caret"></span></template>
            </div>
            <!-- 消息操作条：复制 / 重新生成 / 点赞点踩（仅助手消息、非流式中） -->
            <div v-if="m.role !== 'user' && !m.streaming && m.content" class="msg-ops">
              <button class="op-btn" title="复制回答全文" @click="copyMsg(m)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                复制
              </button>
              <button class="op-btn" title="把原问题重新发送一轮" :disabled="streaming" @click="regenMsg(m)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                重新生成
              </button>
              <span class="op-sep"></span>
              <button class="op-btn fb" :class="{ on: fbOf(m) === 'up' }" title="回答有帮助" @click="setFb(m, 'up')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
              </button>
              <button class="op-btn fb" :class="{ on: fbOf(m) === 'down' }" title="回答不满意" @click="setFb(m, 'down')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
              </button>
            </div>
            <!-- 任务规划转计划（任务计划中心）：有任务规划且非流式中可一键转入 -->
            <div
              v-if="m.role !== 'user' && !m.streaming && m.plan && m.plan.tasks && m.plan.tasks.length"
              class="plan-actions"
            >
              <button class="make-plan-btn" :disabled="streaming" @click="emit('make-plan', m)">
                ✦ 转为我的计划
              </button>
              <span class="plan-actions-hint">把这份规划存入「任务计划中心」，可勾选推进</span>
            </div>
            <!-- 澄清追问快捷应答（里程碑 7）：点击 chip 直接作为用户消息发出 -->
            <div v-if="m.role !== 'user' && m.clarify && m.clarify.questions.length" class="clarify-chips">
              <button
                v-for="(q, qi) in m.clarify.questions"
                :key="qi"
                class="clarify-chip"
                :disabled="streaming"
                @click="emit('send', q)"
              >{{ q }}</button>
            </div>
            <!-- RAG 引用溯源（里程碑 4）：点击角标跳知识库原文高亮（里程碑 7） -->
            <div v-if="m.role !== 'user' && m.citations && m.citations.length" class="cite-row">
              <span class="cite-label">参考来源</span>
              <span
                v-for="(c, ci) in m.citations"
                :key="ci"
                class="cite"
                :data-tip="`${c.doc} · 相似度 ${(c.score * 100).toFixed(0)}%\n${c.snippet}`"
                title="点击查看原文"
                @click="emit('jump-citation', c)"
              >[{{ ci + 1 }}] {{ c.doc }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="chat-input-area">
      <div class="chat-input-box">
        <div class="input-row">
          <textarea
            ref="inputEl"
            v-model="draft"
            rows="1"
            placeholder="向智能体提问，复杂任务将自动拆解并调度多个智能体协作…"
            @keydown="onKeydown"
            @input="resize"
          ></textarea>
          <div class="composer-foot">
            <!-- 工具栏左侧：知识库开关（点击直接切换）+ 记忆开关，并排一行 -->
            <div ref="kbSel" class="model-select foot-left">
              <button
                class="tool-item kb-toggle"
                :class="{ on: useKb, open: kbOpen }"
                :disabled="streaming"
                title="回答是否参考知识库资料（点击箭头可选检索范围）"
                @click="useKb = !useKb"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                知识库
                <span class="kb-cnt">{{ kbSummary }}</span>
                <span class="kb-state">{{ useKb ? '检索开' : '检索关' }}</span>
                <span class="kb-chev" title="选择检索哪些资料" @click.stop="kbOpen = !kbOpen">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
                </span>
              </button>
              <!-- 长期记忆运用开关：点击直接切换，关闭后回答不注入画像与记忆 -->
              <button
                class="tool-item kb-toggle"
                :class="{ on: useMemory }"
                :disabled="streaming"
                title="关闭后回答不参考你的画像与长期记忆（隐私模式）"
                @click="useMemory = !useMemory"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
                记忆
                <span class="kb-cnt">{{ memCount }} 条</span>
                <span class="kb-state">{{ useMemory ? '运用开' : '运用关' }}</span>
              </button>
              <div v-if="kbOpen" class="model-menu kb-menu">
                <!-- 检索开关行 -->
                <button class="kb-menu-row" @click="useKb = !useKb">
                  <span class="kbr-name">知识库检索</span>
                  <span class="kbr-state">{{ useKb ? '已开启' : '已关闭' }}</span>
                  <span class="kbr-dot" :class="{ on: useKb }"></span>
                </button>
                <!-- 文档多选列表：勾选后只检索选中资料 -->
                <div class="kb-docs">
                  <label
                    v-for="d in kbDocs"
                    :key="d.id"
                    class="kb-doc"
                    :class="{ disabled: !useKb }"
                  >
                    <input
                      type="checkbox"
                      :checked="isDocSelected(d.id)"
                      :disabled="!useKb"
                      @change="toggleDoc(d.id)"
                    />
                    <span class="doc-name">{{ d.title || d.filename }}</span>
                  </label>
                  <div v-if="!kbDocs.length" class="kb-empty">
                    还没有资料，去「02 知识库」上传后即可在对话中引用
                  </div>
                </div>
                <!-- 底部：全选 + 说明 -->
                <div class="kb-menu-foot">
                  <button class="kb-mini" :disabled="!useKb" @click="selectAllDocs">全选</button>
                  <span class="kb-note">未勾选任何文档时检索全部资料</span>
                </div>
              </div>
            </div>
            <!-- 工具栏右侧：模型选择（文字+箭头）+ 发送按钮 -->
            <div class="foot-right">
              <div ref="modelSel" class="model-select">
                <button class="tool-item model-pill" :class="{ open: menuOpen }" @click="menuOpen = !menuOpen">
                  {{ currentLabel }}
                  <svg class="chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
                </button>
                <div v-if="menuOpen" class="model-menu">
                  <div
                    v-for="m in models"
                    :key="m.value"
                    class="model-item"
                    :class="{ active: provider === m.value }"
                    @click="selectModel(m.value)"
                  >
                    <span class="mi-name">{{ m.name }}</span>
                    <span class="mi-en">{{ m.label }}</span>
                    <span class="mi-dot"></span>
                  </div>
                </div>
              </div>
              <!-- 流式中变「停止生成」：点击中断 SSE，已生成部分保留 -->
              <button v-if="streaming" class="btn-send stop" title="停止生成" @click="emit('stop')">
                <svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>
              </button>
              <button v-else class="btn-send" :disabled="!canSend" @click="doSend()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.chat-view { flex: 1; display: flex; flex-direction: column; min-height: 0; min-width: 0; }

/* 舞台操作条（DiceBear 式右上操作组） */
.stage-bar {
  height: 58px; flex-shrink: 0;
  display: flex; align-items: center; gap: 16px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: var(--bg);
}
.stage-left { display: flex; align-items: center; gap: 11px; min-width: 0; }
.stage-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  background: var(--pink); transition: all .2s;
}
.stage-dot.live { background: var(--accent); animation: pulse 1.4s infinite; }
.stage-title {
  font-size: 14px; font-weight: 700; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.stage-status {
  font-family: var(--mono); font-size: 10px; color: var(--dim);
  letter-spacing: .16em; flex-shrink: 0;
}
.stage-actions { margin-left: auto; display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.btn-ghost {
  padding: 9px 18px; border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--bg); color: var(--muted);
  font-family: var(--mono); font-size: 12px; letter-spacing: .06em;
  cursor: pointer; transition: all .15s;
}
.btn-ghost:hover { border-color: var(--pink); color: var(--accent); background: var(--pink-soft); }
.btn-pill {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 18px; border: none; border-radius: var(--r-full);
  background: var(--text); color: #fff;
  font-family: var(--mono); font-size: 12px; letter-spacing: .06em;
  cursor: pointer; transition: all .18s;
}
.btn-pill:hover { background: var(--accent); }
/* 窄屏：隐藏状态字样并收紧按钮，保标题可见 */
@media (max-width: 1100px) {
  .stage-bar { padding: 0 16px; }
  .stage-status { display: none; }
  .btn-ghost, .btn-pill { padding: 8px 13px; }
  .chat-input-area { padding: 8px 16px 14px; }
  .agent-bar { padding: 8px 14px; gap: 6px; }
  .agent-pill { padding: 5px 10px; font-size: 11px; }
}

.chat-scroll { flex: 1; overflow-y: auto; min-height: 0; }
.chat-wrap { max-width: 880px; width: 100%; margin: 0 auto; padding: 36px 32px 12px; }

.msg { display: flex; gap: 16px; margin-bottom: 30px; animation: fadeUp .4s ease both; }
.msg-avatar {
  width: 32px; height: 32px; flex-shrink: 0; margin-top: 2px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 11px; font-weight: 700;
  background: var(--surface); color: var(--muted);
  border-radius: var(--r-sm);
}
.avatar-ai { background: var(--pink-soft); color: var(--accent); }
.avatar-user { background: var(--pink); color: #141416; border-radius: var(--r-full); }
.msg-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; display: block; }
.msg-body { max-width: 80%; min-width: 0; }
.msg-meta {
  font-family: var(--mono); font-size: 10.5px; color: var(--dim);
  letter-spacing: .14em; margin-bottom: 10px;
  display: flex; gap: 10px; align-items: center; text-transform: uppercase;
}
.msg-agent-tag {
  font-family: var(--mono); font-size: 10px; letter-spacing: .1em;
  padding: 3px 10px; border-radius: var(--r-full);
  background: var(--pink-soft); color: var(--accent);
}
.msg-agent-tag.router { background: var(--surface-2); color: var(--muted); }
.msg-model { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .08em; }
.msg.user { flex-direction: row-reverse; }
.msg.user .msg-body { display: flex; flex-direction: column; align-items: flex-end; }
.msg.user .bubble {
  background: var(--pink-soft); color: var(--text);
  padding: 13px 18px; font-weight: 600; line-height: 1.7;
  border-radius: 18px 18px 4px 18px;
}
.bubble { line-height: 1.85; white-space: pre-wrap; word-break: break-word; }
.msg:not(.user) .bubble { padding-left: 18px; border-left: 2px solid var(--pink-soft); }
.bubble p { margin-bottom: 11px; }
.bubble p:last-child { margin-bottom: 0; }
.bubble b { color: var(--text); font-weight: 800; }

/* 分段回答（里程碑 6）：每个智能体任务一段，带小标签 */
.seg { margin-bottom: 14px; }
.seg:last-child { margin-bottom: 0; }
.seg-tag {
  display: inline-block; font-family: var(--mono); font-size: 9.5px;
  letter-spacing: .1em; color: var(--accent); background: var(--pink-soft);
  border-radius: var(--r-full); padding: 1px 9px; margin-bottom: 6px;
}
.seg-text { white-space: pre-wrap; word-break: break-word; }

/* 任务规划转计划（任务计划中心） */
.plan-actions {
  display: flex; align-items: center; gap: 12px;
  margin-top: 10px; padding-left: 18px;
}
.make-plan-btn {
  padding: 7px 16px; border: 1px solid var(--pink); border-radius: var(--r-full);
  background: var(--pink-soft); color: var(--accent);
  font-size: 12px; font-weight: 700; cursor: pointer; transition: all .15s;
}
.make-plan-btn:hover:not(:disabled) { background: var(--pink); color: #141416; }
.make-plan-btn:disabled { opacity: .5; cursor: not-allowed; }
.plan-actions-hint { font-size: 10.5px; color: var(--dim); }

/* 澄清追问快捷应答（里程碑 7） */
.clarify-chips {
  display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
  margin-top: 10px; padding-left: 18px;
}
/* 空状态欢迎区快捷示例（自 ChatConfig QUICK START 迁入） */
.welcome-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; padding-left: 18px; }
.welcome-chip {
  padding: 8px 14px; text-align: left;
  font-size: 12.5px; cursor: pointer; transition: all .15s;
  background: var(--bg); border: 1px solid var(--line); color: var(--muted);
  border-radius: var(--r-full);
}
.welcome-chip:hover:not(:disabled) { border-color: var(--pink); color: var(--accent); background: var(--pink-soft); }
.welcome-chip.highlight { background: var(--pink-soft); border-color: var(--pink); color: var(--accent); }
.welcome-chip:disabled { opacity: .5; cursor: not-allowed; }
/* 顶部智能体胶囊条（甲方案）：舞台条之下常驻，历史回放时无高亮 */
.agent-bar {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
  padding: 9px 24px; border-bottom: 1px solid var(--line);
  background: var(--bg); overflow-x: auto; scrollbar-width: none;
}
.agent-bar::-webkit-scrollbar { display: none; }
.agent-bar-label {
  font-family: var(--mono); font-size: 9.5px; letter-spacing: .14em;
  color: var(--dim); white-space: nowrap; margin-right: 2px;
}
.agent-pill {
  display: flex; align-items: center; gap: 6px; white-space: nowrap;
  padding: 6px 13px; border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--bg); color: var(--muted); font-size: 12px;
  cursor: pointer; transition: all .15s; flex-shrink: 0;
}
.agent-pill .ic { font-size: 11px; }
.agent-pill:hover:not(:disabled), .agent-pill.active {
  border-color: var(--pink); color: var(--accent); background: var(--pink-soft);
}
.agent-pill.active { font-weight: 700; }
.agent-pill:disabled { opacity: .55; cursor: not-allowed; }
.agent-pill.collab { border-style: dashed; }
.clarify-chip {
  padding: 8px 14px; text-align: left;
  font-size: 12.5px; cursor: pointer; transition: all .15s;
  background: var(--bg); border: 1px solid var(--line); color: var(--muted);
  border-radius: var(--r-full);
}
.clarify-chip:hover:not(:disabled) { border-color: var(--pink); color: var(--accent); background: var(--pink-soft); }
.clarify-chip:disabled { opacity: .5; cursor: not-allowed; }

/* RAG 引用来源行（里程碑 4） */
.cite-row {
  display: flex; align-items: baseline; flex-wrap: wrap; gap: 8px;
  margin-top: 10px; padding-left: 18px;
}
.cite-label {
  font-family: var(--mono); font-size: 10px; color: var(--dim);
  letter-spacing: .12em; text-transform: uppercase; margin-right: 2px;
}
.cite {
  display: inline-block; max-width: 260px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
  font-family: var(--mono); font-size: 10.5px; font-weight: 700;
  color: var(--accent); background: var(--pink-soft);
  border-radius: var(--r-full); padding: 2px 9px;
  cursor: pointer; position: relative; line-height: 16px; transition: all .15s;
}
.cite:hover { background: var(--accent); color: #fff; }
.cite:hover::after {
  content: attr(data-tip);
  position: absolute; bottom: 26px; left: 0; transform: none;
  background: var(--text); color: #fff;
  font-family: var(--mono); font-size: 11px; font-weight: 400;
  padding: 9px 13px; border-radius: var(--r-sm);
  white-space: pre-line; width: 300px; z-index: 50;
  line-height: 1.5;
}
.caret {
  display: inline-block; width: 8px; height: 15px; background: var(--pink);
  vertical-align: -2px; animation: blink .8s step-end infinite; border-radius: 2px;
}

/* 多智能体协作流水线（里程碑 5） */
.pipe-row {
  display: flex; align-items: center; flex-wrap: wrap; gap: 7px;
  margin: -2px 0 12px; padding-left: 18px;
}
.pipe-step {
  display: inline-flex; align-items: center; gap: 7px;
  font-family: var(--mono); font-size: 10px; letter-spacing: .06em;
  padding: 3px 11px; border: 1px solid var(--line); border-radius: var(--r-full);
  color: var(--muted); background: var(--bg); transition: all .2s;
}
.pipe-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--dim); flex-shrink: 0; }
.pipe-step.active { border-color: var(--pink); color: var(--accent); background: var(--pink-soft); }
.pipe-step.active .pipe-dot { background: var(--accent); animation: pulse 1.4s infinite; }
.pipe-step.done { color: var(--muted); }
.pipe-step.done .pipe-dot { background: var(--pink); }
.pipe-step.pending { color: var(--dim); opacity: .75; }
.pipe-step.fail { border-color: #d8a0a0; color: #c25454; }
.pipe-step.fail .pipe-dot { background: #c25454; }
.pipe-arrow { font-family: var(--mono); font-size: 10px; color: var(--dim); }

/* 输入区（参考截图布局：一体卡片 = 上 textarea + 下工具栏，左知识库 / 右模型+发送） */
.chat-input-area { flex-shrink: 0; padding: 10px 32px 20px; background: var(--bg); }
.chat-input-box { max-width: 880px; margin: 0 auto; }
.input-row {
  display: flex; flex-direction: column; gap: 6px;
  background: var(--surface);
  border: 1.5px solid transparent; border-radius: var(--r-lg); padding: 13px 14px 9px 16px;
  transition: all .2s;
}
.input-row:focus-within { border-color: var(--pink); background: var(--bg); box-shadow: var(--shadow-hover); }
.input-row textarea {
  width: 100%; border: none; outline: none; resize: none; font-size: 14px;
  font-family: var(--sans); line-height: 1.6; max-height: 120px;
  background: transparent; color: var(--text);
}
.input-row textarea::placeholder { color: var(--dim); }
.composer-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  margin-top: 4px;
}
.foot-right { display: flex; align-items: center; gap: 10px; }
/* 左侧开关组：知识库 + 记忆并排一行 */
.foot-left { display: flex; align-items: center; gap: 4px; flex-wrap: nowrap; }
.foot-left .tool-item { flex-shrink: 0; white-space: nowrap; }
/* 知识库胶囊尾部箭头：点箭头才展开文档范围菜单 */
.kb-chev {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; margin-right: -4px; border-radius: 4px;
  opacity: .65; transition: transform .2s, opacity .15s, background .15s;
}
.kb-chev:hover { opacity: 1; background: rgba(0, 0, 0, .06); }
.tool-item.open .kb-chev { transform: rotate(180deg); opacity: 1; }

/* 工具栏按钮（知识库/模型）：无边框文字项，融入输入卡整体（参考截图工具栏） */
.tool-item {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 10px; border: none; border-radius: var(--r-sm);
  background: transparent; color: var(--muted);
  font-size: 12.5px; line-height: 1; cursor: pointer; transition: all .15s;
}
.tool-item:hover:not(:disabled), .tool-item.open { color: var(--accent); background: var(--pink-soft); }
.tool-item:disabled { opacity: .55; cursor: not-allowed; }
.tool-item svg { flex-shrink: 0; }
/* 知识库状态着色：检索开 = 粉（常亮），关 = 灰 */
.kb-toggle.on { color: var(--accent); background: var(--pink-soft); }
.kb-cnt { font-family: var(--mono); font-size: 10.5px; letter-spacing: .03em; opacity: .75; }
.kb-state { font-family: var(--mono); font-size: 10.5px; letter-spacing: .05em; opacity: .85; }
/* 弹出菜单定位与箭头旋转（向上弹出） */
.model-select { position: relative; flex-shrink: 0; }
.model-pill .chev { transition: transform .2s; }
.model-pill.open .chev { transform: rotate(180deg); }
.model-menu {
  position: absolute; bottom: calc(100% + 10px); right: 0; width: 256px;
  background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-md);
  box-shadow: var(--shadow-hover); overflow: hidden; z-index: 60;
  animation: fadeUp .2s ease both;
}
/* KB 菜单：开关行 + 文档多选 + 底部说明（左对齐弹出） */
.kb-menu { left: 0; right: auto; width: 288px; }
.kb-menu-row {
  width: 100%; display: flex; align-items: center; gap: 9px;
  padding: 12px 14px; border: none; background: transparent; cursor: pointer;
  border-bottom: 1px solid var(--line); transition: background .15s;
}
.kb-menu-row:hover { background: var(--pink-soft); }
.kbr-name { font-size: 12.5px; font-weight: 700; color: var(--text); }
.kb-menu-row:hover .kbr-name { color: var(--accent); }
.kbr-state { margin-left: auto; font-family: var(--mono); font-size: 10px; letter-spacing: .08em; color: var(--dim); }
.kbr-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--line); transition: background .15s; }
.kbr-dot.on { background: var(--accent); box-shadow: 0 0 0 3px var(--pink-soft); }
.kb-docs { max-height: 180px; overflow-y: auto; padding: 5px 6px; }
.kb-doc {
  display: flex; align-items: center; gap: 9px;
  padding: 8px 8px; border-radius: var(--r-sm); cursor: pointer;
  font-size: 12px; color: var(--text); transition: background .15s;
}
.kb-doc:hover { background: var(--pink-soft); }
.kb-doc input { accent-color: var(--accent); cursor: pointer; flex-shrink: 0; }
.kb-doc.disabled { opacity: .5; cursor: not-allowed; }
.doc-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kb-empty { padding: 14px 10px; font-size: 11.5px; color: var(--dim); line-height: 1.7; text-align: center; }
.kb-menu-foot {
  display: flex; align-items: center; gap: 9px;
  padding: 9px 14px 11px; border-top: 1px solid var(--line); background: var(--surface);
}
.kb-mini {
  padding: 4px 12px; border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--bg); color: var(--muted); font-family: var(--mono);
  font-size: 9.5px; letter-spacing: .08em; cursor: pointer; transition: all .15s;
}
.kb-mini:hover:not(:disabled) { border-color: var(--pink); color: var(--accent); }
.kb-mini:disabled { opacity: .5; cursor: not-allowed; }
.kb-note { font-size: 10.5px; color: var(--dim); }
.model-item {
  display: flex; align-items: center; gap: 9px;
  padding: 11px 14px; cursor: pointer; font-size: 13px;
  border-bottom: 1px solid var(--line); transition: background .15s;
}
.model-item:last-child { border-bottom: none; }
.model-item:hover { background: var(--surface); }
.model-item.active { background: var(--pink-soft); }
.mi-name { font-weight: 700; color: var(--text); }
.model-item.active .mi-name { color: var(--accent); }
.mi-en { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .08em; }
.mi-dot {
  margin-left: auto; width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0;
  border: 1.5px solid var(--line); transition: all .15s;
}
.model-item.active .mi-dot { border-color: var(--accent); background: var(--accent); }

.btn-send {
  width: 34px; height: 34px; border: none; border-radius: 10px;
  background: var(--text); color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: all .2s;
}
.btn-send:hover { background: var(--accent); }
.btn-send:disabled { opacity: .3; cursor: not-allowed; }
.btn-send svg { width: 16px; height: 16px; }
/* 流式中的停止键：白底粉描边方块，区别于发送键 */
.btn-send.stop {
  background: var(--bg); color: var(--accent);
  border: 1.5px solid var(--accent);
  animation: pulse 1.4s infinite;
}
.btn-send.stop:hover { background: var(--pink-soft); }

/* 消息操作条：复制 / 重新生成 / 点赞点踩 */
.msg-ops {
  display: flex; align-items: center; gap: 2px;
  margin-top: 10px; padding-left: 18px;
}
.op-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 9px; border: none; border-radius: var(--r-full);
  background: transparent; color: var(--dim);
  font-family: var(--mono); font-size: 10.5px; letter-spacing: .04em;
  cursor: pointer; transition: all .15s;
}
.op-btn svg { width: 12px; height: 12px; flex-shrink: 0; }
.op-btn:hover:not(:disabled) { color: var(--accent); background: var(--pink-soft); }
.op-btn:disabled { opacity: .4; cursor: not-allowed; }
.op-btn.fb { padding: 4px 7px; }
.op-btn.fb.on { color: var(--accent); background: var(--pink-soft); }
.op-sep { width: 1px; height: 12px; background: var(--line); margin: 0 5px; flex-shrink: 0; }

/* 限流错误卡：粉描边警示卡 + 一键换模型重试 */
.err-card {
  margin-left: 18px; max-width: 640px;
  border: 1px solid var(--pink); border-radius: var(--r-md);
  background: var(--pink-soft); padding: 14px 16px;
  animation: fadeUp .3s ease both;
}
.err-kicker {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 8.5px; letter-spacing: .16em; color: var(--accent);
}
.err-kicker svg { width: 11px; height: 11px; }
.err-title { font-size: 13.5px; font-weight: 700; margin-top: 6px; color: var(--text); }
.err-text { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.6; word-break: break-all; }
.err-actions { display: flex; gap: 8px; margin-top: 11px; }
.err-retry {
  display: inline-flex; align-items: center; gap: 6px;
  border: none; border-radius: var(--r-full); padding: 7px 14px;
  background: var(--text); color: #fff;
  font-size: 12px; font-weight: 600; cursor: pointer; transition: all .18s;
}
.err-retry:hover { background: var(--accent); box-shadow: 0 4px 14px var(--pink); }
.err-retry.alt { background: transparent; color: var(--text); border: 1px solid var(--line); }
.err-retry.alt:hover { background: #fff; color: var(--accent); border-color: var(--pink); box-shadow: none; }
.err-retry svg { width: 12px; height: 12px; }
</style>
