<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import PageHeader from './PageHeader.vue'
import { getMemories, createMemory, deleteMemory } from '../api'

const props = defineProps({ meta: { type: Object, required: true } })

const TAG_LABELS = {
  general: '通用', study: '学习', competition: '竞赛',
  research: '科研', career: '求职', life: '生活'
}
const TAG_COLORS = {
  study: '#ec4899', competition: '#f59e0b', research: '#8b5cf6',
  career: '#10b981', life: '#3b82f6', general: '#9ca3af'
}

/* 记忆如何工作：三步流程（答辩演示「AI 记得你」的叙事） */
const FLOW = [
  { num: '01', icon: '⚡', title: '提炼', desc: '对话结束自动沉淀关键事实，也可在下方手动记录' },
  { num: '02', icon: '💉', title: '注入', desc: '新会话开启时注入全部五位智能体的系统提示词' },
  { num: '03', icon: '🎯', title: '影响', desc: '回答带着你的背景展开，免去重复自我介绍' }
]

const mems = ref([])
const q = ref('')
const newContent = ref('')
const newTag = ref('general')
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    mems.value = await getMemories(q.value)
  } catch (e) {
    ElMessage.error(e?.message || '加载记忆失败')
  } finally {
    loading.value = false
  }
}

async function add() {
  const content = newContent.value.trim()
  if (!content) return
  try {
    const res = await createMemory(content, newTag.value)
    if (res.created === false) {
      ElMessage.info('已存在相同内容的记忆')
    } else {
      ElMessage.success('记忆已添加，所有智能体共享')
      await load()
    }
    newContent.value = ''
  } catch (e) {
    ElMessage.error(e?.message || '添加失败')
  }
}

