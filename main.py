import argparse

from dxpx.common.login import ROOT, get_auth_headers
from dxpx.fzdx.exam import FZDXExam
from dxpx.fzdx.fzdx import FZDXAutoPlayer
from dxpx.jjfz.exam import Exam as JJFZExam
from dxpx.jjfz.jjfz import JJFZAutoPlayer


def build_parser() -> argparse.ArgumentParser:
    """
    创建统一入口的培训类型及操作参数解析器。

    :return: argparse.ArgumentParser；包含 jjfz 和 fzdx 子命令的解析器。
    """
    parser = argparse.ArgumentParser(description='党校培训学习、题库与考试工具')
    platforms = parser.add_subparsers(dest='platform', title='培训类型')
    for name, title in [('jjfz', '积极分子'), ('fzdx', '发展对象')]:
        command = platforms.add_parser(name, help=title, description=f'{title}学习与考试工具')
        command.set_defaults(command_parser=command)
        command.add_argument('--headers-file', default=ROOT / 'headers.json',
                             help='请求头 JSON 文件路径（默认项目根目录 headers.json）')
        command.add_argument('--init', action='store_true', help='采集课程信息、提交观看记录并保存')
        command.add_argument('--output-dir', default=f'dxpx/{name}/temp', help='课程信息保存目录')
        command.add_argument('--update', action='store_true', help='从已完成考试结果更新题库')
        command.add_argument('--exam', action='store_true', help='运行考试流程')
        command.add_argument('--score', action='store_true', help='查询综合考试历史成绩并显示最高分')
        command.add_argument('--echos', type=int, default=None,
                             help=f'考试执行轮数（默认 {30 if name == "jjfz" else 10}）')
        if name == 'jjfz':
            command.add_argument('--lessons', nargs='+', type=int, metavar='LESSON_ID',
                                 help='完成指定课程的必修视频观看任务')
            command.add_argument('--mode', choices=['end', 'lesson'], default=None,
                                 help='考试模式：end 为综合考试（默认），lesson 为章节测试')
    return parser


def main(argv: list[str] | None = None):
    """
    解析统一命令行参数并调用对应培训类型的学习、题库或考试流程。

    :param argv: 命令行参数列表；默认 None 时读取终端参数。
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    lessons = getattr(args, 'lessons', None)
    mode = getattr(args, 'mode', None)
    if args.platform is None:
        parser.print_help()
        return
    learning = args.init or args.update or lessons
    if args.score and (args.exam or learning):
        parser.error('--score 不能与 --exam、--init、--update 或 --lessons 同时使用')
    if args.exam and learning:
        parser.error('--exam 不能与 --init、--update 或 --lessons 同时使用')
    if not args.exam and (args.echos is not None or mode is not None):
        parser.error('--echos 和 --mode 需要与 --exam 一起使用')
    if args.echos is not None and args.echos < 1:
        parser.error('--echos 必须大于 0')
    if not args.exam and not args.score and not learning:
        args.command_parser.print_help()
        return

    try:
        headers = get_auth_headers(args.headers_file)
    except RuntimeError as error:
        parser.exit(1, f'{error}\n')

    if args.exam or args.score:
        exam_cls = JJFZExam if args.platform == 'jjfz' else FZDXExam
        exam = exam_cls(headers=headers)
        echos = args.echos if args.echos is not None else (30 if args.platform == 'jjfz' else 10)
        try:
            if args.score:
                exam.print_exam_scores()
            elif mode == 'lesson':
                exam.finish_many_lesson_exams(echos=echos)
            else:
                exam.finish_many_exams(echos=echos)
        finally:
            exam.session.close()
        return

    player_cls = JJFZAutoPlayer if args.platform == 'jjfz' else FZDXAutoPlayer
    player = player_cls(headers=headers)
    try:
        if args.init:
            failed, collected = player.get_lessons_and_save(output_dir=args.output_dir, save=True)
            print(f'--init 已采集 {len(collected)} 个课程并提交观看记录，失败记录：\n{failed}')
            print('接口接受不等于网站进度已完成，请以平台显示为准。')
        if args.update:
            player.update_from_exam_results()
        if lessons:
            player.finish_lessons(lessons)
    finally:
        player.session.close()


if __name__ == "__main__":
    main()
