<script setup>
/* 落地页：DiceBear 官网结构（滚动叙事）+ Awwwards 编辑风大字排版
   白色柔粉基调沿用项目变量，黑色胶囊主按钮承接主界面入口 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import PlayChat from './PlayChat.vue'
import AbilityMarquee from './AbilityMarquee.vue'
import StepFlow from './StepFlow.vue'

const props = defineProps({
  user: { type: Object, default: null }  // 当前登录账号（null=未登录显示登录/注册按钮）
})

const emit = defineEmits(['enter', 'logout', 'switch'])

/* 锚点导航 */
const NAV = [
  { id: 'agents', num: '01', label: '智能体' },
  { id: 'features', num: '02', label: '能力' },
  { id: 'pipeline', num: '03', label: '流程' },
  { id: 'numbers', num: '04', label: '数据' }
]

/* 五位领域智能体卡片（5 列单排：一句话描述 + 2 标签） */
const AGENTS = [
  {
    num: 'A1', name: '学习助手', en: 'STUDY COPILOT',
    desc: '课程答疑与规划，资料随问随查。',
    tags: ['RAG 检索', '学习规划'],
    icon: 'book'
  },
  {
    num: 'A2', name: '竞赛指导', en: 'CONTEST COACH',
    desc: '备赛路线与分工，冲奖有章法。',
    tags: ['情报检索', '团队协作'],
    icon: 'trophy'
  },
  {
    num: 'A3', name: '科研助手', en: 'RESEARCH MATE',
    desc: '文献选题到写作，入门少弯路。',
    tags: ['文献梳理', '写作规范'],
    icon: 'flask'
  },
  {
    num: 'A4', name: '求职指导', en: 'CAREER PILOT',
    desc: '简历面试双打磨，精准出击。',
    tags: ['简历打磨', '面试模拟'],
    icon: 'briefcase'
  },
  {
    num: 'A5', name: '生活服务', en: 'CAMPUS LIFE',
    desc: '校园琐事一站管，生活更省心。',
    tags: ['日程管理', '贴心提醒'],
    icon: 'coffee'
  }
]

/* 01 区左侧要点：补充「一个入口」的价值说明，填满左列留白 */
const AGENT_POINTS = [
  { k: '统一入口', v: '一句话说出需求，调度智能体自动分派给对的人' },
  { k: '共享记忆', v: '五位专家共用同一份画像与长期记忆，不必反复自我介绍' },
  { k: '引用可查', v: '每条回答标注知识库出处与相似度，点开即可核对原文' }
]

/* 工作流程步骤 */
const STEPS = [
  { num: 'S1', title: '一句话提问', desc: '用自然语言说出你的需求，无需挑选智能体。' },
  { num: 'S2', title: '意图识别', desc: '调度智能体理解目标，判断涉及的领域。' },
  { num: 'S3', title: '任务拆解', desc: '生成有序任务列表，复杂问题拆成多步。' },
  { num: 'S4', title: '领域执行', desc: '智能体顺序执行任务，可调用知识检索与计算工具。' },
  { num: 'S5', title: '汇总整合', desc: '低温度整合多段产出，衔接去重，输出连贯回答。' },
  { num: 'S6', title: '引用溯源', desc: '回答附带知识库出处与相似度，点开即可核对原文。' }
]

/* 数据区（2026-09-20 换学生收益型文案）：大数字讲「你能得到什么」 */
const NUMBERS = [
  { digit: '1', suffix: '', label: '句话，五位专家分工办妥', sub: 'SCHEDULER · AUTO PLAN' },
  { digit: '0', suffix: '', label: '次重复自我介绍', sub: 'PERSONA + MEMORY SHARED' },
  { digit: '100', suffix: '%', label: '回答可溯源核对', sub: 'CITATION · CLICK TO VERIFY' },
  { digit: '3', suffix: '', label: '家大模型随你换', sub: 'DEEPSEEK · QWEN · GLM' }
]

/* Footer 多列栏目（DiceBear 官网式）：anchor=滚动锚点 / view=进主界面指定视图 / 无 go=纯文本 */
const FOOTER_COLS = [
  {
    title: '探索',
    items: [
      { label: '为什么选方舟', anchor: 'features' },
      { label: '五位智能体', anchor: 'agents' },
      { label: '工作流程', anchor: 'pipeline' },
      { label: '平台数据', anchor: 'numbers' }
    ]
  },
  {
    title: '平台入口',
    items: [
      { label: '智能对话', view: 'chat' },
      { label: '个人中心', view: 'account' },
      { label: '知识库', view: 'knowledge' },
      { label: '任务计划', view: 'plans' },
      { label: '学习足迹', view: 'insights' }
    ]
  },
  {
    title: '关于与支持',
    items: [
      { label: '帮助文档' },
      { label: '技术支持' },
      { label: '使用指南' },
      { label: '联系我们' }
    ]
  }
]

