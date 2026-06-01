import re

import argparse
import requests
import sys
from pathlib import Path

# if __package__ is None or __package__ == '':
#     sys.path.append(str(Path(__file__).resolve().parents[2]))

from dxpx.common.exam import BaseExam
from dxpx.fzdx.fzdx import FZDXAutoPlayer

cookies = {
    '_xsrf': '2|db676230|d2ceff2a13c79a79d32f4c77b30127d8|1780298868',
    'menu_open': 'false',
    'is_first': '"2|1:0|10:1780311172|8:is_first|4:MA==|7d6fc6047434a0c4bd9fbe8e974ae21b1e5147bc0bb1c330fd39062f66333a4e"',
    'token': 'eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoyODgyMCwic3RhdGUiOjEsInVzZXJfc2lkIjoiMjAyNDIxMTEwMzAzIiwidXNlcl9uYW1lIjoiXHU1MzRlXHU0ZTlhXHU2OTYwIiwidXNlcl9wd2QiOiI5N2E3NmZjZGQ4NDBiZDg3YjA0MzgxM2U5ODlmMmExYzA0NjA3ZWRhIiwicGFydHlfY2F0ZWdvcnkiOjAsInBoYXNlIjozLCJhdmF0YXIiOiIiLCJ0cnVlX2F2YXRhciI6Ii9zdGF0aWMvdXBsb2FkL2ltYWdlcy8yMDI1LTA1LTIyLzIwMzQ4Yzk3OWYzMGQ2Mjc0ZWRjM2MwNjM5YWQ2YTYzLmpwZyIsInJvbGVfaWQiOjEsInBhcnR5X2JyYW5jaCI6IiIsInNzb19pZCI6IiIsImlzX3ZpcnR1YWwiOjAsImlzX2ZpcnN0X2xvZ2luIjowLCJzdGF0ZV9pZCI6NTQ0NzEsInNlc3Npb24iOiI4YzcwZTE3ZS1iY2UwLTRkMzItOGMxYi02ZTAzMzEwZjA0NTMiLCJ0b2tlbiI6MTc4MDMxMTE3MiwiZXhwIjoxNzgwMzEyOTcyfQ.t81HWDikixKvCH_JH43nb7TtA76yzUDn82EiJctmJW8',
    'ua_id': '"2|1:0|10:1780311670|5:ua_id|616:eyJ1c2VyX2lkIjogMjg4MjAsICJzdGF0ZSI6IDEsICJ1c2VyX3NpZCI6ICIyMDI0MjExMTAzMDMiLCAidXNlcl9uYW1lIjogIlx1NTM0ZVx1NGU5YVx1Njk2MCIsICJ1c2VyX3B3ZCI6ICI5N2E3NmZjZGQ4NDBiZDg3YjA0MzgxM2U5ODlmMmExYzA0NjA3ZWRhIiwgInBhcnR5X2NhdGVnb3J5IjogMCwgInBoYXNlIjogMywgImF2YXRhciI6ICIiLCAidHJ1ZV9hdmF0YXIiOiAiL3N0YXRpYy91cGxvYWQvaW1hZ2VzLzIwMjUtMDUtMjIvMjAzNDhjOTc5ZjMwZDYyNzRlZGMzYzA2MzlhZDZhNjMuanBnIiwgInJvbGVfaWQiOiAxLCAicGFydHlfYnJhbmNoIjogIiIsICJzc29faWQiOiAiIiwgImlzX3ZpcnR1YWwiOiAwLCAiaXNfZmlyc3RfbG9naW4iOiAwLCAic3RhdGVfaWQiOiA1NDQ3MSwgInNlc3Npb24iOiAiOGM3MGUxN2UtYmNlMC00ZDMyLThjMWItNmUwMzMxMGYwNDUzIiwgInRva2VuIjogMTc4MDMxMTE3Mn0=|b4853d0484ffcc4b85d1b8be5fca8c40427e086fdf842da9b177bad9413dfbf4"',
}

class FZDXExam(BaseExam):
    player_cls = FZDXAutoPlayer

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

    def start_exam(self):
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/exam'
        response = requests.get(url, headers=self.headers, cookies=self.cookies)
        return response

    def get_question(self, question_id: int):
        params = {
            'i': question_id,
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/get_question'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        return self.extract_question(response.text)

    def answer_question(self, question_id: int, qid: int, answer: str):
        """
        回答问题
        :param question_id: 问题ID
        :param qid: 问题QID
        :param answer: 答案。单选：某个选项的answer_id；多选：多个answer_id，用“|”相连；判断：某个选项的answer_id；填空：字符串；
        :return: 是否回答成功
        """
        params = {
            'i': question_id,
        }

        data = {
            'i': question_id,
            'qid': qid,
            'answer': answer,
            '_xsrf': self.cookies['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/answer'
        response = requests.post(url=url, params=params, cookies=self.cookies, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def submit_exam(self):
        data = {
            '_xsrf': self.cookies['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/submit'

        response = requests.post(url=url, cookies=self.cookies, headers=self.headers, data=data)
        return response.json()['code'] == 1

    def get_exam_result(self):
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/result'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        pattern = r'rid=(\d+)'
        match = re.search(pattern, response.text)
        if match:
            rid = match.group(1)
        else:
            rid = 0
        return rid

def main():
    parser = argparse.ArgumentParser(description='发展对象考试工具')
    parser.add_argument('--echos', type=int, default=10, help='设置批量完成考试的次数')
    args = parser.parse_args()

    exam = FZDXExam(cookies=cookies)
    exam.finish_many_exams(echos=args.echos)

if __name__ == '__main__':
    main()
