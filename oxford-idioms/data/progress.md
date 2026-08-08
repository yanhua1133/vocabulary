# 牛津习语词典 进度

更新：2026-08-07（第二轮：例句字面质量 + 版式重做）

## 结果在哪看
- **`out/牛津习语词典.md`** ← 成品，四列：**习语 / 中文解释 / 常用·口语 / 例句**
  6957 条习语
  例句 **4104 条用原书原文**（占 59%），其余原书那句被 OCR 毁了、退回自拟（标「（自拟）」）
  常用度和口语度各 0-5 分，`★` 一颗 `☆` 半颗
  （原书 3569 个关键词里有 960 个只有交叉引用、本身不带条目）
- **`牛津习语词典 重排版.pdf`**（书目录顶层）← 打印版，241 页 / 8 MB，16 开 185×260mm 竖版，A-Z 书签 24 条
  实测：超过两行的格子 0 个，81% 的字是 7.0pt，字母数字混搭 0 处
- `out/词条清单.md` ← 只有单词和习语的骨架清单，方便快速翻检
- `data/idioms.json` ← 机器可读的结构（含从扫描件抽出的原书释义和例句）
- `data/cache.json` ← 子 agent 校对/重写后的 7609 条 `{i, cn, e}`
- `data/ocr/pNNN.json` ← 630 页整页 OCR，带每行 bbox，所有后续步骤都从这里取数
- 校验：`../.venv/bin/python scripts/08_audit.py`（当前 11 条问题 / 6957，0.2%）
  校验脚本直接复用 `07_render.py::final_rows`，查的就是成品本身而不是中间数据。
  **改过 `10_clean_ex.py` 就必须跑一遍**——见下面「例句字面质量的看门狗」

## 原书情况
- 630 页，260 MB，FreePic2Pdf 生成的**纯扫描件**：每页一张 JPEG，没有文字层，只能 OCR
  （跟 GRE3000 不同，那本是文字层被字形混淆，能无损解码）。
- **原书 PDF 不进版本库**（超 GitHub 单文件 100 MB 上限），只在本地，已写进 `.gitignore`。
- PDF 第 18 页 = 书内页码 1，正文到 PDF 第 621 页 = 书内 604 页。
- 双栏，每栏三类行：关键词（大字号 + 音标）、习语条目（加粗 + 重音符号 ˈ/ˌ）、
  交叉引用（`• easy → (as) easy as ABC`）。

## 管线
```
cd oxford-idioms
../.venv/bin/python scripts/01_ocr.py       # 整页 OCR → data/ocr/
../.venv/bin/python scripts/03_gapfill.py   # 补回 Vision 漏掉的整行（补了 1834 行）
../.venv/bin/python scripts/02_entries.py   # 抽词条骨架 → data/entries.json
../.venv/bin/python scripts/04_expand.py    # 补原书释义/例句 → data/idioms.json
../.venv/bin/python scripts/05_batches.py   # 切批次 → work/batches/
#   派 20 个子 agent，每个 7 批，按 prompts/INSTRUCTIONS.md 写 *.out.json
../.venv/bin/python scripts/06_merge.py     # 校验并入 → data/cache.json
../.venv/bin/python scripts/10_clean_ex.py  # 清理原书例句 → data/examples.json
../.venv/bin/python scripts/14_ex_batches.py     # 切例句校对批次 → work/exfix/
#   派 10 个子 agent，每个 7 批，按 prompts/INSTRUCTIONS_EXFIX.md 写 *.out.json
../.venv/bin/python scripts/15_merge_ex_fixes.py # 校验并回填 → data/examples.json
../.venv/bin/python scripts/11_score_batches.py  # 打分批次 → work/scores/
#   派 10 个子 agent，按 prompts/INSTRUCTIONS_SCORE.md 打常用度/口语度
../.venv/bin/python scripts/12_merge_scores.py   # 并入 → data/scores.json
../.venv/bin/python scripts/09_lost.py      # 捞回被挤掉的条目 → work/lost.json
#   再派 1 个子 agent 甄别并补全，结果放 data/lost.json
../.venv/bin/python scripts/07_render.py    # 渲染成品 → out/牛津习语词典.md
../.venv/bin/python scripts/08_audit.py     # 确定性校验
../.venv/bin/python scripts/13_pdf.py       # 排 PDF（--sample 只排前 200 条看版式）
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
——**这一轮的复核偏松**。第二轮专门只盯英文例句本身、不看别的，随机 80 条里查出
**8 条**（10%）：`well be trying`（we'll）、`hell never set`（he'll）、
`I you lay a finger`（If）、`「m still awake`（I'm）、以及三条英文释义被切进例句中间
（`The very close to sth offices are…`、`When she be very angry found…`）。
教训：**验收题目问得越宽，报回来的问题越少**。要查什么就单独问什么。

**例句全量校对**（第二轮）：4118 条原书例句切 69 批派 10 个 agent 逐条校对，
报回 383 条问题（9.3%），三道闸校验后并入 369 条修正、弃用 14 条（原句烂到只能重写）。
**独立终验随机 120 条：0 条有问题。**
补完大小写那一类后又换种子抽 120 条独立终验：**仍是 0 条。**

**大小写是单独一类，别混在「拼写」里查**。第二轮 100 条里有 6 条是它
（`the Job`、`You Know`、`on july`、`of mps`），因为句子语法成立，
复核 agent 按「不报标点风格」的口径没列进来。判据要按词遍历、看左右两边：
左邻词也大写（且它自己不在句首、或虽在句首但是实词）→ 专名词组后半截，
`Labour Party`、`Third World` 不能动；右邻词大写、或隔着 of 是大写 → 专名词组
前半截，`New York`、`Bank of China` 不能动；句首和全大写缩写（US、MP）一律跳过。
判「这个大写是不是错的」靠**语料自己的统计**——词频分不开
（Ruth 4.05、Labour 4.70、Baker 4.23 跟普通词一样高），但 job / know / price
在全书上百处都是小写、几乎没有句中大写，那 `the Job` 就一定是认错的。
`-ing/-ed/-ly` 那条捷径要卡词干频率 ≥4.0，否则 Sal-ly、Ita-ly、Fr-ed 会被当成屈折形式。

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

## 例句字面质量的看门狗（第二轮加的，别拆）
起因是成品里印出了 `Don't be such a goody-g00dy!`——扫描件把字母认成了形近数字。
顺着查下去，同类问题一共四挂，都写成了规则 + 计数，`08_audit.py` 每次都报：

