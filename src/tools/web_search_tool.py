"""联网搜索工具 - 搜索 Amazon 政策变动和跨境电商行业新闻"""

from datetime import datetime, timedelta

from langchain.tools import tool
from coze_coding_dev_sdk import SearchClient
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


def _today_str() -> str:
    """获取当前日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def _yesterday_str() -> str:
    """获取昨天日期字符串"""
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def _do_web_search(query: str, count: int = 10, time_range: str = "1d") -> str:
    """执行联网搜索的公共逻辑
    
    Args:
        query: 搜索关键词
        count: 返回结果数量
        time_range: 时间范围，1d=1天, 1w=1周, 1m=1月
    """
    ctx = request_context.get() or new_context(method="web_search")
    client = SearchClient(ctx=ctx)
    response = client.search(
        query=query,
        search_type="web",
        count=count,
        need_url=True,
        need_summary=True,
        time_range=time_range,
    )

    if not response.web_items:
        return f"未找到与 '{query}' 相关的结果"

    results = []
    for item in response.web_items:
        result = {
            "title": item.title or "",
            "snippet": item.snippet or "",
            "summary": item.summary or "",
            "source_url": item.url or "",
            "source_name": item.site_name or "",
            "publish_time": item.publish_time or "",
        }
        results.append(str(result))

    return "\n---\n".join(results)


@tool
def search_amazon_policy(date: str = "") -> str:
    """搜索 Amazon 平台最新的政策变动、费用调整、合规新规等信息。无需传入日期参数，工具会自动使用当前日期。
    搜索策略：先用1天范围搜索当天最新，再用1周范围补充遗漏。

    Args:
        date: 无需传入，保留参数兼容
    """
    # 第一轮：当天最新（time_range=1d），用不带日期的关键词
    latest_queries = [
        "亚马逊 政策 新规 最新",
        "Amazon policy update new",
        "亚马逊 FBA 费用 变动",
    ]

    # 第二轮：近1周范围，用更具体的日期关键词补充
    today = _today_str()
    week_queries = [
        f"亚马逊 卖家 政策 {today}",
        f"Amazon seller policy change {today}",
    ]

    all_results = []

    # 优先搜索当天最新
    for q in latest_queries:
        result = _do_web_search(query=q, count=5, time_range="1d")
        all_results.append(f"【当天最新 | 搜索词: {q}】\n{result}")

    # 补充近一周
    for q in week_queries:
        result = _do_web_search(query=q, count=5, time_range="1w")
        all_results.append(f"【近一周 | 搜索词: {q}】\n{result}")

    return "\n\n=====\n\n".join(all_results)


@tool
def search_cross_border_news(date: str = "") -> str:
    """搜索跨境电商行业最新新闻，包括关税政策、大卖动态、平台重大事件等。无需传入日期参数，工具会自动使用当前日期。
    搜索策略：先用1天范围搜索当天最新，再用1周范围补充遗漏。

    Args:
        date: 无需传入，保留参数兼容
    """
    # 第一轮：当天最新
    latest_queries = [
        "跨境电商 最新 新闻 今天",
        "cross-border ecommerce news today",
        "跨境电商 关税 政策 最新",
    ]

    # 第二轮：近1周补充
    today = _today_str()
    week_queries = [
        f"跨境电商 行业 动态 {today}",
        f"Amazon seller news {today}",
    ]

    all_results = []

    for q in latest_queries:
        result = _do_web_search(query=q, count=5, time_range="1d")
        all_results.append(f"【当天最新 | 搜索词: {q}】\n{result}")

    for q in week_queries:
        result = _do_web_search(query=q, count=5, time_range="1w")
        all_results.append(f"【近一周 | 搜索词: {q}】\n{result}")

    return "\n\n=====\n\n".join(all_results)
