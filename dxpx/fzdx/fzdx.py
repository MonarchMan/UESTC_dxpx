import json
import re
from pathlib import Path
from wsgiref import headers

from dxpx.common.player import BaseAutoPlayer

class FZDXAutoPlayer(BaseAutoPlayer):
    question_dir = 'dxpx/fzdx/temp'
    lesson_dir = 'dxpx/fzdx/temp'

    def __init__(self, headers: dict):
        """
        初始化实例状态。
        
        :param headers: 请求头字典；认证请求通常需包含 Cookie，提交学习或答题记录时还需 _xsrf。
        """
        super().__init__(headers)

    def get_lessons(self) -> list[str]:
        """
        获取当前培训阶段的课程标识列表。

        :return: 从页面提取的课程标识。
        """
        url = 'https://dxpx.uestc.edu.cn/fzdx/lesson'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url=url, headers=self.headers, params=params)
        pattern = r'<a href="[^"]*lesson_id=(\d+)&tag='
        lesson_ids = re.findall(pattern, response.text)
        lesson_ids = list(set(lesson_ids))
        return lesson_ids

    def get_required_lessons(self, lesson_id: int, page: int = 1) -> tuple[list[tuple[int, int | None]], int]:
        """
        获取指定课程、页码的必修视频及分页信息。
        
        :param lesson_id: 课程或章节标识。
        :param page: 课程列表或播放页的页码，从 1 开始。默认值为 1。
        :return: 二元组 (id_pairs, total_pages)；id_pairs 为去重后的 (视频标识, 资源标识) 整数对，资源标识缺失时为 None。
        """
        params = {
            'lesson_id': lesson_id,
            'page': page,
            'cat': 1,
            'stg': self.stage,
        }

        url = 'https://dxpx.uestc.edu.cn/fzdx/lesson/video'
        response = self.session.get(url=url, headers=self.headers, params=params)

        # 查找 v_id, r_id，部分链接只有v_id
        pattern = r'href="/fzdx/play\?v_id=(\d+)(?:&r_id=(\d+))?[^"]*"'
        matches = re.findall(pattern, response.text)
        id_pairs = list(dict.fromkeys(
            (int(v_id), int(r_id) if r_id else None)
            for v_id, r_id in matches
        ))

        # 查找总页数
        total_pages = 1
        pages_pattern = r"<a\s+href='[^']*page=(\d+)[^']*'[^>]*>末页"
        pages_match = re.search(pages_pattern, response.text)
        if pages_match:
            total_pages = int(pages_match.group(1))

        return id_pairs, total_pages

    def get_lessons_and_save(self, output_dir: str | None = None, save=False) -> tuple[list, list]:
        """
        遍历课程分页，提交视频记录并按需保存课程信息。
        
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 None。
        :param save: 是否将结果保存到本地文件。默认值为 False。
        :return: 二元组 (failed_list, lessons)，分别为提交失败的记录列表和收集到的课程列表。
        """
        output_path = Path(output_dir or self.lesson_dir)
        lessons = []
        failed_list = []
        for lesson_id in self.get_lessons():
            id_params = []
            seen_pairs = set()
            page_num = 1
            while True:
                id_pairs, total_pages = self.get_required_lessons(lesson_id=lesson_id, page=page_num)
                for video_id, resource_id in id_pairs:
                    if (video_id, resource_id) in seen_pairs:
                        continue
                    # 播放页可能补全资源标识，解析前后分别检查重复项。
                    r_id, resource_id = self.get_lesson_r_id(
                        video_id=video_id, resource_id=resource_id, page=page_num,
                    )
                    pair = (video_id, resource_id)
                    if pair in seen_pairs:
                        continue
                    # 跨分页共享已处理集合，防止同一视频资源重复提交。
                    seen_pairs.add(pair)
                    entry = {'video_id': video_id, 'resource_id': resource_id}
                    success = self.check_record(
                        lesson_id=lesson_id,
                        video_id=video_id,
                        resource_id=resource_id,
                        r_id=r_id,
                    )
                    if not success:
                        failed_list.append({'lesson_id': lesson_id, **entry})
                    id_params.append(entry)
                if page_num >= total_pages:
                    break
                page_num += 1
            lessons.append({'lesson_id': lesson_id, 'id_params': id_params})
            print(f"课程{lesson_id}的相关参数已获取")
        if save:
            output_path.mkdir(parents=True, exist_ok=True)
            with (output_path / 'lessons.json').open('w', encoding='utf-8') as f:
                json.dump(lessons, f, ensure_ascii=False, indent=4)
            print(f"lessons数据已保存到{output_path / 'lessons.json'}文件")
        return failed_list, lessons

    def get_lesson_r_id(self, video_id: int, resource_id: int, page: int = 1):
        """
        从视频播放页面提取观看记录标识。
        
        :param video_id: 视频标识。
        :param resource_id: 视频资源标识；部分播放链接允许为 None。
        :param page: 课程列表或播放页的页码，从 1 开始。默认值为 1。
        :return: 二元组 (rid, resource_id)，元素为整数；未匹配到时返回 (None, None)。
        """
        params = {
            'v_id': video_id,
            'r_id': resource_id,
            'r': 'video',
            't': '2',
            'pg': page,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/play'

        response = self.session.get(url=url, params=params, headers=self.headers)
        pattern = r'rid:\s*"(\d+)"\s*,\s*resource_id:\s*"(\d+)"'
        match = re.search(pattern, response.text)

        if match:
            rid = int(match.group(1))
            resource_id = int(match.group(2))
            return rid, resource_id
        return None, None

    def check_record(self, lesson_id: int, video_id: int, resource_id: int, r_id: int):
        """
        向平台提交指定视频的观看记录。
        
        :param lesson_id: 课程或章节标识。
        :param video_id: 视频标识。
        :param resource_id: 视频资源标识；部分播放链接允许为 None。
        :param r_id: 视频观看记录标识。
        :return: bool；平台确认接受记录时为 True，否则为 False。
        """
        data = {
            'rid': r_id,
            'lesson_id': lesson_id,
            'resource_id': resource_id,
            'video_id': video_id,
            '_xsrf': self.headers['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/lesson/resource_record'
        params = {
            'stg': self.stage,
        }
        response = self.session.post(url=url, headers=self.headers, params=params, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def get_course_ware_extra_ids(self, v_id:int):
        """
        从微课件或专家讲座播放页面提取观看记录和资源标识。
        
        :param v_id: 用于加载播放页的视频标识。
        :return: tuple[int, int]；观看记录标识与资源标识。
        """
        params = {
            'v_id': v_id,
            'r': 'video',
            't': '2',
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/play'
        response = self.session.get(url=url, params=params, headers=self.headers)
        pattern = r'rid: "(\d+)",\s+resource_id: "(\d+)"'
        match = re.search(pattern, response.text)
        return int(match.group(1)), int(match.group(2))

    def get_exam_paper(self, r_id: int):
        """
        获取已完成综合考试的题目及正确答案。
        
        :param r_id: 已完成综合考试的结果标识。
        :return: 四元组 (radios, checkboxes, yes_or_nos, gap_fillings)，每项为题目字典列表。
        """
        params = {
            'rid': r_id,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/end_show'
        response = self.session.get(url=url, params=params, headers=self.headers)
        # 以相邻题目或页脚为边界，避免填空题内部的 clear 标签截断答案。
        pattern = r'<div class="error_sub">(.*?)(?=<div class="error_sub">|<div class="foot\b|$)'
        return self.extract_questions(response.text, pattern)

    def get_lesson_exam_paper(self, rid: int):
        """
        为不提供章节测试的发展对象模块保留兼容接口。
        
        :param rid: 章节测试结果标识。
        :return: 空列表；该模块不提供章节测试题目。
        """
        return []

    def get_exam_list(self) -> list:
        """
        获取已完成综合考试的结果标识列表。
        
        :return: list[int]；综合考试结果标识列表。
        """
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/end_record'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url=url, headers=self.headers, params=params)
        pattern = r'rid=(\d+)'
        r_ids = re.findall(pattern, response.text)
        return [int(r_id) for r_id in r_ids]

    def update_from_exam_results(self):
        """
        从已完成考试的结果中收集新题，更新并保存本地题库。
        """
        r_ids = self.get_exam_list()
        new_radio_df, new_checkbox_df, new_yes_or_no_df, new_gap_filling_df = self.collect_unique_questions(
            r_ids=r_ids)
        self.update_questions(new_radio_df, new_checkbox_df, new_yes_or_no_df, new_gap_filling_df)

    def get_lesson_videos(self, stage: int = 43):
        """
        从用户培训课程页面提取指定阶段的视频标识。
        
        :param stage: 培训阶段标识。默认值为 43。
        :return: list[int]；匹配到的视频标识列表。
        """
        url = 'https://dxpx.uestc.edu.cn/user/training/lesson'

        params = {
            'stg': stage,
        }
        response = self.session.get(url=url, params=params, headers=self.headers)
        pattern = rf'<a href="/fzdx/play?v_id=(\d+)&r=video&t=2&stg={stage}" target="_top"'
        v_ids = re.findall(pattern, response.text)
        return [int(v_id) for v_id in v_ids]