const landingEl = ref(null)
let io = null
let revealGuard = 0

/* Hero 漂浮卡：鼠标视差跟随（每张卡深度不同，产生前后层次） */
const heroEl = ref(null)
const mx = ref(0)
const my = ref(0)
const CARD_DEPTH = [26, 15, 32, 18, 24] // 每张卡的视差幅度(px)

function onHeroMove(e) {
  const el = heroEl.value
  if (!el) return
  const r = el.getBoundingClientRect()
  // 归一化到 -1 ~ 1（相对 hero 中心）
  mx.value = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width) * 2 - 1))
  my.value = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height) * 2 - 1))
}
function onHeroLeave() { mx.value = 0; my.value = 0 } // 离开后回弹归位
function cardShift(i) {
  /* 只返回纯位移值（模板 :style 的 key 已是 translate，带前缀会拼成非法值导致视差失效） */
  return `${(mx.value * CARD_DEPTH[i]).toFixed(1)}px ${(my.value * CARD_DEPTH[i]).toFixed(1)}px`
}

function enter() { emit('enter') }
/* footer 平台入口：进主界面并直达指定视图 */
function enterView(v) { emit('enter', v) }

/* 右上角用户区：登录后显示用户卡下拉（头像 + 昵称 + 退出/切换登录） */
const showUserMenu = ref(false)
const displayName = computed(() => props.user?.nickname || props.user?.username || '')
const avatarChar = computed(() => displayName.value[0] || '客')
function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}
function onDocClick(e) {
  if (!e.target.closest('.user-wrap')) showUserMenu.value = false
}
function goto(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}

/* ---------- 可玩性交互 ---------- */
/* 1) 光标跟随环：粉色 lag ring 慢半拍跟随，hover 可交互物时放大（仅精确指针设备） */
const ringEl = ref(null)
let ringRaf = 0
const ringPos = { x: window.innerWidth / 2, y: window.innerHeight / 2 }
const ringTarget = { x: ringPos.x, y: ringPos.y }
function onDocMove(e) { ringTarget.x = e.clientX; ringTarget.y = e.clientY }
function ringLoop() {
  ringPos.x += (ringTarget.x - ringPos.x) * 0.14
  ringPos.y += (ringTarget.y - ringPos.y) * 0.14
  if (ringEl.value) ringEl.value.style.translate = `${ringPos.x.toFixed(1)}px ${ringPos.y.toFixed(1)}px`
  ringRaf = requestAnimationFrame(ringLoop)
}
function onOver(e) {
  if (!ringEl.value) return
  const hit = e.target.closest('button, a, .float-card, .agent-card, .ab-card, .sf-row, .num-card')
  ringEl.value.classList.toggle('big', !!hit)
}

/* 2) 磁吸按钮：hover 时按钮轻微朝鼠标偏移，离开回弹 */
function magnetize() {
  document.querySelectorAll('.magnetic').forEach(el => {
    const onMove = (e) => {
      const r = el.getBoundingClientRect()
      const dx = (e.clientX - r.left - r.width / 2) * 0.22
      const dy = (e.clientY - r.top - r.height / 2) * 0.3
      el.style.translate = `${dx.toFixed(1)}px ${dy.toFixed(1)}px`
    }
    const onLeave = () => { el.style.translate = '0px 0px' }
    el.addEventListener('mousemove', onMove)
    el.addEventListener('mouseleave', onLeave)
  })
}

/* 3) 04 数据卡数字滚动（IO 进入视口触发） */
function countUp(el) {
  const target = parseFloat(el.dataset.count)
  const suffix = el.dataset.suffix || ''
  const t0 = performance.now()
  const dur = 1100
  const tick = (t) => {
    const p = Math.min(1, (t - t0) / dur)
    const eased = 1 - Math.pow(1 - p, 3)
    el.textContent = Math.round(target * eased) + suffix
    if (p < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

/* 滚动淡入 + 落地页滚动模式：挂载时放开 body 滚动，卸载时还原主界面锁滚 */
onMounted(() => {
  document.body.classList.add('landing-mode')
  // 用户下拉卡：点击卡片外任意处关闭
  document.addEventListener('click', onDocClick)
  io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('in')
        io.unobserve(e.target)
        // 数据卡进入视口时触发数字滚动
        e.target.querySelectorAll('.num-value[data-count]').forEach(el => {
          if (!el.dataset.done) { el.dataset.done = '1'; countUp(el) }
        })
      }
    })
  }, { threshold: 0.12 })
  landingEl.value.querySelectorAll('.reveal').forEach(el => io.observe(el))
  // 守护心跳：每 2s 把视口内仍未点亮的 .reveal 强制显示（IO 正常时此循环空转无副作用），
  // 防止个别元素被淡入机制卡在透明态形成空白块；被点亮的元素仍走正常 transition 淡入
  revealGuard = window.setInterval(() => {
    landingEl.value?.querySelectorAll('.reveal:not(.in)').forEach(el => {
      const r = el.getBoundingClientRect()
      if (r.top < window.innerHeight && r.bottom > 0) el.classList.add('in')
    })
  }, 2000)
  // 精确指针设备才启用光标环与磁吸（触屏跳过）
  if (window.matchMedia('(hover: hover)').matches) {
    document.addEventListener('mousemove', onDocMove)
    document.addEventListener('mouseover', onOver)
    ringLoop()
    magnetize()
  }
})
onBeforeUnmount(() => {
  document.body.classList.remove('landing-mode')
  document.removeEventListener('click', onDocClick)
  if (io) io.disconnect()
  clearInterval(revealGuard)
  cancelAnimationFrame(ringRaf)
  document.removeEventListener('mousemove', onDocMove)
  document.removeEventListener('mouseover', onOver)
})
</script>

