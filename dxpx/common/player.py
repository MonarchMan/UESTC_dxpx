import html
import json
import os
import re
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
from pypinyin import lazy_pinyin


class BaseAutoPlayer:
    question_dir = './temp'
    lesson_dir = './temp'

    def __init__(self, cookies: dict):
        self.ts_list = []
        self.cookies = cookies
        self.headers = {}
        self.radio_df = pd.DataFrame()
        self.checkbox_df = pd.DataFrame()
        self.yes_or_no_df = pd.DataFrame()
        self.gap_filling_df = pd.DataFrame()

    def get_lessons(self):
        raise NotImplementedError("未实现")

    def get_required_lessons(self, lesson_id: int, page: int = 1):
        raise NotImplementedError("未实现")

    def get_lesson_r_id(self, video_id: int, resource_id: int, page: int = 1):
        raise NotImplementedError("未实现")

    def check_record(self, lesson_id: int, video_id: int, resource_id: int, r_id: int):
        raise NotImplementedError("未实现")

    def get_course_ware_extra_ids(self, v_id: int):
        raise NotImplementedError("未实现")

    def get_exam_paper(self, r_id: int):
        raise NotImplementedError("未实现")

    def get_lesson_exam_paper(self, rid: int):
        raise NotImplementedError("未实现")

    def get_exam_list(self):
        raise NotImplementedError("未实现")

    def get_lesson_exam_list(self):
        raise NotImplementedError("未实现")

    def update_from_exam_results(self):
        raise NotImplementedError("未实现")

    @staticmethod
    def load_lessons(file_path='./temp/lessons.json'):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def extract_required_lessons_info(text: str):
        pattern = r'<a\s+class="(?:dd_cut_on)?"[^>]*href="[^"]*v_id=(\d+)&r_id=(\d+)[^"]*"[^>]*>'
        id_pairs = re.findall(pattern, text)

        rest_pattern = r'<a\s+href="[^"]*v_id=(\d+)[^"]*"(?:\s+target="_blank")?>'
        rest_ids = re.findall(rest_pattern, text)

        total_pages = 1
        pages_pattern = r"<a\s+href='[^']*page=(\d+)[^']*'[^>]*>末页"
        pages_match = re.search(pages_pattern, text)
        if pages_match:
            total_pages = int(pages_match.group(1))
        return id_pairs, rest_ids, total_pages

    def get_lessons_and_save(self, output_dir: Optional[str] = None, save=False) -> Tuple[List, List]:
        """
        获取课程列表并保存到 lessons.json。
        两步法：
            1) 从 /jjfz/lesson/video 拿 v_id 种子（可能不完整）
            2) 对每个 v_id 种子走 /jjfz/play 拿**完整**的 (v_id, r_id) 对
        :param output_dir: lessons.json 保存目录，默认 self.lesson_dir
        :param save: 是否写入磁盘
        :return: 收集失败的课程信息列表；已收集的 lessons 列表（每个元素 {'lesson_id': ..., 'id_params': [...]}）
        """
        output_dir = output_dir or self.lesson_dir
        lesson_ids = self.get_lessons()
        lessons = []
        failed_list = []
        for lesson_id in lesson_ids:
            page_num = 1
            while True:
                id_pairs, courseware_ids, total_pages = self.get_required_lessons(lesson_id=lesson_id, page=page_num)
                page_num += 1
                id_params = []
                for id_pair in id_pairs:
                    video_id = int(id_pair[0])
                    resource_id = int(id_pair[1])
                    r_id = self.get_lesson_r_id(video_id=video_id, resource_id=resource_id, page=page_num)
                    success = self.check_record(
                        lesson_id=lesson_id,
                        video_id=video_id,
                        resource_id=resource_id,
                        r_id=r_id,
                    )
                    if not success:
                        failed_list.append({
                            'lesson_id': lesson_id,
                            'video_id': video_id,
                            'resource_id': resource_id,
                        })
                    id_params.append((video_id, resource_id, r_id))
                print(f"课程{lesson_id}的相关参数已获取")

                for video_id in courseware_ids:
                    r_id, resource_id = self.get_course_ware_extra_ids(v_id=int(video_id))
                    r_id = int(r_id)
                    resource_id = int(resource_id)
                    success = self.check_record(
                        lesson_id=lesson_id,
                        video_id=int(video_id),
                        resource_id=resource_id,
                        r_id=r_id,
                    )
                    if not success:
                        failed_list.append({
                            'lesson_id': lesson_id,
                            'video_id': int(video_id),
                            'resource_id': resource_id,
                        })
                    id_params.append((int(video_id), resource_id, r_id))

                lessons.append({
                    'lesson_id': lesson_id,
                    'id_params': [
                        {'video_id': video_id, 'resource_id': resource_id}
                        for video_id, resource_id, _ in id_params
                    ],
                })
                if page_num > total_pages:
                    break
        if save:
            os.makedirs(output_dir, exist_ok=True)
            with open(os.path.join(output_dir, 'lessons.json'), 'w', encoding='utf-8') as f:
                json.dump(lessons, f, ensure_ascii=False, indent=4)
            print(f"lessons数据已保存到{output_dir}/lessons.json文件")
        return failed_list, lessons

    def finish_lessons(self, lesson_path: Optional[str] = None) -> list:
        lesson_path = lesson_path or os.path.join(self.lesson_dir, 'lessons.json')
        lessons = self.load_lessons(lesson_path)
        failed_lessons = []
        for lesson in lessons:
            lesson_id = lesson['lesson_id']
            for id_param in lesson['id_params']:
                video_id, resource_id = id_param['video_id'], id_param['resource_id']
                r_id = self.get_lesson_r_id(video_id=video_id, resource_id=resource_id)
                success = self.check_record(
                    lesson_id=lesson_id,
                    video_id=video_id,
                    resource_id=resource_id,
                    r_id=r_id,
                )
                if not success:
                    failed_lessons.append({
                        'lesson_id': lesson_id,
                        'video_id': video_id,
                        'resource_id': resource_id,
                    })
        return failed_lessons

    def collect_unique_questions(self, r_ids: list, lesson_r_ids: Optional[list] = None, save: bool = False):
        lesson_r_ids = lesson_r_ids or []
        questions_by_type = {
            'radios': {},
            'checkboxes': {},
            'yes_or_nos': {},
            'gap_fillings': {},
        }

        all_r_ids = list(r_ids) + list(lesson_r_ids)
        for i, r_id in enumerate(all_r_ids):
            if i < len(r_ids):
                radios, checkboxes, yes_or_nos, gap_fillings = self.get_exam_paper(r_id)
            else:
                radios, checkboxes, yes_or_nos, gap_fillings = self.get_lesson_exam_paper(r_id)

            for radio in radios:
                questions_by_type['radios'].setdefault(radio['title'], radio)
            for checkbox in checkboxes:
                questions_by_type['checkboxes'].setdefault(checkbox['title'], checkbox)
            for yes_or_no in yes_or_nos:
                questions_by_type['yes_or_nos'].setdefault(yes_or_no['title'], yes_or_no)
            for gap_filling in gap_fillings:
                questions_by_type['gap_fillings'].setdefault(gap_filling['title'], gap_filling)

        radio_df = pd.DataFrame(self.sort_by_pinyin(list(questions_by_type['radios'].values())))
        checkbox_df = pd.DataFrame(self.sort_by_pinyin(list(questions_by_type['checkboxes'].values())))
        yes_or_no_df = pd.DataFrame(self.sort_by_pinyin(list(questions_by_type['yes_or_nos'].values())))
        gap_filling_df = pd.DataFrame(self.sort_by_pinyin(list(questions_by_type['gap_fillings'].values())))

        if save:
            self.save_result_parquet(radio_df, checkbox_df, yes_or_no_df, gap_filling_df, self.question_dir)
            self.save_result(radio_df, checkbox_df, yes_or_no_df, gap_filling_df, self.question_dir)

        return radio_df, checkbox_df, yes_or_no_df, gap_filling_df

    def load_questions(self, input_dir: Optional[str] = None):
        input_dir = input_dir or self.question_dir

        question_files = {
            'radio_df': 'radios.parquet',
            'checkbox_df': 'checkboxes.parquet',
            'yes_or_no_df': 'yes_or_nos.parquet',
            'gap_filling_df': 'gap_fillings.parquet',
        }
        for attr, filename in question_files.items():
            file_path = os.path.join(input_dir, filename)
            if os.path.exists(file_path):
                setattr(self, attr, pd.read_parquet(file_path))

    def search_answer(self, question: str, question_type: str):
        if question_type == 'radio':
            df = self.radio_df
        elif question_type == 'checkbox':
            df = self.checkbox_df
        elif question_type == 'yes_or_no':
            df = self.yes_or_no_df
        elif question_type == 'gap_filling':
            df = self.gap_filling_df
        else:
            raise ValueError(f"Invalid question type: {question_type}")

        row = df[df['title'] == question]
        if not row.empty:
            return row.iloc[0]['correct_answer']
        return ''

    def update_questions(
            self,
            new_radios_df: pd.DataFrame,
            new_checkboxes_df: pd.DataFrame,
            new_yes_or_nos_df: pd.DataFrame,
            new_gap_fillings_df: pd.DataFrame,
            output_dir: Optional[str] = None):
        output_dir = output_dir or self.question_dir
        if self.radio_df.empty or self.checkbox_df.empty or self.yes_or_no_df.empty or self.gap_filling_df.empty:
            self.load_questions(output_dir)

        def merge_and_deduplicate(existing_df, new_df):
            if new_df.empty:
                return existing_df

            combined_df = pd.concat([existing_df, new_df], axis=0, ignore_index=True)
            deduplicated_df = combined_df.drop_duplicates(subset=['title'], keep='first')
            return deduplicated_df.sort_values(
                by='title',
                key=lambda x: x.apply(lambda y: ''.join(lazy_pinyin(str(y)))),
            )

        self.radio_df = merge_and_deduplicate(self.radio_df, new_radios_df)
        self.checkbox_df = merge_and_deduplicate(self.checkbox_df, new_checkboxes_df)
        self.yes_or_no_df = merge_and_deduplicate(self.yes_or_no_df, new_yes_or_nos_df)
        self.gap_filling_df = merge_and_deduplicate(self.gap_filling_df, new_gap_fillings_df)

        self.save_result_parquet(self.radio_df, self.checkbox_df, self.yes_or_no_df, self.gap_filling_df, output_dir)
        self.save_result(self.radio_df, self.checkbox_df, self.yes_or_no_df, self.gap_filling_df, output_dir)

    @staticmethod
    def extract_questions(page_html: str, pattern: str):
        error_subs = re.findall(pattern, page_html, re.DOTALL)
        radios = []
        checkboxes = []
        yes_or_nos = []
        gap_fillings = []

        for error_sub_content in error_subs:
            item = {}

            title_pattern = r'<h3>(.*?)</h3>'
            title_match = re.search(title_pattern, error_sub_content, re.DOTALL)
            if title_match:
                cleaned_title = re.sub(r'^\d+、\s*', '', title_match.group(1))
                item['title'] = re.sub(r'\s+', ' ', cleaned_title.strip())
            else:
                item['title'] = ''

            label_pattern = r'<label[^>]*>(.*?)</label>'
            labels = re.findall(label_pattern, error_sub_content, re.DOTALL)

            options = []
            for label_content in labels:
                option_text = re.sub(r'<input[^>]*/?>', '', label_content)
                option_text = re.sub(r'\s+', ' ', option_text.strip())
                if option_text:
                    options.append(option_text)

            item['options'] = np.array(options)

            answer_pattern = r'<span class="sub_color">(.*?)</span>'
            answer_match = re.search(answer_pattern, error_sub_content)
            if answer_match:
                item['correct_answer'] = answer_match.group(1).strip()[5:]
            else:
                continue

            prefix = item['title'][:5]
            item['title'] = item['title'][5:].strip()
            if prefix == '【单选题】':
                radios.append(item)
            elif prefix == '【多选题】':
                checkboxes.append(item)
            elif prefix == '【判断题】':
                yes_or_nos.append(item)
            elif prefix == '【填空题】':
                answer_text_pattern = r'<div class="sub_cont">(.*?)</div>'
                answer_text_match = re.search(answer_text_pattern, error_sub_content)
                if answer_text_match:
                    item['correct_answer'] = answer_text_match.group(1).strip()
                gap_fillings.append(item)

        return radios, checkboxes, yes_or_nos, gap_fillings

    @staticmethod
    def save_result(
            radios_df: pd.DataFrame,
            checkboxes_df: pd.DataFrame,
            yes_or_nos_df: pd.DataFrame,
            gap_fillings_df: pd.DataFrame,
            output_dir: str = './temp'):
        os.makedirs(output_dir, exist_ok=True)

        question_types = [
            ('单选', radios_df, 'radios.txt'),
            ('多选', checkboxes_df, 'checkboxes.txt'),
            ('判断', yes_or_nos_df, 'yes_or_nos.txt'),
            ('填空', gap_fillings_df, 'gap_fillings.txt'),
        ]

        for type_name, questions_df, filename in question_types:
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"{type_name}题 (共{len(questions_df)}道)\n\n")

                for i, question_row in questions_df.iterrows():
                    f.write(f"{i}. ")
                    title = html.unescape(question_row.get('title', '无标题'))
                    f.write(f"{title}\n")

                    options = question_row.get('options')
                    if isinstance(options, np.ndarray):
                        has_options = options.size > 0
                    else:
                        has_options = bool(options)

                    if has_options:
                        if isinstance(options, dict):
                            options_str = '; '.join([f"{key}: {value}" for key, value in options.items()])
                        elif isinstance(options, (list, tuple, np.ndarray)):
                            options_str = '; '.join(options)
                        else:
                            options_str = str(options)
                        f.write(f"{options_str}\n")

                    answer = question_row.get('correct_answer', 'Error!')
                    f.write(f"正确答案: {answer}\n")
                    f.write("-" * 50 + "\n\n")

            print(f"已将{len(questions_df)}道{type_name}题保存到: {filepath}")

    @staticmethod
    def save_result_parquet(
            radios_df: pd.DataFrame,
            checkboxes_df: pd.DataFrame,
            yes_or_nos_df: pd.DataFrame,
            gap_fillings_df: pd.DataFrame,
            output_dir: str = './temp'):
        os.makedirs(output_dir, exist_ok=True)
        radios_df.to_parquet(os.path.join(output_dir, 'radios.parquet'), index=False)
        checkboxes_df.to_parquet(os.path.join(output_dir, 'checkboxes.parquet'), index=False)
        yes_or_nos_df.to_parquet(os.path.join(output_dir, 'yes_or_nos.parquet'), index=False)
        gap_fillings_df.to_parquet(os.path.join(output_dir, 'gap_fillings.parquet'), index=False)

    @staticmethod
    def sort_by_pinyin(items):
        return sorted(items, key=lambda x: ''.join(lazy_pinyin(x['title'])) if 'title' in x else '')
