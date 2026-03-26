#!/usr/bin/env python3
# _*_ coding:utf-8 _*_
# 微信读书自动阅读脚本（青龙版）
# 环境变量说明：
#   wxread_curl_bash: 必选，微信读书 read 接口的 curl 命令
#   wxread_read_num: 可选，阅读次数，默认 40 次（20 分钟）
#   wxread_push_method: 可选，推送方式 (pushplus/wxpusher/telegram/serverchan)
#   wxread_push_token: 可选，对应推送方式的 token

import os
import re
import json
import time
import random
import logging
import hashlib
import requests
import urllib.parse

# 青龙环境变量获取
def get_env(key, default=None):
    return os.getenv(key) or os.getenv(key.lower()) or default

# 配置
READ_NUM = int(get_env('wxread_read_num') or 40)
PUSH_METHOD = get_env('wxread_push_method')
PUSHPLUS_TOKEN = get_env('wxread_pushplus_token')
WXPUSHER_SPT = get_env('wxpusher_spt')
TELEGRAM_BOT_TOKEN = get_env('telegram_bot_token')
TELEGRAM_CHAT_ID = get_env('telegram_chat_id')
SERVERCHAN_SPT = get_env('serverchan_spt')
CURL_BASH = get_env('wxread_curl_bash')

# 加密盐及其它默认值
KEY = "3c5c8717f3daf09iop3423zafeqoi"
COOKIE_DATA = {"rq": "%2Fweb%2Fbook%2Fread", "ql": True}
READ_URL = "https://weread.qq.com/web/book/read"
RENEW_URL = "https://weread.qq.com/web/login/renewal"
FIX_SYNCKEY_URL = "https://weread.qq.com/web/book/chapterInfos"

# 默认 headers/cookies（当未提供 curl_bash 时使用）
DEFAULT_COOKIES = {
    'RK': 'oxEY1bTnXf',
    'ptcz': '53e3b35a9486dd63c4d06430b05aa169402117fc407dc5cc9329b41e59f62e2b',
    'pac_uid': '0_e63870bcecc18',
    'iip': '0',
    '_qimei_uuid42': '183070d3135100ee797b08bc922054dc3062834291',
    'wr_avatar': 'https%3A%2F%2Fthirdwx.qlogo.cn%2Fmmopen%2Fvi_32%2FeEOpSbFh2Mb1bUxMW9Y3FRPfXwWvOLaNlsjWIkcKeeNg6vlVS5kOVuhNKGQ1M8zaggLqMPmpE5qIUdqEXlQgYg%2F132',
    'wr_gender': '0',
}

DEFAULT_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,ko;q=0.5',
    'baggage': 'sentry-environment=production,sentry-release=dev-1730698697208,sentry-public_key=ed67ed71f7804a038e898ba54bd66e44,sentry-trace_id=1ff5a0725f8841088b42f97109c45862',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
}

# 书籍和章节 ID 池
BOOK_IDS = [
    "36d322f07186022636daa5e", "6f932ec05dd9eb6f96f14b9", "43f3229071984b9343f04a4", "d7732ea0813ab7d58g0184b8",
    "3d03298058a9443d052d409", "4fc328a0729350754fc56d4", "a743220058a92aa746632c0", "140329d0716ce81f140468e",
    "1d9321c0718ff5e11d9afe8", "ff132750727dc0f6ff1f7b5", "e8532a40719c4eb7e851cbe", "9b13257072562b5c9b1c8d6"
]

CHAPTER_IDS = [
    "ecc32f3013eccbc87e4b62e", "a87322c014a87ff679a21ea", "e4d32d5015e4da3b7fbb1fa", "16732dc0161679091c5aeb1",
    "8f132430178f14e45fce0f7", "c9f326d018c9f0f895fb5e4", "45c322601945c48cce2e120", "d3d322001ad3d9446802347",
    "65132ca01b6512bd43d90e3", "c20321001cc20ad4d76f5ae", "c51323901dc51ce410c121b", "aab325601eaab3238922e53",
    "9bf32f301f9bf31c7ff0a60", "c7432af0210c74d97b01b1c", "70e32fb021170efdf2eca12", "6f4322302126f4922f45dec"
]

