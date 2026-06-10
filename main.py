from dxpx.common.cookies import load_cookies
from dxpx.jjfz.exam import Exam
from dxpx.jjfz.jjfz import JJFZAutoPlayer


def main():
    cookies = load_cookies('cookies.json')
    player = JJFZAutoPlayer(cookies=cookies)
    player.load_questions()
    jjfz_exam = Exam(cookies=cookies)
    jjfz_exam
