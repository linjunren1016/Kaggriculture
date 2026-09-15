"""
把队员手册生成为 Word (.docx)。

内容全部内联在本脚本里，输出的文档不依赖任何外部 PDF / 视频，
队员只读这一份即可理解全部规则与做法。
"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

CN_FONT = "微软雅黑"
ACCENT = RGBColor(0x1F, 0x4E, 0x79)      # 深蓝，用作标题
WARN_RED = RGBColor(0xC0, 0x00, 0x00)    # 警示色


# ---------------------------------------------------------------- 基础工具
def set_base_style(doc):
    st = doc.styles["Normal"]
    st.font.name = CN_FONT
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)
    st.paragraph_format.space_after = Pt(4)
    st.paragraph_format.line_spacing = 1.25


def style_heading(doc, name, size, color, bold=True):
    st = doc.styles[name]
    st.font.name = CN_FONT
    st.font.size = Pt(size)
    st.font.bold = bold
    st.font.color.rgb = color
    st.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)


def shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hex_fill)
    tc_pr.append(el)


def h1(doc, text):
    return doc.add_heading(text, level=1)


def h2(doc, text):
    return doc.add_heading(text, level=2)


def h3(doc, text):
    return doc.add_heading(text, level=3)


def p(doc, text, bold=False, color=None, size=None):
    par = doc.add_paragraph()
    run = par.add_run(text)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    if size is not None:
        run.font.size = Pt(size)
    return par


def rich(doc, segments):
    """segments: list of (text, bold, color|None)."""
    par = doc.add_paragraph()
    for text, bold, color in segments:
        run = par.add_run(text)
        run.bold = bold
        if color is not None:
            run.font.color.rgb = color
    return par


def bullets(doc, items, style="List Bullet"):
    for it in items:
        if isinstance(it, tuple):
            par = doc.add_paragraph(style=style)
            par.add_run(it[0]).bold = True
            par.add_run(it[1])
        else:
            doc.add_paragraph(it, style=style)


def warn(doc, text):
    """红色警示段落，用 ⚠ 起头，便于扫读。"""
    par = doc.add_paragraph()
    run = par.add_run("⚠  " + text)
    run.bold = True
    run.font.color.rgb = WARN_RED
    return par


def table(doc, header, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, text in enumerate(header):
        hdr[i].text = ""
        par = hdr[i].paragraphs[0]
        run = par.add_run(text)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(hdr[i], "1F4E79")
    for row in rows:
        cells = t.add_row().cells
        for i, text in enumerate(row):
            cells[i].text = str(text)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = w
    doc.add_paragraph()
    return t


def code_block(doc, lines):
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Pt(12)
    par.paragraph_format.space_before = Pt(4)
    par.paragraph_format.space_after = Pt(8)
    for i, line in enumerate(lines):
        run = par.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(9)
        if i < len(lines) - 1:
            run.add_break()
    return par


# ---------------------------------------------------------------- 文档内容
def build(path):
    doc = Document()
    set_base_style(doc)
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
        style_heading(doc, name, size, ACCENT)

    title = doc.add_heading("Kaggriculture 参赛队员手册", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = p(doc, "Kaggle Featured 竞赛｜奖金 $50,000｜队伍规模 3–5 人", size=10)
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note = p(doc, "本手册自足：只读这一份即可理解全部规则与做法，无需查阅任何其他资料。", size=9)
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    # ============================================================ 0
    h1(doc, "0  一分钟速览")
    table(doc,
          ["问题", "答案"],
          [
              ["比赛比什么？", "两个 AI Agent 在农场经营模拟里一对一，720 回合，钱多者胜"],
              ["排行榜怎么算分？", "Elo 式技能分，只看赢 / 输 / 平，不看赢了多少钱"],
              ["被追踪几次提交？", "全部提交中最新的 2 次（滚动窗口，不是每天重置）"],
              ["每天能提几次？", "5 次"],
              ["报名截止", "2026-09-23"],
              ["最终提交截止", "2026-09-30"],
              ["课程要求", "每周报告 + 抽签上台；期末书面报告"],
              ["我们的目标", "胜率，不是赛季末资金"],
          ],
          widths=[Pt(150), Pt(330)])

    # ============================================================ 1
    h1(doc, "1  课程要求")
    table(doc,
          ["项目", "要求"],
          [
              ["组队", "3–5 人一组"],
              ["每周", "整理报告，抽签上台汇报"],
              ["期末", "书面报告缴交"],
              ["技术栈", "Python 虚拟环境 + Jupyter Notebook"],
          ],
          widths=[Pt(120), Pt(360)])

    h2(doc, "1.1  时间")
    table(doc,
          ["节点", "日期", "说明"],
          [
              ["报名截止", "2026-09-23", "必须在此日期前接受竞赛规则"],
              ["最终提交截止", "2026-09-30", "截止时在册的 2 个提交决定最终成绩"],
              ["最终评测", "截止后约 2 周", "对局继续跑，然后出最终榜"],
          ],
          widths=[Pt(110), Pt(110), Pt(260)])
    warn(doc, "Kaggle 另有 Team Merger Deadline（组队合并截止），通常早于或等于报名截止。"
              "组队相关的截止日请以 Kaggle 竞赛页面为准。")

    # ============================================================ 2
    h1(doc, "2  比赛机制")

    h2(doc, "2.1  基本框架")
    bullets(doc, [
        "一局 = 30 天 × 24 小时 = 720 回合（step 0 到 step 719）。",
        "两名选手各有 10×10 农场，初始只有西北角的 5×5 解锁；另三块要花钱买，价格 1k / 2k / 4k。",
        "初始资金 3000 元。",
        ("胜负判定：", "第 720 回合结束时，银行里的钱多者获胜。仓库里没卖掉的货不算钱。平局可能发生。"),
    ])

    h2(doc, "2.2  每回合要做的三个决定")
    table(doc,
          ["输出字段", "内容"],
          [
              ["farmer", "主农民这一回合干什么（一个动作）"],
              ["hands", "每个雇工各干什么（每人一个动作）"],
              ["market", "市场订单列表，最多 10 条，且顺序敏感"],
          ],
          widths=[Pt(110), Pt(370)])

    h2(doc, "2.3  动作与市场指令")
    p(doc, "农民 / 雇工可执行的动作：", bold=True)
    bullets(doc, [
        "移动：上 / 下 / 左 / 右",
        "作物：PLANT（种植）、WATER（浇水）、HARVEST（收获）、FERTILIZE（施肥）",
        "动物：BUILD_COOP（建鸡舍）、BUILD_PASTURE（建牧场）、FEED（喂食）、"
        "CARE（照料）、COLLECT_FERTILIZER（收肥料）",
        "仓库：PICKUP（取货）、DROP（卸货）、PLACE（放置）",
        "地形：DIG（挖掉作物 / 杂草 / 空畜舍）",
        "PASS（什么都不做）",
    ])
    p(doc, "市场指令（最多 10 条）：", bold=True)
    bullets(doc, [
        "BUY_SEED 买种子、BUY_ANIMAL 买牲畜、BUY_PRODUCT 买小麦或肥料",
        "SELL 出售、HIRE 雇工、BUY_LAND 买地",
    ])

    h2(doc, "2.4  可经营的对象")
    table(doc,
          ["类别", "对象", "种子 / 成本", "基础售价", "首次产出", "特点"],
          [
              ["作物", "小麦", "10", "25", "第 2 天", "一次性收获；也是牲畜饲料"],
              ["作物", "胡萝卜", "20", "35", "第 2 天", "一次性收获"],
              ["作物", "番茄", "50", "60", "第 8 天", "持续产出，共 4 次"],
              ["作物", "草莓", "100", "120", "第 10 天", "持续产出，共 4 次"],
              ["作物", "甜瓜", "80", "250", "第 10 天", "一次性收获，单价最高"],
              ["牲畜", "鹅 / 蛋", "300 + 鸡舍", "50", "第 4 天", "每天产出，只要喂食就持续"],
              ["牲畜", "牛 / 牛奶", "400 + 牧场", "160", "第 8 天", "每 2 天产出，只要喂食就持续"],
              ["牲畜", "羊 / 羊毛", "500 + 牧场", "200", "第 6 天", "每 3 天产出，只要喂食就持续"],
          ],
          widths=[Pt(50), Pt(90), Pt(80), Pt(70), Pt(65), Pt(125)])

    h2(doc, "2.5  三条容易忽略的硬规则")
    rich(doc, [("1. 必须每天浇水 / 喂食。", True, None),
               ("作物和动物连续两天没被照顾 → 作物变成杂草、动物永久逃跑。"
                "而且种植当天就算第一天，新种的作物当天不浇水，当晚就变杂草，没有宽限期。", False, None)])
    rich(doc, [("2. 市场是双方共享的。", True, None),
               ("你卖得越多、价格越低。高级品（草莓 / 甜瓜 / 牛奶 / 羊毛）价格极易崩到 1 元地板价。"
                "卖晚了要吃大亏：对手先卖，你的价格就没了。", False, None)])
    rich(doc, [("3. 雇工成本是斐波那契数列。", True, None),
               ("1, 1, 2, 3, 5, 8, 13, 21……每天重置，所以每天都要重新雇。"
                "雇到 10 个时，成本可能已经超过收益。", False, None)])

    doc.add_page_break()

    # ============================================================ 3
    h1(doc, "3  评分机制（最重要的一节）")

    h2(doc, "3.1  只看胜负，不看分差")
    p(doc, "官方评测页原文：")
    quote = doc.add_paragraph()
    quote.paragraph_format.left_indent = Pt(24)
    run = quote.add_run(
        "\u201cThe actual coin difference in a match does not affect the rating change "
        "\u2014 only the win, loss, or tie outcome matters.\u201d")
    run.italic = True
    bullets(doc, [
        "排行榜分数是 Elo 式技能分。",
        ("赢 1 元和赢 50,000 元，加分完全一样。", ""),
        "所以优化目标是胜率，不是这一局比对手多赚多少。",
    ])
    warn(doc, "这是全队最容易走错的方向。举例：方案 A 平均赢 20,000 元、方案 B 平均赢 2,000 元，"
              "但 B 的胜率更高，那么 B 更好。不要被「赢得多」迷惑。")
    p(doc, "唯一的例外：当胜率打平时，分差（margin）变大仍然是正反馈信号 —— "
           "说明策略在改善，只是还没跨过胜负门槛。", size=10)

    h2(doc, "3.2  只有最新的 2 次提交被追踪")
    p(doc, "官方评测页原文：")
    quote = doc.add_paragraph()
    quote.paragraph_format.left_indent = Pt(24)
    run = quote.add_run(
        "\u201conly the latest 2 submissions are tracked. The latest 2 submissions "
        "are also used for final leaderboard evaluation.\u201d")
    run.italic = True
    p(doc, "常见问答页措辞更明确：")
    quote = doc.add_paragraph()
    quote.paragraph_format.left_indent = Pt(24)
    run = quote.add_run("\u201cOnly your most recent N are active\u201d")
    run.italic = True

    rich(doc, [("是「全部提交中最后提交的 2 个」，不是「每天最后提交的 2 个」。", True, WARN_RED)])
    p(doc, "判定依据：官方用的是 latest / most recent（最近的），指的是一个滚动窗口，"
           "而且用了 active（在册）这个词。如果是按天计算，会写成 the latest 2 each day。")

    h3(doc, "滚动窗口实际怎么运作")
    table(doc,
          ["时间", "本次提交", "当前在册的 2 个", "发生了什么"],
          [
              ["周一", "A", "A", "未满 2 个"],
              ["周一", "B", "A、B", "满 2 个"],
              ["周二", "C", "B、C", "A 被挤出，失效"],
              ["周二", "D", "C、D", "B 也被挤出"],
              ["周三", "E、F", "E、F", "C、D 失效"],
              ["周三", "G", "F、G", "E 失效"],
              ["截止时", "—", "F、G", "只有这两个进最终评测"],
          ],
          widths=[Pt(70), Pt(80), Pt(130), Pt(200)])

    h3(doc, "三条推论")
    bullets(doc, [
        ("不存在「提交次数浪费」。", "每天可以提 5 次，试验版本随手提，旧的会自动失效。"
         "想多刷几个不同方案积累对局数据，是鼓励的做法。"),
        ("但旧成绩会清零。", "上周的高分不会被保留，别指望吃老本。"),
        ("截止前必须有意安排最后两次提交。", "见下方警示。"),
    ])
    warn(doc, "这是个真实的坑：如果你在截止前手忙脚乱地提交了几个试验版本，"
              "最终被评测的 2 个里可能包含一个半成品，它会直接拖累最终成绩。"
              "正确做法是确认好两个最佳版本，再按顺序提交。")

    h2(doc, "3.3  上传时的自动校验")
    p(doc, "上传后平台会跑一次 Validation Episode，让你的 Agent 和自己打一局，确认能正常运行。")
    bullets(doc, [
        "失败则该次提交被标记为 Error，可以下载日志排查。",
        "成功则获得一个初始分，进入匹配池。",
    ])
    warn(doc, "Agent 抛异常会导致整局作废并记 0 分。代码必须有异常兜底，"
              "出错时返回「什么都不做」而不是让程序崩掉。")

    h2(doc, "3.4  最终评测")
    p(doc, "截止后所有提交被锁定，对局继续跑约两周，然后运行 Bradley-Terry 锦标赛产出最终榜。")
    p(doc, "所以最终排名取决于：截止时在册的那 2 个方案 + 之后两周的对局运气。")

    doc.add_page_break()

    # ============================================================ 4
    h1(doc, "4  怎么做：五步")

    h2(doc, "第一步　跑通一个能提交的基线")
    bullets(doc, [
        "先要有一个能跑完 720 回合、不报错的最小 Agent。",
        "它的分数高低此时完全不重要，重要的是先拿到 submission id。",
        ("submission id 是后续一切分析的前提。", "没有它，就无法下载自己的对局回放做分析。"),
    ])

    h2(doc, "第二步　下载公开方案与高手回放")
    bullets(doc, [
        "从竞赛的 Code 区找点赞量最高的开源方案，下载下来当实验对象。",
        "从排行榜前排队伍各下载若干条对局回放。",
        "回放可以批量下载；每条回放都有 id，下载时要去重。",
    ])
    warn(doc, "剔除「分数高但提交时间久远、且正在连败」的队伍，它们的回放不值得下载。"
              "见第 6 节「榜单会骗人」。")

    h2(doc, "第三步　做规则，不要急着建模")
    p(doc, "这是这个比赛最重要的一条经验：很多人做 Kaggle 的第一反应是建模型，"
           "但在这个比赛里应该先下载数据、做分析、制定规则、用规则去修正方案。")
    p(doc, "什么时候才值得建模？")
    bullets(doc, [
        "当规则已经多到很难用一个简单流程串起来，并且",
        "回放数据积累到几千、几万条的量级时。",
    ])
    p(doc, "一开始基于几百条回放分析完之后，你想做的操作往往只是一个公式、一个乘积、"
           "一个系数就能完成，不需要模型。")
    p(doc, "关于强化学习：这个比赛棋盘 100 格、角色多、动作多、还有市场供需，复杂度极高，"
           "不建议一上来就用。合理路径是从后往前、从局部开始（见第五步）。")

    h2(doc, "第四步　一次只改一件事，然后验证")
    bullets(doc, [
        "每次只改动一个组件，这样才说得清是哪个改动起了作用。",
        "改完必须验证，不能只看榜单。验证方法见第 5 节。",
    ])

    h2(doc, "第五步　从后往前优化")
    p(doc, "不要从第 0 步开始改。要从最后几步往前做分叉，理由是：")
    bullets(doc, [
        "后面的动作少，对最终结果的影响能直接看出来。",
        "只有在这种情况下，贪心 / 启发式 / 穷举这类方法才跑得动。",
        "一开始改动越靠前，后面需要承担的状态组合就越多，根本算不完。",
    ])
    p(doc, "比较值得尝试的节点是临近结束的几步，以及少数几个中期关键节点。")

    # ============================================================ 5
    h1(doc, "5  验证方法（判断改动是否真的有效）")
    rich(doc, [("核心原则：榜单不能用来判断改动好坏，必须线下验证。", True, WARN_RED)])

    h2(doc, "5.1  反事实验证")
    p(doc, "做法是把对手的轨迹固定住，只替换我方方案，然后重跑。")
    bullets(doc, [
        "下载排名靠前选手的对局回放，以及自己的对局回放。",
        "把方案里的某一个组件替换掉，对手的轨迹保持不变，重新跑一遍。",
        "看两个方向：原本输的局有没有翻盘变成赢；原本赢的局有没有变成输。",
    ])
    warn(doc, "必须跑 10–20 个随机种子。单局结论毫无意义 —— 地图（由随机种子决定）本身也是变量，"
              "换一块地，这次输几十、下次就赢了。")
    rich(doc, [("真实反例：", True, None),
               ("有个改动在某一局把败局翻转成胜局，但应用到全部回放后发现，"
                "新增了 2 局原本赢、现在输的对局，总失败局数从 1 变成 3，反而更差了。", False, None)])

    h2(doc, "5.2  线下 Agent 互相对抗")
    bullets(doc, [
        "把各个版本的 Agent 与 Code 区开源 Agent 互相对打，记录全部轨迹。",
        "优势是没有任何限制，不消耗线上提交次数，可以做任意全面的对比。",
    ])

    h2(doc, "5.3  评测该看哪些指标")
    p(doc, "不能只看平均胜率。要看：")
    bullets(doc, [
        "胜率、胜率矩阵（谁克制谁）",
        "平均分差（margin）",
        "方差、最差情况",
        "成对对局的 delta",
    ])
    p(doc, "关键是要同时看「挑战集」（原本输的局）和「回归集」（原本赢的局），"
           "不能只看平均收益，也不能只看对某一个对手的结果。")

    h2(doc, "5.4  提交前必做")
    bullets(doc, [
        "重新拉一次最新榜单的回放。你折腾的几个小时里，别人可能已经出了新方案。",
        "加上自己提交新增的回放。",
        "再对抗、再评测一遍，确认没问题再提交。",
    ])

    doc.add_page_break()

    # ============================================================ 6
    h1(doc, "6  榜单会骗人（别被吓住，也别被迷惑）")

    h2(doc, "6.1  匹配频率会衰减")
    bullets(doc, [
        "刚提交时平台会非常频繁地安排对局。",
        "大约 2–4 小时后，对局频率明显降下来。",
        "排名越高，被安排的对局越少。",
    ])

    h2(doc, "6.2  榜单假象")
    p(doc, "因为高排名选手被安排的对局少、掉分也慢，所以：")
    bullets(doc, [
        "榜上靠前的可能是十几个小时前的旧方案。",
        "点开它的回放会发现，其实输的局很多。",
    ])
    warn(doc, "不要因为「我的新方案要对上第 10 名，肯定打不过」就不敢提交。那些旧方案未必真的强。")

    h2(doc, "6.3  同一方案提交两次，分数可能差 1000 分以上")
    p(doc, "原因：如果某个提交在早期就撞上一个很强的对手并输掉，它的分数可能一直爬不起来。")
    p(doc, "前排强选手提交新方案时，新方案是从低分区起步的，恰好就在低分区撞上你，你就输了。")
    warn(doc, "单次榜单变化不能证明你的改动有效。榜涨了可能是运气，榜跌了可能也是运气。")

    # ============================================================ 7
    h1(doc, "7  已被验证有效的优化方向")

    h2(doc, "7.1  高价值、低难度")
    table(doc,
          ["改动", "具体做法", "为什么有效"],
          [
              ["遇杂草先挖地", "单位脚下是杂草、挡住原本的生产动作时，先挖掉再继续原计划",
               "杂草会阻塞生产动作，不处理就白白浪费回合"],
              ["提前卖货", "售卖按价值排序，并从最后 4 步左右就开始清仓，而不是等到最后一步",
               "很多方案最后一步还有货没卖出去，这些货一文不值"],
              ["临近结束停止买种子", "最后几步不要再买种子",
               "买了也来不及收获，纯粹浪费钱"],
          ],
          widths=[Pt(95), Pt(200), Pt(185)])

    h2(doc, "7.2  结构性方向")
    bullets(doc, [
        ("把路线与市场拆成两个模块。", "市场订单上限 10 条且顺序敏感，容易和其他逻辑纠缠。"),
        ("从固定路线升级为条件判断。", "在关键节点上根据当前市场情况 / 对手情况切换做法。"),
        ("固定路线的死穴是对手针对。", "如果很多人抄同一条开源路线，可以针对性反制；"
         "同时准备多条候选路线，发现被针对就换。"),
    ])

    h2(doc, "7.3  线上与线下的分工")
    table(doc,
          ["", "线下（研究用）", "线上（提交用）"],
          [
              ["复杂度", "可以用复杂模型、大算力、搜索算法", "文件小于 100MB，内存和 CPU 受限"],
              ["用途", "只用于研究与验证", "提交时必须简化、规则化"],
          ],
          widths=[Pt(70), Pt(210), Pt(200)])
    p(doc, "一个复杂但有效的模型，往往可以用一套简单规则做近似等价的替代，然后再提交上线。")

    # ============================================================ 8
    h1(doc, "8  常见坑（每一条都会造成实际损失）")

    h2(doc, "8.1  策略 / 游戏机制")
    table(doc,
          ["坑", "后果", "正确做法"],
          [
              ["作物没浇水 / 动物没喂食",
               "连续两天就变杂草或永久逃跑",
               "每天都要浇水喂食；种植当天就算第一天，没有宽限期"],
              ["把货留到最后一步才卖",
               "仓库里的货不计入最终资金，等于白干",
               "按价值排序提前清仓"],
              ["雇工雇太多",
               "成本是斐波那契数列，雇到 10 个时成本可能超过收益",
               "按任务量决定雇多少个，不是越多越好"],
              ["同一个市场大量抛售高级品",
               "价格崩到 1 元地板价，自己把自己的收益砸没",
               "分批卖、按价值排序，注意对手是否先卖"],
              ["只看平均分差判断方案好坏",
               "分差不影响评分，方向性错误",
               "看胜率；分差只在胜率打平时作为参考"],
          ],
          widths=[Pt(120), Pt(180), Pt(180)])

    h2(doc, "8.2  提交 / 工程")
    table(doc,
          ["坑", "后果", "正确做法"],
          [
              ["让试验版本成为最后提交",
               "最终评测的在册 2 个里混入半成品",
               "截止前有意安排最后两次提交"],
              ["用榜单涨跌判断改动有效",
               "同方案两次提交可能差 1000 分，会被误导",
               "用反事实验证，跑 10–20 个种子"],
              ["Agent 抛异常没有兜底",
               "整局作废记 0 分",
               "加异常兜底，出错返回「什么都不做」"],
              ["提交包结构不对",
               "提交报错",
               "压缩包根目录必须有主程序文件，暴露 agent 入口"],
              ["Python 版本不合适",
               "依赖装不上，环境跑不起来",
               "用 Python 3.12；最新的 3.14 装不上依赖"],
          ],
          widths=[Pt(120), Pt(180), Pt(180)])

    doc.add_page_break()

    # ============================================================ 9
    h1(doc, "9  混淆点对照表")
    p(doc, "这一节用于开会前扫一眼，避免理解偏差。")
    table(doc,
          ["容易混淆的说法", "正确理解"],
          [
              ["「最近 2 次」是每天最近 2 次", "错。是全部提交中最近 2 次（滚动窗口）"],
              ["分数高就说明方案强", "错。可能是提交早、掉分慢，点开回放可能输很多"],
              ["分差大就更好", "错。只看胜负；分差仅在胜率打平时作正反馈信号"],
              ["榜单涨了说明我的改动有效", "错。可能是运气，必须做反事实验证"],
              ["提交次数要省着用", "错。每天 5 次，旧的自动失效，鼓励多提"],
              ["那可以随便提", "不对。截止时在册的 2 个决定最终成绩，最后两次要刻意安排"],
              ["应该先建模型", "错。先做规则；几千条回放之后再考虑建模"],
              ["从第 0 步开始优化", "错。从最后几步往前做分叉"],
              ["排行榜前列的都是强手", "不一定。可能是旧方案掉分慢"],
              ["赢 1 元和赢 5 万分不一样", "错。评分完全一样"],
          ],
          widths=[Pt(180), Pt(300)])

    # ============================================================ 10
    h1(doc, "10  每周报告建议结构")
    p(doc, "老师要求每周整理报告并抽签上台。建议固定成下面这个结构，"
           "每周围绕同一套框架更新，避免每次重想。")
    table(doc,
          ["小节", "内容"],
          [
              ["本周目标", "这一周打算解决什么问题"],
              ["做了什么", "具体改动 / 实验，一次一件事"],
              ["怎么验证的", "种子数量、对手集合（挑战集 + 回归集）"],
              ["结果", "胜率、胜率矩阵、平均分差、最差情况"],
              ["结论", "采纳 / 放弃，以及为什么"],
              ["下周计划", "下一件要改的事"],
          ],
          widths=[Pt(100), Pt(380)])
    warn(doc, "汇报时务必强调「胜负才是评分依据、分差不是」。这是评委最容易产生疑问的点，"
              "提前说清楚能避免被追问。")

    doc.save(path)
    print("wrote", path)


if __name__ == "__main__":
    build(r"D:\hiwsk\Documents\deepseek工作区\kaggriculture\Kaggriculture队员手册.docx")
