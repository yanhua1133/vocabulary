# 牛津习语词典 进度

更新：2026-08-05（第一步「列出词条」完成）

## 结果在哪看
- **`out/词条清单.md`** ← 3654 个关键词、7893 条习语，按书内页码顺序
- `data/entries.json` ← 同样的内容，机器可读（含 OCR 原样音标）
- `data/ocr/pNNN.json` ← 630 页的整页 OCR 结果，带每行 bbox，后续都从这里取数

## 原书情况
- 630 页，260 MB，FreePic2Pdf 生成的**纯扫描件**：每页一张 JPEG，没有任何文字层，
  只能 OCR（这点跟 GRE3000 不同，那本是文字层被字形混淆，能无损解码）。
- **原书 PDF 不进版本库**（超过 GitHub 单文件 100 MB 上限），只留在本地，已写进 `.gitignore`。
- PDF 第 18 页 = 书内页码 1，正文到 PDF 第 621 页 = 书内 604 页。
- 双栏排版，每栏三类行：关键词（大字号 + 音标）、习语条目（加粗 + 重音符号）、
  交叉引用（`• easy → (as) easy as ABC`）。

## 管线
```
../../.venv/bin/python scripts/01_ocr.py        # 整页 OCR → data/ocr/
../../.venv/bin/python scripts/03_gapfill.py    # 补回 Vision 漏掉的整行
../../.venv/bin/python scripts/02_entries.py    # 抽词条 → data/entries.json + out/
```

## 踩过的坑（都写进脚本注释了，别踩第二遍）
1. **OCR 用 macOS Vision，`language_preference` 第一位必须是 `zh-Hans`**。
   写成 `en-US` 在前时中文整段丢失，只吐 `thiE#` 这种乱码。220dpi 够用，300dpi 不会更好。
   机器上的 tesseract 只有 eng 语言包，不能用。
2. **Vision 会静默丢整行**，丢的多半正好是加粗的习语条目行（p1 右栏
   `absence makes the heart grow ˈfonder` 整行没输出）。靠「相邻行 y 间距 > 正常行距 1.75 倍」
   检测，把空带单独裁出来用 `en-US` 重 OCR，全书补回 1834 行。
3. **字重判据行不通**：Vision 的行 bbox 不够准，量笔画宽度时粗体反而比正文细。
   改用版面规律——条目行只出现在关键词之后或上一条收尾之后，再叠加重音符号 ˈ。
4. **重音符号 ˈ 被认成 ASCII 单引号，偶尔认成双引号**；次重音 ˌ 被认成逗号，
   而英文正文里的逗号长得一模一样，**不能还原**，硬还原会把 `respect, etc.` 变成
   `respectˌetc.` 再被当成条目，一下多召回 4000 多条垃圾。
5. **交叉引用**的项目符号和箭头 OCR 得五花八门，但「箭头前那个词紧接着重复一次」
   （`hedge hedge your bets`）是稳的。只能认**相邻**重复——放宽成「首词在后文任意位置重复」
   会误杀 `the ˈbigger… the ˈbetter`、`for ˌbetter or (for) ˈworse`。
6. **关键词不能只靠字号**：Vision 的行高逐页漂移，末页 `yore /jɔː(r)/` 的 h 跟同页正文
   一样是 0.0147，卡 0.015 会整页漏光。改成「带音标的一律认，没音标的才看字号」。

## 已知缺口（下一步「展开」时处理）
- **音标质量差**：中文优先的 OCR 把 IPA 认得很烂（`/əˈbæk/` → `/abaek/`）。
  修法跟补漏行一样——把关键词行单独裁出来用 `en-US` 重 OCR。
- 少量条目被排版断成两行后没能拼回（`against your better judgement (especially` /
  `ˈjudgment)`），页眉词偶尔会被吞进相邻条目。
- 释义、例句、中文翻译都还没抽，`data/ocr/` 里有全部原始行，展开时按同样的版面规律切。
