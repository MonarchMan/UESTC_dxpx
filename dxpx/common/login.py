"""提供平台登录、验证码识别和共享请求头加载功能。"""

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://dxpx.uestc.edu.cn"


class LoginHeaders(dict):
    """携带来源路径的请求头字典，供会话将更新写回原文件。"""

    def __init__(self, headers: dict, path: str | Path):
        """
        保存请求头及其来源路径。

        :param headers: 从文件加载的请求头。
        :param path: 原请求头文件路径。
        """
        super().__init__(headers)
        self.path = Path(path).resolve()


def load_headers(path: str) -> dict:
    """
    从 JSON 文件加载请求头，并从 Cookie 中提取可用的 _xsrf。
    
    :param path: 请求头 JSON 文件路径。
    :return: dict；包含 Cookie 的请求头字典，Cookie 含 _xsrf 时附加同名字段。
    :raises FileNotFoundError: 请求头文件不存在。
    :raises ValueError: 请求头缺少必需的 Cookie 字段。
    """
    with open(path, "r", encoding="utf-8") as f:
        headers = json.load(f)
    if (not isinstance(headers, dict)
            or not isinstance(headers.get('Cookie'), str)
            or not headers['Cookie'].strip()):
        raise ValueError(f"headers 文件 {path} 需要包含非空字符串 'Cookie' 字段")
    # 保留完整 Cookie，仅额外提取提交表单时使用的令牌。
    match = re.search(r"_xsrf=([^;]+)", headers["Cookie"])
    if match:
        headers["_xsrf"] = match.group(1)
    return LoginHeaders(headers, path)


def get_auth_headers(headers_file: str | Path = ROOT / 'headers.json') -> dict:
    """
    优先使用环境配置登录，失败后验证本地请求头并导入有效身份。

    :param headers_file: 请求头保存和备用导入路径，默认项目根目录 headers.json。
    :return: dict；已通过认证且携带保存路径的请求头。
    :raises RuntimeError: 账号密码登录及本地请求头认证均失败。
    """
    try:
        headers = login_from_env(headers_file=headers_file)
        return LoginHeaders(headers, headers_file)
    except (OSError, ValueError, RuntimeError, requests.RequestException):
        # 登录失败不会覆盖原文件，因此仍可使用用户手动配置的身份。
        pass
    try:
        headers = load_headers(headers_file)
        verify_headers(headers)
        # 验证请求也会轮换 Cookie，保存最新身份再交给业务流程。
        with open(headers_file, 'w', encoding='utf-8') as file:
            json.dump(headers, file, ensure_ascii=False, indent=4)
        return headers
    except (OSError, ValueError, RuntimeError, requests.RequestException) as error:
        raise RuntimeError(
            '自动登录和 headers.json 认证均失败。请在项目根目录 .env 中配置有效的 '
            'DXPX_SID、DXPX_PASSWORD，或者在 '
            f'{headers_file} 中配置有效的请求头（包含 Cookie）。'
        ) from error


def is_login_response(response: requests.Response) -> bool:
    """
    判断响应是否明确要求登录，不将普通权限错误认作登录失效。

    :param response: 平台返回的响应。
    :return: bool；状态为 401、跳转登录页或包含登录表单时为 True。
    """
    paths = {urlparse(item.url).path.rstrip('/') for item in [*response.history, response]}
    location = urlparse(response.headers.get('Location', '')).path.rstrip('/')
    return (response.status_code == 401
            or bool(paths.intersection({'/login', '/user/login'}))
            or location in {'/login', '/user/login'}
            or bool(re.search(r'id=[\"\']login_btn[\"\']', response.text)))


