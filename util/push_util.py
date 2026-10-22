import html
import json
import re
from datetime import datetime

import pytz
import requests


def get_beijing_time() -> datetime:
    """获取北京时间"""
    target_timezone = pytz.timezone("Asia/Shanghai")
    return datetime.now().astimezone(target_timezone)


def format_now() -> str:
    """格式化当前时间"""
    return get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")


class PushConfig:
    """推送配置类"""

    def __init__(
        self,
        push_plus_token: str | None = None,
        push_plus_hour: str | None = None,
        push_plus_max: int | str | None = 30,
        push_wechat_webhook_key: str | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
    ):
        self.push_plus_token = push_plus_token
        self.push_plus_hour = push_plus_hour
        self.push_plus_max = int(push_plus_max) if push_plus_max else 30
        self.push_wechat_webhook_key = push_wechat_webhook_key
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id


def push_plus(token: str, title: str, content: str) -> None:
    """
    推送消息到 PushPlus（HTML 格式）

    :param token: PUSHPLUS 的 token
    :param title: 推送标题
    :param content: 推送内容（HTML 格式）
    """
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html",
        "channel": "wechat",
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            json_res = response.json()
            print(f"pushplus推送完毕：{json_res['code']}-{json_res['msg']}")
        else:
            print("pushplus推送失败")
    except requests.exceptions.RequestException as e:
        print(f"pushplus推送网络异常: {e}")
    except Exception as e:
        print(f"pushplus推送未知异常: {e}")


