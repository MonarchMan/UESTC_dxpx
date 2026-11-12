"""真实登录集成测试，运行命令：uv run python -m tests.test_login。"""

import unittest

from dxpx.common.login import ROOT, load_headers, login_from_env, verify_headers


class LoginIntegrationTest(unittest.TestCase):
    def test_real_login_and_saved_headers(self):
        """
        通过真实网络请求验证登录、请求头落盘及独立会话认证。
        """
        path = ROOT / "headers.json"
        headers = login_from_env(headers_file=path)
        self.assertTrue(headers.get("Cookie"))
        saved = load_headers(path)
        self.assertEqual(saved["Cookie"], headers["Cookie"])
        # 从磁盘重新加载并独立验证，避免只验证登录时的内存状态。
        verify_headers(saved)


if __name__ == "__main__":
    unittest.main()
