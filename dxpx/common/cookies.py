"""共享的 cookies 加载工具。"""

import json


def load_cookies(path: str) -> dict:
    """从 JSON 文件加载 cookies。文件需至少包含 '_xsrf' 键。

    :param path: cookies JSON 文件路径
    :return: cookies 字典
    :raises FileNotFoundError: 文件不存在
    :raises ValueError: 文件不含 '_xsrf' 字段
    """
    with open(path, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
    if '_xsrf' not in cookies:
        raise ValueError(f"cookies 文件 {path} 缺少必需的 '_xsrf' 字段")
    return cookies
