"""课程解析与记录提交的离线测试，不读取身份信息或访问平台。"""

import json
import os
import tempfile
import unittest
from unittest import mock

from dxpx.common.player import BaseAutoPlayer
from dxpx.jjfz.jjfz import JJFZAutoPlayer


class FakePlayer(JJFZAutoPlayer):
    """用内存数据替代网络请求，专注验证分页/去重/保护逻辑。"""

    def __init__(self, pages, courseware=None):
        """
        创建不联网的课程测试实例。

        :param pages: 按页码保存的资源与分页信息。
        :param courseware: 按视频标识保存的微课件记录。
        """
        super().__init__(headers={})
        # pages: {page:int -> (id_pairs, courseware_ids, total_pages)}
        self.pages = pages
        self.courseware = courseware or {}
        self.requested_pages = []
        self.record_calls = []
        self.r_id_calls = []
        self.r_ids = {}

    def get_lesson_v_resource_id(self, video_id, page=1):
        """
        返回空的相邻资源列表。

        :param video_id: 视频标识。
        :param page: 页码，默认值为 1。
        :return: list；固定返回空列表。
        """
        return []

    def get_lessons(self):
        """
        返回固定的课程标识。

        :return: list；测试课程标识。
        """
        return ['620']

    def get_required_lessons(self, lesson_id, page=1):
        """
        记录页码并返回对应测试数据。

        :param lesson_id: 课程标识。
        :param page: 页码，默认值为 1。
        :return: 三元组；资源对、微课件标识和总页数。
        """
        self.requested_pages.append(page)
        return self.pages.get(page, ([], [], 1))

    def get_lesson_r_id(self, video_id, resource_id, page=1):
        """
        记录资源解析请求并返回预设记录标识。

        :param video_id: 视频标识。
        :param resource_id: 资源标识。
        :param page: 页码，默认值为 1。
        :return: int；观看记录标识。
        """
        self.r_id_calls.append((video_id, resource_id, page))
        return self.r_ids.get((video_id, resource_id), 9000 + resource_id)

    def check_record(self, lesson_id, video_id, resource_id, r_id):
        """
        记录提交参数并模拟接口接受。

        :param lesson_id: 课程标识。
        :param video_id: 视频标识。
        :param resource_id: 资源标识。
        :param r_id: 观看记录标识。
        :return: bool；固定返回 True。
        """
        self.record_calls.append((lesson_id, video_id, resource_id, r_id))
        return True

    def get_course_ware_extra_ids(self, v_id):
        """
        返回预设的微课件记录。

        :param v_id: 视频标识。
        :return: 二元组；观看记录和资源标识，未配置时为 None。
        """
        return self.courseware.get(v_id)


class ExtractInfoTest(unittest.TestCase):
    def _page(self, links, footer=''):
        """
        构造课程列表测试页面。

        :param links: 视频与资源标识对。
        :param footer: 分页链接 HTML，默认为空。
        :return: str；测试页面 HTML。
        """
        anchors = ''.join(
            f'<a class="" href="/jjfz/play?v_id={v}&r_id={r}&r=video&pg=1">x</a>'
            for v, r in links
        )
        return f'<html><body>{anchors}{footer}</body></html>'

    def test_same_video_different_resources_kept(self):
        """
        验证同一视频的不同资源均被保留。
        """
        text = self._page([(17965, 70244), (17965, 70245), (17935, 69894)])
        id_pairs, _, _ = BaseAutoPlayer.extract_required_lessons_info(text)
        self.assertIn(('17965', '70244'), id_pairs)
        self.assertIn(('17965', '70245'), id_pairs)
        self.assertEqual(len(id_pairs), 3)

    def test_duplicate_links_deduped(self):
        """
        验证重复链接只保留一次。
        """
        text = self._page([(17965, 70244), (17965, 70244), (17935, 69894)])
        id_pairs, _, _ = BaseAutoPlayer.extract_required_lessons_info(text)
        self.assertEqual(id_pairs, [('17965', '70244'), ('17935', '69894')])

    def test_total_pages_from_last_page_link(self):
        """
        验证末页链接的总页数解析。
        """
        text = self._page(
            [(1, 2)],
            footer='<a href="/jjfz/lesson/video?lesson_id=620&page=1">1</a>'
                   '<a href="/jjfz/lesson/video?lesson_id=620&page=3">末页</a>',
        )
        _, _, total_pages = BaseAutoPlayer.extract_required_lessons_info(text)
        self.assertEqual(total_pages, 3)

    def test_total_pages_default_one(self):
        """
        验证无分页时总页数默认为一。
        """
        _, _, total_pages = BaseAutoPlayer.extract_required_lessons_info(self._page([(1, 2)]))
        self.assertEqual(total_pages, 1)


