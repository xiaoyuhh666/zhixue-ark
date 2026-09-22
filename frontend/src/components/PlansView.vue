<script setup>
/* 任务计划中心（2026-09-20 新增一级模块）：对话规划一键转入 + 手动创建 + 步骤勾选推进 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import PageHeader from './PageHeader.vue'
import { getPlans, createPlan, updatePlan, deletePlan } from '../api'

const props = defineProps({
  meta: { type: Object, required: true }
})

const plans = ref([])
const creating = ref(false)
const newTitle = ref('')
const newDeadline = ref('')
const newStep = ref('')

async function load() {
  try {
    plans.value = await getPlans()
  } catch (e) {
    ElMessage.error(e?.message || '加载计划失败')
  }
}

async function create() {
  const title = newTitle.value.trim()
  if (!title) {
    ElMessage.warning('先给计划起个名字')
    return
  }
  creating.value = true
  try {
    const items = []
    if (newStep.value.trim()) items.push({ content: newStep.value.trim() })
    await createPlan({ title, deadline: newDeadline.value, category: newCat.value, items })
    newTitle.value = newDeadline.value = newStep.value = ''
    ElMessage.success('计划已创建')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function toggleStep(plan, idx) {
  const items = plan.items.map((it, i) => (i === idx ? { ...it, done: !it.done } : it))
  try {
    const updated = await updatePlan(plan.id, { items })
    plans.value = plans.value.map(p => (p.id === plan.id ? updated : p))
  } catch (e) {
    ElMessage.error(e?.message || '更新失败')
  }
}

async function addStep(plan) {
  const v = (plan._draft || '').trim()
  if (!v) return
  try {
    const updated = await updatePlan(plan.id, { items: [...plan.items, { content: v }] })
    updated._draft = ''
    plans.value = plans.value.map(p => (p.id === plan.id ? updated : p))
  } catch (e) {
    ElMessage.error(e?.message || '添加失败')
  }
}

async function remove(plan) {
  try {
    await deletePlan(plan.id)
    plans.value = plans.value.filter(p => p.id !== plan.id)
    ElMessage.success('计划已删除')
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

const active = computed(() => activePlans.value.filter(p => !p.finished))
const finished = computed(() => activePlans.value.filter(p => p.finished))

/* ---- 顶部统计条：进行中 / 已完成 / 步骤完成率 / 累计步骤 ---- */
const statRate = computed(() => {
  const t = plans.value.reduce((s, p) => s + (p.total || 0), 0)
  const d = plans.value.reduce((s, p) => s + (p.done_count || 0), 0)
  return t ? Math.round(d / t * 100) : 0
})
const totalSteps = computed(() => plans.value.reduce((s, p) => s + (p.total || 0), 0))
const totalDoneSteps = computed(() => plans.value.reduce((s, p) => s + (p.done_count || 0), 0))

/* ---- 计划分类色板与标签（分类筛选 + 卡片色点） ---- */
const CAT_COLORS = {
  study: '#ec4899', competition: '#f59e0b', research: '#8b5cf6',
  career: '#10b981', life: '#3b82f6', general: '#9ca3af'
}
const CAT_LABELS = {
  study: '学习助手', competition: '竞赛指导', research: '科研助手',
  career: '求职指导', life: '生活服务', general: '通用'
}

/* 计划分类筛选（与知识库一致） */
const activeCat = ref('all')

/* 新建计划归属模块：五域 + 通用（默认学习助手） */
const AGENT_CATS = [
  { key: 'study', icon: '📚', label: '学习助手' },
  { key: 'competition', icon: '🏆', label: '竞赛指导' },
  { key: 'research', icon: '🔬', label: '科研助手' },
  { key: 'career', icon: '💼', label: '求职指导' },
  { key: 'life', icon: '🏫', label: '生活服务' },
  { key: 'general', icon: '📄', label: '通用' }
]
const newCat = ref('study')
const catStats = computed(() => {
  const counts = {}
  for (const p of plans.value) counts[p.category || 'general'] = (counts[p.category || 'general'] || 0) + 1
  return Object.keys(CAT_LABELS).filter(c => counts[c]).map(c => ({ key: c, label: CAT_LABELS[c], count: counts[c], color: CAT_COLORS[c] }))
})
const activePlans = computed(() =>
  activeCat.value === 'all' ? plans.value : plans.value.filter(p => (p.category || 'general') === activeCat.value)
)

