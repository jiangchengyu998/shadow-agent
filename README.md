# shadow-agent

shadow-agent 是一个本地优先的英语 shadowing 学习包生成工具。

它会从一段音频或视频中转写英文文本，挑选适合跟读的句子，切成单句音频，并生成一个包含原速音频、0.8x 慢速音频、转写文本和学习说明的 study pack。

## 当前 MVP 能做什么

1. 接收本地音频或视频文件，例如 `input/emails.mp3`。
2. 使用 `faster-whisper` 生成带时间戳的英文转写。
3. 根据 `targets.txt` 手动目标句做模糊匹配，或用简单规则自动选择句子。
4. 使用 `ffmpeg`/`pydub` 把选中的句子切成独立 MP3。
5. 生成 `README_学习说明.md` 和 `shadow_pack.zip`。

## 环境要求

- macOS
- Python 3.11 或 3.12
- ffmpeg

建议使用 Python 3.11。`faster-whisper` 的底层依赖在太新的 Python 版本上可能没有合适的预编译包。

## 安装

先安装 ffmpeg：

```bash
brew install ffmpeg
```

创建虚拟环境：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python --version
```

安装 Python 依赖：

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

如果你在国内网络下遇到 `Failed to resolve 'pypi.org'` 或下载很慢，可以使用清华镜像：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

也可以把镜像设置成默认源：

```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

## 快速运行

把音频文件放到 `input/` 目录，例如：

```text
input/emails.mp3
```

运行：

```bash
python -m shadow_agent.main input/emails.mp3
```

运行过程中会看到类似进度：

```text
[1/4] Transcribing audio...
[2/4] Selecting shadowing sentences...
[3/4] Clipping audio...
[4/4] Building study pack...
Done: output/shadow_pack.zip
```

## 手动指定想练的句子

可以创建一个 `targets.txt`：

```text
Everything with email depends on the situation.
A really nice way to do it is to make the next step clear.
```

一行就是一个 target。 如果你希望多个句子被剪成同一个音频片段，就把它们写在同一行：

```text
Everything with email depends on the situation. A really nice way to do it is to make the next step clear.
```

然后运行：

```bash
python -m shadow_agent.main input/emails.mp3 --targets targets.txt
```

程序会把 `targets.txt` 里的每一行和转写文本做 fuzzy matching。 如果一行 target 对应连续的多个转写片段，程序会把这些片段合并成一个剪辑范围，并把匹配结果写入：

```text
output/selected_segments.json
```

如果匹配不到，可以降低阈值：

```bash
python -m shadow_agent.main input/emails.mp3 --targets targets.txt --min-score 60
```

## 输出文件

默认输出到 `output/`：

```text
output/
├── clips/
│   ├── 01_xxx.mp3
│   └── 02_xxx.mp3
├── clips_0.8x/
│   ├── 01_xxx_0.8x.mp3
│   └── 02_xxx_0.8x.mp3
├── transcript.json
├── selected_segments.json
├── clips.json
├── README_学习说明.md
└── shadow_pack.zip
```

如果 `output/` 里已经有文件，程序会创建时间戳目录，例如：

```text
output/run_20260701_143000/
```

这样不会覆盖之前生成的学习包。

## 常见问题

### pip 安装时报 `Failed to resolve 'pypi.org'`

这是网络或 DNS 无法访问 PyPI，不是包名写错。可以换国内镜像：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### faster-whisper 安装失败

先确认 Python 版本：

```bash
python --version
```

推荐使用 Python 3.11：

```bash
brew install python@3.11
rm -rf .venv
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 提示找不到 ffmpeg

安装 ffmpeg：

```bash
brew install ffmpeg
```

然后确认：

```bash
ffmpeg -version
```

### 没有匹配到目标句

可以尝试：

- 检查 `targets.txt` 里的句子是否和音频内容接近。
- 降低 `--min-score`，例如 `--min-score 60`。
- 先查看 `output/transcript.json`，复制其中的句子到 `targets.txt`。

## 项目结构

```text
shadow-agent/
├── input/
├── output/
├── shadow_agent/
│   ├── main.py
│   ├── transcribe.py
│   ├── selector.py
│   ├── clipper.py
│   ├── packer.py
│   └── utils.py
├── requirements.txt
└── README.md
```

## 下一步方向

- 优化自动选句规则。
- 为每个句子生成中文翻译、表达讲解和发音提示。
- 增加可复用的测试样例。
- 后续再考虑 LLM-based sentence scoring。
