"""智能体目录 API（里程碑 5）：供前端「智能体广场」页展示元信息。"""
from fastapi import APIRouter

from ..graph.agents import AGENTS

router = APIRouter(prefix="/api/agents")


@router.get("")
def list_agents():
    """返回五位领域智能体的职责描述与能力标签，及调度智能体说明。"""
    return {
        "supervisor": {
            "label": "调度智能体",
            "desc": "自动识别用户意图，将请求路由给最合适的领域智能体；"
                    "复合任务可拆解并依次调度多个智能体协作。",
        },
        "agents": [
            {
                "key": key,
                "label": spec["label"],
                "desc": spec["desc"],
                "tags": spec["tags"],
            }
            for key, spec in AGENTS.items()
            if key != "general"
        ],
    }
