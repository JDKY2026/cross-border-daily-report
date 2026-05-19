"""日报生成与上传工具 - 将整理好的数据生成 HTML 网页并上传至对象存储"""

import json
import os
from datetime import datetime

from langchain.tools import tool
from coze_coding_dev_sdk.s3 import S3SyncStorage
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


def _build_html(date: str, policy_items: list, industry_items: list) -> str:
    """构建日报 HTML 页面"""

    def _render_items(items: list) -> str:
        if not items:
            return '<p style="color:#999;">暂无相关信息</p>'
        cards = []
        for item in items:
            title = item.get("title", "无标题")
            summary = item.get("summary", "")
            source_url = item.get("source_url", "#")
            source_name = item.get("source_name", "")
            publish_time = item.get("publish_time", "")
            card = f"""
            <div class="card">
                <a class="card-title" href="{source_url}" target="_blank" rel="noopener noreferrer">{title}</a>
                <p class="card-summary">{summary}</p>
                <p class="card-meta">{source_name}{" · " + publish_time if publish_time else ""}</p>
            </div>"""
            cards.append(card)
        return "\n".join(cards)

    policy_html = _render_items(policy_items)
    industry_html = _render_items(industry_items)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>跨境电商日报 | {date}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                         "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 20px 16px;
        }}
        .header {{
            text-align: center;
            padding: 32px 0 24px;
            border-bottom: 2px solid #e8ecf1;
            margin-bottom: 28px;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: 600;
            color: #1a1a2e;
        }}
        .header .date {{
            font-size: 14px;
            color: #8899aa;
            margin-top: 6px;
        }}
        .section {{
            margin-bottom: 32px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a2e;
            padding-bottom: 10px;
            border-bottom: 1px solid #e8ecf1;
            margin-bottom: 16px;
        }}
        .card {{
            background: #fff;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            transition: box-shadow 0.2s;
        }}
        .card:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .card-title {{
            font-size: 15px;
            font-weight: 500;
            color: #2b6cb0;
            text-decoration: none;
            display: block;
            margin-bottom: 6px;
        }}
        .card-title:hover {{
            text-decoration: underline;
        }}
        .card-summary {{
            font-size: 14px;
            color: #555;
            margin-bottom: 6px;
        }}
        .card-meta {{
            font-size: 12px;
            color: #999;
        }}
        .footer {{
            text-align: center;
            padding: 24px 0 16px;
            font-size: 12px;
            color: #bbb;
            border-top: 1px solid #e8ecf1;
            margin-top: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>跨境电商日报</h1>
            <div class="date">{date}</div>
        </div>

        <div class="section">
            <div class="section-title">📋 政策变动</div>
            {policy_html}
        </div>

        <div class="section">
            <div class="section-title">📰 行业动态</div>
            {industry_html}
        </div>

        <div class="footer">
            生成时间：{now}
        </div>
    </div>
</body>
</html>"""
    return html


def _upload_to_s3(html_content: str, date: str) -> str:
    """上传 HTML 到对象存储，返回可访问的 URL"""
    ctx = request_context.get() or new_context(method="upload_daily_report")

    storage = S3SyncStorage(
        endpoint_url=os.getenv("COZE_BUCKET_ENDPOINT_URL"),
        access_key="",
        secret_key="",
        bucket_name=os.getenv("COZE_BUCKET_NAME"),
        region="cn-beijing",
    )

    file_name = f"daily-reports/daily-report-{date}.html"
    file_key = storage.upload_file(
        file_content=html_content.encode("utf-8"),
        file_name=file_name,
        content_type="text/html; charset=utf-8",
    )

    signed_url = storage.generate_presigned_url(key=file_key, expire_time=86400)
    return signed_url


def _parse_data_param(data):
    """解析工具入参，兼容 JSON 字符串和已经解析的 list/dict"""
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        if not data.strip():
            return []
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except json.JSONDecodeError:
            return [{"title": "数据解析失败", "summary": data[:200], "source_url": "#", "source_name": "", "publish_time": ""}]
    return []


@tool
def generate_daily_report(policy_data: str, industry_data: str, date: str) -> str:
    """将搜索到的政策变动和行业动态数据整理为 HTML 日报网页，上传至对象存储并返回可访问的 URL。

    Args:
        policy_data: 政策变动数据，JSON 格式字符串，每个元素包含 title/summary/source_url/source_name/publish_time
        industry_data: 行业动态数据，JSON 格式字符串，每个元素包含 title/summary/source_url/source_name/publish_time
        date: 日报日期，格式 YYYY-MM-DD
    """
    policy_items = _parse_data_param(policy_data)
    industry_items = _parse_data_param(industry_data)

    html = _build_html(date=date, policy_items=policy_items, industry_items=industry_items)

    # 先保存到 /tmp
    tmp_path = f"/tmp/daily-report-{date}.html"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 上传到对象存储
    url = _upload_to_s3(html_content=html, date=date)

    return f"日报已生成并上传成功！\n日期：{date}\n访问链接：{url}"
