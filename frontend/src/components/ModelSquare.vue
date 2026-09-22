<script setup>
/* 模型广场（2026-09-21 新增一级模块）：展示已接入的三家 LLM 供应商
   目录元数据（MODEL_CATALOG）+ 实时接入状态（已配置/未接入/实测延迟）；
   设为默认与测试连通复用 settings 接口，与个人中心数据同源 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import PageHeader from './PageHeader.vue'
import { getModelSquare, updateSettings, testSettingsKey } from '../api'

const props = defineProps({
  meta: { type: Object, required: true }
})

const emit = defineEmits(['navigate'])

const data = ref({ models: [], default_provider: 'deepseek', configured_count: 0 })
const loading = ref(true)
/* 测试状态：{ [provider]: { status: 'testing'|'ok'|'fail', text, latency_ms } } */
const testState = ref({})
/* 设为默认进行中的 provider（按钮 loading） */
const settingP = ref('')

function badgeOf(m) {
  if (data.value.default_provider === m.provider) return { text: '默认使用中', cls: 'default' }
  if (m.configured) return { text: '已接入', cls: 'ok' }
  return { text: '未接入', cls: 'demo' }
}

async function load() {
  try {
    data.value = await getModelSquare()
  } catch (e) {
    ElMessage.error(e?.message || '模型广场加载失败')
  } finally {
    loading.value = false
  }
}

/* 设为默认：写 default_provider，运行时立即生效（与个人中心设置同源） */
async function setDefault(provider) {
  settingP.value = provider
  try {
    await updateSettings({ default_provider: provider })
    ElMessage.success(`默认模型已切换为 ${provider.toUpperCase()}，立即生效`)
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '切换失败')
  } finally {
    settingP.value = ''
  }
}

/* 测试连通：用当前生效 Key 发最小请求；延迟回显到卡片 */
async function testKey(provider) {
  testState.value = { ...testState.value, [provider]: { status: 'testing', text: '测试中…' } }
  try {
    const r = await testSettingsKey(provider)
    testState.value = {
      ...testState.value,
      [provider]: r.ok
        ? { status: 'ok', text: `✓ 连通正常 · ${r.model}`, latency_ms: r.latency_ms }
        : { status: 'fail', text: `✗ ${r.error}` },
    }
  } catch (e) {
    testState.value = { ...testState.value, [provider]: { status: 'fail', text: `✗ ${e?.message || '请求失败'}` } }
  }
}

onMounted(load)
</script>

<template>
  <section class="models-view">
    <div class="page-wrap">
      <PageHeader v-bind="meta" />

      <!-- 接入概览条 -->
      <div class="overview">
        <div class="ov-item">
          <span class="ov-label">已接入</span>
          <span class="ov-num">{{ data.configured_count }} / {{ data.models.length }}</span>
          <span class="ov-unit">家</span>
        </div>
        <div class="ov-item">
          <span class="ov-label">当前默认</span>
          <span class="ov-chip">{{ (data.models.find(m => m.provider === data.default_provider) || {}).name || data.default_provider }}</span>
        </div>
        <span class="ov-hint">OPENAI-COMPATIBLE · RUNTIME HOT-SWAP</span>
      </div>

      <!-- 供应商卡片 -->
      <div class="sq-grid" :class="{ loading }">
        <article v-for="m in data.models" :key="m.provider" class="sq-card" :class="{ 'is-default': data.default_provider === m.provider }">
          <div class="sq-head">
            <div class="logo-mark">{{ m.logo }}</div>
            <span class="state-badge" :class="badgeOf(m).cls">{{ badgeOf(m).text }}</span>
          </div>
          <div class="sq-name">{{ m.name }}</div>
          <div class="sq-model mono">{{ m.model }}</div>

          <!-- 规格行 -->
          <div class="spec">
            <div class="spec-row"><span class="spec-label">上下文窗口</span><span class="spec-val">{{ m.context }}</span></div>
            <div class="spec-row"><span class="spec-label">输出方式</span><span class="spec-val">{{ m.streaming ? '流式 SSE' : '同步' }}</span></div>
            <div class="spec-row"><span class="spec-label">工具调用</span><span class="spec-val">{{ m.function_calling ? 'Function Calling' : '不支持' }}</span></div>
            <div class="spec-row">
              <span class="spec-label">实测延迟</span>
              <span v-if="testState[m.provider]" class="spec-val mono lat" :class="testState[m.provider].status">
                {{ testState[m.provider].status === 'ok' ? `${testState[m.provider].latency_ms} ms` : testState[m.provider].text }}
              </span>
              <span v-else-if="m.latency_ms != null" class="spec-val mono lat ok">{{ m.latency_ms }} ms</span>
              <span v-else class="spec-val mono lat idle">待测试</span>
            </div>
          </div>

          <!-- 测试结果说明行（失败原因等） -->
          <div v-if="testState[m.provider] && testState[m.provider].status === 'fail'" class="test-fail">
            {{ testState[m.provider].text }}
          </div>

          <!-- 操作行 -->
          <div class="btn-row">
            <button
              class="btn primary"
              :disabled="data.default_provider === m.provider || settingP === m.provider"
              @click="setDefault(m.provider)"
            >{{ data.default_provider === m.provider ? '当前默认' : (settingP === m.provider ? '切换中…' : '设为默认') }}</button>
            <button
              class="btn"
              :disabled="testState[m.provider]?.status === 'testing'"
              @click="testKey(m.provider)"
            >{{ testState[m.provider]?.status === 'testing' ? '测试中…' : '测试连通' }}</button>
          </div>
        </article>
      </div>

      <!-- 底部入口：去个人中心配置密钥 -->
      <div class="foot-bar">
        <span class="mono">填入 API 密钥即接入真实调用 · 密钥管理集中在个人中心</span>
        <button class="foot-link" @click="emit('navigate', 'account/settings')">前往个人中心管理密钥 →</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.models-view { flex: 1; overflow-y: auto; min-height: 0; }
