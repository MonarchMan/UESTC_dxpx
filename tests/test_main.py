"""统一命令行入口测试，不访问平台或提交学习、考试数据。"""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import main


class MainCommandTest(unittest.TestCase):
    def test_help_does_not_load_credentials(self):
        """
        验证未指定操作或请求帮助时不会读取身份信息。
        """
        for argv in ([], ['jjfz'], ['fzdx'], ['--help'], ['jjfz', '--help'], ['fzdx', '--help']):
            with self.subTest(argv=argv), patch.object(main, 'get_auth_headers') as load:
                with redirect_stdout(io.StringIO()) as output:
                    if '--help' in argv:
                        with self.assertRaises(SystemExit) as error:
                            main.main(argv)
                        self.assertEqual(error.exception.code, 0)
                    else:
                        main.main(argv)
                self.assertTrue(output.getvalue())
                load.assert_not_called()

    def test_init_and_update(self):
        """
        验证两类培训的初始化、更新及组合命令使用对应实例和输出目录。
        """
        for platform, cls in [('jjfz', 'JJFZAutoPlayer'), ('fzdx', 'FZDXAutoPlayer')]:
            for actions in (['--init'], ['--update'], ['--init', '--update']):
                with self.subTest(platform=platform, actions=actions):
                    with patch.object(main, 'get_auth_headers') as load, patch.object(main, cls) as factory:
                        player = factory.return_value
                        player.get_lessons_and_save.return_value = ([], [])
                        with redirect_stdout(io.StringIO()):
                            main.main([platform, *actions])
                        factory.assert_called_once_with(headers=load.return_value)
                        if '--init' in actions:
                            player.get_lessons_and_save.assert_called_once_with(
                                output_dir=f'dxpx/{platform}/temp', save=True,
                            )
                        else:
                            player.get_lessons_and_save.assert_not_called()
                        self.assertEqual(player.update_from_exam_results.call_count, int('--update' in actions))
                        player.session.close.assert_called_once_with()

    def test_custom_paths(self):
        """
        验证请求头和课程输出路径参数传给对应加载、保存函数。
        """
        with patch.object(main, 'get_auth_headers') as load, patch.object(main, 'FZDXAutoPlayer') as factory:
            factory.return_value.get_lessons_and_save.return_value = ([], [])
            with redirect_stdout(io.StringIO()):
                main.main(['fzdx', '--init', '--headers-file', 'custom.json', '--output-dir', 'output'])
            load.assert_called_once_with('custom.json')
            factory.return_value.get_lessons_and_save.assert_called_once_with(output_dir='output', save=True)

    def test_selected_lessons(self):
        """
        验证指定课程参数作为整数列表传入积极分子课程处理函数。
        """
        with patch.object(main, 'get_auth_headers'), patch.object(main, 'JJFZAutoPlayer') as factory:
            main.main(['jjfz', '--lessons', '567', '568', '569'])
            factory.return_value.finish_lessons.assert_called_once_with([567, 568, 569])
            factory.return_value.session.close.assert_called_once_with()

    def test_exam_dispatch(self):
        """
        验证两类综合考试、章节测试、默认轮数及自定义轮数的分发。
        """
        cases = [
            (['jjfz', '--exam'], 'JJFZExam', 'finish_many_exams', 30),
            (['fzdx', '--exam'], 'FZDXExam', 'finish_many_exams', 10),
            (['jjfz', '--exam', '--mode', 'end', '--echos', '2'], 'JJFZExam', 'finish_many_exams', 2),
            (['jjfz', '--exam', '--mode', 'lesson', '--echos', '1'], 'JJFZExam', 'finish_many_lesson_exams', 1),
            (['fzdx', '--exam', '--echos', '1'], 'FZDXExam', 'finish_many_exams', 1),
        ]
        for argv, cls, method, echos in cases:
            with self.subTest(argv=argv):
                with patch.object(main, 'get_auth_headers'), patch.object(main, cls) as factory:
                    main.main(argv)
                    getattr(factory.return_value, method).assert_called_once_with(echos=echos)
                    factory.return_value.session.close.assert_called_once_with()

    def test_invalid_arguments(self):
        """
        验证冲突参数、不支持的功能及非正数轮数在读取凭据前被拒绝。
        """
        cases = [
            ['jjfz', '--exam', '--init'], ['fzdx', '--exam', '--update'],
            ['jjfz', '--exam', '--lessons', '567'], ['jjfz', '--mode', 'lesson'],
            ['fzdx', '--echos', '2'], ['fzdx', '--exam', '--echos', '0'],
            ['jjfz', '--exam', '--echos', '-1'], ['fzdx', '--exam', '--mode', 'lesson'],
            ['fzdx', '--lessons', '567'],
        ]
        for argv in cases:
            with self.subTest(argv=argv), patch.object(main, 'get_auth_headers') as load:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    main.main(argv)
                self.assertEqual(error.exception.code, 2)
                load.assert_not_called()

    def test_sessions_close_on_failure(self):
        """
        验证学习或考试流程抛出异常时仍然关闭会话。
        """
        cases = [
            (['fzdx', '--update'], 'FZDXAutoPlayer', 'update_from_exam_results'),
            (['fzdx', '--exam'], 'FZDXExam', 'finish_many_exams'),
        ]
        for argv, cls, method in cases:
            with self.subTest(argv=argv):
                with patch.object(main, 'get_auth_headers'), patch.object(main, cls) as factory:
                    getattr(factory.return_value, method).side_effect = RuntimeError('操作失败')
                    with self.assertRaises(RuntimeError):
                        main.main(argv)
                    factory.return_value.session.close.assert_called_once_with()

    def test_missing_headers(self):
        """
        验证两种身份来源都失败时输出配置提示并以失败状态退出。
        """
        with patch.object(main, 'get_auth_headers', side_effect=RuntimeError('请配置 .env 账号密码或者 headers.json')):
            with redirect_stderr(io.StringIO()) as output, self.assertRaises(SystemExit) as error:
                main.main(['fzdx', '--update'])
            self.assertEqual(error.exception.code, 1)
            self.assertIn('headers.json', output.getvalue())


if __name__ == '__main__':
    unittest.main()