class GetLessonsAndSaveTest(unittest.TestCase):
    def test_pagination_requests_each_page_once(self):
        """
        验证每页仅采集一次且播放页码正确。
        """
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
        """
        验证跨页重复资源仅提交一次。
        """
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
        """
        验证同一视频的不同分节均被提交。
        """
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
        """
        验证微课件资源被采集。
        """
        player = FakePlayer({1: ([], ['7'], 1)}, courseware={7: ('700', '70')})
        _, lessons = player.get_lessons_and_save(save=False)
        self.assertEqual(lessons[0]['id_params'], [{'video_id': 7, 'resource_id': 70}])
        self.assertEqual(player.record_calls, [('620', 7, 70, 700)])

    def test_courseware_without_resource_reported_not_crashed(self):
        """
        验证缺失微课件资源时记录失败。
        """
        player = FakePlayer({1: ([('1', '11')], ['7'], 1)}, courseware={})
        failed, lessons = player.get_lessons_and_save(save=False)
        self.assertEqual(len(lessons[0]['id_params']), 1)
        self.assertEqual(failed[0]['reason'], 'no_resource_id')

    def test_no_rid_not_submitted(self):
        """
        验证无观看记录标识时不提交。
        """
        player = FakePlayer({1: ([('1', '11')], [], 1)})
        player.r_ids[(1, 11)] = 0
        failed, _ = player.get_lessons_and_save(save=False)
        self.assertEqual(player.record_calls, [])
        self.assertEqual(failed[0]['reason'], 'no_rid')

    def test_empty_lesson_list_raises_and_keeps_file(self):
        """
        验证空课程结果不会覆盖已有文件。
        """
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
        """
        读取测试文件内容。

        :param path: 测试文件路径。
        :return: str；文件文本。
        """
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_all_pages_empty_raises(self):
        """
        验证全部分页为空时明确失败。
        """
        player = FakePlayer({1: ([], [], 1)})
        with self.assertRaises(RuntimeError):
            player.get_lessons_and_save(save=False)

    def test_page_loop_is_bounded(self):
        """
        验证分页超限时明确失败。
        """
        # total_pages 异常巨大时不会无限翻页
        player = FakePlayer({page: ([('1', '11')], [], 999999) for page in range(1, 4)})
        player.max_pages_per_lesson = 3
        with self.assertRaises(RuntimeError):
            player.get_lessons_and_save(save=False)
        self.assertEqual(player.requested_pages, [1, 2, 3])

    def test_saved_file_contains_all_pages(self):
        """
        验证保存结果聚合全部分页，播放参数使用当前页码。
        """
        player = FakePlayer({1: ([('1', '11')], [], 2), 2: ([('2', '22')], [], 2)})
        with tempfile.TemporaryDirectory() as directory:
            _, lessons = player.get_lessons_and_save(output_dir=directory, save=True)
            with open(os.path.join(directory, 'lessons.json'), encoding='utf-8') as file:
                self.assertEqual(json.load(file), lessons)
        self.assertEqual(player.r_id_calls, [(1, 11, 1), (2, 22, 2)])

    def test_duplicate_lessons_processed_once(self):
        """
        验证重复课程只处理一次。
        """
        player = FakePlayer({1: ([('1', '11')], [], 1)})
        player.get_lessons = lambda: ['620', '620']
        _, lessons = player.get_lessons_and_save()
        self.assertEqual(len(lessons), 1)
        self.assertEqual(len(player.record_calls), 1)


