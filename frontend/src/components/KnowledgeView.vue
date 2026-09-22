<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import PageHeader from './PageHeader.vue'
import { getKbDocuments, getKbDocContent, getKbChunks, searchKb, uploadKbDoc, deleteKbDoc } from '../api'

const props = defineProps({
  meta: { type: Object, required: true },
  citationJump: { type: Object, default: null }  // 引用溯源跳转（里程碑 7）：{docId, snippet}
})

const emit = defineEmits(['ask'])  // 检索试验台「去对话页追问」：携带问题文本

const docs = ref([])
const uploading = ref(false)
const fileInput = ref(null)
const dragOver = ref(false)
// 上传两阶段：upload（真实字节进度）→ parse（服务端解析/嵌入，不确定进度动画）
const phase = ref('upload')
const percent = ref(0)

const EXT_LABELS = { pdf: 'PDF', docx: 'DOC', pptx: 'PPT', md: 'MD', txt: 'TXT' }

const totalChunks = computed(() =>
  docs.value.reduce((s, d) => s + (d.chunk_count || 0), 0)
)
const readyCount = computed(() => docs.value.filter(d => d.status === 'ready').length)

async function load() {
  try {
    docs.value = await getKbDocuments()
  } catch (e) {
    ElMessage.error(e?.message || '加载文档列表失败')
  }
}

async function upload(file) {
  if (!file || uploading.value) return
  uploading.value = true
  phase.value = 'upload'
  percent.value = 0
  try {
    // 大文档需 CPU 嵌入，可能耗时数十秒
    const doc = await uploadKbDoc(file, (p) => {
      percent.value = Math.round(p * 100)
      if (p >= 1) phase.value = 'parse' // 字节传完，转入服务端解析阶段
    }, uploadCat.value)
    if (doc.status === 'ready') {
      ElMessage.success(`已入库：${doc.filename}（${doc.chunk_count} 分块）`)
    } else {
      ElMessage.error(`解析失败：${doc.note || '未提取到文本'}`)
    }
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

function onPick(e) {
  const files = e.target.files
  if (files && files[0]) upload(files[0])
  e.target.value = ''
}

function onDrop(e) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files && files[0]) upload(files[0])
}

