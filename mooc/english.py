import html
import re

import requests
import os

class English:
    def __init__(self, cookies: dict):
        """
        初始化实例状态。
        
        :param cookies: 学堂在线请求使用的 Cookie 字典。
        """
        self.cookies = cookies
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh',
            'app-name': 'xtzx',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'django-language': 'zh',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.xuetangx.com/learn/uestcP0502KC006759/uestcP0502KC006759/26144715/exercise/65306913',
            'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'terminal-type': 'web',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
            'x-client': 'web',
            'xtbz': 'xt',
        }

    def get_unit_exercise_list(self, unit_id: int, lesson_id: int) -> list:
        """
        获取指定单元的练习题，并清理题干和选项中的部分 HTML 标签。
        
        :param unit_id: 英语练习所在单元标识。
        :param lesson_id: 英语课程标识。
        :return: 包含 title、options 及可用用户答案 answer 的题目列表。
        """
        url = f'https://www.xuetangx.com/api/v1/lms/exercise/get_exercise_list/{unit_id}/{lesson_id}/'
        response = requests.get(url=url, cookies=self.cookies, headers=self.headers)
        data = response.json()['data']
        problems = data['problems']
        questions = []
        for problem in problems:
            question = {
                "title": problem['content']['Body'],
                "options": [],
            }
            title_patten = r'<p[^>]*>(.*?)</p>'
            title_match = re.search(title_patten, question["title"], re.DOTALL)
            if title_match:
                question["title"] = title_match.group(1)
                # 然后使用正则表达式去除<span>和</span>标签
                # 这个正则表达式会匹配所有形如<span...>和</span>的标签
                question["title"] = re.sub(r'<span[^>]*>|</span>', '', question["title"])
            for option in problem['content']['Options']:
                # 提取<p>标签中的内容（有些题目的options选项里有html标签，需进行处理）
                pattern = r'<p[^>]*>(.*?)</p>'
                match = re.search(pattern, option['value'])
                if match:
                    option['value'] = match.group(1)
                question["options"].append(option)
            # 平台用不同字段保存单个答案和多个答案，统一放入 answer。
            if "my_answer" in problem['user']:
                question['answer'] = problem['user']['my_answer']
            elif "my_answers" in problem['user']:

                question['answer'] = problem['user']['my_answers']
            questions.append(question)
        return questions

    def get_all_unit_exercise_list(self, lesson_id: int, save: bool = False) -> list:
        """
        汇总预设单元的练习题，按题干排序并按需保存。
        
        :param lesson_id: 英语课程标识。
        :param save: 是否将结果保存到本地文件。默认值为 False。
        :return: 按题干排序后的练习题列表。
        """
        unit_ids = [5686240, 5686242, 5686244, 5686246, 5686248, 5686250, 5686252, 5686253]
        all_questions = []
        for unit_id in unit_ids:
            questions = self.get_unit_exercise_list(unit_id, lesson_id)
            all_questions.extend(questions)

        # 按title排序questions列表
        # 使用sorted函数和lambda表达式按title字段排序
        sorted_questions = sorted(all_questions, key=lambda question: question['title'])

        if save:
            self.save(sorted_questions)
        return sorted_questions

    @staticmethod
    def save(questions: list, output_dir="../doc/mooc"):
        # 确保输出目录存在
        """
        将英语练习题的题干、选项和用户答案写入文本文件。
        
        :param questions: 待保存的题目字典列表，包含题干、选项及用户答案。
        :param output_dir: 输出目录；为 None 时使用实例配置的对应保存目录。默认值为 '../doc/mooc'。
        """
        os.makedirs(output_dir, exist_ok=True)
        # 构建完整文件路径
        file_path = os.path.join(output_dir, "english.txt")

        with open(file_path, 'w', encoding='utf-8') as f:
            for question in questions:
                # 写入标题
                if "title" in question:
                    f.write(f"{html.unescape(question['title'])}\n")
                # 写入选项
                if "options" in question:
                    # 假设options是字典，需要格式化输出
                    options_str = "\n".join([f"{option['key']}: {option['value']}" for option in question['options']])
                    f.write(f"{options_str}\n")
                # 写入答案
                if isinstance(question['answer'], list):
                    f.write(f"Answer: {','.join(question['answer'])}\n")
                elif isinstance(question['answer'], dict):
                    # 获取字典的key列表并转换为字符串
                    keys_str = ", ".join(list(question['answer'].keys()))
                    f.write(f"Answer: {keys_str}\n")
                # 每个问题后添加空行分隔
                f.write("\n")

def main():
    """
    使用当前模块配置获取英语练习题并保存到本地。
    """
    cookies = {
        '_abfpc': '00303bb98fec79728efcbc4e4dd27b2d8a4443f0_2.0',
        'cna': '123f7a1ee75f27568b50a13df12d8eeb',
        'provider': 'xuetang',
        'django_language': 'zh',
        'point': '{%22point_active%22:true%2C%22platform_task_active%22:true%2C%22learn_task_active%22:true}',
        'login_type': 'WX',
        'csrftoken': 'q7qEucNQFFhUv5VWFuaGex5mm5uDYoKa',
        'sessionid': 'aj8jzruu9u7jy55akxirwoygdnm779pv',
        'mode_type': 'normal',
        'k': '40726631',
        'sensorsdata2015jssdkcross': '%7B%22distinct_id%22%3A%2240726631%22%2C%22first_id%22%3A%2219a6bf6f851fd5-0f843fc590e41e-4c657b58-1327104-19a6bf6f852135e%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219a6bf6f851fd5-0f843fc590e41e-4c657b58-1327104-19a6bf6f852135e%22%7D',
    }
    english = English(cookies)
    questions = english.get_all_unit_exercise_list(lesson_id=13098217, save=True)
    print(f"Total questions: {len(questions)}")

if __name__ == '__main__':
    main()
