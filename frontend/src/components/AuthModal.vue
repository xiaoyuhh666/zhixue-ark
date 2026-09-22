<script setup>
/* 登录 / 注册弹窗：落地页所有「进入平台」入口统一触发的账号门禁。
   白粉视觉：遮罩模糊 + 白卡圆角 + 黑胶囊主按钮，登录/注册双 Tab 切换 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import { loginUser, registerUser } from '../api'

const emit = defineEmits(['close', 'success'])

const mode = ref('login')       // 'login' | 'register'
const username = ref('')
const nickname = ref('')
const password = ref('')
const showPwd = ref(false)      // 密码明文切换（小眼睛）
const busy = ref(false)

function switchMode(m) {
  mode.value = m
}

async function submit() {
  if (busy.value) return
  const u = username.value.trim()
  if (!u || !password.value) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  busy.value = true
  try {
    const data = mode.value === 'login'
      ? await loginUser({ username: u, password: password.value })
      : await registerUser({ username: u, password: password.value, nickname: nickname.value })
    ElMessage.success(mode.value === 'login' ? `欢迎回来，${data.user.nickname}` : `注册成功，${data.user.nickname}`)
    emit('success', { token: data.token, ...data.user })
  } catch (e) {
    ElMessage.error(e?.message || '请求失败，请稍后再试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth-mask" @click.self="emit('close')">
    <div class="auth-card">
      <button class="auth-close" @click="emit('close')" aria-label="关闭">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>

      <div class="auth-logo">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.7L20 10l-6.1 1.3L12 17l-1.9-5.7L4 10l6.1-1.3z"/></svg>
      </div>
      <div class="auth-title">{{ mode === 'login' ? '欢迎回来' : '创建你的账号' }}</div>
      <div class="auth-sub">智学方舟 · 一艘方舟，五域专家</div>

      <!-- 登录 / 注册切换胶囊 -->
      <div class="auth-tabs">
        <button class="auth-tab" :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button>
        <button class="auth-tab" :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <label class="auth-field">
          <span>用户名</span>
          <input v-model="username" type="text" placeholder="3~24 个字符" autocomplete="username" />
        </label>
        <label v-if="mode === 'register'" class="auth-field">
          <span>昵称 <i>选填</i></span>
          <input v-model="nickname" type="text" placeholder="智能体怎么称呼你？" autocomplete="off" />
        </label>
        <label class="auth-field">
          <span>密码</span>
          <div class="pwd-wrap">
            <input
              v-model="password"
              :type="showPwd ? 'text' : 'password'"
              :placeholder="mode === 'register' ? '至少 6 位' : '输入密码'"
              autocomplete="current-password"
            />
            <button type="button" class="pwd-eye" @click="showPwd = !showPwd" tabindex="-1" :aria-label="showPwd ? '隐藏密码' : '显示密码'">
              <svg v-if="showPwd" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
            </button>
          </div>
        </label>
        <button type="submit" class="auth-submit" :disabled="busy">
          {{ busy ? '请稍候…' : (mode === 'login' ? '登录，进入方舟' : '注册并进入') }}
        </button>
      </form>

      <div class="auth-foot">{{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
        <button class="auth-link" @click="switchMode(mode === 'login' ? 'register' : 'login')">
          {{ mode === 'login' ? '立即注册' : '去登录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-mask {
  position: fixed; inset: 0; z-index: 2000;
  background: rgba(30, 24, 26, .42);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
  animation: am-in .18s ease both;
}
@keyframes am-in { from { opacity: 0; } to { opacity: 1; } }

.auth-card {
  position: relative; width: 400px; max-width: calc(100vw - 40px);
  background: #fff; border: 1px solid var(--line);
  border-radius: 24px; padding: 34px 34px 26px;
  box-shadow: 0 32px 80px rgba(60, 30, 40, .18);
  animation: ac-in .26s cubic-bezier(.22, 1, .36, 1) both;
}
@keyframes ac-in { from { opacity: 0; transform: translateY(16px) scale(.97); } to { opacity: 1; transform: none; } }

.auth-close {
  position: absolute; top: 16px; right: 16px;
  width: 32px; height: 32px; border-radius: 50%;
  border: 1px solid var(--line); background: #fff; color: var(--muted);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  transition: all .15s;
}
.auth-close:hover { color: var(--text); border-color: var(--pink); }

.auth-logo {
  width: 42px; height: 42px; border-radius: 13px;
  background: var(--pink-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 16px;
}
.auth-title { font-size: 22px; font-weight: 800; letter-spacing: -.01em; }
.auth-sub { font-size: 12px; color: var(--muted); margin: 6px 0 20px; }

.auth-tabs {
  display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-full); padding: 4px; margin-bottom: 20px;
}
.auth-tab {
  height: 34px; border: none; border-radius: var(--r-full);
  background: transparent; font-size: 13px; font-weight: 700; color: var(--muted);
  cursor: pointer; transition: all .18s;
}
.auth-tab.active { background: #fff; color: var(--text); box-shadow: 0 2px 8px rgba(60, 30, 40, .08); }

.auth-form { display: flex; flex-direction: column; gap: 14px; }
.auth-field { display: flex; flex-direction: column; gap: 6px; }
.auth-field span { font-size: 12px; font-weight: 700; color: var(--text); }
.auth-field i { font-style: normal; font-weight: 400; color: var(--dim); font-size: 11px; }
.auth-field input {
  height: 42px; border: 1px solid var(--line); border-radius: 12px;
  padding: 0 14px; font-size: 14px; color: var(--text); background: #fff;
  outline: none; transition: border-color .15s, box-shadow .15s;
}
.auth-field input:focus { border-color: var(--pink); box-shadow: 0 0 0 3px var(--pink-soft); }

/* 密码框：小眼睛明文切换（input 右侧留出按钮位） */
.pwd-wrap { position: relative; }
.pwd-wrap input { width: 100%; padding-right: 44px; }
.pwd-eye {
  position: absolute; right: 6px; top: 50%; translate: 0 -50%;
  width: 32px; height: 32px; border: none; border-radius: 50%;
  background: transparent; color: var(--dim); cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: color .15s;
}
.pwd-eye:hover { color: var(--text); }

.auth-submit {
  height: 44px; border: none; border-radius: var(--r-full);
  background: var(--text); color: #fff; font-size: 14px; font-weight: 700;
  cursor: pointer; margin-top: 6px; transition: all .18s;
}
/* 黑→深粉 hover：对齐落地页黑胶囊定稿模式（.btn-send 同款） */
.auth-submit:hover { background: var(--accent); transform: translateY(-1px); box-shadow: 0 10px 24px rgba(214, 67, 127, .28); }
.auth-submit:disabled { opacity: .6; cursor: wait; transform: none; }

.auth-foot { margin-top: 18px; text-align: center; font-size: 12.5px; color: var(--muted); }
.auth-link {
  border: none; background: none; color: var(--accent);
  font-size: 12.5px; font-weight: 700; cursor: pointer; padding: 0 2px;
}
.auth-link:hover { text-decoration: underline; }
</style>
