<script setup>
/* 02 区能力画廊：双排反向跑马灯（参考 DiceBear 风格画廊），纯展示不可玩，
   hover 整排暂停 + 卡片上浮；边缘渐隐遮罩 */
const ROW_TOP = [
  { icon: '✦', name: 'Supervisor 调度', desc: '识别意图，分派任务', tag: 'INTENT · PLAN' },
  { icon: '⬡', name: '多智能体协作', desc: '五位专家顺序接力', tag: 'PIPELINE' },
  { icon: '◈', name: 'RAG 引用溯源', desc: '回答附出处与相似度', tag: 'KB_SEARCH' },
  { icon: '❖', name: '共享长期记忆', desc: '跨智能体记住你是谁', tag: 'MEMORY' },
  { icon: '✳', name: '画像个性化', desc: '学校·专业·年级自适应', tag: 'PROFILE' },
  { icon: '◇', name: '三大模型热切换', desc: 'DeepSeek · Qwen · GLM', tag: 'OpenAI 兼容' }
]
const ROW_BOTTOM = [
  { icon: '⚡', name: 'SSE 流式输出', desc: '逐字实时推送', tag: 'FastAPI' },
  { icon: '⌘', name: 'ReAct 工具循环', desc: '检索 + 计算，3 轮上限', tag: 'TOOL CALLING' },
  { icon: '▤', name: '多格式知识库', desc: 'PDF · DOCX · PPTX · MD', tag: 'bge-m3 向量化' },
  { icon: '⬡', name: 'LangGraph 图调度', desc: '条件边驱动的状态机', tag: '静态图' },
  { icon: '◎', name: 'CPU 友好', desc: '全链路零 GPU 依赖', tag: '100% 本地' },
  { icon: '✦', name: '会话回放', desc: '历史对话完整重建', tag: 'plan 持久化' }
]
</script>

<template>
  <div class="ab">
    <!-- 上排：向左滚 -->
    <div class="ab-row">
      <div class="ab-track">
        <span v-for="n in 2" :key="'t' + n" class="ab-run">
          <article v-for="(c, i) in ROW_TOP" :key="i" class="ab-card">
            <span class="ab-icon">{{ c.icon }}</span>
            <h3 class="ab-name">{{ c.name }}</h3>
            <p class="ab-desc">{{ c.desc }}</p>
            <span class="ab-tag mono">{{ c.tag }}</span>
          </article>
        </span>
      </div>
    </div>
    <!-- 下排：向右滚 -->
    <div class="ab-row mt">
      <div class="ab-track rev">
        <span v-for="n in 2" :key="'b' + n" class="ab-run">
          <article v-for="(c, i) in ROW_BOTTOM" :key="i" class="ab-card">
            <span class="ab-icon alt">{{ c.icon }}</span>
            <h3 class="ab-name">{{ c.name }}</h3>
            <p class="ab-desc">{{ c.desc }}</p>
            <span class="ab-tag mono">{{ c.tag }}</span>
          </article>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ab { max-width: 1280px; margin: 0 auto; overflow: hidden; }
.ab-row {
  overflow: hidden;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
}
.ab-row.mt { margin-top: 18px; }
.ab-track { display: flex; width: max-content; animation: ab-l 30s linear infinite; }
.ab-track.rev { animation: ab-r 34s linear infinite; }
.ab-row:hover .ab-track { animation-play-state: paused; }
.ab-run { display: flex; gap: 16px; padding-right: 16px; }
.ab-card {
  width: 218px; flex-shrink: 0;
  background: #fff; border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 22px 20px 18px;
  transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
}
.ab-card:hover {
  transform: translateY(-5px);
  border-color: var(--pink);
  box-shadow: 0 14px 34px rgba(240, 130, 160, .16);
}
.ab-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 13px;
  background: var(--pink-soft); color: var(--accent);
  font-size: 17px; margin-bottom: 15px;
}
.ab-icon.alt { background: #f3f0ff; color: #7a6bd6; }
.ab-name { font-size: 15px; font-weight: 800; letter-spacing: -.01em; margin-bottom: 6px; }
.ab-desc { font-size: 12px; color: var(--muted); line-height: 1.6; margin-bottom: 12px; }
.ab-tag { font-size: 8.5px; color: var(--dim); letter-spacing: .12em; border-top: 1px dashed var(--line); padding-top: 10px; display: block; }
@keyframes ab-l { to { transform: translateX(-50%); } }
@keyframes ab-r { from { transform: translateX(-50%); } to { transform: translateX(0); } }
</style>
