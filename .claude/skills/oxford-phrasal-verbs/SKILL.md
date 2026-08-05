---
name: oxford-phrasal-verbs
description: |
  驱动《牛津短语动词词典》重排：572 页纯扫描件，整页 OCR → 抽词条和短语动词 → 富集 → 渲染 Markdown 和 PDF。
  触发场景：用户输入 /oxford-phrasal-verbs，或提到牛津短语动词词典、短语动词、phrasal verbs、
  oxford-phrasal-verbs 目录下的文件。
  不要触发：GRE3000、牛津习语词典、牛津搭配词典（各有各的 skill）。
---

# 牛津短语动词词典重排

**工作目录：`oxford-phrasal-verbs/`**，命令先 `cd oxford-phrasal-verbs`，
解释器用 `../.venv/bin/python`。

**还没开工**。目录下只有原书 `牛津短语动词词典.pdf`（572 页、211 MB，不入库）。

## 这本书的情况

- **纯扫描件**（FreePic2Pdf 生成，每页一张图、零文字层），**跟牛津习语词典是同一套制作工具、
  同样的版式路数**，四本书里跟它最像的就是这本，管线可复用度最高。
- 572 页，规模跟习语词典（630 页）接近，并发数可以照搬。
- 结构上：词头是动词，下面挂 `verb + particle` 的短语动词条目，每条有释义和例句——
  跟习语词典「词头 + 习语条目」的两层结构几乎一一对应，
  `02_entries.py` / `04_expand.py` 的判据大概率只要小改。

## 起步方式

**直接拷 `oxford-idioms/scripts/` 过来改**，先跑通 OCR 和抽取，
拿两三页扫描图派独立 agent 逐条核对召回率和精度，再往下走。

动手前必读 `oxford-idioms/data/progress.md`，那里是这套管线的全部踩坑记录。
最要紧的几条：

1. OCR 用 macOS Vision，`language_preference` 第一位**必须**是 `zh-Hans`。220dpi 够用。
2. Vision 会**静默丢整行**（丢的多半正是加粗的条目行），要靠行距异常检测补回。
3. Vision 会把一行**切成几块**，必须按行合并，且要防着把词头行并进上一行。
4. 判据宁窄勿宽：每加一条过滤都先量误伤，宽判据清得多但会误删正经条目。
5. 子 agent 遇到残片会自己**猜**一条填上，必须在渲染层用「与原始行有无实质公共内容」剔除。
6. 缓存按上游序号存，**清洗一律做在渲染层**。
7. 例句**优先用原书的**，只有原书那句被 OCR 毁了才退回自拟，并标「（自拟）」。
8. 排 PDF：playwright 自带 Chromium；量行数要 `viewport` 等于版心宽 + `emulate_media("print")`；
   行数用 Range 行盒实测；缩完字号要回弹，别缩过头浪费宽度；边框宽度 Chrome 改不动，
   要粗线得用背景渐变画。

## 工作纪律

跟 `oxford-idioms` 一致：每轮产出能打开的文件；子 agent 的报告逐条核；
过滤判据先量化误伤再上；排版改完必须看图；每块结束更新 `data/progress.md`；
回话只给数字和路径，全中文。
