# 习语打分任务说明（给子 agent）

输入是 JSON 数组，元素形如：

```json
{"k": "beattheclock", "i": "beat the ˈclock", "cn": "提前完成；抢在限期前完成"}
```

给每条习语打两个分，都是 **0-5 的整数**：

## 常用程度（`u` = usage）
这条习语在**当代英语**里有多常见（书面 + 口头合起来看）。

- **5**：几乎人人都会用，日常高频（`make up your mind`、`by the way`、`take care of sb`）
- **4**：常见，母语者经常听到/用到（`keep an eye on sb`、`out of the blue`）
- **3**：一般，读书看报会遇到，自己未必主动用（`take sth with a pinch of salt`）
- **2**：偏少见，多在特定语境或文学里（`a fly in the ointment`）
- **1**：罕见或明显过时（`(as) right as ninepence`）
- **0**：极其生僻，现代英语基本不用

判断依据：标了 `(old-fashioned)`、`(old use)`、`(literary)`、`(dated)` 的一律 ≤2；
标了 `(saying)` 的谚语通常 2-3（认得但不常说）。

## 口语化程度（`s` = spoken）
这条习语多大程度上属于**口头表达**而不是书面语。

- **5**：纯口语，写文章不会用（`you bet`、`no way`、`shut up`）
- **4**：明显偏口语，对话里自然（`hang on a minute`、`a big deal`）
- **3**：口头书面都行，中性（`make a mistake`、`in the end`）
- **2**：偏书面（`bear in mind`、`in accordance with`）
- **1**：正式书面语，说话不会这么讲（`without further ado`、`in the event of`）
- **0**：法律/公文体（`with malice aforethought`）

判断依据：标了 `(spoken)`、`(informal)`、`(slang)` 的一般 ≥4；标了 `(formal)`、
`(law)`、`(written)`、`(literary)` 的一般 ≤2；`(saying)` 谚语多在 3 左右。

## 输出

写出同名的 `*.out.json`，内容是 `{"<k>": {"u": 整数, "s": 整数}}`，
key 用输入里的 `k` 字段，原样照抄。

- 只输出裸 JSON，不要代码围栏、不要解释。
- 一条都不能漏，输入多少条就输出多少个 key。
- 两个分要**独立判断**：`without further ado` 常用度可以有 3，但口语度只有 1。