async function remove(id) {
  try {
    await deleteKbDoc(id)
    docs.value = docs.value.filter(d => d.id !== id)
    ElMessage.success('文档与向量已删除')
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

function fmt(iso) {
  return iso ? iso.slice(0, 10) : ''
}

/* ---- 文档原文预览弹层（里程碑 7 引用溯源） ---- */
const preview = ref(null)  // {filename, categoryLabel, html}
const pvBody = ref(null)
const CAT_LABELS = { study: '课程学习', competition: '竞赛', research: '科研', career: '求职', life: '生活', general: '通用' }

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

async function openContent(docId, snippet) {
  try {
    const d = await getKbDocContent(docId)
    if (!d.content) {
      ElMessage.warning('该文档无可还原原文')
      return
    }
    // 空白归一化匹配（块拼接与 overlap 导致的空白差异），并映射回原文区间高亮
    let html = escHtml(d.content)
    let hit = false
    if (snippet) {
      let normStr = ''
      const map = []  // 归一化串下标 -> 原文字符下标
      for (let ci = 0; ci < d.content.length; ci++) {
        if (!/\s/.test(d.content[ci])) { normStr += d.content[ci]; map.push(ci) }
      }
      const normSnip = snippet.replace(/\s+/g, '')
      const pos = normSnip ? normStr.indexOf(normSnip) : -1
      if (pos >= 0) {
        const start = map[pos]
        const end = map[pos + normSnip.length - 1] + 1
        html = escHtml(d.content.slice(0, start)) + '<mark>' + escHtml(d.content.slice(start, end)) + '</mark>' + escHtml(d.content.slice(end))
        hit = true
      }
    }
    preview.value = { filename: d.filename, categoryLabel: CAT_LABELS[d.category] || d.category, html }
    ElMessage.success(hit ? '已定位到原文片段' : '原文片段未精确定位，已展示全文')
    await nextTick()
    const mk = pvBody.value && pvBody.value.querySelector('mark')
    if (mk) mk.scrollIntoView({ block: 'center' })
  } catch (e) {
    ElMessage.error(e?.message || '原文加载失败（文档可能已删除）')
  }
}

function closePreview() {
  preview.value = null
}

/* 引用角标跳转进入本页时自动打开原文弹层 */
watch(() => props.citationJump, (jump) => {
  if (jump && jump.docId != null) openContent(jump.docId, jump.snippet)
})

/* ---- 检索试验台（Retrieval Playground）：实时演示向量检索效果 ---- */
const q = ref('')
const searching = ref(false)
const searched = ref(false)  // 区分「未搜过」提示态与「无结果」态
const hits = ref([])

async function doSearch() {
  const query = q.value.trim()
  if (!query || searching.value) return
  searching.value = true
  try {
    const r = await searchKb(query, 3)
    hits.value = r.items || []
    searched.value = true
  } catch (e) {
    ElMessage.error(e?.message || '检索失败')
  } finally {
    searching.value = false
  }
}

/* 带着当前问题去对话页追问（App.vue 预填输入框并切换视图） */
function askInChat() {
  const query = q.value.trim()
  if (query) emit('ask', query)
}

/* ---- 上传归类：为哪位智能体补充资料（上传时随文件提交 category） ---- */
const AGENT_CATS = [
  { key: 'study', icon: '📚', label: '学习助手' },
  { key: 'competition', icon: '🏆', label: '竞赛指导' },
  { key: 'research', icon: '🔬', label: '科研助手' },
  { key: 'career', icon: '💼', label: '求职指导' },
  { key: 'life', icon: '🏫', label: '生活服务' },
  { key: 'general', icon: '📄', label: '通用资料' }
]
const uploadCat = ref('study')  // 默认归学习助手（平台主场景）
const uploadCatLabel = computed(() => (AGENT_CATS.find(c => c.key === uploadCat.value) || {}).label || '通用')

/* ---- 分块可视化：点击「分块」展开该文档的向量块流水线 ---- */
const openDoc = ref(null)  // 当前展开分块面板的文档 id
const chunks = ref([])
const chunksLoading = ref(false)
const openedChunks = ref(new Set())  // 已展开全文的块序号（点击文本行切换截断）

function toggleChunkText(i) {
  const s = new Set(openedChunks.value)
  s.has(i) ? s.delete(i) : s.add(i)
  openedChunks.value = s
}

async function toggleChunks(d) {
  if (openDoc.value === d.id) { openDoc.value = null; return }
  openDoc.value = d.id
  chunks.value = []
  openedChunks.value = new Set()
  chunksLoading.value = true
  try {
    const r = await getKbChunks(d.id)
    chunks.value = r.chunks || []
  } catch (e) {
    ElMessage.error(e?.message || '分块加载失败')
  } finally {
    chunksLoading.value = false
  }
}

/* ---- 分类筛选 + 分布条 ---- */
const activeCat = ref('all')
const CAT_COLORS = {
  study: '#ec4899', competition: '#f59e0b', research: '#8b5cf6',
  career: '#10b981', life: '#3b82f6', general: '#9ca3af'
}
const filteredDocs = computed(() =>
  activeCat.value === 'all' ? docs.value : docs.value.filter(d => d.category === activeCat.value)
)
const catStats = computed(() => {
  const counts = {}
  for (const d of docs.value) counts[d.category] = (counts[d.category] || 0) + 1
  return Object.keys(CAT_LABELS)
    .filter(c => counts[c])
    .map(c => ({ key: c, label: CAT_LABELS[c], count: counts[c], color: CAT_COLORS[c] }))
})

onMounted(load)
</script>

<template>
  <section class="kb-view">
    <div class="page-wrap">
      <PageHeader v-bind="meta" />

      <div class="stat-row">
        <div class="stat-cell"><div class="stat-num">{{ readyCount }}</div><div class="stat-label">已入库文档</div></div>
        <div class="stat-cell"><div class="stat-num">{{ totalChunks }}</div><div class="stat-label">向量分块</div></div>
        <div class="stat-cell"><div class="stat-num">TOP {{ 3 }}</div><div class="stat-label">检索条数</div></div>
        <div class="stat-cell"><div class="stat-num">BGE-M3</div><div class="stat-label">嵌入模型 · CPU</div></div>
      </div>

      <!-- 分类分布条：文档按分类的占比可视化 -->
      <div v-if="catStats.length" class="dist-row">
        <div class="dist-bar">
          <div
            v-for="c in catStats"
            :key="c.key"
            class="dist-seg"
            :style="{ width: (c.count / docs.length * 100) + '%', background: c.color }"
            :title="`${c.label} ${c.count} 篇`"
          ></div>
        </div>
        <div class="dist-legend">
          <span v-for="c in catStats" :key="c.key" class="dist-item">
            <i :style="{ background: c.color }"></i>{{ c.label }} {{ c.count }}
          </span>
        </div>
      </div>

      <!-- 检索试验台：输入问题实时看 Top-3 命中片段与相似度 -->
      <div class="playground">
        <div class="pg-head">RETRIEVAL PLAYGROUND · 检索试验台</div>
        <div class="pg-input-row">
          <input
            v-model="q"
            class="pg-input"
            placeholder="输入一个问题，看看知识库能检索到什么…"
            :disabled="searching"
            @keydown.enter="doSearch"
          />
          <button class="pg-btn" :disabled="!q.trim() || searching" @click="doSearch">
            {{ searching ? '检索中…' : '检索' }}
          </button>
        </div>
        <div v-if="searched" class="pg-results">
          <div v-if="!hits.length" class="pg-empty">
            没有检索到相关片段 —— 上传相关资料后即可命中
          </div>
          <div v-for="(h, i) in hits" :key="i" class="pg-hit">
            <div class="pg-hit-head">
              <span class="pg-rank">#{{ i + 1 }}</span>
              <div class="pg-score"><div class="pg-score-fill" :style="{ width: (h.score * 100) + '%' }"></div></div>
              <span class="pg-score-num">{{ (h.score * 100).toFixed(0) }}%</span>
              <span class="pg-doc">{{ h.doc }}</span>
            </div>
            <div class="pg-snippet">{{ h.snippet }}</div>
          </div>
        </div>
        <div v-else class="pg-hint">
          语义检索由 BGE-M3 向量驱动，Top-3 片段与相似度实时可见；命中后可带着问题去对话页追问。
        </div>
        <button v-if="searched && hits.length" class="pg-ask" @click="askInChat">
          带着这个问题去对话页追问 →
        </button>
      </div>

      <div
        class="upload-zone"
        :class="{ over: dragOver, busy: uploading }"
        @click="fileInput && fileInput.click()"
        @dragover.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop.prevent="onDrop"
      >
        <!-- 上传归类：本批资料归属哪位智能体（随上传提交 category） -->
        <div v-if="!uploading" class="up-cat-row" @click.stop>
          <span class="up-cat-label">补充给：</span>
          <button
            v-for="c in AGENT_CATS"
            :key="c.key"
            class="up-cat-chip"
            :class="{ active: uploadCat === c.key }"
            @click="uploadCat = c.key"
          ><span class="up-cat-ic">{{ c.icon }}</span>{{ c.label }}</button>
        </div>
        <div class="up-line">
          {{ uploading ? (phase === 'upload' ? 'Uploading' : 'Parsing · Chunking · Embedding') : 'Drop Files Here' }}
        </div>
        <template v-if="uploading">
          <!-- 两阶段进度条：字节上传真实进度 → 服务端解析不确定动画 -->
          <div class="progress">
            <div
              class="progress-bar"
              :class="{ indet: phase === 'parse' }"
              :style="{ width: phase === 'upload' ? `${Math.max(percent, 4)}%` : '40%' }"
            ></div>
          </div>
          <div class="progress-text">
            {{ phase === 'upload' ? `上传中 ${percent}%` : 'CPU 向量化中，大文件需要一些时间…' }}
          </div>
        </template>
        <template v-else>
          拖拽文件到此处，或 <b>点击上传</b>（支持 PDF / DOCX / PPTX / MD / TXT，单文件 ≤ 10MB）
          <div class="up-hint">本批资料将归入「{{ uploadCatLabel }}」，{{ uploadCatLabel }}在对话中将优先检索它们</div>
        </template>
        <input ref="fileInput" type="file" accept=".pdf,.docx,.pptx,.md,.txt" hidden @change="onPick" />
      </div>

      <div class="doc-table">
        <!-- 分类筛选 chips：点击过滤，再点取消 -->
        <div v-if="docs.length" class="cat-row">
          <button class="cat-chip" :class="{ active: activeCat === 'all' }" @click="activeCat = 'all'">
            全部 {{ docs.length }}
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
        <div v-if="docs.length === 0" class="empty">
          知识库还是空的。上传课程讲义、竞赛汇总等资料后，对话将自动检索并附带来源引用。
        </div>
        <div v-if="docs.length && filteredDocs.length === 0" class="empty">
          该分类下暂无文档。
        </div>
        <div v-for="d in filteredDocs" :key="d.id" class="doc-item">
          <div class="doc-row">
            <div class="doc-icon">{{ EXT_LABELS[d.ext] || 'DOC' }}</div>
            <div class="doc-info">
              <div class="doc-name">{{ d.filename }}</div>
              <div class="doc-meta">
                <span class="cat-dot" :style="{ background: CAT_COLORS[d.category] || CAT_COLORS.general }"></span>
                {{ CAT_LABELS[d.category] || d.category }} · .{{ d.ext }} · {{ d.chunk_count }} 分块<template v-if="d.note"> · {{ d.note }}</template>
              </div>
            </div>
            <div class="doc-right">
              <span>{{ fmt(d.created_at) }}</span>
              <span class="doc-status" :class="d.status === 'ready' ? 'ok' : 'fail'">
                {{ d.status === 'ready' ? '● 已入库' : '◌ 失败' }}
              </span>
              <button class="doc-chunks" title="查看该文档的向量分块" @click="toggleChunks(d)">
                {{ openDoc === d.id ? '收起' : '分块' }}
              </button>
              <button class="doc-x" title="删除文档与向量" @click="remove(d.id)">×</button>
            </div>
          </div>
          <!-- 分块可视化面板：解析→分块→向量化 产物逐条展示 -->
          <div v-if="openDoc === d.id" class="chunk-panel">
            <div class="kb-pipe">
              <span class="kb-pipe-step">解析 ✓</span>
              <span class="kb-pipe-arrow">→</span>
              <span class="kb-pipe-step">分块 {{ chunks.length }}</span>
              <span class="kb-pipe-arrow">→</span>
              <span class="kb-pipe-step">向量化 ✓</span>
            </div>
            <div v-if="chunksLoading" class="chunk-loading">正在取回向量块…</div>
            <div v-for="c in chunks" :key="c.index" class="chunk-card">
              <div class="chunk-head">
                <span class="chunk-idx">#{{ c.index + 1 }}</span>
                <span class="chunk-chars">{{ c.chars }} 字</span>
              </div>
              <div class="chunk-text" :class="{ open: openedChunks.has(c.index) }" title="点击展开/收起" @click="toggleChunkText(c.index)">{{ c.text }}</div>
            </div>
            <div v-if="!chunksLoading && !chunks.length" class="chunk-loading">
              未取到向量块（文档可能解析失败）
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 文档原文预览弹层（里程碑 7 引用溯源）：片段 <mark> 高亮 -->
    <div v-if="preview" class="pv-mask" @click.self="closePreview">
      <div class="pv-card">
        <div class="pv-head">
          <div class="pv-head-info">
            <div class="pv-title">{{ preview.filename }}</div>
            <div class="pv-meta">{{ preview.categoryLabel }} · 引用原文溯源</div>
          </div>
          <button class="pv-close" title="关闭" @click="closePreview">×</button>
        </div>
        <div ref="pvBody" class="pv-body" v-html="preview.html"></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.kb-view { flex: 1; overflow-y: auto; min-height: 0; }
.page-wrap { max-width: 1080px; width: 100%; margin: 0 auto; padding: 44px 36px 60px; animation: fadeUp .45s ease both; }

.stat-row { display: flex; gap: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin-top: 34px; }
.stat-cell { flex: 1; padding: 20px 8px; text-align: center; }
.stat-cell + .stat-cell { border-left: 1px solid var(--line); }
.stat-num { font-family: var(--mono); font-size: 24px; font-weight: 700; color: var(--text); }
.stat-label { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; margin-top: 6px; text-transform: uppercase; }

.upload-zone {
  border: 1.5px dashed var(--line); background: var(--surface);
  border-radius: var(--r-md); padding: 34px; text-align: center;
  color: var(--muted); cursor: pointer; margin: 36px 0 30px;
  transition: all .2s; font-size: 13px;
}
.upload-zone:hover, .upload-zone.over { border-color: var(--pink); background: var(--pink-soft); }
.upload-zone.busy { cursor: wait; color: var(--dim); }
.upload-zone b { color: var(--accent); font-weight: 600; }
.up-line { font-family: var(--mono); font-size: 10.5px; letter-spacing: .18em; color: var(--dim); margin-bottom: 12px; text-transform: uppercase; }

/* 上传进度条（里程碑 5） */
.progress {
  height: 4px; width: 60%; max-width: 420px; margin: 4px auto 12px;
  background: var(--surface-2); border-radius: var(--r-full); overflow: hidden;
}
.progress-bar { height: 100%; background: var(--pink); border-radius: var(--r-full); transition: width .15s ease; }
.progress-bar.indet { animation: slide 1.2s ease-in-out infinite; }
@keyframes slide { from { transform: translateX(-110%); } to { transform: translateX(280%); } }
.progress-text { font-family: var(--mono); font-size: 11px; color: var(--accent); letter-spacing: .06em; }

.doc-table { border-top: 1px solid var(--line); }
.empty { font-size: 13px; color: var(--dim); padding: 30px 0; }
.doc-row {
  display: flex; align-items: center; gap: 18px; padding: 17px 12px;
  border-bottom: 1px solid var(--line); font-size: 13px;
  border-radius: var(--r-sm); transition: background .15s;
  animation: fadeUp .4s ease both;
}
.doc-row:hover { background: var(--surface); }
.doc-icon {
  width: 42px; height: 42px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 10px; font-weight: 700; letter-spacing: .06em;
  background: var(--pink-soft); color: var(--accent);
  border-radius: var(--r-sm);
}
.doc-info { min-width: 0; }
.doc-name { font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-meta { font-family: var(--mono); font-size: 10.5px; color: var(--dim); margin-top: 4px; letter-spacing: .04em; }
.doc-right { margin-left: auto; display: flex; align-items: center; gap: 20px; font-family: var(--mono); font-size: 11px; color: var(--dim); flex-shrink: 0; }
.doc-status { font-size: 10px; letter-spacing: .14em; }
.doc-status.ok { color: var(--accent); }
.doc-status.fail { color: #c25454; }
.doc-x {
  border: none; background: none; color: var(--dim);
  font-size: 16px; cursor: pointer; padding: 0 4px; line-height: 1; transition: color .15s;
}
.doc-x:hover { color: var(--accent); }

/* 文档原文预览弹层（里程碑 7 引用溯源） */
.pv-mask {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(20, 20, 22, .35);
  display: flex; align-items: center; justify-content: center;
  animation: fadeUp .2s ease both;
}
.pv-card {
  width: min(760px, 92vw); height: min(78vh, 720px);
  background: var(--bg); border: 1px solid var(--line);
  border-radius: var(--r-lg); box-shadow: var(--shadow-hover);
  display: flex; flex-direction: column; overflow: hidden;
}
.pv-head {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 22px; border-bottom: 1px solid var(--line); flex-shrink: 0;
}
.pv-head-info { min-width: 0; }
.pv-title { font-size: 14px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pv-meta { font-family: var(--mono); font-size: 10.5px; color: var(--dim); margin-top: 3px; letter-spacing: .06em; }
.pv-close {
  margin-left: auto; width: 30px; height: 30px; flex-shrink: 0;
  border: none; background: transparent; color: var(--dim);
  font-size: 18px; cursor: pointer; border-radius: 50%; transition: all .15s;
}
.pv-close:hover { color: var(--accent); background: var(--pink-soft); }
.pv-body {
  flex: 1; overflow-y: auto; padding: 22px 26px;
  white-space: pre-wrap; word-break: break-word;
  font-size: 13px; line-height: 1.85; color: var(--text);
}
.pv-body :deep(mark) { background: var(--pink); color: #141416; border-radius: 3px; padding: 0 2px; }

/* ---- 分类分布条 ---- */
.dist-row { margin-top: 14px; }
.dist-bar { display: flex; height: 8px; border-radius: var(--r-full); overflow: hidden; background: var(--surface-2); }
.dist-seg { transition: width .4s ease; }
.dist-legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 9px; }
.dist-item { display: inline-flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .06em; }
.dist-item i { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }

/* ---- 检索试验台 ---- */
.playground {
  border: 1px solid var(--line); border-radius: var(--r-md); background: var(--surface);
  padding: 18px 20px; margin-top: 26px;
}
.pg-head { font-family: var(--mono); font-size: 10.5px; letter-spacing: .18em; color: var(--accent); text-transform: uppercase; }
.pg-input-row { display: flex; gap: 10px; margin-top: 13px; }
.pg-input {
  flex: 1; border: 1px solid var(--line); border-radius: var(--r-sm);
  background: var(--bg); padding: 11px 14px; font-size: 13.5px; color: var(--text);
  outline: none; transition: border-color .15s;
}
.pg-input:focus { border-color: var(--pink); }
.pg-btn {
  border: none; border-radius: var(--r-sm); padding: 0 22px;
  background: var(--text); color: #fff; font-size: 13px; cursor: pointer; transition: all .2s;
}
.pg-btn:hover:not(:disabled) { background: var(--accent); }
.pg-btn:disabled { opacity: .45; cursor: not-allowed; }
.pg-hint { margin-top: 12px; font-size: 12px; color: var(--dim); line-height: 1.7; }
.pg-results { margin-top: 14px; display: flex; flex-direction: column; gap: 10px; }
.pg-empty { font-size: 12.5px; color: var(--dim); padding: 6px 2px; }
.pg-hit { border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg); padding: 12px 14px; }
.pg-hit-head { display: flex; align-items: center; gap: 10px; }
.pg-rank { font-family: var(--mono); font-size: 11px; font-weight: 700; color: var(--accent); }
.pg-score { flex: 1; height: 5px; background: var(--surface-2); border-radius: var(--r-full); overflow: hidden; }
.pg-score-fill { height: 100%; background: linear-gradient(90deg, var(--pink), var(--accent)); border-radius: var(--r-full); transition: width .4s ease; }
.pg-score-num { font-family: var(--mono); font-size: 10.5px; color: var(--muted); width: 34px; text-align: right; }
.pg-doc { font-family: var(--mono); font-size: 10.5px; color: var(--dim); letter-spacing: .04em; }
.pg-snippet { margin-top: 9px; font-size: 12.5px; line-height: 1.75; color: var(--text); opacity: .88; word-break: break-word; }
.pg-ask {
  margin-top: 14px; border: 1px solid var(--pink); border-radius: var(--r-full);
  background: var(--pink-soft); color: var(--accent); font-size: 12.5px;
  padding: 9px 18px; cursor: pointer; transition: all .15s;
}
.pg-ask:hover { background: var(--pink); color: #141416; }

/* ---- 上传归类 chips ---- */
.up-cat-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 16px; }
.up-cat-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: .12em; color: var(--dim); }
.up-cat-chip {
  display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--bg); color: var(--muted);
  font-size: 12px; padding: 6px 13px; cursor: pointer; transition: all .15s;
}
.up-cat-chip:hover { border-color: var(--pink); color: var(--accent); }
.up-cat-chip.active { border-color: var(--pink); background: var(--pink-soft); color: var(--accent); font-weight: 600; }
.up-cat-ic { font-size: 12px; }
.up-hint { margin-top: 10px; font-size: 11.5px; color: var(--dim); }

/* ---- 分类筛选 chips + 文档分类色点 ---- */
.cat-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 14px; }
.cat-chip {
  display: inline-flex; align-items: center; gap: 7px;
  border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--surface); color: var(--muted);
  font-size: 12px; padding: 7px 14px; cursor: pointer; transition: all .15s;
}
.cat-chip:hover { border-color: var(--pink); color: var(--accent); }
.cat-chip.active { border-color: var(--pink); background: var(--pink-soft); color: var(--accent); font-weight: 600; }
.cat-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0; }

