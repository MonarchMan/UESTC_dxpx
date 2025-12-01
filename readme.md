# 电子科技大学（UESTC）积极分子培训脚本
## All you need is a Python script!
2025.11.21 经过测试，脚本顺利运行，并完成所有课程的观看任务。后续会考虑加入发展对相关视频的支持。<br>

## 使用方法
### 1. 安装依赖
通常情况下编译器已经预装了所需依赖，如`requests`等。如果未安装，请根据提示安装。
### 2. 修改Cookies
#### 2.1 复制请求
登录自己的积极分子账号后，打开浏览器开发者工具（如Chrome的F12或Edge的F12），切换到Network（网络）标签页。
刷新页面，找到第一个请求，复制其Cookies值。<br>
如果你不会操作，以谷歌浏览器为例，右键第一个请求，选择“Copy"，再点击"Copy as cURL"。<br>
![谷歌浏览器开发者工具操作示例](images/copy_url_with_bash.png)<br>
#### 2.2 转换为Python代码
之后，转到网站：(https://curlconverter.com/python/)
，将复制的cURL命令粘贴到网站中。将生成的Python代码（选中部分）复制到脚本中。<br>
![curlconverter.com操作示例](images/curl_converter.png)<br>
#### 2.3 修改jjfz,py脚本Cookies
将刚刚复制的cookies代码替换到脚本的main函数中的cookies中，即图中红框里的大括号部分。<br>
![修改cookies示例](images/code.png)<br>
#### 2.4 运行jjfz.py脚本，坐等完成
在pycharm或者其他python编辑器中运行jjfz.py脚本的get_lessons_and_save函数，也可以在命令行中运行，坐等完成。

## 主要功能
### 1. 视频刷课
**jjfz.py** 运行 get_lessons_and_save() 方法，即可获取所有课程的信息。
### 2. 章节测试刷题
**exam.py** 运行 finish_all_lesson_exams() 方法，即可完成所有章节测试。
### 3. 综合提升考试刷题
**exam.py** 运行 finish_all_exams() 方法，即可完成所有综合提升考试。
### 4. 获取系统题库
建议先运行十次以上自动刷题，以在系统上留下考试记录。脚本会通过查询考试记录，获取所有考题，然后去重、按拼音排序、分类（单选、多选、判断、填空）。<br>
主要提供两种方式获取题库：
1. 在考试记录样本量很少的情况下，**jjfz.py** 运行get_exam_list()方法获取综合提升考试题目，运行get_lesson_exam_list()获取章节测试题目，
之后运行collect_unique_questions方法，处理所有题目，并设置save参数为true，使其保存文件到本地。
2. 在考试记录样本量足够的情况下，**exam.py** 运行finish_many_exams()开启多轮综合提升考试刷题，运行finish_many_lesson_exams()开启
多轮章节测试刷题， 脚本会从本地导入已有考题，再将新获取的错题（错题即为题库中没有的数据）添加到本地题库中。

## 运行效果
### 1. 视频刷课
截至到测试时间，脚本顺利运行，并完成所有课程的观看任务。<br>
![运行效果](images/result.png)
### 2. 章节测试刷题
截至到测试时间，脚本顺利运行，并完成所有章节测试。<br>
![运行效果](images/chapter_test.png)

## 注意事项
1. 请确保自己的积极分子账号已登录，且Cookies值已正确复制到脚本中。
2. 脚本运行完成后，会在控制台输出完成信息。
3. 使用刷题功能时，由于做题时系统给出的题目中空格等符号的数量可能与本地题库不一致，导致判断错题的逻辑错误，但是会保证你能得到不错的分数。
4. **本项目仅供技术学习交流,为此引出的任何与技术无关的问题与作者本人无关**
