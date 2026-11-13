"""两类培训缺失、空白和正常题库的离线回归测试。"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dxpx.fzdx.fzdx import FZDXAutoPlayer
from dxpx.jjfz.jjfz import JJFZAutoPlayer


class QuestionBankTest(unittest.TestCase):
    player_classes = (JJFZAutoPlayer, FZDXAutoPlayer)
    question_types = ('radio', 'checkbox', 'yes_or_no', 'gap_filling')

    def test_missing_question_bank(self):
        """
        验证两类培训缺少全部题库时，各题型查询均按未命中处理。
        """
        for player_class in self.player_classes:
            with self.subTest(platform=player_class.__name__), tempfile.TemporaryDirectory() as directory:
                player = player_class(headers={})
                self.addCleanup(player.session.close)
                player.load_questions(directory)
                for question_type in self.question_types:
                    self.assertEqual(player.search_answer('测试题目', question_type), '')

    def test_partial_question_bank(self):
        """
        验证仅有单选题库时仍可命中答案，其他题型查询不会报错。
        """
        for player_class in self.player_classes:
            with self.subTest(platform=player_class.__name__), tempfile.TemporaryDirectory() as directory:
                pd.DataFrame([{'title': '测试题目', 'correct_answer': 'B'}]).to_parquet(
                    Path(directory) / 'radios.parquet', index=False, engine='pyarrow',
                )
                player = player_class(headers={})
                self.addCleanup(player.session.close)
                player.load_questions(directory)
                self.assertEqual(player.search_answer('测试题目', 'radio'), 'B')
                self.assertEqual(player.search_answer('其他题目', 'radio'), '')
                for question_type in self.question_types[1:]:
                    self.assertEqual(player.search_answer('测试题目', question_type), '')

    def test_empty_parquet_question_bank(self):
        """
        验证无列空表保存为 Parquet 后，重新加载及查询均正常。
        """
        for player_class in self.player_classes:
            with self.subTest(platform=player_class.__name__), tempfile.TemporaryDirectory() as directory:
                for filename in ('radios', 'checkboxes', 'yes_or_nos', 'gap_fillings'):
                    pd.DataFrame().to_parquet(
                        Path(directory) / f'{filename}.parquet', index=False, engine='pyarrow',
                    )
                player = player_class(headers={})
                self.addCleanup(player.session.close)
                player.load_questions(directory)
                for question_type in self.question_types:
                    self.assertEqual(player.search_answer('测试题目', question_type), '')

    def test_invalid_question_type_still_raises(self):
        """
        验证空题库不会掩盖不支持的题型参数错误。
        """
        for player_class in self.player_classes:
            with self.subTest(platform=player_class.__name__):
                player = player_class(headers={})
                self.addCleanup(player.session.close)
                with self.assertRaises(ValueError):
                    player.search_answer('测试题目', 'invalid')


if __name__ == '__main__':
    unittest.main()
