<script setup>
/* 画像页（2026-09-20 双栏改版）：左侧个人名片卡 + 右侧编辑表单
   功能：8 项字段（含学校/学习偏好/每周时长）、完整度进度、从对话提炼候选弹窗 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import PageHeader from './PageHeader.vue'
import { getProfile, updateProfile, extractProfile, updateAvatar } from '../api'

const props = defineProps({
  meta: { type: Object, required: true },
  // 登录账号（头像上传：图片压缩后经 /api/auth/avatar 落库）
  user: { type: Object, default: null }
})

const emit = defineEmits(['avatar-updated'])

const form = ref({
  nickname: '', major: '', grade: '', school: '',
  preferences: [], weekly_hours: 0, interests: [], goals: []
})
const stats = ref({ conversation_count: 0, memory_count: 0, doc_count: 0, top_agent: '—' })
const saving = ref(false)
const extracting = ref(false)

async function load() {
  try {
    const p = await getProfile()
    form.value = {
      nickname: p.nickname || '', major: p.major || '', grade: p.grade || '', school: p.school || '',
      preferences: p.preferences || [], weekly_hours: p.weekly_hours || 0,
      interests: p.interests || [], goals: p.goals || []
    }
    stats.value = p
  } catch (e) {
    ElMessage.error(e?.message || '画像加载失败')
  }
}

async function save() {
  saving.value = true
  try {
    await updateProfile(form.value)
    ElMessage.success('画像已保存，将在后续对话中注入各智能体')
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

/* ---- 头像上传：选图 -> canvas 压到 256px JPEG -> 落库 -> 通知上层刷新账号态 ---- */
const avatarInput = ref(null)
const uploadingAvatar = ref(false)

function pickAvatar() {
  avatarInput.value?.click()
}

function onAvatarChange(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  uploadingAvatar.value = true
  compressImage(file)
    .then(dataUrl => updateAvatar(dataUrl))
    .then(r => {
      ElMessage.success('头像已更新')
      emit('avatar-updated', r.avatar)
    })
    .catch(err => ElMessage.error(err?.message || '头像上传失败'))
    .finally(() => { uploadingAvatar.value = false })
}

/* 压到 256px 内的 JPEG（透明底先铺白），单张几十 KB，随账号存库无压力 */
function compressImage(file, size = 256) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const scale = Math.min(1, size / Math.max(img.width, img.height))
      const w = Math.max(1, Math.round(img.width * scale))
      const h = Math.max(1, Math.round(img.height * scale))
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, w, h)
      ctx.drawImage(img, 0, 0, w, h)
      URL.revokeObjectURL(url)
      resolve(canvas.toDataURL('image/jpeg', 0.85))
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('图片读取失败')) }
    img.src = url
  })
}

/* ---- chips 编辑（兴趣 / 目标 / 偏好共用） ---- */
function addTag(field, e) {
  const v = (e.target.value || '').trim()
  if (!v) return
  if (!form.value[field].includes(v)) form.value[field].push(v)
  e.target.value = ''
}
function delTag(field, i) {
  form.value[field].splice(i, 1)
}

/* ---- 画像完整度：8 项字段填写比例 ---- */
const completeness = computed(() => {
  const f = form.value
  const items = [
    f.nickname, f.major, f.grade, f.school,
    f.interests.length ? '1' : '', f.goals.length ? '1' : '',
    f.preferences.length ? '1' : '', f.weekly_hours > 0 ? '1' : ''
  ]
  return Math.round(items.filter(Boolean).length / 8 * 100)
})

/* ---- 从对话提炼候选（弹窗勾选合入，保存后生效） ---- */
const extractModal = ref(null)  // {interests:[], goals:[], scanned, memory_used, picked:{}}

async function runExtract() {
  extracting.value = true
  try {
    const r = await extractProfile()
    if (!r.interests.length && !r.goals.length) {
      ElMessage.info(`最近 ${r.scanned} 条对话没有提炼到新的画像信息，先去对话页聊几句吧`)
      return
    }
    const picked = {}
    for (const i of r.interests) picked[`i:${i}`] = true
    for (const g of r.goals) picked[`g:${g}`] = true
    extractModal.value = { ...r, picked }
  } catch (e) {
    ElMessage.error(e?.message || '提炼失败')
  } finally {
    extracting.value = false
  }
}

