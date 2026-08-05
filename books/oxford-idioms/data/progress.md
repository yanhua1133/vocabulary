# 牛津习语词典 进度

更新：2026-08-05（成品已交付）

## 结果在哪看
- **`out/牛津习语词典.md`** ← 成品，四列：**单词 / 习语 / 中文解释 / 例句**
  2576 个单词、7274 条习语，释义和例句 100% 经过校对重写
  （原书 3569 个关键词里有 960 个只有交叉引用、本身不带条目）
- `out/词条清单.md` ← 只有单词和习语的骨架清单，方便快速翻检
- `data/idioms.json` ← 机器可读的结构（含从扫描件抽出的原书释义和例句）
- `data/cache.json` ← 子 agent 校对/重写后的 7609 条 `{i, cn, e}`
- `data/ocr/pNNN.json` ← 630 页整页 OCR，带每行 bbox，所有后续步骤都从这里取数
- 校验：`../../.venv/bin/python scripts/08_audit.py`（当前 38 条问题 / 7274，0.5%）
  校验脚本直接复用 `07_render.py::final_rows`，查的就是成品本身而不是中间数据

## 原书情况
- 630 页，260 MB，FreePic2Pdf 生成的**纯扫描件**：每页一张 JPEG，没有文字层，只能 OCR
  （跟 GRE3000 不同，那本是文字层被字形混淆，能无损解码）。
- **原书 PDF 不进版本库**（超 GitHub 单文件 100 MB 上限），只在本地，已写进 `.gitignore`。
- PDF 第 18 页 = 书内页码 1，正文到 PDF 第 621 页 = 书内 604 页。
- 双栏，每栏三类行：关键词（大字号 + 音标）、习语条目（加粗 + 重音符号 ˈ/ˌ）、
  交叉引用（`• easy → (as) easy as ABC`）。

## 管线
```
cd books/oxford-idioms
../../.venv/bin/python scripts/01_ocr.py       # 整页 OCR → data/ocr/
../../.venv/bin/python scripts/03_gapfill.py   # 补回 Vision 漏掉的整行（补了 1834 行）
../../.venv/bin/python scripts/02_entries.py   # 抽词条骨架 → data/entries.json
../../.venv/bin/python scripts/04_expand.py    # 补原书释义/例句 → data/idioms.json
../../.venv/bin/python scripts/05_batches.py   # 切批次 → work/batches/
#   派 20 个子 agent，每个 7 批，按 prompts/INSTRUCTIONS.md 写 *.out.json
../../.venv/bin/python scripts/06_merge.py     # 校验并入 → data/cache.json
../../.venv/bin/python scripts/07_render.py    # 渲染成品 → out/牛津习语词典.md
../../.venv/bin/python scripts/08_audit.py     # 确定性校验
```

## 踩过的坑（都写进脚本注释了，别踩第二遍）
1. **OCR 用 macOS Vision，`language_preference` 第一位必须是 `zh-Hans`**，
   写成 `en-US` 在前时中文整段丢失只吐乱码。220dpi 够用，300dpi 不会更好。
   机器上的 tesseract 只装了 eng，不能用。
2. **Vision 会静默丢整行**，丢的多半正好是加粗的习语条目行。靠「相邻行 y 间距 >
   正常行距 1.75 倍」检测，把空带裁出来用 `en-US` 重 OCR，全书补回 1834 行。
3. **Vision 还会把一行切成好几块**（`used` / `when you` / `are emphasizing…`），
   y 只差千分之几。必须按行合并，否则按 y 排序会把语序打乱、正文没法用。
   合并时要加两个保护：碎片必须横向不重叠；大字号的关键词片段绝不并进上一行——
   少了这两条会一口气吞掉 160 多个关键词。
4. **字重判据行不通**：Vision 的行 bbox 不够准，量笔画宽度时粗体反而比正文细。
   改用版面规律（条目行只出现在关键词后或上一条收尾后）+ 重音符号 ˈ。
5. **次重音 ˌ 被认成逗号**，跟英文正文里的逗号长得一模一样，判据阶段**不能还原**
   （硬还原会把 `respect, etc.` 变成条目，多召回四千多条垃圾）；只在已确认是条目的
   文本上，还原「逗号后不留空格」的那种（`a,stiff` → `a ˌstiff`）。
6. **交叉引用**的项目符号和箭头 OCR 得五花八门，只能认「箭头前那个词紧挨着重复」
   （`hedge hedge your bets`）。放宽成「首词在后文任意位置重复」会误杀
   `the ˈbigger… the ˈbetter`、`for ˌbetter or (for) ˈworse`。
7. **关键词不能只靠字号**：Vision 的行高逐页漂移，末页 `yore` 的 h 跟正文一样。
   改成「音标斜杠齐全的一律认，其余才看字号」，另外结尾斜杠常被吃掉（`travel/travl`）。
8. **别用「以 the 开头就不是条目」这种排除项**——`the curtain comes down on sth`
   就是正经条目。只挡 that/which/and/but 这类连词关系词。
9. 关键词的 OCR 错字用 wordfreq 兜底纠正（`iuck`→`luck`、`sood`→`good`、
   `CUstomer`→`customer`），全大写的要留住真缩写（ABC、AWOL）。

## 抽样复核记录（派独立 agent 看扫描图逐条对）
- 第一轮（p500、p550）：召回 93.3%，精度 87.5% —— 暴露出条目断行截断、交叉引用漏过滤等问题。
- 修完管线后（p100、p300）：这两页的条目**全部抽到**，关键词 17/17 全对。

## 渲染层的三道收尾（为什么不回头改 02）
`data/cache.json` 是按 `data/idioms.json` 的**序号**存的，上游一改序号就全错位、
7600 条得重跑。所以下面三件事都放在 `07_render.py` 做：
1. **拼回断成两条的习语**：条目在栏底断行、断点又不在括号里时 02 接不上
   （`…half a dozen of the` + `ˈother (saying)`）。判据是「前一条以 the/of/and 这类
   虚词收尾 + 后一条短且以小写或重音符号起头」，拼回 36 条。
   注意别把 in/on/out/up 算作虚词，`keep your ˈhand in` 本身就是完整条目。
2. **同一个关键词下的重复条目**只留一条（跨栏、跨页续行造成的），去掉 104 条。
3. **音标残片**（`ˈa:rmtʃer; a:rmˈtʃer/`）直接扔掉。
4. **剔除模型猜出来的条目** 198 条。有个子 agent 报告说，它遇到例句碎片、词源框、
   乱码时会按关键词猜一条该词条下真实存在的习语填上（把 `In this sense, ˈcheese'
   comes from the Urdu` 填成 `a ˌbig ˈwheel (informal)`）。猜得对不对无从验证、
   来源行本身也不是条目，一律剔除。判据是原始行与模型给的条目**有没有实质公共内容**：
   补全（`ˈjudgment)` → `against your better ˈjudgement…`）和从例句还原
   （`the biter bit — she'd tried…` → `the biter ˈbit`）公共子串都很长，这些留着。

## 已知缺口
- 5 条关键词的音标残片被当成了条目（`ˈa:rmtʃer; a:rmˈtʃer/`），渲染时已按形状过滤掉
  一部分，剩下的靠 `08_audit.py` 报出来。
- 20 条例句里没直接出现习语的实词，多数是模型换了近义说法。
- 音标整体没做：中文优先的 OCR 把 IPA 认得很差，成品里干脆不列。要补的话，
  跟补漏行同一个办法——把关键词行单独裁出来用 `en-US` 重 OCR。
