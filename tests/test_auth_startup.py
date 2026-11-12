"""启动认证选择测试，不访问真实平台或读取真实账号密码。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from dxpx.common.login import get_auth_headers, load_headers


class AuthStartupTest(unittest.TestCase):
    def test_env_login_has_priority(self):
        """
        验证环境登录成功时不读取备用请求头，并保留自定义保存路径。
        """
        with patch('dxpx.common.login.login_from_env', return_value={'Cookie': 'token=new'}) as login:
            with patch('dxpx.common.login.load_headers') as load:
                result = get_auth_headers('custom.json')
                login.assert_called_once_with(headers_file='custom.json')
                load.assert_not_called()
                self.assertEqual(result['Cookie'], 'token=new')
                self.assertEqual(result.path, Path('custom.json').resolve())

    def test_headers_fallback(self):
        """
        验证未配置账号、登录拒绝或网络失败后，导入并保存验证更新的备用身份。
        """
        for error in (ValueError('未配置'), RuntimeError('登录拒绝'), requests.Timeout('超时')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'headers.json'
                path.write_text(json.dumps({'Cookie': 'token=old'}), encoding='utf-8')
                with patch('dxpx.common.login.login_from_env', side_effect=error):
                    with patch('dxpx.common.login.verify_headers') as verify:
                        verify.side_effect = lambda headers: headers.update(Cookie='token=renewed')
                        result = get_auth_headers(path)
                        verify.assert_called_once_with(result)
                self.assertEqual(result['Cookie'], 'token=renewed')
                self.assertEqual(load_headers(path)['Cookie'], 'token=renewed')
                self.assertEqual(result.path, path.resolve())

    def test_both_sources_fail(self):
        """
        验证备用文件缺失、损坏或身份失效时给出两种配置方法且不覆盖原文件。
        """
        for content in (None, '{', '[]', '{"Cookie": null}', '{"Cookie": ""}', '{"Cookie": "token=old"}'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'headers.json'
                if content is not None:
                    path.write_text(content, encoding='utf-8')
                with patch('dxpx.common.login.login_from_env', side_effect=ValueError('未配置')):
                    with patch('dxpx.common.login.verify_headers', side_effect=RuntimeError('失效')):
                        with self.assertRaises(RuntimeError) as error:
                            get_auth_headers(path)
                self.assertIn('DXPX_SID', str(error.exception))
                self.assertIn('DXPX_PASSWORD', str(error.exception))
                self.assertIn(str(path), str(error.exception))
                if content is not None:
                    self.assertEqual(path.read_text(encoding='utf-8'), content)
                else:
                    self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
