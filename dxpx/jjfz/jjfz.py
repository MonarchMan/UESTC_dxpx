import json

from typing import List, Tuple, Optional

import os
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed


from dxpx.common.player import BaseAutoPlayer

pages = 2


def load_lessons(file_path='./temp/lessons.json'):
    """
    从 JSON 文件加载本地课程记录。
    
    :param file_path: 本地课程 JSON 文件路径。默认值为 './temp/lessons.json'。
    :return: JSON 解析结果；通常为包含 lesson_id 和 id_params 的课程字典列表。
    """
    return BaseAutoPlayer.load_lessons(file_path)


class JJFZAutoPlayer(BaseAutoPlayer):
    question_dir = 'dxpx/jjfz/temp'
    lesson_dir = 'dxpx/jjfz/temp'

    def __init__(self, headers: dict):
        """
        初始化实例状态。
        
        :param headers: 已加载的身份请求头，补充页面需要的其他请求头后继续使用。
        """
        super().__init__(headers)
        self.headers.update({
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
        })

    def parse_m3u8(self, url: str):
        """
        解析 M3U8 播放列表，提取媒体属性、片段地址和总时长。
        
        :param url: M3U8 播放列表地址。
        :return: dict；包含版本、目标时长、序号、缓存标志、总时长和 segments 列表。
        """
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url, headers=self.headers, params=params)
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
        """
        下载已解析播放列表中指定位置的 TS 视频片段。
        
        :param index: TS 片段在 self.ts_list 中的位置，从 0 开始。
        :return: 二元组 (filename, content)；content 为二进制内容，下载失败时为 None。
        """
        segment = self.ts_list[index]
        total = len(self.ts_list)
        try:
            params = {
                'stg': self.stage,
            }
            response = self.session.get(self.ts_list[index]['url'], headers=self.headers, params=params, timeout=30)

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
        """
        并发下载当前播放列表中的所有 TS 片段到指定目录。
        
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 './temp'。
        :param max_workers: 并发下载线程数量。默认值为 5。
        :return: dict[str, bool]；以片段文件名为键、是否成功保存为值的结果字典。
        """
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n开始下载 {len(self.ts_list)} 个视频片段...")
        print(f"使用 {max_workers} 个线程并发下载\n")

        results = {}

        # 网络下载并发执行，完成后按各自文件名保存，不依赖完成顺序。
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
        """
        按播放列表顺序拼接本地 TS 片段，不执行 MP4 转码。
        
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 'ts_segments'。
        :param output_file: 期望的输出文件名；实际将 .mp4 后缀替换为 .ts。默认值为 'merged_video.mp4'。
        :return: str；实际生成的合并 TS 文件路径。
        """
        print(f"\n开始合并视频片段...")

        # 方法1：直接合并TS文件（简单但可能有问题）
        merged_ts = output_file.replace('.mp4', '.ts')

        # 合并必须遵循播放列表顺序，不能使用下载完成顺序。
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
        定位目标时间所属的片段及片段内偏移。
        
        :param target_seconds: 目标播放时间，单位为秒。
        :return: dict；包含 segment_index、segment、offset_in_segment、total_time；超出总时长时定位末片段。
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

    def check_record(self, lesson_id: int, video_id: int, resource_id: int, r_id: int) -> bool:
        """
        向平台提交指定视频的观看记录。
        
        :param lesson_id: 课程或章节标识。
        :param video_id: 视频标识。
        :param resource_id: 视频资源标识；部分播放链接允许为 None。
        :param r_id: 视频观看记录标识。
        :return: bool；平台确认接受记录时为 True，否则为 False。
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/resource_record'
        data = {
            'rid': r_id,
            'lesson_id': lesson_id,
            'resource_id': resource_id,
            'video_id': video_id,
            '_xsrf': self.headers['_xsrf'],
        }
        params = {
            'stg': self.stage,
        }
        response = self.session.post(url=url, headers=self.headers, params=params, data=data)
        if response.status_code == 200:
            try:
                return response.json().get('code') == 1
            except ValueError:
                return False
        return False

    def get_lessons_and_save(self, output_dir: Optional[str] = None, save=False) -> Tuple[List, List]:
        """
        遍历课程分页，提交视频记录并按需保存课程信息。
        
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 None。
        :param save: 是否将结果保存到本地文件。默认值为 False。
        :return: 二元组 (failed_list, lessons)，分别为提交失败的记录列表和收集到的课程列表。
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

    def get_required_lessons(self, lesson_id: int, page: int = 1) -> list[int]:
        """
        获取指定课程、页码的必修视频及分页信息。
        
        :param lesson_id: 课程或章节标识。
        :param page: 课程列表或播放页的页码，从 1 开始。默认值为 1。
        :return: 三元组 (id_pairs, rest_ids, total_pages)；分别为字符串资源对、微课件视频标识列表和总页数。
        """
        params = {
            'lesson_id': lesson_id,
            'required': 1,
            'page': page,
            'stg': self.stage,
        }

        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/video'
        response = self.session.get(url=url, params=params, headers=self.headers)
        return self.extract_required_lessons_info(response.text)

    def get_lesson_r_id(self, video_id: int, resource_id: int, page: int = 1) -> int:
        """
        从播放页第八个脚本中提取包含完整资源字段的观看记录标识。
        
        :param video_id: 视频标识。
        :param resource_id: 视频资源标识；部分播放链接允许为 None。
        :param page: 课程列表或播放页的页码，从 1 开始。默认值为 1。
        :return: int；匹配到的观看记录标识，脚本不足或未匹配到时为 0。
        """
        params = {
            'v_id': video_id,
            'r_id': resource_id,
            'r': 'video',
            't': '2',
            'pg': page,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/play'
        response = self.session.get(url=url, params=params, headers=self.headers)

        # 1) 取 /html/body/script[8]（XPath 1-indexed → Python list index 7）
        script_pattern = re.compile(r'<script\b[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
        scripts = script_pattern.findall(response.text)
        if len(scripts) < 8:
            return 0
        script_block = scripts[7]

        # 2) 在 script_block 里找"4 字段齐全"的 rid
        #    形如：rid: "N", resource_id: "M", video_id: "K", lesson_id: "L"
        rid_pattern = re.compile(
            r'rid:\s*"(\d+)"\s*,\s*resource_id:\s*"(\d+)"\s*,\s*video_id:\s*"(\d+)"\s*,\s*lesson_id:\s*"(\d+)"'
        )
        match = rid_pattern.search(script_block)
        if match:
            return int(match.group(1))
        return 0

    def finish_single_lesson(self, lesson_id: int) -> dict:
        """
        收集单个课程的视频资源对，去重后提交观看记录。
        
        :param lesson_id: 课程或章节标识。
        :return: dict；success 和 failed 分别记录成功条目与包含失败原因的条目。
        """
        results = {'success': [], 'failed': []}
        seen_pairs = set()
        v_ids = self.get_required_lessons(lesson_id)
        for v_id in v_ids:
            pairs = self.get_lesson_v_resource_id(v_id)
            for video_id, resource_id in pairs:
                if (video_id, resource_id) in seen_pairs:
                    continue
                seen_pairs.add((video_id, resource_id)) #去重，避免同一对视频被多个种子扫到时重复提交影响速度
                r_id = self.get_lesson_r_id(video_id, resource_id)
                if not r_id:
                    results['failed'].append({
                        'video_id': video_id,
                        'resource_id': resource_id,
                        'reason': 'no_rid',
                    })
                    continue
                ok = self.check_record(lesson_id, video_id, resource_id, r_id)
                entry = {
                    'video_id': video_id,
                    'resource_id': resource_id,
                    'r_id': r_id,
                }
                if ok:
                    results['success'].append(entry)
                else:
                    entry['reason'] = 'check_record_failed'
                    results['failed'].append(entry)
        return results

    def finish_lessons(self, lesson_ids: list) -> list:
        """
        依次提交多个课程的视频观看记录并汇总结果。
        
        :param lesson_ids: 需要处理的课程标识列表。
        :return: list；存在失败观看记录的课程标识列表。
        """
        failed_lessons = []
        total_success = 0
        total_failed = 0
        for lid in lesson_ids:
            print(f'提交 lesson {lid}...')
            results = self.finish_single_lesson(lid)
            s_count = len(results['success'])
            f_count = len(results['failed'])
            total_success += s_count
            total_failed += f_count
            print(f'  成功 {s_count} 条, 失败 {f_count} 条')
            for entry in results['failed']:
                print(f'    失败: {entry}')
            if f_count > 0:
                failed_lessons.append(lid)
        print(f'\n总计: 成功 {total_success} 条, 失败 {total_failed} 条')
        return failed_lessons

    def get_lesson_v_resource_id(self, video_id: int, page: int = 1) -> list[tuple[int, int]]:
        """
        从播放页中不含 title 属性的链接提取视频和资源标识。
        
        :param video_id: 视频标识。
        :param page: 课程列表或播放页的页码，从 1 开始。默认值为 1。
        :return: list[tuple[int, int]]；匹配到的 (video_id, resource_id) 列表。
        """
        params = {
            'v_id': video_id,
            'r': 'video',
            't': '2',
            'pg': page,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/play'
        response = self.session.get(url=url, params=params, headers=self.headers)
        # 匹配 <a ... href=".../jjfz/play?v_id=N...&r_id=M...">
        # 两个负向先行排除带 title= 属性的 <a> 标签
        pattern = re.compile(
            r'<a\s(?!title=)(?![^>]*\stitle=)[^>]*href="[^"]*\bv_id=(\d+)[^"]*\br_id=(\d+)[^"]*"',
            re.DOTALL,
        )
        return [(int(v), int(r)) for v, r in pattern.findall(response.text)]

    def get_course_ware_extra_ids(self, v_id:int):
        """
        从微课件或专家讲座播放页面提取观看记录和资源标识。
        
        :param v_id: 用于加载播放页的视频标识。
        :return: tuple[str, str]；观看记录标识与资源标识。
        """
        params = {
            'v_id': v_id,
            'r': 'video',
            't': '2',
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/play'
        response = self.session.get(url=url, params=params, headers=self.headers)
        pattern = r'rid: "(\d+)",\s+resource_id: "(\d+)"'
        match = re.search(pattern, response.text)
        return match.group(1), match.group(2)

    def get_lessons(self) -> list:
        """
        获取当前培训阶段的课程标识列表。
        
        :return: list[str]；从页面提取的课程标识。
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson'
        params = {
            'stg': self.stage
        }
        response = self.session.get(url=url, headers=self.headers, params=params)
        pattern = r'<a href="[^"]*lesson_id=(\d+)">'
        lesson_ids = re.findall(pattern, response.text)
        return lesson_ids

    def get_exam_paper(self, r_id: int) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
        """
        获取已完成综合考试的题目及正确答案。
        
        :param r_id: 已完成综合考试的结果标识。
        :return: 四元组 (radios, checkboxes, yes_or_nos, gap_fillings)，每项为题目字典列表。
        """
        params = {
            'rid': r_id,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_show'
        response = self.session.get(url=url, params=params, headers=self.headers)
        pattern = r'<div class="error_sub">(.*?)</div>\s*(?=<div class="error_sub"|<!--    <div class="foot_top">-->)'
        return self.extract_questions(response.text, pattern)

    def get_lesson_exam_paper(self, rid: int):
        """
        获取已完成章节测试的题目及正确答案。
        
        :param rid: 章节测试结果标识。
        :return: 四元组 (radios, checkboxes, yes_or_nos, gap_fillings)，每项为题目字典列表。
        """
        params = {
            'rid': rid,
            'stg': self.stage,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/show'

        response = self.session.get(url=url, params=params, headers=self.headers)
        pattern = r'<div class="error_sub">(.*?)</div>\s*(?=<div class="error_sub"|<!--    <div class="foot_top">-->)'
        return self.extract_questions(response.text, pattern)


    def get_exam_list(self) -> list:
        """
        获取已完成综合考试的结果标识列表。
        
        :return: list[int]；综合考试结果标识列表。
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_record'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url=url, headers=self.headers, params=params)
        pattern = r'rid=(\d+)'
        r_ids = re.findall(pattern, response.text)
        r_ids = [int(r_id) for r_id in r_ids]
        return r_ids

    def get_lesson_exam_list(self):
        """
        获取已完成章节测试的结果标识列表。
        
        :return: list[int]；章节测试结果标识列表。
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/record'
        params = {
            'stg': self.stage,
        }
        response = self.session.get(url=url, headers=self.headers, params=params)
        pattern = r'rid=(\d+)'
        r_ids = re.findall(pattern, response.text)
        r_ids = [int(r_id) for r_id in r_ids]
        return r_ids

    def update_from_exam_results(self):
        """
        从已完成考试的结果中收集新题，更新并保存本地题库。
        """
        r_ids = self.get_exam_list()
        lesson_r_ids = self.get_lesson_exam_list()
        new_raios_df, new_checkboxes_df, new_yes_or_nos_df, new_gap_fillings_df = self.collect_unique_questions(
            r_ids=r_ids, lesson_r_ids=lesson_r_ids)
        self.update_questions(new_raios_df, new_checkboxes_df, new_yes_or_nos_df, new_gap_fillings_df)




