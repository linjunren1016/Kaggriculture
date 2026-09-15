# Kaggriculture — 参赛工作区

Kaggle Featured 竞赛（奖金 $50,000）。本目录含一个可直接提交的 Agent、本地评测工具、
Kaggle 式自对局校验脚本，以及比赛机制的中文速查。

## 课程要求（来自老师的飞书文档）

| 项目 | 要求 |
| :--- | :--- |
| 队伍 | **3–5 人一组** |
| 每周 | 整理报告 + 抽签上台 |
| 期末 | 书面报告 |
| 教材 | `The Kaggle Book`（Bojan），另需 Python 虚拟环境 + Jupyter Notebook |
| 报名截止 | **2026-09-23**（Entry Deadline） |
| 参考 | BruceQD（青岛大学）B 站视频；字幕下载用 kedou.life |

## 关键：评分机制（必须读，方向性结论）

官方 `Evaluation` 页原文确认了三件事，它们**推翻了"多赚钱"这个直觉目标**：

1. **只看胜负，不看分差。** 原文：
   > "The actual coin difference in a match does not affect the rating change
   > — only the win, loss, or tie outcome matters."

   所以目标是**胜率**，不是最大化赛季末资金。赢 1 块和赢 5 万，加的分完全一样。

2. **每天可提交 5 个，但只有最近 2 个被追踪和用于最终评测。**
   > "only the latest 2 submissions are tracked. The latest 2 submissions are
   > also used for final leaderboard evaluation."

   推论：**不存在"提交次数浪费"**，早期提交会被自动替换掉。想刷分就多提。
   但也意味着**旧成绩会清零**，不能靠一次高分吃老本。

3. **上传时会跑一次 Validation Episode（自己 vs 自己）。** 失败则标记 `Error`。
   本目录的 `validate_submission.py` 在本地复现这一步。

最终评测：截止后所有提交锁定，对局再跑约两周，然后跑 **Bradley-Terry 锦标赛**出最终榜。

### 榜单假象（来自老师提供的字幕整理稿）

- 匹配频率会衰减：刚提交时对局密集，几小时后明显变少；**排名越高，被安排的对局越少**。
- 因此榜上靠前的可能是**很旧的方案**，掉分慢而已，点开回放输的局很多。
  **不要因为对手排第 10 就以为打不过**。
- **同一份方案提交两次，分数可能差 1000 分以上**（早期撞上强手就会一直爬不起来）。
  所以**单次榜单变化不能证明改动有效**，必须做反事实验证。

## 目录内容

| 文件 | 说明 |
| :--- | :--- |
| `main.py` | **提交文件**。根目录、含 `agent(obs)` 函数 |
| `submission.tar.gz` | 打包好的提交包（`main.py` 位于根目录） |
| `benchmark.py` | 本地评测：与 `pass` / `random` / `starter` 各跑 N 局 |
| `validate_submission.py` | Kaggle 式自对局校验（复现 Validation Episode） |
| `tune.py` | 参数扫描工具 |
| `probe_crop.py` | 单株作物生命周期探针 |
| `extract_docx.py` | 从 .docx 提取正文（含表格）的小工具 |
| `benchmark_results.json` / `tune_results.json` | 最近评测与扫描结果 |
| `README.md` / `AGENTS.md` | 官方规则全文与上手指南 |
| `_docx/doc.txt` | 老师提供的字幕整理稿纯文本（1133 行，便于检索） |

## 环境

默认的 Python 3.14 **不可用**：`kaggle-environments` 依赖 `pygame`，而 `pygame`
没有 Python 3.14 的预编译 wheel，源码编译会失败。本目录使用 Python 3.12 虚拟环境：

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -U kaggle-environments
```

已装版本 **1.32.7**，与 PyPI 最新版一致（字幕稿里提醒过要留意环境版本更新）。

## 常用命令

```powershell
# 提交前必跑：Kaggle 式自对局校验
.\.venv\Scripts\python.exe validate_submission.py --archive submission.tar.gz

# 评测（5 局 × 每个对手）
.\.venv\Scripts\python.exe benchmark.py --episodes 5