<template>
  <div ref="landingEl" class="landing">
    <!-- 光标跟随环（仅精确指针设备可见） -->
    <span ref="ringEl" class="cursor-ring" aria-hidden="true"></span>
    <!-- 吸顶导航 -->
    <header class="land-nav">
      <div class="brand">
        <div class="brand-logo">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.7L20 10l-6.1 1.3L12 17l-1.9-5.7L4 10l6.1-1.3z"/></svg>
        </div>
        <div class="brand-text">
          <div class="brand-name">智学方舟®</div>
          <div class="brand-sub">CAMPUS MULTI-AGENT OS</div>
        </div>
      </div>
      <nav class="land-links">
        <button v-for="item in NAV" :key="item.id" class="land-link" @click="goto(item.id)">
          <span class="num">{{ item.num }}</span>{{ item.label }}
        </button>
      </nav>
      <!-- 未登录：登录 / 注册（点击弹 AuthModal）；已登录：用户名胶囊 + 下拉卡 -->
      <button v-if="!user" class="btn-dark magnetic" @click="enter">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.7L20 10l-6.1 1.3L12 17l-1.9-5.7L4 10l6.1-1.3z"/></svg>
        登录 / 注册
      </button>
      <div v-else class="user-wrap">
        <button class="user-chip" :class="{ open: showUserMenu }" @click="toggleUserMenu">
          <span class="uc-avatar">{{ avatarChar }}</span>
          <span class="uc-name">{{ displayName }}</span>
          <span class="uc-caret">^</span>
        </button>
        <transition name="um-pop">
          <div v-if="showUserMenu" class="user-menu">
            <div class="um-head">
              <span class="um-avatar">{{ avatarChar }}</span>
              <b class="um-name">{{ displayName }}</b>
            </div>
            <div class="um-actions">
              <button class="um-btn" @click="emit('logout')">退出登录</button>
              <button class="um-btn primary" @click="emit('switch')">切换登录</button>
            </div>
          </div>
        </transition>
      </div>
    </header>

    <!-- Hero：点阵背景 + 超大标题 + 漂浮智能体卡（鼠标视差跟随） -->
    <section ref="heroEl" class="hero" @mousemove="onHeroMove" @mouseleave="onHeroLeave">
      <div class="hero-glow"></div>
      <div class="hero-inner">
        <div class="hero-tip reveal">
          <span class="tip-dot"></span>
          <span class="mono">调度智能体在线 — 5 位领域专家 · 3 大模型热切换</span>
        </div>
        <h1 class="hero-title reveal">
          大学里的事 <br />
          交给一艘<span class="hollow">方舟</span>
        </h1>
        <p class="hero-sub reveal">
          智学方舟 · 校园多智能体平台。一位调度智能体听懂你的需求，
          五位领域专家替你办妥：<em>学习、竞赛、科研、求职、生活</em>。
        </p>
        <div class="hero-actions reveal">
          <button class="btn-dark btn-lg magnetic" @click="enter">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.7L20 10l-6.1 1.3L12 17l-1.9-5.7L4 10l6.1-1.3z"/></svg>
            进入智学方舟
          </button>
          <button class="btn-ghost btn-lg magnetic" @click="goto('agents')">
            先看看有什么功能
            <span class="arrow">↓</span>
          </button>
        </div>
        <div class="scroll-hint mono reveal">SCROLL ↓ 向下滚动，看看这艘方舟装了什么</div>
      </div>

      <!-- 右侧漂浮智能体卡（宽屏可见）：视差跟随 + hover 动效 -->
      <div class="hero-cards">
        <div
          v-for="(a, i) in AGENTS" :key="a.num"
          class="float-card"
          :style="{ top: (i * 18) + '%', left: ((i % 2) * 55) + '%', animationDelay: (i * 0.7) + 's', translate: cardShift(i) }"
        >
          <span class="fc-avatar">{{ a.name[0] }}</span>
          <span class="fc-name">{{ a.name }}</span>
          <span class="fc-status mono">READY</span>
        </div>
        <!-- 装饰星：填补卡片间空隙，随鼠标一起视差漂移 -->
        <span class="hero-spark s1" :style="`translate:${(mx * 20).toFixed(1)}px ${(my * 20).toFixed(1)}px`">✦</span>
        <span class="hero-spark s2" :style="`translate:${(mx * 12).toFixed(1)}px ${(my * 12).toFixed(1)}px`">✦</span>
        <span class="hero-spark s3" :style="`translate:${(mx * 16).toFixed(1)}px ${(my * 16).toFixed(1)}px`">＋</span>
      </div>
    </section>

    <!-- 01 五位智能体：左标题 + 右迷你试玩机，下方全宽卡片 -->
    <section id="agents" class="section">
      <div class="sec-duo">
        <div class="sec-head reveal">
          <span class="kicker mono">01 — AGENTS DIRECTORY</span>
          <h2 class="sec-title">五位专家 <br />一个入口 </h2>
          <p class="sec-desc">不用再开五个 ChatGPT 分身。所有领域智能体共享同一份画像与记忆，你只管提问。</p>
          <ul class="sec-points">
            <li v-for="p in AGENT_POINTS" :key="p.k" class="sec-point">
              <span class="sp-dot"></span>
              <span><b>{{ p.k }}</b> · {{ p.v }}</span>
            </li>
          </ul>
        </div>
        <div class="duo-right reveal">
          <PlayChat @enter="enter" />
        </div>
      </div>
      <div class="agent-grid">
        <article v-for="(a, i) in AGENTS" :key="a.num" class="agent-card reveal" :style="{ transitionDelay: (i * 70) + 'ms' }">
          <div class="ac-top">
            <span class="ac-icon">
              <!-- 书本 -->
              <svg v-if="a.icon === 'book'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
              <!-- 奖杯 -->
              <svg v-else-if="a.icon === 'trophy'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8M12 17v4M7 4h10v6a5 5 0 0 1-10 0V4z"/><path d="M7 6H4a2 2 0 0 0 2 4M17 6h3a2 2 0 0 1-2 4"/></svg>
              <!-- 烧瓶 -->
              <svg v-else-if="a.icon === 'flask'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v6L4.5 18a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 8V2"/><path d="M8.5 2h7M7 15h10"/></svg>
              <!-- 公文包 -->
              <svg v-else-if="a.icon === 'briefcase'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
              <!-- 咖啡杯 -->
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/></svg>
            </span>
            <span class="ac-num mono">{{ a.num }}</span>
          </div>
          <h3 class="ac-name">{{ a.name }}</h3>
          <div class="ac-en mono">{{ a.en }}</div>
          <p class="ac-desc">{{ a.desc }}</p>
          <div class="ac-tags">
            <span v-for="t in a.tags" :key="t" class="ac-tag mono">{{ t }}</span>
          </div>
        </article>
      </div>
    </section>

    <!-- 02 核心能力：居中标题 + 双排反向跑马灯画廊（纯展示） -->
    <section id="features" class="section section-tint">
      <div class="sec-head center reveal">
        <span class="kicker mono">02 — CAPABILITIES</span>
        <h2 class="sec-title">不是聊天机器人 <br />是一套调度系统 </h2>
        <p class="sec-desc">LangGraph 驱动的任务流水线 + 可溯源的检索增强生成，这是它在能力上的底气。</p>
      </div>
      <div class="reveal">
        <AbilityMarquee />
      </div>
    </section>

    <!-- 03 工作流程：全宽步骤流（依次点亮 + 行内产物可视化） -->
    <section id="pipeline" class="section">
      <div class="sec-head pipe-head reveal">
        <span class="kicker mono">03 — PIPELINE</span>
        <h2 class="sec-title">一次提问背后 <br />发生了什么 </h2>
        <p class="sec-desc">从一句「帮我规划考研和求职怎么平衡」到带引用的结构化回答，全程可视化。</p>
      </div>
      <StepFlow :steps="STEPS" />
    </section>

    <!-- 04 数据 -->
    <section id="numbers" class="section section-tint">
      <div class="sec-head reveal">
        <span class="kicker mono">04 — NUMBERS</span>
        <h2 class="sec-title">用数字说话 </h2>
      </div>
      <div class="num-grid">
        <div v-for="(n, i) in NUMBERS" :key="n.label" class="num-card reveal" :style="{ transitionDelay: (i * 70) + 'ms' }">
          <div class="num-value" :data-count="n.digit" :data-suffix="n.suffix">{{ n.digit + n.suffix }}</div>
          <div class="num-label">{{ n.label }}</div>
          <div class="num-sub mono">{{ n.sub }}</div>
        </div>
      </div>
    </section>

    <!-- Footer：DiceBear 官网式多列栏目 -->
    <footer class="foot">
      <div class="foot-main">
        <div class="foot-brand">
          <div class="brand">
            <div class="brand-logo">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.7L20 10l-6.1 1.3L12 17l-1.9-5.7L4 10l6.1-1.3z"/></svg>
            </div>
            <div class="brand-name">智学方舟®</div>
          </div>
          <p class="foot-desc">面向大学生的校园多智能体平台——五位领域专家，一位调度智能体，共享同一份画像与记忆。</p>
        </div>
        <div class="foot-cols">
          <div v-for="col in FOOTER_COLS" :key="col.title" class="foot-col">
            <div class="fcol-title">{{ col.title }}</div>
            <template v-for="item in col.items" :key="item.label">
              <button v-if="item.anchor" class="fitem" @click="goto(item.anchor)">{{ item.label }}</button>
              <button v-else-if="item.view" class="fitem" @click="enterView(item.view)">{{ item.label }}</button>
              <span v-else class="fitem plain">{{ item.label }}</span>
            </template>
          </div>
        </div>
      </div>
      <div class="foot-base mono">
        <span>© 2026 智学方舟 ZHIXUE ARK® — 毕业设计作品</span>
        <span>FASTAPI + LANGGRAPH + VUE3 · 5 AGENTS · 1 MEMORY · 0 GPU</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  /* window 原生滚动（body.landing-mode），容器自身不设内部滚动 */
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
}

