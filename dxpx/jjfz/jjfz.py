import json

import argparse
from typing import List, Tuple

import requests
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

if __package__ is None or __package__ == '':
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from dxpx.common.cookies import load_cookies

from dxpx.common.player import BaseAutoPlayer

pages = 2


def load_lessons(file_path='./temp/lessons.json'):
    return BaseAutoPlayer.load_lessons(file_path)


class JJFZAutoPlayer(BaseAutoPlayer):
    question_dir = 'dxpx/jjfz/temp'
    lesson_dir = 'dxpx/jjfz/temp'

    def __init__(self, cookies: dict):
        super().__init__(cookies)
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

    def check_record(self, lesson_id: int, video_id: int, resource_id: int, r_id: int) -> bool:
        """
        向 /jjfz/lesson/resource_record 提交一条视频观看记录。
        这是服务器判断“看过”的唯一手段——必须带有 rid（观看记录 ID）才会接受。
        :param lesson_id: 课程ID
        :param video_id: 视频ID
        :param resource_id: 资源ID
        :param r_id: 观看记录ID（从 script[8] 里抓到的那个）
        :return: True 表示服务器返回 code=1（接受）
        """
        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/resource_record'
        data = {
            'rid': r_id,
            'lesson_id': lesson_id,
            'resource_id': resource_id,
            'video_id': video_id,
            '_xsrf': self.cookies['_xsrf'],
        }
        response = requests.post(url=url, cookies=self.cookies, headers=self.headers, data=data)
        if response.status_code == 200:
            try:
                return response.json().get('code') == 1
            except ValueError:
                return False
        return False

    def get_required_lessons(self, lesson_id: int, page: int = 1) -> list[int]:
        """
        获取课程的必修课程列表
        :param lesson_id: 课程ID
        :param page: 页码
        :return:
        必修课程视频列表，每个元素为(video_id, resource_id)元组
        微课件或专家讲座的video_id列表
        总页数
        """
        params = {
            'lesson_id': lesson_id,
            'required': 1,
            'page': page,
        }

        url = 'https://dxpx.uestc.edu.cn/jjfz/lesson/video'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        return self.extract_required_lessons_info(response.text)

    def get_lesson_r_id(self, video_id: int, resource_id: int, page: int = 1) -> int:
        """
        从 /jjfz/play 播放页的 /html/body/script[8] 中提取真正的 rid（观看记录 ID）。

        该 script 块里 rid= 会出现多次（如 current_time 定时器里也有一个），
        真正用于 /jjfz/lesson/resource_record 提交的是 player.on('ended') 块里的那个。
        它的唯一签名是后面紧跟 resource_id=, video_id=, lesson_id= 三个字段。
        而 current_time 块只有 rid+time+_xsrf，匹配不上。
        :param video_id: 视频ID
        :param resource_id: 资源ID
        :param page: 页码，非必须参数，默认值为1
        :return: r_id（int）。未找到时返回 0。
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

    def submit_lesson_records(self, lesson_id: int) -> dict:
        """
        走完整流程：对一个 lesson 提交所有必修视频的观看记录。
        链路：get_required_lessons → get_lesson_v_resource_id → get_lesson_r_id → check_record
        注：play 页对每个种子都返回 N 对相邻视频，同一对可能被多种子重复扫到——seen_pairs 去重。
        :param lesson_id: 课程ID
        :return: {'success': [...], 'failed': [...]}
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

    def get_lesson_v_resource_id(self, video_id: int, page: int = 1) -> list[tuple[int, int]]:
        """
        通过访问 /jjfz/play 页面，提取其中所有 (video_id, resource_id) 对。
        匹配形如：
            <a style="width:70%;" href="/jjfz/play?v_id=15228&r_id=61245&r=video&pg=1">...</a>
        的 <a> 标签。r_id 就是 resource_id。
        排除带 title= 属性的 <a> 标签。
        :param video_id: 视频ID（决定从哪个视频开始加载播放页）
        :param page: 页码，非必须参数，默认值为1
        :return: 二元组列表，每个元素为 (video_id, resource_id) 元组
        """
        params = {
            'v_id': video_id,
            'r': 'video',
            't': '2',
            'pg': page,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/play'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        # 匹配 <a ... href=".../jjfz/play?v_id=N...&r_id=M...">
        # 两个负向先行排除带 title= 属性的 <a> 标签
        pattern = re.compile(
            r'<a\s(?!title=)(?![^>]*\stitle=)[^>]*href="[^"]*\bv_id=(\d+)[^"]*\br_id=(\d+)[^"]*"',
            re.DOTALL,
        )
        return [(int(v), int(r)) for v, r in pattern.findall(response.text)]

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

    def get_exam_paper(self, r_id: int) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
        """
        获取考试题库
        :param r_id: 考试ID（rid）
        :return: 考试题库
        """
        params = {
            'rid': r_id,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/end_show'
        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'<div class="error_sub">(.*?)</div>\s*(?=<div class="error_sub"|<!--    <div class="foot_top">-->)'
        return self.extract_questions(response.text, pattern)

    def get_lesson_exam_paper(self, rid: int):
        """
        获取课程考试题库
        :param rid: 课程考试ID（rid）
        :return: 课程考试题库
        """
        params = {
            'rid': rid,
        }
        url = 'https://dxpx.uestc.edu.cn/jjfz/exam_center/show'

        response = requests.get(url=url, params=params, cookies=self.cookies, headers=self.headers)
        pattern = r'<div class="error_sub">(.*?)</div>\s*(?=<div class="error_sub"|<!--    <div class="foot_top">-->)'
        return self.extract_questions(response.text, pattern)


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

    def update_from_exam_results(self):
        """
        从已完成的课程考试和综合测试结果更新题库
        :return:
        """
        r_ids = self.get_exam_list()
        lesson_r_ids = self.get_lesson_exam_list()
        new_raios_df, new_checkboxes_df, new_yes_or_nos_df, new_gap_fillings_df = self.collect_unique_questions(
            r_ids=r_ids, lesson_r_ids=lesson_r_ids)
        self.update_questions(new_raios_df, new_checkboxes_df, new_yes_or_nos_df, new_gap_fillings_df)


def main():
    parser = argparse.ArgumentParser(description='积极分子学习与题库工具')
    parser.add_argument(
        '--cookies-file', default='cookies.json',
        help='cookies JSON 文件路径（默认 cookies.json）',
    )
    parser.add_argument('--init', action='store_true', help='获取课程列表，完成观看任务并保存')
    parser.add_argument('--output-dir', default=JJFZAutoPlayer.lesson_dir, help='设置课程列表保存目录')
    parser.add_argument('--update', action='store_true', help='从已完成考试结果更新题库')
    parser.add_argument('--submit', type=int, metavar='LESSON_ID',
                        help='提交指定 lesson 的所有必修视频观看记录')
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

    player = JJFZAutoPlayer(cookies=cookies)
    if args.init:
        failed_lessons, success_lessons = player.get_lessons_and_save(output_dir=args.output_dir, save=True)
        print(f"--init 完成：采集 {len(success_lessons)} 个 lesson, 共 {len(failed_lessons)} 个视频（未提交）")
    if args.update:
        player.update_from_exam_results()

    # --submit 走 submit_lesson_records 链路
    if args.submit:
        target_lessons = [args.submit]
        total_success = 0
        total_failed = 0
        for lid in target_lessons:
            print(f'提交 lesson {lid}...')
            results = player.submit_lesson_records(lid)
            s_count = len(results['success'])
            f_count = len(results['failed'])
            total_success += s_count
            total_failed += f_count
            print(f'  成功 {s_count} 条, 失败 {f_count} 条')
            for entry in results['failed']:
                print(f'    失败: {entry}')
        print(f'\n总计: 成功 {total_success} 条, 失败 {total_failed} 条')
        return

    if not args.init and not args.update:
        parser.print_help()


if __name__ == "__main__":
    main()
