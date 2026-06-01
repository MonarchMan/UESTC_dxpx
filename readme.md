# 电子科技大学（UESTC）积极分子培训脚本
## All you need is a Python script!
2025.11.21 经过测试，脚本顺利运行，并完成所有课程的观看任务。后续会考虑加入发展对象相关的支持。<br>
2026.05.20 对本期积极分子课程再次进行测试，顺利完成所有任务。<br>
2026.06.01 增加发展对象的视频课程、考试支持，并完成测试。<br>

## 使用方法
### 1. 安装依赖
通常情况下编译器已经预装了所需依赖，如`requests`、`pandas`、`pypinyin`等。如果未安装，请根据提示安装。

### 2. 修改 Cookies
#### 2.1 复制请求
登录自己的积极分子账号后，打开浏览器开发者工具（如Chrome的F12或Edge的F12），切换到Network（网络）标签页。
刷新页面，找到第一个请求，复制其Cookies值。<br>
如果你不会操作，以谷歌浏览器为例，右键第一个请求，选择“Copy"，再点击"Copy as cURL"。<br>
![谷歌浏览器开发者工具操作示例](images/copy_url_with_bash.png)<br>
#### 2.2 转换为Python代码
之后，转到网站：(https://curlconverter.com/python/)
，将复制的cURL命令粘贴到网站中。将生成的Python代码（选中部分）复制到脚本中。<br>
![curlconverter.com操作示例](images/curl_converter.png)<br>
#### 2.3 修改脚本 Cookies
将刚刚复制的 cookies 代码替换到对应脚本的 `cookies` 中。积极分子修改 `dxpx/jjfz/jjfz.py`、`dxpx/jjfz/exam.py`，发展对象修改 `dxpx/fzdx/fzdx.py`、`dxpx/fzdx/exam.py`。<br>
![修改cookies示例](images/code.png)<br>
#### 2.4 运行脚本
所有命令都建议在项目根目录运行，也就是本 `readme.md` 所在目录。

### 3. 积极分子（jjfz）
#### 3.1 初始化课程信息
获取课程信息并保存到默认目录：
```bash
python dxpx\jjfz\jjfz.py --init
```

指定课程信息保存目录：
```bash
python dxpx\jjfz\jjfz.py --init --output-dir dxpx/jjfz/temp
```

#### 3.2 更新本地题库
从已完成的综合考试和章节测试记录中抓取题目，去重后更新本地题库：
```bash
python dxpx\jjfz\jjfz.py --update
```

#### 3.3 自动完成考试
综合提升考试，默认模式为 `end`：
```bash
python dxpx\jjfz\exam.py --mode end --echos 30
```

章节测试：
```bash
python dxpx\jjfz\exam.py --mode lesson --echos 30
```

`--echos` 表示循环执行次数，可根据需要调整。

### 4. 发展对象（fzdx）
#### 4.1 初始化课程信息
获取课程信息并保存到默认目录：
```bash
python dxpx\fzdx\fzdx.py --init
```

指定课程信息保存目录：
```bash
python dxpx\fzdx\fzdx.py --init --output-dir dxpx/fzdx/temp
```

#### 4.2 更新本地题库
从已完成的考试记录中抓取题目，去重后更新本地题库：
```bash
python dxpx\fzdx\fzdx.py --update
```

#### 4.3 自动完成考试
```bash
python dxpx\fzdx\exam.py --echos 10
```

`--echos` 表示循环执行次数，可根据需要调整。

## 主要功能
### 1. 视频刷课
运行 `jjfz.py` 或 `fzdx.py` 的 `--init`，即可获取所有课程的信息，并记录课程资源参数。

### 2. 章节测试刷题
积极分子脚本支持章节测试，运行：
```bash
python dxpx\jjfz\exam.py --mode lesson --echos 30
```

### 3. 综合考试刷题
积极分子综合考试：
```bash
python dxpx\jjfz\exam.py --mode end --echos 30
```

发展对象考试：
```bash
python dxpx\fzdx\exam.py --echos 10
```

### 4. 获取系统题库
建议先运行十次以上自动刷题，以在系统上留下考试记录。脚本会通过查询考试记录，获取所有考题，然后去重、按拼音排序、分类（单选、多选、判断、填空）。<br>
更新题库可以直接运行：<br>
**积极分子：**
```bash
python dxpx\jjfz\jjfz.py --update
```
**发展对象：**
```bash
python dxpx\fzdx\fzdx.py --update
```

## 运行效果
### 1. 视频刷课
截至到测试时间，脚本顺利运行，并完成所有课程的观看任务。<br>
![运行效果](images/result.png)
### 2. 章节测试刷题
截至到测试时间，脚本顺利运行，并完成所有章节测试。<br>
![运行效果](images/chapter_test.png)

## 其他脚本
[研究生英语-学堂在线刷题脚本](mooc/english.py)，题目和答案见[研究生英语-学堂在线题库](doc/mooc/english.txt)。

## 注意事项
1. 请确保自己的积极分子账号已登录，且Cookies值已正确复制到脚本中。
2. 脚本运行完成后，会在控制台输出完成信息。
3. 使用刷题功能时，由于做题时系统给出的题目中空格等符号的数量可能与本地题库不一致，导致判断错题的逻辑错误，但是会保证你能得到不错的分数。
4. **本项目仅供技术学习交流,为此引出的任何与技术无关的问题与作者本人无关**
