"""
挖 Kaggriculture 讨论区：找公开的策略/复盘帖，以及榜单头部选手的线索。

讨论区是此前完全没碰过的信息源。这里用网页抓取而非 CLI
（CLI 的讨论命令针对数据集，对竞赛讨论区支持有限）。
"""
import json
import re
import urllib.request

out = ["Kaggriculture 讨论区 / 公开方案线索", ""]


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; research)",
        "Accept": "application/json, text/html",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# 1) Kaggle 的公开讨论 API（按竞赛 id）
COMP_ID = 68420
for ep in [
    f"https://www.kaggle.com/api/i/discussions.DiscussionsService/GetTopicListByCompetition?competitionId={COMP_ID}&pageSize=30&sortBy=votes",
]:
    try:
        txt = fetch(ep)
        out.append(f"OK  {ep}")
        out.append(f"    {txt[:600]}")
    except Exception as exc:
        out.append(f"ERR {ep}  {type(exc).__name__}: {exc}")

out.append("")
# 2) 从竞赛页面 HTML 里找讨论/notebook 链接
for url in ["https://www.kaggle.com/competitions/kaggriculture/discussion",
            "https://www.kaggle.com/competitions/kaggriculture/code"]:
    try:
        html = fetch(url)
        out.append(f"OK  {url}  ({len(html)} 字符)")
        links = sorted(set(re.findall(r'"(/[^"]*(?:discussion|code)/[^"]+)"', html)))[:25]
        for l in links:
            out.append(f"    {l}")
    except Exception as exc:
        out.append(f"ERR {url}  {type(exc).__name__}: {exc}")

text = "\n".join(out)
with open("_docx/discussion_probe.txt", "w", encoding="utf-8") as fh:
    fh.write(text)
print(text)