function mergePicked() {
  const m = extractModal.value
  let n = 0
  for (const key of Object.keys(m.picked)) {
    if (!m.picked[key]) continue
    const isInterest = key.startsWith('i:')
    const label = key.slice(2)
    const list = isInterest ? m.interests : m.goals
    if (!list.includes(label)) continue
    const target = isInterest ? form.value.interests : form.value.goals
    if (!target.includes(label)) { target.push(label); n++ }
  }
  extractModal.value = null
  ElMessage.success(`已合入 ${n} 条候选，点击「保存画像」后生效`)
}

onMounted(load)
</script>

<template>
  <section class="profile-view">
    <div class="page-wrap">
      <PageHeader v-bind="meta" />

      <!-- 统计条：对齐知识库页 4 格风格 -->
      <div class="stat-row">
        <div class="stat-cell"><div class="stat-num">{{ stats.conversation_count }}</div><div class="stat-label">累计对话</div></div>
        <div class="stat-cell"><div class="stat-num">{{ stats.memory_count }}</div><div class="stat-label">长期记忆</div></div>
        <div class="stat-cell"><div class="stat-num">{{ stats.doc_count }}</div><div class="stat-label">知识文档</div></div>
        <div class="stat-cell"><div class="stat-num">{{ stats.top_agent }}</div><div class="stat-label">最常用智能体</div></div>
      </div>

      <div class="profile-grid">
        <!-- 左：个人名片卡 -->
        <aside class="card">
          <div class="avatar" title="点击更换头像" @click="pickAvatar">
            <img v-if="user?.avatar" :src="user.avatar" alt="头像" />
            <template v-else>{{ (form.nickname || '同')[0] }}</template>
            <span class="avatar-edit">{{ uploadingAvatar ? '…' : '✎' }}</span>
          </div>
          <input ref="avatarInput" type="file" accept="image/*" hidden @change="onAvatarChange" />
          <div class="card-name">{{ form.nickname || '未设置昵称' }}</div>
          <div class="card-sub">{{ [form.major, form.grade].filter(Boolean).join(' · ') || '专业年级待填写' }}</div>
          <div v-if="form.school" class="card-school">{{ form.school }}</div>
          <div class="card-tags">
            <span v-if="!form.interests.length && !form.goals.length" class="card-empty">暂无标签，可在右侧添加</span>
            <span v-for="(t, i) in form.interests" :key="'i' + i" class="tag">{{ t }}</span>
            <span v-for="(g, i) in form.goals" :key="'g' + i" class="tag goal">{{ g }}</span>
          </div>
          <div class="complete">
            <div class="complete-head"><span>画像完整度</span><b>{{ completeness }}%</b></div>
            <div class="complete-bar"><div class="complete-fill" :style="{ width: completeness + '%' }"></div></div>
            <div class="complete-hint">越完整，智能体回答越贴合你</div>
          </div>
          <button class="btn-save" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存画像' }}</button>
          <button class="btn-extract" :disabled="extracting" @click="runExtract">{{ extracting ? '提炼中…' : '✦ 从对话提炼' }}</button>
        </aside>

        <!-- 右：编辑表单 -->
        <div class="form-col">
          <div class="sec-label">01 — 基础信息</div>
          <div class="grid-2">
            <label class="field"><span>昵称</span><input v-model="form.nickname" placeholder="怎么称呼你" /></label>
            <label class="field"><span>学校</span><input v-model="form.school" placeholder="如 华中科技大学" /></label>
            <label class="field"><span>专业</span><input v-model="form.major" placeholder="如 计算机科学与技术" /></label>
            <label class="field"><span>年级</span><input v-model="form.grade" placeholder="如 大三" /></label>
          </div>

          <div class="sec-label">02 — 兴趣方向</div>
          <div class="chip-box">
            <span v-for="(t, i) in form.interests" :key="i" class="chip">{{ t }}<b @click="delTag('interests', i)">×</b></span>
            <input class="chip-input" placeholder="输入后回车添加" @keydown.enter.prevent="addTag('interests', $event)" />
          </div>

          <div class="sec-label">03 — 当前目标</div>
          <div class="chip-box">
            <span v-for="(g, i) in form.goals" :key="i" class="chip">{{ g }}<b @click="delTag('goals', i)">×</b></span>
            <input class="chip-input" placeholder="输入后回车添加" @keydown.enter.prevent="addTag('goals', $event)" />
          </div>

          <div class="sec-label">04 — 学习偏好</div>
          <div class="chip-box">
            <span v-for="(p, i) in form.preferences" :key="i" class="chip">{{ p }}<b @click="delTag('preferences', i)">×</b></span>
            <input class="chip-input" placeholder="如 喜欢例子驱动 / 回答要简洁，回车添加" @keydown.enter.prevent="addTag('preferences', $event)" />
          </div>

          <div class="sec-label">05 — 每周可投入时间</div>
          <div class="hours-row">
            <input v-model.number="form.weekly_hours" type="number" min="0" max="168" class="hours-input" />
            <span class="hours-unit">小时 / 周</span>
            <span class="hours-hint">智能体会按你的时间预算调整规划粒度</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 提炼候选弹窗 -->
    <div v-if="extractModal" class="pv-mask" @click.self="extractModal = null">
      <div class="pv-card">
        <div class="pv-head">
          <div class="pv-head-info">
            <div class="pv-title">提炼候选 · 画像生长</div>
            <div class="pv-meta">扫描最近 {{ extractModal.scanned }} 条对话 + {{ extractModal.memory_used }} 条长期记忆</div>
          </div>
          <button class="pv-close" title="关闭" @click="extractModal = null">×</button>
        </div>
        <div class="pv-body">
          <div v-if="extractModal.interests.length" class="pv-group">
            <div class="pv-group-label">兴趣方向</div>
            <label v-for="i in extractModal.interests" :key="'i' + i" class="pick">
              <input v-model="extractModal.picked['i:' + i]" type="checkbox" /><span>{{ i }}</span>
            </label>
          </div>
          <div v-if="extractModal.goals.length" class="pv-group">
            <div class="pv-group-label">当前目标</div>
            <label v-for="g in extractModal.goals" :key="'g' + g" class="pick">
              <input v-model="extractModal.picked['g:' + g]" type="checkbox" /><span>{{ g }}</span>
            </label>
          </div>
        </div>
        <div class="pv-foot">
          <button class="btn-save" @click="mergePicked">合入表单</button>
          <span class="pv-foot-hint">合入后需点击「保存画像」生效</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.profile-view { flex: 1; overflow-y: auto; min-height: 0; }
