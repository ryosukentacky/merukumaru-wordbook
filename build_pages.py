#!/usr/bin/env python3
# Build GitHub Pages HTML for all word files in words/ into docs/.
# Quiz blocks in the Markdown (question + choices + <details> with the answer
# revealed on ChatGPT) are converted into interactive quizzes that replicate
# ChatGPT's behaviour: click a choice -> verdict + "正解：X" + explanation,
# score counter "正解数：n/3問" and a "もう一度" reset button.
import html, json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
WORDS = os.path.join(BASE, "words")
DOCS = os.path.join(BASE, "docs")

# #11/#12: ChatGPT showed no "正解：X" line; the correct choices were verified
# from the checked radio-button state during extraction (batch 3, 2026-11-26).
ANSWER_OVERRIDES = {
    "011": ["B", "B", "C"],
    "012": ["B", "B", "B"],
}

CSS = """
body{font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;max-width:760px;margin:0 auto;padding:20px;line-height:1.85;color:#222;background:#fff}
h1{font-size:25px;line-height:1.4}
h2{font-size:19px;border-left:5px solid #4a6fa5;padding-left:8px;margin-top:30px}
h3{font-size:16px;margin-top:22px}
blockquote{background:#f0f4fb;border-radius:8px;padding:10px 14px;margin:14px 0;font-size:14px}
blockquote p{margin:4px 0}
pre{background:#f6f6f6;border:1px solid #ddd;border-radius:8px;padding:10px 12px;overflow-x:auto;font-size:13.5px;line-height:1.6}
code{background:#f0f0f0;padding:1px 5px;border-radius:4px;font-size:.92em}
pre code{background:none;padding:0}
table{border-collapse:collapse;margin:12px 0}
td,th{border:1px solid #ccc;padding:5px 10px;font-size:14px}
th{background:#eef4ff}
img{max-width:100%}
.nav{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:14px;margin:10px 0}
a{color:#2f5aa8}
.q{border:1px solid #ddd;border-radius:10px;padding:12px 14px;margin:12px 0}
.q .qt{font-weight:bold}
.q button{display:block;width:100%;text-align:left;margin:6px 0;padding:10px;border:1px solid #bbb;border-radius:8px;background:#f7f7f7;font-size:15px;cursor:pointer}
.q button.ok{background:#e2f2e2;border-color:#4a8a4a}
.q button.ng{background:#fbe3e3;border-color:#c0504a}
.exp{display:none;background:#f0f4fb;border-radius:8px;padding:8px 12px;margin-top:8px;font-size:14px}
#score{font-weight:bold}
#reset{padding:9px 16px;border:1px solid #bbb;border-radius:8px;background:#f7f7f7;cursor:pointer;font-size:15px}
details{border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin:12px 0}
summary{cursor:pointer;font-weight:bold}
"""

QUIZ_JS = """
const QUIZ = __QUIZ_JSON__;
let correct = 0;
const quizEl = document.getElementById('quiz');
function updateScore(){ document.getElementById('score').textContent = '正解数：' + correct + ' / ' + QUIZ.length + '問'; }
function build(){
  quizEl.innerHTML = ''; correct = 0;
  QUIZ.forEach(item => {
    const box = document.createElement('div'); box.className = 'q';
    const t = document.createElement('div'); t.className = 'qt'; t.textContent = item.q; box.appendChild(t);
    const exp = document.createElement('div'); exp.className = 'exp';
    item.choices.forEach((c, ci) => {
      const b = document.createElement('button'); b.textContent = 'ABCDEF'[ci] + '. ' + c;
      b.onclick = () => {
        if (box.dataset.done) return; box.dataset.done = '1';
        const ok = ci === item.answer;
        if (ok) { b.classList.add('ok'); correct++; }
        else { b.classList.add('ng'); box.querySelectorAll('button')[item.answer].classList.add('ok'); }
        exp.innerHTML = '<strong>' + (ok ? '正解です！' : '正解を確認しましょう') + '</strong><br>正解：' + 'ABCDEF'[item.answer] + '<br>' + item.exp;
        exp.style.display = 'block'; updateScore();
      };
      box.appendChild(b);
    });
    box.appendChild(exp); quizEl.appendChild(box);
  });
  updateScore();
}
build();
document.getElementById('reset').onclick = build;
"""

