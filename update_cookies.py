"""从剪贴板更新 cookies.json。

用法：
1. 在 Firefox 里登录 dxpx.uestc.edu.cn，F12 -> 网络 -> 刷新页面
2. 右键第一个请求 -> 复制 -> 复制为 cURL（或只复制请求头里的 Cookie 值）
3. 运行本脚本：python update_cookies.py

脚本自动识别粘贴内容（cURL 命令 / 裸 Cookie 串 / JSON），提取 cookie 写入 cookies.json。
"""

import json
import re
import subprocess
import sys


def get_clipboard() -> str:
    text = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard'],
                          capture_output=True, text=True, encoding='utf-8')
    if text.returncode != 0:
        raise RuntimeError(f'读取剪贴板失败: {text.stderr.strip()}')
    return text.stdout


def extract_cookies(raw: str) -> dict:
    raw = raw.strip()
    # 已经是 JSON
    if raw.startswith('{'):
        data = json.loads(raw)
        if 'cookies' in data:  # curlconverter 完整输出
            return data['cookies']
        return data

    # cURL 命令中的 -H "Cookie: ..."
    m = re.search(r'(?:-H\s+)?["\']Cookie:\s*([^"\']+)["\']', raw, re.IGNORECASE)
    if m:
        cookie_header = m.group(1)
    else:
        # 裸 Cookie 串：key=val; key=val
        cookie_header = raw.splitlines()[0]

    cookies = {}
    for part in cookie_header.split(';'):
        part = part.strip()
        if '=' in part:
            k, _, v = part.partition('=')
            k = k.strip()
            v = v.strip()
            if k == 'HttpOnly':  # cURL 复制出来的伪 cookie，丢弃
                continue
            # Windows cmd 的 curl 转义残留
            v = v.replace('^', '').replace('\\"', '"')
            cookies[k] = v
    return cookies


def main():
    raw = get_clipboard()
    if not raw.strip():
        print('剪贴板是空的。请先在 Firefox 中"复制为 cURL"，再运行本脚本。')
        sys.exit(1)
    cookies = extract_cookies(raw)
    if '_xsrf' not in cookies:
        print('❌ 提取到的 cookie 里没有 _xsrf 字段，可能没有登录。请重新登录后再复制。')
        sys.exit(1)
    if 'token' not in cookies and 'uid' not in cookies:
        print('⚠️ 没有 token/uid cookie，可能登录态不完整。')
    with open('cookies.json', 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=4)
    print(f'✅ 已写入 cookies.json（{len(cookies)} 个字段）')


if __name__ == '__main__':
    main()