# 默认阅读数据（三体）
DEFAULT_DATA = {
    "appId": "wb182564874603h266381671",
    "b": "ce032b305a9bc1ce0b0dd2a",
    "c": "7f632b502707f6ffaa6bf2e",
    "ci": 27,
    "co": 389,
    "sm": "19 聚会《三体》网友的聚会地点是一处僻静",
    "pr": 74,
    "rt": 15,
    "ts": 1744264311434,
    "rn": 466,
    "sg": "2b2ec618394b99deea35104168b86381da9f8946d4bc234e062fa320155409fb",
    "ct": 1744264311,
    "ps": "4ee326507a65a465g015fae",
    "pc": "aab32e207a65a466g010615",
    "s": "36cc0815"
}


def convert(curl_command):
    """从 curl 命令中提取 headers 和 cookies"""
    headers_temp = {}
    for match in re.findall(r"-H '([^:]+): ([^']+)'", curl_command):
        headers_temp[match[0]] = match[1]

    cookies = {}
    cookie_header = next((v for k, v in headers_temp.items() if k.lower() == 'cookie'), '')
    cookie_b = re.search(r"-b '([^']+)'", curl_command)
    cookie_string = cookie_b.group(1) if cookie_b else cookie_header

    if cookie_string:
        for cookie in cookie_string.split('; '):
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookies[key.strip()] = value.strip()

    headers = {k: v for k, v in headers_temp.items() if k.lower() != 'cookie'}
    return headers, cookies


# 初始化 headers 和 cookies
if CURL_BASH:
    headers, cookies = convert(CURL_BASH)
else:
    headers, cookies = DEFAULT_HEADERS, DEFAULT_COOKIES

data = DEFAULT_DATA.copy()


def log_info(msg):
    logging.info(msg)
    print(msg)


def log_error(msg):
    logging.error(msg)
    print(msg)


def log_warning(msg):
    logging.warning(msg)
    print(msg)


def encode_data(data):
    """数据编码"""
    return '&'.join(f"{k}={urllib.parse.quote(str(data[k]), safe='')}" for k in sorted(data.keys()))


def cal_hash(input_string):
    """计算哈希值"""
    _7032f5 = 0x15051505
    _cc1055 = _7032f5
    length = len(input_string)
    _19094e = length - 1

    while _19094e > 0:
        _7032f5 = 0x7fffffff & (_7032f5 ^ ord(input_string[_19094e]) << (length - _19094e) % 30)
        _cc1055 = 0x7fffffff & (_cc1055 ^ ord(input_string[_19094e - 1]) << _19094e % 30)
        _19094e -= 2

    return hex(_7032f5 + _cc1055)[2:].lower()


def get_wr_skey():
    """刷新 cookie 密钥"""
    try:
        # 确保请求中包含 wr_skey
        if 'wr_skey' not in cookies:
            log_error("[错误] cookies 中缺少 wr_skey，请在 curl 命令中包含完整的 cookie")
            log_info(f"当前 cookies: {cookies}")
            return None

        response = requests.post(RENEW_URL, headers=headers, cookies=cookies,
                                 data=json.dumps(COOKIE_DATA, separators=(',', ':')), timeout=10)

        log_info(f"renewal 响应状态码：{response.status_code}")
        log_info(f"renewal 响应内容：{response.text[:200]}")
        set_cookie = response.headers.get('Set-Cookie', '')
        log_info(f"Set-Cookie: {set_cookie}")

        # 检查响应是否返回错误
        try:
            res_json = response.json()
            if res_json.get('errCode') != 0 and 'succ' not in res_json:
                log_error(f"[错误] renewal 请求失败：{res_json}")
                log_error("[错误] cookie 已过期，请重新抓取 curl 命令！")
                log_info("[提示] 操作方法：在浏览器中打开微信读书 -> F12 打开开发者工具 -> Network -> 刷新页面 -> 找到 /web/book/read 请求 -> 复制为 curl")
                return None
        except:
            pass

        if 'wr_skey=' in set_cookie:
            for cookie_part in set_cookie.split(','):
                if "wr_skey=" in cookie_part:
                    wr_skey = cookie_part.split('wr_skey=')[1].split(';')[0].strip()
                    # 检查是否为空
                    if not wr_skey:
                        log_error("[错误] 服务器返回空的 wr_skey，cookie 已失效")
                        log_error("[错误] 请重新抓取 curl 命令更新 cookie")
                        return None
                    log_info(f"[成功] 获取到 wr_skey: {wr_skey}")
                    return wr_skey[:8] if len(wr_skey) >= 8 else wr_skey
        else:
            log_error("[错误] Set-Cookie 中没有 wr_skey，可能是 cookie 已过期或 curl 命令不完整")
            log_info(f"当前 cookies: {cookies}")
    except Exception as e:
        log_error(f"[错误] 获取 wr_skey 失败：{e}")
    return None


