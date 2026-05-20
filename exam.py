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
        print("开始综合测试")
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
        lesson_ids = [567, 568, 569, 570, 571, 572, 573, 574, 575, 576, 577]
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
        '_xsrf': '2|50c39dbf|59a5a9c2e1d8bd270abeda544ba39aa9|1779195541',
        'is_first': '"2|1:0|10:1779201638|8:is_first|4:MA==|37f1419d1d5829322f6a042ff2decc441134808aae2215ec275ba183ef0b2f0e"',
        'token': 'eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjozMjk0OCwic3RhdGUiOjEsInVzZXJfc2lkIjoiMjAyNDEzMDEwMjAyNSIsInVzZXJfbmFtZSI6Ilx1NWMzOVx1ODIyYSIsInVzZXJfcHdkIjoiZTc0NjM0MGU1OWY3ZmUxY2VhYzc2YzcxMDAzMDJhMmQ3MjhjNGY1NCIsInBhcnR5X2NhdGVnb3J5IjowLCJwaGFzZSI6MiwiYXZhdGFyIjoiIiwidHJ1ZV9hdmF0YXIiOiIiLCJyb2xlX2lkIjoxLCJwYXJ0eV9icmFuY2giOiIiLCJzc29faWQiOiIiLCJpc192aXJ0dWFsIjowLCJpc19maXJzdF9sb2dpbiI6MCwic3RhdGVfaWQiOjUxNzE2LCJzZXNzaW9uIjoiMDIyODQ5NGUtZDY3YS00NWQyLWI4YmEtNzgyZWFmY2E1YjhlIiwidG9rZW4iOjE3NzkyMDE2MzgsImV4cCI6MTc3OTIwMzQzOH0.YdZrBDfWXN4aaQqLLoIF_MR6A3HajSOhgmmPyeOLLvM',
        'menu_open': 'false',
        'ua_id': '2|1:0|10:1779203883|5:ua_id|516:eyJ1c2VyX2lkIjogMzI5NDgsICJzdGF0ZSI6IDEsICJ1c2VyX3NpZCI6ICIyMDI0MTMwMTAyMDI1IiwgInVzZXJfbmFtZSI6ICJcdTVjMzlcdTgyMmEiLCAidXNlcl9wd2QiOiAiZTc0NjM0MGU1OWY3ZmUxY2VhYzc2YzcxMDAzMDJhMmQ3MjhjNGY1NCIsICJwYXJ0eV9jYXRlZ29yeSI6IDAsICJwaGFzZSI6IDIsICJhdmF0YXIiOiAiIiwgInRydWVfYXZhdGFyIjogIiIsICJyb2xlX2lkIjogMSwgInBhcnR5X2JyYW5jaCI6ICIiLCAic3NvX2lkIjogIiIsICJpc192aXJ0dWFsIjogMCwgImlzX2ZpcnN0X2xvZ2luIjogMCwgInN0YXRlX2lkIjogNTE3MTYsICJzZXNzaW9uIjogIjAyMjg0OTRlLWQ2N2EtNDVkMi1iOGJhLTc4MmVhZmNhNWI4ZSIsICJ0b2tlbiI6IDE3NzkyMDE2Mzh9|83ca338a7a0c24500cff386e4654750a323668cf2db07188aaf27f8e77f5263c',
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
    # exam.finish_many_lesson_exams(echos=50)
    exam.finish_many_exams(echos=10)


if __name__ == '__main__':
    main()