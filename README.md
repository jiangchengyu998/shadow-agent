# shadow-agent

shadow-agent 是一个本地优先的英语 shadowing 学习包生成工具。

它会从一段音频或视频中转写英文文本，挑选适合跟读的句子，切成单句音频，并生成一个包含原速音频、0.8x 慢速音频、转写文本和学习说明的 study pack。

## 当前 MVP 能做什么

1. 接收本地音频或视频文件，例如 `input/emails.mp3`。
2. 使用 `faster-whisper` 生成带时间戳的英文转写。
3. 根据 `targets.txt` 手动目标句做模糊匹配，或用简单规则自动选择句子。
4. 使用 `ffmpeg`/`pydub` 把选中的句子切成独立 MP3。
5. 使用 OpenAI API 为每句生成中文翻译、重点表达和发音提示，保存到 `README_学习说明.md` 和 `shadow_pack.zip`。

音频转写和切片在本地完成；学习讲解仅将选中句子的英文文本发送给 OpenAI，按 API 使用量计费。运行前需在当前终端环境配置 `OPENAI_API_KEY`（不会自动读取 `.env` 文件）。只做本地音频处理可加 `--skip-study-notes`，以后再补讲解。

原速和 0.8x 慢速片段的开头、结尾都会各添加 1 秒静音，方便准备和跟读。静音不包含额外的原音频内容；当前切片在句首前、句尾后各保留 0.1 秒的原音频缓冲。若句首缺字或句尾混入其他内容，需要检查转写时间戳，添加静音不会修正时间边界。此设置对重新生成的学习包生效。

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

新转写会保存逐词时间戳，匹配时可以从转写片段内部开始、结束，减少句首漏词和句尾带入下一句。匹配分数同时考虑整体文本相似度、长度和首尾词语；分数不是准确率。未达到阈值的目标会显示警告并跳过。

旧 `transcript.json` 如果没有 `words`，只能按整段边界匹配。需要重新执行转写命令才能获得逐词时间戳；`--selected-segments` 只使用已有时间，不会修正旧边界。逐词时间戳也可能有误差，必要时仍需试听微调。

如果匹配不到，可以降低阈值：

```bash
python -m shadow_agent.main input/emails.mp3 --targets targets.txt --min-score 60
```

## 输出文件

### 自动生成学习讲解

正常运行时，会为每个选中句子补全三个字段：

- 中文翻译：整句的自然中文译文。
- Key expressions：句中的实用表达、中文含义和用法，以及英文例句。
- Pronunciation notes：针对原句的意群划分、重音和常见功能词弱读提示。

发音提示基于文本生成，是练习建议；请以原音频的实际发音、停顿和语调为准。

默认讲解模型为 `gpt-4.1`，可以用 `--notes-model` 单独指定，不影响转写用的 `--model`：

```bash
python -m shadow_agent.main input/emails.mp3 --targets targets.txt --notes-model gpt-4.1
```

接口采用 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) 返回结构化内容，并在写入前检查字段是否完整。

若要跳过 API 调用：

```bash
python -m shadow_agent.main input/emails.mp3 --skip-study-notes
```

已有学习包可以直接补讲解，无需原始音频、转写或重新切片。例如：

```bash
python -m shadow_agent.study_notes output/261122-generations
```

请替换为实际的输出目录。该目录需包含 `selected_segments.json`、`clips.json` 和音频文件。命令会更新这个目录中的 `README_学习说明.md` 和 `shadow_pack.zip`。

讲解逐句保存到同目录的 `study_notes.json`。网络或 API 出错时，已生成的讲解、音频和转写会保留；重新执行上述补全命令会继续处理。缓存按英文原文精确匹配，调整时间戳或句子编号后仍可复用，原文改变则重新生成。

可以手动修改 `study_notes.json` 中的 `translation`（字符串）、`key_expressions` 和 `pronunciation_notes`（非空字符串列表），然后重新执行补全命令，将改动写入 README 和 ZIP。保持 `text` 与原句一致，保留 `id` 和 `model` 字段。更换 `--notes-model` 会用于尚未生成的句子；若要重新生成某句，先从 JSON 列表中删除对应记录。

### 调整时间后重新切片

编辑上次输出的 `selected_segments.json`，把 `start` 调小可以提前开始，把 `end` 调小可以提前结束，单位都是秒。然后传入原始音频和修改后的 JSON：

```bash
python -m shadow_agent.main input/emails.mp3 --selected-segments output/selected_segments.json
```

如果上次结果在 `output/run_.../`，请使用该目录下 JSON 的实际路径。此命令跳过转写和选句，重新生成原速、慢速音频、学习说明及 ZIP。已有输出会保留，新结果写入新的时间戳目录；命令最后会显示 ZIP 路径。新目录也会保存修改后的 `selected_segments.json`，并在原 JSON 同目录存在 `transcript.json` 时复制它。

句首前、句尾后各保留 0.1 秒原音频缓冲；两种速度的片段前后各加 1 秒静音。下次微调可以继续编辑原 JSON 并重复运行此命令。

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
├── study_notes.json
├── README_学习说明.md
└── shadow_pack.zip
```

使用 target 文件时，输出目录会带上文件名（不含扩展名）。例如 `--targets targets-meetings.txt` 会输出到 `output/targets-meetings/`，再次运行会创建 `output/targets-meetings_run_时间戳/`，保留之前的结果。`--output` 指定的目录也遵循此规则。

没有 target 文件时，如果 `output/` 里已经有文件，程序会创建时间戳目录，例如：

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
│   ├── study_notes.py
│   └── utils.py
├── requirements.txt
└── README.md
```

## 下一步方向

- 优化自动选句规则。
- 增加可复用的测试样例。
- 后续再考虑 LLM-based sentence scoring。
