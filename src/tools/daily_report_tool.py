"""日报生成与上传工具 - 将整理好的数据生成 HTML 网页并上传至对象存储"""

import json
import os
from datetime import datetime

from langchain.tools import tool
from coze_coding_dev_sdk.s3 import S3SyncStorage
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


def _format_publish_time(raw: str) -> str:
    """将 ISO 时间格式化为简洁的日期显示"""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return raw[:16] if len(raw) > 16 else raw


def _build_html(date: str, policy_items: list, industry_items: list) -> str:
    """构建日报 HTML 页面 - 现代专业风格"""

    policy_count = len(policy_items)
    industry_count = len(industry_items)

    def _render_section(items: list, section_type: str) -> str:
        if not items:
            empty_icon = "&#128203;" if section_type == "policy" else "&#128240;"
            return f'<div class="empty-state"><span class="empty-icon">{empty_icon}</span><p>今日暂无相关信息</p></div>'

        cards = []
        for idx, item in enumerate(items, 1):
            title = item.get("title", "无标题")
            summary = item.get("summary", "")
            source_url = item.get("source_url", "#")
            source_name = item.get("source_name", "")
            publish_time = _format_publish_time(item.get("publish_time", ""))

            tag_class = "tag-policy" if section_type == "policy" else "tag-industry"
            accent_class = "accent-policy" if section_type == "policy" else "accent-industry"

            card = f"""
            <a class="card {accent_class}" href="{source_url}" target="_blank" rel="noopener noreferrer">
                <div class="card-header">
                    <span class="card-index">{idx:02d}</span>
                    <span class="card-tag {tag_class}">{"政策" if section_type == "policy" else "行业"}</span>
                </div>
                <h3 class="card-title">{title}</h3>
                <p class="card-summary">{summary}</p>
                <div class="card-footer">
                    <span class="card-source">{source_name}</span>
                    {f'<span class="card-time">{publish_time}</span>' if publish_time else ''}
                </div>
            </a>"""
            cards.append(card)
        return "\n".join(cards)

    policy_html = _render_section(policy_items, "policy")
    industry_html = _render_section(industry_items, "industry")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 提取日期组件用于显示
    date_parts = date.split("-")
    display_year = date_parts[0] if len(date_parts) > 0 else ""
    display_month = date_parts[1] if len(date_parts) > 1 else ""
    display_day = date_parts[2] if len(date_parts) > 2 else ""

    # 星期几
    try:
        weekday_names = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"]
        weekday = weekday_names[datetime.strptime(date, "%Y-%m-%d").weekday()]
    except Exception:
        weekday = ""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>跨境电商日报 | {{date}}</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #ffffff;
            --bg-card-hover: #f8fafc;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --accent-policy: #6366f1;
            --accent-policy-light: #eef2ff;
            --accent-policy-dark: #4f46e5;
            --accent-industry: #0ea5e9;
            --accent-industry-light: #f0f9ff;
            --accent-industry-dark: #0284c7;
            --border-light: #e2e8f0;
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.05);
            --radius: 12px;
            --radius-lg: 16px;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI",
                         "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: #f1f5f9;
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* ===== Hero Banner ===== */
        .hero {{
            background: linear-gradient(135deg, #1e1b4b 0%, #312e81 30%, #4338ca 60%, #6366f1 100%);
            padding: 48px 24px 56px;
            position: relative;
            overflow: hidden;
        }}
        .hero::before {{
            content: "";
            position: absolute;
            top: -50%;
            right: -20%;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(129,140,248,0.2) 0%, transparent 70%);
            border-radius: 50%;
        }}
        .hero::after {{
            content: "";
            position: absolute;
            bottom: -30%;
            left: -10%;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%);
            border-radius: 50%;
        }}
        .hero-inner {{
            max-width: 860px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }}
        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255,255,255,0.12);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 13px;
            color: rgba(255,255,255,0.9);
            margin-bottom: 20px;
            letter-spacing: 0.5px;
        }}
        .hero-badge .dot {{
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #34d399;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}
        .hero h1 {{
            font-size: 32px;
            font-weight: 700;
            color: #fff;
            letter-spacing: -0.5px;
            margin-bottom: 8px;
        }}
        .hero-date {{
            font-size: 15px;
            color: rgba(255,255,255,0.7);
            font-weight: 400;
        }}
        .hero-stats {{
            display: flex;
            gap: 16px;
            margin-top: 28px;
        }}
        .stat-card {{
            flex: 1;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: var(--radius);
            padding: 16px 20px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 28px;
            font-weight: 700;
            color: #fff;
            line-height: 1.2;
        }}
        .stat-label {{
            font-size: 12px;
            color: rgba(255,255,255,0.6);
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        /* ===== Main Content ===== */
        .main {{
            max-width: 860px;
            margin: -24px auto 0;
            padding: 0 16px 40px;
            position: relative;
            z-index: 2;
        }}

        /* ===== Section ===== */
        .section {{
            margin-bottom: 36px;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--border-light);
        }}
        .section-icon {{
            width: 36px;
            height: 36px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }}
        .section-icon.policy {{
            background: var(--accent-policy-light);
        }}
        .section-icon.industry {{
            background: var(--accent-industry-light);
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 650;
            color: var(--text-primary);
            letter-spacing: -0.2px;
        }}
        .section-count {{
            margin-left: auto;
            font-size: 13px;
            color: var(--text-muted);
            background: #f1f5f9;
            padding: 3px 10px;
            border-radius: 12px;
        }}

        /* ===== Card ===== */
        .card {{
            display: block;
            background: var(--bg-card);
            border-radius: var(--radius);
            padding: 20px 24px;
            margin-bottom: 10px;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-light);
            text-decoration: none;
            color: inherit;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
        }}
        .card::before {{
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            border-radius: 0 3px 3px 0;
        }}
        .card.accent-policy::before {{
            background: var(--accent-policy);
        }}
        .card.accent-industry::before {{
            background: var(--accent-industry);
        }}
        .card:hover {{
            box-shadow: var(--shadow-lg);
            border-color: transparent;
            transform: translateY(-1px);
        }}
        .card.accent-policy:hover {{
            border-color: rgba(99,102,241,0.2);
        }}
        .card.accent-industry:hover {{
            border-color: rgba(14,165,233,0.2);
        }}

        .card-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
        }}
        .card-index {{
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted);
            font-variant-numeric: tabular-nums;
        }}
        .card-tag {{
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 6px;
            letter-spacing: 0.3px;
        }}
        .tag-policy {{
            background: var(--accent-policy-light);
            color: var(--accent-policy-dark);
        }}
        .tag-industry {{
            background: var(--accent-industry-light);
            color: var(--accent-industry-dark);
        }}

        .card-title {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.5;
            margin-bottom: 8px;
            letter-spacing: -0.1px;
        }}

        .card-summary {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.7;
            margin-bottom: 12px;
        }}

        .card-footer {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .card-source {{
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 500;
        }}
        .card-time {{
            font-size: 12px;
            color: var(--text-muted);
        }}
        .card-time::before {{
            content: "\\00B7";
            margin-right: 12px;
        }}

        /* ===== Empty State ===== */
        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            background: var(--bg-card);
            border-radius: var(--radius);
            border: 1px dashed var(--border-light);
        }}
        .empty-icon {{
            font-size: 32px;
            display: block;
            margin-bottom: 8px;
            opacity: 0.4;
        }}
        .empty-state p {{
            color: var(--text-muted);
            font-size: 14px;
        }}

        /* ===== Footer ===== */
        .report-footer {{
            text-align: center;
            padding: 28px 0 16px;
            border-top: 1px solid var(--border-light);
            margin-top: 8px;
        }}
        .footer-text {{
            font-size: 12px;
            color: var(--text-muted);
        }}
        .footer-brand {{
            font-weight: 600;
            color: var(--text-secondary);
        }}

        /* ===== Responsive ===== */
        @media (max-width: 640px) {{
            .hero {{
                padding: 36px 16px 48px;
            }}
            .hero h1 {{
                font-size: 24px;
            }}
            .hero-stats {{
                gap: 10px;
            }}
            .stat-card {{
                padding: 12px 14px;
            }}
            .stat-number {{
                font-size: 22px;
            }}
            .card {{
                padding: 16px 18px;
            }}
            .card-title {{
                font-size: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="hero">
        <div class="hero-inner">
            <div class="hero-badge">
                <span class="dot"></span>
                Cross-border Daily
            </div>
            <h1>跨境电商日报</h1>
            <div class="hero-date">{display_year}年{display_month}月{display_day}日 {weekday}</div>
            <div class="hero-stats">
                <div class="stat-card">
                    <div class="stat-number">{policy_count}</div>
                    <div class="stat-label">政策变动</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{industry_count}</div>
                    <div class="stat-label">行业动态</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{policy_count + industry_count}</div>
                    <div class="stat-label">今日要闻</div>
                </div>
            </div>
        </div>
    </div>

    <div class="main">
        <div class="section">
            <div class="section-header">
                <div class="section-icon policy">&#128220;</div>
                <div class="section-title">政策变动</div>
                <div class="section-count">{policy_count} 条</div>
            </div>
            {policy_html}
        </div>

        <div class="section">
            <div class="section-header">
                <div class="section-icon industry">&#128240;</div>
                <div class="section-title">行业动态</div>
                <div class="section-count">{industry_count} 条</div>
            </div>
            {industry_html}
        </div>

        <div class="report-footer">
            <p class="footer-text">由 <span class="footer-brand">跨境电商日报 Agent</span> 自动生成 &middot; {now}</p>
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
def generate_daily_report(policy_data: str, industry_data: str, date: str = "") -> str:
    """将搜索到的政策变动和行业动态数据整理为 HTML 日报网页，上传至对象存储并返回可访问的 URL。无需传入日期参数，工具会自动使用当前日期。

    Args:
        policy_data: 政策变动数据，JSON 格式字符串，每个元素包含 title/summary/source_url/source_name/publish_time
        industry_data: 行业动态数据，JSON 格式字符串，每个元素包含 title/summary/source_url/source_name/publish_time
        date: 无需传入，保留参数兼容，工具会自动使用当前日期
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    else:
        date = datetime.now().strftime("%Y-%m-%d")
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
