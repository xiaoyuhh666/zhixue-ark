<script setup>
/* 对话页左侧边栏（DeepSeek 风格）：开启新对话 + 会话搜索 + 我的计划迷你卡
   + 时间分组历史（可折叠，记住状态）。智能体选择已迁至 ChatView 顶部胶囊条 */
import { computed, ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { getPlans, updatePlan } from '../api'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: Number, default: null }
})

const emit = defineEmits(['select', 'delete', 'new-chat', 'navigate'])

/* ---------- 会话搜索（纯前端标题过滤，与折叠叠加） ---------- */
const query = ref('')

/* ---------- 我的计划迷你卡：取任务计划中心「进行中」前 2 条，卡内展开步骤可勾选 ---------- */
const plans = ref([])
const expandedPlan = ref(null)   // 当前展开的计划 id
const planBusy = ref(false)      // 勾选保存中（防连点）

onMounted(async () => {
  try {
    const data = await getPlans()
    plans.value = (data || []).filter(p => !p.finished).slice(0, 2)
  } catch { /* 计划加载失败不打扰对话主流程 */ }
})

function togglePlanCard(p) {
  expandedPlan.value = expandedPlan.value === p.id ? null : p.id
}

/* 卡内勾选步骤：全量回传 items，成功后本地同步进度 */
async function toggleStep(p, idx) {
  if (planBusy.value) return
  planBusy.value = true
  const items = p.items.map((it, i) => i === idx ? { ...it, done: !it.done } : it)
  try {
    await updatePlan(p.id, { title: p.title, deadline: p.deadline, items })
    p.items = items
    p.done_count = items.filter(i => i.done).length
    if (p.done_count === p.total) {
      plans.value = plans.value.filter(x => x.id !== p.id)  // 已完成移出迷你卡
      ElMessage.success('计划全部完成，太棒了！')
    }
  } catch (e) {
    ElMessage.error(e?.message || '步骤更新失败')
  } finally {
    planBusy.value = false
  }
}

/* ---------- 历史会话按更新时间分组：今天 / 昨天 / 7 天内 / 更早 ---------- */
const GROUP_ORDER = ['今天', '昨天', '7 天内', '更早']
const DAY_MS = 86400000
const COLLAPSE_KEY = 'zhixue-sidebar-collapsed'

function groupOf(iso) {
  if (!iso) return '更早'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '更早'
  const now = new Date()
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const t = d.getTime()
  if (t >= startOfDay) return '今天'
  if (t >= startOfDay - DAY_MS) return '昨天'
  if (t >= startOfDay - 7 * DAY_MS) return '7 天内'
  return '更早'
}

/* 相对时间：学生隔几天回来一眼认出「上周复习数据结构的那个会话」 */
function relTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < DAY_MS) return Math.floor(diff / 3600000) + ' 小时前'
  if (diff < 7 * DAY_MS) return Math.floor(diff / DAY_MS) + ' 天前'
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/* 折叠状态（localStorage 记住，默认全部展开） */
const collapsed = ref(new Set(JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '[]')))

function toggleGroup(label) {
  const next = new Set(collapsed.value)
  next.has(label) ? next.delete(label) : next.add(label)
  collapsed.value = next
  localStorage.setItem(COLLAPSE_KEY, JSON.stringify([...next]))
}

/* 搜索中平铺显示匹配项；否则按组显示（折叠组隐藏条目） */
const groups = computed(() => {
  if (query.value.trim()) return []
  const map = {}
  for (const c of props.conversations) {
    const g = groupOf(c.updated_at || c.created_at)
    ;(map[g] = map[g] || []).push(c)
  }
  return GROUP_ORDER.filter(g => map[g]?.length)
    .map(g => ({ label: g, items: map[g], closed: collapsed.value.has(g) }))
})

const searchHits = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return null
  return props.conversations.filter(c => (c.title || '').toLowerCase().includes(q))
})

/* 当前会话所在组被收起时自动展开 */
watch(() => props.activeId, (id) => {
  if (id == null) return
  const conv = props.conversations.find(c => c.id === id)
  if (!conv) return
  const g = groupOf(conv.updated_at || conv.created_at)
  if (collapsed.value.has(g)) toggleGroup(g)
})
</script>