/* ---- 分块可视化面板 ---- */
.doc-item { border-bottom: 1px solid var(--line); }
.doc-row { border-bottom: none; }
.doc-chunks {
  border: none; background: transparent; color: var(--dim); font-family: var(--mono);
  font-size: 10.5px; letter-spacing: .08em; cursor: pointer; padding: 4px 8px;
  border-radius: var(--r-sm); transition: all .15s;
}
.doc-chunks:hover { color: var(--accent); background: var(--pink-soft); }
.chunk-panel { padding: 6px 4px 18px 52px; animation: fadeUp .25s ease both; }
.kb-pipe { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.kb-pipe-step {
  font-family: var(--mono); font-size: 10px; letter-spacing: .1em; color: var(--accent);
  border: 1px solid var(--pink); border-radius: var(--r-full); padding: 4px 12px; background: var(--pink-soft);
}
.kb-pipe-arrow { color: var(--dim); font-size: 11px; }
.chunk-loading { font-family: var(--mono); font-size: 11px; color: var(--dim); padding: 8px 0; }
.chunk-card { border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg); padding: 11px 14px; margin-bottom: 8px; }
.chunk-head { display: flex; align-items: center; gap: 10px; }
.chunk-idx { font-family: var(--mono); font-size: 11px; font-weight: 700; color: var(--accent); }
.chunk-chars { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .06em; }
.chunk-text {
  margin-top: 7px; font-size: 12px; line-height: 1.75; color: var(--muted);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  cursor: pointer; transition: all .2s;
}
.chunk-text.open { -webkit-line-clamp: unset; color: var(--text); }
</style>