/* ---- 截止日仅用于待办排序（紧急优先），页面不展示任何时间元素 ---- */

/* ---- 已完成归档折叠（记忆开关状态） ---- */
const doneOpen = ref(localStorage.getItem('zhixue-plans-done-collapsed') !== '1')
function toggleDone() {
  doneOpen.value = !doneOpen.value
  localStorage.setItem('zhixue-plans-done-collapsed', doneOpen.value ? '0' : '1')
}

/* ---- 「待办聚焦」置顶条：所有未完成计划的待办步骤平铺（不按时间过滤），紧急的排前面 ----
   有截止日的按剩余天数升序在前（逾期最急），无截止日的按计划顺序殿后；
   每条 { id, planId, planTitle, content, color, days, cls }；cls: over=逾期 / today=今天 / soon=临近 / ''=无截止 */
const focusStrip = computed(() => {
  const list = []
  const today = new Date(); today.setHours(0, 0, 0, 0)
  for (const p of plans.value) {
    if (p.finished) continue
    let days = null
    if (p.deadline) days = Math.round((new Date(p.deadline + 'T00:00:00') - today) / 86400000)
    for (const [i, it] of (p.items || []).entries()) {
      if (it.done) continue
      list.push({
        id: `${p.id}-${i}`, planId: p.id, idx: i, planTitle: p.title,
        content: it.content, color: CAT_COLORS[p.category || 'general'] || '#9ca3af',
        days, cls: days == null ? '' : days < 0 ? 'over' : days === 0 ? 'today' : 'soon',
      })
    }
  }
  /* 紧急优先：逾期 > 今天 > 剩 N 天 > 无截止（组内按天数升序） */
  return list.sort((a, b) => {
    if (a.days == null) return b.days == null ? 0 : 1
    if (b.days == null) return -1
    return a.days - b.days
  })
})

/* 聚焦条内直接勾选推进（复用 toggleStep；勾完 focusStrip 自动重算，条目消失） */
function focusToggle(it) {
  const plan = plans.value.find(p => p.id === it.planId)
  if (plan) toggleStep(plan, it.idx)
}

onMounted(load)
</script>

