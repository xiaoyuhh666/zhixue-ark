<script setup>
/* 学习足迹（2026-09-20 新增一级模块）：14 天对话趋势（手绘 SVG）+ 智能体使用分布 + 引用命中 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import PageHeader from './PageHeader.vue'
import { getInsights } from '../api'

const props = defineProps({
  meta: { type: Object, required: true }
})

const data = ref({ daily: [], agents: [], citations_msgs: 0, citations_snippets: 0, active_days: 0, total_conversations: 0, total_messages: 0, weak_points: [] })

/* ---- SVG 折线图几何计算（viewBox 720x240，左右留白） ---- */
const W = 720, H = 240, PAD_L = 34, PAD_R = 16, PAD_T = 18, PAD_B = 30
const chart = computed(() => {
  const daily = data.value.daily || []
  const max = Math.max(1, ...daily.map(d => d.count))
  const iw = W - PAD_L - PAD_R
  const ih = H - PAD_T - PAD_B
  const x = (i) => PAD_L + (daily.length > 1 ? (i / (daily.length - 1)) * iw : iw / 2)
  const y = (c) => PAD_T + ih - (c / max) * ih
  const pts = daily.map((d, i) => ({ ...d, cx: x(i), cy: y(d.count) }))
  const line = pts.map(p => `${p.cx.toFixed(1)},${p.cy.toFixed(1)}`).join(' ')
  const area = `${PAD_L},${PAD_T + ih} ${line} ${(W - PAD_R).toFixed(1)},${PAD_T + ih}`
  const yTicks = [0, 0.5, 1].map(t => ({ y: PAD_T + ih - t * ih, label: Math.round(t * max) }))
  return { pts, line, area, max, yTicks, baseY: PAD_T + ih }
})

const agentMax = computed(() => Math.max(1, ...(data.value.agents || []).map(a => a.count)))

onMounted(async () => {
  try {
    data.value = await getInsights()
  } catch (e) {
    ElMessage.error(e?.message || '加载足迹失败')
  }
})
</script>

<template>
  <section class="insights-view">
    <div class="page-wrap">
      <PageHeader v-bind="meta" />

      <!-- 总量四格 -->
      <div class="stat-row">
        <div class="stat-cell"><div class="stat-num">{{ data.total_conversations }}</div><div class="stat-label">累计对话</div></div>
        <div class="stat-cell"><div class="stat-num">{{ data.total_messages }}</div><div class="stat-label">累计消息</div></div>
        <div class="stat-cell"><div class="stat-num">{{ data.citations_snippets }}</div><div class="stat-label">引用片段</div></div>
        <div class="stat-cell"><div class="stat-num">{{ data.active_days }}</div><div class="stat-label">活跃天数</div></div>
      </div>

      <!-- 我的薄弱点：长期记忆聚合，竖向列表完整展示每条内容 -->
      <div class="chart-card weak-card">
        <div class="chart-head">
          <div class="chart-title">我的薄弱点</div>
          <div class="chart-sub">WEAK POINTS · 长期记忆自动识别</div>
        </div>
        <div v-if="data.weak_points.length" class="weak-list">
          <div
            v-for="w in data.weak_points"
            :key="w.id"
            class="weak-item"
            :title="w.content"
          >{{ w.content }}</div>
        </div>
        <div v-else class="chart-empty">暂未识别到薄弱点，多和智能体聊聊学习上的困扰吧</div>
        <div v-if="data.weak_points.length" class="weak-foot">来自长期记忆自动提炼 · 可在「个人中心 → 记忆」中管理</div>
      </div>

      <!-- 14 天对话趋势：手绘 SVG 折线 -->
      <div class="chart-card">
        <div class="chart-head">
          <div class="chart-title">近 14 天对话趋势</div>
          <div class="chart-sub">DAILY CONVERSATIONS · 按用户消息计数</div>
        </div>
        <svg :viewBox="`0 0 ${W} ${H}`" class="trend-svg" role="img">
          <!-- 网格与刻度 -->
          <line v-for="t in chart.yTicks" :key="'g' + t.y" :x1="PAD_L" :y1="t.y" :x2="W - PAD_R" :y2="t.y" stroke="var(--line)" stroke-width="1" stroke-dasharray="3 4" />
          <text v-for="t in chart.yTicks" :key="'t' + t.y" :x="PAD_L - 8" :y="t.y + 3" text-anchor="end" class="axis-text">{{ t.label }}</text>
          <!-- 面积 + 折线 -->
          <polygon :points="chart.area" fill="var(--pink-soft)" opacity="0.75" />
          <polyline :points="chart.line" fill="none" stroke="var(--pink)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <!-- 数据点 + 日期 -->
          <g v-for="(p, i) in chart.pts" :key="'p' + i">
            <circle :cx="p.cx" :cy="p.cy" r="3.4" fill="var(--bg)" stroke="var(--accent)" stroke-width="1.8" />
            <text v-if="p.count > 0" :x="p.cx" :y="p.cy - 9" text-anchor="middle" class="val-text">{{ p.count }}</text>
            <text v-if="i % 2 === 0" :x="p.cx" :y="chart.baseY + 18" text-anchor="middle" class="axis-text">{{ p.date }}</text>
          </g>
        </svg>
      </div>

      <div class="bottom-grid">
        <!-- 智能体使用分布 -->
        <div class="chart-card">
          <div class="chart-head">
            <div class="chart-title">智能体使用分布</div>
            <div class="chart-sub">AGENT USAGE · 按回复消息数</div>
          </div>
          <div v-if="data.agents.length" class="agent-bars">
            <div v-for="a in data.agents" :key="a.name" class="bar-row">
              <span class="bar-name">{{ a.name }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: (a.count / agentMax * 100) + '%' }"></div>
              </div>
              <span class="bar-count">{{ a.count }}</span>
            </div>
          </div>
          <div v-else class="chart-empty">还没有智能体回复记录，去对话页聊聊吧</div>
        </div>

        <!-- 引用命中 -->
        <div class="chart-card cite-card">
          <div class="chart-head">
            <div class="chart-title">知识库引用命中</div>
            <div class="chart-sub">CITATIONS · RAG 溯源</div>
          </div>
          <div class="cite-big">{{ data.citations_msgs }}</div>
          <div class="cite-label">条回答附带来源引用</div>
          <div class="cite-sub">共 {{ data.citations_snippets }} 个可溯源片段 · 点击对话中的引用角标可查看原文</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.insights-view { flex: 1; overflow-y: auto; min-height: 0; }