/* ---------- 通用按钮（DiceBear 式胶囊） ---------- */
.btn-dark {
  display: inline-flex; align-items: center; gap: 9px;
  background: var(--text); color: #fff;
  border: 1.5px solid var(--text); border-radius: var(--r-full);
  padding: 10px 22px; font-size: 13.5px; font-weight: 700;
  cursor: pointer; transition: all .18s;
}
.btn-dark:hover { background: #000; transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.btn-ghost {
  display: inline-flex; align-items: center; gap: 9px;
  background: #fff; color: var(--text);
  border: 1.5px solid var(--line); border-radius: var(--r-full);
  padding: 10px 22px; font-size: 13.5px; font-weight: 700;
  cursor: pointer; transition: all .18s;
}
.btn-ghost:hover { border-color: var(--text); transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.btn-lg { padding: 15px 30px; font-size: 15px; }

/* ---------- 吸顶导航 ---------- */
.land-nav {
  position: sticky; top: 0; z-index: 50;
  display: flex; align-items: center; gap: 26px;
  padding: 0 clamp(20px, 4vw, 48px); height: 64px;
  background: rgba(255, 255, 255, .82);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 11px; flex-shrink: 0; }
.brand-logo {
  width: 34px; height: 34px; flex-shrink: 0;
  background: var(--pink); color: #141416;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-sm); box-shadow: var(--shadow);
}
.brand-name { font-size: 17px; font-weight: 800; letter-spacing: -.02em; }
.brand-sub { font-family: var(--mono); font-size: 9px; color: var(--dim); letter-spacing: .2em; margin-top: 2px; }
.land-links { display: flex; align-items: center; gap: 4px; margin-left: auto; }
.land-link {
  display: flex; align-items: center; gap: 7px;
  padding: 8px 15px; border: none; background: transparent;
  font-size: 13px; color: var(--muted); cursor: pointer;
  border-radius: var(--r-full); transition: all .15s;
}
.land-link .num { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; }
.land-link:hover { color: var(--text); background: var(--surface); }
.land-nav .btn-dark { margin-left: 18px; flex-shrink: 0; }

/* ---------- 右上角用户区（登录后）：用户名胶囊 + 下拉卡 ---------- */
.user-wrap { position: relative; margin-left: 18px; flex-shrink: 0; }
.user-chip {
  display: flex; align-items: center; gap: 9px;
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-full);
  padding: 5px 14px 5px 6px; cursor: pointer; transition: all .18s;
  box-shadow: var(--shadow);
}
.user-chip:hover, .user-chip.open { border-color: var(--pink); background: var(--pink-soft); }
.uc-avatar {
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--pink); color: #b4486e;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 800; flex-shrink: 0;
}
.uc-name { font-size: 13.5px; font-weight: 700; color: var(--text); max-width: 110px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uc-caret { font-size: 10px; color: var(--dim); transition: transform .18s; }
.user-chip.open .uc-caret { transform: rotate(180deg); }

.user-menu {
  position: absolute; right: 0; top: calc(100% + 10px);
  width: 240px; background: #fff;
  border: 1px solid var(--line); border-radius: 18px;
  box-shadow: 0 18px 44px rgba(20, 20, 22, .13);
  padding: 8px; z-index: 60;
}
.um-head {
  display: flex; align-items: center; gap: 13px;
  padding: 12px 14px;
}
.um-avatar {
  width: 44px; height: 44px; border-radius: 50%; flex-shrink: 0;
  background: var(--pink); color: #b4486e;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 800;
}
.um-name { font-size: 15px; font-weight: 800; color: var(--text); }

.um-actions {
  display: flex; gap: 8px;
  padding: 10px; border-top: 1px solid var(--line);
}
.um-btn {
  flex: 1; padding: 10px; cursor: pointer;
  border: 1px solid var(--line); border-radius: 12px;
  background: #fff; font-size: 12.5px; font-weight: 700; color: var(--muted);
  transition: all .15s;
}
.um-btn:hover { border-color: var(--pink); background: var(--pink-soft); color: var(--text); }
.um-btn.primary {
  background: var(--text); color: #fff; border-color: var(--text);
}
.um-btn.primary:hover { background: var(--accent); border-color: var(--accent); color: #fff; }

/* 下拉卡弹出过渡 */
.um-pop-enter-active, .um-pop-leave-active { transition: opacity .16s, transform .16s; }
.um-pop-enter-from, .um-pop-leave-to { opacity: 0; transform: translateY(-6px); }

/* ---------- Hero ---------- */
.hero {
  position: relative;
  min-height: calc(100vh - 64px);
  display: flex; align-items: center;
  padding: clamp(48px, 8vh, 96px) clamp(20px, 5vw, 64px);
  overflow: hidden;
  /* 点阵背景（DiceBear 式） */
  background-image: radial-gradient(var(--line) 1.1px, transparent 1.1px);
  background-size: 24px 24px;
}
.hero-glow {
  position: absolute; right: -12%; top: -18%;
  width: 46vw; height: 46vw; max-width: 640px; max-height: 640px;
  background: radial-gradient(circle, rgba(247, 168, 196, .34), transparent 62%);
  filter: blur(10px); pointer-events: none;
}
/* Hero 内容与下方区块同刻度：限宽 1200 居中，文字块靠容器左缘，
   卡片锚定容器右缘（见 .hero-cards），宽屏下中间不再空出一大块。
   容器盒子会盖住右侧卡片区，pointer-events:none 放行卡片 hover，
   交互元素（按钮）单独恢复事件 */
.hero-inner { position: relative; z-index: 2; width: min(1200px, 100%); margin-inline: auto; pointer-events: none; }
.hero-inner .btn-dark, .hero-inner .btn-ghost { pointer-events: auto; }
.hero-tip {
  display: inline-flex; align-items: center; gap: 9px;
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-full);
  padding: 8px 16px; font-size: 11px; color: var(--muted);
  box-shadow: var(--shadow); margin-bottom: 34px; letter-spacing: .08em;
}
.tip-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--pink); animation: pulse 1.4s infinite; }
.hero-title {
  font-size: clamp(46px, 8.2vw, 108px);
  font-weight: 800; line-height: 1.04; letter-spacing: -.04em;
  margin-bottom: 30px;
}
/* 「方舟」二字：黑色实心（原描边空心效果已按用户要求去除） */
.hollow { color: var(--text); }
.hero-sub {
  font-size: clamp(15px, 1.6vw, 18px); line-height: 1.75; color: var(--muted);
  max-width: 640px; margin-bottom: 40px;
}
.hero-sub em { font-style: normal; color: var(--accent); font-weight: 600; }
.hero-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 52px; }
.arrow { font-size: 14px; transition: transform .18s; }
.btn-ghost:hover .arrow { transform: translateY(3px); }
.scroll-hint { font-size: 10.5px; color: var(--dim); letter-spacing: .18em; }