<template>
  <aside class="chat-config">
    <!-- DeepSeek 式开启新对话大按钮 -->
    <button class="new-chat-btn" @click="emit('new-chat')">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/></svg>
      开启新对话
    </button>

    <!-- 会话搜索：输入即按标题过滤 -->
    <div class="search-box">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input v-model="query" type="text" placeholder="搜索历史会话…" />
      <button v-if="query" class="search-clear" title="清空" @click="query = ''">×</button>
    </div>

    <!-- 我的计划迷你卡（进行中，最多 2 条）：点击卡头展开步骤清单，卡内可勾选推进 -->
    <div
      v-for="p in plans"
      :key="p.id"
      class="plan-card"
      :class="{ open: expandedPlan === p.id }"
    >
      <div class="plan-head" @click="togglePlanCard(p)">
        <div class="plan-kicker">MY PLAN · 进行中
          <svg class="chev" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
        </div>
        <div class="plan-title">{{ p.title }}</div>
        <div class="plan-bar"><div class="plan-fill" :style="{ width: p.total ? (p.done_count / p.total * 100) + '%' : '0%' }"></div></div>
        <div class="plan-meta"><span>已完成 {{ p.done_count }}/{{ p.total }} 步</span><span v-if="p.deadline">截止 {{ p.deadline }}</span></div>
      </div>
      <!-- 展开区：步骤清单，点击即勾选推进（同步任务计划中心） -->
      <div v-if="expandedPlan === p.id" class="plan-steps">
        <label
          v-for="(it, idx) in p.items"
          :key="idx"
          class="plan-step"
          :class="{ done: it.done }"
        >
          <input
            type="checkbox"
            :checked="it.done"
            :disabled="planBusy"
            @change="toggleStep(p, idx)"
          />
          <span class="step-text">{{ it.content }}</span>
        </label>
        <div class="plan-foot">勾选实时同步「任务计划中心」</div>
      </div>
    </div>

    <!-- 搜索结果（平铺） -->
    <template v-if="query.trim()">
      <div
        v-for="c in searchHits"
        :key="c.id"
        class="history-item"
        :class="{ active: c.id === activeId }"
        @click="emit('select', c.id)"
      >
        <div class="hi-body">
          <span class="history-title">{{ c.title }}</span>
          <span class="hi-preview">{{ c.last_message || '暂无消息' }}</span>
        </div>
        <span class="hi-time">{{ relTime(c.updated_at || c.created_at) }}</span>
        <button class="history-del" title="删除会话" @click.stop="emit('delete', c.id)">×</button>
      </div>
      <div v-if="!searchHits || searchHits.length === 0" class="history-empty">没有找到相关会话</div>
    </template>

    <!-- 时间分组历史列表：组名点击折叠/展开，状态记住 -->
    <template v-else>
      <div v-for="g in groups" :key="g.label" class="history-group">
        <div class="group-label" :class="{ closed: g.closed }" @click="toggleGroup(g.label)">
          <svg class="chev" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
          {{ g.label }}
          <span class="cnt">{{ g.items.length }}</span>
        </div>
        <template v-if="!g.closed">
          <div
            v-for="c in g.items"
            :key="c.id"
            class="history-item"
            :class="{ active: c.id === activeId }"
            @click="emit('select', c.id)"
          >
            <div class="hi-body">
              <span class="history-title">{{ c.title }}</span>
              <span class="hi-preview">{{ c.last_message || '暂无消息' }}</span>
            </div>
            <span class="hi-time">{{ relTime(c.updated_at || c.created_at) }}</span>
            <button class="history-del" title="删除会话" @click.stop="emit('delete', c.id)">×</button>
          </div>
        </template>
      </div>
      <div v-if="groups.length === 0" class="history-empty">暂无历史会话<br />点击上方按钮开始新对话</div>
    </template>
  </aside>
</template>

<style scoped>
.chat-config {
  width: 300px; flex-shrink: 0;
  border-right: 1px solid var(--line);
  background: var(--bg);
  overflow-y: auto; min-height: 0;
  padding: 18px 14px 24px;
}

/* DeepSeek 式开启新对话大按钮 */
.new-chat-btn {
  display: flex; align-items: center; justify-content: center; gap: 9px;
  width: 100%; padding: 13px 16px; margin-bottom: 10px;
  border: 1px solid var(--line); border-radius: var(--r-lg);
  background: var(--bg); color: var(--text);
  font-size: 14px; font-weight: 700; cursor: pointer; transition: all .18s;
}
.new-chat-btn:hover { border-color: var(--pink); background: var(--pink-soft); color: var(--accent); box-shadow: var(--shadow-hover); }
.new-chat-btn svg { color: var(--accent); }

/* 会话搜索框 */
.search-box {
  display: flex; align-items: center; gap: 8px;
  border: 1px solid var(--line); border-radius: var(--r-full);
  padding: 8px 13px; margin-bottom: 10px; color: var(--dim);
  transition: border-color .15s;
}
.search-box:focus-within { border-color: var(--pink); }
.search-box input {
  flex: 1; min-width: 0; border: none; outline: none; background: transparent;
  font-size: 12.5px; color: var(--text); font-family: var(--sans);
}
.search-box input::placeholder { color: var(--dim); }
.search-clear {
  border: none; background: transparent; color: var(--dim);
  font-size: 14px; cursor: pointer; line-height: 1; padding: 0;
}
.search-clear:hover { color: var(--accent); }

