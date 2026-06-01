import re
from typing import Optional

import pandas as pd


class BaseExam:
    player_cls = None

    def __init__(self, cookies: dict):
        self.ts_list = []
        self.cookies = cookies
        self.headers = {}

    def create_player(self):
        if self.player_cls is None:
            raise NotImplementedError("未实现")
        player = self.player_cls(self.cookies)
        player.load_questions()
        return player

    def start_exam(self):
        raise NotImplementedError("未实现")

    def get_question(self, question_id: int):
        raise NotImplementedError("未实现")

    def answer_question(self, question_id: int, qid: int, answer: str):
        raise NotImplementedError("未实现")

    def submit_exam(self):
        raise NotImplementedError("未实现")

    def get_exam_result(self):
        raise NotImplementedError("未实现")

    def finish_exam(self, return_new: bool = False, player: Optional[object] = None):
        if player is None:
            player = self.create_player()
        self.start_exam()
        print("开始考试")

        new_radios = []
        new_checkboxes = []
        new_yes_or_nos = []
        new_gap_fillings = []

        for i in range(1, 31):
            title, options, qid = self.get_question(i)
            answer = player.search_answer(title, 'radio')
            if answer:
                index = ord(answer[0]) - ord('A')
                self.answer_question(i, qid, options[index][1])
            else:
                self.answer_question(i, qid, options[0][1])
                new_radios.append(i - 1)

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

        for i in range(61, 81):
            title, options, qid = self.get_question(i)
            answer = player.search_answer(title, 'yes_or_no')
            if answer:
                index = ord(answer[0]) - ord('A')
                self.answer_question(i, qid, options[index][1])
            else:
                self.answer_question(i, qid, options[0][1])
                new_yes_or_nos.append(i - 61)

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

    def finish_many_exams(self, echos: int = 30):
        player = self.create_player()
        new_radios = pd.DataFrame()
        new_checkboxes = pd.DataFrame()
        new_yes_or_nos = pd.DataFrame()
        new_gap_fillings = pd.DataFrame()
        for i in range(echos):
            print(f"\n==========>第 {i + 1} 次考试<============")
            radios, checkboxes, yes_or_nos, gap_fillings = self.finish_exam(return_new=True, player=player)
            new_radios = pd.concat([new_radios, radios])
            new_checkboxes = pd.concat([new_checkboxes, checkboxes])
            new_yes_or_nos = pd.concat([new_yes_or_nos, yes_or_nos])
            new_gap_fillings = pd.concat([new_gap_fillings, gap_fillings])
        if any(len(df) > 0 for df in [new_radios, new_checkboxes, new_yes_or_nos, new_gap_fillings]):
            player.update_questions(new_radios, new_checkboxes, new_yes_or_nos, new_gap_fillings)

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
            title = re.sub(r'^\d+.\s*', '', title_match.group(1))
        else:
            title = 'No title found'

        options_pattern = r'<label[^>]*>(.*?)</label>'
        labels = re.findall(options_pattern, html, re.DOTALL)
        options = []
        for label_content in labels:
            answer_id_match = re.search(r'value="(\d+)"', label_content)
            if answer_id_match:
                answer_id = answer_id_match.group(1)
            else:
                answer_id = ''
            option_text = re.sub(r'<input[^>]*/?>', '', label_content)
            option_text = re.sub(r'\s+', ' ', option_text.strip())
            if option_text:
                options.append((option_text, answer_id))

        return title, options, qid
