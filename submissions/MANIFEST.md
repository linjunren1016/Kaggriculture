# 提交版本归档（submissions/）

这个目录存放**每一次真正提交给 Kaggle 的 agent**，目的：改动 agent 之后仍然找得到以前每一版。

命名规则：`<submission_ref>__<机制简称>.py`（还没拿到 ref 的用 `pending__`）。
同名 `.tar.gz` 是当时实际提交的打包文件。

---

## 提交记录

| submission | 提交时间 | 归档文件 | sha256(前16) | 机制 | 线上分 | 判定 |
|---|---|---|---|---|---|---|
| 56268283 | 2026-09-16 03:27 | `56268283__adarsh_single_repair.py` | `3177EFA6BB9F2D04` | 单张高分选手动作表 + V38 修复/护栏层 | **1776.7**（峰值 1784.9） | ★ **目前最佳** |
| 56250957 | 2026-09-15 09:24 | `56250957__v38_kawashigi_adaptive.py` | `F34A54B960A0EBD3` | V38 本体（预录动作表，来自第三方公开 notebook） | 1152.7 | 被 56268283 取代 |
| 56249501 | 2026-09-15 08:06 | 未识别 | — | — | 960.6 | — |
| 56248341 | 2026-09-15 07:00 | 未识别 | — | — | 766.1 | — |
| 56244529 | 2026-09-15 03:47 | 未识别 | — | — | 356.0 | — |
| 56234750 | 2026-09-14 15:54 | 未识别 | — | — | 392.3 | — |
| 56229463 | 2026-09-14 11:15 | 未识别 | — | — | 412.6 | — |
| 56275283 | 2026-09-16 09:28 | `56275283__adarsh_route_library.py` | `8AE5C0922B6133C2` | 11 张动作表按商店前缀自动选表 + 修复层 | 1181.8 | ✗ **不如单表版**（≈V38 水平） |

- 线上分是读取时刻的 publicScore，**会随时间漂移**（天梯是 Bradley-Terry，对手变强会拉低所有人）。
- 「未识别」的 5 版：代码存在 git 历史里（当时提交的是 `main.py` / `submission.tar.gz`），但没和 ref 对应上。**如需追溯，从 git log 找当时的 main.py 即可。**

## 归档文件对照

| 归档文件 | 字节 | sha256(前16) |
|---|---|---|
| `56268283.tar.gz` | 105,401 | `CCCE4E9F9CE38954` |
| `56250957.tar.gz` | 93,534 | `13CDC31C559AB251` |
| `56275283__adarsh_route_library.tar.gz` | 202,836 | `453847C40ABE1660` |

建议提交用：

```bash
kaggle competitions submit kaggriculture -f submission.tar.gz -m "备注"
```

## 新增一版的做法

1. 把要提交的 `.py` 复制进来，命名 `<submission_ref>__<机制简称>.py`；
2. `.tar.gz` 也复制进来，命名 `<submission_ref>.tar.gz`；
3. 在上面的表里加一行；
4. `git add -A && git commit -m "submit: <ref> <机制> <分数>"`。

---

## 必须记住的评测经验（踩过的坑）

1. **回放里的 action 数组相对 observation 整体错位 +1。**
   `steps[t].observation` 是第 t 步的**前**状态；产生它的动作在 `steps[t+1].action`。
   拿 `steps[t].action` 直接喂会得到完全错误的复原。修正后 12/12 局可比特级复现。
   **任何从回放复原 agent 的代码都必须用 `ACTION_SHIFT = 1`。**

2. **反事实评测用「冻结对手轨迹」，会系统性高估我们。**
   对手在反事实里只是重放录像，不会针对我们应变，所以显得比线上弱。
   后果：本地判「更强」的方案（如路线库 29.2% vs 25.0%）一到线上就翻车。
   → **本地结论只能当方向参考，不能当验收依据。**

3. **线上天梯的前 30 分钟爬升速度是很好用的快筛。**
   实测：好版本半小时到 1300；差版本半小时只有 1000。
   比等 6–8 小时收敛快得多。（`kaggle competitions submissions kaggriculture`）

4. **固定单表 > 任何运行时选表机制。** 三组实测：

   | 方案 | 结构 | 线上分 |
   |---|---|---|
   | ADARSH 单表 + 修复层 | **固定单表** | **1776.7** ★ |
   | 11 张表路线库 | 按商店前缀选表 | 1181.8 |
   | V38 | 5 张表按商店模式选 | 1152.7 |

   两个「选表」方案几乎同分，都远低于固定单表 —— 所以问题出在**选表机制本身**，不是表的质量。
   推测原因：165 种商店前缀里库里只有 11 种，匹配不上时选表退化成「取列表第一张」，
   比那张精选过的表更差。

## 不进版本库的东西

`.gitignore` 已排除，都可从 Kaggle 重新下载或本地重建：
`episodes/`（16.9GB 官方对局 parquet）、`replays/`、`replays_55341437/`（3.6GB）、
`replays_online/`（718MB）、`_docx/`（378MB，含 sept_replays.pkl）、
`opponents_src/`、`.venv/`（997MB）、`submission.tar.gz`（工作副本）。

## 远程仓库

`origin` = https://github.com/linjunren1016/Kaggriculture

**本机网络阻断 `github.com:443`**（TCP 直连超时），但 `api.github.com` / `codeload.github.com` 可达。
所以 push 必须走代理。已在本仓库配好 **repo-local** 代理（不动全局 git 配置）：

```bash
git -C <repo> config http.proxy            # -> http://127.0.0.1:7897
```

**推之前先确认代理软件是开着的**（Clash 默认端口 7897）。代理关着时 `git push` 会报
`Failed to connect to github.com port 443 via 127.0.0.1`，那不是仓库问题，开代理即可。

日常提交：

```bash
git add -A && git commit -m "submit: <ref> <机制> <分数>"
git push
```
