"""智能体工具箱（里程碑 6）：定向知识库检索 + Python 计算器。

- kb_search：按分类定向检索知识库（ChromaDB where 过滤），供智能体通过
  function calling 自主决定何时检索，取代旧版「全局前置注入」。
- python_calc：ast 白名单求值器，零第三方依赖，只允许数字四则运算与
  少量安全函数，杜绝任意代码执行。

工具通过 LangChain @tool 定义，绑定到领域智能体后走 OpenAI 兼容
function calling 协议（DeepSeek/Qwen/GLM 均支持）。
"""
import ast

from langchain_core.tools import tool

from ..services import kb


@tool
def kb_search(query: str, category: str = "general") -> str:
    """在用户知识库中定向检索课程资料、竞赛资料等文档片段。

    Args:
        query: 检索问题或关键词，如「二叉树的性质」
        category: 文档分类过滤，可选 study(学习)/competition(竞赛)/research(科研)/career(求职)/life(生活)/general(通用)
    """
    text, _ = kb_search_impl(query, category)
    return text


def kb_search_impl(
    query: str, category: str = "general", doc_ids: list[int] | None = None,
) -> tuple[str, list[dict]]:
    """检索实现：返回 (给 LLM 阅读的文本, 结构化引用列表)。

    doc_ids：用户在对话页知识库菜单勾选的文档范围；None/空 = 检索全部。
    """
    try:
        hits = kb.search(
            query, category=category if category != "general" else None, doc_ids=doc_ids or None,
        )
    except Exception as e:  # 向量库异常不阻塞回答
        return f"知识库检索失败：{e}", []
    if not hits:
        return "知识库中没有找到相关内容。可以提示用户先在知识库页面上传相关资料。", []
    lines = [f"《{h['doc']}》（相似度 {h['score']:.2f}）：{h['snippet']}" for h in hits]
    return "检索到以下知识库片段，回答时请标注来源：\n" + "\n".join(lines), hits


# ---------- Python 计算工具：ast 白名单求值 ----------

# 允许的二元运算符
_BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}
# 允许的一元运算符
_UNARY_OPS = {ast.UAdd: lambda a: +a, ast.USub: lambda a: -a}
# 允许的安全函数（sqrt 用幂运算实现，避免引入 math 依赖）
_SAFE_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": lambda x: x ** 0.5,
}
_MAX_RESULT = 1e15  # 结果上限，防止 Pow 产生天文数字拖慢序列化


def _safe_eval(node: ast.AST) -> float:
    """递归求值 ast 节点，遇到白名单外的语法直接抛错。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("只支持数字常量")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = _SAFE_FUNCS.get(node.func.id)
        if fn is None:
            raise ValueError(f"不支持的函数：{node.func.id}")
        if node.keywords:
            raise ValueError("不支持关键字参数")
        args = [_safe_eval(a) for a in node.args]
        if not 1 <= len(args) <= 2:
            raise ValueError("参数个数不符")
        return fn(*args)
    raise ValueError("表达式包含不允许的语法")


def calc_expression(expression: str) -> str:
    """求值白名单内的算术表达式，返回给 LLM 阅读的结果文本。"""
    expression = expression.strip()
    if not expression or len(expression) > 200:
        return "计算失败：表达式为空或超长"
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        return f"计算失败：{e}" if str(e) else "计算失败：表达式不合法"
    if isinstance(result, float):
        result = round(result, 6)
        if abs(result) > _MAX_RESULT:
            return "计算失败：结果超出范围"
        result = int(result) if result.is_integer() else result
    elif abs(result) > _MAX_RESULT:
        return "计算失败：结果超出范围"
    return f"计算结果：{expression} = {result}"


@tool
def python_calc(expression: str) -> str:
    """计算算术表达式的值，用于学分绩点、总分、时间规划等数字问题。

    Args:
        expression: 算术表达式，如 (19.5*4+18*3)/7，支持 + - * / // % ** 与 abs/round/min/max/sqrt
    """
    return calc_expression(expression)


# 各智能体的工具清单：学习助手可检索知识库 + 计算；科研助手可检索知识库
TOOLBOX: dict[str, list] = {
    "study": [kb_search, python_calc],
    "research": [kb_search],
}
