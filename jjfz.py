import json

import requests
import os
import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

pages = 2


def load_lessons(file_path='./temp/lessons.json'):
    with open(file_path, 'r', encoding='utf-8') as f:
        lessons = json.load(f)
    return lessons


class JJFZAutoPlayer:
    def __init__(self):
        self.ts_list = []
        self.cookies = {
            'first_lesson_study': '1',
            '_xsrf': '2|8d1892bd|0fd757f0a4a52949a179c5a18981bfd6|1763696939',
            'is_first': '"2|1:0|10:1763717002|8:is_first|4:MA==|2548a59054020800b906b3be54822c32143c05608b0dbd9479589c031a941373"',
            'token': 'eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjozMDczMiwic3RhdGUiOjEsInVzZXJfc2lkIjoiMjAyNTIxMTEwNDExIiwidXNlcl9uYW1lIjoiXHU1ZjZkXHU1YjUwXHU2MDUyIiwidXNlcl9wd2QiOiJiYWNiYmMxNTc0ZTkxMzY3NzhkMmFkMzQ1ZDhhYjBlMWY4MGE3ODlhIiwicGFydHlfY2F0ZWdvcnkiOjAsInBoYXNlIjoyLCJhdmF0YXIiOiIiLCJ0cnVlX2F2YXRhciI6IiIsInJvbGVfaWQiOjEsInBhcnR5X2JyYW5jaCI6IiIsInNzb19pZCI6IiIsImlzX3ZpcnR1YWwiOjAsImlzX2ZpcnN0X2xvZ2luIjowLCJzdGF0ZV9pZCI6NDc5NTQsInNlc3Npb24iOiIwYzQ3YjkxOS0zYTZlLTRjMWItYmI5OS00MTAzNzdiYWQ2YTciLCJ0b2tlbiI6MTc2MzcxNzAwMiwiZXhwIjoxNzYzNzE4ODAyfQ.f5pBhUj2UoUJOdUkttqLPNzbdOemkpEv0NdW-eiMMlQ',
            'ua_id': '"2|1:0|10:1763717021|5:ua_id|524:eyJ1c2VyX2lkIjogMzA3MzIsICJzdGF0ZSI6IDEsICJ1c2VyX3NpZCI6ICIyMDI1MjExMTA0MTEiLCAidXNlcl9uYW1lIjogIlx1NWY2ZFx1NWI1MFx1NjA1MiIsICJ1c2VyX3B3ZCI6ICJiYWNiYmMxNTc0ZTkxMzY3NzhkMmFkMzQ1ZDhhYjBlMWY4MGE3ODlhIiwgInBhcnR5X2NhdGVnb3J5IjogMCwgInBoYXNlIjogMiwgImF2YXRhciI6ICIiLCAidHJ1ZV9hdmF0YXIiOiAiIiwgInJvbGVfaWQiOiAxLCAicGFydHlfYnJhbmNoIjogIiIsICJzc29faWQiOiAiIiwgImlzX3ZpcnR1YWwiOiAwLCAiaXNfZmlyc3RfbG9naW4iOiAwLCAic3RhdGVfaWQiOiA0Nzk1NCwgInNlc3Npb24iOiAiMGM0N2I5MTktM2E2ZS00YzFiLWJiOTktNDEwMzc3YmFkNmE3IiwgInRva2VuIjogMTc2MzcxNzAwMn0=|7698ae9ac85c10a40a4c4f16c563c05d65283208499d66d87b06a55ef9e0e2bb"',
        }

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

                # 处理微课件
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


def main():

    player = JJFZAutoPlayer()
    failed_lessons = player.get_lessons_and_save(output_dir='./temp')
    # player.get_required_lessons(lesson_id=517)
    print(f"失败的课程: {failed_lessons}")
    # player.get_required_lessons(lesson_id=515)


if __name__ == "__main__":
    main()