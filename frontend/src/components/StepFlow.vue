<script setup>
/* 03 区全宽步骤流（2026-09-20 重设计，替代「左时间线 + 右轨道卡」双栏）：
   六步各占一行，编号 + 标题描述 + 行内产物迷你可视化；
   进入视口后 S1→S6 依次点亮（每步右侧产物入场），播完停顿后循环；
   IO 离场暂停清零、回场重播，1s 心跳兜底防停演 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  steps: { type: Array, required: true }  // [{num,title,desc}]
})

const STEP_MS = 950      // 每步点亮间隔
const HOLD_TICKS = 3     // 播完后停留的 tick 数（≈2.85s）再重播

const rootEl = ref(null)
const litCount = ref(0)  // 已点亮步数（0~6）
let timer = 0
let holdLeft = 0
let io = null
let heartbeat = 0
let inView = false

function tick() {
  if (holdLeft > 0) {
    holdLeft--
    if (holdLeft === 0) litCount.value = 0  // 停留结束，清零重播
    return
  }
  if (litCount.value < props.steps.length) {
    litCount.value++
    if (litCount.value === props.steps.length) holdLeft = HOLD_TICKS
  }
}
function start() {
  if (timer) return
  timer = window.setInterval(tick, STEP_MS)
}
function stop() {
  if (timer) { clearInterval(timer); timer = 0 }
  holdLeft = 0
  litCount.value = 0
}

onMounted(() => {
  io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      inView = e.isIntersecting
      if (inView) start(); else stop()
    })
  }, { threshold: 0.25 })
  if (rootEl.value) io.observe(rootEl.value)
  // 心跳兜底：在视口却没在播就重启（IO 失灵 / 定时器被意外清掉的场合）
  heartbeat = window.setInterval(() => {
    if (inView && !timer) start()
  }, 1000)
})
onBeforeUnmount(() => {
  stop()
  if (io) io.disconnect()
  clearInterval(heartbeat)
})
</script>

<template>
  <div ref="rootEl" class="sf">
    <div
      v-for="(s, i) in steps" :key="s.num"
      class="sf-row" :class="{ on: i < litCount }"
    >
      <span class="sf-num mono">{{ s.num }}</span>
      <div class="sf-text">
        <h3 class="sf-title">{{ s.title }}</h3>
        <p class="sf-desc">{{ s.desc }}</p>
      </div>
      <div class="sf-viz">
        <!-- S1 一句话提问：黑色气泡 + 闪烁光标 -->
        <template v-if="i === 0">
          <div class="vz-bubble">
            帮我规划考研和求职怎么平衡
            <span class="vz-caret"></span>
          </div>
        </template>
        <!-- S2 意图识别：双域识别胶囊 -->
        <template v-else-if="i === 1">
          <div class="vz-chips">
            <span class="vz-chip pink">📚 学习</span>
            <span class="vz-x">×</span>
            <span class="vz-chip pink">💼 求职</span>
          </div>
        </template>
        <!-- S3 任务拆解：任务 chips 依次弹入 -->
        <template v-else-if="i === 2">
          <div class="vz-chips">
            <span class="vz-chip dark">T1 定目标</span>
            <span class="vz-chip dark">T2 查资料</span>
            <span class="vz-chip dark">T3 出方案</span>
          </div>
        </template>
        <!-- S4 领域执行：智能体 + 检索工具进度 -->
        <template v-else-if="i === 3">
          <div class="vz-exec">
            <span class="vz-agent">📚</span>
            <div class="vz-tool">
              <div class="vz-tool-name mono">KB_SEARCH · 检索知识库</div>
              <div class="vz-bar"><i></i></div>
            </div>
          </div>
        </template>
        <!-- S5 汇总整合：汇总胶囊 -->
        <template v-else-if="i === 4">
          <div class="vz-merge">3 段产出 → 1 个连贯回答</div>
        </template>
        <!-- S6 引用溯源：引用卡 + 相似度 -->
        <template v-else>
          <div class="vz-cite">
            <div class="vz-cite-head"><span class="vz-cite-icon">📄</span>考研与求职时间规划.pdf</div>
            <div class="vz-cite-bar"><i></i><em>0.72</em></div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sf {
  max-width: 1200px; margin: 0 auto;
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-lg);
  overflow: hidden;
}
.sf-row {
  display: grid; grid-template-columns: 88px 1fr 300px;
  gap: 24px; align-items: center;
  padding: 20px 28px; border-bottom: 1px solid var(--line);
  opacity: .32; transition: opacity .5s ease, background .3s ease;
}
.sf-row:last-child { border-bottom: none; }
.sf-row.on { opacity: 1; }
.sf-row.on:nth-child(odd) { background: #fff; }
.sf-row.on:nth-child(even) { background: linear-gradient(90deg, var(--pink-soft), rgba(252, 228, 238, 0)); }

.sf-num {
  font-size: 26px; font-weight: 800; color: var(--dim); letter-spacing: .04em;
  transition: color .3s ease;
}
.sf-row.on .sf-num { color: var(--accent); }

.sf-title { font-size: 17px; font-weight: 800; margin-bottom: 4px; }
.sf-desc { font-size: 13px; color: var(--muted); }

/* 行内产物可视化：入场 = 上移淡入，内部小元素各自 delay 排队 */
.sf-viz { min-height: 46px; display: flex; align-items: center; }
.sf-row .sf-viz > * { opacity: 0; transform: translateY(8px); transition: opacity .4s ease, transform .4s ease; }
.sf-row.on .sf-viz > * { opacity: 1; transform: translateY(0); }