class FinishFromLocalTest(unittest.TestCase):
    def test_duplicate_entries_submitted_once(self):
        """
        验证本地重复条目仅提交一次。
        """
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
        """
        创建不联网的课程处理实例。

        :return: JJFZAutoPlayer；测试实例。
        """
        return JJFZAutoPlayer(headers={'_xsrf': 'x'})

    @staticmethod
    def _response(html):
        """
        构造页面响应。

        :param html: 响应的 HTML 文本。
        :return: Mock；模拟成功响应。
        """
        return mock.Mock(status_code=200, text=html)

    def test_matching_rid_returned(self):
        """
        验证脚本位置改变后仍能匹配记录。
        """
        html = (
            '<script>var a = 1;</script>'
            '<script>player.on("ended", function(){'
            'rid: "555", resource_id: "70244", video_id: "17965", lesson_id: "620" })</script>'
        )
        player = self._player()
        with mock.patch.object(player.session, 'get', return_value=self._response(html)):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 555)

    def test_mismatched_resource_rejected(self):
        """
        验证不匹配的资源记录被拒绝。
        """
        html = (
            '<script>rid: "555", resource_id: "99999", video_id: "17965", lesson_id: "620"</script>'
        )
        player = self._player()
        with mock.patch.object(player.session, 'get', return_value=self._response(html)):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 0)

    def test_mismatched_video_rejected(self):
        """
        验证不匹配的视频记录被拒绝。
        """
        html = (
            '<script>rid: "555", resource_id: "70244", video_id: "11111", lesson_id: "620"</script>'
        )
        player = self._player()
        with mock.patch.object(player.session, 'get', return_value=self._response(html)):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 0)

    def test_missing_rid_returns_zero(self):
        """
        验证未找到记录时返回零。
        """
        player = self._player()
        with mock.patch.object(player.session, 'get', return_value=self._response('<html></html>')):
            self.assertEqual(player.get_lesson_r_id(17965, 70244), 0)


class JJFZFinishSingleLessonTest(unittest.TestCase):
    def test_all_pages_processed_with_current_page(self):
        """
        验证指定课程模式遍历全部分页并正确传递播放页码。
        """
        player = FakePlayer({
            1: ([('1', '11')], [], 2),
            2: ([('1', '11'), ('2', '22')], [], 2),
        })
        results = player.finish_single_lesson(620)
        self.assertEqual(player.requested_pages, [1, 2])
        self.assertEqual(player.r_id_calls, [(1, 11, 1), (2, 22, 2)])
        self.assertEqual(results['accepted'], 2)

    def test_empty_course_reported_as_failed(self):
        """
        验证没有获取到资源的课程不会报告成功。
        """
        player = FakePlayer({1: ([], [], 1)})
        self.assertEqual(player.finish_lessons([620]), [620])

    def test_single_lesson_page_limit_raises(self):
        """
        验证指定课程模式分页超限时明确失败。
        """
        player = FakePlayer({1: ([('1', '11')], [], 2)})
        player.max_pages_per_lesson = 1
        with self.assertRaises(RuntimeError):
            player.finish_single_lesson(620)

    def test_required_pairs_and_courseware_collected_once(self):
        """
        验证普通资源与微课件去重后提交。
        """

        player = JJFZAutoPlayer(headers={'_xsrf': 'x'})
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
        """
        验证缺失观看记录标识时返回失败。
        """

        player = JJFZAutoPlayer(headers={'_xsrf': 'x'})
        player.get_required_lessons = lambda lesson_id, page=1: ([('1', '11')], [], 1)
        player.get_lesson_v_resource_id = lambda video_id, page=1: []
        player.get_lesson_r_id = lambda video_id, resource_id, page=1: 0
        player.check_record = lambda *a, **k: self.fail('不应在无 rid 时提交')

        results = player.finish_single_lesson(620)
        self.assertEqual(results['accepted'], 0)
        self.assertEqual(results['failed'][0]['reason'], 'no_rid')


