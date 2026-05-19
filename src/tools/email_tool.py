"""邮件发送工具 - 将完整 HTML 日报内容嵌入邮件正文发送给用户"""

import json
import smtplib
import ssl
import time
import os
import logging
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid

from coze_workload_identity import Client
from cozeloop.decorator import observe

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
        if "@" not in account:
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


def send_report_email(html_content: str, date: str) -> str:
    """发送完整 HTML 日报邮件（非 @tool，供其他工具内部调用）

    Args:
        html_content: 完整的 HTML 日报内容
        date: 日报日期

    Returns:
        发送结果描述
    """
    recipient = os.getenv("DAILY_REPORT_RECIPIENT_EMAIL", "")
    if not recipient:
        return "未配置收件人邮箱，跳过邮件发送"

    to_addrs = [addr.strip() for addr in recipient.split(",") if addr.strip()]
    if not to_addrs:
        return "收件人邮箱为空，跳过邮件发送"

    # 构建邮件 HTML：用简洁的邮件包裹层 + 日报内容
    email_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f5f5f5;">
<div style="max-width:700px; margin:0 auto; padding:12px;">
<div style="background:#fff; border-radius:8px; padding:16px; font-family:sans-serif; font-size:13px; color:#666; text-align:center; margin-bottom:12px;">
📧 跨境电商日报 | {date} | 由 Agent 自动生成推送
</div>
{html_content}
<div style="background:#fff; border-radius:8px; padding:16px; font-family:sans-serif; font-size:12px; color:#999; text-align:center; margin-top:12px;">
本邮件由跨境电商日报 Agent 自动生成，内容来源于亿邦动力、出海网、大数跨境等权威媒体
</div>
</div>
</body>
</html>"""

    subject = f"📰 跨境电商日报 | {date}"
    result = _send_html_email(subject=subject, html_content=email_html, to_addrs=to_addrs)

    if result.get("status") == "success":
        return f"日报邮件已发送至 {', '.join(to_addrs)}"
    else:
        return f"邮件发送失败: {result.get('message', '未知错误')}"
