import re

import argparse
import requests
import sys
from pathlib import Path

# if __package__ is None or __package__ == '':
#     sys.path.append(str(Path(__file__).resolve().parents[2]))

from dxpx.common.cookies import load_cookies
from dxpx.common.exam import BaseExam
from dxpx.fzdx.fzdx import FZDXAutoPlayer

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
    parser.add_argument(
        '--cookies-file', default='cookies.json',
        help='cookies JSON 文件路径（默认 cookies.json）',
    )
    parser.add_argument('--echos', type=int, default=10, help='设置批量完成考试的次数')
    args = parser.parse_args()

    try:
        cookies = load_cookies(args.cookies_file)
    except FileNotFoundError:
        print(f"❌ 找不到 cookies 文件: {args.cookies_file}")
        print("   请从 cookies.example.json 复制一份，填入你的登录信息")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    exam = FZDXExam(cookies=cookies)
    exam.finish_many_exams(echos=args.echos)

if __name__ == '__main__':
    main()