class AuthSession(requests.Session):
    """通过 CookieJar 续期身份，明确失效时使用根目录账号密码重新登录。"""

    def __init__(self, headers: dict):
        """
        加载已有身份，不在创建实例时发起网络请求。

        :param headers: 共享请求头；load_headers 返回的字典会写回其原文件。
        """
        super().__init__()
        self.shared_headers = headers
        self.headers_file = getattr(headers, 'path', ROOT / 'headers.json')
        self.last_verified = 0.0
        self.auth_generation = 0
        self.saved_cookie = None
        headers.setdefault('_xsrf', '')
        self._load_cookies()

    def _load_cookies(self):
        """
        从共享请求头同步 CookieJar，跳过服务器误写入的 HttpOnly 属性。
        """
        self.cookies.clear()
        for part in self.shared_headers.get('Cookie', '').split(';'):
            name, sep, value = part.strip().partition('=')
            if sep and name.lower() != 'httponly':
                self.cookies.set(name, value, domain=urlparse(BASE_URL).hostname, path='/')
        self.saved_cookie = self.shared_headers.get('Cookie', '')
        match = re.search(r'(?:^|;\s*)_xsrf=([^;]+)', self.saved_cookie)
        self.shared_headers['_xsrf'] = match.group(1) if match else ''

    def _save_cookies(self):
        """
        将有效 Cookie 写回共享请求头和原文件，并同步表单使用的 _xsrf。
        """
        for cookie in list(self.cookies):
            if cookie.value is None or cookie.name.lower() == 'httponly':
                self.cookies.clear(cookie.domain, cookie.path, cookie.name)
        self.cookies.clear_expired_cookies()
        cookie = self.prepare_request(requests.Request('GET', BASE_URL + '/user')).headers.get('Cookie', '')
        self.shared_headers['Cookie'] = cookie
        match = re.search(r'(?:^|;\s*)_xsrf=([^;]+)', cookie)
        self.shared_headers['_xsrf'] = match.group(1) if match else ''
        if cookie != self.saved_cookie:
            with open(self.headers_file, 'w', encoding='utf-8') as file:
                json.dump(self.shared_headers, file, ensure_ascii=False, indent=4)
            self.saved_cookie = cookie

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        使用最新 Cookie 和表单令牌发起一次请求，不执行重试。

        :param method: HTTP 请求方法。
        :param url: 平台请求地址。
        :param kwargs: requests 支持的请求参数。
        :return: requests.Response；原始响应。
        """
        supplied = kwargs.pop('headers', None) or self.shared_headers
        kwargs['headers'] = {key: value for key, value in supplied.items()
                             if key.lower() not in {'cookie', '_xsrf'}}
        data = kwargs.get('data')
        if isinstance(data, dict) and '_xsrf' in data:
            kwargs['data'] = {**data, '_xsrf': self.shared_headers.get('_xsrf', '')}
        return super().request(method, url, **kwargs)

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        接收并持久化续期 Cookie，认证失效时重新登录一次。

        :param method: HTTP 请求方法；GET、HEAD 允许登录后重试一次。
        :param url: 请求地址；外部媒体地址不携带平台身份，也不触发登录。
        :param kwargs: requests 支持的请求参数；未指定超时时使用 30 秒。
        :return: requests.Response；通过认证的响应或非认证错误响应。
        :raises RuntimeError: 重新登录后认证仍失败，或提交请求需由调用者重新开始。
        """
        kwargs.setdefault('timeout', 30)
        if urlparse(url).netloc != urlparse(BASE_URL).netloc:
            supplied = kwargs.pop('headers', None) or {}
            kwargs['headers'] = {key: value for key, value in supplied.items()
                                 if key.lower() not in {'cookie', '_xsrf', 'authorization'}}
            return super().request(method, url, **kwargs)
        if self.shared_headers.get('Cookie', '') != self.saved_cookie:
            self._load_cookies()
        safe = method.upper() in {'GET', 'HEAD'}
        generation = self.auth_generation
        # 首次提交或长时间空闲后，先验证身份，避免提交过程中才发现登录失效。
        if not safe and (not self.last_verified or time.monotonic() - self.last_verified > 600):
            self.get(BASE_URL + '/user')
        if not safe and not self.shared_headers.get('_xsrf'):
            params = {'stg': (kwargs.get('params') or {}).get('stg', 43)}
            self.get(BASE_URL + '/fzdx/lesson', params=params)
        if not safe and generation != self.auth_generation:
            raise RuntimeError('身份已重新登录，请重新开始当前操作；尚未发送提交请求。')
        response = self._request(method, url, **kwargs)
        if is_login_response(response):
            response.close()
            fresh = login_from_env(headers_file=self.headers_file)
            self.shared_headers.update(fresh)
            self._load_cookies()
            self.last_verified = 0.0
            self.auth_generation += 1
            if not safe:
                raise RuntimeError('身份已重新登录，请重新开始当前操作；未自动重放提交请求。')
            response = self._request(method, url, **kwargs)
            if is_login_response(response):
                response.close()
                raise RuntimeError('重新登录后仍无法访问，请检查账号和平台登录状态。')
        if response.status_code < 400:
            self.last_verified = time.monotonic()
            self._save_cookies()
        return response

def get_captcha(session: requests.Session, ocr=None) -> str:
    """
    请求当前登录会话的验证码图片并识别其中的数字和字母。
    
    :param session: 获取登录页、验证码及提交登录时共用的 requests.Session。
    :param ocr: 可复用的验证码识别器；为 None 时创建本地 ddddocr 识别器。默认值为 None。
    :return: str；去除首尾空白后的数字、字母验证码。
    :raises RuntimeError: 响应不是图片，或识别结果不是数字、字母。
    """
    if ocr is None:
        import ddddocr

        ocr = ddddocr.DdddOcr(show_ad=False)
    # 时间戳避免复用缓存图片，会话保证图片与后续登录请求关联。
    params = {"v": int(time.time() * 1000)}
    response = session.get(BASE_URL + "/api/captcha", params=params, timeout=30)
    response.raise_for_status()
    if not response.headers.get("Content-Type", "").startswith("image/"):
        raise RuntimeError("Captcha endpoint did not return an image")
    code = ocr.classification(response.content).strip()
    if not re.fullmatch(r"[A-Za-z0-9]+", code):
        raise RuntimeError("Captcha recognition returned no valid letters/digits")
    return code


