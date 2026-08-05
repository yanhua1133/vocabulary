---
name: oxford-idioms
description: |
  驱动《牛津习语词典》重排：整页 OCR → 抽词条 → 补释义例句 → 打常用度/口语度 → 渲染 Markdown 和 PDF。
  触发场景：用户输入 /oxford-idioms，或提到牛津习语词典、idioms.json、习语表、
  习语的中文解释/例句/常用度、oxford-idioms 目录下的文件。
  不要触发：GRE3000、牛津搭配词典、牛津短语动词词典（各有各的 skill）。
---

# 牛津习语词典重排

**工作目录：`oxford-idioms/`**，命令一律先 `cd oxford-idioms`，解释器用 `../.venv/bin/python`。

**已完工**。成品 `牛津习语词典 重排版.pdf`（书目录顶层，241 页）+ `out/牛津习语词典.md`，
6956 条习语，四列：习语 / 中文解释 / 常用·口语 / 例句。

**动手前先读 `data/progress.md`**——那里记着这本书全部的踩坑记录（OCR 参数、抽取判据、
渲染层的九道收尾、PDF 版式约束），每一条都是真金白银试出来的，别重蹈覆辙。

## 命令

| 命令 | 我要做的事 |
|---|---|
| `/oxford-idioms status` | 读 `data/progress.md` 打印，再补一句下一步。到此为止。 |
| `/oxford-idioms verify` | 跑 `scripts/08_audit.py`，只报数字。 |
| `/oxford-idioms render` | 跑 `07_render.py` 重渲染 Markdown 成品。 |
| `/oxford-idioms pdf` | 跑 `13_pdf.py` 重排 PDF（`--sample` 只排前 200 条看版式）。 |
| `/oxford-idioms fix "<抱怨>"` | 按用户指出的问题修，重渲染重排，把改好的行贴出来。 |

## 管线

```
cd oxford-idioms
../.venv/bin/python scripts/01_ocr.py       # 整页 OCR → data/ocr/
../.venv/bin/python scripts/03_gapfill.py   # 补回 Vision 漏掉的整行
../.venv/bin/python scripts/02_entries.py   # 抽词条骨架 → data/entries.json
../.venv/bin/python scripts/04_expand.py    # 补原书释义/例句 → data/idioms.json
../.venv/bin/python scripts/05_batches.py   # 切批次 → work/batches/
#   派 20 个子 agent，按 prompts/INSTRUCTIONS.md 写 *.out.json
../.venv/bin/python scripts/06_merge.py     # 校验并入 → data/cache.json
../.venv/bin/python scripts/10_clean_ex.py  # 清理原书例句 → data/examples.json
../.venv/bin/python scripts/11_score_batches.py   # 打分批次 → work/scores/
#   派 10 个子 agent，按 prompts/INSTRUCTIONS_SCORE.md 打分
../.venv/bin/python scripts/12_merge_scores.py    # 并入 → data/scores.json
../.venv/bin/python scripts/09_lost.py      # 捞回被挤掉的条目，再派 1 个 agent 甄别
../.venv/bin/python scripts/07_render.py    # 渲染成品
../.venv/bin/python scripts/08_audit.py     # 确定性校验
../.venv/bin/python scripts/13_pdf.py       # 排 PDF
```

**改动只往渲染层加**：`data/cache.json` 按 `data/idioms.json` 的序号存，
上游一改序号就全错位、7000 条得重跑。所以去重、拼断行、剔残片、改挂关键词
全都做在 `07_render.py` 里。

## 工作纪律

1. **每轮都要产出能打开的文件**，打不开就别做这件事。
2. **子 agent 的报告要逐条核**——它们带出的缺陷比产出的数据还值钱，
   这本书十类系统性问题全是这么发现的。
3. **任何过滤判据都要先量化误伤**再上。宽判据看着清得多，实际会误删正经条目。
4. **排版改完必须看图**，不能只看脚本报的数字（`实测超行 0` 不等于版面没问题）。
5. 一个工作块结束就更新 `data/progress.md`。
6. 回话只给数字和文件路径，不复述过程。全部用中文。