<template>
  <section class="plans-view">
    <div class="page-wrap">
      <PageHeader v-bind="meta" />

      <!-- 顶部总览卡：四格统计 + 待办聚焦（合并一卡，页面主干） -->
      <div class="hero-card">
        <div class="stat-row">
          <div class="stat-cell"><div class="stat-num">{{ active.length }}</div><div class="stat-label">进行中</div></div>
          <div class="stat-cell"><div class="stat-num">{{ finished.length }}</div><div class="stat-label">已完成</div></div>
          <div class="stat-cell"><div class="stat-num">{{ statRate }}%</div><div class="stat-label">步骤完成率</div></div>
          <div class="stat-cell"><div class="stat-num">{{ totalDoneSteps }}<i class="stat-sub">/ {{ totalSteps }}</i></div><div class="stat-label">累计步骤</div></div>
        </div>

        <!-- 待办聚焦：全部未完成步骤平铺，紧急优先，可直接勾选推进（不做时间过滤） -->
        <div v-if="focusStrip.length" class="focus-sec">
          <div class="focus-head">
            <span class="focus-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/></svg>
              待办聚焦
            </span>
            <span class="focus-count">{{ focusStrip.length }} 步待办 · 紧急优先</span>
          </div>
          <div class="focus-list">
            <label
              v-for="it in focusStrip"
              :key="it.id"
              class="focus-item"
              :class="it.cls"
            >
              <input
                type="checkbox"
                :checked="false"
                @change="focusToggle(it)"
              />
              <i class="cat-dot" :style="{ background: it.color }"></i>
              <span class="focus-text">{{ it.content }}</span>
              <span class="focus-plan">{{ it.planTitle }}</span>
            </label>
          </div>
        </div>
      </div>

      <!-- 快速新建 -->
      <div class="creator">
        <!-- 归属模块：本计划属于哪位智能体（决定分类色点与筛选归属） -->
        <div class="c-cat-row">
          <span class="c-cat-label">所属模块：</span>
          <button
            v-for="c in AGENT_CATS"
            :key="c.key"
            class="cat-chip"
            :class="{ active: newCat === c.key }"
            @click="newCat = c.key"
          >{{ c.icon }} {{ c.label }}</button>
        </div>
        <div class="creator-line">
          <input v-model="newTitle" class="c-title" placeholder="新计划名称，如「数据结构期末复习」" @keydown.enter="create" />
          <input v-model="newDeadline" class="c-date" type="date" title="截止日期（可空）" />
          <button class="c-btn" :disabled="creating" @click="create">{{ creating ? '创建中…' : '+ 新建计划' }}</button>
        </div>
        <input v-model="newStep" class="c-step" placeholder="第一步做什么？（可选，创建后可继续添加步骤）" @keydown.enter="create" />
      </div>

      <!-- 进行中：组标题与分类筛选并排一行，筛选紧跟其后不散排 -->
      <div v-if="active.length" class="list-head">
        <span class="group-label inline">进行中 · {{ active.length }}</span>
        <div class="cat-row">
          <button class="cat-chip" :class="{ active: activeCat === 'all' }" @click="activeCat = 'all'">
            全部 {{ plans.length }}
          </button>
          <button
            v-for="c in catStats"
            :key="c.key"
            class="cat-chip"
            :class="{ active: activeCat === c.key }"
            @click="activeCat = activeCat === c.key ? 'all' : c.key"
          >
            <i class="cat-dot" :style="{ background: c.color }"></i>{{ c.label }} {{ c.count }}
          </button>
        </div>
      </div>
      <div v-for="p in active" :key="p.id" class="plan-card">
        <div class="plan-head">
          <div class="plan-title">
            <i class="cat-dot" :style="{ background: CAT_COLORS[p.category || 'general'] }"></i>
            {{ p.title }}
            <span v-if="p.source_message_id" class="plan-src">来自对话</span>
          </div>
          <div class="plan-right">
            <span class="plan-progress">{{ p.done_count }}/{{ p.total }}</span>
            <button class="plan-del" title="删除计划" @click="remove(p)">×</button>
          </div>
        </div>
        <div class="plan-bar"><div class="plan-fill" :style="{ width: (p.total ? p.done_count / p.total * 100 : 0) + '%' }"></div></div>
        <label v-for="(it, i) in p.items" :key="i" class="step" :class="{ done: it.done }">
          <input type="checkbox" :checked="it.done" @change="toggleStep(p, i)" />
          <span>{{ it.content }}</span>
        </label>
        <div v-if="!p.items.length" class="step-empty">还没有步骤，从对话页把规划「转为计划」，或在下方添加</div>
        <div class="step-add">
          <input v-model="p._draft" placeholder="添加步骤，回车确认" @keydown.enter="addStep(p)" />
        </div>
      </div>

      <!-- 已完成（可折叠归档） -->
      <button v-if="finished.length" class="group-label done-label clickable" @click="toggleDone">
        {{ doneOpen ? '▾' : '▸' }} 已完成 · {{ finished.length }}
      </button>
      <template v-if="finished.length && doneOpen">
        <div v-for="p in finished" :key="p.id" class="plan-card finished">
          <div class="plan-head">
            <div class="plan-title">{{ p.title }} <span class="plan-done-mark">✓ 全部完成</span></div>
            <button class="plan-del" title="删除计划" @click="remove(p)">×</button>
          </div>
          <label v-for="(it, i) in p.items" :key="i" class="step done">
            <input type="checkbox" :checked="it.done" @change="toggleStep(p, i)" />
            <span>{{ it.content }}</span>
          </label>
        </div>
      </template>

      <div v-if="!plans.length" class="empty">
        还没有计划。在对话页让智能体做一份规划，然后点回复下方的「✦ 转为计划」一键带过来；
        或在上方直接新建。
      </div>
    </div>
  </section>
