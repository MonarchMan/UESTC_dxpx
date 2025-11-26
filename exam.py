import pandas as pd
import requests
import re
import numpy as np
from jjfz import JJFZAutoPlayer

class Exam:
    def __init__(self, cookies):
        self.cookies = cookies
        self.headers = {
            'Accept': 'text/html, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Connection': 'keep-alive',
            'Referer': 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_exam',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

    def start_exam(self):
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_exam'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)

    def get_question(self, question_id: int):
        params = {
            'i': question_id,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/get_question'
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
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/answer'
        response = requests.post(url=url, params=params, cookies=self.cookies, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def submit_exam(self):
        data = {
            '_xsrf': self.cookies['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/submit'

        response = requests.post(url=url, cookies=self.cookies, headers=self.headers, data=data)
        return response.json()['code'] == 1

    def get_exam_result(self):
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/result'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        pattern = r'rid=(\d+)'
        match = re.search(pattern, response.text)
        if match:
            rid = match.group(1)
        else:
            rid = 0
        return rid

    def finish_exam(self, return_new: bool=False, player: JJFZAutoPlayer = None):
        if player is None:
            player = JJFZAutoPlayer(self.cookies)
            player.load_questions()
        self.start_exam()
        print("开始考试")
        new_radios = []
        new_checkboxes = []
        new_yes_or_nos = []
        new_gap_fillings = []
        # 单选
        for i in range(1, 31):
            title, options, qid = self.get_question(i)
            answer = player.search_answer(title, 'radio')
            if answer:
                index = ord(answer[0]) - ord('A')
                self.answer_question(i, qid, options[index][1])
            else:
                self.answer_question(i, qid, options[0][1])
                new_radios.append(i - 1)

        # 多选
        for i in range(31, 61):
            title, options, qid = self.get_question(i)
            answer = player.search_answer(title, 'checkbox')
            if answer:
                final_answer = []
                for option in answer:
                    index = ord(option) - ord('A')
                    final_answer.append(options[index][1])
                self.answer_question(i, qid, '|'.join(final_answer))
            else:
                self.answer_question(i, qid, options[0][1] + '|' + options[1][1])
                new_checkboxes.append(i - 31)

        # 判断
        for i in range(61, 81):
            title, options, qid = self.get_question(i)
            answer = player.search_answer(title, 'yes_or_no')
            if answer:
                index = ord(answer[0]) - ord('A')
                self.answer_question(i, qid, options[index][1])
            else:
                self.answer_question(i, qid, options[0][1])
                new_yes_or_nos.append(i - 61)

        # 填空
        for i in range(81, 101):
            title, options, qid = self.get_question(i)
            answer = player.search_answer(title, 'gap_filling')
            if answer:
                self.answer_question(i, qid, answer)
            else:
                self.answer_question(i, qid, "unknown answer")
                new_gap_fillings.append(i - 81)

        self.submit_exam()
        rid = self.get_exam_result()
        print("提交试卷，考试结束")

        if return_new:
            radios, checkboxes, yes_or_nos, gap_fillings = player.get_exam_paper(r_id=rid)
            radios = [radios[i] for i in new_radios] if len(new_radios) > 0 else []
            checkboxes = [checkboxes[i] for i in new_checkboxes] if len(new_checkboxes) > 0 else []
            yes_or_nos = [yes_or_nos[i] for i in new_yes_or_nos] if len(new_yes_or_nos) > 0 else []
            gap_fillings = [gap_fillings[i] for i in new_gap_fillings] if len(new_gap_fillings) > 0 else []
            return pd.DataFrame(radios), pd.DataFrame(checkboxes), pd.DataFrame(yes_or_nos), pd.DataFrame(gap_fillings)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def finish_many_exams(self, echos: int=30):
        player = JJFZAutoPlayer(self.cookies)
        player.load_questions()
        new_radios, new_checkboxes, new_yes_or_nos, new_gap_fillings = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        for i in range(echos):
            radios, checkboxes, yes_or_nos, gap_fillings = self.finish_exam(return_new=True, player=player)
            new_radios = pd.concat([new_radios, radios])
            new_checkboxes = pd.concat([new_checkboxes, checkboxes])
            new_yes_or_nos = pd.concat([new_yes_or_nos, yes_or_nos])
            new_gap_fillings = pd.concat([new_gap_fillings, gap_fillings])
        if len(new_radios) > 0:
            player.update_questions(new_radios, new_checkboxes, new_yes_or_nos, new_gap_fillings)

    def start_lesson_exam(self, lesson_id: int):
        params = {
            'lesson_id': lesson_id,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam'
        response = requests.get(url, params=params, cookies=self.cookies, headers=self.headers)

    def get_lesson_question(self, lesson_id: int, question_id: int):
        params = {
            'i': question_id,
            'lid': lesson_id,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/get_question'

        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        return self.extract_question(response.text)

    def answer_lesson_question(self, lesson_id: int, question_id: int, qid: int, answer: str):
        params = {
            'i': question_id,
        }

        data = {
            'i': question_id,
            'lid': lesson_id,
            'qid': qid,
            'answer': answer,
            '_xsrf': self.cookies['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/answer'

        response = requests.post(url=url, params=params, cookies=self.cookies, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def submit_lesson_exam(self, lesson_id: int):
        data = {
            'lid': lesson_id,
            '_xsrf': self.cookies['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/submit'

        response = requests.post(url=url, cookies=self.cookies, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def get_lesson_exam_result(self, lesson_id: int):
        """
        获取章节测试结果
        :param lesson_id: 章节ID
        :return: 考试结果ID
        """
        params = {
            'lid': lesson_id,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/result'

        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'rid=(\d+)'
        match = re.search(pattern, response.text)
        if match:
            rid = match.group(1)
            return int(rid)
        return 0

    def finish_lesson_exam(self, lesson_id: int, return_new: bool=False, player: JJFZAutoPlayer=None):
        if player is None:
            player = JJFZAutoPlayer(self.cookies)
            player.load_questions()
        self.start_lesson_exam(lesson_id)
        print("开始章节测试")

        new_radios = []
        new_checkboxes = []
        new_yes_or_nos = []
        # 单选
        for i in range(1, 11):
            title, options, qid = self.get_lesson_question(lesson_id, i)
            answer = player.search_answer(title, 'radio')
            if answer:
                index = ord(answer[0]) - ord('A')
                self.answer_lesson_question(lesson_id, i, qid, options[index][1])
            else:
                self.answer_lesson_question(lesson_id, i, qid, options[0][1])
                new_radios.append(i - 1)

        # 多选
        for i in range(11, 16):
            title, options, qid = self.get_lesson_question(lesson_id, i)
            answer = player.search_answer(title, 'checkbox')
            if answer:
                final_answer = []
                for option in answer:
                    index = ord(option) - ord('A')
                    final_answer.append(options[index][1])
                self.answer_lesson_question(lesson_id, i, qid, '|'.join(final_answer))
            else:
                self.answer_lesson_question(lesson_id, i, qid, options[0][1] + '|' + options[1][1])
                new_checkboxes.append(i - 11)

        # 判断
        for i in range(16, 21):
            title, options, qid = self.get_lesson_question(lesson_id, i)
            answer = player.search_answer(title, 'yes_or_no')
            if answer:
                index = ord(answer[0]) - ord('A')
                self.answer_lesson_question(lesson_id, i, qid, options[index][1])
            else:
                self.answer_lesson_question(lesson_id, i, qid, options[0][1])
                new_yes_or_nos.append(i - 16)

        self.submit_lesson_exam(lesson_id)
        rid = self.get_lesson_exam_result(lesson_id)
        print("提交试卷，章节测试结束")

        if return_new:
            radios, checkboxes, yes_or_nos, _ = player.get_lesson_exam_paper(rid=rid)
            radios = [radios[i] for i in new_radios] if len(new_radios) > 0 else []
            checkboxes = [checkboxes[i] for i in new_checkboxes] if len(new_checkboxes) > 0 else []
            yes_or_nos = [yes_or_nos[i] for i in new_yes_or_nos] if len(new_yes_or_nos) > 0 else []
            return pd.DataFrame(radios), pd.DataFrame(checkboxes), pd.DataFrame(yes_or_nos)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def finish_all_lesson_exams(self, player: JJFZAutoPlayer=None):
        lesson_ids = [514, 515, 516, 517, 518, 519, 520, 521, 522, 523, 524, 547, 553]
        new_radios, new_checkboxes, new_yes_or_nos = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        for lesson_id in lesson_ids:
            radios, checkboxes, yes_or_nos = self.finish_lesson_exam(lesson_id, return_new=True, player=player)
            new_radios = pd.concat([new_radios, radios])
            new_checkboxes = pd.concat([new_checkboxes, checkboxes])
            new_yes_or_nos = pd.concat([new_yes_or_nos, yes_or_nos])
        return new_radios, new_checkboxes, new_yes_or_nos


    def finish_many_lesson_exams(self, echos: int=30):
        player = JJFZAutoPlayer(self.cookies)
        player.load_questions()
        new_radios, new_checkboxes, new_yes_or_nos = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        for i in range(echos):
            radios, checkboxes, yes_or_nos = self.finish_all_lesson_exams(player=player)
            new_radios = pd.concat([new_radios, radios])
            new_checkboxes = pd.concat([new_checkboxes, checkboxes])
            new_yes_or_nos = pd.concat([new_yes_or_nos, yes_or_nos])
        if len(new_radios) > 0:
            player.update_questions(new_radios, new_checkboxes, new_yes_or_nos, pd.DataFrame())


    @staticmethod
    def extract_question(html: str):
        exam_label_pattern = r'<div[^>]*class="exam_label_btn[^"]*"[^>]*data-val="([^"]*)"'
        qid_match = re.search(exam_label_pattern, html)
        if qid_match:
            qid = int(qid_match.group(1))
        else:
            qid = 0
        title_pattern = r'<h2[^>]*>(.*?)</h2>'
        title_match = re.search(title_pattern, html)
        if title_match:
            # 先去除开头数字，再处理空白字符
            cleaned_title = re.sub(r'^\d+.\s*', '', title_match.group(1))
            title = cleaned_title
        else:
            title = 'No title found'

        # 获取选项
        options_pattern = r'<label[^>]*>(.*?)</label>'
        labels = re.findall(options_pattern, html, re.DOTALL)
        options = []
        for label_content in labels:
            # 从 input 标签提取 answer_id
            answer_id_match = re.search(r'value="(\d+)"', label_content)
            if answer_id_match:
                answer_id = answer_id_match.group(1)
            else:
                answer_id = ''
            # 移除 input 标签
            option_text = re.sub(r'<input[^>]*/?>', '', label_content)
            # 清理空白字符
            option_text = re.sub(r'\s+', ' ', option_text.strip())
            if option_text:
                options.append((option_text, answer_id))

        return title, options, qid


def main():
    cookies = {
        'first_lesson_study': '1',
        '_xsrf': '2|95603c0c|6a5e80cd340c5747d2f5683bc6a566b2|1763696561',
        'menu_open': 'false',
        'is_first': '"2|1:0|10:1764089803|8:is_first|4:MA==|cd2cf025ed7ad821dad88c02585a6cc94699e0cb0e9534a01aa6d238db89fc86"',
        'token': 'eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjozMDcyNywic3RhdGUiOjEsInVzZXJfc2lkIjoiMjAyNTIxMTEwMzIzIiwidXNlcl9uYW1lIjoiXHU1ZjkwXHU0ZTM0XHU1ZGRkIiwidXNlcl9wd2QiOiI5NTFlYWFhODNlODUzZmEwMzk0ODQwOTE2ZTlmZjljMGE5NGZmZjZhIiwicGFydHlfY2F0ZWdvcnkiOjAsInBoYXNlIjoyLCJhdmF0YXIiOiIiLCJ0cnVlX2F2YXRhciI6IiIsInJvbGVfaWQiOjEsInBhcnR5X2JyYW5jaCI6IiIsInNzb19pZCI6IiIsImlzX3ZpcnR1YWwiOjAsImlzX2ZpcnN0X2xvZ2luIjowLCJzdGF0ZV9pZCI6NDc5NDksInNlc3Npb24iOiJmZGQ5OGNlMC00OTJjLTQ0YzItYmY2Yi0xYTNhMTAzNWJlZDUiLCJ0b2tlbiI6MTc2NDA4OTgwMywiZXhwIjoxNzY0MDkxNjAzfQ.D24TXxTwf_mbdHaK6QfciBWhUm1rLIFB-f-uM9TYib8',
        'ua_id': '"2|1:0|10:1764089878|5:ua_id|524:eyJ1c2VyX2lkIjogMzA3MjcsICJzdGF0ZSI6IDEsICJ1c2VyX3NpZCI6ICIyMDI1MjExMTAzMjMiLCAidXNlcl9uYW1lIjogIlx1NWY5MFx1NGUzNFx1NWRkZCIsICJ1c2VyX3B3ZCI6ICI5NTFlYWFhODNlODUzZmEwMzk0ODQwOTE2ZTlmZjljMGE5NGZmZjZhIiwgInBhcnR5X2NhdGVnb3J5IjogMCwgInBoYXNlIjogMiwgImF2YXRhciI6ICIiLCAidHJ1ZV9hdmF0YXIiOiAiIiwgInJvbGVfaWQiOiAxLCAicGFydHlfYnJhbmNoIjogIiIsICJzc29faWQiOiAiIiwgImlzX3ZpcnR1YWwiOiAwLCAiaXNfZmlyc3RfbG9naW4iOiAwLCAic3RhdGVfaWQiOiA0Nzk0OSwgInNlc3Npb24iOiAiZmRkOThjZTAtNDkyYy00NGMyLWJmNmItMWEzYTEwMzViZWQ1IiwgInRva2VuIjogMTc2NDA4OTgwM30=|66e0eb98d5a3d68a6724e28ee868a68197e82d7fb5a4b7f54a0f92fbe1e0ec6f"',
    }

    exam = Exam(cookies=cookies)
    # for i in range(30):
    #     print(f"第{i+1}次考试")
    #     exam.finish_exam()
    # exam.finish_many_exams(echos=40)
    # title, options, qid = exam.get_lesson_question(lesson_id=514, question_id=1)
    # exam.answer_lesson_question(lesson_id=514, question_id=1, qid=qid, answer=options[0][1])
    # for i in range(100):
    #     exam.finish_all_lesson_exams()
    exam.finish_many_lesson_exams(echos=50)


if __name__ == '__main__':
    main()