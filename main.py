from jjfz import JJFZAutoPlayer
from exam import Exam

def main():
    cookies = {
        'first_lesson_study': '1',
        '_xsrf': '2|95603c0c|6a5e80cd340c5747d2f5683bc6a566b2|1763696561',
        'menu_open': 'false',
        'is_first': '"2|1:0|10:1763964149|8:is_first|4:MA==|5448f2b12dc33a60b27b5813cf3d79ed420ef32638444c2aae795a1555b0c538"',
        'token': 'eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjozMDg2OCwic3RhdGUiOjEsInVzZXJfc2lkIjoiMjAyNTIxMTEwNDE0IiwidXNlcl9uYW1lIjoiXHU2NjEzXHU1MmM3XHU1ZjNhIiwidXNlcl9wd2QiOiJjNDFhNmRhNjEyMTYwYjVhYzgyOTA3ZjIyYjcyZWUzZmFhZTc1ODI0IiwicGFydHlfY2F0ZWdvcnkiOjAsInBoYXNlIjoyLCJhdmF0YXIiOiIiLCJ0cnVlX2F2YXRhciI6IiIsInJvbGVfaWQiOjEsInBhcnR5X2JyYW5jaCI6IiIsInNzb19pZCI6IiIsImlzX3ZpcnR1YWwiOjAsImlzX2ZpcnN0X2xvZ2luIjowLCJzdGF0ZV9pZCI6NDgwOTQsInNlc3Npb24iOiIwMGQ4OWFjNi1hMjY5LTQ5NGYtYTdmMC1jYjhlZTcwNzVkOTgiLCJ0b2tlbiI6MTc2Mzk2NDE0OSwiZXhwIjoxNzYzOTY1OTQ5fQ.xZbnsnyA4eA49gDLYKjG_o408gYJ35elKf1eHju1iQc',
        'ua_id': '"2|1:0|10:1763965486|5:ua_id|524:eyJ1c2VyX2lkIjogMzA4NjgsICJzdGF0ZSI6IDEsICJ1c2VyX3NpZCI6ICIyMDI1MjExMTA0MTQiLCAidXNlcl9uYW1lIjogIlx1NjYxM1x1NTJjN1x1NWYzYSIsICJ1c2VyX3B3ZCI6ICJjNDFhNmRhNjEyMTYwYjVhYzgyOTA3ZjIyYjcyZWUzZmFhZTc1ODI0IiwgInBhcnR5X2NhdGVnb3J5IjogMCwgInBoYXNlIjogMiwgImF2YXRhciI6ICIiLCAidHJ1ZV9hdmF0YXIiOiAiIiwgInJvbGVfaWQiOiAxLCAicGFydHlfYnJhbmNoIjogIiIsICJzc29faWQiOiAiIiwgImlzX3ZpcnR1YWwiOiAwLCAiaXNfZmlyc3RfbG9naW4iOiAwLCAic3RhdGVfaWQiOiA0ODA5NCwgInNlc3Npb24iOiAiMDBkODlhYzYtYTI2OS00OTRmLWE3ZjAtY2I4ZWU3MDc1ZDk4IiwgInRva2VuIjogMTc2Mzk2NDE0OX0=|2b87ab2ad7d5accd122591f5577b494b188ba2253180e143054b64726a0af31c"',
    }
    player = JJFZAutoPlayer(cookies=cookies)
    player.load_questions()
    jjfz_exam = Exam(cookies=cookies)
    jjfz_exam