</template>

<style scoped>
.plans-view { flex: 1; overflow-y: auto; min-height: 0; }
.page-wrap { max-width: 1080px; width: 100%; margin: 0 auto; padding: 44px 36px 60px; animation: fadeUp .45s ease both; }

/* 快速新建条（紧凑化：给下方计划列表让出视觉重心） */
.creator {
  margin-top: 22px; background: var(--bg); border: 1px dashed var(--line);
  border-radius: var(--r-lg); padding: 13px 18px 11px;
}
.creator-line { display: flex; gap: 10px; }
.c-title { flex: 1; border: none; border-bottom: 1px solid var(--line); background: transparent; padding: 9px 2px; font-size: 14px; color: var(--text); outline: none; }
.c-title:focus { border-color: var(--pink); }
.c-date { border: 1px solid var(--line); border-radius: var(--r-sm); padding: 8px 10px; font-family: var(--mono); font-size: 12px; color: var(--text); background: var(--bg); outline: none; }
.c-btn {
  border: none; border-radius: var(--r-full); background: var(--text); color: #fff;
  font-size: 12.5px; font-weight: 700; padding: 0 22px; cursor: pointer; transition: background .2s; white-space: nowrap;
}
.c-btn:hover:not(:disabled) { background: var(--accent); }
.c-btn:disabled { opacity: .5; cursor: not-allowed; }
.c-step { width: 100%; margin-top: 12px; border: none; background: transparent; font-size: 12.5px; color: var(--muted); outline: none; }

/* ---- 列表头：组标题与分类筛选并排一行 ---- */
.list-head { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 16px; margin: 34px 0 14px; }
.group-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: .18em; color: var(--dim); text-transform: uppercase; }
.group-label.inline { margin: 0; flex-shrink: 0; }
.cat-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; }
.done-label { color: var(--accent); }

