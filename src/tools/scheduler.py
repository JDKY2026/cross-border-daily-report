"""日报定时调度器 - 每天早上8点自动触发日报生成并发送邮件"""

import importlib
import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _run_daily_report():
    """定时任务：构建 Agent 并触发日报生成（使用 importlib 避免循环导入）"""
    try:
        logger.info("[Scheduler] 定时任务触发：开始生成跨境电商日报")

        agent_module = importlib.import_module("agents.agent")
        build_agent = agent_module.build_agent

        agent = build_agent()
        today = datetime.now().strftime("%Y-%m-%d")
        message = f"请生成{today}的跨境电商日报，生成后请发送邮件通知。"

        config = {"configurable": {"thread_id": f"scheduler-{today}"}}
        result = agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )

        logger.info("[Scheduler] 日报生成任务完成")
    except Exception as e:
        logger.error(f"[Scheduler] 日报生成任务失败: {e}")


def start_scheduler():
    """启动定时调度器（幂等，多次调用只会启动一次）"""
    global _scheduler

    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("[Scheduler] 调度器已在运行中，跳过")
            return

        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        _scheduler.add_job(
            _run_daily_report,
            trigger=CronTrigger(hour=8, minute=0),
            id="daily_report_job",
            name="跨境电商日报生成",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("[Scheduler] 定时调度器已启动，每天 08:00 (Asia/Shanghai) 自动生成日报")


def stop_scheduler():
    """停止定时调度器"""
    global _scheduler
    with _lock:
        if _scheduler is not None and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("[Scheduler] 定时调度器已停止")
