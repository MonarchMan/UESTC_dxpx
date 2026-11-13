import html
import json
import os
import re
import tempfile
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
from pypinyin import lazy_pinyin

from dxpx.common.login import AuthSession


class BaseAutoPlayer:
    question_dir = './temp'
    lesson_dir = './temp'

    def __init__(self, headers: dict, stage: int = 43):
        """
        初始化实例状态。
        
        :param headers: 请求头字典；认证请求通常需包含 Cookie，提交学习或答题记录时还需 _xsrf。
        :param stage: 培训阶段标识。默认值为 43。
        """
        self.ts_list = []
        self.headers = headers
        self.session = AuthSession(headers)
        self.stage = stage
        self.radio_df = pd.DataFrame()
        self.checkbox_df = pd.DataFrame()
        self.yes_or_no_df = pd.DataFrame()
        self.gap_filling_df = pd.DataFrame()

    def get_lessons(self):
        """
        获取当前培训阶段的课程标识列表。
        
        :return: list[str]；从页面提取的课程标识。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def get_required_lessons(self, lesson_id: int, page: int = 1):
        """
        获取指定课程、页码的必修视频及分页信息。
        
        :param lesson_id: 课程或章节标识。
        :param page: 课程列表或播放页的页码，从 1 开始。默认值为 1。
        :return: 由子类定义的视频标识集合及分页信息。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def get_lesson_r_id(self, video_id: int, resource_id: int, page: int = 1):
        """
        从视频播放页面提取观看记录标识。
        
        :param video_id: 视频标识。
        :param resource_id: 视频资源标识；部分播放链接允许为 None。
        :param page: 课程列表或播放页的页码，从 1 开始。默认值为 1。
        :return: 由子类定义的观看记录标识或标识组合。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def check_record(self, lesson_id: int, video_id: int, resource_id: int, r_id: int):
        """
        向平台提交指定视频的观看记录。
        
        :param lesson_id: 课程或章节标识。
        :param video_id: 视频标识。
        :param resource_id: 视频资源标识；部分播放链接允许为 None。
        :param r_id: 视频观看记录标识。
        :return: bool；平台确认接受记录时为 True，否则为 False。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def get_course_ware_extra_ids(self, v_id: int):
        """
        从微课件或专家讲座播放页面提取观看记录和资源标识。
        
        :param v_id: 用于加载播放页的视频标识。
        :return: 二元组 (r_id, resource_id)，分别为观看记录标识和资源标识。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def get_exam_paper(self, r_id: int):
        """
        获取已完成综合考试的题目及正确答案。
        
        :param r_id: 已完成综合考试的结果标识。
        :return: 四元组 (radios, checkboxes, yes_or_nos, gap_fillings)，每项为题目字典列表。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def get_lesson_exam_paper(self, rid: int):
        """
        获取已完成章节测试的题目及正确答案。
        
        :param rid: 章节测试结果标识。
        :return: 四元组 (radios, checkboxes, yes_or_nos, gap_fillings)，每项为题目字典列表。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def get_exam_list(self):
        """
        获取已完成综合考试的结果标识列表。
        
        :return: list[int]；综合考试结果标识列表。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def get_lesson_exam_list(self):
        """
        获取已完成章节测试的结果标识列表。
        
        :return: list[int]；章节测试结果标识列表。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def update_from_exam_results(self):
        """
        从已完成考试的结果中收集新题，更新并保存本地题库。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    @staticmethod
    def load_lessons(file_path='./temp/lessons.json'):
        """
        从 JSON 文件加载本地课程记录。
        
        :param file_path: 本地课程 JSON 文件路径。默认值为 './temp/lessons.json'。
        :return: JSON 解析结果；通常为包含 lesson_id 和 id_params 的课程字典列表。
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def extract_required_lessons_info(text: str):
        """
        从课程列表页面提取资源标识，保留同一视频的不同资源。

        :param text: 待解析的课程列表页面 HTML 文本。
        :return: 三元组 (id_pairs, rest_ids, total_pages)；资源对与微课件标识按出现顺序去重，总页数至少为 1。
        """
        pattern = r'<a\s+class="(?:dd_cut_on)?"[^>]*href="[^"]*v_id=(\d+)&r_id=(\d+)[^"]*"[^>]*>'
        id_pairs = re.findall(pattern, text)

        rest_pattern = r'<a\s+href="(?![^"]*[?&]r_id=)[^"]*v_id=(\d+)[^"]*"(?:\s+target="_blank")?>'
        rest_ids = re.findall(rest_pattern, text)

        # 按资源对去重：同一视频可能对应多个资源，只按 v_id 去重会丢掉后续资源
        seen_pairs = set()
        unique_id_pairs = []
        for v_id, r_id in id_pairs:
            key = (v_id, r_id)
            if key not in seen_pairs:
                unique_id_pairs.append((v_id, r_id))
                seen_pairs.add(key)

        # 对 rest_ids 去重
        unique_rest_ids = list(dict.fromkeys(rest_ids))

        total_pages = 1
        # “末页/尾页”链接最可靠，同时兼容单双引号
        pages_pattern = r"<a\s[^>]*href=['\"][^'\"]*[?&]page=(\d+)[^'\"]*['\"][^>]*>\s*(?:末页|尾页)"
        pages_matches = re.findall(pages_pattern, text)
        if pages_matches:
            total_pages = max(int(page) for page in pages_matches)
        else:
            # 没有“末页”时退化为页面中出现过的最大页码
            all_page_nums = re.findall(r'[?&]page=(\d+)', text)
            if all_page_nums:
                total_pages = max(int(page) for page in all_page_nums)
        return unique_id_pairs, unique_rest_ids, max(total_pages, 1)

    def get_lessons_and_save(self, output_dir: Optional[str] = None, save=False) -> Tuple[List, List]:
        """
        遍历课程分页，提交视频记录并按需保存课程信息。
        
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 None。
        :param save: 是否将结果保存到本地文件。默认值为 False。
        :return: 二元组 (failed_list, lessons)，分别为提交失败的记录列表和收集到的课程列表。
        :raises NotImplementedError: 基类仅定义接口，需由子类覆写后调用。
        """
        raise NotImplementedError("未实现")

    def finish_lessons_from_local(self, lesson_path: Optional[str] = None) -> list:
        """
        读取本地课程信息，依次提交其中的视频观看记录。
        
        :param lesson_path: 本地课程 JSON 文件路径；为 None 时使用课程目录下的 lessons.json。默认值为 None。
        :return: list[dict]；提交失败的课程、视频和资源标识。
        """
        lesson_path = lesson_path or os.path.join(self.lesson_dir, 'lessons.json')
        lessons = self.load_lessons(lesson_path)
        failed_lessons = []
        seen = set()
        for lesson in lessons:
            lesson_id = lesson['lesson_id']
            for id_param in lesson['id_params']:
                video_id, resource_id = id_param['video_id'], id_param['resource_id']
                key = (lesson_id, video_id, resource_id)
                if key in seen:
                    continue
                seen.add(key)
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
        """
        汇总考试及章节测试题目，按题干去重、排序并按需保存。
        
        :param r_ids: 已完成综合考试的结果标识列表。
        :param lesson_r_ids: 已完成章节测试的结果标识列表；为 None 时不收集章节测试题目。默认值为 None。
        :param save: 是否将结果保存到本地文件。默认值为 False。
        :return: 依次包含单选、多选、判断、填空题的四个 DataFrame。
        """
        lesson_r_ids = lesson_r_ids or []
        questions_by_type = {
            'radios': {},
            'checkboxes': {},
            'yes_or_nos': {},
            'gap_fillings': {},
        }

        # 综合考试和章节测试使用不同结果接口，按拼接位置选择调用方式。
        all_r_ids = list(r_ids) + list(lesson_r_ids)
        for i, r_id in enumerate(all_r_ids):
            if i < len(r_ids):
                radios, checkboxes, yes_or_nos, gap_fillings = self.get_exam_paper(r_id)
            else:
                radios, checkboxes, yes_or_nos, gap_fillings = self.get_lesson_exam_paper(r_id)

            # 以题干作为去重键，保留首次收集到的题目及答案。
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
        """
        加载本地存在的 Parquet 题库文件到实例属性。
        
        :param input_dir: 题库目录；为 None 时使用实例的 question_dir。默认值为 None。
        """
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
        """
        按题型和完整题干查找本地题库中的答案。
        
        :param question: 待匹配的完整题干文本。
        :param question_type: 题型，可取 radio、checkbox、yes_or_no 或 gap_filling。
        :return: 匹配题目的 correct_answer 字段值；题库为空或未找到时返回空字符串。
        :raises ValueError: 传入了不支持的题型。
        """
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

        # 缺少题库文件时保留无列空表，按未命中处理，避免访问 title 时报错。
        if df.empty:
            return ''

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
        """
        合并新旧题库，按题干去重、拼音排序并重排索引后保存。
        
        :param new_radios_df: 待合并的新单选题 DataFrame。
        :param new_checkboxes_df: 待合并的新多选题 DataFrame。
        :param new_yes_or_nos_df: 待合并的新判断题 DataFrame。
        :param new_gap_fillings_df: 待合并的新填空题 DataFrame。
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 None。
        """
        output_dir = output_dir or self.question_dir
        if self.radio_df.empty or self.checkbox_df.empty or self.yes_or_no_df.empty or self.gap_filling_df.empty:
            self.load_questions(output_dir)

        def merge_and_deduplicate(existing_df, new_df):
            """
            合并两份题库，按题干保留首条记录并重排索引。
            
            :param existing_df: 已有题库 DataFrame。
            :param new_df: 待合并的新题 DataFrame。
            :return: DataFrame；合并、去重和排序后的题库，新表为空时仅重排原表索引。
            """
            if new_df.empty:
                return existing_df.reset_index(drop=True)

            # 原题在前，重复题保留已有答案；排序后重排索引用于文本编号。
            combined_df = pd.concat([existing_df, new_df], axis=0, ignore_index=True)
            deduplicated_df = combined_df.drop_duplicates(subset=['title'], keep='first')
            return deduplicated_df.sort_values(
                by='title',
                key=lambda x: x.apply(lambda y: ''.join(lazy_pinyin(str(y)))),
            ).reset_index(drop=True)

        self.radio_df = merge_and_deduplicate(self.radio_df, new_radios_df)
        self.checkbox_df = merge_and_deduplicate(self.checkbox_df, new_checkboxes_df)
        self.yes_or_no_df = merge_and_deduplicate(self.yes_or_no_df, new_yes_or_nos_df)
        self.gap_filling_df = merge_and_deduplicate(self.gap_filling_df, new_gap_fillings_df)

        self.save_result_parquet(self.radio_df, self.checkbox_df, self.yes_or_no_df, self.gap_filling_df, output_dir)
        self.save_result(self.radio_df, self.checkbox_df, self.yes_or_no_df, self.gap_filling_df, output_dir)

    @staticmethod
    def extract_questions(page_html: str, pattern: str) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
        """
        从结果页面中解析题干、选项和正确答案，并按题型分类。
        
        :param page_html: 待解析的考试结果页面 HTML 文本。
        :param pattern: 用于匹配单个题目内容块的正则表达式。
        :return: 四元组 (radios, checkboxes, yes_or_nos, gap_fillings)，每项为题目字典列表。
        """
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

            # 题型由题干前缀确定，入库前移除该前缀。
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
        """
        将四类题库分别保存为便于阅读的文本文件。
        
        :param radios_df: 单选题 DataFrame。
        :param checkboxes_df: 多选题 DataFrame。
        :param yes_or_nos_df: 判断题 DataFrame。
        :param gap_fillings_df: 填空题 DataFrame。
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 './temp'。
        """
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
                    # 数组不能直接转为单个布尔值，需单独判断是否含选项。
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
        """
        使用 pyarrow 将四类题库保存为不含索引的 Parquet 文件。
        
        :param radios_df: 单选题 DataFrame。
        :param checkboxes_df: 多选题 DataFrame。
        :param yes_or_nos_df: 判断题 DataFrame。
        :param gap_fillings_df: 填空题 DataFrame。
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 './temp'。
        """
        os.makedirs(output_dir, exist_ok=True)
        radios_df.to_parquet(os.path.join(output_dir, 'radios.parquet'), index=False, engine='pyarrow')
        checkboxes_df.to_parquet(os.path.join(output_dir, 'checkboxes.parquet'), index=False, engine='pyarrow')
        yes_or_nos_df.to_parquet(os.path.join(output_dir, 'yes_or_nos.parquet'), index=False, engine='pyarrow')
        gap_fillings_df.to_parquet(os.path.join(output_dir, 'gap_fillings.parquet'), index=False, engine='pyarrow')

    @staticmethod
    def sort_by_pinyin(items):
        """
        按题干的拼音顺序排列题目，缺少题干时使用空排序键。
        
        :param items: 待排序的题目字典序列，题干位于 title 字段。
        :return: list；排序后的新题目列表，不修改传入列表。
        """
        return sorted(items, key=lambda x: ''.join(lazy_pinyin(x['title'])) if 'title' in x else '')