.page-wrap { max-width: 1080px; width: 100%; margin: 0 auto; padding: 44px 36px 60px; animation: fadeUp .45s ease both; }

.stat-row { display: flex; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin-top: 34px; }

/* 我的薄弱点：竖向列表，每条完整展示不截断 */
.weak-card { margin-top: 26px; }
.weak-list { display: flex; flex-direction: column; gap: 8px; padding: 6px 2px 2px; }
.weak-item {
  display: block; width: fit-content; max-width: 100%;
  border: 1px solid var(--pink); border-radius: var(--r-md);
  background: #fff; color: var(--text); font-size: 13px; font-weight: 500;
  padding: 9px 16px; line-height: 1.6; word-break: break-all;
  transition: all .18s; cursor: default;
}
.weak-item:hover { background: var(--pink-soft); border-color: var(--accent); color: var(--accent); transform: translateX(3px); box-shadow: 0 3px 10px var(--pink); }
.weak-foot {
  margin-top: 14px; padding-top: 11px; border-top: 1px dashed var(--line);
  font-family: var(--mono); font-size: 9px; letter-spacing: .08em; color: var(--dim);
}
.stat-cell { flex: 1; padding: 20px 8px; text-align: center; }
.stat-cell + .stat-cell { border-left: 1px solid var(--line); }
.stat-num { font-family: var(--mono); font-size: 24px; font-weight: 700; color: var(--text); }
.stat-label { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; margin-top: 6px; text-transform: uppercase; }

.chart-card {
  margin-top: 30px; background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); padding: 24px 26px;
}
.chart-head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 16px; }
.chart-title { font-size: 15px; font-weight: 800; color: var(--text); }
.chart-sub { font-family: var(--mono); font-size: 9.5px; letter-spacing: .14em; color: var(--dim); }
.trend-svg { width: 100%; height: auto; display: block; }
.axis-text { font-family: var(--mono); font-size: 10px; fill: var(--dim); letter-spacing: .05em; }
.val-text { font-family: var(--mono); font-size: 10.5px; fill: var(--accent); font-weight: 700; }

.bottom-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 22px; }
.agent-bars { display: flex; flex-direction: column; gap: 13px; }
.bar-row { display: flex; align-items: center; gap: 12px; }
.bar-name { width: 70px; flex-shrink: 0; font-size: 12.5px; font-weight: 600; color: var(--text); }
.bar-track { flex: 1; height: 14px; background: var(--surface-2); border-radius: var(--r-full); overflow: hidden; }
.bar-fill { height: 100%; background: var(--pink); border-radius: var(--r-full); transition: width .5s ease; }
.bar-count { font-family: var(--mono); font-size: 11.5px; color: var(--muted); width: 30px; text-align: right; }
.chart-empty { font-size: 12.5px; color: var(--dim); padding: 18px 0; }

.cite-card { display: flex; flex-direction: column; }
.cite-big { font-family: var(--mono); font-size: 52px; font-weight: 700; color: var(--accent); line-height: 1; margin-top: 8px; }
.cite-label { font-size: 13px; font-weight: 700; color: var(--text); margin-top: 10px; }
.cite-sub { font-size: 11.5px; color: var(--dim); line-height: 1.8; margin-top: 8px; }

@media (max-width: 1100px) {
  .bottom-grid { grid-template-columns: 1fr; }
  .page-wrap { padding: 30px 18px 48px; }
}
</style>
