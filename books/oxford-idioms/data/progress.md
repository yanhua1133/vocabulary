# 牛津习语词典 进度

更新：2026-08-05（成品已交付）

## 结果在哪看
- **`out/牛津习语词典.md`** ← 成品，四列：**习语 / 中文解释 / 常用·口语 / 例句**
  6957 条习语
  例句 **4749 条用原书原文**，其余原书那句被 OCR 毁了、退回自拟（标「（自拟）」）
  常用度和口语度各 0-5 分，`★` 一颗 `☆` 半颗
  （原书 3569 个关键词里有 960 个只有交叉引用、本身不带条目）
- **`pdf/牛津习语词典.pdf`** ← 打印版，256 页 / 6 MB，16 开 185×260mm 竖版，A-Z 书签 24 条
- `out/词条清单.md` ← 只有单词和习语的骨架清单，方便快速翻检
- `data/idioms.json` ← 机器可读的结构（含从扫描件抽出的原书释义和例句）
- `data/cache.json` ← 子 agent 校对/重写后的 7609 条 `{i, cn, e}`
- `data/ocr/pNNN.json` ← 630 页整页 OCR，带每行 bbox，所有后续步骤都从这里取数
- 校验：`../../.venv/bin/python scripts/08_audit.py`（当前 37 条问题 / 6957，0.5%）
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
../../.venv/bin/python scripts/10_clean_ex.py  # 清理原书例句 → data/examples.json
../../.venv/bin/python scripts/11_score_batches.py  # 打分批次 → work/scores/
#   派 10 个子 agent，按 prompts/INSTRUCTIONS_SCORE.md 打常用度/口语度
../../.venv/bin/python scripts/12_merge_scores.py   # 并入 → data/scores.json
../../.venv/bin/python scripts/09_lost.py      # 捞回被挤掉的条目 → work/lost.json
#   再派 1 个子 agent 甄别并补全，结果放 data/lost.json
../../.venv/bin/python scripts/07_render.py    # 渲染成品 → out/牛津习语词典.md
../../.venv/bin/python scripts/08_audit.py     # 确定性校验
../../.venv/bin/python scripts/13_pdf.py       # 排 PDF（--sample 只排前 200 条看版式）
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

## 抽样复核记录
**成品验收**（随机 60 条，独立 agent 凭英语知识核对）：释义错 **0**、例句错 **0**、
翻译错 **0**、习语写法错 1。唯一的系统性问题是所属单词错配 6/60，已按上面第 9 条修掉。

**抽取阶段**（派独立 agent 看扫描图逐条对）
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
3. **音标残片、例句片段、关键词行**。有个子 agent 对残片选择原样保留（另一些则做了
   还原），于是这类垃圾会直接留在成品里。三条判据都验证过没有误伤：
   没闭合的音标（含 `a:` 这种长音标记又带 `/` 或 `;`）；大写起头、超过 35 字符
   又不含重音符号的例句片段（习语哪怕大写起头也带 ˈ，如 `Bob's your ˈuncle`）；
   以连字符结尾的断词残行。整行的
   `labour (BrE) (AmE labor) /ˈleɪbə(r)/` 也是关键词不是条目，判据是剥掉音标和
   括号后只剩一两个词——`je ne sais quoi /…/`、`a ˌsine qua ˈnon /…/` 这类外来语
   条目原书就带音标，词数多，留着。
4. **剔除模型猜出来的条目** 198 条。有个子 agent 报告说，它遇到例句碎片、词源框、
   乱码时会按关键词猜一条该词条下真实存在的习语填上（把 `In this sense, ˈcheese'
   comes from the Urdu` 填成 `a ˌbig ˈwheel (informal)`）。猜得对不对无从验证、
   来源行本身也不是条目，一律剔除。判据是原始行与模型给的条目**有没有实质公共内容**：
   补全（`ˈjudgment)` → `against your better ˈjudgement…`）和从例句还原
   （`the biter bit — she'd tried…` → `the biter ˈbit`）公共子串都很长，这些留着。

