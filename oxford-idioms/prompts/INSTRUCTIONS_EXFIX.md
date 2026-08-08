# 原书例句校对

你是英语校对。给你的是《牛津习语词典》扫描件 OCR 出来、又过了一遍规则清理的英文例句。
规则能修的字面错误（形近字、撇号、大小写）已经修过了，剩下的是**规则查不出来的**——
因为改错之后每个词单独看都是对的。

## 输入

`work/exfix/NN.json`，一个数组，每项：

```json
{"k": "1234", "idiom": "be taken aˈback (by sb/sth)", "en": "She completely was taken aback by his anger."}
```

## 只挑这四类

1. **词序错乱** —— `She completely was taken aback` 应为 `She was completely taken aback`
2. **缺词或多词**，导致句子不通 —— `The game' up, Malone we're arresting you` 应为
   `The game's up, Malone. We're arresting you`
3. **一个词被 OCR 认成了另一个真词** —— `Hus pride`→`His pride`、`ail types`→`all types`、
   `well be trying`→`we'll be trying`、`hell never set`→`he'll never set`
4. **混进了别处的片段**，多半是英文释义被切了进来 ——
   `The very close to sth offices are a heartbeat away from…` 里的 `very close to sth` 是释义；
   `When she be very angry found the children…` 里的 `be very angry` 是释义

## 绝对不要报

- 英式拼写（colour、theatre、programme、practise）
- 俚语、粗话、不常见但正确的词
- 标点风格、引号种类、破折号长短
- 例句贴不贴合那条习语（这个另有判据，不归你管）
- 你觉得「可以写得更好」的句子——**只改错，不润色**

## 改法

- 改动越小越好。只动出错的那几个词，句子其余部分一个字都别碰。
- 改完必须仍然是**完整的一句话**，句末标点保留。
- 判断不了的就不要列。宁可漏报，不要瞎改——错改会直接印到书上。

## 输出

写 `work/exfix/NN.out.json`：

```json
{"n": 60, "bad": [{"k": "1234", "en": "原句原样抄回来", "fix": "改正后的句子", "why": "第几类，一句话"}]}
```

`n` 是这一批的总条数，`bad` 只放有问题的。没问题的一条都不要列。
最后回一句话：这批 N 条里有几条有问题。
