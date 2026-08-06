# 修坏掉的搭配（给子 agent）

这批条目的**搭配文本本身被 OCR 弄坏了**，`cn` 和 `ex` 是上一轮校对过的、基本可信。
输入元素形如：

```json
{"id": "time||timehim", "w": "time", "c": ["time him"],
 "cn": "时间的迷雾", "ex": "The origins of this custom are lost in the mists of time.  这个习俗的起源湮没在时间的迷雾中。"}
```

这里 `c` 写的 `time him` 是错的，从 `cn`（时间的迷雾）和 `ex`（lost in the mists of time）
能看出真正的搭配是 **`the mists of time`**。

对每一条输出 `{"<id>": {"c": [...], "cn": ..., "ex": ...}}`：

## `c` —— 修好的搭配（数组）
- **从 `cn` 和 `ex` 反推真正的搭配**，写成完整可查的形式，词头 `w` 要在里面。
- 原书是牛津搭配词典，搭配都是标准英语，不会有 `time him`、
  `enough without you constantly telling me how it was al bad` 这种东西——
  那都是 OCR 把正文、例句碎片混进来了。
- 一格可以有多条（`can hardly believe sth`、`can scarcely believe sth`），
  但必须都是**真实存在的搭配**，别硬凑。
- 实在推不出来（信息太少），就输出 `["__DROP__"]`，这条会被丢掉。

## `cn` —— 中文解释
- 只能是中文，≤20 字，多义用 `；` 分隔。
- 去掉 `（搭配疑误）` 这个标记。
- 跟修好的 `c` 对得上。

## `ex` —— 例句
- 格式：**英文句子 + 两个空格 + 中文翻译**，英文 8-18 词、完整句。
- **必须用上修好的 `c` 里的搭配**（可做时态/单复数变形）。
- 原来那句能用就留着，对不上就重写。

## 输出
- 每个输入 `fNNN.json` 写一个 `fNNN.out.json` 在同一目录。
- 只输出裸 JSON，key 原样照抄，一条不漏。
