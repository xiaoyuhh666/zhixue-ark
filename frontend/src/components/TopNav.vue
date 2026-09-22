<script setup>
/* 顶部横向导航（DiceBear Playground 风格）：品牌 + 视图导航 + 状态/用户区
   2026-09-20 信息架构重组：5 个高频工作面 + 用户下拉卡（个人中心入口） */
import { onBeforeUnmount, onMounted, ref, computed } from 'vue'
import { getProfile } from '../api'

const props = defineProps({
  view: { type: String, default: 'chat' },
  // 登录账号（auth 用户）：右上角用户卡优先展示账号昵称/用户名，与注册信息一致
  user: { type: Object, default: null }
})

const emit = defineEmits(['switch', 'open-account', 'logout', 'home'])

const NAV = [
  { key: 'chat', num: '01', label: '智能对话' },
  { key: 'knowledge', num: '02', label: '知识库' },
  { key: 'plans', num: '03', label: '任务计划' },
  { key: 'insights', num: '04', label: '学习足迹' },
  { key: 'models', num: '05', label: '模型广场' }
]

/* 用户下拉卡：名字可点击，展示画像摘要 + 个人中心入口 */
const userOpen = ref(false)
const userCard = ref(null)
const profile = ref({ nickname: '同学', school: '', major: '', grade: '' })

/* 展示名：登录账号昵称 > 用户名 > 画像昵称（与注册信息一致） */
const displayName = computed(
  () => props.user?.nickname || props.user?.username || profile.value.nickname || '同学'
)