/* 计划卡 */
.plan-card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); padding: 20px 22px; margin-bottom: 14px;
  transition: box-shadow .2s, border-color .2s;
}
.plan-card:hover { box-shadow: var(--shadow-hover); border-color: var(--pink); }
.plan-card.finished { opacity: .75; }
.plan-head { display: flex; align-items: center; gap: 14px; }
.plan-title { flex: 1; min-width: 0; font-size: 15.5px; font-weight: 800; color: var(--text); display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.plan-ddl, .plan-flag, .plan-src {
  font-family: var(--mono); font-size: 9.5px; letter-spacing: .08em;
  padding: 3px 10px; border-radius: var(--r-full); font-weight: 400;
}
.plan-ddl { border: 1px solid var(--line); color: var(--muted); }
.plan-flag { background: #fdeaea; color: #c0392b; }
.plan-src { background: var(--pink-soft); color: var(--accent); }
.plan-done-mark { font-family: var(--mono); font-size: 10px; color: var(--accent); letter-spacing: .1em; }
.plan-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.plan-progress { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.plan-del {
  width: 24px; height: 24px; border: none; background: transparent; color: var(--dim);
  font-size: 16px; cursor: pointer; border-radius: 50%; opacity: 0; transition: all .15s;
}
.plan-card:hover .plan-del { opacity: 1; }
.plan-del:hover { color: var(--accent); background: var(--pink-soft); }
.plan-bar { height: 4px; background: var(--surface-2); border-radius: var(--r-full); overflow: hidden; margin: 12px 0 6px; }
.plan-fill { height: 100%; background: var(--pink); border-radius: var(--r-full); transition: width .3s ease; }

.step { display: flex; align-items: flex-start; gap: 11px; padding: 9px 2px; font-size: 13.5px; color: var(--text); cursor: pointer; line-height: 1.55; }
.step input { accent-color: var(--accent); width: 15px; height: 15px; margin-top: 2px; flex-shrink: 0; }
.step.done span { color: var(--dim); text-decoration: line-through; }
.step-empty { font-size: 12px; color: var(--dim); padding: 8px 2px; }
.step-add input {
  width: 100%; border: none; border-bottom: 1px dashed var(--line); background: transparent;
  padding: 8px 2px; font-size: 12.5px; color: var(--muted); outline: none; transition: border-color .15s;
}
.step-add input:focus { border-color: var(--pink); }

.empty { margin-top: 48px; padding: 40px; border: 1.5px dashed var(--line); border-radius: var(--r-lg); text-align: center; font-size: 13px; color: var(--dim); line-height: 2; }

/* ---- 顶部总览卡：统计四格 + 待办聚焦合并 ---- */
.hero-card {
  margin-top: 34px; background: var(--surface);
  border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 6px 22px 16px; box-shadow: var(--shadow-hover);
}
.stat-row { display: flex; border-bottom: 1px dashed var(--line); }
.stat-cell { flex: 1; padding: 18px 8px 14px; text-align: center; }
.stat-cell + .stat-cell { border-left: 1px solid var(--line); }
.stat-num { font-family: var(--mono); font-size: 24px; font-weight: 700; color: var(--text); }
.stat-sub { font-style: normal; font-size: 13px; font-weight: 400; color: var(--dim); margin-left: 2px; }
.stat-label { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; margin-top: 6px; text-transform: uppercase; }

/* ---- 待办聚焦区（卡内分区）：全部未完成步骤，紧急优先，无时间过滤 ---- */
.focus-sec { padding-top: 14px; }
.focus-head { display: flex; align-items: baseline; gap: 12px; }
.focus-title {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: 14.5px; font-weight: 800; color: var(--accent);
}
.focus-title svg { width: 15px; height: 15px; }
.focus-count { font-family: var(--mono); font-size: 9.5px; letter-spacing: .1em; color: var(--dim); }
.focus-list { margin-top: 6px; display: flex; flex-direction: column; }
.focus-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 4px; font-size: 13px; color: var(--text); cursor: pointer;
  border-top: 1px dashed var(--line); line-height: 1.5;
}
.focus-item:first-child { border-top: none; }
.focus-item input { accent-color: var(--accent); width: 15px; height: 15px; flex-shrink: 0; }
.focus-text { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.focus-plan {
  flex-shrink: 0; margin-left: auto; max-width: 180px;
  font-size: 11px; color: var(--dim);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ---- 新建计划归属模块 chips ---- */
.c-cat-row { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-bottom: 10px; }
.c-cat-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: .12em; color: var(--dim); }

/* ---- 计划分类筛选（list-head 内，无独立间距） ---- */
.cat-chip {
  display: inline-flex; align-items: center; gap: 7px;
  border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--surface); color: var(--muted);
  font-size: 12px; padding: 7px 14px; cursor: pointer; transition: all .15s;
}
.cat-chip:hover { border-color: var(--pink); color: var(--accent); }
.cat-chip.active { border-color: var(--pink); background: var(--pink-soft); color: var(--accent); font-weight: 600; }
.cat-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0; }

/* ---- 已完成归档折叠头 ---- */
.group-label.clickable {
  display: inline-block; background: none; border: none; cursor: pointer;
  font-family: var(--mono); font-size: 10.5px; letter-spacing: .18em; color: var(--accent);
  margin: 34px 0 14px; text-transform: uppercase; padding: 0;
  transition: opacity .15s;
}
.group-label.clickable:hover { opacity: .7; }
</style>