/* 我的计划迷你卡：点击卡头展开步骤清单，卡内勾选推进 */
.plan-card {
  border: 1px solid var(--line); border-radius: var(--r-md);
  margin-bottom: 8px; transition: border-color .15s, box-shadow .15s;
}
.plan-card:hover { border-color: var(--pink); }
.plan-card.open { border-color: var(--pink); box-shadow: var(--shadow-hover); }
.plan-head { padding: 11px 13px; cursor: pointer; }
.plan-kicker {
  font-family: var(--mono); font-size: 8.5px; letter-spacing: .16em;
  color: var(--accent); display: flex; align-items: center; gap: 6px;
}
.plan-kicker .chev { margin-left: auto; transition: transform .2s; color: var(--accent); }
.plan-card.open .plan-kicker .chev { transform: rotate(180deg); }
.plan-title {
  font-size: 12.5px; font-weight: 700; margin-top: 5px; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.plan-bar { height: 5px; background: var(--surface); border-radius: var(--r-full); margin-top: 8px; overflow: hidden; }
.plan-fill { height: 100%; background: var(--pink); border-radius: var(--r-full); transition: width .3s; }
.plan-meta {
  display: flex; justify-content: space-between;
  font-family: var(--mono); font-size: 8.5px; color: var(--dim); margin-top: 5px;
}
/* 展开区：步骤清单 */
.plan-steps { border-top: 1px dashed var(--line); padding: 8px 13px 10px; }
.plan-step {
  display: flex; align-items: flex-start; gap: 9px;
  padding: 7px 2px; cursor: pointer; font-size: 12px; line-height: 1.55;
  color: var(--text);
}
.plan-step + .plan-step { border-top: 1px solid var(--surface); }
.plan-step input { margin-top: 2px; accent-color: var(--accent); cursor: pointer; flex-shrink: 0; }
.plan-step:has(input:disabled) { opacity: .6; cursor: wait; }
.plan-step.done .step-text { color: var(--dim); text-decoration: line-through; }
.plan-foot {
  font-family: var(--mono); font-size: 8.5px; letter-spacing: .1em;
  color: var(--dim); padding-top: 7px; border-top: 1px solid var(--surface);
}

/* 时间分组历史列表：组名可折叠（2026-09-20 适度加大字号与间距） */
.group-label {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--mono); font-size: 11px; color: var(--dim);
  letter-spacing: .18em; margin: 20px 6px 7px;
  cursor: pointer; border-radius: var(--r-sm); padding: 5px 7px;
  transition: color .15s, background .15s; user-select: none;
}
.group-label:hover { color: var(--accent); background: var(--pink-soft); }
.group-label .chev { transition: transform .2s; flex-shrink: 0; }
.group-label.closed .chev { transform: rotate(-90deg); }
.group-label .cnt {
  margin-left: auto; font-size: 9.5px; letter-spacing: .04em;
  border: 1px solid var(--line); border-radius: var(--r-full); padding: 1px 8px;
}
.history-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 13px; font-size: 13.5px; cursor: pointer;
  color: var(--muted); border-radius: var(--r-sm); transition: all .15s;
}
.history-item:hover { color: var(--text); background: var(--surface); }
.history-item.active { color: var(--text); background: var(--pink-soft); font-weight: 600; }
/* 双行卡：标题 + 最后一条消息摘要，右侧相对时间（跨会话记忆的直观呈现） */
.hi-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.history-title { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hi-preview {
  font-size: 11px; font-weight: 400; color: var(--dim); line-height: 1.4;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.history-item:hover .hi-preview, .history-item.active .hi-preview { color: var(--muted); }
.hi-time {
  flex-shrink: 0; align-self: flex-start; margin-top: 3px;
  font-family: var(--mono); font-size: 9px; color: var(--dim); letter-spacing: .02em;
}
.history-del {
  flex-shrink: 0; width: 20px; height: 20px;
  border: none; background: transparent; color: var(--dim);
  font-size: 15px; line-height: 1; cursor: pointer;
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: all .15s;
}
.history-item:hover .history-del { opacity: 1; }
.history-del:hover { color: var(--accent); background: #fff; }
.history-empty { padding: 20px 8px; font-size: 12.5px; color: var(--dim); line-height: 1.8; text-align: center; }
</style>