def push_wechat_webhook(key: str, title: str, content: str) -> None:
    """
    推送企业微信通知（WebHook 方式）

    :param key: WebHook 机器人的 key
    :param title: 推送标题
    :param content: 推送内容（纯文本效果更佳）
    """
    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    payload = {
        "msgtype": "markdown_v2",
        "markdown_v2": {"content": _build_wechat_content(title, content)},
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            json_res = response.json()
            if json_res.get("errcode") == 0:
                print(f"企业微信推送完毕：{json_res['errmsg']}")
            else:
                print(f"企业微信推送失败：{json_res.get('errmsg', '未知错误')}")
        else:
            print("企业微信推送失败")
    except requests.exceptions.RequestException as e:
        print(f"企业微信推送异常: {e}")
    except Exception as e:
        print(f"企业微信推送发生未知异常: {e}")


def _build_wechat_content(title: str, content: str) -> str:
    """构建企业微信 Markdown 内容"""
    return f"# {title}\n{content}"


def push_telegram_bot(bot_token: str, chat_id: str, content: str) -> None:
    """
    推送消息到 Telegram Bot（HTML 格式）

    :param bot_token: Telegram Bot Token
    :param chat_id: Telegram Chat ID
    :param content: 推送内容（HTML 格式）
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": int(chat_id), "text": content, "parse_mode": "HTML"}

    print(f"post to url: {url}")
    print(f"payload: {json.dumps(payload)}")

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            json_res = response.json()
            if json_res.get("ok") is True:
                print(f"telegram bot推送完毕：{json_res['result']['message_id']}")
            else:
                print(f"telegram bot推送失败: {json.dumps(json_res)}")
        else:
            print(f"telegram bot推送失败: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"telegram bot推送异常: {e}")
    except Exception as e:
        print(f"telegram bot推送发生未知异常: {e}")


def push_results(exec_results: list[dict], summary: str, config: PushConfig) -> None:
    """推送所有结果"""
    if _not_in_push_time_range(config):
        return
    _push_to_push_plus(exec_results, summary, config)
    _push_to_wechat_webhook(exec_results, summary, config)
    _push_to_telegram_bot(exec_results, summary, config)


def _not_in_push_time_range(config: PushConfig) -> bool:
    """检查是否不在推送时间范围内"""
    if not config.push_plus_hour:
        return False  # 未设置推送时间则始终推送

    time_bj = get_beijing_time()

    # 直接匹配整点
    if config.push_plus_hour.isdigit():
        if time_bj.hour == int(config.push_plus_hour):
            print(
                f"当前设置推送整点为：{config.push_plus_hour}, "
                f"当前整点为：{time_bj.hour}，执行推送"
            )
            return False

    # 从 cron_change_time 文件中读取备用时间
    try:
        with open("cron_change_time", "r") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                match = re.search(r"北京时间\(0?(\d+):\d+\)", last_line)
                if match:
                    cron_hour = int(match.group(1))
                    if int(config.push_plus_hour) == cron_hour:
                        print(
                            f"当前设置推送整点为：{config.push_plus_hour}, "
                            f"根据执行记录，本次执行整点为：{cron_hour}，执行推送"
                        )
                        return False
    except Exception as e:
        print(f"读取cron_change_time文件出错: {e}")

    print(f"当前整点时间为：{time_bj}，不在配置的推送时间，不执行推送")
    return True


def _push_to_push_plus(exec_results: list[dict], summary: str, config: PushConfig) -> None:
    """推送到 PushPlus"""
    token = config.push_plus_token
    if not token or token == "NO":
        print("未配置 PUSH_PLUS_TOKEN 跳过PUSHPLUS推送")
        return

    # 构建 HTML 内容
    html_content = f"<div>{summary}</div>"
    if len(exec_results) >= config.push_plus_max:
        html_content += "<div>账号数量过多，详细情况请前往github actions中查看</div>"
    else:
        html_content += "<ul>"
        for result in exec_results:
            user = result["user"]
            msg = result["msg"]
            if result.get("success") is True:
                html_content += f"<li><span>账号：{user}</span>刷步数成功，接口返回：{msg}</li>"
            else:
                html_content += f"<li><span>账号：{user}</span>刷步数失败，失败原因：{msg}</li>"
        html_content += "</ul>"

    # 生成标题
    if len(exec_results) == 1:
        title_msg = html.escape(str(exec_results[0].get("msg", "无信息")))
    else:
        success_count = sum(1 for r in exec_results if r.get("success") is True)
        fail_count = len(exec_results) - success_count
        title_msg = f"成功{success_count}个/失败{fail_count}个"

    push_plus(token, title_msg, html_content)


def _push_to_wechat_webhook(exec_results: list[dict], summary: str, config: PushConfig) -> None:
    """推送到企业微信"""
    key = config.push_wechat_webhook_key
    if not key or key == "NO":
        print("未配置 WECHAT_WEBHOOK_KEY 跳过微信推送")
        return

    content = f"## {summary}"
    if len(exec_results) >= config.push_plus_max:
        content += "\n- 账号数量过多，详细情况请前往github actions中查看"
    else:
        for result in exec_results:
            user = result["user"]
            msg = result["msg"]
            if result.get("success") is True:
                content += f"\n- 账号：{user}刷步数成功，接口返回：{msg}"
            else:
                content += f"\n- 账号：{user}刷步数失败，失败原因：{msg}"

    push_wechat_webhook(key, f"{format_now()} 刷步数通知", content)


def _push_to_telegram_bot(exec_results: list[dict], summary: str, config: PushConfig) -> None:
    """推送到 Telegram"""
    token = config.telegram_bot_token
    chat_id = config.telegram_chat_id
    if not token or token == "NO" or not chat_id:
        print("未配置 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 跳过telegram推送")
        return

    html_content = f"<b>{summary}</b>"
    if len(exec_results) >= config.push_plus_max:
        html_content += "<blockquote>账号数量过多，详细情况请前往github actions中查看</blockquote>"
    else:
        for result in exec_results:
            user = result["user"]
            msg = result["msg"]
            if result.get("success") is True:
                html_content += (
                    f"<pre><blockquote>账号：{user}</blockquote>"
                    f"刷步数成功，接口返回：<b>{msg}</b></pre>"
                )
            else:
                html_content += (
                    f"<pre><blockquote>账号：{user}</blockquote>"
                    f"刷步数失败，失败原因：<b>{msg}</b></pre>"
                )

    push_telegram_bot(token, chat_id, html_content)