/* 漂浮智能体卡（放大版）：floaty 用 transform 动画，视差用独立 translate 属性，hover 用独立 scale/rotate 属性，三者互不覆盖 */
/* 卡片贴 1200 容器右缘：宽屏 right=max(视口留白, 50%-588px)，窄屏回落到原 clamp */
.hero-cards { position: absolute; right: max(clamp(12px, 4vw, 64px), calc(50% - 588px)); top: 6%; width: 440px; height: 88%; z-index: 1; }
.float-card {
  position: absolute;
  display: flex; align-items: center; gap: 13px;
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-md);
  padding: 16px 22px; box-shadow: var(--shadow-hover);
  animation: floaty 5.2s ease-in-out infinite;
  /* 视差位移柔顺回弹；hover 缩放/旋转/描边同步过渡 */
  transition: translate .5s cubic-bezier(.22, 1, .36, 1), scale .25s ease, rotate .25s ease, box-shadow .25s ease, border-color .25s ease;
}
.float-card:hover {
  scale: 1.09; rotate: -2.5deg; z-index: 5;
  border-color: var(--pink);
  box-shadow: 0 18px 44px rgba(240, 130, 160, .24);
}
@keyframes floaty {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-11px); }
}
.fc-avatar {
  width: 46px; height: 46px; flex-shrink: 0;
  background: var(--pink-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-full); font-weight: 800; font-size: 17px;
  transition: scale .25s ease, rotate .25s ease;
}
.float-card:hover .fc-avatar { scale: 1.14; rotate: -10deg; background: var(--pink); color: #fff; }
.fc-name { font-size: 16px; font-weight: 700; white-space: nowrap; }
.fc-status { margin-left: 6px; font-size: 10px; color: var(--dim); letter-spacing: .14em; }

/* 卡片间隙装饰星：与卡片同频视差漂移，增强饱满度 */
.hero-spark { position: absolute; font-size: 18px; color: var(--pink); animation: floaty 6.5s ease-in-out infinite; transition: translate .5s cubic-bezier(.22,1,.36,1); }
.hero-cards { pointer-events: none; }
.hero-cards .float-card { pointer-events: auto; }
.s1 { top: 10%; left: 14%; color: var(--accent); opacity: .55; font-size: 22px; }
.s2 { top: 46%; right: -2%; opacity: .45; font-size: 15px; }
.s3 { bottom: 6%; left: 30%; opacity: .35; font-size: 16px; }

/* ---------- 通用区块 ---------- */
.section { padding: clamp(84px, 12vh, 140px) clamp(20px, 5vw, 64px); }
.section-tint { background: var(--surface); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.sec-head { max-width: 820px; margin-bottom: 60px; }
.kicker { display: inline-block; font-size: 11px; color: var(--accent); letter-spacing: .22em; margin-bottom: 20px; }
.sec-title {
  font-size: clamp(34px, 5.4vw, 64px);
  font-weight: 800; line-height: 1.08; letter-spacing: -.03em;
  margin-bottom: 22px;
}
.sec-desc { font-size: 15.5px; line-height: 1.8; color: var(--muted); max-width: 560px; }
/* 01 区左侧要点：补充价值说明，填满左列留白、与右侧演示框等高呼应 */
.sec-points { display: flex; flex-direction: column; gap: 15px; margin-top: 32px; }
.sec-point { display: flex; align-items: flex-start; gap: 12px; font-size: 15.5px; line-height: 1.75; color: var(--muted); }
.sec-point b { color: var(--text); font-weight: 700; }
.sp-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--pink); flex-shrink: 0; margin-top: 8px; }
/* 01 区排版：标题/正文字号放大，保持与演示框比例协调 */
.sec-duo .sec-title { font-size: clamp(38px, 5.8vw, 68px); }
.sec-duo .sec-desc { font-size: 17px; max-width: 600px; }