function onDocClick(e) {
  if (userOpen.value && userCard.value && !userCard.value.contains(e.target)) {
    userOpen.value = false
  }
}
onMounted(async () => {
  document.addEventListener('click', onDocClick)
  try {
    const p = await getProfile()
    profile.value = p
  } catch { /* 下拉卡加载失败不影响导航 */ }
})
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <header class="topnav">
    <!-- 品牌：点击 logo 区回落地页（用户在红框处要求的返回交互） -->
    <button class="brand" title="返回产品首页" @click="emit('home')">
      <div class="brand-logo">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.7L20 10l-6.1 1.3L12 17l-1.9-5.7L4 10l6.1-1.3z"/></svg>
      </div>
      <div class="brand-text">
        <div class="brand-name">智学方舟®</div>
        <div class="brand-sub">CAMPUS MULTI-AGENT OS</div>
      </div>
    </button>

    <!-- 视图导航 -->
    <nav class="nav-links">
      <button
        v-for="item in NAV"
        :key="item.key"
        class="nav-link"
        :class="{ active: view === item.key }"
        @click="emit('switch', item.key)"
      >
        <span class="num">{{ item.num }}</span>{{ item.label }}
      </button>
    </nav>

    <!-- 右侧状态区 -->
    <div class="topnav-right">
      <!-- 用户卡：点击展开下拉，进入个人中心 -->
      <div ref="userCard" class="user-wrap">
        <button class="user-mini" :class="{ open: userOpen }" @click="userOpen = !userOpen">
          <div class="user-avatar">{{ displayName[0] }}</div>
          <span class="user-name">{{ displayName }}</span>
          <svg class="chev" :class="{ up: userOpen }" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
        </button>
        <div v-if="userOpen" class="user-drop">
          <div class="ud-head">
            <div class="ud-avatar">{{ displayName[0] }}</div>
            <div class="ud-info">
              <div class="ud-name">{{ displayName }}</div>
              <div class="ud-sub">{{ [profile.major, profile.grade].filter(Boolean).join(' · ') || '画像待完善' }}</div>
            </div>
          </div>
          <button class="ud-item" @click="userOpen = false; emit('open-account')">
            <span>个人中心</span>
            <span class="ud-hint">画像 · 记忆 · 统计 · 设置</span>
            <span class="ud-arrow">→</span>
          </button>
          <!-- 退出登录：清账号态并回落地页 -->
          <button class="ud-item ud-logout" @click="userOpen = false; emit('logout')">
            <span>退出登录</span>
            <span class="ud-arrow">⏻</span>
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topnav {
  height: 60px; flex-shrink: 0;
  display: flex; align-items: center; gap: 26px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: var(--bg);
}
/* 品牌（迁移自 Sidebar.brand） */
/* 品牌（迁移自 Sidebar.brand）：整体为返回落地页的可点按钮，hover 微浮起提示可点 */
button.brand {
  display: flex; align-items: center; gap: 11px; flex-shrink: 0;
  background: none; border: 0; padding: 0; text-align: left;
  cursor: pointer; border-radius: var(--r-sm);
  transition: transform .18s ease, opacity .18s ease;
}
button.brand:hover { transform: translateY(-1px); opacity: .82; }
button.brand:active { transform: translateY(0); opacity: .95; }
.brand-logo {
  width: 34px; height: 34px; flex-shrink: 0;
  background: var(--pink); color: #141416;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-sm);
  box-shadow: var(--shadow);
}
.brand-name { font-size: 17px; font-weight: 800; letter-spacing: -.02em; color: var(--text); }
.brand-sub {
  font-family: var(--mono); font-size: 9px; color: var(--dim);
  letter-spacing: .2em; margin-top: 2px; white-space: nowrap;
}
/* 视图导航：胶囊链接，激活态粉底深粉字 */
.nav-links { display: flex; align-items: center; gap: 4px; }
.nav-link {
  display: flex; align-items: center; gap: 7px;
  padding: 8px 15px; border: none; background: transparent;
  font-size: 13px; color: var(--muted); cursor: pointer;
  border-radius: var(--r-full); transition: all .15s;
  white-space: nowrap;
}
.nav-link .num { font-family: var(--mono); font-size: 10px; color: var(--dim); letter-spacing: .1em; }
.nav-link:hover { color: var(--text); background: var(--surface); }
.nav-link.active { color: var(--accent); background: var(--pink-soft); font-weight: 600; }
.nav-link.active .num { color: var(--accent); }
/* 右侧状态区 */
.topnav-right { margin-left: auto; display: flex; align-items: center; gap: 14px; }
/* 用户卡 + 下拉 */
.user-wrap { position: relative; }
.user-mini {
  display: flex; align-items: center; gap: 9px;
  border: none; background: transparent; cursor: pointer;
  padding: 5px 9px; border-radius: var(--r-full); transition: background .15s;
}
.user-mini:hover, .user-mini.open { background: var(--surface); }
.user-avatar {
  width: 32px; height: 32px; flex-shrink: 0;
  background: var(--pink-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-full); font-weight: 700; font-size: 13px;
}
.user-name { font-size: 12.5px; font-weight: 700; color: var(--text); white-space: nowrap; }
.chev { color: var(--dim); transition: transform .2s; }
.chev.up { transform: rotate(180deg); }
.user-drop {
  position: absolute; top: calc(100% + 10px); right: 0; width: 240px;
  background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-md);
  box-shadow: var(--shadow-hover); overflow: hidden; z-index: 90;
  animation: fadeUp .2s ease both;
}
.ud-head { display: flex; align-items: center; gap: 12px; padding: 16px; border-bottom: 1px solid var(--line); }
.ud-avatar {
  width: 40px; height: 40px; flex-shrink: 0;
  background: var(--pink-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-full); font-weight: 800; font-size: 16px;
  border: 1.5px solid var(--pink);
}
.ud-name { font-size: 14px; font-weight: 800; color: var(--text); }
.ud-sub { font-size: 11px; color: var(--dim); margin-top: 3px; }
.ud-item {
  width: 100%; display: flex; align-items: center; gap: 10px;
  padding: 13px 16px; border: none; background: transparent;
  cursor: pointer; text-align: left; transition: background .15s;
}
.ud-item:hover { background: var(--pink-soft); }
.ud-item span:first-child { font-size: 13px; font-weight: 700; color: var(--text); }
.ud-item:hover span:first-child { color: var(--accent); }
.ud-hint { font-size: 10px; color: var(--dim); }
.ud-arrow { margin-left: auto; color: var(--dim); font-family: var(--mono); }
.ud-item.ud-logout { color: #d4455a; }
.ud-item.ud-logout:hover { background: #fdf2f4; }
/* 窄屏收紧间距并隐藏次要信息，保导航可用 */
@media (max-width: 1100px) {
  .topnav { gap: 14px; padding: 0 16px; }
  .nav-link { padding: 8px 10px; }
  .nav-link .num { display: none; }
  .brand-sub { display: none; }
  .ud-hint { display: none; }
}
</style>