# 提交
kaggle competitions submit kaggriculture -f submission.tar.gz -m "说明"
kaggle competitions submissions kaggriculture
```

## Agent 策略与实测表现

**策略：露地作物经济（`MAX_LIVESTOCK = 0`）**

1. **不要养牲畜（在当前实现下）。** 喂食需要小麦**拿在手上**，而每天结束时
   所有单位的库存会自动倒回仓库、单位回到仓库旁重生。因此每头牲畜每天都要一次
   「仓库往返」。8 头牛约占掉一整个单位的全天工时，只换来约 $640/天。
   实测（同种子、对 `starter`）：**养牲畜 $691 / 不养 $20,715**。
   牲畜代码保留在 `main.py`，把 `MAX_LIVESTOCK` 设为正数即可重新启用。

2. **雇工数量有明确最优点。** 雇工成本是斐波那契数列且每天重置，但人手过多会
   互相抢同一块地。实测 `HIRE_CAP` 取 4/6/8/10/12 → 平均
   $19,167 / $20,597 / $20,408 / $12,917 / $12,277，**最优点在 6**。

3. **必须做种植预约（reservation）。** 引擎对 `PLANT` 做**按回合的原子校验**：
   若某作物本回合的 `PLANT` 请求总数超过持有种子数，则**该作物所有请求全部作废**。
   因此 8 个单位同时请求稀缺种子会导致**一个都种不下去**，形成永久死锁。
   `main.py` 用每回合共享的 `reserved` 账本按单位顺序预留种子来规避。

### 实测成绩（本地，720 回合完整赛季，种子 1000–1004）

| 对手 | 战绩 | 胜率 | 我方平均资金 | 对手平均资金 |
| :--- | :--- | :--- | :--- | :--- |
| `pass` | 5W-0L-0T | 100% | $20,034 | $3,000 |
| `random` | 5W-0L-0T | 100% | $19,175 | $0 |
| `starter` | 5W-0L-0T | 100% | $20,367 | $3,428 |

合计 **15 胜 0 负**。

> 重要限制：以上对手都是**引擎内置的弱基线**（`starter` 只会在一块地上种胡萝卜）。
> 线上对手是真人提交的强方案，所以这些胜率**不能**说明线上能赢。
> 自对局校验里双方资金几乎相同（14075 vs 14302），说明面对同水平对手时
> 局面非常接近 —— 真正要打的是 Code 区那条强固定路线。

## 已知的踩坑记录

- **`HARVEST` 在 `first_yield_day` 之前是静默空操作**，而一次性作物的
  `yield_units` 在**种植当天就是 1**。只依据 `yield_units > 0` 判断会导致单位
  对着同一块地无限收割。必须按作物自己的 `first_yield_day` / `max_yield_day` 判断。
- **Kaggle 文件加载器取的是「模块全局作用域里最后一个可调用对象」**，不是名为
  `agent` 的函数。因此文件里在 `agent` 之后**不能出现任何模块级 lambda 或函数定义**。
- **不要用 PowerShell 的 `Set-Content -Encoding UTF8` 写 Python 文件**：它会写入
  UTF-8 BOM，导致 `compile()` 抛 `SyntaxError: invalid non-printable character U+FEFF`。
- **Agent 抛异常会导致整局作废并记 0 分**。`main.py` 用 `_safe` 装饰器兜底：
  出错时打印到 stderr（可用 `kaggle competitions logs` 查看）并返回 `PASS`。
- **`PASS` 要写成 `["PASS"]`**。写成裸字符串 `"PASS"` 时引擎读 `op[0]` 会拿到
  `"P"`，虽然多数情况下无害，但不符合契约。

## 路线图（依据整理稿的方法论）

1. **拉 replay 当基准**：从 Code 区点赞最高的开源方案（整理稿点名 **Kaito V27**）
   与 top 50/100 选手的 replay 里提取一条高胜率**固定动作序列**做基座。
   V27 是五模块结构：固定动作表 → 环境识别 → 杂草修复 → 卖单重排 → 雇工对齐 → 异常兜底。
2. **两处已被验证有效的微调**（讲者进入金牌区的做法）：
   遇杂草先 `DIG`；售卖按价值排序并**从 step 716 就开始清仓**，临近结束不再买种子。
3. **反事实验证**：固定对手轨迹，把己方方案替换进去重跑；同时看「输转赢」和
   「赢转输」两个方向；**必须跑 10–20 个 seed**，单局结论无意义。
4. **本地 agent 互相对抗**：把各版本 agent 与 Code 区开源 agent 互相打，记录全部轨迹。
5. **提交前**重新拉一次最新 replay 再验一遍，然后提交（每天最多 5 次，只算最近 2 次）。

### 从后往前优化（整理稿的核心建议）

不要从前面改。**从 step 716 往前**做分叉，因为后续动作少，对终局的影响能直接看出，
贪心/启发式/穷举才跑得动。关键节点候选：step 80 / 160 / 340 / 716。