| 类别 | 修法 | 现在 |
|---|---|---|
| 字母数字混搭（`g00dy`、`100k`、`0f`） | `respell()` 按形近逐个回代，能拼回真词才改 | 0 |
| 拼不出来的词（`tme`、`picrures`） | 修不掉的整条弃用，退回自拟例句 | 0 |
| 句中无故大写（`You're Playing with fire`、`cap In hand`） | `polish()`，虚词表 + 不规则动词表 | 0 |
| 标点后缺空格（`worrying you,get it off`） | `polish()` | 0 |

三个必须记住的坑：

1. **判词用 `wordfreq`，不要用 `/usr/share/dict/words`**。后者是 1934 年的美式原形
   词表，`paperwork`、`laptop`、`o'clock`、`colours`、`asked` 全查不到，拿它当判据
   会把上百条好例句当错字扔掉。`zipf_frequency >= 2.5` 正好分开真词和 OCR 错字
   （paperwork 3.8 / colours 4.2 在上面，tme 2.0 / stuf 2.0 / therr 1.4 在下面）。
   屈折形式（honked、denting、fonder）频率偏低，要还原词干再查一次，
   但**词干至少留 4 个字母**——否则 `difer` 会被「还原」成 `dif` 混过去。
2. **补撇号的规则必须先看整个词是不是常用词**。`\b(we)(ll|ve|re)\b → we'll` 这条
   把全书 **449 处 `were` 改成了 `we're`**、`Hell's teeth` 改成了 `He'll's teeth`，
   而且肉眼抽查完全看不出来。现在只留一条带 `zipf >= 4` 护栏的规则，别再另起一条。
   按空格拼的版本（`we ll` → `we'll`）只收 `ll/ve/nt`——它们单独成词在英文里不存在；
   **`re` 绝不能收**，`were` 被断成 `we re` 的情况比真缩写多得多。
3. **纯数字词分不清**。`80`=go、`200`=zoo、`100k`=look 跟真数字长得一模一样，
   只能靠句法位置判：前面是 to/you/has 是动词位，还原成词；前面是 she/of/the 是
   名词位，那种句子多半已经烂掉（`She 248 was fortunate`），整条弃用。

还有一条判据被移到了渲染层：**「例句真的用上了这条习语」要在 `07_render` 再验一次**。
`10_clean_ex` 是按 `idioms.json` 的原始条目文本判的，而渲染要做改挂、纠正关键词、
拼回断行，对应关系会漂，`run aˈmok` 会配到 `The crowd through the city streets…`。
判据本身也有两个坑：重音符号要先去掉再切词（`aˈmok` 会被切成 `a` + `mok`，
两截都短于 4 字符，core 落空就变成无条件判过）；实词要收到 3 字母
（只收 4 字母以上的话 `catch sb's ˈeye`、`blow your ˈtop` 只剩动词能比，
而例句里的动词多半是 caught / blew 这种不规则变化）。

