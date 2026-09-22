<script setup>
// meta 中混有顶栏用的 title/badge 等字段，本组件只用四个页头字段，
// 关闭 attrs 透传避免 "Extraneous non-props attributes" 警告
defineOptions({ inheritAttrs: false })

defineProps({
  kicker: String,
  title: String,
  en: String,
  desc: String
})
</script>

<template>
  <div class="page-kicker">{{ kicker }}</div>
  <h1 class="display">{{ title }}<span class="display-en">{{ en }}</span></h1>
  <p class="page-desc">{{ desc }}</p>
</template>

<style scoped>
.page-kicker {
  font-family: var(--mono); font-size: 10.5px; color: var(--accent);
  letter-spacing: .28em; margin-bottom: 14px; text-transform: uppercase;
}
.display {
  font-size: clamp(34px, 4.6vw, 52px); font-weight: 800;
  letter-spacing: -.03em; line-height: 1.05; margin-bottom: 16px;
}
.display-en {
  display: block; font-family: var(--mono); font-size: 12px; font-weight: 400;
  color: var(--dim); letter-spacing: .3em; margin-top: 12px;
}
.page-desc { color: var(--muted); font-size: 13.5px; max-width: 560px; line-height: 1.8; }
</style>
