"""聊天接口：Supervisor 调度 + 领域智能体，SSE 流式对话（里程碑 2）。

SSE 帧协议：
    {"type": "meta",  "conversation_id": 1, "title": "..."}
    {"type": "clarify", "questions": ["..."], "reason": "..."}  # 澄清追问（里程碑 7，无后续任务帧）
    {"type": "agent", "agent": "学习助手",  "reason": "竞赛规划"}   # 调度决策
    {"type": "tool",  "name": "kb_search", "args": {...}, "summary": "..."}  # 工具调用（里程碑 6）
    {"type": "citations", "items": [{"doc": "...", "snippet": "...", "score": 0.9}]}  # RAG 命中（可选）
    {"type": "delta", "content": "增量文本"}                       # 多次
    {"type": "done",  "message_id": 123}
    {"type": "error", "message": "..."}
"""
import json
import threading

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import PROVIDER_LABELS, get_settings
from ..db import SessionLocal
from ..graph.agents import AGENTS
from ..graph.build import build_graph
from ..models import Conversation, KnowledgeDoc, Message, User
from ..services import runtime_settings
from ..services.profile import build_context, extract_and_store
from .auth import get_current_user

router = APIRouter()

# 携带最近 N 条历史作为智能体上下文
MAX_HISTORY = 12


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str
    provider: str | None = None  # deepseek | qwen | glm
    use_kb: bool = True  # 知识库检索开关（前端输入框左下角可切换）
    kb_doc_ids: list[int] | None = None  # 勾选的检索范围（None/空 = 全部资料）
    use_memory: bool = True  # 长期记忆运用开关（关闭时不注入画像与记忆，回答不带个人背景）


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(content) -> str:
    """AIMessage.content 可能是 str 或内容块列表，统一转纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content or "")


def resolve_provider(provider: str, user_id: int = 0) -> tuple[str, str, int | None]:
    """BYOK 优先 + 平台配额：用户自配 Key 不限量；平台 .env Key 受每日配额约束。

    返回 (provider, notice, quota_left)；quota_left 为平台配额剩余（None = 不限量），
    notice 非空时由调用方推 status 帧，额度用尽返回 ("", 错误文案, None)。
    用户自配 Key 按账号隔离（u{id}: 前缀）；平台 Key 配额按供应商分桶、全局共享。
    """
    settings = get_settings()
    user_key = runtime_settings.user_scope(user_id, f"{provider}_api_key")
    # 1. 用户自配 Key（运行时）：BYOK 直用，不限量
    if runtime_settings.get_setting(user_key):
        return provider, "", None
    # 2. 平台 Key（.env）：付费供应商受每日配额约束，免费供应商不限
    if settings.provider_config(provider)[0]:
        if not runtime_settings.consume_platform(provider):
            limit = runtime_settings.PLATFORM_DAILY_LIMIT
            return "", (
                f"「{PROVIDER_LABELS[provider]}」今日平台体验次数已用完（{limit}/{limit}）。"
                "请到「个人中心 → 模型管理」配置你自己的 API Key，即可不限量使用"
            ), None
        return provider, "", runtime_settings.platform_left(provider)
    # 3. 完全未接入：回落兜底供应商（同样受平台配额约束）
    fallback = settings.FALLBACK_PROVIDER.lower()
    if provider == fallback:
        return provider, "", None  # 兜底自身未接入时走原有报错流程
    fb_provider, _, fb_left = resolve_provider(fallback, user_id)
    if not fb_provider:
        return "", (
            "免费兜底模型不可用，请到「个人中心 → 模型管理」配置 API Key 后使用"
        ), None
    return fb_provider, (
        f"「{PROVIDER_LABELS[provider]}」未接入，已自动切换至"
        f"「{PROVIDER_LABELS[fb_provider]}」（今日剩余 {fb_left} 次）"
    ), fb_left


@router.post("/api/chat")
def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    """流式对话：调度智能体识别意图 -> 领域智能体生成回复，全程 SSE 推送。

    数据按账号隔离：会话归属校验、kb 检索范围收窄到本人文档、BYOK 按用户解钥。
    """
    settings = get_settings()
    provider = (req.provider or settings.LLM_PROVIDER).lower()
    if provider not in PROVIDER_LABELS:  # 供应商已下线或非法：回落默认，防库中残留旧值
        provider = settings.LLM_PROVIDER.lower()
    # BYOK 优先 + 平台配额：自配 Key 不限量，平台 Key 日限 20 次
    provider, notice, quota_left = resolve_provider(provider, user.id)
    provider_label = PROVIDER_LABELS.get(provider, provider)

    def event_stream():
        if not provider:  # 平台配额用尽：单 error 帧，引导配置自己的 Key
            yield _sse({"type": "error", "message": notice})
            return
        db: Session = SessionLocal()
        try:
            # 0. 未配置密钥：直接报错提示（运行时 Key 优先于 .env，用户级键隔离）
            user_key = runtime_settings.user_scope(user.id, f"{provider}_api_key")
            api_key = runtime_settings.get_setting(user_key) or settings.provider_config(provider)[0]
            if not api_key:
                yield _sse({"type": "error", "message": f"{provider_label} 未配置 API 密钥，请到「个人中心 → 模型」配置后使用"})
                return
            if notice:  # 兜底切换提示：前端时间线步骤展示
                yield _sse({"type": "status", "stage": "fallback", "message": notice})
            if quota_left is not None:  # 平台 Key 配额提醒：每次对话播报剩余次数
                yield _sse({
                    "type": "status", "stage": "quota",
                    "message": f"本次使用平台体验额度 · {provider_label} 今日剩余 {quota_left}/{runtime_settings.PLATFORM_DAILY_LIMIT} 次",
                })
            # 1. 定位或创建会话（归属当前用户；他人会话一律按不存在处理）
            if req.conversation_id:
                conv = (
                    db.query(Conversation)
                    .filter(Conversation.id == req.conversation_id, Conversation.user_id == user.id)
                    .first()
                )
                if conv is None:
                    yield _sse({"type": "error", "message": "会话不存在"})
                    return
            else:
                conv = Conversation(user_id=user.id, title=req.message[:20] or "新对话")
                db.add(conv)
                db.commit()
                db.refresh(conv)

            # 1.5 kb 检索范围收窄到本人文档：null/[] 检索本人全部资料，
            #     勾选子集时与本人文档求交集，防越权检索他人文档
            user_doc_ids = [
                r[0] for r in db.query(KnowledgeDoc.id).filter_by(user_id=user.id).all()
            ]
            if req.kb_doc_ids:
                kb_scope = [i for i in req.kb_doc_ids if i in user_doc_ids]
            else:
                kb_scope = user_doc_ids  # 空 = 本人无文档，工具检索自然返回空

            # 2. 保存用户消息
            db.add(Message(conversation_id=conv.id, role="user", content=req.message))
            db.commit()

            # 3. 组装上下文（最近历史 -> LangChain 消息）
            history = (
                db.query(Message)
                .filter_by(conversation_id=conv.id)
                .order_by(Message.id)
                .all()
            )
            lc_msgs = [
                HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
                for m in history[-MAX_HISTORY:]
            ]
            # 里程碑 7：上一轮是澄清追问 -> 提示调度直接出计划，防止连环追问
            prev_ai = next((m for m in reversed(history) if m.role == "assistant"), None)
            if prev_ai and prev_ai.plan and prev_ai.plan.get("action") == "clarify":
                lc_msgs.append(SystemMessage(
                    content="上一轮已向用户澄清追问，用户本轮已补充信息，请直接产出任务执行计划，不要再次追问。"
                ))

            yield _sse({
                "type": "meta", "conversation_id": conv.id, "title": conv.title,
                "last_message": req.message[:60],  # 供左栏会话卡摘要即时更新
            })

            # 3.5 组装共享背景：用户画像 + 长期记忆（use_memory 关闭时跳过注入）
            ctx = build_context(db, conv.user_id, req.message) if req.use_memory else ""
            # 里程碑 6：知识库检索改为智能体工具调用（kb_search），不再全局前置注入

            # 4. 生成回复：Supervisor 调度图 -> 顺序多智能体协作 -> 汇总，全程流式推送
            full = ""
            agent_label = "智学方舟"
            citations: list[dict] = []
            segments: list[dict] = []  # 分段产出 [{agent, label, content}]
            plan_obj: dict | None = None
            tools_events: list[dict] = []  # 工具调用事件（持久化到 plan 供回放）
            try:
                node_to_index: dict[str, int] = {}
                cur_agent_idx = 0  # 当前正在执行的智能体段下标（agent_start 推进）
                for mode, payload in build_graph().stream(
                    {"messages": lc_msgs, "context": ctx, "use_kb": req.use_kb,
                     "kb_doc_ids": kb_scope, "provider": provider, "user_id": user.id},
                    stream_mode=["messages", "updates", "custom"],
                    config={"recursion_limit": 50},
                ):
                    if mode == "updates":
                        # supervisor 完成 -> 澄清追问 或 推送任务规划帧
                        delta = payload.get("supervisor") if isinstance(payload, dict) else None
                        if delta:
                            cl = delta.get("clarify")
                            if cl:  # 里程碑 7：澄清追问轮——无任务规划，直接推追问帧
                                agent_label = "调度智能体"
                                plan_obj = {
                                    "action": "clarify",
                                    "questions": cl.get("questions") or [],
                                    "reason": cl.get("reason", ""),
                                }
                                full = "为了给你更合适的方案，请先告诉我：\n" + "\n".join(
                                    f"{i}）{q}" for i, q in enumerate(plan_obj["questions"], 1)
                                )
                                yield _sse({"type": "clarify", "questions": plan_obj["questions"], "reason": plan_obj["reason"]})
                            else:
                                tasks = delta.get("tasks") or [{"agent": "general", "objective": ""}]
                                plan_tasks = [
                                    {"agent": t["agent"], "label": AGENTS[t["agent"]]["label"], "objective": t.get("objective", "")}
                                    for t in tasks
                                ]
                                reason = "多智能体协作" if len(tasks) > 1 else plan_tasks[0]["objective"]
                                agent_label = "多智能体协作" if len(tasks) > 1 else plan_tasks[0]["label"]
                                plan_obj = {"tasks": plan_tasks, "segments": segments, "reason": reason}
                                yield _sse({"type": "plan", "tasks": plan_tasks, "reason": reason})
                        continue
                    if mode == "custom":
                        # 节点内事件（里程碑 6）：任务开始 / 工具调用
                        if isinstance(payload, dict) and payload.get("kind") == "agent_start":
                            idx = payload.get("index", 0)
                            cur_agent_idx = idx
                            node_to_index[payload.get("key", "")] = idx
                            while len(segments) <= idx:
                                segments.append({"agent": "", "label": "", "content": ""})
                            segments[idx] = {
                                "agent": payload.get("key", ""),
                                "label": payload.get("agent", ""),
                                "content": "",
                            }
                            yield _sse({
                                "type": "agent_start", "agent": payload.get("agent", ""),
                                "index": idx, "objective": payload.get("objective", ""),
                            })
                        elif isinstance(payload, dict) and payload.get("kind") == "tool":
                            tools_events.append({
                                "name": payload.get("name", ""),
                                "summary": payload.get("summary", ""),
                                "index": cur_agent_idx,
                            })
                            yield _sse({
                                "type": "tool", "name": payload.get("name"),
                                "args": payload.get("args") or {},
                                "summary": payload.get("summary", ""),
                            })
                            if payload.get("citations"):
                                citations = payload["citations"]
                                yield _sse({"type": "citations", "items": citations})
                        continue
                    # messages 模式：(chunk, metadata)
                    chunk, meta = payload
                    node = meta.get("langgraph_node")
                    if node in ("supervisor", "gate") or node not in node_to_index:
                        continue  # 过滤调度/路由节点 token；汇总节点由 agent_start 建段后流入
                    idx = node_to_index[node]
                    text = _chunk_text(chunk.content)
                    if text:
                        full += text
                        if idx < len(segments):
                            segments[idx]["content"] += text
                        yield _sse({"type": "delta", "content": text, "index": idx})
            except Exception as e:  # 网络 / 密钥 / 额度等错误统一推给前端
                msg = str(e)
                low = msg.lower()
                # 限流错误打标（429 / 智谱 1305 / 访问量过大）：前端渲染「换模型重试」错误卡
                is_rate = (
                    any(k in low for k in ("429", "1305", "rate limit", "too many requests"))
                    or "访问量过大" in msg
                )
                # 兜底：已流式产出的部分内容先落库，刷新后不丢已生成文本
                if full:
                    try:
                        if plan_obj:
                            plan_obj["tools"] = tools_events
                        db.add(Message(
                            conversation_id=conv.id, role="assistant",
                            agent=agent_label, content=full, model=provider,
                            citations=citations or None, plan=plan_obj or None,
                        ))
                        db.commit()
                    except Exception:
                        db.rollback()
                yield _sse({
                    "type": "error", "message": f"模型调用失败：{msg}",
                    "kind": "rate_limit" if is_rate else "generic",
                })
                return

            # 5. 保存助手消息（记录来源智能体、RAG 引用与任务计划分段）
            if plan_obj:
                plan_obj["tools"] = tools_events  # 工具事件一并持久化，回放时间线用
            assistant = Message(
                conversation_id=conv.id, role="assistant",
                agent=agent_label, content=full, model=provider,
                citations=citations or None,
                plan=plan_obj or None,
            )
            db.add(assistant)
            db.commit()
            yield _sse({"type": "done", "message_id": assistant.id})

            # 6. 后台线程提炼画像与记忆（不阻塞响应）
            threading.Thread(
                target=extract_and_store,
                args=(conv.user_id, conv.id, provider, [("user", req.message), ("assistant", full)]),
                daemon=True,
            ).start()
        finally:
            db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
