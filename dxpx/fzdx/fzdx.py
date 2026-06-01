import json
import argparse
import re
import sys
from pathlib import Path

import requests

# if __package__ is None or __package__ == '':
#     sys.path.append(str(Path(__file__).resolve().parents[2]))

from dxpx.common.player import BaseAutoPlayer

class FZDXAutoPlayer(BaseAutoPlayer):
    question_dir = 'dxpx/fzdx/temp'
    lesson_dir = 'dxpx/fzdx/temp'

    def __init__(self, cookies: dict):
        super().__init__(cookies)
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'Connection': 'keep-alive',
            'Referer': 'https://dxpx.uestc.edu.cn/fzdx',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

    def get_lessons(self):
        """
        获取所有课程ID
        :return: 课程ID列表
        """
        url = 'https://dxpx.uestc.edu.cn/fzdx/lesson'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        pattern = r'<a href="[^"]*lesson_id=(\d+)&tag=0">'
        lesson_ids = re.findall(pattern, response.text)
        lesson_ids = list(set(lesson_ids))
        return lesson_ids

    def get_required_lessons(self, lesson_id: int, page: int = 1):
        """
        获取课程的必修课程列表
        :param lesson_id: 课程ID
        :param page: 页码
        :return: 必修课程列表，每个元素为(video_id, resource_id)元组
        """
        params = {
            'lesson_id': lesson_id,
            'page': page,
            'cat': 1
        }

        url = 'https://dxpx.uestc.edu.cn/fzdx/lesson/video'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers, params=params)

        return self.extract_required_lessons_info(response.text)

    def get_lesson_r_id(self, video_id: int, resource_id: int, page: int = 1):
        """
        获取课程的r_id
        :param video_id: 视频ID
        :param resource_id: 资源ID
        :param page: 页码，非必须参数，默认值为1
        :return: r_id
        """
        params = {
            'v_id': video_id,
            'r_id': resource_id,
            'r': 'video',
            't': '2',
            'pg': page,
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/play'

        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'rid: "(\d+)"'
        rids = re.findall(pattern, response.text)
        return int(rids[0])

    def check_record(self, lesson_id: int, video_id: int, resource_id: int, r_id: int):
        data = {
            'rid': r_id,
            'lesson_id': lesson_id,
            'resource_id': resource_id,
            'video_id': video_id,
            '_xsrf': self.cookies['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/lesson/resource_record'
        response = requests.post(url=url, cookies=self.cookies, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def get_course_ware_extra_ids(self, v_id:int):
        """
        获取只有 v_id 的微课件或者专家讲座课程的资源ID对
        :param v_id: 视频ID
        :return: 资源ID(r_id, resource_id)元组
        """
        params = {
            'v_id': v_id,
            'r': 'video',
            't': '2',
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/play'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'rid: "(\d+)",\s+resource_id: "(\d+)"'
        match = re.search(pattern, response.text)
        return int(match.group(1)), int(match.group(2))

    def get_exam_paper(self, r_id: int):
        """
        获取已完成考试的试卷详情
        :param r_id: 考试结果ID
        :return: 分类后的题目列表
        """
        params = {
            'rid': r_id,
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/end_show'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'<div class="error_sub">(.*?)</div>\s*(?=<div class="error_sub"|<div class="clear"></div>)'
        return self.extract_questions(response.text, pattern)

    def get_lesson_exam_paper(self, rid: int):
        """
        发展对象没有章节测试，返回空列表，作兼容方法
        :param rid: 考试结果ID
        :return: 分类后的题目列表
        """
        return []

    def get_exam_list(self) -> list:
        """
        获取已完成的考试列表
        :return: 已完成的考试结果ID列表
        """
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/end_record'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        pattern = r'rid=(\d+)'
        r_ids = re.findall(pattern, response.text)
        return [int(r_id) for r_id in r_ids]

    def update_from_exam_results(self):
        """
        从已完成的考试结果中更新题目
        :return:
        """
        r_ids = self.get_exam_list()
        new_radio_df, new_checkbox_df, new_yes_or_no_df, new_gap_filling_df = self.collect_unique_questions(
            r_ids=r_ids)
        self.update_questions(new_radio_df, new_checkbox_df, new_yes_or_no_df, new_gap_filling_df)

def main():
    cookies = {
        '_xsrf': '2|db676230|d2ceff2a13c79a79d32f4c77b30127d8|1780298868',
        'menu_open': 'false',
        'is_first': '"2|1:0|10:1780311172|8:is_first|4:MA==|7d6fc6047434a0c4bd9fbe8e974ae21b1e5147bc0bb1c330fd39062f66333a4e"',
        'token': 'eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoyODgyMCwic3RhdGUiOjEsInVzZXJfc2lkIjoiMjAyNDIxMTEwMzAzIiwidXNlcl9uYW1lIjoiXHU1MzRlXHU0ZTlhXHU2OTYwIiwidXNlcl9wd2QiOiI5N2E3NmZjZGQ4NDBiZDg3YjA0MzgxM2U5ODlmMmExYzA0NjA3ZWRhIiwicGFydHlfY2F0ZWdvcnkiOjAsInBoYXNlIjozLCJhdmF0YXIiOiIiLCJ0cnVlX2F2YXRhciI6Ii9zdGF0aWMvdXBsb2FkL2ltYWdlcy8yMDI1LTA1LTIyLzIwMzQ4Yzk3OWYzMGQ2Mjc0ZWRjM2MwNjM5YWQ2YTYzLmpwZyIsInJvbGVfaWQiOjEsInBhcnR5X2JyYW5jaCI6IiIsInNzb19pZCI6IiIsImlzX3ZpcnR1YWwiOjAsImlzX2ZpcnN0X2xvZ2luIjowLCJzdGF0ZV9pZCI6NTQ0NzEsInNlc3Npb24iOiI4YzcwZTE3ZS1iY2UwLTRkMzItOGMxYi02ZTAzMzEwZjA0NTMiLCJ0b2tlbiI6MTc4MDMxMTE3MiwiZXhwIjoxNzgwMzEyOTcyfQ.t81HWDikixKvCH_JH43nb7TtA76yzUDn82EiJctmJW8',
        'ua_id': '"2|1:0|10:1780311670|5:ua_id|616:eyJ1c2VyX2lkIjogMjg4MjAsICJzdGF0ZSI6IDEsICJ1c2VyX3NpZCI6ICIyMDI0MjExMTAzMDMiLCAidXNlcl9uYW1lIjogIlx1NTM0ZVx1NGU5YVx1Njk2MCIsICJ1c2VyX3B3ZCI6ICI5N2E3NmZjZGQ4NDBiZDg3YjA0MzgxM2U5ODlmMmExYzA0NjA3ZWRhIiwgInBhcnR5X2NhdGVnb3J5IjogMCwgInBoYXNlIjogMywgImF2YXRhciI6ICIiLCAidHJ1ZV9hdmF0YXIiOiAiL3N0YXRpYy91cGxvYWQvaW1hZ2VzLzIwMjUtMDUtMjIvMjAzNDhjOTc5ZjMwZDYyNzRlZGMzYzA2MzlhZDZhNjMuanBnIiwgInJvbGVfaWQiOiAxLCAicGFydHlfYnJhbmNoIjogIiIsICJzc29faWQiOiAiIiwgImlzX3ZpcnR1YWwiOiAwLCAiaXNfZmlyc3RfbG9naW4iOiAwLCAic3RhdGVfaWQiOiA1NDQ3MSwgInNlc3Npb24iOiAiOGM3MGUxN2UtYmNlMC00ZDMyLThjMWItNmUwMzMxMGYwNDUzIiwgInRva2VuIjogMTc4MDMxMTE3Mn0=|b4853d0484ffcc4b85d1b8be5fca8c40427e086fdf842da9b177bad9413dfbf4"',
    }
    parser = argparse.ArgumentParser(description='发展对象学习与题库工具')
    parser.add_argument('--init', action='store_true', help='获取课程列表并保存')
    parser.add_argument('--output-dir', default=FZDXAutoPlayer.lesson_dir, help='设置课程列表保存目录')
    parser.add_argument('--update', action='store_true', help='从已完成考试结果更新题库')
    args = parser.parse_args()

    player = FZDXAutoPlayer(cookies=cookies)
    if args.init:
        failed_list = player.get_lessons_and_save(output_dir=args.output_dir, save=True)
        print(failed_list)
    if args.update:
        player.update_from_exam_results()
    if not args.init and not args.update:
        parser.print_help()

if __name__ == '__main__':
    main()
