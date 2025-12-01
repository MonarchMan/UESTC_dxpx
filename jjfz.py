import json

import numpy as np
import requests
import os
import re
import html
import pandas as pd
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from pypinyin import lazy_pinyin

pages = 2


def load_lessons(file_path='./temp/lessons.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        lessons = json.load(f)
    return lessons


class JJFZAutoPlayer:
    def __init__(self, cookies: dict):
        self.ts_list = []
        self.cookies = cookies

        self.headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://dxpx.uestc.edu.cn',
            'Referer': 'https://dxpx.uestc.edu.cn/jjfz/play?v_id=12722&r_id=52564&r=video&t=2&pg=1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
        self.radio_df = pd.DataFrame()
        self.checkbox_df = pd.DataFrame()
        self.yes_or_no_df = pd.DataFrame()
        self.gap_filling_df = pd.DataFrame()

    def parse_m3u8(self, url: str):
        """
        解析M3U8文件
        :param url: m3u8文件url
        :return:
        """
        response = requests.get(url, headers=self.headers, cookies=self.cookies)
        response.encoding = 'utf-8'
        content = response.text

        lines = content.strip().split('\n')

        info = {
            'version': None,
            'target_duration': None,
            'media_sequence': None,
            'allow_cache': None,
            'total_duration': 0,
            'segments': []
        }

        current_duration = None

        base_url = url.rsplit('/', 1)[0] + '/'
        for line in lines:
            line = line.strip()

            if line.startswith('#EXT-X-VERSION:'):
                info['version'] = int(line.split(':')[1])

            elif line.startswith('#EXT-X-TARGETDURATION:'):
                info['target_duration'] = int(line.split(':')[1])

            elif line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
                info['media_sequence'] = int(line.split(':')[1])

            elif line.startswith('#EXT-X-ALLOW-CACHE:'):
                info['allow_cache'] = line.split(':')[1]

            elif line.startswith('#EXTINF:'):
                # 提取时长：#EXTINF:5.000000,
                duration_str = line.split(':')[1].split(',')[0]
                current_duration = float(duration_str)

            elif line and not line.startswith('#'):
                # 这是一个TS片段文件名
                if current_duration is not None:
                    segment_url = urljoin(base_url, line)
                    info['segments'].append({
                        'url': segment_url,
                        'filename': line,
                        'duration': current_duration
                    })
                    info['total_duration'] += current_duration
                    current_duration = None

        self.ts_list = info['segments']
        return info

    def download_ts(self, index):
        """下载单个TS片段"""
        segment = self.ts_list[index]
        total = len(self.ts_list)
        try:
            response = requests.get(self.ts_list[index]['url'], headers=self.headers, cookies=self.cookies, timeout=30)

            if response.status_code == 200:
                print(f"[{index + 1}/{total}] 下载成功: {segment['filename']} "
                      f"({segment['duration']:.2f}秒)")
                return segment['filename'], response.content
            else:
                print(f"[{index + 1}/{total}] 下载失败: {segment['filename']} "
                      f"状态码: {response.status_code}")
                return segment['filename'], None

        except Exception as e:
            print(f"[{index + 1}/{total}] 下载出错: {segment['filename']} "
                  f"错误: {str(e)}")
            return segment['filename'], None

    def download_all(self, output_dir='./temp', max_workers=5):
        """下载所有TS片段"""
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n开始下载 {len(self.ts_list)} 个视频片段...")
        print(f"使用 {max_workers} 个线程并发下载\n")

        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.download_ts, i): i
                for i in range(len(self.ts_list))
            }

            for future in as_completed(futures):
                filename, content = future.result()
                if content:
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    results[filename] = True
                else:
                    results[filename] = False

        success_count = sum(1 for v in results.values() if v)
        print(f"\n下载完成！成功: {success_count}/{len(self.ts_list)}")

        return results

    def merge_ts(self, output_dir='ts_segments', output_file='merged_video.mp4'):
        """合并TS片段为完整视频"""
        print(f"\n开始合并视频片段...")

        # 方法1：直接合并TS文件（简单但可能有问题）
        merged_ts = output_file.replace('.mp4', '.ts')

        with open(merged_ts, 'wb') as outfile:
            for i, segment in enumerate(self.ts_list):
                filepath = os.path.join(output_dir, segment['filename'])
                if os.path.exists(filepath):
                    with open(filepath, 'rb') as infile:
                        outfile.write(infile.read())
                    print(f"合并进度: {i + 1}/{len(self.ts_list)}")

        print(f"\n合并完成！输出文件: {merged_ts}")
        print(f"\n提示：如需转换为MP4格式，请使用FFmpeg:")
        print(f"ffmpeg -i {merged_ts} -c copy {output_file}")

        return merged_ts

    def seek_to_time(self, target_seconds):
        """
        跳转到指定时间（模拟拖动进度条）

        Args:
            target_seconds: 目标时间（秒）

        Returns:
            需要下载的片段索引和该片段内的偏移时间
        """
        current_time = 0

        for i, segment in enumerate(self.ts_list):
            if current_time + segment['duration'] >= target_seconds:
                offset = target_seconds - current_time
                return {
                    'segment_index': i,
                    'segment': segment,
                    'offset_in_segment': offset,
                    'total_time': current_time
                }
            current_time += segment['duration']

        # 如果超出范围，返回最后一个片段
        return {
            'segment_index': len(self.ts_list) - 1,
            'segment': self.ts_list[-1],
            'offset_in_segment': 0,
            'total_time': current_time
        }

    def check_record(self, lesson_id: int, video_id: int, resource_id: int, r_id: int):
        data = {
            'rid': r_id,
            'lesson_id': lesson_id,
            'resource_id': resource_id,
            'video_id': video_id,
            '_xsrf': self.cookies['_xsrf'],
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/resource_record'
        response = requests.post(url=url, cookies=self.cookies, headers=self.headers, data=data)
        if response.status_code == 200:
            if response.json()['code'] == 1:
                return True
        return False

    def get_required_lessons(self, lesson_id: int, page: int = 1):
        """
        获取课程的必修课程列表
        :param lesson_id: 课程ID
        :param page: 页码
        :return: 必修课程列表，每个元素为(video_id, resource_id)元组
        """
        params = {
            'lesson_id': lesson_id,
            'required': 1,
            'page': page,
        }

        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/video'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'<a\s+class="(?:dd_cut_on)?"[^>]*href="[^"]*v_id=(\d+)&r_id=(\d+)[^"]*"[^>]*>'
        id_pairs = re.findall(pattern, response.text)

        # 微课件或者专家讲座 中没有提供r_id的
        rest_pattern = r'<a\s+href="[^"]*v_id=(\d+)[^"]*"(?:\s+target="_blank")?>'
        rest_ids = re.findall(rest_pattern, response.text)

        total_pages = 1
        pages_pattern = r"<a\s+href='[^']*page=(\d+)[^']*'[^>]*>末页"
        pages_match = re.search(pages_pattern, response.text)
        if pages_match:
            total_pages = int(pages_match.group(1))
        return id_pairs, rest_ids, total_pages

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
        url = 'https://dxpx.uestc.edu.cn/jjfz/play'

        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'rid: "(\d+)"'
        rids = re.findall(pattern, response.text)
        return rids[0]

    def get_course_ware_extra_ids(self, v_id:int):
        """
        获取只有 v_id 的微课件或者专家讲座课程的资源ID对
        :param v_id: 视频ID
        :return: 资源ID对列表，每个元素为(r_id, resource_id)元组
        """
        params = {
            'v_id': v_id,
            'r': 'video',
            't': '2',
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/play'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'rid: "(\d+)",\s+resource_id: "(\d+)"'
        match = re.search(pattern, response.text)
        return match.group(1), match.group(2)

    def get_lessons(self):
        """
        获取所有课程ID
        :return: 课程ID列表
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        pattern = r'<a href="[^"]*lesson_id=(\d+)">'
        lesson_ids = re.findall(pattern, response.text)
        return lesson_ids

    def get_lessons_and_save(self, output_dir='./temp', save=False):
        """
        获取所有课程的必修课程列表，并保存到JSON文件
        :param output_dir: 输出目录，默认值为./temp
        :param save: 是否保存到JSON文件，默认值为False
        :return: 失败的课程列表，每个元素为{'lesson_id': lesson_id, 'video_id': video_id, 'resource_id': resource_id}字典
        """
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
                    # r_id 随会话变化而变化，故持久化没用
                    r_id = self.get_lesson_r_id(video_id=video_id, resource_id=resource_id, page=page_num)
                    success = self.check_record(lesson_id=lesson_id, video_id=video_id, resource_id=resource_id, r_id=r_id)
                    if not success:
                        failed_list.append({
                            'lesson_id': lesson_id,
                            'video_id': video_id,
                            'resource_id': resource_id,
                        })
                    id_params.append((video_id, resource_id, r_id))
                print(f"课程{lesson_id}的相关参数已获取")

                # 处理只有v_id的微课件或者专家讲座课程
                for video_id in courseware_ids:
                    id_pair = self.get_course_ware_extra_ids(v_id=video_id)
                    r_id = int(id_pair[0])
                    resource_id = int(id_pair[1])
                    success = self.check_record(lesson_id=lesson_id, video_id=video_id, resource_id=resource_id, r_id=r_id)
                    if not success:
                        failed_list.append({
                            'lesson_id': lesson_id,
                            'video_id': video_id,
                            'resource_id': resource_id,
                        })
                    id_params.append((video_id, resource_id, r_id))

                lessons.append({
                    'lesson_id': lesson_id,
                    'id_params': []
                })
                for video_id, resource_id, r_id in id_params:
                    lessons[-1]['id_params'].append({
                        'video_id': video_id,
                        'resource_id': resource_id,
                    })
                if page_num > total_pages:
                    break
        if save:
            # 保存lessons到JSON文件
            with open(f'{output_dir}/lessons.json', 'w', encoding='utf-8') as f:
                json.dump(lessons, f, ensure_ascii=False, indent=4)
            print(f"lessons数据已保存到{output_dir}/lessons.json文件")
        return failed_list

    def finish_lessons(self) -> list:
        lessons = load_lessons()
        failed_lessons = []
        for lesson in lessons:
            lesson_id = lesson['lesson_id']
            for id_param in lesson['id_params']:
                video_id, resource_id = id_param['video_id'], id_param['resource_id']
                r_id = self.get_lesson_r_id(video_id=video_id, resource_id=resource_id)
                success = self.check_record(lesson_id=lesson_id, video_id=video_id, resource_id=resource_id, r_id=r_id)
                if not success:
                    failed_lessons.append({
                        'lesson_id': lesson_id,
                        'video_id': video_id,
                        'resource_id': resource_id,
                    })
        return failed_lessons

    def get_exam_paper(self, r_id: int):
        params = {
            'rid': r_id,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_show'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        return self.extract_questions(response.text)

    def get_lesson_exam_paper(self, rid: int):
        params = {
            'rid': rid,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/show'

        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        return self.extract_questions(response.text)


    def collect_unique_questions(self, r_ids: list, lesson_r_ids: list=None, save: bool=False):
        # 使用字典存储不同类型的题目，天然去重
        if lesson_r_ids is None:
            lesson_r_ids = []
        questions_by_type = {
            'radios': {},
            'checkboxes': {},
            'yes_or_nos': {},
            'gap_fillings': {}
        }
        interval = len(r_ids)
        r_ids.extend(lesson_r_ids)

        for i, r_id in enumerate(r_ids):
            if i < interval:
                radios, checkboxes, yes_or_nos, gap_fillings = self.get_exam_paper(r_id)
            else:
                radios, checkboxes, yes_or_nos, gap_fillings = self.get_lesson_exam_paper(r_id)

            # 添加单选题
            for radio in radios:
                if radio['title'] not in questions_by_type['radios']:
                    questions_by_type['radios'][radio['title']] = radio

            # 添加多选题
            for checkbox in checkboxes:
                if checkbox['title'] not in questions_by_type['checkboxes']:
                    questions_by_type['checkboxes'][checkbox['title']] = checkbox

            # 添加判断题
            for yes_or_no in yes_or_nos:
                if yes_or_no['title'] not in questions_by_type['yes_or_nos']:
                    questions_by_type['yes_or_nos'][yes_or_no['title']] = yes_or_no

            # 添加填空题
            for gap_filling in gap_fillings:
                if gap_filling['title'] not in questions_by_type['gap_fillings']:
                    questions_by_type['gap_fillings'][gap_filling['title']] = gap_filling

        # 转换为列表并按拼音排序
        total_radios = self.sort_by_pinyin(list(questions_by_type['radios'].values()))
        total_checkboxes = self.sort_by_pinyin(list(questions_by_type['checkboxes'].values()))
        total_yes_or_nos = self.sort_by_pinyin(list(questions_by_type['yes_or_nos'].values()))
        total_gap_fillings = self.sort_by_pinyin(list(questions_by_type['gap_fillings'].values()))
        # 转换为DataFrame
        radio_df = pd.DataFrame(total_radios)
        checkbox_df = pd.DataFrame(total_checkboxes)
        yes_or_no_df = pd.DataFrame(total_yes_or_nos)
        gap_filling_df = pd.DataFrame(total_gap_fillings)

        # 保存结果到本地文件
        if save:
            # 保存为Parquet文件
            self.save_result_parquet(radio_df, checkbox_df, yes_or_no_df, gap_filling_df)
            # 保存为CSV文件
            self.save_result(radio_df, checkbox_df, yes_or_no_df, gap_filling_df)

        return radio_df, checkbox_df, yes_or_no_df, gap_filling_df

    def get_exam_list(self) -> list:
        """
        获取已完成的考试列表
        :return: 已完成的考试列表，每个元素为一个考试ID（rid）
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_record'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        pattern = r'rid=(\d+)'
        r_ids = re.findall(pattern, response.text)
        r_ids = [int(r_id) for r_id in r_ids]
        return r_ids

    def get_lesson_exam_list(self):
        """
        获取已完成的课程考试列表
        :return: 已完成的课程考试列表，每个元素为一个考试ID（rid）
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/record'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        pattern = r'rid=(\d+)'
        r_ids = re.findall(pattern, response.text)
        r_ids = [int(r_id) for r_id in r_ids]
        return r_ids

    def load_questions(self, input_dir: str='./temp'):
        """
        从指定目录加载题目数据
        :param input_dir: 输入文件路径，默认值为 './temp'
        :return:
        """
        self.radio_df = pd.read_parquet(os.path.join(input_dir, 'radios.parquet'))
        self.checkbox_df = pd.read_parquet(os.path.join(input_dir, 'checkboxes.parquet'))
        self.yes_or_no_df = pd.read_parquet(os.path.join(input_dir, 'yes_or_nos.parquet'))
        self.gap_filling_df = pd.read_parquet(os.path.join(input_dir, 'gap_fillings.parquet'))

    def search_answer(self, question: str, question_type: str):
        """
        搜索指定题目类型的答案
        :param question: 题目内容
        :param question_type: 题目类型，可选值为 'radio', 'checkbox', 'yes_or_no', 'gap_filling'
        :return: 题目对应的答案
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

        row = df[df['title'] == question]
        if not row.empty:
            return row.iloc[0]['correct_answer']
        else:
            return ''

    def update_questions(self, new_radios_df: pd.DataFrame, new_checkboxes_df: pd.DataFrame, 
                         new_yes_or_nos_df: pd.DataFrame, new_gap_fillings_df: pd.DataFrame,
                         output_dir: str = './temp'):
        """
        更新题目数据，将新题目合并到现有DataFrame中并保持拼音排序
        :param new_radios_df: 新的单选题DataFrame
        :param new_checkboxes_df: 新的多选题DataFrame
        :param new_yes_or_nos_df: 新的判断题DataFrame
        :param new_gap_fillings_df: 新的填空题DataFrame
        :param output_dir: 输出目录，默认值为 './temp'
        """
        # 确保DataFrame已加载
        if self.radio_df.empty or self.checkbox_df.empty or self.yes_or_no_df.empty or self.gap_filling_df.empty:
            self.load_questions(output_dir)
        
        # 合并并去重各类题目
        def merge_and_deduplicate(existing_df, new_df):
            if new_df.empty:
                return existing_df
            
            # 合并两个DataFrame
            combined_df = pd.concat([existing_df, new_df], axis=0, ignore_index=True)
            # 根据title列去重，保留第一个出现的值
            deduplicated_df = combined_df.drop_duplicates(subset=['title'], keep='first')

            # 直接对DataFrame进行拼音排序
            # 使用sort_values方法配合自定义排序键
            sorted_df = deduplicated_df.sort_values(
                by='title',
                key=lambda x: x.apply(lambda y: ''.join(lazy_pinyin(str(y))))
            ).reset_index(drop=True)

            return sorted_df
        
        # 执行合并与去重
        updated_radios_df = merge_and_deduplicate(self.radio_df, new_radios_df)
        updated_checkboxes_df = merge_and_deduplicate(self.checkbox_df, new_checkboxes_df)
        updated_yes_or_nos_df = merge_and_deduplicate(self.yes_or_no_df, new_yes_or_nos_df)
        updated_gap_fillings_df = merge_and_deduplicate(self.gap_filling_df, new_gap_fillings_df)
        
        # 更新实例的DataFrame
        self.radio_df = updated_radios_df
        self.checkbox_df = updated_checkboxes_df
        self.yes_or_no_df = updated_yes_or_nos_df
        self.gap_filling_df = updated_gap_fillings_df
        
        # 保存到文件
        self.save_result_parquet(updated_radios_df, updated_checkboxes_df, updated_yes_or_nos_df, updated_gap_fillings_df,
                                 output_dir)
        self.save_result(updated_radios_df, updated_checkboxes_df, updated_yes_or_nos_df, updated_gap_fillings_df, output_dir)

    @staticmethod
    def extract_questions(html: str):
        pattern = r'<div class="error_sub">(.*?)</div>\s*(?=<div class="error_sub"|<!--    <div class="foot_top">-->)'
        error_subs = re.findall(pattern, html, re.DOTALL)
        radios = []
        checkboxes = []
        yes_or_nos = []
        gap_fillings = []

        for error_sub_content in error_subs:
            item = {}

            # 2. 提取 h3 标签中的标题
            title_pattern = r'<h3>(.*?)</h3>'
            title_match = re.search(title_pattern, error_sub_content, re.DOTALL)
            if title_match:
                # 先去除开头数字，再处理空白字符
                cleaned_title = re.sub(r'^\d+、\s*', '', title_match.group(1))
                # 清理空白字符
                item['title'] = re.sub(r'\s+', ' ', cleaned_title.strip())
            else:
                item['title'] = ''

            # 3. 提取所有 label 中的选项文本
            # 匹配 <label>...</label> 并提取其中除了 input 标签外的文本
            label_pattern = r'<label[^>]*>(.*?)</label>'
            labels = re.findall(label_pattern, error_sub_content, re.DOTALL)

            options = []
            for label_content in labels:
                # 移除 input 标签
                option_text = re.sub(r'<input[^>]*/?>', '', label_content)
                # 清理空白字符
                option_text = re.sub(r'\s+', ' ', option_text.strip())
                if option_text:
                    options.append(option_text)

            item['options'] = np.array(options)

            # 4. 提取 class="sub_color" 的 span 中的正确答案
            answer_pattern = r'<span class="sub_color">(.*?)</span>'
            answer_match = re.search(answer_pattern, error_sub_content)
            if answer_match:
                item['correct_answer'] = answer_match.group(1).strip()[5:]
            else:
                # 没有提供正确答案，默认设为空字符串
                # item['correct_answer'] = ''
                # 没有提供正确答案，无意义，跳过
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
    def save_result(radios_df: pd.DataFrame, checkboxes_df: pd.DataFrame, yes_or_nos_df: pd.DataFrame, gap_fillings_df: pd.DataFrame, output_dir: str= './temp'):
        """
        保存考试结果到指定目录
        :param radios_df: 单选题DataFrame，包含题目信息和用户答案
        :param checkboxes_df: 多选题DataFrame，包含题目信息和用户答案
        :param yes_or_nos_df: 判断题DataFrame，包含题目信息和用户答案
        :param gap_fillings_df: 填空题DataFrame，包含题目信息和用户答案
        :param output_dir: 输出文件目录，默认值为 './temp'
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 定义题目类型和对应的文件名
        question_types = [
            ('单选', radios_df, 'radios.txt'),
            ('多选', checkboxes_df, 'checkboxes.txt'),
            ('判断', yes_or_nos_df, 'yes_or_nos.txt'),
            ('填空', gap_fillings_df, 'gap_fillings.txt')
        ]

        # 处理每种题型
        for type_name, questions_df, filename in question_types:
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"{type_name}题 (共{len(questions_df)}道)\n\n")

                # 为每个题目添加编号并写入文件
                for i, question_row in questions_df.iterrows():
                    # 写入编号
                    f.write(f"{i + 1}. ")

                    # 写入title（第一行）
                    title = html.unescape(question_row.get('title', '无标题'))
                    f.write(f"{title}\n")

                    # 写入options（第二行，如果不为空）
                    if 'options' in question_row.index and question_row['options'].any():
                        options = question_row['options']
                        # 如果options是字典格式 {"A": "选项A", "B": "选项B", ...}
                        if isinstance(options, dict):
                            options_str = '; '.join([f"{key}: {value}" for key, value in options.items()])
                        # 如果options是列表格式 ["选项A", "选项B", ...]
                        elif isinstance(options, (list, tuple)):
                            options_str = '; '.join(options)
                        else:
                            options_str = str(options)
                        f.write(f"{options_str}\n")

                    # 写入正确答案（第三行）
                    answer = question_row.get('correct_answer', 'Error!')
                    f.write(f"正确答案: {answer}\n")

                    # 添加题目标题分隔符
                    f.write("-" * 50 + "\n\n")

            print(f"已将{len(questions_df)}道{type_name}题保存到: {filepath}")

    @staticmethod
    def save_result_parquet(radios_df: pd.DataFrame, checkboxes_df: pd.DataFrame, yes_or_nos_df: pd.DataFrame, gap_fillings_df: pd.DataFrame, output_dir: str= './temp'):
        """
        保存考试结果到指定目录
        :param radios_df: 单选题DataFrame，包含题目信息和用户答案
        :param checkboxes_df: 多选题DataFrame，包含题目信息和用户答案
        :param gap_fillings_df: 填空题DataFrame，包含题目信息和用户答案
        :param yes_or_nos_df: 判断题DataFrame，包含题目信息和用户答案
        :param output_dir: 输出文件路径，默认值为 './exam_results.parquet'
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        radio_path = os.path.join(output_dir, 'radios.parquet')
        checkboxes_path = os.path.join(output_dir, 'checkboxes.parquet')
        yes_or_nos_path = os.path.join(output_dir, 'yes_or_nos.parquet')
        gap_fillings_path = os.path.join(output_dir, 'gap_fillings.parquet')

        radios_df.to_parquet(radio_path, index=False)
        checkboxes_df.to_parquet(checkboxes_path, index=False)
        yes_or_nos_df.to_parquet(yes_or_nos_path, index=False)
        gap_fillings_df.to_parquet(gap_fillings_path, index=False)

    @staticmethod
    def sort_by_pinyin(items):
        """按title的拼音顺序排序题目列表"""
        return sorted(items, key=lambda x: ''.join(lazy_pinyin(x['title'])) if 'title' in x else '')


def main():
    cookies = {
        'first_lesson_study': '1',
        '_xsrf': '2|95603c0c|6a5e80cd340c5747d2f5683bc6a566b2|1763696561',
        'menu_open': 'false',
        'is_first': '"2|1:0|10:1764071481|8:is_first|4:MA==|145c6b85b9a55bced47d1948924c5d4885c292c248811b4143c5af37960714b1"',
        'token': 'eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjozMDczMiwic3RhdGUiOjEsInVzZXJfc2lkIjoiMjAyNTIxMTEwNDExIiwidXNlcl9uYW1lIjoiXHU1ZjZkXHU1YjUwXHU2MDUyIiwidXNlcl9wd2QiOiJiYWNiYmMxNTc0ZTkxMzY3NzhkMmFkMzQ1ZDhhYjBlMWY4MGE3ODlhIiwicGFydHlfY2F0ZWdvcnkiOjAsInBoYXNlIjoyLCJhdmF0YXIiOiIiLCJ0cnVlX2F2YXRhciI6IiIsInJvbGVfaWQiOjEsInBhcnR5X2JyYW5jaCI6IiIsInNzb19pZCI6IiIsImlzX3ZpcnR1YWwiOjAsImlzX2ZpcnN0X2xvZ2luIjowLCJzdGF0ZV9pZCI6NDc5NTQsInNlc3Npb24iOiIyM2RhOTYzYy02NTY0LTQ5NjUtOTFmZi1lNTNhOTRhMjg5MTciLCJ0b2tlbiI6MTc2NDA3MTQ4MSwiZXhwIjoxNzY0MDczMjgxfQ.NPHzPdG0EXyST2bXqt4Y_Pr95ijcnUYFOm0pJFX6lyM',
        'ua_id': '"2|1:0|10:1764086656|5:ua_id|524:eyJ1c2VyX2lkIjogMzA3MzIsICJzdGF0ZSI6IDEsICJ1c2VyX3NpZCI6ICIyMDI1MjExMTA0MTEiLCAidXNlcl9uYW1lIjogIlx1NWY2ZFx1NWI1MFx1NjA1MiIsICJ1c2VyX3B3ZCI6ICJiYWNiYmMxNTc0ZTkxMzY3NzhkMmFkMzQ1ZDhhYjBlMWY4MGE3ODlhIiwgInBhcnR5X2NhdGVnb3J5IjogMCwgInBoYXNlIjogMiwgImF2YXRhciI6ICIiLCAidHJ1ZV9hdmF0YXIiOiAiIiwgInJvbGVfaWQiOiAxLCAicGFydHlfYnJhbmNoIjogIiIsICJzc29faWQiOiAiIiwgImlzX3ZpcnR1YWwiOiAwLCAiaXNfZmlyc3RfbG9naW4iOiAwLCAic3RhdGVfaWQiOiA0Nzk1NCwgInNlc3Npb24iOiAiMjNkYTk2M2MtNjU2NC00OTY1LTkxZmYtZTUzYTk0YTI4OTE3IiwgInRva2VuIjogMTc2NDA3MTQ4MX0=|0a9cbcb345d2d47f07cddea9e1d0b942c5744a1a13de9ad0b2b221140c4dd827"',
    }

    player = JJFZAutoPlayer(cookies=cookies)
    player.load_questions()
    player.save_result(player.radio_df.reset_index(drop=True), player.checkbox_df.reset_index(drop=True),
                       player.yes_or_no_df.reset_index(drop=True), player.gap_filling_df.reset_index(drop=True))
    player.save_result_parquet(player.radio_df.reset_index(drop=True), player.checkbox_df.reset_index(drop=True),
                               player.yes_or_no_df.reset_index(drop=True), player.gap_filling_df.reset_index(drop=True))
    # failed_lessons = player.get_lessons_and_save(output_dir='./temp')
    # player.get_required_lessons(lesson_id=517)
    # print(f"失败的课程: {failed_lessons}")
    # player.get_required_lessons(lesson_id=515)
    # player.get_exam_paper(595964)
    r_ids = player.get_exam_list()
    # r_ids = [611867]
    # player.load_questions()
    lesson_r_ids = player.get_lesson_exam_list()
    new_raios_df, new_checkboxes_df, new_yes_or_nos_df, new_gap_fillings_df = player.collect_unique_questions(r_ids=r_ids, lesson_r_ids=lesson_r_ids)
    player.update_questions(new_raios_df, new_checkboxes_df, new_yes_or_nos_df, new_gap_fillings_df)


if __name__ == "__main__":
    main()