class JJFZRequestCompatibilityTest(unittest.TestCase):
    def test_headers_identity_and_stage_preserved(self):
        """
        验证导航标头不会丢失身份、保存路径及会话共享关系。
        """
        from dxpx.common.login import LoginHeaders
        from dxpx.jjfz.exam import Exam
        from dxpx.fzdx.fzdx import FZDXAutoPlayer

        headers = LoginHeaders({
            'Cookie': '_xsrf=test', 'X-Requested-With': 'XMLHttpRequest',
            'content-type': 'application/json',
        }, 'custom.json')
        player = JJFZAutoPlayer(headers=headers)
        self.addCleanup(player.session.close)
        self.assertIs(player.headers, headers)
        self.assertIs(player.session.shared_headers, headers)
        self.assertEqual(player.session.headers_file, headers.path)
        self.assertEqual(headers['Cookie'], '_xsrf=test')
        self.assertNotIn('x-requested-with', {key.lower() for key in headers})
        self.assertNotIn('content-type', {key.lower() for key in headers})
        self.assertEqual(player.stage, 42)
        exam = Exam(headers={})
        fzdx = FZDXAutoPlayer(headers={})
        self.addCleanup(exam.session.close)
        self.addCleanup(fzdx.session.close)
        self.assertEqual(exam.stage, 42)
        self.assertEqual(fzdx.stage, 43)

    def test_lesson_links_with_extra_params(self):
        """
        验证课程链接携带阶段参数及重复链接时的提取结果。
        """
        player = JJFZAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        response = mock.Mock(text=(
            '<a href="/jjfz/lesson/video?lesson_id=620&stg=42">课程</a>'
            "<a class='lesson' href='/jjfz/lesson/video?lesson_id=621&stg=42'>课程</a>"
            '<a href="/jjfz/lesson/video?lesson_id=620">重复</a>'
        ))
        with mock.patch.object(player.session, 'get', return_value=response) as get:
            self.assertEqual(player.get_lessons(), ['620', '621'])
        self.assertEqual(get.call_args.kwargs['params'], {'stg': 42})

    def test_correct_record_endpoint_and_params(self):
        """
        验证观看记录使用播放页接口及独立的阶段查询参数。
        """
        player = JJFZAutoPlayer(headers={'_xsrf': 'test'})
        self.addCleanup(player.session.close)
        response = mock.Mock(status_code=200)
        response.json.return_value = {'code': 1}
        with mock.patch.object(player.session, 'post', return_value=response) as post:
            self.assertTrue(player.check_record(620, 1, 11, 111))
        self.assertTrue(post.call_args.kwargs['url'].endswith('/jjfz/play/resource_record'))
        self.assertEqual(post.call_args.kwargs['params'], {'stg': 42})

    def test_multiple_records_in_same_script(self):
        """
        验证同一脚本中先出现其他资源记录时仍能找到目标记录。
        """
        player = JJFZAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        response = mock.Mock(text=(
            '<script>rid: "111", resource_id: "99", video_id: "1", lesson_id: "620";'
            "rid: '222', resource_id: '11', video_id: '1', lesson_id: '620'</script>"
        ))
        with mock.patch.object(player.session, 'get', return_value=response):
            self.assertEqual(player.get_lesson_r_id(1, 11), 222)

    def test_missing_rid_never_posts(self):
        """
        验证本地记录等调用路径缺少 rid 时不会发送提交请求。
        """
        player = JJFZAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        with mock.patch.object(player.session, 'post') as post:
            self.assertFalse(player.check_record(620, 1, 11, 0))
        post.assert_not_called()

    def test_missing_courseware_record_returns_none(self):
        """
        验证微课件记录缺失时返回 None 而不抛解析异常。
        """
        player = JJFZAutoPlayer(headers={})
        self.addCleanup(player.session.close)
        with mock.patch.object(player.session, 'get', return_value=mock.Mock(text='<html></html>')):
            self.assertIsNone(player.get_course_ware_extra_ids(1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
