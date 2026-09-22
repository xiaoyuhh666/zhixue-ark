<script setup>
/* 个人中心（2026-09-20 信息架构重组）：右上角用户卡进入
   四个 Tab：我的画像（原 02 页）/ 长期记忆（原 03 页）/ 智能体图鉴 / 模型管理 */
import { onMounted, reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import ProfileView from './ProfileView.vue'
import MemoryView from './MemoryView.vue'
import { getStats, getSettings, updateSettings, testSettingsKey, getInsights, getKbDocuments, getPlans } from '../api'

const props = defineProps({
  meta: { type: Object, required: true },
  user: { type: Object, default: null },  // 当前登录账号（退出登录展示用）
  // 当前 Tab：由 App 层 hash 二级路径驱动（#/app/account/<tab>），参与浏览器回退
  tab: { type: String, default: 'profile' }
})

const emit = defineEmits(['navigate', 'logout', 'tab'])

/* 当前 Tab 由 props.tab 驱动（hash 二级路径），点击时 emit('tab') 让 App 层写入历史 */

/* 各 Tab 的页头（迁入的画像/记忆页保留自己的 PageHeader） */
const TAB_META = {
  profile: {
    title: '我的画像', badge: '画像',
    kicker: 'ME · 01 — User Persona', en: 'User Persona',
    desc: '画像注入所有智能体的提示词：填得越完整，回答越贴合你的情况。'
  },
  memory: {
    title: '长期记忆', badge: '记忆',
    kicker: 'ME · 02 — Long-term Memory', en: 'Long-term Memory',
    desc: '对话结束后自动沉淀的记忆条目，所有智能体跨会话共享，可检索、手动增删。'
  }
}

/* ---- 智能体图鉴 Tab：五助手出场档案 + 五域覆盖雷达 + 协作成就 ---- */
const stats = ref({ conversations: 0, messages: 0, docs: 0, memories: 0 })
const insights = ref({})
const kbDocs = ref([])
const plans = ref([])

const AGENT_DEX = [
  { key: 'study', icon: '📚', name: '学习助手', duty: '课程复习 · 知识点讲解 · 学习规划' },
  { key: 'competition', icon: '🏆', name: '竞赛指导', duty: '赛程规划 · 备赛策略 · 团队分工' },
  { key: 'research', icon: '🔬', name: '科研助手', duty: '文献检索 · 论文写作 · 科研入门' },
  { key: 'career', icon: '💼', name: '求职指导', duty: '简历打磨 · 面试准备 · 秋招节奏' },
  { key: 'life', icon: '🏫', name: '生活服务', duty: '作息调节 · 校园生活 · 心理疏解' }
]

/* 图鉴卡：派出次数（insights.agents 按中文名归组）+ 域内资料/计划数 */
const dexAgents = computed(() => {
  const usage = {}
  for (const a of insights.value.agents || []) usage[a.name] = a.count
  const docCount = {}, planCount = {}
  for (const d of kbDocs.value) docCount[d.category] = (docCount[d.category] || 0) + 1
  for (const p of plans.value) planCount[p.category || 'general'] = (planCount[p.category || 'general'] || 0) + 1
  const list = AGENT_DEX.map(a => ({
    ...a,
    dispatch: usage[a.name] || 0,
    docs: docCount[a.key] || 0,
    plans: planCount[a.key] || 0
  }))
  const max = Math.max(...list.map(a => a.dispatch), 0)
  return list.map(a => ({ ...a, top: a.dispatch > 0 && a.dispatch === max }))
})

/* 五域覆盖雷达：域内 (文档数*2 + 计划数) 封顶 6，归一到 0~1 */
const R = 78, CX = 100, CY = 100
const radarPts = computed(() => {
  const n = dexAgents.value.length
  return dexAgents.value.map((a, i) => {
    const v = Math.min(1, (a.docs * 2 + a.plans) / 6)
    const ang = -Math.PI / 2 + i * 2 * Math.PI / n
    return { x: CX + Math.cos(ang) * R * v, y: CY + Math.sin(ang) * R * v }
  })
})
const radarOuter = computed(() => {
  const n = dexAgents.value.length
  return Array.from({ length: n }, (_, i) => {
    const ang = -Math.PI / 2 + i * 2 * Math.PI / n
    return `${CX + Math.cos(ang) * R},${CY + Math.sin(ang) * R}`
  }).join(' ')
})
function ringPts(scale) {
  const n = dexAgents.value.length
  return Array.from({ length: n }, (_, i) => {
    const ang = -Math.PI / 2 + i * 2 * Math.PI / n
    return `${CX + Math.cos(ang) * R * scale},${CY + Math.sin(ang) * R * scale}`
  }).join(' ')
}
const radarPolygon = computed(() => radarPts.value.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '))

/* 协作成就：从现有数据推导，达成点亮 */
const badges = computed(() => {
  const s = stats.value, ins = insights.value
  return [
    { icon: '🚀', name: '首航', desc: '开启第一场对话', got: (s.conversations || 0) >= 1 },
    { icon: '💯', name: '深度用户', desc: '累计 10 场对话', got: (s.conversations || 0) >= 10 },
    { icon: '📚', name: '资料奠基', desc: '上传第一份知识文档', got: (s.docs || 0) >= 1 },
    { icon: '🔍', name: '检索达人', desc: '回答附来源引用', got: (ins.citations_msgs || 0) >= 1 },
    { icon: '🧠', name: '长期主义', desc: '沉淀第一条长期记忆', got: (s.memories || 0) >= 1 },
    { icon: '🔥', name: '坚持记录', desc: '活跃天数 ≥ 3', got: (ins.active_days || 0) >= 3 }
  ]
})

async function loadDex() {
  try { insights.value = await getInsights() } catch { /* 不阻塞 */ }
  try { kbDocs.value = await getKbDocuments() } catch { /* 不阻塞 */ }
  try { plans.value = await getPlans() } catch { /* 不阻塞 */ }
}

/* ---- 模型管理 Tab ---- */
const settings = ref({ providers: [], default_provider: 'deepseek' })
const keyDraft = reactive({ deepseek_api_key: '', qwen_api_key: '', glm_api_key: '' })
const savingSettings = ref(false)
/* 连通测试状态：{ [provider]: { status: 'testing'|'ok'|'fail', text, ms } } */
const testState = ref({})
/* 「全部测试」：批量跑完后生成延迟排行（升序，最快者标冠军） */
const testingAll = ref(false)
const allRank = ref([])

/* 当前使用的供应商对象（默认模型摘要卡） */
const currentProvider = computed(() =>
  settings.value.providers.find(p => p.provider === settings.value.default_provider) || null
)

/* 模型用量分布：真实来自 messages 表按 provider 归组，归一为横条百分比 */
const modelUsage = computed(() => {
  const list = stats.value.model_usage || []
  const max = Math.max(...list.map(u => u.count), 1)
  return list.map(u => ({ ...u, pct: Math.round((u.count / max) * 100) }))
})

async function testKey(provider) {
  testState.value = { ...testState.value, [provider]: { status: 'testing', text: '测试中…' } }
  try {
    const r = await testSettingsKey(provider)
    testState.value = {
      ...testState.value,
      [provider]: r.ok
        ? { status: 'ok', text: `✓ 连通正常 · ${r.latency_ms}ms · ${r.model}`, ms: r.latency_ms }
        : { status: 'fail', text: `✗ ${r.error}`, ms: null },
    }
  } catch (e) {
    testState.value = { ...testState.value, [provider]: { status: 'fail', text: `✗ ${e?.message || '请求失败'}`, ms: null } }
  }
}

async function testAll() {
  testingAll.value = true
  allRank.value = []
  try {
    const ps = settings.value.providers
    await Promise.all(ps.map(p => testKey(p.provider)))
    allRank.value = ps
      .map(p => ({ label: p.label, ms: testState.value[p.provider]?.ms }))
      .filter(x => x.ms != null)
      .sort((a, b) => a.ms - b.ms)
    if (!allRank.value.length) ElMessage.warning('没有供应商测试通过，请先检查密钥')
  } finally {
    testingAll.value = false
  }
}

async function loadStats() {
  try { stats.value = await getStats() } catch { /* 不阻塞 */ }
}

async function loadSettings() {
  try { settings.value = await getSettings() } catch { /* 不阻塞 */ }
}

async function saveSettings() {
  savingSettings.value = true
  try {
    const body = {}
    for (const k of ['deepseek_api_key', 'qwen_api_key', 'glm_api_key']) {
      if (keyDraft[k].trim()) body[k] = keyDraft[k].trim()  // 留空=不改动
    }
    if (!Object.keys(body).length) {
      ElMessage.warning('请先粘贴要保存的 API Key')
      return
    }
    await updateSettings(body)
    ElMessage.success('密钥已保存，立即生效（无需重启）')
    keyDraft.deepseek_api_key = keyDraft.qwen_api_key = keyDraft.glm_api_key = ''
    await loadSettings()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    savingSettings.value = false
  }
}

async function clearKey(provider) {
  try {
    await updateSettings({ [`${provider}_api_key`]: '' })
    ElMessage.success('已清除该密钥，回落到 .env 配置')
    await loadSettings()
  } catch (e) {
    ElMessage.error(e?.message || '清除失败')
  }
}

onMounted(() => { loadStats(); loadSettings(); loadDex() })
</script>

<template>
  <section class="account-view">
    <div class="page-wrap">
      <div class="page-kicker">ME — ACCOUNT</div>

      <!-- Tab 栏 -->
      <div class="tab-bar">
        <button class="tab" :class="{ active: tab === 'profile' }" @click="emit('tab', 'profile')">
          <span class="tab-num">01</span>我的画像
        </button>
        <button class="tab" :class="{ active: tab === 'memory' }" @click="emit('tab', 'memory')">
          <span class="tab-num">02</span>长期记忆
        </button>
        <button class="tab" :class="{ active: tab === 'stats' }" @click="emit('tab', 'stats')">
          <span class="tab-num">03</span>智能体图鉴
        </button>
        <button class="tab" :class="{ active: tab === 'settings' }" @click="emit('tab', 'settings')">
          <span class="tab-num">04</span>模型管理
        </button>
      </div>

      <!-- 画像 / 记忆：整页组件迁入，保留自身页头与逻辑 -->
      <template v-if="tab === 'profile' || tab === 'memory'">
        <ProfileView v-if="tab === 'profile'" :meta="TAB_META.profile" class="tab-panel" />
        <MemoryView v-else :meta="TAB_META.memory" class="tab-panel" />
      </template>

      <!-- 智能体图鉴：出场档案 + 五域雷达 + 协作成就 -->
      <div v-else-if="tab === 'stats'" class="tab-panel">
        <div class="panel-head">
          <div class="panel-title">智能体图鉴</div>
          <div class="panel-sub">五位助手各司其职 —— 谁最常为你出场？五域覆盖几何？</div>
        </div>

        <!-- 出场档案卡 -->
        <div class="dex-cards">
          <div v-for="a in dexAgents" :key="a.key" class="dex-card" :class="{ top: a.top }">
            <div class="dex-avatar">{{ a.icon }}</div>
            <div class="dex-name">
              {{ a.name }}
              <span v-if="a.top" class="dex-top">★ 最常出场</span>
            </div>
            <div class="dex-duty">{{ a.duty }}</div>
            <div class="dex-nums">
              <div class="dex-num"><b>{{ a.dispatch }}</b><i>派出</i></div>
              <div class="dex-num"><b>{{ a.docs }}</b><i>资料</i></div>
              <div class="dex-num"><b>{{ a.plans }}</b><i>计划</i></div>
            </div>
          </div>
        </div>

        <!-- 五域覆盖雷达 + 图例 -->
        <div class="dex-radar-row">
          <svg class="dex-radar" viewBox="0 0 200 200">
            <polygon v-for="s in [0.33, 0.66, 1]" :key="s" :points="ringPts(s)" class="radar-ring" />
            <line
              v-for="(p, i) in radarPts" :key="'ax' + i"
              :x1="CX" :y1="CY"
              :x2="(CX + Math.cos(-Math.PI / 2 + i * 2 * Math.PI / dexAgents.length) * R).toFixed(1)"
              :y2="(CY + Math.sin(-Math.PI / 2 + i * 2 * Math.PI / dexAgents.length) * R).toFixed(1)"
              class="radar-axis"
            />
            <polygon :points="radarPolygon" class="radar-data" />
            <circle v-for="(p, i) in radarPts" :key="'dot' + i" :cx="p.x.toFixed(1)" :cy="p.y.toFixed(1)" r="3" class="radar-dot" />
            <text
              v-for="(a, i) in dexAgents" :key="'lb' + i"
              :x="(CX + Math.cos(-Math.PI / 2 + i * 2 * Math.PI / dexAgents.length) * (R + 14)).toFixed(1)"
              :y="(CY + Math.sin(-Math.PI / 2 + i * 2 * Math.PI / dexAgents.length) * (R + 14) + 3).toFixed(1)"
              text-anchor="middle" class="radar-label"
            >{{ a.icon }}</text>
          </svg>
          <div class="dex-legend">
            <div class="legend-title">五域覆盖雷达</div>
            <p class="legend-desc">覆盖度 = 该域知识资料 ×2 + 计划数，封顶为满分六格。给冷落的域上传一份资料或建一个计划，雷达就会撑开一角。</p>
            <div v-for="a in dexAgents" :key="a.key" class="legend-row">
              <span class="legend-ic">{{ a.icon }}</span>{{ a.name }}
              <span class="legend-val">{{ a.docs * 2 + a.plans }}/6</span>
            </div>
            <button class="ghost-btn" @click="emit('navigate', 'knowledge')">去补充资料 →</button>
          </div>
        </div>

        <!-- 协作成就徽章 -->
        <div class="sec-label">协作成就</div>
        <div class="badge-row">
          <div v-for="b in badges" :key="b.name" class="badge" :class="{ got: b.got }">
            <div class="badge-ic">{{ b.icon }}</div>
            <div class="badge-name">{{ b.name }}</div>
            <div class="badge-desc">{{ b.desc }}</div>
          </div>
        </div>

        <button class="ghost-btn" @click="emit('navigate', 'insights')">查看学习足迹趋势 →</button>
      </div>

      <!-- 模型管理：当前使用摘要 + 三家 API Key -->
      <div v-else class="tab-panel">
        <div class="panel-head">
          <div class="panel-title">模型管理</div>
          <div class="panel-sub">API 密钥运行时生效，无需重启服务</div>
        </div>

        <!-- 00 — 当前使用摘要：默认模型 + 三家接入状态，联动模型广场 -->
        <div class="model-manage-card">
          <div class="mmc-left">
            <div class="mmc-label">当前使用</div>
            <div class="mmc-main">
              {{ currentProvider?.label || '未选择' }}
              <span class="mmc-model">{{ currentProvider?.model || '—' }}</span>
            </div>
            <div class="mmc-dots">
              <span v-for="p in settings.providers" :key="p.provider" class="mmc-dot-item">
                <span class="state-dot" :class="p.configured ? 'ok' : 'off'"></span>{{ p.label }}
              </span>
            </div>
          </div>
          <button class="ghost-btn" @click="emit('navigate', 'models')">前往模型广场 →</button>
        </div>

        <!-- 模型用量分布：messages 表按供应商归组的真实条数（柱状图） -->
        <div class="sec-label">模型用量分布</div>
        <div v-if="modelUsage.length" class="usage-chart">
          <div v-for="u in modelUsage" :key="u.provider" class="usage-col">
            <span class="usage-num">{{ u.count }}</span>
            <div class="usage-bar-area">
              <i class="usage-bar" :style="{ height: u.pct + '%' }"></i>
            </div>
            <span class="usage-name">
              {{ u.label }}
              <i v-if="u.provider === settings.default_provider" class="usage-def">默认</i>
            </span>
          </div>
        </div>
        <div v-else class="usage-empty">还没有对话记录 —— 去智能对话聊一轮，这里就会长出柱状图</div>

        <div class="sec-head">
          <div class="sec-label">01 — LLM API 密钥（OpenAI 兼容）</div>
          <button class="ghost-btn small" :disabled="testingAll" @click="testAll">
            {{ testingAll ? '测试中…' : '⚡ 全部测试' }}
          </button>
        </div>
        <div class="key-list">
          <div v-for="p in settings.providers" :key="p.provider" class="key-row">
            <div class="key-info">
              <div class="key-name">{{ p.label }}</div>
              <div class="key-state">
                <span class="state-dot" :class="p.configured ? 'ok' : 'off'"></span>
                {{ p.configured ? `已配置 ${p.masked}（${p.source === 'runtime' ? '运行时' : '.env'}）` : '未接入' }}
              </div>
            </div>
            <input
              v-model="keyDraft[`${p.provider}_api_key`]"
              class="key-input"
              type="password"
              :placeholder="p.configured ? '输入新密钥可覆盖' : '粘贴 API Key 后点保存'"
              autocomplete="off"
            />
            <button v-if="p.source === 'runtime'" class="ghost-btn small" @click="clearKey(p.provider)">清除</button>
            <button
              class="ghost-btn small"
              :disabled="!p.configured || testState[p.provider]?.status === 'testing'"
              :title="p.configured ? '发一个最小请求验证 Key 可用' : '先配置 Key 才能测试'"
              @click="testKey(p.provider)"
            >{{ testState[p.provider]?.status === 'testing' ? '测试中…' : '测试连通' }}</button>
            <!-- 测试结果行：必须在 v-for 作用域内（此前误置于循环外导致 p 未定义、设置面板渲染崩溃） -->
            <div v-if="testState[p.provider]" class="test-result" :class="testState[p.provider].status">
              {{ testState[p.provider].text }}
            </div>
          </div>
        </div>

        <button class="primary-btn" :disabled="savingSettings" @click="saveSettings">
          {{ savingSettings ? '保存中…' : '保存密钥' }}
        </button>

        <!-- 全部测试结果：延迟排行（升序，最快者高亮） -->
        <div v-if="allRank.length" class="lat-rank">
          <span class="lat-rank-label">延迟排行</span>
          <span v-for="(r, i) in allRank" :key="r.label" class="lat-item" :class="{ best: i === 0 }">
            {{ i === 0 ? '🏆 ' : '' }}{{ r.label }} {{ r.ms }}ms
          </span>
        </div>

        <!-- 密钥说明卡 -->
        <div class="key-notes">
          <div class="kn-item">密钥优先级：这里保存的运行时 Key 优先于 .env，点「清除」后自动回落 .env 配置</div>
          <div class="kn-item">输入框留空 = 不改动现有密钥；保存后立即生效，无需重启服务</div>
          <div class="kn-item">已配置的密钥以掩码显示（如 sk-****f691），仅用于确认，不会回传明文</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.account-view { flex: 1; overflow-y: auto; min-height: 0; }
.page-wrap { max-width: 1080px; width: 100%; margin: 0 auto; padding: 40px 36px 60px; animation: fadeUp .45s ease both; }
.page-kicker { font-family: var(--mono); font-size: 10.5px; color: var(--accent); letter-spacing: .18em; text-transform: uppercase; }

/* Tab 栏（编辑风：mono 序号 + 胶囊） */
.tab-bar { display: flex; gap: 6px; border-bottom: 1px solid var(--line); padding-bottom: 0; margin-top: 26px; }
.tab {
  display: flex; align-items: center; gap: 8px;
  padding: 11px 18px; border: none; background: transparent;
  font-size: 13.5px; color: var(--muted); cursor: pointer;
  border-radius: var(--r-md) var(--r-md) 0 0; transition: all .15s;
  border-bottom: 2px solid transparent;
}
.tab:hover { color: var(--text); background: var(--surface); }
.tab.active { color: var(--accent); background: var(--pink-soft); font-weight: 700; border-bottom-color: var(--pink); }
.tab-num { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; }
.tab.active .tab-num { color: var(--accent); }

.tab-panel { min-height: 0; }
/* 迁入的画像/记忆页：去掉自身外层滚动，融入本页滚动 */
.tab-panel :deep(.profile-view), .tab-panel :deep(.memory-view) { flex: none; overflow: visible; }

.panel-head { margin: 34px 0 20px; }
.panel-title { font-size: 21px; font-weight: 800; letter-spacing: -.01em; color: var(--text); }
.panel-sub { font-size: 12px; color: var(--dim); margin-top: 6px; }

.stat-row { display: flex; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.stat-cell { flex: 1; padding: 22px 8px; text-align: center; }
.stat-cell + .stat-cell { border-left: 1px solid var(--line); }
.stat-num { font-family: var(--mono); font-size: 26px; font-weight: 700; color: var(--text); }
.stat-label { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; margin-top: 6px; text-transform: uppercase; }
.ghost-btn {
  margin-top: 18px; padding: 10px 20px;
  border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--bg); color: var(--muted); font-size: 12.5px; cursor: pointer; transition: all .15s;
}
.ghost-btn:hover { border-color: var(--pink); color: var(--accent); background: var(--pink-soft); }
.ghost-btn.small { margin-top: 0; margin-left: 10px; padding: 8px 14px; flex-shrink: 0; }
.ghost-btn:disabled { opacity: .5; cursor: not-allowed; }

.sec-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: .16em; color: var(--dim); margin: 30px 0 12px; text-transform: uppercase; }
/* sec-head：区块标题 + 右侧操作按钮同行 */
.sec-head { display: flex; align-items: center; justify-content: space-between; margin: 30px 0 12px; }
.sec-head .sec-label { margin: 0; }

/* ---- 模型用量分布（柱状图）---- */
.usage-chart { display: flex; align-items: flex-end; gap: 40px; padding: 4px 4px 0; }
.usage-col { display: flex; flex-direction: column; align-items: center; gap: 8px; min-width: 86px; }
.usage-num { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.usage-bar-area {
  width: 48px; height: 110px; display: flex; align-items: flex-end;
  background: var(--surface); border-radius: 10px 10px 4px 4px; overflow: hidden;
}
.usage-bar { display: block; width: 100%; background: var(--pink); border-radius: 8px 8px 0 0; transition: height .5s ease; }
.usage-name { font-size: 12.5px; font-weight: 700; color: var(--text); display: flex; align-items: center; gap: 6px; }
.usage-def { font-family: var(--mono); font-size: 9.5px; font-style: normal; color: var(--accent); background: var(--pink-soft); padding: 2px 8px; border-radius: var(--r-full); }
.usage-empty { font-size: 12px; color: var(--dim); padding: 8px 0; }

/* ---- 延迟排行（全部测试结果）---- */
.lat-rank {
  display: flex; align-items: center; flex-wrap: wrap; gap: 12px;
  margin-top: 14px; padding: 11px 16px;
  background: var(--surface); border-radius: var(--r-md);
}
.lat-rank-label { font-family: var(--mono); font-size: 10px; letter-spacing: .14em; color: var(--dim); text-transform: uppercase; }
.lat-item { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.lat-item.best { color: var(--accent); font-weight: 700; }

/* ---- 密钥说明卡 ---- */
.key-notes { margin-top: 18px; border-top: 1px dashed var(--line); padding-top: 14px; display: flex; flex-direction: column; gap: 7px; }
.kn-item { font-size: 11.5px; color: var(--dim); line-height: 1.6; display: flex; gap: 8px; }
.kn-item::before { content: '·'; color: var(--accent); font-weight: 800; }

/* ---- 00 模型管理摘要卡 ---- */
.model-manage-card {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 16px 18px;
}
.mmc-label { font-family: var(--mono); font-size: 10px; letter-spacing: .16em; color: var(--dim); text-transform: uppercase; margin-bottom: 6px; }
.mmc-main { font-size: 17px; font-weight: 700; color: var(--ink); display: flex; align-items: baseline; gap: 8px; }
.mmc-model { font-family: var(--mono); font-size: 12px; font-weight: 400; color: var(--dim); }
.mmc-dots { display: flex; gap: 14px; margin-top: 8px; flex-wrap: wrap; }
.mmc-dot-item { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--dim); }
.key-row { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; padding: 13px 0; border-bottom: 1px solid var(--line); }
.key-info { width: 230px; flex-shrink: 0; }
.key-name { font-size: 13.5px; font-weight: 700; color: var(--text); }
.key-state { display: flex; align-items: center; gap: 7px; font-family: var(--mono); font-size: 10px; color: var(--dim); margin-top: 5px; }
.state-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.state-dot.ok { background: var(--pink); }
.state-dot.off { background: var(--line); }
.key-input {
  flex: 1; min-width: 0; border: 1px solid var(--line); border-radius: var(--r-sm);
  padding: 10px 13px; font-size: 12.5px; font-family: var(--mono);
  color: var(--text); outline: none; background: var(--bg); transition: border-color .15s;
}
.key-input:focus { border-color: var(--pink); }
/* 连通测试结果行：ok 粉 / fail 红 / testing 灰 */
.test-result {
  font-size: 12px; font-family: var(--mono); padding: 2px 0 8px;
  border-bottom: 1px solid var(--line); margin-bottom: 2px;
  width: 100%;  /* 在 key-row（flex-wrap）内独占一行，紧贴所属密钥行下方 */
}
.test-result.ok { color: var(--pink); }
.test-result.fail { color: #d4455a; }
.test-result.testing { color: var(--dim); }
.primary-btn {
  margin-top: 20px; padding: 12px 30px;
  border: none; border-radius: var(--r-full);
  background: var(--text); color: #fff; font-size: 13.5px; font-weight: 700;
  cursor: pointer; transition: background .2s;
}
.primary-btn:hover:not(:disabled) { background: var(--accent); }
.primary-btn:disabled { opacity: .5; cursor: not-allowed; }

@media (max-width: 1100px) {
  .page-wrap { padding: 28px 18px 48px; }
  .key-row { flex-wrap: wrap; }
  .key-info { width: 100%; }
  .key-input { flex: 1 1 200px; }
}

/* ---- 智能体图鉴 ---- */
.dex-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.dex-card {
  border: 1px solid var(--line); border-radius: var(--r-md); background: var(--surface);
  padding: 18px 16px 14px; text-align: center; transition: all .2s;
}
.dex-card:hover { border-color: var(--pink); transform: translateY(-3px); }
.dex-card.top { border-color: var(--pink); background: var(--pink-soft); }
.dex-avatar {
  width: 46px; height: 46px; border-radius: 50%; margin: 0 auto 10px;
  background: var(--bg); border: 1px solid var(--line);
  display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.dex-card.top .dex-avatar { border-color: var(--pink); background: #fff; }
.dex-name { font-size: 14px; font-weight: 700; color: var(--text); }
.dex-top {
  display: inline-block; margin-left: 4px; font-size: 9.5px; color: var(--accent);
  font-family: var(--mono); letter-spacing: .06em;
}
.dex-duty { margin-top: 5px; font-size: 10.5px; color: var(--dim); line-height: 1.6; min-height: 33px; }
.dex-nums { display: flex; margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 11px; }
.dex-num { flex: 1; }
.dex-num + .dex-num { border-left: 1px solid var(--line); }
.dex-num b { display: block; font-family: var(--mono); font-size: 17px; font-weight: 700; color: var(--accent); }
.dex-num i { font-style: normal; font-size: 9.5px; color: var(--dim); letter-spacing: .1em; }

/* 雷达区 */
.dex-radar-row { display: flex; align-items: center; gap: 30px; margin: 26px 0 6px; }
.dex-radar { width: 250px; height: 250px; flex-shrink: 0; }
.radar-ring { fill: none; stroke: var(--line); stroke-width: 1; }
.radar-axis { stroke: var(--line); stroke-width: 1; }
.radar-data { fill: rgba(236, 72, 153, .16); stroke: var(--accent); stroke-width: 1.6; stroke-linejoin: round; }
.radar-dot { fill: var(--accent); }
.radar-label { font-size: 12px; }
.dex-legend { flex: 1; }
.legend-title { font-family: var(--mono); font-size: 12px; font-weight: 700; letter-spacing: .14em; color: var(--text); }
.legend-desc { margin: 8px 0 14px; font-size: 12px; line-height: 1.8; color: var(--dim); }
.legend-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--muted); padding: 6px 0;
  border-bottom: 1px dashed var(--line);
}
.legend-ic { font-size: 13px; }
.legend-val { margin-left: auto; font-family: var(--mono); font-size: 11px; color: var(--accent); }
.dex-legend .ghost-btn { margin-top: 14px; }

/* 成就徽章 */
.badge-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-top: 14px; }
.badge {
  border: 1.5px dashed var(--line); border-radius: var(--r-md);
  padding: 16px 10px; text-align: center; opacity: .5; transition: all .2s;
}
.badge.got { border: 1px solid var(--pink); background: var(--pink-soft); opacity: 1; }
.badge-ic { font-size: 22px; }
.badge-name { margin-top: 7px; font-size: 12.5px; font-weight: 700; color: var(--text); }
.badge.got .badge-name { color: var(--accent); }
.badge-desc { margin-top: 3px; font-size: 10.5px; color: var(--dim); }
</style>