/* S1 黑色提问气泡 */
.vz-bubble {
  background: var(--text); color: #fff; font-size: 12.5px; font-weight: 600;
  padding: 9px 14px; border-radius: 14px 14px 14px 4px;
  display: inline-flex; align-items: center; gap: 2px;
}
.vz-caret { width: 2px; height: 13px; background: var(--pink); margin-left: 6px; animation: vz-blink 1s steps(1) infinite; }
@keyframes vz-blink { 50% { opacity: 0; } }

/* S2/S3 chips：容器常显，入场交给每枚 chip 自己（0/.12/.24s 依次弹入） */
.vz-chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sf-row .vz-chips { opacity: 1; transform: none; transition: none; }
.sf-row .vz-chips > * { opacity: 0; transform: translateY(8px); transition: opacity .35s ease, transform .35s ease; }
.sf-row.on .vz-chips > * { opacity: 1; transform: translateY(0); }
.sf-row.on .vz-chips > :nth-child(2) { transition-delay: .12s; }
.sf-row.on .vz-chips > :nth-child(3) { transition-delay: .24s; }
.vz-chip {
  font-size: 12px; font-weight: 700; padding: 6px 12px;
  border-radius: var(--r-full); white-space: nowrap;
}
.vz-chip.pink { background: var(--pink-soft); color: var(--accent); }
.vz-chip.dark { background: var(--text); color: #fff; }
.vz-x { font-size: 12px; color: var(--dim); font-weight: 700; }

/* S4 智能体执行 */
.vz-exec { display: flex; align-items: center; gap: 12px; width: 100%; }
.vz-agent {
  width: 38px; height: 38px; border-radius: 50%; flex: none;
  background: var(--pink-soft); display: flex; align-items: center; justify-content: center;
  font-size: 17px; transition-delay: .12s;
}
.vz-tool { flex: 1; min-width: 0; transition-delay: .2s; }
.vz-tool-name { font-size: 10px; color: var(--dim); letter-spacing: .1em; margin-bottom: 6px; }
.vz-bar { height: 5px; border-radius: 99px; background: var(--surface); overflow: hidden; }
.vz-bar i {
  display: block; height: 100%; width: 0; border-radius: 99px;
  background: linear-gradient(90deg, var(--pink), var(--accent));
}
.sf-row.on .vz-bar i { animation: vz-fill 1.6s ease forwards .3s; }
@keyframes vz-fill { to { width: 82%; } }

/* S5 汇总胶囊 */
.vz-merge {
  background: rgba(139, 109, 255, .12); color: #6a4de0;
  font-size: 12.5px; font-weight: 700; padding: 9px 16px;
  border-radius: var(--r-full); white-space: nowrap;
}

/* S6 引用卡 */
.vz-cite {
  width: 100%; background: var(--surface); border: 1px solid var(--line);
  border-radius: 12px; padding: 9px 12px; transition-delay: .12s;
}
.vz-cite-head { font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px; margin-bottom: 7px; }
.vz-cite-bar { display: flex; align-items: center; gap: 8px; }
.vz-cite-bar i {
  flex: 1; height: 4px; border-radius: 99px; background: var(--surface);
  position: relative; overflow: hidden; display: block;
}
.vz-cite-bar i::after {
  content: ''; position: absolute; inset: 0; width: 0;
  background: var(--accent); border-radius: 99px;
}
.sf-row.on .vz-cite-bar i::after { animation: vz-fill2 1.4s ease forwards .35s; }
@keyframes vz-fill2 { to { width: 72%; } }
.vz-cite-bar em { font-style: normal; font-size: 10.5px; color: var(--accent); font-weight: 800; }

/* 窄屏：产物区换行到文字下方 */
@media (max-width: 900px) {
  .sf-row { grid-template-columns: 56px 1fr; row-gap: 12px; padding: 18px 18px; }
  .sf-num { font-size: 20px; }
  .sf-viz { grid-column: 2; min-height: 0; }
}
</style>