/* 01 双栏布局：左文右玩具（02 全宽跑马灯、03 全宽步骤流） */
.sec-duo { display: grid; grid-template-columns: minmax(0, 1fr) 460px; gap: 56px; align-items: start; max-width: 1200px; margin: 0 auto 72px; }
.sec-duo .sec-head { margin-bottom: 0; }
.pipe-head { max-width: 1200px; margin: 0 auto 60px; }
@media (max-width: 1100px) {
  .sec-duo { grid-template-columns: 1fr; gap: 40px; }
}
/* 02 居中标题 */
.sec-head.center { margin: 0 auto 56px; text-align: center; }
.sec-head.center .sec-desc { margin-left: auto; margin-right: auto; }

/* 光标跟随环（lag ring） */
.cursor-ring {
  position: fixed; left: -15px; top: -15px; width: 30px; height: 30px;
  border: 1.5px solid var(--pink); border-radius: 50%;
  pointer-events: none; z-index: 9999; opacity: .55;
  transition: width .2s, height .2s, left .2s, top .2s, background .2s, border-color .2s, opacity .2s;
}
.cursor-ring.big {
  width: 44px; height: 44px; left: -22px; top: -22px;
  background: var(--pink-soft); border-color: var(--accent); opacity: .85;
}
@media (hover: none) { .cursor-ring { display: none; } }