def inline(text):
    text = html.escape(text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text

def parse_quiz(lines, i, num):
    """lines[i] is a '**Qn. ...**' line. Returns (quiz_dict, next_i) or (None, i)."""
    qm = re.match(r"\*\*(Q\d+\..*?)\*\*\s*(.*)$", lines[i])
    if not qm:
        return None, i
    qtext = qm.group(1) + ((" " + qm.group(2)) if qm.group(2) else "")
    j = i + 1
    choices = []
    while j < len(lines):
        cm = re.match(r"- ([A-F])\. (.*)$", lines[j])
        if cm:
            choices.append(cm.group(2).strip())
            j += 1
        elif lines[j].strip() == "":
            j += 1
            break
        else:
            break
    # skip blank lines, expect <details>
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    if j >= len(lines) or lines[j].strip() != "<details>":
        return None, i
    body = []
    j += 1
    while j < len(lines) and lines[j].strip() != "</details>":
        body.append(lines[j])
        j += 1
    j += 1  # consume </details>
    answer = None
    exp_lines = []
    for bl in body:
        s = bl.strip()
        if s.startswith("<summary>") or s == "":
            continue
        am = re.match(r"正解：([A-F])$", s)
        if am:
            answer = "ABCDEF".index(am.group(1))
            continue
        if s.startswith("正解："):
            # Early-era format: "正解：{correct choice text}。{explanation}"
            rest = s[len("正解："):]
            matched = None
            for ci, c in enumerate(choices):
                cn = c.rstrip("。").strip()
                if rest.rstrip("。").startswith(cn):
                    matched = ci
                    tail = rest[len(cn):].lstrip("。").strip()
                    break
            if matched is not None:
                answer = matched
                if tail:
                    exp_lines.append(tail)
                continue
            exp_lines.append(s)
            continue
        if s == "正解です！":
            continue
        exp_lines.append(s)
    if answer is None:
        ov = ANSWER_OVERRIDES.get(num)
        if ov:
            qn = int(re.match(r"Q(\d+)", qtext).group(1))
            answer = "ABCDEF".index(ov[qn - 1])
    if answer is None or not choices:
        return None, i
    exp = "<br>".join(html.escape(x) for x in exp_lines)
    return {"q": qtext, "choices": choices, "answer": answer, "exp": exp}, j

def md_to_html(lines, num):
    out = []
    quizzes = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        # footer nav line of the Markdown version -> skip (HTML nav is generated)
        if s.startswith("前：") and "目次に戻る" in s:
            i += 1
            continue
        if s == "---":
            i += 1
            continue
        # quiz block?
        if re.match(r"\*\*Q\d+\.", s):
            q, ni = parse_quiz(lines, i, num)
            if q is not None:
                quizzes.append(q)
                i = ni
                continue
        # code fence
        if s.startswith("```"):
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue
        # headings
        m = re.match(r"(#{1,3}) (.*)$", s)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        # table
        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            if len(cells) > 1 and all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells[1]):
                head, body_rows = cells[0], cells[2:]
                t = ["<table><tr>"] + [f"<th>{inline(c)}</th>" for c in head] + ["</tr>"]
                for r in body_rows:
                    t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
                t.append("</table>")
                out.append("".join(t))
            else:
                for r in cells:
                    out.append("<p>" + "｜".join(inline(c) for c in r) + "</p>")
            continue
        # blockquote
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            paras = [b for b in buf]
            out.append("<blockquote>" + "".join(f"<p>{inline(p)}</p>" if p else "" for p in paras) + "</blockquote>")
            continue
        # list
        if s.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:])
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        # leftover details block (non-quiz) -> keep native
        if s == "<details>":
            buf = [line]
            i += 1
            while i < n and lines[i].strip() != "</details>":
                buf.append(lines[i]); i += 1
            if i < n:
                buf.append(lines[i]); i += 1
            inner = []
            for b in buf:
                bs = b.strip()
                if bs.startswith("<summary>"):
                    inner.append(bs)
                elif bs in ("<details>", "</details>"):
                    inner.append(bs)
                elif bs:
                    inner.append(f"<p>{inline(bs)}</p>")
            out.append("\n".join(inner))
            continue
        if s == "":
            i += 1
            continue
        # paragraph (merge following plain lines)
        buf = [s]
        i += 1
        while i < n:
            ns = lines[i].strip()
            if ns == "" or ns.startswith(("#", "- ", "|", ">", "```", "<details>")) or ns == "---" or re.match(r"\*\*Q\d+\.", ns) or (ns.startswith("前：") and "目次に戻る" in ns):
                break
            buf.append(ns)
            i += 1
        out.append("<p>" + "<br>".join(inline(x) for x in buf) + "</p>")
    return "\n".join(out), quizzes