def fix_no_synckey():
    """修复无 synckey 问题"""
    try:
        requests.post(FIX_SYNCKEY_URL, headers=headers, cookies=cookies,
                      data=json.dumps({"bookIds": ["3300060341"]}, separators=(',', ':')), timeout=10)
    except Exception as e:
        log_error(f"[错误] 修复 synckey 失败：{e}")


def refresh_cookie():
    """刷新 cookie"""
    log_info("检查 cookie 状态...")

    # 如果已经有 wr_skey，先尝试使用现有的
    existing_skey = cookies.get('wr_skey')
    if existing_skey:
        log_info(f"使用现有 wr_skey: {existing_skey}")
        return True

    # 没有 wr_skey 时才尝试刷新
    log_info("未检测到 wr_skey，尝试获取...")
    new_skey = get_wr_skey()
    if new_skey:
        cookies['wr_skey'] = new_skey
        log_info(f"密钥刷新成功：{new_skey}")
        return True
    else:
        log_error("无法获取 wr_skey，curl_bash 可能已过期")
        send_notify("微信读书运行失败：无法获取 wr_skey")
        return False


def send_notify(content):
    """发送通知"""
    if not PUSH_METHOD:
        return

    try:
        if PUSH_METHOD == "pushplus" and PUSHPLUS_TOKEN:
            requests.post(
                "https://www.pushplus.plus/send",
                data=json.dumps({
                    "token": PUSHPLUS_TOKEN,
                    "title": "微信读书通知",
                    "content": content
                }),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
        elif PUSH_METHOD == "wxpusher" and WXPUSHER_SPT:
            requests.get(f"https://wxpusher.zjiecode.com/api/send/message/{WXPUSHER_SPT}/{content}", timeout=10)
        elif PUSH_METHOD == "telegram" and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": content},
                timeout=10
            )
        elif PUSH_METHOD == "serverchan" and SERVERCHAN_SPT:
            requests.post(
                f"https://sctapi.ftqq.com/{SERVERCHAN_SPT}.send",
                data=json.dumps({"title": "微信读书通知", "desp": content}),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
    except Exception as e:
        log_error(f"[错误] 推送失败：{e}")


def main():
    """主函数"""
    # 检查必要环境变量
    if not CURL_BASH:
        log_error("[错误] 缺少必要环境变量 wxread_curl_bash，请在青龙面板配置")
        send_notify("[错误] 微信读书运行失败：缺少 wxread_curl_bash 环境变量")
        return

    # 刷新 cookie
    if not refresh_cookie():
        return

    index = 1
    last_time = int(time.time()) - 30
    log_info(f"一共需要阅读 {READ_NUM} 次...")

    while index <= READ_NUM:
        data.pop('s', None)
        data['b'] = random.choice(BOOK_IDS)
        data['c'] = random.choice(CHAPTER_IDS)
        this_time = int(time.time())
        data['ct'] = this_time
        data['rt'] = this_time - last_time
        data['ts'] = int(this_time * 1000) + random.randint(0, 1000)
        data['rn'] = random.randint(0, 1000)
        data['sg'] = hashlib.sha256(f"{data['ts']}{data['rn']}{KEY}".encode()).hexdigest()
        data['s'] = cal_hash(encode_data(data))

        log_info(f"尝试第 {index} 次阅读...")

        try:
            response = requests.post(
                READ_URL,
                headers=headers,
                cookies=cookies,
                data=json.dumps(data, separators=(',', ':')),
                timeout=10
            )
            res_data = response.json()
            log_info(f"响应：{res_data}")

            if 'succ' in res_data:
                if 'synckey' in res_data:
                    last_time = this_time
                    index += 1
                    time.sleep(30)
                    log_info(f"阅读成功，阅读进度：{(index - 1) * 0.5} 分钟")
                else:
                    log_warning("[警告] 无 synckey, 尝试修复...")
                    fix_no_synckey()
            else:
                log_error("[错误] cookie 已过期，尝试刷新...")
                if not refresh_cookie():
                    return
        except Exception as e:
            log_error(f"[错误] 请求失败：{e}")
            time.sleep(5)

    total_minutes = (index - 1) * 0.5
    log_info("阅读脚本已完成！")
    log_info(f"总阅读时长：{total_minutes} 分钟")
    send_notify(f"微信读书自动阅读完成！\n总阅读时长：{total_minutes}分钟")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')
    main()
