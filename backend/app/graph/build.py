"""LangGraph 调度图（里程碑 6）：Supervisor 任务规划 -> 顺序多智能体协作 -> 汇总。

图结构（静态图 + 条件边实现动态任务链）：
    START -> supervisor -(条件边)-> 第一个任务的智能体
    各智能体 -> gate -(条件边)-> 下一个任务的智能体 | synthesizer | END
    synthesizer -> END

- 单任务计划：supervisor -> 智能体 -> gate -> END（与里程碑 2 行为一致，不额外汇总）
- 多任务计划：按 tasks 顺序执行各智能体，前序产出注入后续任务上下文，
  最后由 synthesizer 低温度汇总为一条连贯回复

流式说明：
    graph.stream(..., stream_mode=["messages", "updates", "custom"])
    - "updates" 模式拿到 supervisor 的任务规划（tasks）
    - "messages" 模式拿到各节点增量 token（supervisor/gate 的 token 由调用方过滤）
    - "custom" 模式拿到节点内主动推送事件：agent_start（任务开始）/ tool（工具调用）
"""
import json
from functools import lru_cache
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from ..llm.client import get_chat_model
from .agents import AGENTS, STYLE_PROMPT
from .tools import TOOLBOX, calc_expression, kb_search_impl

SUPERVISOR_PROMPT = """你是「智学方舟」多智能体平台的调度智能体（Supervisor）。
分析用户最新请求，二选一：
A. 请求意图清晰 -> 产出任务执行计划（action=plan）：
1. 单领域请求只需一个任务；跨领域协作请求（如学习与竞赛双线安排）拆成 2~3 个任务；
2. 任务按执行顺序排列，每个任务写明该步要达成的目标；
3. agent 只能从以下 key 中选择：
- general：问候寒暄、平台功能咨询、无法归类的通用问题
- study：课程学习、选课、复习备考、知识点讲解、作业辅导
- competition：学科竞赛、数学建模、挑战杯、互联网+等竞赛规划与备赛
- research：文献检索、论文阅读与写作、科研入门、导师沟通、保研
- career：实习、校招、简历、面试、职业规划
- life：校园生活、社团活动、宿舍、心理调适、办事流程、美食游玩
B. 请求意图模糊且关键信息缺失、无法合理默认（如「帮我做个规划」没说学习还是竞赛、什么时间范围）-> 澄清追问（action=clarify）：
1. 只在确有必要时追问；每轮对话最多追问一次；寒暄、事实问答、信息足够时禁止追问；
2. questions 列出 1~2 个具体问题，帮助确定领域与目标。

只输出如下 JSON，不要输出任何其他文字：
{"action": "plan", "tasks": [{"agent": "<key>", "objective": "<该任务目标，不超过12字>"}]}
或
{"action": "clarify", "questions": ["<问题1>", "<问题2>"]}"""

SYNTHESIZER_PROMPT = """你是「智学方舟」的汇总智能体。多位领域智能体已按顺序完成各自任务，
请把它们的产出整合为一条连贯的最终回复：
1. 用一两句话点明整体安排思路，再分点整合各任务的关键结论；
2. 不要逐字重复原文，突出任务之间的衔接与优先级；
3. 结尾给一个可执行的下一步行动建议，控制在 300 字以内。"""


def _merge_outputs(a: dict | None, b: dict | None) -> dict:
    """outputs 字段 reducer：顺序节点各自写入，合并而非覆盖。"""
    return {**(a or {}), **(b or {})}


class AgentState(TypedDict):
    """调度图共享状态。"""

    messages: Annotated[list[AnyMessage], add_messages]
    tasks: list[dict]  # 任务计划 [{agent, objective}]（supervisor 产出）
    cur: int  # 当前执行到的任务下标
    outputs: Annotated[dict, _merge_outputs]  # 各智能体产出 {agent_key: 文本}
    context: str  # 用户画像 + 长期记忆（所有智能体共享，里程碑 3）
    clarify: dict | None  # 澄清追问 {questions, reason}（supervisor 产出，里程碑 7）
    use_kb: bool  # 知识库检索开关（False 时智能体不绑 kb_search 工具）
    kb_doc_ids: list[int] | None  # 用户勾选的检索范围（None/空 = 全部资料）
    provider: str  # 用户选择的 LLM 供应商（请求级参数，全图所有模型调用跟随）


