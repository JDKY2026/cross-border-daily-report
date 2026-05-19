"""邮件发送工具 - 将日报链接通过邮件推送给用户"""

import json
import smtplib
import ssl
import time
import os
import logging
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid

from langchain.tools import tool
from coze_workload_identity import Client
from cozeloop.decorator import observe
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context

logger = logging.getLogger(__name__)


def _get_email_config() -> dict:
    """获取邮件配置信息"""
    client = Client()
    email_credential = client.get_integration_credential("integration-email-imap-smtp")
    return json.loads(email_credential)


@observe
def _send_html_email(subject: str, html_content: str, to_addrs: list) -> dict:
    """发送 HTML 格式邮件的内部实现"""
    try:
        config = _get_email_config()
        # 兼容处理: QQ邮箱账号可能是手机号格式，需要补全 @qq.com 后缀
        account = config["account"]
        if not "@" in account:
            account = f"{account}@qq.com"

        msg = MIMEText(html_content, "html", "utf-8")
        msg["From"] = formataddr(("跨境电商日报", account))
        msg["To"] = ", ".join(to_addrs) if to_addrs else ""
        msg["Subject"] = Header(subject, "utf-8")
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        if not to_addrs:
            return {"status": "error", "message": "收件人为空"}

        ctx = ssl.create_default_context()

        attempts = 3
        last_err = None
        for i in range(attempts):
            try:
                with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=ctx, timeout=30) as server:
                    server.ehlo()
                    server.login(account, config["auth_code"])
                    server.sendmail(account, to_addrs, msg.as_string())
                    server.quit()
                return {"status": "success", "message": f"邮件成功发送给 {len(to_addrs)} 位收件人"}
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, smtplib.SMTPDataError,
                    smtplib.SMTPHeloError, ssl.SSLError, OSError) as e:
                last_err = e
                time.sleep(1 * (i + 1))

        return {"status": "error", "message": f"发送失败: {type(last_err).__name__}"}
    except smtplib.SMTPAuthenticationError as e:
        return {"status": "error", "message": f"认证失败: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"发送失败: {str(e)}"}


def _build_email_html(date: str, report_url: str, policy_count: int, industry_count: int) -> str:
    """构建邮件正文 HTML"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:32px 20px;">
    <div style="background:linear-gradient(135deg,#1e1b4b,#4338ca);border-radius:16px 16px 0 0;padding:32px 28px;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:rgba(255,255,255,0.6);letter-spacing:1px;">CROSS-BORDER DAILY</p>
        <h1 style="margin:0;font-size:24px;color:#fff;font-weight:700;">跨境电商日报</h1>
        <p style="margin:8px 0 0;font-size:14px;color:rgba(255,255,255,0.7);">{date}</p>
    </div>
    <div style="background:#fff;border-radius:0 0 16px 16px;padding:28px;box-shadow:0 4px 12px rgba(0,0,0,0.06);">
        <div style="display:flex;margin-bottom:24px;">
            <div style="flex:1;text-align:center;padding:12px;background:#eef2ff;border-radius:10px;margin-right:8px;">
                <div style="font-size:24px;font-weight:700;color:#4f46e5;">{policy_count}</div>
                <div style="font-size:12px;color:#6366f1;margin-top:2px;">政策变动</div>
            </div>
            <div style="flex:1;text-align:center;padding:12px;background:#f0f9ff;border-radius:10px;margin-left:8px;">
                <div style="font-size:24px;font-weight:700;color:#0284c7;">{industry_count}</div>
                <div style="font-size:12px;color:#0ea5e9;margin-top:2px;">行业动态</div>
            </div>
        </div>
        <a href="{report_url}" target="_blank" style="display:block;background:linear-gradient(135deg,#6366f1,#4f46e5);color:#fff;text-align:center;padding:14px 24px;border-radius:10px;text-decoration:none;font-size:15px;font-weight:600;letter-spacing:0.5px;">
            查看完整日报 &#10132;
        </a>
        <p style="margin:16px 0 0;font-size:12px;color:#94a3b8;text-align:center;">点击上方按钮在浏览器中打开日报网页</p>
    </div>
    <p style="margin:16px 0 0;text-align:center;font-size:11px;color:#94a3b8;">由跨境电商日报 Agent 自动生成推送</p>
</div>
</body>
</html>"""


@tool
def send_daily_report_email(date: str, report_url: str, policy_count: int, industry_count: int) -> str:
    """将生成的日报链接通过邮件推送给用户。在生成日报网页后调用此工具发送邮件通知。

    Args:
        date: 日报日期，格式 YYYY-MM-DD
        report_url: 日报网页的访问链接
        policy_count: 政策变动条数
        industry_count: 行业动态条数
    """
    recipient = os.getenv("DAILY_REPORT_RECIPIENT_EMAIL", "")
    if not recipient:
        return "未配置收件人邮箱，请在环境变量 DAILY_REPORT_RECIPIENT_EMAIL 中设置"

    to_addrs = [addr.strip() for addr in recipient.split(",") if addr.strip()]
    if not to_addrs:
        return "收件人邮箱为空，请检查配置"

    subject = f"跨境电商日报 | {date}"
    html_content = _build_email_html(
        date=date,
        report_url=report_url,
        policy_count=policy_count,
        industry_count=industry_count,
    )

    result = _send_html_email(subject=subject, html_content=html_content, to_addrs=to_addrs)

    if result.get("status") == "success":
        return f"日报邮件已成功发送至 {', '.join(to_addrs)}"
    else:
        return f"邮件发送失败: {result.get('message', '未知错误')}"
