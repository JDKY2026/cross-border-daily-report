"""联网搜索工具 - 搜索 Amazon 政策变动和跨境电商行业新闻"""

from langchain.tools import tool
from coze_coding_dev_sdk import SearchClient
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


def _do_web_search(query: str, count: int = 10, time_range: str = "1w") -> str:
    """执行联网搜索的公共逻辑"""
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
def search_amazon_policy(date: str) -> str:
    """搜索 Amazon 平台政策变动、费用调整、合规新规等信息。

    Args:
        date: 搜索日期，格式 YYYY-MM-DD，用于限定时间范围
    """
    queries = [
        f"Amazon policy change {date}",
        f"Amazon FBA fee update {date}",
        f"Amazon seller policy update {date}",
    ]

    all_results = []
    for q in queries:
        result = _do_web_search(query=q, count=5, time_range="1w")
        all_results.append(f"【搜索词: {q}】\n{result}")

    return "\n\n=====\n\n".join(all_results)


@tool
def search_cross_border_news(date: str) -> str:
    """搜索跨境电商行业重要新闻，包括关税政策、大卖动态、平台重大事件等。

    Args:
        date: 搜索日期，格式 YYYY-MM-DD，用于限定时间范围
    """
    queries = [
        f"cross-border ecommerce news {date}",
        f"Amazon seller news {date}",
        f"cross-border trade regulation {date}",
    ]

    all_results = []
    for q in queries:
        result = _do_web_search(query=q, count=5, time_range="1w")
        all_results.append(f"【搜索词: {q}】\n{result}")

    return "\n\n=====\n\n".join(all_results)
