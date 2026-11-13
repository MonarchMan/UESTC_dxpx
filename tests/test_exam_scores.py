"""综合考试历史成绩解析、显示及请求参数的离线测试。"""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from dxpx.common.exam import BaseExam
from dxpx.fzdx.exam import FZDXExam
from dxpx.jjfz.exam import Exam as JJFZExam


class ExamScoresTest(unittest.TestCase):
    page = '''<table><tr><th>最高成绩：100.0分</th></tr>
        <tr><td>1.　2026-11-13 22:07</td><td>分数：82.0分</td>
        <td>用时：0:00:14</td><td><a href="/fzdx/exam_center/end_show?rid=1&amp;stg=43">查看试卷</a></td></tr>
        <tr><td>2.　2026-11-13 20:17</td><td>分数：100.0分</td>
        <td>用时：0:00:19</td><td><a href="/fzdx/exam_center/end_show?rid=2&amp;stg=43">查看试卷</a></td></tr>
        <tr><td>3.　2026-11-12 20:17</td><td>分数：0分</td>
        <td>用时：0:00:01</td><td><a href="/fzdx/exam_center/end_show?rid=3&amp;stg=43">查看试卷</a></td></tr>
        </table>'''

    def test_parse_and_print_history(self):
        """
        验证页面顺序、零分、考试时间和最高分均正确解析和打印。
        """
        records = BaseExam.extract_exam_scores(self.page)
        self.assertEqual([record['score'] for record in records], [82.0, 100.0, 0.0])
        self.assertEqual(records[0]['time'], '2026-11-13 22:07')
        self.assertEqual(records[0]['duration'], '0:00:14')
        exam = FZDXExam({})
        self.addCleanup(exam.session.close)
        with patch.object(exam, 'get_exam_scores', return_value=records), \
                redirect_stdout(io.StringIO()) as output:
            exam.print_exam_scores()
        self.assertIn('最高分：100 分', output.getvalue())
        self.assertIn('共 3 次考试', output.getvalue())
        self.assertIn('2026-11-13 22:07', output.getvalue())

    def test_empty_history(self):
        """
        验证无考试记录时显示提示，避免对空列表计算最高分。
        """
        self.assertEqual(BaseExam.extract_exam_scores('<table></table>'), [])
        exam = FZDXExam({})
        self.addCleanup(exam.session.close)
        with patch.object(exam, 'get_exam_scores', return_value=[]), \
                redirect_stdout(io.StringIO()) as output:
            exam.print_exam_scores()
        self.assertIn('暂无综合考试记录', output.getvalue())

    def test_platform_request_and_error_page(self):
        """
        验证两类培训携带对应阶段参数，错误页面与请求失败不会被视为空记录。
        """
        for cls, platform, stage in [(FZDXExam, 'fzdx', 43), (JJFZExam, 'jjfz', 42)]:
            exam = cls({})
            self.addCleanup(exam.session.close)
            response = Mock(text=self.page)
            with self.subTest(platform=platform), patch.object(exam.session, 'get', return_value=response) as get:
                self.assertEqual(len(exam.get_exam_scores()), 3)
                get.assert_called_once_with(
                    f'https://dxpx.uestc.edu.cn/{platform}/exam_center/end_record',
                    headers=exam.headers, params={'stg': stage}, timeout=30,
                )
                response.text = '<title>错误</title>'
                with self.assertRaisesRegex(RuntimeError, '访问权限'):
                    exam.get_exam_scores()
                response.raise_for_status.side_effect = RuntimeError('请求失败')
                with self.assertRaisesRegex(RuntimeError, '请求失败'):
                    exam.get_exam_scores()

    def test_malformed_record(self):
        """
        验证包含试卷链接却缺少合法分数时明确报错。
        """
        with self.assertRaisesRegex(RuntimeError, '格式发生变化'):
            BaseExam.extract_exam_scores(self.page.replace('分数：82.0分', '分数：未知'))


if __name__ == '__main__':
    unittest.main()
