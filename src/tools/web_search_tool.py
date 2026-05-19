"""联网搜索工具 - 搜索 Amazon 政策变动和跨境电商行业新闻

优先从指定来源搜索：亿邦动力(ebrun.com)、出海网(chwe.cn)、大数跨境(10100.com)
"""

from datetime import datetime

from langchain.tools import tool
from coze_coding_dev_sdk import SearchClient
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


PREFERRED_SOURCES = [
    {"name": "亿邦动力", "domain": "ebrun.com"},
    {"name": "出海网", "domain": "chwe.cn"},
    {"name": "大数跨境", "domain": "10100.com"},
]


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _search(query: str, count: int = 3, time_range: str = "1w") -> list:
    """执行搜索，返回极简结果"""
    ctx = request_context.get() or new_context(method="web_search")
    client = SearchClient(ctx=ctx)
    response = client.search(
        query=query,
        search_type="web",
        count=count,
        need_url=True,
        need_summary=False,
        time_range=time_range,
    )
    if not response.web_items:
        return []
    results = []
    for item in response.web_items:
        results.append({
            "t": item.title or "",
            "s": (item.snippet or "")[:80],
            "u": item.url or "",
            "n": item.site_name or "",
            "p": item.publish_time or "",
        })
    return results


def _compact(results: list) -> str:
    """将结果压缩为极简文本"""
    if not results:
        return ""
    lines = []
    for r in results:
        lines.append(f"{r['t']} | {r['n']} | {r['p']}\n{r['s']}\n{r['u']}")
    return "\n".join(lines)


@tool
def search_daily_news(date: str = "") -> str:
    """一次性搜索跨境电商全部信息，包括 Amazon 政策变动和行业新闻。无需传入日期参数。
    搜索来源优先级：亿邦动力 > 出海网 > 大数跨境 > 其他。

    Args:
        date: 无需传入，保留参数兼容
    """
    today = _today_str()
    parts = []

    # 指定来源搜索 Amazon 政策（每个来源1条，近一周）
    for src in PREFERRED_SOURCES:
        rs = _search(f"亚马逊 政策 新规 site:{src['domain']}", count=1, time_range="1w")
        if rs:
            parts.append(f"[政策|{src['name']}]\n" + _compact(rs))

    # 指定来源搜索行业新闻（每个来源1条，近一周）
    for src in PREFERRED_SOURCES:
        rs = _search(f"跨境电商 新闻 site:{src['domain']}", count=1, time_range="1w")
        if rs:
            parts.append(f"[新闻|{src['name']}]\n" + _compact(rs))

    # 通用兜底（各2条当天）
    rs = _search("亚马逊 政策 新规 最新", count=2, time_range="1d")
    if rs:
        parts.append("[政策|通用]\n" + _compact(rs))
    rs = _search("跨境电商 最新 新闻", count=2, time_range="1d")
    if rs:
        parts.append("[新闻|通用]\n" + _compact(rs))

    if not parts:
        return f"今日({today})暂未找到相关新闻"

    return f"日期:{today}\n\n" + "\n\n".join(parts)