5. **纠正认错的关键词** 71 个。牛津的条目一定含它所属的关键词，所以整组条目都不含
   当前关键词时就有问题：组里有形近词的是 OCR 错字（`albsence`→`absence`、
   `allive`→`alive`、`LI`→`labour`），组里每条都含同一个实词的说明关键词行被漏识别、
   条目挂到了上一个关键词底下，改挂过去。两条都不满足就不猜，交给校验报出来。

6. **合并跨词条重复** 142 条。同一条习语挂在两个关键词下——一处是原书正文，
   另一处是交叉引用行被子 agent 还原成了条目。保留原书底下**有释义正文**的那条，
   交叉引用行底下是空的。组首被删时要把单词标记交给同组下一行，否则那一组会丢标题。
   忽略括号标签后重合的也一样处理，但**只在「一条有正文、另一条没有」时才删**——
   `in the ˈair` 和 `(up) in the ˈair` 两条都有正文，是两个词条，不能合。

7. **收拢断开的后半截** 46 条。长条目被排版切成两行、两半又各自被子 agent 补成了
   条目。两个判据都必须**很窄**，宽了会误删大量正经条目：
   - 后一条以 `(AmE`、`(BrE`、`(also`、`(usually` 这类**标签**开头 → 拼回前一条。
     不能放宽成「以左括号开头」——`(up) in the ˈair`、`(not) at ˈall`、
     `(whether) by ˌaccident or deˈsign` 原书就长这样。
   - 后一条整个被前一条包住（`ˈvanishing act` ⊂ `do/perform/stage a
     disapˈpearing/ˈvanishing act`）→ 删。只比**紧邻**的那条，比整组会误删
     `be about to do sth` ⊂ `not be about to do sth` 这种两条都成立的。

8. **捞回被挤掉的条目** 10 条。原书两条习语被 OCR 挤进同一行时
   （`drive a hard ˈbargain what sb is ˈdriving at`），子 agent 只会留下一条，
   另一条整条消失。`09_lost.py` 拿原始行减去已收录的那条，剩下部分自带重音符号、
   词数像习语、全书别处又没有的，捞出来交给模型甄别（40 个候选里 12 条是真习语）。
   这些不参与全书去重——`now, ˈnow` 和已有的 `now… now…` 去掉标点后长得一样，
   但它们是两条。

9. **改挂错位的条目** 216 条。02 偶尔整行漏掉一个关键词（`all`、`iron`、`money`
   在 `data/book.json` 里根本不存在），它底下的条目就顺延挂到了前一个关键词上。
   词典按字母排序，漏掉的关键词一定落在「本组」和「下一组」之间，拿这个区间去条目
   文本里筛基本能唯一确定：`have many/several irons in the fire` 挂在 invitation 下、
   下一组是 ironing，区间里只有 `irons` 对得上。另有一类是边界错位一格
   （`have ˌmoney to ˈburn` 排在 moments 组末尾，而下一组正是 money），直接划过去。
   条目里找不到所属单词的比例从 11.3% 降到 2.5%。
   注意这里的虚词表要比 `FUNC` 窄——`all`、`that`、`there`、`one` 本身就是关键词。

## 去重时留哪一条：一律留「原书底下有正文的」
三处去重（组内重复、收拢后半截、忽略括号的重合）都按这条规矩，缺一处就会连环删。
`a ˌbird in the ˈhand is worth two in the ˈbush` 被 OCR 拆成两行、两半都被子 agent
补成了整条，前一半没正文、后一半有：组内去重先入为主留下前一半，后面的去重又因为
它没正文把它删掉，整条习语就只剩交叉引用来的、连重音符号都没有的劣质版本。

## 常用度 / 口语度
两个 0-5 分，`★` 一颗、`☆` 半颗。跟 GRE3000 不同，这里**没法用 wordfreq 客观算**——
wordfreq 只有单词频率，习语是多词组合查不到，只能交给模型判断。
评分标准写死在 `prompts/INSTRUCTIONS_SCORE.md` 里（含分档说明和例子、以及
「标了 (old-fashioned) 的常用度一律 ≤2」「标了 (spoken)(informal) 的口语度一般 ≥4」
这类硬规则），让不同批次之间的尺度尽量一致。
对应关系用**条目文本的归一化形式**做 key，不用行号——成品的行会随去重、改挂变动。