.page-wrap { max-width: 1080px; width: 100%; margin: 0 auto; padding: 44px 36px 60px; animation: fadeUp .45s ease both; }

/* 概览条：灰底横条 + 默认模型粉胶囊 */
.overview {
  display: flex; align-items: center; flex-wrap: wrap; gap: 10px 26px;
  margin-top: 34px; padding: 16px 22px;
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md);
}
.ov-item { display: flex; align-items: center; gap: 9px; }
.ov-label { font-size: 12.5px; color: var(--muted); }
.ov-num { font-size: 21px; font-weight: 800; color: var(--text); letter-spacing: -.02em; }
.ov-unit { font-size: 12px; color: var(--dim); }
.ov-chip {
  padding: 4px 13px; border-radius: var(--r-full);
  background: var(--pink-soft); color: var(--accent);
  font-size: 12.5px; font-weight: 700;
}
.ov-hint { margin-left: auto; font-family: var(--mono); font-size: 9.5px; letter-spacing: .14em; color: var(--dim); }

/* 卡片网格 */
.sq-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; margin-top: 22px; }
.sq-grid.loading { opacity: .45; pointer-events: none; }
.sq-card {
  display: flex; flex-direction: column; min-width: 0;
  background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 22px; box-shadow: var(--shadow);
  transition: transform .25s ease, border-color .25s ease, box-shadow .25s ease;
}
/* 项目惯例：hover 上浮 + 粉描边 */
.sq-card:hover { transform: translateY(-4px); border-color: var(--pink); box-shadow: var(--shadow-hover); }
.sq-card.is-default { border-color: var(--pink); }

.sq-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.logo-mark {
  width: 42px; height: 42px; flex-shrink: 0;
  background: var(--text); color: var(--bg);
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-sm); font-family: var(--mono); font-size: 18px; font-weight: 800;
}
.state-badge { padding: 4px 11px; border-radius: var(--r-full); font-size: 11px; font-weight: 700; white-space: nowrap; }
.state-badge.default { background: var(--pink-soft); color: var(--accent); }
.state-badge.ok { background: var(--bg); color: var(--text); border: 1px solid var(--line); }
.state-badge.demo { background: var(--surface); color: var(--dim); border: 1px solid var(--line); }

.sq-name { margin-top: 15px; font-size: 16.5px; font-weight: 800; color: var(--text); letter-spacing: -.01em; }
.sq-model { margin-top: 5px; font-size: 11px; color: var(--dim); letter-spacing: .02em; }

/* 规格行：分割线 + 右对齐值 */
.spec { margin-top: 16px; border-top: 1px solid var(--line); }
.spec-row {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  min-height: 40px; border-bottom: 1px solid var(--line);
}
.spec-label { font-size: 12px; color: var(--muted); }
.spec-val { font-size: 12.5px; font-weight: 600; color: var(--text); }
.spec-val.lat.idle { color: var(--dim); font-weight: 400; }
.spec-val.lat.ok { color: var(--accent); }
.spec-val.lat.testing { color: var(--dim); font-weight: 400; }

/* 失败说明行 */
.test-fail { margin-top: 12px; font-size: 11.5px; color: var(--accent); background: var(--pink-soft); border-radius: var(--r-sm); padding: 8px 12px; }

/* 操作行：黑胶囊主按钮 + 灰描边次按钮（对齐 auth-submit/btn-send 定稿模式） */
.btn-row { display: flex; gap: 9px; margin-top: 18px; }
.btn {
  flex: 1; min-height: 36px; padding: 0 12px;
  border-radius: var(--r-full); font-size: 12.5px; font-weight: 700;
  cursor: pointer; transition: all .18s ease;
  border: 1px solid var(--line); background: var(--bg); color: var(--text);
}
.btn:hover:not(:disabled) { border-color: var(--pink); color: var(--accent); }
.btn:disabled { cursor: default; opacity: .9; }
.btn.primary { background: var(--text); border-color: var(--text); color: #fff; }
.btn.primary:hover:not(:disabled) { background: var(--accent); border-color: var(--accent); color: #fff; box-shadow: 0 6px 18px rgba(214, 67, 127, .28); }
.btn.primary:disabled { background: var(--accent); border-color: var(--accent); color: #fff; }

/* 底部入口条 */
.foot-bar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 10px 18px;
  margin-top: 22px; padding: 15px 22px;
  border: 1px dashed var(--line); border-radius: var(--r-md);
}
.foot-bar > .mono { font-size: 11px; color: var(--dim); letter-spacing: .04em; }
.foot-link {
  margin-left: auto; border: none; background: none; cursor: pointer;
  font-size: 12.5px; font-weight: 700; color: var(--accent);
  transition: opacity .15s;
}
.foot-link:hover { opacity: .72; }

@media (max-width: 900px) {
  .sq-grid { grid-template-columns: 1fr; }
  .ov-hint { display: none; }
  .page-wrap { padding: 30px 18px 48px; }
}
</style>