## 例句从哪来
- **原书优先**。第一版成品的例句全是模型自拟的——我沿用了 GRE3000「例句一律自写」
  的做法，但那是那本书单独确认过的，这本没有。原书例句是词典的权威内容，抽出来
  5257 条，`10_clean_ex.py` 清理后 4374 条判定可用，最终回填 4308 条。
- 清理修的是固定套路：`T've`→`I've`、`Im`→`I'm`、`WaS`→`was` 这类大小写和撇号问题、
  中文里插进的空格。判定「可用」要求：完整句、有中译、句首大写句末有标点、
  不以介词冠词收尾、英文里没混进别的字符、且真的用上了这条习语。
- 剩下 2699 条原书那句被 OCR 毁得没法救（截断、词序错乱），用模型自拟的，
  中文翻译后面标「（自拟）」，一眼能分辨。
- **中译必须完整**：原书的中译常常跨行，抽取时只抓到头一个字
  （`…it was like apples and oranges.` 的中译只剩一个「他」）。判定可用时加了
  「汉字数 ≥ max(4, 英文词数 × 0.45)」，对不上的整条弃用、退回自拟例句，
  绝不能把残缺的中文印上去。当前残缺中译 0 条。
- **规则查不出来的那三类，只能派模型全量过**（`14_ex_batches.py` → agent →
  `15_merge_ex_fixes.py`）。因为改错之后每个词单独看都是对的：
  ① 词序错乱（`She completely was taken aback`）；
  ② 英文释义被切进例句中间（`The very close to sth offices are a heartbeat away…`、
  `When she be very angry found the children…`）；
  ③ 一个词被认成了**另一个真词**（`Hus pride`→`His`、`well be trying`→`we'll`）。
  随机抽 80 条独立复核，这三类合计 10%；补了几条确定性规则后再抽 100 条仍有 6%。
- **回填模型的修正要设三道闸**，别无条件接受：原句必须跟现存的一字不差（对不上
  说明批次过期或抄错行）；相似度 ≥ 0.7（只许修错、不许重写）；改完还要能通过
  `usable()`（别把干净例句改出错字）。
- 释义占位词 `sth` / `sb` 出现在例句里 = 英文释义被切了进来，直接弃用。
  真例句不会用这两个词，这个信号很准。

## PDF 版式
16 开 185×260mm 竖版，四列宽度 **19% / 10.5% / 10.5% / 60%**。
**按各列内容宽度的 P90 分配，不是按平均值**——目标是「九成的格子刚好两行满」。
实测半角宽 P90 是 46 / 26 / 12 / 136，扣掉星级列固定要的宽度后按这个比例分。
按平均值（30 / 19 / 6 / 108）分会让长尾大量超行、被迫缩字号，这正是上一版一页里
蹦出二十几种字号的根源。渲染器和行数约束沿用 GRE3000 踩出来的经验（见那本的
progress）：必须用 playwright 自带 Chromium，量行数的页面必须 `viewport=609px`
+ `emulate_media("print")`，行数必须用 Range 行盒实测。
- **字号只走固定档位** `7.0 / 6.4 / 5.8 / 5.2 / 4.6 / 4.0 / 3.4 / 2.9pt`，
  从大到小挑第一个放得下的。老做法是「每次缩 7%、再每次涨回 3%」，最后落在
  `0.93^n × 1.03^m` 上，一页里能冒出 25 种字号（3.3–9.0pt），相邻两行大小不一，
  看着就是脏。改成档位后 **78% 的字是 7.0pt**，整页最多五种字号。
  - 配套要求：**格子里所有子元素的字号都用 em 写**（`.lab` 0.74em、`.tag` 0.72em、
    星级列 0.86em）。缩排时只改 `td` 一个值，子元素跟着走；写成绝对 pt 的话，
    td 缩完子元素还是原大小，反而比正文大。
  - 每列下限不同：习语列可以一路降到 2.9pt（几十条带三四个变体的超长条目只能靠
    小字，好在都是英文，比中文耐看），其余三列不低于 4.6pt。
