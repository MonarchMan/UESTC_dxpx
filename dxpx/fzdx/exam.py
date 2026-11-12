import re

from dxpx.common.exam import BaseExam
from dxpx.fzdx.fzdx import FZDXAutoPlayer

class FZDXExam(BaseExam):
    player_cls = FZDXAutoPlayer

    def __init__(self, headers: dict):
        """
        初始化实例状态。
        
        :param headers: 请求头字典；认证请求通常需包含 Cookie，提交学习或答题记录时还需 _xsrf。
        """
        super().__init__(headers)

    def start_exam(self):
        """
        请求综合考试页面，建立考试状态。
        
        :return: requests.Response；已检查 HTTP 状态的考试页面响应。
        """
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/exam'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response

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
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/get_question'
        response = self.session.get(url=url, params=params, headers=self.headers, timeout=30)
        response.raise_for_status()
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
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/answer'
        response = self.session.post(url=url, params=params, headers=self.headers, data=data, timeout=30)
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
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/submit'

        params = {
            'stg': self.stage,
        }
        response = self.session.post(url=url, headers=self.headers, params=params, data=data, timeout=30)
        response.raise_for_status()
        return response.json()['code'] == 1

    def get_exam_result(self):
        """
        从综合考试结果页面提取结果标识。
        
        :return: 匹配到的结果标识字符串；未匹配到时返回整数 0。
        """
        url = 'https://dxpx.uestc.edu.cn/fzdx/exam_center/result'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url=url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        pattern = r'rid=(\d+)'
        match = re.search(pattern, response.text)
        if match:
            rid = match.group(1)
        else:
            rid = 0
        return rid