/* 磁吸按钮：translate 由 JS 驱动，回弹带弹性 */
.magnetic { transition: translate .25s cubic-bezier(.22, 1.4, .36, 1); will-change: translate; }

/* ---------- 智能体卡片 ---------- */
/* 5 列单排：彻底消灭 auto-fit 4+1 落单卡；≤1100px 断点内改 3+2 Bento */
.agent-grid {
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 16px; max-width: 1280px; margin: 0 auto;
}
.agent-card {
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 22px 20px; cursor: pointer; transition: all .2s;
}
.agent-card:hover { transform: translateY(-6px); box-shadow: var(--shadow-hover); border-color: var(--pink); }
.ac-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.ac-icon {
  width: 40px; height: 40px; border-radius: var(--r-sm);
  background: var(--pink-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
}
.ac-icon svg { width: 19px; height: 19px; }
.ac-num { font-size: 10px; color: var(--dim); letter-spacing: .14em; }
.ac-name { font-size: 17.5px; font-weight: 800; letter-spacing: -.01em; }
.ac-en { font-size: 9.5px; color: var(--dim); letter-spacing: .18em; margin: 5px 0 11px; }
.ac-desc { font-size: 12.5px; line-height: 1.7; color: var(--muted); margin-bottom: 14px; }
.ac-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.ac-tag {
  font-size: 10px; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-full);
  padding: 3.5px 10px; letter-spacing: .06em;
}
.agent-card:hover .ac-tag { border-color: var(--pink-soft); background: var(--pink-soft); color: var(--accent); }

