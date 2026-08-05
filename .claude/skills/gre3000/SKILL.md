---
name: gre3000
description: |
  驱动 GRE3000.pdf 单词书重排：解码原书 → 生成 data/book.json → 富集字段 → 渲染 out/ 下的 Markdown 词表。
  触发场景：用户输入 /gre3000，或提到 GRE3000.pdf、book.json、单词书/词表整理、List/Unit 表格输出、
  音标/近义词/反义词列、常用度/口语度星级。
  不要触发：与本书无关的 PDF、OCR 或词汇任务。
---

# GRE3000 词表重排

**工作目录：`gre3000/`**（仓库根下每本书一个目录，另外只有 `.venv/` 和 `.claude/`）。
下文所有相对路径都相对它，命令一律先 `cd gre3000`，解释器用 `../.venv/bin/python`。

原书结构：31 个 List × 10 个 Unit × 10 个词头（约 2970 词条；连同近义词/反义词共约 11600 个不同单词）。

## 命令

| 命令 | 我要做的事 |
|---|---|
| `/gre3000 status` | 读 `data/progress.md` 打印出来，再补一句下一步是什么。到此为止。 |
| `/gre3000 build <N>` | 按下面流程跑完 List N，然后给出 `out/List<N>.md` 路径 + 5 行预览。 |
| `/gre3000 build all` | 对 `data/todo_llm.json` 里还有缺口的 List 依次执行同样流程。 |
| `/gre3000 verify` | 跑 `scripts/15_audit.py`，只报数字。 |
| `/gre3000 pdf [N]` | 跑 `scripts/18_pdf.py [N]` → `pdf/List<N>.pdf`（playwright 打印，16 开 185×260mm 竖版）。 |
| `/gre3000 pdf merge` | 跑 `scripts/18_pdf.py --merge` → `GRE3000 重排版.pdf`，带 List/Unit 两级书签。 |
| `/gre3000 fix "<抱怨>"` | 按用户指出的问题修，重渲染那个 List，把改好的行贴出来。 |

### `build <N>` 的执行步骤

```
cd gre3000
../.venv/bin/python scripts/13_llm_batches.py <N> 45   # 生成 work/batches/L<N>_*.json
# 在同一条消息里并行派发约 6 个 general-purpose 子 agent，每个负责 3 个批次文件
../.venv/bin/python scripts/14_merge_cache.py L<N>_    # 校验后并入 data/enrich_cache.json
../.venv/bin/python scripts/11_enrich.py
../.venv/bin/python scripts/12_render.py <N>
```

给子 agent 的任务说明：读取批次文件（`{word, pos, cn, related_to, need}` 的 JSON 数组），
写出同名的 `*.out.json`，内容是「单词原样字符串 → `{cn, pos, phrase, example, spoken}`」的 JSON 对象。
字段要求：

- `cn`：简体中文释义，不超过 20 字；`related_to` 非空时给出与该词相关的那个义项。
- `pos`：只用 `n. v. vt. vi. adj. adv. prep. conj. pron. num.`，多个用 `/` 连接。
- `phrase`：含该词的常用英文搭配，2-5 个单词。
- `example`：一个 6-18 词的自然英文例句（必须含该词或其屈折形式），后接两个空格，再接中文翻译。
- `spoken`：0-5 的整数，表示该词在日常口语中出现的可能性。
- 只输出裸 JSON，不要代码围栏，不许漏词。

## 工作纪律（用户明确要求）

1. **每一轮都必须推进 `out/` 里的成品文件**。如果这一轮结束用户打不开任何新东西，就别做这件事。
2. **不要追求 100% 识别精度**。正文命中率 96% 就够用；只有当渲染出来的行明显是乱码时才回头修字形。
3. **例句不必忠于原书**。原书例句乱码或不通顺，直接换成自己写的干净句子；短语同理。
4. **不画蛇添足**：不加额外工具、额外校验图、额外抽象层。
5. **一个工作块结束就更新 `data/progress.md` 和 memory。**
6. **回话只给数字和文件路径**，不要复述内部过程。
7. **所有产出物（skill、文档、进度、说明）一律用中文。**

## 管线文件

- `scripts/glyphs.py` + `data/labels_*.json`：解码原书被混淆的 CFF 文字层（**永远不要**对页面截图做 OCR）。
  `scripts/decode.py <页号>` 可以打印单页解码结果，用来定位某一行的问题。
- `scripts/01..06`：字形清点、tesseract 先验、token 提取、字典约束求解、人工标注。
  已经跑完，只在解码本身出问题时重跑（`03` 会重建 `data/tokens.json`）。
- `scripts/10_parse_book.py` → `data/book.json`（List → Unit → 词条：词头、音标、词性、中文释义、例句、近义词、反义词、派生词）。
- `scripts/11_enrich.py` → `data/words.json`：wordfreq 词频算常用★、Zipf<1.5 打罕见删除线标记、
  构词特征算口语★、cmudict 给近反义词补音标；模型字段从 `data/enrich_cache.json` 读。
- `scripts/12_render.py [N...]` → `out/List<N>.md`。
- `scripts/15_audit.py` → 全量确定性校验（拼写/音标/例句/短语/词性/释义/罕见标记），必须保持 0 问题。
- `scripts/17_review_batches.py` + `prompts/INSTRUCTIONS_REVIEW.md` → 全量语义复核批次。
- `scripts/18_pdf.py [N...]` → `pdf/List<N>.pdf`。
- 
## 输出格式

每个 Unit 一张表，7 列：**单词 / 音标 / 常用 / 口语 / 词性 / 中文释义 / 常用短语**。
例句**不占列**，而是紧跟在该词下面、跨整行的一格（`<td colspan="7">例 ...</td>`）——
Markdown 表格不能合并单元格，所以整张表用内嵌 HTML 写，GitHub / VSCode / Typora 都能正常渲染。


- 词头加粗；近义词行前缀 `↳近`，反义词行前缀 `↳反`。
- **只有单词列**被 `~~...~~` 包住 = 极其罕见（wordfreq Zipf < 1.5），其余列正常显示。
- 词性写中文全称（形容词、及物动词、不及物动词…），不写 adj./vt.。
- 常用短语格内两行：英文搭配 + `<br>` + 中文。
- 每个词的「词条行 + 例句行」包在同一个 `<tbody>` 里，PDF 打印时 `tbody { break-inside: avoid }`
  保证整组不被分页切开。
- PDF 版（`18_pdf.py` 里的 `drop_halfstar`）会略去常用度只有 `☆` 的近/反义词行，词头保留；
  Markdown 版保留全部。
- **星级：`★` = 一颗，`☆` = 半颗**。不补尾部空星。最低分就是半颗星 `☆`，没有零分。
  例：`☆`(0.5) / `★`(1) / `★★☆`(2.5) / `★★★★★`(5)。
  常用度由 Zipf 词频线性映射到 0.5-5 的半星刻度；口语度取模型判断。
