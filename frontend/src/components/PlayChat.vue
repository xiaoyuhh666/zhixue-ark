<script setup>
/* 01 区迷你试玩机：预设问题 → 打字机模拟多智能体调度回复（纯前端演示，不调 API） */
import { ref, onBeforeUnmount } from 'vue'

const emit = defineEmits(['enter'])

const SCENES = [
  {
    q: '下周有期末考，怎么平衡复习和社团招新？',
    steps: [
      { agent: '调度智能体', label: '识别意图 · 拆解为 2 个任务', sys: true },
      { agent: '学习助手', text: '先按「分值 × 薄弱程度」排优先级：高数 60%、英语 25%、专业课 15%。每晚 7-9 点固定刷高数错题，零碎时间过英语真题。' },
      { agent: '生活服务', text: '招新摊位建议排在周末两天，工作日晚间完整留白给复习。需要的话我可以生成一张周计划表。' }
    ]
  },
  {
    q: '大创项目要中期检查了，帮我拆任务',
    steps: [
      { agent: '调度智能体', label: '识别意图 · 拆解为 2 个任务', sys: true },
      { agent: '竞赛指导', text: '中期检查三件套：进度报告、演示 demo、经费明细。按周拆好里程碑——本周写报告框架，下周补实验数据。' },
      { agent: '科研助手', text: '实验数据部分我检索了你上传的参考文献，图表规范可以沿用组里往届模板，我已整理好引用列表。' }
    ]
  },
  {
    q: '考研和秋招同时准备，可行吗？',
    steps: [
      { agent: '调度智能体', label: '识别意图 · 拆解为 2 个任务', sys: true },
      { agent: '求职指导', text: '可行，策略是「简历先行」：9 月前投出 20 份简历锁定保底 offer，之后全力冲刺考研初试。' },
      { agent: '学习助手', text: '复习采用「上午考研、下午秋招」双线制，数学每天保持 3 小时不间断，真题周测安排在周六上午。' }
    ]
  }
]

const scene = ref(-1)   // 当前播放的场景序号
const msgs = ref([])    // 消息流
const typing = ref(false)
const timers = ref([])
let typeTimer = null

function clearAll() {
  timers.value.forEach(clearTimeout)
  timers.value = []
  if (typeTimer) { clearInterval(typeTimer); typeTimer = null }
  typing.value = false
}

function play(i) {
  clearAll()
  scene.value = i
  msgs.value = []
  msgs.value.push({ role: 'user', text: SCENES[i].q })
  let delay = 450
  SCENES[i].steps.forEach((st) => {
    timers.value.push(setTimeout(() => {
      if (st.sys) {
        msgs.value.push({ role: 'sys', text: st.label })
        return
      }
      // 智能体分段：打字机逐字输出
      const m = { role: 'agent', agent: st.agent, text: '' }
      msgs.value.push(m)
      typing.value = true
      let p = 0
      typeTimer = setInterval(() => {
        m.text = st.text.slice(0, ++p)
        if (p >= st.text.length) {
          clearInterval(typeTimer); typeTimer = null; typing.value = false
        }
      }, 20)
    }, delay))
    delay += st.text ? st.text.length * 20 + 800 : 800
  })
}

onBeforeUnmount(clearAll)
</script>

