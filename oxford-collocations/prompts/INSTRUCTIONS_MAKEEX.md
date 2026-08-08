# 给搭配自拟例句

原书只有两成多的搭配带例句，剩下的要自己写。每条搭配都必须有一句例句 + 中译。

## 输入

`work/makeex/NNNN.json`，数组，每项：

```json
{"k": "accommodation||provideaccommodation", "word": "accommodation", "pos": "noun",
 "coll": ["provide accommodation", "offer accommodation"], "cn": "提供住处"}
```

- `coll` 是这一格里的搭配（可能不止一条），**用第一条造句**就行
- `cn` 是中文解释，用它确定这条搭配到底是哪个意思，别写跑偏

## 写例句的要求

1. **一句话，10 到 18 个词**。太长排不进两行。
2. 例句里必须**原样包含 `coll[0]`**（可以有屈折变化：`provide` → `provided`、
   `accommodation` → `accommodations`），但别换成同义词。
3. 用日常、具体的场景，别写教科书式的空话。
4. 中译要地道，跟英文对得上，以句号结尾。
5. 英文句首大写、句末有标点。不要用生僻词。

## 输出

写 `work/makeex/NNNN.out.json`：

```json
{"n": 300, "ex": [{"k": "accommodation||provideaccommodation",
                   "en": "The council must provide accommodation for families who lose their homes.",
                   "zh": "市政委员会必须为无家可归的家庭提供住处。"}]}
```

- `k` 原样抄回来，一个字都不能改，否则回填时对不上
- **每一条都要写**，不许跳过。`n` 是这一批的条数，`ex` 的长度必须等于 `n`
- 最后回一句话：这批写了多少条