def main():
    os.makedirs(DOCS, exist_ok=True)
    files = sorted(f for f in os.listdir(WORDS) if f.endswith(".md"))
    entries = []
    for f in files:
        num = f[:3]
        with open(os.path.join(WORDS, f), encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), f)
        entries.append({"num": num, "file": f, "html": f[:-3] + ".html", "title": title, "lines": lines})
    for idx, e in enumerate(entries):
        body, quizzes = md_to_html(e["lines"][1:], e["num"])  # skip the '# title' line; rendered as h1
        prev = entries[idx - 1] if idx > 0 else None
        nxt = entries[idx + 1] if idx + 1 < len(entries) else None
        def nav():
            left = f'<a href="{prev["html"]}">← 前：{html.escape(prev["title"])}</a>' if prev else "<span></span>"
            right = f'<a href="{nxt["html"]}">次：{html.escape(nxt["title"])} →</a>' if nxt else "<span></span>"
            return f'<div class="nav">{left}<a href="index.html">目次に戻る</a>{right}</div>'
        quiz_html = ""
        script = ""
        if quizzes:
            quiz_html = '<div id="quiz"></div>\n<p id="score"></p>\n<button id="reset">もう一度</button>'
            # The quiz questions were consumed out of the body; insert the widget
            # right after the 理解確認 heading.
            marker = None
            for k, chunk in enumerate(body.split("\n")):
                if "理解確認" in chunk and chunk.startswith("<h2"):
                    marker = k
                    break
            if marker is not None:
                parts = body.split("\n")
                parts.insert(marker + 1, quiz_html)
                body = "\n".join(parts)
            else:
                body += "\n" + quiz_html
            script = "<script>\n" + QUIZ_JS.replace("__QUIZ_JSON__", json.dumps(quizzes, ensure_ascii=False)) + "\n</script>"
        page = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(e['title'])} ― 日本語語彙 単語帳</title>
<style>{CSS}</style>
</head>
<body>
{nav()}
<h1>{html.escape(e['title'])}</h1>
{body}
{nav()}
{script}
</body>
</html>
"""
        with open(os.path.join(DOCS, e["html"]), "w", encoding="utf-8") as fh:
            fh.write(page)
        e["nquiz"] = len(quizzes)
    # index.html
    items = "\n".join(
        f'<li><a href="{e["html"]}">{html.escape(e["title"])}</a></li>' for e in entries)
    index = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>日本語語彙 単語帳 ― 目次</title>
<style>{CSS}</style>
</head>
<body>
<h1>日本語語彙 単語帳（全{len(entries)}語）</h1>
<p>ChatGPTの会話「メルクマール解説」の全文を収めた単語帳です。各ページに、ChatGPTと同じ形式の理解確認クイズ（選択肢を押すと正解と解説が表示され、正解数とリセット付き）が付いています。</p>
<ol>
{items}
</ol>
</body>
</html>
"""
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index)
    noquiz = [e["num"] for e in entries if e["nquiz"] == 0]
    print(f"built {len(entries)} pages; pages without interactive quiz: {noquiz}")

if __name__ == "__main__":
    main()