def parse_supervisor_action(text: str) -> tuple[list[dict], dict | None]:
    """容错解析调度输出，返回 (任务列表, 澄清追问|None)（里程碑 7）。

    兼容三种输出：新版 {"action": "plan"|"clarify", ...}、旧版 {"tasks": [...]}、
    更旧版单任务 {"agent": ...}。action 缺失视为 plan（向后兼容）；
    clarify 但无有效 questions 时回落 plan；任务全非法回落通用助手单任务。
    """
    start, end = text.find("{"), text.rfind("}")
    tasks: list[dict] = []
    clarify: dict | None = None
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            # 澄清追问分支：必须带至少一个有效问题
            if str(data.get("action", "plan")).lower() == "clarify" and isinstance(data.get("questions"), list):
                qs = [str(q).strip()[:60] for q in data["questions"] if str(q).strip()][:2]
                if qs:
                    clarify = {"questions": qs, "reason": str(data.get("reason", ""))[:40] or "需要澄清"}
            raw = data.get("tasks")
            if isinstance(raw, list):
                for t in raw[:3]:  # 最多 3 个任务，防止过度拆解
                    if not isinstance(t, dict):
                        continue
                    agent = str(t.get("agent", "")).strip()
                    tasks.append({"agent": agent, "objective": str(t.get("objective", ""))[:24]})
            elif isinstance(data, dict) and data.get("agent"):  # 旧版单任务格式
                tasks.append({"agent": str(data.get("agent")), "objective": ""})
        except json.JSONDecodeError:
            tasks = []
    if clarify:  # 追问轮不携带任务
        return [], clarify
    valid = [t for t in tasks if t["agent"] in AGENTS]
    if not valid:
        valid = [{"agent": "general", "objective": ""}]
    return valid, None


def _supervisor_node(state: AgentState) -> dict:
    """规划节点：只看最近 4 条消息，低温度输出任务计划 / 澄清追问。"""
    recent = state["messages"][-4:]
    inputs = [SystemMessage(content=SUPERVISOR_PROMPT)]
    ctx = state.get("context", "")
    if ctx:  # 画像与记忆辅助意图判断
        inputs.append(SystemMessage(content=f"用户背景信息（仅供参考判断）：\n{ctx}"))
    inputs += recent
    tasks: list[dict] = [{"agent": "general", "objective": ""}]
    clarify: dict | None = None
    try:
        resp = get_chat_model(state.get("provider"), temperature=0.1).invoke(inputs)
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        tasks, clarify = parse_supervisor_action(content)
    except Exception:  # 调度失败不阻塞对话，回落通用助手单任务
        pass
    return {"tasks": tasks, "cur": 0, "clarify": clarify}


def _clarify_node(state: AgentState) -> dict:
    """澄清节点（里程碑 7）：把追问问题编成可读文本作为助手消息。

    追问事件帧由 chat.py 从 supervisor 的 updates delta 中读取（clarify 字段），
    此节点只负责产出消息文本；其 token 会被调用方按节点过滤，不产生 delta 帧。
    """
    c = state.get("clarify") or {"questions": []}
    qs = c.get("questions") or []
    text = "为了给你更合适的方案，请先告诉我：\n" + "\n".join(
        f"{i}）{q}" for i, q in enumerate(qs, 1)
    )
    return {"messages": [AIMessage(content=text)]}