- **绝不出现第三行**。除了档位，还靠两件事：
  ① 括号里的语域标签和 `(also …)` 变体用 0.72em 排——它们是次要信息，
     `against your better ˈjudgement (especially BrE) (AmE usually…)` 的括号
     比习语本身还长，缩小它们就够了；必须一次 `re.sub` 包完，
     分两次会产生嵌套 span、把后一个正则搞坏。
  ② 原书例句太长的（半角宽 > 170）直接弃用、退回自拟的那句短例句。
  超行的格子 `13_pdf.py` 会把内容打出来，不是只报个数字。
- **例句列的中英文什么时候连排**。md 里中英文之间是 `<br>`，它会把格子钉死成
  「英文一行 + 中文一行」，逼着英文缩字号硬挤进第一行、中文那行却空掉大半。
  改成：**先按原字号原折行量一次，两行放得下就一个字不动**；只有放不下的才拆掉
  `<br>` 让中英连排，英文用大字号溢到第二行、中文接着排、两行填满。
  别一刀切全拆——英文本来一行装得下的那些，拆了反而破坏上下对齐。
- **最后一列越出纸面**是星级列 `white-space: nowrap` 撑的：加了「常」「口」标签后
  内容变宽，nowrap 不让它换行，就把整张表顶出了版心。给它留够宽度（11%）即可。
  当前文字越出版心的行数 0。
- 常用/口语两行星级前面标了「常」「口」，光两排星分不清哪行是哪个。
- **表格线要画得住**：0.4px 的浅灰线（#d8d8d8）在 300dpi 下只有一个像素多点，
  印出来几乎看不见，最右那条贴着版心边界的更像是没画。现在格线 0.6px #9a9a9a、
  外框 0.9px #7a7a7a。竖线位置实测 31.5 / 133.5 / 192.0 / 245.2 / 493.5，
  版心右界 493.9，五条都在。
- **A-Z 书签**靠渲染时插进表格的字母分节条来建。两个坑：
  ① 不能拿「每页第一行的首字母」凑合——条目大多以 a/the/be 开头，排出来是乱序的；
  ② 认分节条要同时看「整段就一个 ASCII 大写字母」和「字号 9pt 大于正文」，
  只看前者会把正文里的 A、I 单字母条目也算进去（一下 428 条书签）。
- **分节位置取每个字母最长的那段连续块**。简单地「首字母一变就分节」不行——
  改挂关键词时会把 iron、money 补回原位，个别打乱字母序，书签会排成 A B N T U…

## 条目文本的收尾（`07_render.py::tidy_idiom`）
1. **`•` 后被切断的变体**。原书用 `•` 分隔同义变体（`ˌnight and ˈday •ˌday and ˈnight`），
   这是正经体例不能拆；但变体正好落在栏底时会切成半截
   （`every man has his ˈprice •everyone has`、`get/have/take the ˈmeasure of sb • get/`），
   半截没有信息量，删掉。判据：`•` 后那段以虚词/斜杠收尾，或不足两个词。
2. **整条被抄了两遍**（`a force to be ˈreckoned with a force to be ˈreckoned with`）。
3. **例句碎片粘在条目前面**（`mechanic explained that they would have to ˈmake it`）。
   判据必须很窄，否则会切掉 `when the cat's aˈway the mice will ˈplay`、
   `the goose that lays the golden ˈeggs` 这类正经谚语：只认「限定句」
   （`…ed that`、`which is`）和「整条以分词分句起头」两种，且 `-ing` 起头的要排掉
   something / nothing / anything。切完从第一个带重音符号的词起算，再往前捡回
   be / a / your 这类习语常见的起手词。
4. **派生词块**（`ˈwheel-spinning noun: Save yourself some…`）冒号后是正文，切掉。
5. **栏底切断留下的孤零零斜杠**（`ˌsomething like ˈsb/`）。

`08_audit.py` 判「条目像残片」时**不能只看以虚词收尾**——英语习语本来就有很多
以介词结尾的（`to beˈgin with`、`in the region of`、`a rod/stick to ˈbeat sb with`、
`ˈsomething like that`）。with / of / that 收尾一律放行，只留 the / a / and 收尾。

## 已知缺口
- 11 条例句被判「没用上习语」，逐条看过全是屈折变化没比上
  （`lose your ˈlife` → `lost their lives`），不是真问题。
- **音标整体不做**，这是决定不是遗漏：音标属于**关键词**，而成品四列
  （习语/中文解释/常用·口语/例句）里根本没有关键词列，音标没有落脚处；
  硬加一列会把刚调好的 P90 列宽和两行约束全部推翻。习语本身的重读信息已经由
  条目里的 ˈ / ˌ 承担了。真要补的话得先决定版面，不是纯技术活。
