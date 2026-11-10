"""本地离线测试：不发起任何网络请，不读取 cookies。

运行：
    python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dxpx.common.player import BaseAutoPlayer  # noqa: E402


class FakePlayer(BaseAutoPlayer):
    """用内存数据替代网络请求，专注验证分页/去重/保护逻辑。"""

    def __init__(self, pages, courseware=None):
        super().__init__(cookies={})
        # pages: {page:int -> (id_pairs, courseware_ids, total_pages)}
        self.pages = pages
        self.courseware = courseware or {}
        self.requested_pages = []
        self.record_calls = []
        self.r_id_calls = []
        self.r_ids = {}

    def get_lessons(self):
        return ['620']

    def get_required_lessons(self, lesson_id, page=1):
        self.requested_pages.append(page)
        return self.pages.get(page, ([], [], 1))

    def get_lesson_r_id(self, video_id, resource_id, page=1):
        self.r_id_calls.append((video_id, resource_id, page))
        return self.r_ids.get((video_id, resource_id), 9000 + resource_id)

    def check_record(self, lesson_id, video_id, resource_id, r_id):
        self.record_calls.append((lesson_id, video_id, resource_id, r_id))
        return True

    def get_course_ware_extra_ids(self, v_id):
        return self.courseware.get(v_id)


class ExtractInfoTest(unittest.TestCase):
    def _page(self, links, footer=''):
        anchors = ''.join(
            f'<a class="" href="/jjfz/play?v_id={v}&r_id={r}&r=video&pg=1">x</a>'
            for v, r in links
        )
        return f'<html><body>{anchors}{footer}</body></html>'

    def test_same_video_different_resources_kept(self):
        text = self._page([(17965, 70244), (17965, 70245), (17935, 69894)])
        id_pairs, _, _ = BaseAutoPlayer.extract_required_lessons_info(text)
        self.assertIn(('17965', '70244'), id_pairs)
        self.assertIn(('17965', '70245'), id_pairs)
        self.assertEqual(len(id_pairs), 3)

    def test_duplicate_links_deduped(self):
        text = self._page([(17965, 70244), (17965, 70244), (17935, 69894)])
        id_pairs, _, _ = BaseAutoPlayer.extract_required_lessons_info(text)
        self.assertEqual(id_pairs, [('17965', '70244'), ('17935', '69894')])

    def test_total_pages_from_last_page_link(self):
        text = self._page(
            [(1, 2)],
            footer='<a href="/jjfz/lesson/video?lesson_id=620&page=1">1</a>'
                   '<a href="/jjfz/lesson/video?lesson_id=620&page=3">末页</a>',
        )
        _, _, total_pages = BaseAutoPlayer.extract_required_lessons_info(text)
        self.assertEqual(total_pages, 3)

    def test_total_pages_default_one(self):
        _, _, total_pages = BaseAutoPlayer.extract_required_lessons_info(self._page([(1, 2)]))
        self.assertEqual(total_pages, 1)


class GetLessonsAndSaveTest(unittest.TestCase):
    def test_pagination_requests_each_page_once(self):
        player = FakePlayer({
            1: ([('1', '11'), ('2', '22')], [], 2),
            2: ([('3', '33')], [], 2),
        })
        failed, lessons = player.get_lessons_and_save(save=False)
        self.assertEqual(player.requested_pages, [1, 2])
        self.assertEqual(failed, [])
        self.assertEqual(
            lessons[0]['id_params'],
            [
                {'video_id': 1, 'resource_id': 11},
                {'video_id': 2, 'resource_id': 22},
                {'video_id': 3, 'resource_id': 33},
            ],
        )

    def test_duplicate_across_pages_submitted_once(self):
        player = FakePlayer({
            1: ([('1', '11')], [], 2),
            2: ([('1', '11'), ('2', '22')], [], 2),
        })
        player.get_lessons_and_save(save=False)
        self.assertEqual(
            [c[:3] for c in player.record_calls],
            [('620', 1, 11), ('620', 2, 22)],
        )

    def test_same_video_different_resources_both_submitted(self):
        player = FakePlayer({1: ([('1', '11'), ('1', '12')], [], 1)})
        _, lessons = player.get_lessons_and_save(save=False)
        self.assertEqual(
            lessons[0]['id_params'],
            [
                {'video_id': 1, 'resource_id': 11},
                {'video_id': 1, 'resource_id': 12},
            ],
        )
        self.assertEqual(len(player.record_calls), 2)

    def test_courseware_ids_included(self):
        player = FakePlayer({1: ([], ['7'], 1)}, courseware={7: ('700', '70')})
        _, lessons = player.get_lessons_and_save(save=False)
        self.assertEqual(lessons[0]['id_params'], [{'video_id': 7, 'resource_id': 70}])
        self.assertEqual(player.record_calls, [('620', 7, 70, 700)])

    def test_courseware_without_resource_reported_not_crashed(self):
        player = FakePlayer({1: ([('1', '11')], ['7'], 1)}, courseware={})
        failed, lessons = player.get_lessons_and_save(save=False)
        self.assertEqual(len(lessons[0]['id_params']), 1)
        self.assertEqual(failed[0]['reason'], 'no_resource_id')

    def test_no_rid_not_submitted(self):
        player = FakePlayer({1: ([('1', '11')], [], 1)})
        player.r_ids[(1, 11)] = 0
        failed, _ = player.get_lessons_and_save(save=False)
        self.assertEqual(player.record_calls, [])
        self.assertEqual(failed[0]['reason'], 'no_rid')

    def test_empty_lesson_list_raises_and_keeps_file(self):
        player = FakePlayer({})
        player.get_lessons = lambda: []

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'lessons.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump([{'lesson_id': 'old', 'id_params': []}], f)
            before = self._read(path)

            with self.assertRaises(RuntimeError):
                player.get_lessons_and_save(output_dir=tmp, save=True)

            after = self._read(path)
            self.assertEqual(before, after)

    @staticmethod
    def _read(path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_all_pages_empty_raises(self):
        player = FakePlayer({1: ([], [], 1)})
        with self.assertRaises(RuntimeError):
            player.get_lessons_and_save(save=False)

    def test_page_loop_is_bounded(self):
        # total_pages 异常巨大时不会无限翻页
        player = FakePlayer({1: ([('1', '11')], [], 999999)})
        player.get_lessons_and_save(save=False)
        self.assertLessEqual(len(player.requested_pages), BaseAutoPlayer.max_pages_per_lesson)


class FinishFromLocalTest(unittest.TestCase):
    def test_duplicate_entries_submitted_once(self):
        player = FakePlayer({})
        lessons = [{
            'lesson_id': '620',
            'id_params': [
                {'video_id': 1, 'resource_id': 11},
                {'video_id': 1, 'resource_id': 11},
                {'video_id': 1, 'resource_id': 12},
            ],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'lessons.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(lessons, f)
            failed = player.finish_lessons_from_local(path)

        self.assertEqual(failed, [])
        self.assertEqual(len(player.record_calls), 2)


class JJFZRidValidationTest(unittest.TestCase):
    def _player(self):
        from dxpx.jjfz.jjfz import JJFZAutoPlayer
        return JJFZAutoPlayer(cookies={'_xsrf': 'x'})

    @staticmethod
    def _response(html):
        return mock.Mock(status_code=200, text=html)

    def test_matching_rid_returned(self):
        html = (
            '<script>var a = 1;</script>'
            '<script>player.on("ended", function(){'
            'rid: "555", resource_id: "70244", video_id: "17965", lesson_id: "620" })</script>'
        )
        player = self._player()
        with mock.patch('dxpx.jjfz.jjfz.requests.get', return_value=self._response(html)):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 555)

    def test_mismatched_resource_rejected(self):
        html = (
            '<script>rid: "555", resource_id: "99999", video_id: "17965", lesson_id: "620"</script>'
        )
        player = self._player()
        with mock.patch('dxpx.jjfz.jjfz.requests.get', return_value=self._response(html)):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 0)

    def test_mismatched_video_rejected(self):
        html = (
            '<script>rid: "555", resource_id: "70244", video_id: "11111", lesson_id: "620"</script>'
        )
        player = self._player()
        with mock.patch('dxpx.jjfz.jjfz.requests.get', return_value=self._response(html)):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 0)

    def test_missing_rid_returns_zero(self):
        player = self._player()
        with mock.patch('dxpx.jjfz.jjfz.requests.get', return_value=self._response('<html></html>')):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 0)


class JJFZFinishSingleLessonTest(unittest.TestCase):
    def test_required_pairs_and_courseware_collected_once(self):
        from dxpx.jjfz.jjfz import JJFZAutoPlayer

        player = JJFZAutoPlayer(cookies={'_xsrf': 'x'})
        player.get_required_lessons = lambda lesson_id, page=1: (
            [('1', '11'), ('1', '12')], ['7'], 1
        )
        player.get_lesson_v_resource_id = lambda video_id, page=1: [(1, 11), (2, 22)]
        player.get_course_ware_extra_ids = lambda v_id: ('700', '70')
        player.get_lesson_r_id = lambda video_id, resource_id, page=1: 5000 + resource_id
        player.check_record = lambda lesson_id, video_id, resource_id, r_id: True

        results = player.finish_single_lesson(620)
        self.assertEqual(results['attempted'], 4)
        self.assertEqual(results['accepted'], 4)
        self.assertEqual(results['failed'], [])
        pairs = [(e['video_id'], e['resource_id']) for e in results['success']]
        self.assertEqual(sorted(pairs), [(1, 11), (1, 12), (2, 22), (7, 70)])

    def test_no_rid_reported_as_failure(self):
        from dxpx.jjfz.jjfz import JJFZAutoPlayer

        player = JJFZAutoPlayer(cookies={'_xsrf': 'x'})
        player.get_required_lessons = lambda lesson_id, page=1: ([('1', '11')], [], 1)
        player.get_lesson_v_resource_id = lambda video_id, page=1: []
        player.get_lesson_r_id = lambda video_id, resource_id, page=1: 0
        player.check_record = lambda *a, **k: self.fail('不应在无 rid 时提交')

        results = player.finish_single_lesson(620)
        self.assertEqual(results['accepted'], 0)
        self.assertEqual(results['failed'][0]['reason'], 'no_rid')


if __name__ == '__main__':
    unittest.main(verbosity=2)