def verify_headers(headers: dict) -> None:
    """
    使用独立会话验证请求头能否访问用户中心，并回填验证时轮换的 Cookie。
    
    :param headers: 请求头字典；认证请求通常需包含 Cookie，提交学习或答题记录时还需 _xsrf。
    :raises RuntimeError: 用户中心请求发生非预期跳转或返回登录表单。
    """
    # 不复用登录会话，确认保存的请求头本身足以通过认证。
    with requests.Session() as session:
        for part in headers.get('Cookie', '').split(';'):
            name, sep, value = part.strip().partition('=')
            if sep and name.lower() != 'httponly':
                session.cookies.set(name, value, domain=urlparse(BASE_URL).hostname, path='/')
        clean_headers = {key: value for key, value in headers.items()
                         if key.lower() not in {'cookie', '_xsrf'}}
        response = session.get(BASE_URL + "/user", headers=clean_headers, timeout=30)
        response.raise_for_status()
        if urlparse(response.url).path.rstrip("/") != "/user":
            raise RuntimeError("Authentication verification redirected away from /user")
        if re.search(r'id=[\"\']login_btn[\"\']', response.text):
            raise RuntimeError("Authentication verification returned the login form")
        # 独立验证同样会轮换 Cookie，保存验证后最新的一份身份。
        for cookie in list(session.cookies):
            if cookie.value is None or cookie.name.lower() == 'httponly':
                session.cookies.clear(cookie.domain, cookie.path, cookie.name)
        headers['Cookie'] = session.prepare_request(
            requests.Request('GET', BASE_URL + '/user')
        ).headers.get('Cookie', '')


def login(sid: str, password: str, *,
          headers_file: str | Path = ROOT / "headers.json") -> dict:
    """
    完成验证码登录，验证会话后将请求头保存为 JSON 文件。
    
    :param sid: 平台登录账号。
    :param password: 原始明文密码；提交前使用 UTF-8 编码计算 SHA-1 摘要。
    :param headers_file: 登录成功后保存请求头的 JSON 文件路径。默认值为 ROOT / 'headers.json'。
    :return: dict；已验证并写入文件的请求头，包含 Cookie、User-Agent 和 Referer。
    :raises ValueError: 账号或密码为空。
    :raises RuntimeError: 登录被拒绝或保存前的会话验证失败。
    """
    if not sid or not password:
        raise ValueError("Set DXPX_SID and DXPX_PASSWORD")
    # 与平台登录页保持一致：对原始密码计算 SHA-1，不重复处理摘要。
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest()

    import ddddocr

    ocr = ddddocr.DdddOcr(show_ad=False)
    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Referer": BASE_URL + "/user/login",
            "Origin": BASE_URL,
        })
        # 先访问登录页建立匿名会话，后续验证码和登录共用其 Cookie。
        response = session.get(BASE_URL + "/user/login", timeout=30)
        response.raise_for_status()
        for attempt in range(3):
            data = {
                "sid": sid,
                "pass": digest.lower(),
                "next": "/user",
                "v_code": get_captcha(session, ocr),
            }
            if session.cookies.get("_xsrf"):
                data["_xsrf"] = session.cookies.get("_xsrf")
            response = session.post(BASE_URL + "/api/login", data=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 1:
                break
            message = str(result.get("message", "Login rejected"))
            # 仅验证码错误允许换图重试，账号密码等错误立即终止。
            if attempt < 2 and ("验证码" in message or "captcha" in message.lower()):
                continue
            raise RuntimeError(f"Login failed (code={result.get('code')}): {message}")

        response = session.get(BASE_URL + "/user", timeout=30)
        response.raise_for_status()
        # 由 requests 按目标地址选择 Cookie，避免拼入其他域或路径的凭据。
        cookie = session.prepare_request(requests.Request("GET", BASE_URL + "/user")).headers.get("Cookie", "")
        headers = {
            "User-Agent": session.headers["User-Agent"],
            "Referer": BASE_URL + "/user",
            "Cookie": cookie,
        }
        # 验证通过后才覆盖原文件，登录失败不会破坏已有请求头。
        verify_headers(headers)
        with open(headers_file, "w", encoding="utf-8") as f:
            json.dump(headers, f, ensure_ascii=False, indent=4)
        return headers


def login_from_env(*, headers_file: str | Path = ROOT / "headers.json") -> dict:
    """
    从项目根目录的 .env 文件和系统环境变量读取账号密码并执行登录。
    
    :param headers_file: 登录成功后保存请求头的 JSON 文件路径。默认值为 ROOT / 'headers.json'。
    :return: dict；登录成功后保存的请求头字典。
    """
    # 系统环境变量优先于文件配置，便于终端临时切换账号。
    load_dotenv(ROOT / ".env", override=False)
    return login(
        os.getenv("DXPX_SID", ""),
        os.getenv("DXPX_PASSWORD", ""),
        headers_file=headers_file,
    )


def main():
    """
    解析命令行参数并执行当前模块的入口流程。
    """
    parser = argparse.ArgumentParser(description="Log in using credentials from .env")
    parser.add_argument("--headers-file", default=ROOT / "headers.json")
    args = parser.parse_args()
    login_from_env(headers_file=args.headers_file)
    print("Login verified; headers saved.")


if __name__ == "__main__":
    main()
