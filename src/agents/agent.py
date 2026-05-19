"""跨境电商日报 Agent - 自动搜索政策变动与行业新闻，生成 HTML 日报，邮件推送"""

import os
import json
import logging
from typing import Annotated

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from coze_coding_utils.runtime_ctx.context import default_headers
from storage.memory.memory_saver import get_memory_saver
from tools.web_search_tool import search_amazon_policy, search_cross_border_news
from tools.daily_report_tool import generate_daily_report
from tools.email_tool import send_daily_report_email
from tools.scheduler import start_scheduler

logger = logging.getLogger(__name__)

LLM_CONFIG = "config/agent_llm_config.json"

# 默认保留最近 20 轮对话 (40 条消息)
MAX_MESSAGES = 40


def _windowed_messages(old, new):
    """滑动窗口: 只保留最近 MAX_MESSAGES 条消息"""
    return add_messages(old, new)[-MAX_MESSAGES:]  # type: ignore


class AgentState(MessagesState):
    messages: Annotated[list[AnyMessage], _windowed_messages]


# 服务启动时初始化定时调度器
_scheduler_started = False


def _ensure_scheduler():
    """确保调度器已启动（延迟启动，避免 import 时副作用）"""
    global _scheduler_started
    if not _scheduler_started:
        _scheduler_started = True
        try:
            start_scheduler()
            logger.info("日报定时调度器已启动，每天 08:00 自动生成日报并推送邮件")
        except Exception as e:
            logger.warning(f"调度器启动失败: {e}")


def build_agent(ctx=None):
    # 启动定时调度器
    _ensure_scheduler()

    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    config_path = os.path.join(workspace_path, LLM_CONFIG)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
    base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")

    llm = ChatOpenAI(
        model=cfg["config"].get("model"),
        api_key=api_key,
        base_url=base_url,
        temperature=cfg["config"].get("temperature", 0.3),
        streaming=True,
        timeout=cfg["config"].get("timeout", 600),
        extra_body={
            "thinking": {
                "type": cfg["config"].get("thinking", "disabled")
            }
        },
        default_headers=default_headers(ctx) if ctx else {},
    )

    tools = [search_amazon_policy, search_cross_border_news, generate_daily_report, send_daily_report_email]

    return create_agent(
        model=llm,
        system_prompt=cfg.get("sp"),
        tools=tools,
        checkpointer=get_memory_saver(),
        state_schema=AgentState,
    )