.page-wrap { max-width: 1080px; width: 100%; margin: 0 auto; padding: 44px 36px 60px; animation: fadeUp .45s ease both; }

/* 统计条（对齐知识库页） */
.stat-row { display: flex; gap: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin-top: 34px; }
.stat-cell { flex: 1; padding: 20px 8px; text-align: center; min-width: 0; }
.stat-cell + .stat-cell { border-left: 1px solid var(--line); }
.stat-num { font-family: var(--mono); font-size: 24px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat-label { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; margin-top: 6px; text-transform: uppercase; }

/* 双栏：左名片卡 + 右编辑表单 */
.profile-grid { display: grid; grid-template-columns: 280px 1fr; gap: 32px; margin-top: 36px; align-items: start; }
.card {
  position: sticky; top: 20px;
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 26px 22px; text-align: center;
}
.avatar {
  width: 64px; height: 64px; margin: 0 auto 12px;
  border-radius: 50%; background: var(--pink-soft); border: 1.5px solid var(--pink);
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; font-weight: 800; color: var(--accent);
  cursor: pointer; position: relative; overflow: visible;
  transition: transform .15s ease, box-shadow .15s ease;
}
.avatar:hover { transform: scale(1.04); box-shadow: var(--shadow); }
.avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; display: block; }
.avatar-edit {
  position: absolute; right: -2px; bottom: -2px;
  width: 20px; height: 20px; border-radius: 50%;
  background: var(--pink); color: #141416;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; border: 1.5px solid var(--bg);
}
.card-name { font-size: 17px; font-weight: 800; color: var(--text); }
.card-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
.card-school { font-family: var(--mono); font-size: 10px; letter-spacing: .12em; color: var(--dim); margin-top: 6px; }
.card-tags { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin: 16px 0 4px; min-height: 24px; }
.tag { font-size: 11px; padding: 3px 10px; border-radius: var(--r-full); background: var(--pink-soft); color: var(--accent); font-weight: 600; }
.tag.goal { background: var(--surface-2); color: var(--muted); border: 1px solid var(--line); }
.card-empty { font-size: 11.5px; color: var(--dim); }
.complete { text-align: left; margin: 18px 0 16px; }
.complete-head { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--muted); }
.complete-head b { font-family: var(--mono); color: var(--accent); }
.complete-bar { height: 5px; background: var(--surface-2); border-radius: var(--r-full); overflow: hidden; margin-top: 7px; }
.complete-fill { height: 100%; background: var(--pink); border-radius: var(--r-full); transition: width .3s ease; }
.complete-hint { font-size: 10.5px; color: var(--dim); margin-top: 6px; }
.btn-save {
  width: 100%; padding: 12px; border: none; border-radius: var(--r-full);
  background: var(--text); color: #fff; font-size: 13.5px; font-weight: 700;
  cursor: pointer; transition: all .2s;
}
.btn-save:hover:not(:disabled) { background: var(--accent); }
.btn-save:disabled { opacity: .5; cursor: not-allowed; }
.btn-extract {
  width: 100%; padding: 11px; margin-top: 9px;
  border: 1px solid var(--line); border-radius: var(--r-full);
  background: var(--bg); color: var(--muted); font-size: 12.5px; font-weight: 600;
  cursor: pointer; transition: all .2s;
}
.btn-extract:hover:not(:disabled) { border-color: var(--pink); color: var(--accent); background: var(--pink-soft); }
.btn-extract:disabled { opacity: .5; cursor: not-allowed; }

