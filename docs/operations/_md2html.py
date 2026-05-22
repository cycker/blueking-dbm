#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown -> Handbook HTML 转换器（仅改变表现形式，不修改文本内容）

输入：docs/operations/handbook-md/<NN>-<slug>.md
输出：docs/operations/handbook/chapters/<NN>-<slug>.html

样式约定（与 handbook/assets/style.css 配套）：
- <main class="main"> 内：crumb / page-title / page-lead / section[.section] / pager
- 章节用 <section class="section" id="..."><h2><span class="ix">N.M</span>标题</h2>...</section>
- 表格 .tbl，行内 <code>，块代码 <pre><code [class="lang-xxx"]>
- 块引用根据首个 emoji 标志映射到 .callout (info/tip/warn/danger)
- 链接里 .md -> .html
"""
import os
import re
import sys
import html as html_mod

ROOT = os.path.dirname(os.path.abspath(__file__))
MD_DIR = os.path.join(ROOT, "handbook-md")
OUT_DIR = os.path.join(ROOT, "handbook", "chapters")
HANDBOOK_DIR = os.path.join(ROOT, "handbook")

# 章节短标题（与 index.html 一致），用于 <title> 与面包屑
CHAPTER_SHORT = {
    1:  "导读与概念对照",
    2:  "集群拓扑与节点规范",
    3:  "目录与配置文件",
    4:  "单据系统（Tickets）",
    5:  "mongosh 使用指南",
    6:  "bk-dbmon 监控与备份",
    7:  "MongoDB 版本支持",
    8:  "MongoDB 工具集",
    9:  "MongoDB 日志（各版本差异）",
    10: "MongoDB 索引设计与优化",
    11: "URI 与 Read Preference",
    12: "真实业务案例",
    13: "DBM 性能视图(Grafana)",
    14: "DBHA 与故障自愈",
    15: "附录：常用命令与配置",
}

# Callout 类型映射（按首字符 emoji / 关键字判定）
def detect_callout_kind(text: str) -> str:
    t = text.lstrip()
    # warn/danger
    if t.startswith(("⚠", "🚨", "❗")):
        return "warn"
    if t.startswith(("🛑", "🔥")):
        return "danger"
    # tip / success
    if t.startswith(("✅", "🛡", "💡", "🌱", "🎯")):
        return "tip"
    # info（默认）
    return "info"


# ---------- 行内格式化 ---------- #
INLINE_CODE_RE = re.compile(r"`([^`\n]+?)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
ITALIC_RE = re.compile(r"(?<![\*\w])\*([^*\n][^*\n]*?)\*(?!\*)")

PLACEHOLDER = "\x01CODE{}\x02"


def rewrite_link(href: str) -> str:
    """./xxx.md or xxx.md(#anchor) -> xxx.html(#anchor)；外链不动。"""
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return href
    # 去掉 ./ 前缀
    if href.startswith("./"):
        href = href[2:]
    # 把 .md 替换为 .html（保留 #anchor）
    if ".md" in href:
        head, sep, tail = href.partition("#")
        head = re.sub(r"\.md$", ".html", head)
        href = head + (("#" + tail) if sep else "")
    return href


def render_inline(text: str) -> str:
    """处理行内：代码、链接、加粗、斜体。其他文本做 HTML 转义。"""
    # 1) 抽取行内 code，避免被其他规则破坏
    codes = []

    def stash_code(m):
        codes.append(m.group(1))
        return PLACEHOLDER.format(len(codes) - 1)

    text = INLINE_CODE_RE.sub(stash_code, text)

    # 2) 抽取链接
    links = []

    def stash_link(m):
        label, href = m.group(1), m.group(2)
        links.append((label, rewrite_link(href)))
        return f"\x03LNK{len(links)-1}\x04"

    text = LINK_RE.sub(stash_link, text)

    # 3) escape HTML
    text = html_mod.escape(text, quote=False)

    # 4) bold / italic
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = ITALIC_RE.sub(r"<em>\1</em>", text)

    # 5) 还原链接（label 再 escape，href 不 escape）
    def unstash_link(m):
        idx = int(m.group(1))
        label, href = links[idx]
        # label 内可能还含格式（粗体等），递归处理一次（不会再有 link/code 因为已被抽走）
        # 简单做：bold/italic 再处理
        lab = html_mod.escape(label, quote=False)
        lab = BOLD_RE.sub(r"<strong>\1</strong>", lab)
        lab = ITALIC_RE.sub(r"<em>\1</em>", lab)
        return f'<a href="{href}">{lab}</a>'

    text = re.sub(r"\x03LNK(\d+)\x04", unstash_link, text)

    # 6) 还原行内 code
    def unstash_code(m):
        idx = int(m.group(1))
        return f"<code>{html_mod.escape(codes[idx], quote=False)}</code>"

    text = re.sub(r"\x01CODE(\d+)\x02", unstash_code, text)
    return text


# ---------- 块级解析 ---------- #
def slugify(s: str) -> str:
    """生成 section id：去掉空白 + 标点，保留中文/英文/数字/-。"""
    s = s.strip().lower()
    s = re.sub(r"[\s（）()【】《》『』〔〕、：:，,。.!！?？/&+*@#$%^~`\"'<>·\\]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "section"


def parse_table(lines, i):
    """从 lines[i] 开始解析 GFM 表格，返回 (html, next_i)。约定 lines[i] 是表头行。"""
    header = lines[i]
    sep = lines[i + 1] if i + 1 < len(lines) else ""
    if not re.match(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", sep):
        return None
    def split_row(row):
        row = row.strip()
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        return [c.strip() for c in row.split("|")]

    headers = split_row(header)
    body = []
    j = i + 2
    while j < len(lines):
        ln = lines[j]
        if not ln.strip() or ln.lstrip().startswith("#"):
            break
        if "|" not in ln:
            break
        body.append(split_row(ln))
        j += 1

    out = ['<table class="tbl"><thead><tr>']
    for h in headers:
        out.append(f"<th>{render_inline(h)}</th>")
    out.append("</tr></thead><tbody>")
    for row in body:
        # 行单元格数补齐
        while len(row) < len(headers):
            row.append("")
        out.append("<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in row[:len(headers)]) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out), j


def parse_code_block(lines, i):
    """从 lines[i] (=```lang) 开始解析围栏代码块，返回 (html, next_i)。"""
    fence = lines[i].rstrip()
    m = re.match(r"^(```+)(.*)$", fence)
    if not m:
        return None
    fence_marker = m.group(1)
    lang = m.group(2).strip()
    j = i + 1
    buf = []
    while j < len(lines):
        if lines[j].rstrip().startswith(fence_marker) and re.match(r"^`{3,}\s*$", lines[j].rstrip()):
            break
        buf.append(lines[j])
        j += 1
    code = "\n".join(buf)
    code_escaped = html_mod.escape(code, quote=False)
    cls = f' class="language-{lang}"' if lang else ""
    html = f"<pre><code{cls}>{code_escaped}</code></pre>"
    return html, j + 1  # 跳过结束围栏


def parse_list(lines, i):
    """解析 ul/ol（支持嵌套靠两个空格缩进；这里只支持一级简单实现，足够当前文档）。"""
    first = lines[i]
    ordered = bool(re.match(r"^\s*\d+\.\s+", first))
    items = []
    pat = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")
    j = i
    while j < len(lines):
        ln = lines[j]
        if not ln.strip():
            # 列表内允许单空行；下一行若不是列表则结束
            if j + 1 < len(lines) and pat.match(lines[j + 1]):
                j += 1
                continue
            break
        m = pat.match(ln)
        if not m:
            break
        items.append(m.group(1).rstrip())
        j += 1
    tag = "ol" if ordered else "ul"
    html = f"<{tag}>" + "".join(f"<li>{render_inline(it)}</li>" for it in items) + f"</{tag}>"
    return html, j


def parse_blockquote(lines, i):
    """解析连续 > 行；按首行 emoji 映射 callout 变体。"""
    j = i
    body_lines = []
    while j < len(lines) and lines[j].lstrip().startswith(">"):
        ln = lines[j].lstrip()
        # 去掉前导 '>' 和后面的一个空格
        ln = ln[1:]
        if ln.startswith(" "):
            ln = ln[1:]
        body_lines.append(ln)
        j += 1
    # 把 body_lines 当作一个独立的小型 markdown 文档解析（支持段/列表/代码块）
    inner_html = render_blocks(body_lines, in_callout=True)
    kind = detect_callout_kind("\n".join(body_lines))
    icon_map = {"info": "💡", "tip": "✅", "warn": "⚠️", "danger": "🛑"}
    ico = icon_map.get(kind, "💡")
    html = (
        f'<div class="callout {kind}">'
        f'<div class="ico">{ico}</div>'
        f'<div class="body">{inner_html}</div>'
        f'</div>'
    )
    return html, j


def render_blocks(lines, in_callout=False):
    """把若干行渲染为 HTML 串（用于 main 主体内 / callout body 内）。"""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        # 水平线
        if re.match(r"^-{3,}\s*$", s):
            i += 1
            continue
        # 围栏代码块
        if s.startswith("```"):
            r = parse_code_block(lines, i)
            if r:
                html, ni = r
                out.append(html)
                i = ni
                continue
        # 表格
        if "|" in s and i + 1 < n and re.match(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", lines[i + 1]):
            r = parse_table(lines, i)
            if r:
                html, ni = r
                out.append(html)
                i = ni
                continue
        # 块引用
        if s.startswith(">"):
            html, ni = parse_blockquote(lines, i)
            out.append(html)
            i = ni
            continue
        # 列表
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", ln):
            html, ni = parse_list(lines, i)
            out.append(html)
            i = ni
            continue
        # 标题（仅 callout 内可能出现 #；主体内 H2/H3 由外层处理 section，这里用作回退）
        m = re.match(r"^(#{2,6})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            out.append(f"<h{level}>{render_inline(title)}</h{level}>")
            i += 1
            continue
        # 段落：吸收到下一空行/特殊块
        para = [ln]
        i += 1
        while i < n:
            nxt = lines[i]
            if not nxt.strip():
                break
            ns = nxt.strip()
            if (ns.startswith(("```", ">"))
                or re.match(r"^-{3,}\s*$", ns)
                or re.match(r"^(#{1,6})\s+", ns)
                or re.match(r"^\s*(?:[-*]|\d+\.)\s+", nxt)
                or ("|" in ns and i + 1 < n and re.match(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", lines[i + 1]))):
                break
            para.append(nxt)
            i += 1
        text = " ".join(p.rstrip() for p in para)
        out.append(f"<p>{render_inline(text)}</p>")
    return "".join(out)


# ---------- 顶层文档解析 ---------- #
H1_RE = re.compile(r"^#\s+(.*)$")
H2_RE = re.compile(r"^##\s+(.*)$")
H3_RE = re.compile(r"^###\s+(.*)$")

PAGER_RE = re.compile(r"(?:[⬅←➡→]|上一章|下一章|返回目录|返回索引|返回首页).*\[[^\]]+\]\([^)]+\)|\[[^\]]+\]\([^)]+\)\s*[｜|│]\s*\[[^\]]+\]\([^)]+\)")


def _is_pager_line(line: str) -> bool:
    """判断一行是否是章末导航 pager 行：至少 2 个链接 + 含导航语义标志。"""
    links = re.findall(r"\[[^\]]+\]\([^)]+\)", line)
    if len(links) < 2:
        return False
    if re.search(r"[⬅←➡→]|上一章|下一章|返回目录|返回索引|返回首页|返回主页", line):
        return True
    return False


def split_top(md: str):
    """把整篇 md 切分为：title / lead / sections[(h2_title, body_lines)] / pager_html"""
    lines = md.replace("\r\n", "\n").split("\n")
    n = len(lines)
    # 1) 找 H1
    title = ""
    i = 0
    while i < n and not lines[i].strip():
        i += 1
    if i < n:
        m = H1_RE.match(lines[i].strip())
        if m:
            title = m.group(1).strip()
            i += 1
    # 2) lead：紧跟 H1 的第一段（非空段，可能是 > 引用，或普通段落）
    while i < n and not lines[i].strip():
        i += 1
    lead_html = ""
    if i < n and lines[i].lstrip().startswith(">") and not (i + 1 < n and H2_RE.match(lines[i + 1].strip() if lines[i + 1].strip() else "")):
        # 把整个引用块当 lead 段（去掉 emoji 类型，单纯渲染为 page-lead 段落）
        j = i
        buf = []
        while j < n and lines[j].lstrip().startswith(">"):
            ln = lines[j].lstrip()[1:]
            if ln.startswith(" "):
                ln = ln[1:]
            buf.append(ln)
            j += 1
        lead_html = render_inline(" ".join(b.strip() for b in buf if b.strip()))
        i = j
    # 3) 找出末尾 pager 行（容忍前置 "---"、空行、"## 章节导航" 这类小标题）
    pager_html = ""
    end = n
    while end > i and not lines[end - 1].strip():
        end -= 1
    if end > i and _is_pager_line(lines[end - 1]):
        pager_line = lines[end - 1]
        end -= 1
        # 向上吞掉空行 / --- 分隔线 / "## 章节导航" 这种导航小标题
        while end > i:
            tail = lines[end - 1].strip()
            if not tail:
                end -= 1
                continue
            if re.match(r"^-{3,}$", tail):
                end -= 1
                continue
            if re.match(r"^#{1,6}\s+(章节导航|导航|本章导航)\s*$", tail):
                end -= 1
                continue
            break
        pager_html = build_pager(pager_line)
    # 4) 把剩余 [i:end) 切成多个 section（按 H2）
    sections = []
    # 先扫到第一个 H2 之间的“概述段”（如果有）
    overview = []
    k = i
    while k < end and not H2_RE.match(lines[k].strip()):
        overview.append(lines[k])
        k += 1
    # 解析 overview（不放入 section，直接在 main 顶部输出）
    overview_html = render_blocks(overview)
    # 切 section
    while k < end:
        m = H2_RE.match(lines[k].strip())
        if not m:
            k += 1
            continue
        h2_title = m.group(1).strip()
        body = []
        k += 1
        while k < end and not H2_RE.match(lines[k].strip()):
            body.append(lines[k])
            k += 1
        sections.append((h2_title, body))
    return title, lead_html, overview_html, sections, pager_html


def build_pager(pager_line: str) -> str:
    """解析 [⬅ 上一章](./xx.md) ｜ [返回目录](./README.md) ｜ [下一章 ➡](./yy.md) → .pager 卡片"""
    parts = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", pager_line)
    prev = nxt = home = None
    for label, href in parts:
        h = rewrite_link(href)
        if "⬅" in label or "←" in label or "上一章" in label:
            prev = (label, h)
        elif "➡" in label or "→" in label or "下一章" in label:
            nxt = (label, h)
        else:
            home = (label, h)
    out = ['<nav class="pager">']
    if prev:
        out.append(
            f'<a href="{prev[1]}"><span class="arrow">⬅</span>'
            f'<span><span class="lbl">PREV</span><span class="ttl">{html_mod.escape(prev[0], quote=False)}</span></span></a>'
        )
    else:
        out.append('<span></span>')
    if nxt:
        out.append(
            f'<a class="next" href="{nxt[1]}">'
            f'<span><span class="lbl">NEXT</span><span class="ttl">{html_mod.escape(nxt[0], quote=False)}</span></span>'
            f'<span class="arrow">➡</span></a>'
        )
    else:
        out.append('<span></span>')
    out.append('</nav>')
    return "".join(out)


def section_html(h2_title: str, body_lines, chno: int):
    """把单个 ## section 渲染成 <section class="section">..."""
    # 抽取标题前缀编号：支持 N.M / N / A.1 / 7.0 等
    m = re.match(r"^([A-Za-z\d]+(?:\.[A-Za-z\d]+)?)\s+(.*)$", h2_title)
    if m:
        ix = m.group(1)
        rest = m.group(2)
    else:
        # 对“案例总览/工单全景概览”等无显式编号的小节，回退显示章节号
        ix = str(chno)
        rest = h2_title
    sid = slugify(h2_title)
    body_html = render_blocks(body_lines)
    return (
        f'<section class="section" id="{sid}">'
        f'<h2><span class="ix">{html_mod.escape(ix, quote=False)}</span>{render_inline(rest)}</h2>'
        f'{body_html}'
        f'</section>'
    )


# ---------- 整页拼装 ---------- #
PAGE_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title_doc} | MongoDB 手册</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../assets/style.css?v=20260521b" />
</head>
<body>
<div class="layout">
  <aside class="sidebar"></aside>
  <main class="main">
    <nav class="crumb"><a href="../index.html">🏠 首页</a><span class="sep">/</span><span>第 {chno} 章</span><span class="sep">/</span><span style="color:#cbd5e1">{title}</span></nav>
    <h1 class="page-title">{title}</h1>
{lead_block}{overview_block}{sections_html}{pager_html}
  </main>
</div>
<script src="../assets/app.js?v=20260521b"></script>
<script>HandbookInit({{ activeId:'ch{chno02}' }});</script>
</body>
</html>
"""


def convert_one(md_path: str, html_path: str, chno: int):
    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read()
    title, lead_html, overview_html, sections, pager_html = split_top(md)
    if not title:
        short = CHAPTER_SHORT.get(chno, f"第 {chno} 章")
        title = f"第 {chno} 章 · {short}"
    # 浏览器 <title> 与页面 <h1> 保持一致：均使用 md H1
    title_doc = title

    lead_block = f'    <p class="page-lead">{lead_html}</p>\n' if lead_html else ""
    overview_block = overview_html or ""
    sec_html = "".join(section_html(h, b, chno) for (h, b) in sections)

    page = PAGE_TPL.format(
        title_doc=html_mod.escape(title_doc, quote=False),
        title=html_mod.escape(title, quote=False),
        chno=chno,
        chno02=f"{chno:02d}",
        lead_block=lead_block,
        overview_block=overview_block,
        sections_html=sec_html,
        pager_html=pager_html,
    )
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)




REDIRECT_TPL = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Redirecting…</title>
<meta http-equiv="refresh" content="0; url=chapters/{name}">
<link rel="canonical" href="chapters/{name}">
<script>location.replace('chapters/{name}' + location.search + location.hash);</script>
</head>
<body>
<p>正在跳转到 <a href="chapters/{name}">chapters/{name}</a> …</p>
</body>
</html>
"""


def write_root_redirects():
    """为 chapters/NN-slug.html 在 handbook/ 根目录生成同名重定向页。"""
    if not os.path.isdir(OUT_DIR):
        return
    for fn in sorted(os.listdir(OUT_DIR)):
        if not re.match(r"^\d{2}-[a-z0-9-]+\.html$", fn):
            continue
        out = os.path.join(HANDBOOK_DIR, fn)
        with open(out, "w", encoding="utf-8") as f:
            f.write(REDIRECT_TPL.format(name=fn))
        print(f"↪ redirect: handbook/{fn} -> chapters/{fn}")


def main(argv):
    files = []
    if len(argv) > 1:
        files = argv[1:]
    else:
        for fn in sorted(os.listdir(MD_DIR)):
            m = re.match(r"^(\d{2})-([a-z0-9-]+)\.md$", fn)
            if not m:
                continue
            files.append(os.path.join(MD_DIR, fn))
    for md_path in files:
        fn = os.path.basename(md_path)
        m = re.match(r"^(\d{2})-([a-z0-9-]+)\.md$", fn)
        if not m:
            print(f"skip: {fn}")
            continue
        chno = int(m.group(1))
        out = os.path.join(OUT_DIR, fn.replace(".md", ".html"))
        convert_one(md_path, out, chno)
        print(f"✓ {fn} -> {os.path.relpath(out, ROOT)}")
    write_root_redirects()


if __name__ == "__main__":
    main(sys.argv)
