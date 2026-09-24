# 智学方舟 zhixue-ark

> 「大学里的事，交给一艘方舟。」—— 面向大学生的校园多智能体 AI 平台：一个统一聊天入口，五位领域智能体共享一份用户画像与长期记忆，由调度智能体（Supervisor）自动拆解任务，知识库回答自带引用溯源。

![Vue 3](https://img.shields.io/badge/Vue-3.5-42b883) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688) ![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1c3c3c) ![Python](https://img.shields.io/badge/Python-3.11+-3776ab) ![Node](https://img.shields.io/badge/Node-18+-339933)

## 在线体验

| 端 | 地址 |
| --- | --- |
| 前端（Vercel） | <https://zhixue-ark.vercel.app> |
| 后端 API（Render） | <https://zhixue-ark.onrender.com/api/health> |

> 免费层提示：Render 后端 15 分钟无访问会休眠，**首次打开需等约 50 秒冷启动**，之后再访问即恢复秒开。

## 核心特性

| 能力 | 说明 |
| --- | --- |
| 统一入口 | 一次提问即可，无需选择「该问谁」；意图模糊时智能体先澄清追问 |
| 五位领域智能体 | 学习助手 / 竞赛指导 / 科研助手 / 求职指导 / 生活服务，另设通用助手兜底 |
| 可解释的调度 | LangGraph 状态图驱动，任务规划、分发、工具调用以时间线形式对用户透明 |
| 私有知识可溯源 | 上传课件/讲义到知识库，回答附引用角标，可核查原文片段与相似度分数 |
| 画像与记忆共享 | 用户画像与长期记忆被所有智能体共享，对话结束后自动提炼新记忆 |
| 多用户与 BYOK | 账号级数据隔离；用户自带 API Key（掩码存储、优先级高于平台 Key、不限量） |

## 系统架构

```mermaid
flowchart LR
    subgraph FE["前端 · Vue 3 + Vite"]
        UI["着陆页 / 智能对话 / 知识库 / 任务计划<br/>学习足迹 / 模型广场 / 个人中心"]
    end
    subgraph BE["后端 · FastAPI"]
        API["REST + SSE 流式接口"]
        GRAPH["LangGraph 调度图<br/>Supervisor → 领域智能体 → 汇总"]
        RAG["RAG 服务<br/>智谱 embedding-3 + 向量检索"]
        MEM["画像 / 长期记忆服务"]
    end
    LLM["云端 LLM（OpenAI 兼容协议）<br/>DeepSeek / 通义千问 / 智谱 GLM"]
    DB[("Turso 云数据库 / 本地 SQLite<br/>用户 · 会话 · 消息 · 记忆 · 知识向量")]

    UI -- "HTTP / SSE（/api/*）" --> API
    API --> GRAPH
    GRAPH -- "对话补全" --> LLM
    GRAPH -- "kb_search 工具" --> RAG
    API --> MEM
    API --> DB
    RAG --> DB
```

对话全程经 SSE 推送结构化帧（`meta` → `plan` → `agent_start` → `tool` → `citations` → `delta` → `done`），前端渲染为回答上方的可解释时间线。

## 技术栈

| 层 | 组件 |
| --- | --- |
| AI 层 | LangGraph（状态图编排）· LangChain OpenAI（工具绑定 / ReAct）· DeepSeek / 通义千问 / 智谱 GLM（OpenAI 兼容，可切换自动回落）· 智谱 embedding-3（向量化） |
| 服务层 | Vue 3 + Vite + 原生 CSS · FastAPI + Uvicorn（REST + SSE）· SQLAlchemy 2.0 · Pydantic Settings |
| 部署层 | Vercel（前端静态托管 + /api 反代）· Render（后端容器）· Turso libSQL（云数据库，向量同库存储）· PBKDF2 + HMAC Token 认证 |

**纯 CPU 可运行，无 GPU 与外部中间件依赖。**

## 快速开始（本地）

Windows 用户可直接双击 `启动平台.bat` 一键拉起前后端；或手动执行：

```bash
# ① 后端：装依赖、配 Key、起服务（8000 端口）
cd backend && cp .env.example .env && pip install -r requirements.txt
# 编辑 backend/.env，至少填入一家供应商的 API Key（GLM 有永久免费档）
uvicorn app.main:app --port 8000

# ② 前端：装依赖、起开发服务器（5173 端口，/api 自动代理到 8000）
cd frontend && npm install && npm run dev
```

浏览器访问 `http://localhost:5173`。首次启动自动建表并初始化本地 SQLite（`backend/data/app.db`）。

## 环境变量（backend/.env）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | 否 | 默认供应商：`deepseek` / `qwen` / `glm` |
| `DEEPSEEK_API_KEY` / `QWEN_API_KEY` / `GLM_API_KEY` | **至少一家** | 三家均为 OpenAI 兼容协议；嵌入服务复用 `GLM_API_KEY` |
| `FALLBACK_PROVIDER` | 否 | 兜底供应商：所选供应商未配 Key 时自动切换 |
| `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` | 否 | 配置后业务数据 + 知识库向量持久化到 Turso 云库；留空回落本地 SQLite |
| `DATABASE_URL` / `HOST` / `PORT` | 否 | 本地库连接串与监听配置（有默认值） |

完整清单见 [backend/.env.example](backend/.env.example)。密钥只存环境变量，不入 Git。

## 端到端体验路径（4 步）

1. **访问** 前端地址，注册 / 登录
2. **在聊天框输入**「这道二叉树题帮我讲讲」（保持底部「知识库 · 检索开」「记忆 · 运用开」）
3. **观察调度时间线实时推进**：Supervisor 识别意图 → 分派学习助手 → 自动检索知识库 → 流式生成回答
4. **获得带「参考来源 [1]」角标的回答**：点击角标核查原文，或一键「✦ 转为我的计划」沉淀为待办

## 部署

| 平台 | 职责 | 关键配置 |
| --- | --- | --- |
| Vercel | 前端静态托管 | Root Directory = `frontend`；`vercel.json` 将 `/api/*` 反代到 Render |
| Render | FastAPI 后端 | Root Directory = `backend`；Start = `uvicorn app.main:app --host 0.0.0.0 --port $PORT`；环境变量在控制台配置 |
| Turso | libSQL 云数据库 | 创建数据库 + Token 后，将 URL / Token 填入 Render 环境变量，重启不丢数据 |

## 项目结构

```
zhixue-ark/
├── frontend/                    # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── App.vue              # 智能对话主页面
│   │   ├── api.js               # 请求 / SSE / 上传 / 鉴权封装
│   │   └── components/          # 着陆页 / 知识库 / 计划 / 足迹 / 模型广场 / 个人中心等
│   └── vercel.json              # /api 反向代理
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口（亦可托管 dist 单端口部署）
│   │   ├── config.py            # pydantic-settings 读取 .env
│   │   ├── db.py                # Turso 优先 / 本地 SQLite 回落
│   │   ├── graph/               # LangGraph 调度图（Supervisor / 领域智能体 / 工具）
│   │   ├── api/                 # auth / chat / conversations / kb / plans / memories / profile / insights / settings
│   │   ├── services/            # RAG（kb.py）/ 画像 / 运行时设置
│   │   └── llm/                 # OpenAI 兼容客户端
│   ├── requirements.txt
│   └── .env.example             # 环境变量模板
└── 启动平台.bat                  # Windows 一键启动
```

---

*对应代码版本 v0.1.0（2026-09）*
