import pandas as pd
import re
from pathlib import Path

from dxpx.common.exam import BaseExam
from dxpx.jjfz.jjfz import JJFZAutoPlayer

class Exam(BaseExam):
    player_cls = JJFZAutoPlayer
    record_url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_record'

    def __init__(self, headers: dict, stage: int = 42):
        """
        初始化实例状态。
        
        :param headers: 请求头字典；认证请求通常需包含 Cookie，提交学习或答题记录时还需 _xsrf。
        :param stage: 积极分子培训阶段标识，默认值为 42。
        """
        super().__init__(headers, stage=stage)

    def start_exam(self):
        """
        请求综合考试页面，建立考试状态。
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_exam'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url=url, headers=self.headers, params=params)

    def get_question(self, question_id: int):
        """
        获取综合考试中指定序号的题目。
        
        :param question_id: 题目在当前试卷中的序号，从 1 开始。
        :return: 三元组 (title, options, qid)；options 中每项为 (选项文本, 答案标识)。
        """
        params = {
            'i': question_id,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/get_question'
        response = self.session.get(url=url, params=params, headers=self.headers)
        return self.extract_question(response.text)

    def answer_question(self, question_id: int, qid: int, answer: str):
        """
        向平台提交一道综合考试题目的答案。
        
        :param question_id: 题目在当前试卷中的序号，从 1 开始。
        :param qid: 平台分配的题目标识，不同于题目序号。
        :param answer: 提交的答案；选择题为选项标识，多选用 | 分隔，填空题为答案文本。
        :return: bool；平台接受答案时为 True，否则为 False。
        """
        params = {
            'i': question_id,
            'stg': self.stage,
        }

        data = {
            'i': question_id,
            'qid': qid,
            'answer': answer,
            '_xsrf': self.headers['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/answer'
        response = self.session.post(url=url, params=params, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def submit_exam(self):
        """
        提交当前综合考试试卷。
        
        :return: bool；平台确认提交成功时为 True，否则为 False。
        """
        data = {
            '_xsrf': self.headers['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/submit'

        params = {
            'stg': self.stage,
        }
        response = self.session.post(url=url, headers=self.headers, params=params, data=data)
        return response.json()['code'] == 1

    def get_exam_result(self):
        """
        从综合考试结果页面提取结果标识。
        
        :return: 匹配到的结果标识字符串；未匹配到时返回整数 0。
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/result'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url=url, headers=self.headers, params=params)
        pattern = r'rid=(\d+)'
        match = re.search(pattern, response.text)
        if match:
            rid = match.group(1)
        else:
            rid = 0
        return rid

    def start_lesson_exam(self, lesson_id: int):
        """
        请求指定章节测试页面，建立测试状态。
        
        :param lesson_id: 课程或章节标识。
        """
        params = {
            'lesson_id': lesson_id,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam'
        response = self.session.get(url, params=params, headers=self.headers)

    def get_lesson_question(self, lesson_id: int, question_id: int):
        """
        获取章节测试中指定序号的题目。
        
        :param lesson_id: 课程或章节标识。
        :param question_id: 题目在当前试卷中的序号，从 1 开始。
        :return: 三元组 (title, options, qid)；options 中每项为 (选项文本, 答案标识)。
        """
        params = {
            'i': question_id,
            'lid': lesson_id,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/get_question'

        response = self.session.get(url=url, params=params, headers=self.headers)
        return self.extract_question(response.text)

    def answer_lesson_question(self, lesson_id: int, question_id: int, qid: int, answer: str):
        """
        向平台提交指定章节测试题目的答案。
        
        :param lesson_id: 课程或章节标识。
        :param question_id: 题目在当前试卷中的序号，从 1 开始。
        :param qid: 平台分配的题目标识，不同于题目序号。
        :param answer: 提交的答案；选择题为选项标识，多选用 | 分隔，填空题为答案文本。
        :return: bool；平台接受答案时为 True，否则为 False。
        """
        params = {
            'i': question_id,
            'stg': self.stage,
        }

        data = {
            'i': question_id,
            'lid': lesson_id,
            'qid': qid,
            'answer': answer,
            '_xsrf': self.headers['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/answer'

        response = self.session.post(url=url, params=params, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def submit_lesson_exam(self, lesson_id: int):
        """
        向平台提交指定章节的测试试卷。
        
        :param lesson_id: 课程或章节标识。
        :return: bool；平台确认提交成功时为 True，否则为 False。
        """
        data = {
            'lid': lesson_id,
            '_xsrf': self.headers['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/submit'

        params = {
            'stg': self.stage,
        }
        response = self.session.post(url=url, headers=self.headers, params=params, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def get_lesson_exam_result(self, lesson_id: int):
        """
        从章节测试结果页面提取结果标识。
        
        :param lesson_id: 课程或章节标识。
        :return: int；匹配到的结果标识，未匹配到时为 0。
        """
        params = {
            'lid': lesson_id,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/exam/result'

        response = self.session.get(url=url, params=params, headers=self.headers)
        pattern = r'rid=(\d+)'
        match = re.search(pattern, response.text)
        if match:
            rid = match.group(1)
            return int(rid)
        return 0

    def finish_lesson_exam(self, lesson_id: int, return_new: bool=False, player: JJFZAutoPlayer=None):
        """
        完成一次章节测试，并按需收集本地题库缺失的题目。
        
        :param lesson_id: 课程或章节标识。
        :param return_new: 是否返回本地题库缺失的题目；为 False 时返回对应数量的空表。默认值为 False。
        :param player: 已加载题库的课程处理实例；为 None 时按当前流程创建实例。默认值为 None。
        :return: 单选、多选和判断三个 DataFrame；return_new 为 False 时均为空表。
        """
        if player is None:
            player = JJFZAutoPlayer(self.headers)
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

        # 只提取本轮未命中题库的题目，用结果页中的正确答案补充题库。
        if return_new:
            radios, checkboxes, yes_or_nos, _ = player.get_lesson_exam_paper(rid=rid)
            radios = [radios[i] for i in new_radios] if len(new_radios) > 0 else []
            checkboxes = [checkboxes[i] for i in new_checkboxes] if len(new_checkboxes) > 0 else []
            yes_or_nos = [yes_or_nos[i] for i in new_yes_or_nos] if len(new_yes_or_nos) > 0 else []
            return pd.DataFrame(radios), pd.DataFrame(checkboxes), pd.DataFrame(yes_or_nos)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def finish_all_lesson_exams(self, player: JJFZAutoPlayer=None):
        """
        读取本地课程列表，逐个完成章节测试并汇总新题。
        
        :param player: 可复用的课程处理实例；为 None 时使用默认课程目录并由单次测试流程创建实例。默认值为 None。
        :return: 依次包含新单选、多选和判断题的三个 DataFrame。
        """
        lesson_dir = player.lesson_dir if player is not None else JJFZAutoPlayer.lesson_dir
        lesson_path = Path(lesson_dir) / 'lessons.json'
        lessons = JJFZAutoPlayer.load_lessons(str(lesson_path))
        lesson_ids = [int(lesson['lesson_id']) for lesson in lessons]

        new_radios, new_checkboxes, new_yes_or_nos = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        for lesson_id in lesson_ids:
            radios, checkboxes, yes_or_nos = self.finish_lesson_exam(lesson_id, return_new=True, player=player)
            new_radios = pd.concat([new_radios, radios])
            new_checkboxes = pd.concat([new_checkboxes, checkboxes])
            new_yes_or_nos = pd.concat([new_yes_or_nos, yes_or_nos])
        return new_radios, new_checkboxes, new_yes_or_nos


    def finish_many_lesson_exams(self, echos: int=30):
        """
        多轮完成全部章节测试，并合并保存收集到的新题。
        
        :param echos: 批量执行轮数。默认值为 30。
        """
        player = JJFZAutoPlayer(self.headers)
        player.load_questions()
        new_radios, new_checkboxes, new_yes_or_nos = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        for i in range(echos):
            radios, checkboxes, yes_or_nos = self.finish_all_lesson_exams(player=player)
            new_radios = pd.concat([new_radios, radios])
            new_checkboxes = pd.concat([new_checkboxes, checkboxes])
            new_yes_or_nos = pd.concat([new_yes_or_nos, yes_or_nos])
        if len(new_radios) > 0:
            player.update_questions(new_radios, new_checkboxes, new_yes_or_nos, pd.DataFrame())