<template>
  <div class="play-chat">
    <!-- 窗口标题栏 -->
    <div class="pc-bar">
      <span class="pc-dot d1"></span><span class="pc-dot d2"></span><span class="pc-dot d3"></span>
      <span class="pc-title mono">TRY ME — 点下方问题，看看它们怎么协作</span>
    </div>
    <!-- 消息舞台 -->
    <div class="pc-body">
      <div v-if="!msgs.length" class="pc-empty mono">STANDBY — 等待你的第一个问题…</div>
      <template v-for="(m, idx) in msgs" :key="idx">
        <div v-if="m.role === 'user'" class="pc-msg user">{{ m.text }}</div>
        <div v-else-if="m.role === 'sys'" class="pc-msg sys mono">
          <span class="pc-sys-dot"></span>{{ m.agent }} · {{ m.text }}
        </div>
        <div v-else class="pc-msg agent">
          <span class="pc-avatar">{{ m.agent[0] }}</span>
          <div class="pc-bubble">
            <div class="pc-agent mono">{{ m.agent }} <span class="pc-live">● LIVE</span></div>
            {{ m.text }}<span v-if="typing && idx === msgs.length - 1" class="pc-caret">▌</span>
          </div>
        </div>
      </template>
    </div>
    <!-- 预设问题 chips + CTA -->
    <div class="pc-chips">
      <button v-for="(s, i) in SCENES" :key="i" class="pc-chip" :class="{ on: scene === i }" @click="play(i)">
        {{ s.q }}
      </button>
    </div>
    <button class="pc-cta" @click="emit('enter')">在平台中亲自体验 <span class="arrow">→</span></button>
  </div>
</template>

<style scoped>
.play-chat {
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-lg);
  box-shadow: 0 24px 60px rgba(240, 130, 160, .13); overflow: hidden;
  display: flex; flex-direction: column;
}
.pc-bar { display: flex; align-items: center; gap: 6px; padding: 13px 18px; border-bottom: 1px solid var(--line); background: var(--surface); }
.pc-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--line); }
.d1 { background: #f5a8b8; } .d2 { background: #f7cdd7; } .d3 { background: #e3e3e6; }
.pc-title { margin-left: 8px; font-size: 9.5px; color: var(--dim); letter-spacing: .12em; }
.pc-body { min-height: 300px; max-height: 300px; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }
.pc-empty { margin: auto; font-size: 10.5px; color: var(--dim); letter-spacing: .15em; }
.pc-msg { font-size: 13px; line-height: 1.7; animation: pc-in .3s ease both; }
@keyframes pc-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.pc-msg.user {
  align-self: flex-end; max-width: 85%;
  background: var(--text); color: #fff;
  padding: 9px 14px; border-radius: 14px 14px 4px 14px;
}
.pc-msg.sys {
  align-self: center; display: flex; align-items: center; gap: 7px;
  font-size: 9.5px; color: var(--dim); letter-spacing: .1em;
  background: var(--pink-soft); border-radius: 999px; padding: 5px 12px;
}
.pc-sys-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); animation: pc-blink 1s ease-in-out infinite; }
@keyframes pc-blink { 50% { opacity: .25; } }
.pc-msg.agent { display: flex; gap: 10px; max-width: 92%; }
.pc-avatar {
  width: 28px; height: 28px; flex-shrink: 0; margin-top: 2px;
  background: var(--pink-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; font-weight: 800; font-size: 12px;
}
.pc-bubble { background: var(--surface); border: 1px solid var(--line); border-radius: 4px 14px 14px 14px; padding: 10px 13px; flex: 1; }
.pc-agent { font-size: 9px; color: var(--accent); letter-spacing: .12em; margin-bottom: 5px; }
.pc-live { color: var(--dim); font-size: 8px; }
.pc-caret { color: var(--accent); animation: pc-blink .7s steps(1) infinite; }
.pc-chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 18px 14px; }
.pc-chip {
  font-size: 11.5px; padding: 7px 13px; border-radius: 999px;
  border: 1px solid var(--line); background: #fff; cursor: pointer;
  transition: all .18s;
}
.pc-chip:hover { border-color: var(--pink); background: var(--pink-soft); transform: translateY(-1px); }
.pc-chip.on { background: var(--text); color: #fff; border-color: var(--text); }
.pc-cta {
  margin: 0 18px 18px; padding: 12px; border: none; border-radius: var(--r-md);
  background: var(--text); color: #fff; font-size: 13px; font-weight: 700; cursor: pointer;
  transition: all .18s;
}
.pc-cta:hover { background: var(--accent); transform: translateY(-2px); }
.pc-cta .arrow { margin-left: 4px; display: inline-block; transition: transform .18s; }
.pc-cta:hover .arrow { transform: translateX(4px); }
</style>
