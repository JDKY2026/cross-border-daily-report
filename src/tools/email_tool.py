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
def _send_email(subject: str, content: str, to_addrs: list) -> dict:
    """发送纯文本邮件的内部实现 - 纯文本格式不易被邮箱风控拦截"""
    try:
        config = _get_email_config()
        # 兼容处理: QQ邮箱账号可能是手机号格式，需要补全 @qq.com 后缀
        account = config["account"]
        if not "@" in account:
            account = f"{account}@qq.com"

        msg = MIMEText(content, "plain", "utf-8")
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


def _build_email_content(date: str, report_url: str, policy_count: int, industry_count: int) -> str:
    """构建邮件正文 - 使用简洁纯文本+链接格式，避免被 QQ 邮箱风控拦截"""
    return f"""跨境电商日报 | {date}

━━━━━━━━━━━━━━━━━━

📊 今日概览
  · 政策变动：{policy_count} 条
  · 行业动态：{industry_count} 条

━━━━━━━━━━━━━━━━━━

🔗 点击查看完整日报（含详细摘要与来源链接）：
{report_url}

━━━━━━━━━━━━━━━━━━

提示：点击上方链接在浏览器中打开，即可查看完整日报网页。
本邮件由跨境电商日报 Agent 自动生成推送。"""


@tool
def send_daily_report_email(report_url: str, policy_count: int, industry_count: int, date: str = "") -> str:
    """将生成的日报链接通过邮件推送给用户。在生成日报网页后调用此工具发送邮件通知。无需传入日期参数，工具会自动使用当前日期。

    Args:
        report_url: 日报网页的访问链接
        policy_count: 政策变动条数
        industry_count: 行业动态条数
        date: 无需传入，保留参数兼容，工具会自动使用当前日期
    """
    if not date:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
    else:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
    recipient = os.getenv("DAILY_REPORT_RECIPIENT_EMAIL", "")
    if not recipient:
        return "未配置收件人邮箱，请在环境变量 DAILY_REPORT_RECIPIENT_EMAIL 中设置"

    to_addrs = [addr.strip() for addr in recipient.split(",") if addr.strip()]
    if not to_addrs:
        return "收件人邮箱为空，请检查配置"

    subject = f"跨境电商日报 | {date}"
    content = _build_email_content(
        date=date,
        report_url=report_url,
        policy_count=policy_count,
        industry_count=industry_count,
    )

    result = _send_email(subject=subject, content=content, to_addrs=to_addrs)

    if result.get("status") == "success":
        return f"日报邮件已成功发送至 {', '.join(to_addrs)}"
    else:
        return f"邮件发送失败: {result.get('message', '未知错误')}"