async function remove(id) {
  try {
    await deleteMemory(id)
    mems.value = mems.value.filter(m => m.id !== id)
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

function fmt(iso) {
  return iso ? iso.slice(0, 16).replace('T', ' ') : ''
}
/* 来源标记：有关联会话 = 对话中沉淀，否则手动记录 */
function srcLabel(m) {
  return m.source_conversation_id ? { icon: '⚡', text: '对话沉淀' } : { icon: '✎', text: '手动记录' }
}
function tagColor(tag) {
  return TAG_COLORS[tag] || TAG_COLORS.general
}

onMounted(load)
</script>

<template>
  <section class="memory-view">
    <div class="page-wrap">
      <PageHeader v-bind="meta" />

      <!-- 记忆如何工作：提炼 → 注入 → 影响 -->
      <div class="flow-row">
        <template v-for="(f, i) in FLOW" :key="f.num">
          <div class="flow-card">
            <div class="flow-head"><span class="flow-num">{{ f.num }}</span><span class="flow-ic">{{ f.icon }}</span></div>
            <div class="flow-title">{{ f.title }}</div>
            <div class="flow-desc">{{ f.desc }}</div>
          </div>
          <div v-if="i < FLOW.length - 1" class="flow-arrow">→</div>
        </template>
      </div>

      <div class="toolbar">
        <input v-model="q" class="search" placeholder="搜索记忆关键词" @keydown.enter="load" />
        <button class="btn-ghost" @click="load">搜索</button>
      </div>

      <div class="add-row">
        <input v-model="newContent" class="add-input" placeholder="记一条长期记忆，如：正在准备数学建模国赛" @keydown.enter="add" />
        <select v-model="newTag" class="tag-select">
          <option value="general">通用</option>
          <option value="study">学习</option>
          <option value="competition">竞赛</option>
          <option value="research">科研</option>
          <option value="career">求职</option>
          <option value="life">生活</option>
        </select>
        <button class="btn-add" @click="add">添加</button>
      </div>

      <!-- 记忆时间线：竖线 + 分类色节点 + 来源标记 -->
      <div class="tl-head">记忆时间线 <span class="tl-count">{{ mems.length }}</span></div>
      <div v-if="!loading && mems.length === 0" class="empty">
        还没有长期记忆。对话中会自动沉淀（需配置模型），也可以在上方手动添加。
      </div>
      <div v-else class="tl">
        <div v-for="m in mems" :key="m.id" class="tl-item">
          <span class="tl-dot" :style="{ background: tagColor(m.tag) }"></span>
          <div class="tl-card">
            <div class="tl-meta">
              <span class="mem-tag" :style="{ background: tagColor(m.tag) + '1a', color: tagColor(m.tag) }">{{ TAG_LABELS[m.tag] || '通用' }}</span>
              <span class="tl-src"><i>{{ srcLabel(m).icon }}</i>{{ srcLabel(m).text }}</span>
              <span class="mem-time">{{ fmt(m.created_at) }}</span>
              <button class="mem-x" title="删除" @click="remove(m.id)">×</button>
            </div>
            <div class="mem-content">{{ m.content }}</div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.memory-view { flex: 1; overflow-y: auto; min-height: 0; }
.page-wrap { max-width: 1080px; width: 100%; margin: 0 auto; padding: 44px 36px 60px; animation: fadeUp .45s ease both; }

/* ---- 记忆如何工作：三步流程 ---- */
.flow-row { display: flex; align-items: stretch; gap: 14px; margin-top: 34px; }
.flow-card {
  flex: 1; border: 1px solid var(--line); border-radius: var(--r-md);
  background: var(--surface); padding: 16px 18px; transition: all .2s;
}
.flow-card:hover { border-color: var(--pink); transform: translateY(-2px); }
.flow-head { display: flex; align-items: center; justify-content: space-between; }
.flow-num { font-family: var(--mono); font-size: 11px; font-weight: 700; letter-spacing: .12em; color: var(--accent); }
.flow-ic { font-size: 17px; }
.flow-title { margin-top: 9px; font-size: 14px; font-weight: 700; color: var(--text); }
.flow-desc { margin-top: 5px; font-size: 11.5px; line-height: 1.7; color: var(--dim); }
.flow-arrow { align-self: center; font-family: var(--mono); font-size: 15px; color: var(--pink); flex-shrink: 0; }

/* ---- 搜索与添加 ---- */
.toolbar { display: flex; gap: 12px; margin-top: 28px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.search {
  flex: 1; max-width: 360px; border: none; border-bottom: 1px solid var(--line);
  background: transparent; padding: 8px 2px; font-size: 13px; color: var(--text);
  font-family: var(--sans);
}
.search:focus { outline: none; border-bottom-color: var(--pink); }
.btn-ghost {
  border: 1px solid var(--line); background: var(--bg); border-radius: var(--r-full);
  padding: 7px 18px; font-family: var(--mono); font-size: 11px; letter-spacing: .08em;
  color: var(--muted); cursor: pointer; transition: all .15s;
}
.btn-ghost:hover { border-color: var(--pink); color: var(--accent); }
.add-row { display: flex; gap: 12px; margin-top: 18px; align-items: center; }
.add-input {
  flex: 1; border: 1px solid var(--line); border-radius: var(--r-full);
  padding: 11px 18px; font-size: 13px; color: var(--text); background: var(--bg);
  font-family: var(--sans); transition: border-color .15s;
}
.add-input:focus { outline: none; border-color: var(--pink); }
.tag-select {
  border: 1px solid var(--line); border-radius: var(--r-full); background: var(--bg);
  padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--muted);
  cursor: pointer;
}
.btn-add {
  border: none; border-radius: var(--r-full); background: var(--text); color: #fff;
  padding: 11px 24px; font-family: var(--mono); font-size: 12px; letter-spacing: .08em;
  cursor: pointer; transition: background .18s;
}
.btn-add:hover { background: var(--accent); }

/* ---- 记忆时间线 ---- */
.tl-head {
  margin-top: 30px; font-family: var(--mono); font-size: 11.5px; font-weight: 700;
  letter-spacing: .16em; color: var(--muted);
}
.tl-count {
  margin-left: 8px; background: var(--pink-soft); color: var(--accent);
  border-radius: var(--r-full); padding: 2px 9px; font-size: 10px;
}
.empty { font-size: 13px; color: var(--dim); padding: 30px 0; }
.tl { margin-top: 18px; position: relative; padding-left: 26px; }
.tl::before { content: ''; position: absolute; left: 5px; top: 8px; bottom: 8px; width: 2px; background: var(--line); border-radius: 1px; }
.tl-item { position: relative; padding-bottom: 14px; animation: fadeUp .4s ease both; }
.tl-dot {
  position: absolute; left: -26px; top: 18px; width: 12px; height: 12px;
  border-radius: 50%; border: 2.5px solid #fff; box-shadow: 0 0 0 1.5px var(--line);
}
.tl-card {
  border: 1px solid var(--line); border-radius: var(--r-md); background: var(--surface);
  padding: 13px 16px 12px; transition: border-color .15s;
}
.tl-card:hover { border-color: var(--pink); }
.tl-meta { display: flex; align-items: center; gap: 10px; }
.mem-tag {
  flex-shrink: 0; font-family: var(--mono); font-size: 10px; letter-spacing: .08em;
  border-radius: var(--r-full); padding: 3px 10px;
}
.tl-src {
  display: inline-flex; align-items: center; gap: 4px;
  font-family: var(--mono); font-size: 10px; letter-spacing: .06em; color: var(--dim);
}
.tl-src i { font-style: normal; font-size: 10.5px; }
.mem-time { margin-left: auto; flex-shrink: 0; font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .04em; }
.mem-x {
  flex-shrink: 0; border: none; background: none; color: var(--dim);
  font-size: 15px; cursor: pointer; padding: 0 2px; line-height: 1; transition: color .15s;
}
.mem-x:hover { color: var(--accent); }
.mem-content { margin-top: 8px; font-size: 13.5px; line-height: 1.7; color: var(--text); }
</style>