def _make_agent_node(key: str):
    """领域智能体节点工厂：人设 + 共享风格 + 画像记忆 + 任务上下文。

    里程碑 6：绑定了工具的智能体（study/research）走 ReAct 循环——
    bind_tools -> 模型决定是否调用工具 -> 执行并把结果回灌 -> 再生成，
    上限 MAX_TOOL_ROUNDS 轮；未绑定工具的智能体保持单次生成。
    """

    def _node(state: AgentState) -> dict:
        cur = state.get("cur", 0)
        tasks = state.get("tasks") or [{"agent": key, "objective": ""}]
        objective = tasks[cur].get("objective", "") if cur < len(tasks) else ""
        writer = get_stream_writer()  # custom 流写入器：向调用方推任务开始事件
        writer({"kind": "agent_start", "key": key, "agent": AGENTS[key]["label"], "index": cur, "objective": objective})

        system = AGENTS[key]["prompt"] + "\n\n" + STYLE_PROMPT
        ctx = state.get("context", "")
        if ctx:  # 注入所有智能体共享的用户画像与长期记忆
            system += "\n\n【用户画像与长期记忆（所有智能体共享）】\n" + ctx
        if objective:
            system += f"\n\n【当前任务目标】{objective}（专注该目标回答，无需面面俱到）"
        outputs = state.get("outputs") or {}
        if outputs:  # 前序智能体产出：供衔接参考，避免重复
            prev = "\n".join(f"- {AGENTS[k]['label']}：{v}" for k, v in outputs.items() if k in AGENTS)
            system += "\n\n【前序智能体产出（供衔接参考，不要重复其内容）】\n" + prev
        msgs: list = [SystemMessage(content=system)] + state["messages"]

        tools = TOOLBOX.get(key, [])
        if not state.get("use_kb", True):  # 知识库开关关闭：剔除 kb_search
            tools = [t for t in tools if getattr(t, "name", "") != "kb_search"]
        if not tools:  # 无工具智能体：单次生成
            resp = get_chat_model(state.get("provider"), temperature=0.7).invoke(msgs)
            return {"messages": [resp], "outputs": {key: _chunk_text(resp.content)}, "cur": cur + 1}

        model = get_chat_model(state.get("provider"), temperature=0.7).bind_tools(tools)
        for _ in range(MAX_TOOL_ROUNDS):
            resp = model.invoke(msgs)
            calls = getattr(resp, "tool_calls", None) or []
            if not calls:  # 模型不再需要工具，输出最终回答
                return {"messages": [resp], "outputs": {key: _chunk_text(resp.content)}, "cur": cur + 1}
            msgs.append(resp)
            for call in calls:
                name, args = call["name"], call.get("args") or {}
                result, citations = _run_tool(name, args, state.get("kb_doc_ids") or None)
                # 推送工具事件：chat.py 转 SSE tool 帧（检索命中时附带 citations）
                writer({
                    "kind": "tool", "name": name, "args": args,
                    "summary": _tool_summary(name, args, result),
                    "citations": citations,
                })
                msgs.append(ToolMessage(content=result, tool_call_id=call["id"], name=name))
        # 工具轮次耗尽：去掉工具强制收尾，保证一定能给出回答
        resp = get_chat_model(state.get("provider"), temperature=0.7).invoke(
            msgs + [SystemMessage(content="请基于以上已获取的信息直接给出最终回答，不要再调用工具。")]
        )
        return {"messages": [resp], "outputs": {key: _chunk_text(resp.content)}, "cur": cur + 1}

    return _node


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


def _gate_node(state: AgentState) -> dict:
    """任务链路由节点：判断继续下一个任务、进入汇总还是结束。"""
    return {}


def _route_after_gate(state: AgentState) -> str:
    """gate 条件边：还有任务就执行下一个，否则单任务结束 / 多任务进汇总。"""
    tasks = state.get("tasks") or []
    cur = state.get("cur", 0)
    if cur < len(tasks):
        key = tasks[cur]["agent"]
        return key if key in AGENTS else "general"
    return "synthesizer" if len(tasks) > 1 else END