## 用打分兜最后一遍残片
打分的子 agent 顺手提供了一个很好的信号：被误切进来的释义正文和例句碎片，
常用度一律被打到最低。光看分会误杀真·生僻习语（`like ˈbilly-o`、
`the/a ˌcurate's ˈegg` 都是 0 分的正经条目），所以再叠两个条件——**没有重音符号**、
**没有语域标签**（带 `(BrE)`、`(informal)` 的一定是正经条目，哪怕冷僻到没人用）。
三条同时满足的 41 条里只有 `now… now…` 一条是错杀，其余全是
`a person who does what they want`、`(Some people find the phrase thank God
offensive.)`、`ORIGIN` 这类正文碎片。

## 例句从哪来
- **原书优先**。第一版成品的例句全是模型自拟的——我沿用了 GRE3000「例句一律自写」
  的做法，但那是那本书单独确认过的，这本没有。原书例句是词典的权威内容，抽出来
  5257 条，`10_clean_ex.py` 清理后 4374 条判定可用，最终回填 4308 条。
- 清理修的是固定套路：`T've`→`I've`、`Im`→`I'm`、`WaS`→`was` 这类大小写和撇号问题、
  中文里插进的空格。判定「可用」要求：完整句、有中译、句首大写句末有标点、
  不以介词冠词收尾、英文里没混进别的字符、且真的用上了这条习语。
- 剩下 2699 条原书那句被 OCR 毁得没法救（截断、词序错乱），用模型自拟的，
  中文翻译后面标「（自拟）」，一眼能分辨。
- **已知残留**：通过清理的原书例句里仍有零星词序错乱（`She completely was taken
  aback by his anger.` 原书是 `She was completely taken aback`），这种规则查不出来，
  要修得派模型逐条校对 4308 条。

## PDF 版式
16 开 185×260mm 竖版，四列宽度 **17% / 10% / 9% / 64%**——按各列实际内容量
（平均半角宽 30 / 19 / 6 / 108）分配，四列才会一起满、行高才整齐。
一开始按 21/17/7/55 分，前两列大量留白、例句列却要挤三行还被缩到 4pt。渲染器和行数约束沿用 GRE3000
踩出来的经验（见那本的 progress）：必须用 playwright 自带 Chromium，量行数的页面
必须 `viewport=609px` + `emulate_media("print")`，行数必须用 Range 行盒实测。
- **只有习语列留三行，其余压两行**。列宽调匀后基本都能进两行，只有带 BrE/AmE 变体的
  超长条目（`against your better ˈjudgement (especially BrE) (AmE usually…`）放不下，
  占比不到 1%，给它第三行比缩到 4.2pt 看不清强。
  成品复核：2.9 万个格子里 1 行 4117、2 行 23637、3 行 1094，超限 4 个；
  行高中位 21.8pt、九成 31.4pt。
- 常用/口语两行星级前面标了「常」「口」，光两排星分不清哪行是哪个。
- **A-Z 书签**靠渲染时插进表格的字母分节条来建。两个坑：
  ① 不能拿「每页第一行的首字母」凑合——条目大多以 a/the/be 开头，排出来是乱序的；
  ② 认分节条要同时看「整段就一个 ASCII 大写字母」和「字号 9pt 大于正文」，
  只看前者会把正文里的 A、I 单字母条目也算进去（一下 428 条书签）。
- **分节位置取每个字母最长的那段连续块**。简单地「首字母一变就分节」不行——
  改挂关键词时会把 iron、money 补回原位，个别打乱字母序，书签会排成 A B N T U…

## 已知缺口
- 5 条关键词的音标残片被当成了条目（`ˈa:rmtʃer; a:rmˈtʃer/`），渲染时已按形状过滤掉
  一部分，剩下的靠 `08_audit.py` 报出来。
- 20 条例句里没直接出现习语的实词，多数是模型换了近义说法。
- 音标整体没做：中文优先的 OCR 把 IPA 认得很差，成品里干脆不列。要补的话，
  跟补漏行同一个办法——把关键词行单独裁出来用 `en-US` 重 OCR。
