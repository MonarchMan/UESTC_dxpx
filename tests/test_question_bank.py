"""两类培训缺失、空白和正常题库的离线回归测试。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from dxpx.fzdx.fzdx import FZDXAutoPlayer
from dxpx.jjfz.jjfz import JJFZAutoPlayer


class QuestionBankTest(unittest.TestCase):
    player_classes = (JJFZAutoPlayer, FZDXAutoPlayer)
    question_types = ('radio', 'checkbox', 'yes_or_no', 'gap_filling')

    def test_result_page_preserves_gap_answer_before_clear(self):
        """
        验证真实结果页中的内部清浮动标签不会截断填空答案。
        """
        from types import SimpleNamespace

        page = '''<div class="error_sub">
            <h3>81、【填空题】（&nbsp;&nbsp;）是全面抗战的起点。</h3>
            <div class="sub_list"><div class="sub_list1">
            <span class="sub_color">正确答案：</span>
            <div class="sub_cont">七七事变|卢沟桥事变</div>
            <div class="clear"></div></div>
            <div class="sub_list2"><span>所答答案：</span>
            <div class="sub_cont">unknown answer</div></div></div>
            </div><div class="foot margin_top0">页脚</div>'''
        player = FZDXAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        with patch.object(player.session, 'get', return_value=SimpleNamespace(text=page)):
            paper = player.get_exam_paper(1)
        self.assertEqual(len(paper[3]), 1)
        self.assertEqual(paper[3][0]['correct_answer'], '七七事变|卢沟桥事变')

    def test_empty_answer_is_repaired_and_alternative_is_selected(self):
        """
        验证有效答案补全旧空答案，并从可接受的填空写法中选取一种。
        """
        player = FZDXAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        player.gap_filling_df = pd.DataFrame([{
            'title': '题目（&nbsp;）', 'options': [], 'correct_answer': '',
        }])
        new = pd.DataFrame([{
            'title': '题目()', 'options': [], 'correct_answer': '七七事变|卢沟桥事变',
        }])
        with patch.object(player, 'load_questions'), patch.object(player, 'save_result'), \
                patch.object(player, 'save_result_parquet'):
            player.update_questions(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), new)
        self.assertEqual(len(player.gap_filling_df), 1)
        self.assertEqual(player.search_answer('题目（ ）', 'gap_filling'), '七七事变')

    def test_normalized_question_matches_for_both_platforms(self):
        """
        验证各题型均兼容 HTML 实体、全半角括号及括号内空白。
        """
        variants = ('坚持（&nbsp;&nbsp;）原则', '坚持（\u00a0 ）原则',
                    '坚持( )原则', '坚持（）原则', '坚持(&#160;)原则')
        for player_class in self.player_classes:
            player = player_class(headers={})
            self.addCleanup(player.session.close)
            for question_type, attr in zip(self.question_types, (
                    'radio_df', 'checkbox_df', 'yes_or_no_df', 'gap_filling_df')):
                setattr(player, attr, pd.DataFrame([{
                    'title': variants[0], 'options': ['A、甲', 'B、乙'], 'correct_answer': 'B',
                }]))
                for title in variants:
                    with self.subTest(platform=player_class.__name__, kind=question_type, title=title):
                        self.assertEqual(player.search_answer(title, question_type), 'B')
                self.assertEqual(getattr(player, attr).iloc[0]['title'], variants[0])

    def test_conflicts_and_exact_match_priority(self):
        """
        验证原文匹配优先，标准化后的答案或选项冲突不自动选取。
        """
        for player_class in self.player_classes:
            player = player_class(headers={})
            self.addCleanup(player.session.close)
            for second in ({'options': ['A、甲'], 'correct_answer': 'B'},
                           {'options': ['A、乙'], 'correct_answer': 'A'}):
                player.radio_df = pd.DataFrame([
                    {'title': '题目（ ）', 'options': ['A、甲'], 'correct_answer': 'A'},
                    {'title': '题目()', **second},
                ])
                self.assertEqual(player.search_answer('题目（ ）', 'radio'), 'A')
                self.assertEqual(player.search_answer('题目( )', 'radio'), '')

    def test_indexes_reused_and_replaced_with_bank(self):
        """
        验证同一题库查询复用缓存，替换题库后重建缓存。
        """
        player = FZDXAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        player.radio_df = pd.DataFrame([{'title': '题目()', 'correct_answer': 'A'}])
        self.assertEqual(player.search_answer('题目（ ）', 'radio'), 'A')
        cached = player._answer_indexes['radio']
        self.assertEqual(player.search_answer('题目（ ）', 'radio'), 'A')
        self.assertIs(player._answer_indexes['radio'], cached)
        player.radio_df = pd.DataFrame([{'title': '题目()', 'correct_answer': 'B'}])
        self.assertEqual(player.search_answer('题目（ ）', 'radio'), 'B')

    def test_normalized_dedup_preserves_conflicts(self):
        """
        验证更新题库使用相同匹配键去重，并保留答案冲突项。
        """
        player = FZDXAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        player.radio_df = pd.DataFrame([{
            'title': '题目（&nbsp;）', 'options': ['A、甲'], 'correct_answer': 'A',
        }])
        new = pd.DataFrame([
            {'title': '题目()', 'options': ['A、甲'], 'correct_answer': 'A'},
            {'title': '题目( )', 'options': ['A、甲'], 'correct_answer': 'B'},
        ])
        with patch.object(player, 'load_questions'), patch.object(player, 'save_result'), \
                patch.object(player, 'save_result_parquet'):
            player.update_questions(new, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        self.assertEqual(len(player.radio_df), 2)
        self.assertEqual(player.search_answer('题目（）', 'radio'), '')

    def test_meaningful_text_is_not_removed(self):
        """
        验证年份、标点及正文空格不会被无差别删除。
        """
        normalize = FZDXAutoPlayer.normalize_question
        self.assertNotEqual(normalize('2025年（甲）'), normalize('2026年（甲）'))
        self.assertNotEqual(normalize('甲 乙'), normalize('甲乙'))
        self.assertNotEqual(normalize('甲、乙'), normalize('甲乙'))

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