/* ---------- 能力条目（编辑风大字行） ---------- */
.cap-list { max-width: 1080px; margin: 0 auto; border-top: 1px solid var(--line); }
.cap-row {
  display: flex; align-items: flex-start; gap: clamp(18px, 3vw, 44px);
  padding: 34px 10px; border-bottom: 1px solid var(--line);
  transition: background .18s, transform .2s;
}
.cap-row:hover { background: #fff; }
.cap-num { font-size: 11px; color: var(--dim); letter-spacing: .14em; padding-top: 10px; flex-shrink: 0; }
.cap-main { flex: 1; min-width: 0; }
.cap-name { font-size: clamp(22px, 3vw, 34px); font-weight: 800; letter-spacing: -.02em; margin-bottom: 10px; transition: color .15s; }
.cap-row:hover .cap-name { color: var(--accent); }
.cap-desc { font-size: 14px; line-height: 1.75; color: var(--muted); max-width: 640px; }
.cap-tag {
  flex-shrink: 0; font-size: 10px; color: var(--dim); letter-spacing: .16em;
  border: 1px solid var(--line); border-radius: var(--r-full);
  padding: 6px 14px; margin-top: 6px; background: #fff;
}

/* ---------- 流程时间线（旧左时间线已删，03 区改用 StepFlow 全宽步骤流组件） ---------- */

/* ---------- 数据 ---------- */
.num-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 18px; max-width: 1280px; margin: 0 auto;
}
.num-card {
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 30px 26px; transition: all .2s;
}
.num-card:hover { transform: translateY(-6px); box-shadow: var(--shadow-hover); }
.num-value { font-size: clamp(52px, 6vw, 84px); font-weight: 800; letter-spacing: -.04em; line-height: 1; margin-bottom: 16px; color: var(--text); }
.num-label { font-size: 15px; font-weight: 700; margin-bottom: 8px; }
.num-sub { font-size: 9.5px; color: var(--dim); letter-spacing: .14em; }

/* ---------- Footer（DiceBear 官网式多列栏目） ---------- */
.foot { background: var(--surface); border-top: 1px solid var(--line); }
.foot-main {
  display: grid;
  grid-template-columns: minmax(260px, 1.1fr) 2.6fr;
  gap: clamp(36px, 5vw, 80px);
  padding: clamp(56px, 9vh, 84px) clamp(20px, 5vw, 64px) clamp(40px, 6vh, 60px);
  max-width: 1440px; margin: 0 auto;
}
.foot-brand .brand { display: flex; align-items: center; gap: 11px; }
.foot-brand .brand-logo {
  width: 34px; height: 34px; flex-shrink: 0;
  background: var(--pink); color: #141416;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-sm); box-shadow: var(--shadow);
}
.foot-brand .brand-name { font-size: 17px; font-weight: 800; letter-spacing: -.02em; }
.foot-desc { font-size: 13px; line-height: 1.85; color: var(--muted); margin: 18px 0 22px; max-width: 300px; }
.foot-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 26px; }
.fcol-title { font-size: 13.5px; font-weight: 800; margin-bottom: 18px; }
.fitem {
  display: block; padding: 0; margin-bottom: 13px;
  border: none; background: none; text-align: left;
  font-family: inherit; font-size: 13px; line-height: 1.5;
  color: var(--muted); cursor: pointer; transition: color .15s;
}
.fitem:hover { color: var(--accent); }
.fitem.plain { cursor: default; color: var(--dim); }
.fitem.plain:hover { color: var(--dim); }
.foot-base {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; flex-wrap: wrap;
  border-top: 1px solid var(--line);
  padding: 20px clamp(20px, 5vw, 64px);
  font-size: 10px; color: var(--dim); letter-spacing: .14em;
}

/* ---------- 滚动淡入 ---------- */
.reveal { opacity: 0; transform: translateY(26px); transition: opacity .7s cubic-bezier(.16, 1, .3, 1), transform .7s cubic-bezier(.16, 1, .3, 1); }
.reveal.in { opacity: 1; transform: none; }

/* ---------- 窄屏 ---------- */
@media (max-width: 1100px) {
  .hero-cards { display: none; }
  .land-links { display: none; }
  .land-nav .btn-dark { margin-left: auto; }
  .cap-tag { display: none; }
  .foot-main { grid-template-columns: 1fr; gap: 36px; }
  /* 平板：智能体卡 3+2 Bento，无落单 */
  .agent-grid { grid-template-columns: repeat(6, 1fr); }
  .agent-card:nth-child(-n+3) { grid-column: span 2; }
  .agent-card:nth-child(n+4) { grid-column: span 3; }
}
</style>