def _synthesizer_node(state: AgentState) -> dict:
    """汇总节点：低温度把各智能体产出整合为一条连贯回复。"""
    writer = get_stream_writer()
    tasks = state.get("tasks") or []
    writer({"kind": "agent_start", "key": "__synth__", "agent": "调度智能体 · 汇总", "index": len(tasks), "objective": ""})

    user_q = ""
    for m in reversed(state["messages"]):
        if getattr(m, "type", "") == "human":
            user_q = _chunk_text(m.content)
            break
    outputs = state.get("outputs") or {}
    parts = "\n\n".join(
        f"【{AGENTS[k]['label']}的产出】\n{v}" for k, v in outputs.items() if k in AGENTS
    )
    system = SYNTHESIZER_PROMPT
    ctx = state.get("context", "")
    if ctx:
        system += "\n\n【用户画像】" + ctx.split("\n")[0]
    resp = get_chat_model(state.get("provider"), temperature=0.3).invoke(
        [SystemMessage(content=system)]
        + [SystemMessage(content=f"用户原始问题：{user_q}\n\n各智能体产出：\n{parts}")]
        + state["messages"][-1:]
    )
    return {"messages": [resp], "outputs": {"__synth__": _chunk_text(resp.content)}}


# ReAct 循环上限：防止模型反复调用工具拖长响应
MAX_TOOL_ROUNDS = 3


def _run_tool(name: str, args: dict, doc_ids: list[int] | None = None) -> tuple[str, list[dict] | None]:
    """按名执行工具，返回 (结果文本, 结构化引用)。未知工具返回错误提示。

    doc_ids：用户勾选的知识库检索范围（AgentState 透传），None = 检索全部。
    """
    try:
        if name == "kb_search":
            text, hits = kb_search_impl(args.get("query", ""), args.get("category") or "general", doc_ids)
            return text, hits
        if name == "python_calc":
            return calc_expression(args.get("expression", "")), None
        return f"未知工具：{name}", None
    except Exception as e:  # 工具异常以文本回灌，不中断对话
        return f"工具执行失败：{e}", None


def _tool_summary(name: str, args: dict, result: str) -> str:
    """工具事件的摘要文案：给前端时间线展示用。"""
    if name == "kb_search":
        n = result.count("《")
        return f"定向检索「{args.get('query', '')}」· 命中 {n} 段" if n else f"检索「{args.get('query', '')}」· 无命中"
    if name == "python_calc":
        return f"计算 {args.get('expression', '')} · {result.split('=')[-1].strip() if '=' in result else result}"
    return result[:60]


@lru_cache
def build_graph():
    """构建并编译调度图（进程内缓存单例；静态图 + 条件边支持任意任务序列）。"""
    g = StateGraph(AgentState)
    g.add_node("supervisor", _supervisor_node)
    g.add_node("clarify", _clarify_node)
    for key in AGENTS:
        g.add_node(key, _make_agent_node(key))
    g.add_node("gate", _gate_node)
    g.add_node("synthesizer", _synthesizer_node)

    g.add_edge(START, "supervisor")

    # supervisor -> 澄清追问 或 第一个任务对应的智能体
    def _route_first(state: AgentState) -> str:
        if state.get("clarify"):  # 里程碑 7：意图模糊先追问
            return "clarify"
        tasks = state.get("tasks") or []
        if tasks:
            key = tasks[0]["agent"]
            return key if key in AGENTS else "general"
        return "general"

    g.add_conditional_edges("supervisor", _route_first, {"clarify": "clarify", **{key: key for key in AGENTS}})
    g.add_edge("clarify", END)
    # 所有智能体完成后进入 gate，由 gate 决定后续走向
    for key in AGENTS:
        g.add_edge(key, "gate")
    g.add_conditional_edges("gate", _route_after_gate, {**{key: key for key in AGENTS}, "synthesizer": "synthesizer", END: END})
    g.add_edge("synthesizer", END)
    return g.compile()
