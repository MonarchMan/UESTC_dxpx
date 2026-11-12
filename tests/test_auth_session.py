"""真实会话集成测试：uv run python -B -m tests.test_auth_session。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dxpx.common.login import (
    AuthSession, BASE_URL, ROOT, load_headers, login_from_env, verify_headers,
)
from dxpx.fzdx.fzdx import FZDXAutoPlayer


class AuthSessionIntegrationTest(unittest.TestCase):
    def test_real_fallback_and_cookie_renewal(self):
        """
        使用真实请求检查登录兜底、Cookie 轮换、原路径落盘及课程请求接入。
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'headers.json'
            path.write_text(json.dumps({
                'User-Agent': 'Mozilla/5.0',
                'Cookie': 'HttpOnly; uid=expired; token=expired',
            }), encoding='utf-8')
            headers = load_headers(path)
            # 只统计真实登录次数，不替换服务器响应或验证码数据。
            with patch('dxpx.common.login.login_from_env', wraps=login_from_env) as relogin:
                with AuthSession(headers) as session:
                    response = session.get(BASE_URL + '/user', headers=headers)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(relogin.call_count, 1)
                    self.assertNotIn('expired', response.request.headers['Cookie'])
                    previous = headers['Cookie']
                    response = session.get(BASE_URL + '/user', headers=headers)
                    self.assertEqual(response.request.headers['Cookie'], previous)
                    self.assertNotEqual(headers['Cookie'], previous)
                    self.assertEqual(relogin.call_count, 1)
                player = FZDXAutoPlayer(headers)
                try:
                    self.assertTrue(player.get_lessons())
                    self.assertTrue(headers.get('_xsrf'))
                    self.assertEqual(relogin.call_count, 1)
                finally:
                    player.session.close()
            saved = load_headers(path)
            self.assertEqual(saved['Cookie'], headers['Cookie'])
            self.assertNotIn('HttpOnly', saved['Cookie'])
            verify_headers(saved)
            # 将验证时收到的最新身份留给后续正常运行。
            (ROOT / 'headers.json').write_text(
                json.dumps(saved, ensure_ascii=False, indent=4), encoding='utf-8',
            )


if __name__ == '__main__':
    unittest.main()