/* 右侧表单 */
.sec-label { font-family: var(--mono); font-size: 10.5px; letter-spacing: .16em; color: var(--dim); margin: 26px 0 12px; text-transform: uppercase; }
.sec-label:first-child { margin-top: 4px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 26px; }
.field { display: flex; flex-direction: column; gap: 7px; }
.field span { font-size: 12px; color: var(--muted); }
.field input {
  border: none; border-bottom: 1px solid var(--line); background: transparent;
  padding: 7px 2px; font-size: 14px; color: var(--text); outline: none; transition: border-color .15s;
}
.field input:focus { border-color: var(--pink); }
.chip-box {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  background: var(--surface); border-radius: var(--r-md);
  padding: 12px 14px; min-height: 48px;
}
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--pink-soft); color: var(--accent);
  font-size: 12.5px; font-weight: 600; padding: 5px 11px; border-radius: var(--r-full);
}
.chip b { cursor: pointer; font-weight: 400; opacity: .6; }
.chip b:hover { opacity: 1; }
.chip-input { flex: 1; min-width: 120px; border: none; background: transparent; outline: none; font-size: 13px; color: var(--text); }
.hours-row { display: flex; align-items: center; gap: 10px; }
.hours-input {
  width: 90px; border: 1px solid var(--line); border-radius: var(--r-sm);
  padding: 9px 12px; font-size: 14px; font-family: var(--mono);
  color: var(--text); outline: none; background: var(--bg); transition: border-color .15s;
}
.hours-input:focus { border-color: var(--pink); }
.hours-unit { font-size: 13px; color: var(--text); font-weight: 600; }
.hours-hint { font-size: 11.5px; color: var(--dim); }

/* 提炼候选弹窗（复用知识库预览弹层风格） */
.pv-mask {
  position: fixed; inset: 0; background: rgba(20, 20, 22, .45); backdrop-filter: blur(3px);
  display: flex; align-items: center; justify-content: center; z-index: 200;
  animation: fadeUp .2s ease both;
}
.pv-card { width: 460px; max-width: calc(100vw - 48px); max-height: 76vh; display: flex; flex-direction: column; background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-lg); box-shadow: var(--shadow-hover); overflow: hidden; }
.pv-head { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid var(--line); }
.pv-title { font-size: 15px; font-weight: 800; color: var(--text); }
.pv-meta { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .08em; margin-top: 4px; }
.pv-close { border: none; background: transparent; font-size: 20px; color: var(--dim); cursor: pointer; line-height: 1; }
.pv-close:hover { color: var(--accent); }
.pv-body { padding: 18px 22px; overflow-y: auto; flex: 1; }
.pv-group { margin-bottom: 16px; }
.pv-group-label { font-family: var(--mono); font-size: 10px; letter-spacing: .14em; color: var(--dim); margin-bottom: 9px; text-transform: uppercase; }
.pick { display: flex; align-items: center; gap: 10px; padding: 8px 2px; font-size: 13.5px; color: var(--text); cursor: pointer; }
.pick input { accent-color: var(--accent); width: 15px; height: 15px; }
.pv-foot { display: flex; align-items: center; gap: 14px; padding: 14px 22px; border-top: 1px solid var(--line); }
.pv-foot .btn-save { width: auto; padding: 10px 26px; font-size: 13px; }
.pv-foot-hint { font-size: 11px; color: var(--dim); }

/* 窄屏：双栏改单栏，名片卡取消吸顶 */
@media (max-width: 1100px) {
  .profile-grid { grid-template-columns: 1fr; }
  .card { position: static; }
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
