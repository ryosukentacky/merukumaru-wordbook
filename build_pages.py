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
.ix{border:1px solid #c9d4e6;border-radius:10px;padding:12px 14px;margin:14px 0;background:#fbfcfe}
.ix-title{font-weight:bold;margin-bottom:8px}
.ix-tabbar{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.ix-tab{padding:8px 14px;border:1px solid #bbb;border-radius:999px;background:#f0f0f0;font-size:14.5px;cursor:pointer}
.ix-tab.on{background:#4a6fa5;border-color:#4a6fa5;color:#fff}
.ix-panel{display:none}
.ix-panel.on{display:block}
.ix-diagram{background:#eef4ff;border-radius:8px;padding:8px 12px;margin-bottom:8px;font-size:14.5px}
.ix-note{font-size:13px;color:#555;margin-top:8px}
.ix input[type=range]{width:100%;margin:10px 0 2px}
.ix-scale{display:flex;justify-content:space-between;font-size:13px;color:#555}
.ix-scale .mid{flex:1;text-align:center}
.ix-state{background:#eef4ff;border-radius:8px;padding:8px 12px;margin-top:10px}
.ix-state .lab{font-weight:bold}
.ix-state p{margin:4px 0 0}
.ix-disp{font-weight:bold;margin-top:10px}
.ix-check label{display:block;margin:6px 0;font-size:15px;cursor:pointer}
.ix-foot{display:flex;gap:12px;align-items:center;margin-top:10px;flex-wrap:wrap}
.ix-count{font-weight:bold}
.ix button.act{padding:9px 16px;border:1px solid #bbb;border-radius:8px;background:#f7f7f7;cursor:pointer;font-size:15px}
.ix button.act:disabled{opacity:.45;cursor:default}
.ix-items{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.ix-chip{border:1px solid #bbb;border-radius:999px;padding:4px 12px;font-size:13.5px;background:#f7f7f7}
.ix-chip.sent{background:#e2f2e2;border-color:#4a8a4a}
.ix-msg{background:#eef4ff;border-radius:8px;padding:8px 12px;margin-top:10px;display:none}
.ix-cap{font-size:12.5px;color:#777;margin-top:8px}
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

# Interactive components (tabs / sliders / selectors / simulations / checklists)
# reproduced from the states recorded in the Markdown, driven by IX_DATA.
IX_JS = """
const IX_DATA = __IX_JSON__;
function ixTabs(root){
  const tabs = root.querySelectorAll('.ix-tab'), panels = root.querySelectorAll('.ix-panel');
  function show(k){ tabs.forEach((t,i)=>t.classList.toggle('on', i===k)); panels.forEach((p,i)=>p.classList.toggle('on', i===k)); }
  tabs.forEach((t,i)=>{ t.onclick = ()=>show(i); });
  show(parseInt(root.dataset.initial || '0', 10));
}
document.querySelectorAll('.ix-tabs, .ix-selector').forEach(ixTabs);
document.querySelectorAll('.ix-slider').forEach(root => {
  const d = IX_DATA[parseInt(root.dataset.ix, 10)];
  const input = root.querySelector('input[type=range]');
  const lab = root.querySelector('.ix-slabel'), txt = root.querySelector('.ix-stext'), disp = root.querySelector('.ix-disp');
  function nearest(v){ let best = d.states[0]; d.states.forEach(s => { if (Math.abs(s.value - v) < Math.abs(best.value - v)) best = s; }); return best; }
  function render(){
    const v = parseInt(input.value, 10);
    if (d.continuous){
      if (d.display_rule === 'split'){ disp.textContent = d.value_names[0] + '：' + (100 - v) + '% ／ ' + d.value_names[1] + '：' + v + '%'; }
      else if (d.display_rule === 'water'){ const r = 100 - v, a = Math.floor(r / 2), b = r - a; disp.textContent = '他人の田 ' + a + '% ／ 自分の田 ' + v + '% ／ 他人の田 ' + b + '%'; }
      const s = nearest(v); lab.textContent = s.label || ''; txt.textContent = s.text || '';
    } else {
      const s = d.states.find(s => s.value === v) || nearest(v);
      lab.textContent = s.label || ''; txt.textContent = s.text || '';
    }
  }
  input.oninput = render; render();
});
document.querySelectorAll('.ix-sim').forEach(root => {
  const d = IX_DATA[parseInt(root.dataset.ix, 10)];
  const groups = root.querySelectorAll('.ix-sgroup'); const out = root.querySelector('.ix-out');
  const sel = (d.initial || [0, 0]).slice();
  function render(){
    groups.forEach((g, gi) => { g.querySelectorAll('.ix-tab').forEach((b, bi) => b.classList.toggle('on', sel[gi] === bi)); });
    out.textContent = d.outcomes[sel.join(',')] || d.outcomes[String(sel[0])] || '';
  }
  groups.forEach((g, gi) => { g.querySelectorAll('.ix-tab').forEach((b, bi) => { b.onclick = () => { sel[gi] = bi; render(); }; }); });
  render();
});
document.querySelectorAll('.ix-send').forEach(root => {
  const d = IX_DATA[parseInt(root.dataset.ix, 10)];
  let mode = (d.initial && d.initial[0]) || 0, mails = 0, sent = 0;
  const modeBtns = root.querySelectorAll('.ix-mode'), act = root.querySelector('.ix-act'),
        rst = root.querySelector('.ix-rst'), st = root.querySelector('.ix-status'),
        chips = root.querySelectorAll('.ix-chip'), msg = root.querySelector('.ix-msg');
  function render(){
    modeBtns.forEach((b, i) => b.classList.toggle('on', mode === i));
    act.textContent = mode === 0 ? 'まとめて送付する' : '完成した資料を1件送付する';
    st.textContent = 'メール送信回数 ' + mails + '回 ／ 残りの資料 ' + (4 - sent) + '件 ／ 送付済み：' + sent + '/4件';
    chips.forEach((c, i) => { c.classList.toggle('sent', i < sent); c.textContent = '資料' + (i + 1) + '（' + (i < sent ? '送付済' : '未送付') + '）'; });
    act.disabled = sent >= 4;
  }
  modeBtns.forEach((b, i) => { b.onclick = () => { mode = i; mails = 0; sent = 0; msg.style.display = 'none'; render(); }; });
  act.onclick = () => {
    if (sent >= 4) return;
    if (mode === 0){ mails = 1; sent = 4; msg.textContent = '4件の資料を1回のメールで送付しました。'; }
    else { mails++; sent++; if (sent >= 4) msg.textContent = '4件の資料を4回に分けて送付しました。'; }
    if (sent >= 4) msg.style.display = 'block';
    render();
  };
  rst.onclick = () => { mails = 0; sent = 0; msg.style.display = 'none'; render(); };
  render();
});
document.querySelectorAll('.ix-check').forEach(root => {
  const d = IX_DATA[parseInt(root.dataset.ix, 10)];
  const boxes = root.querySelectorAll('input[type=checkbox]'), cnt = root.querySelector('.ix-count'),
        msg = root.querySelector('.ix-msg'), rst = root.querySelector('.ix-rst');
  function render(){
    const n = Array.from(boxes).filter(b => b.checked).length;
    cnt.textContent = n + '/' + boxes.length;
    if (d.complete_message){ const all = n === boxes.length; msg.textContent = all ? d.complete_message : ''; msg.style.display = all ? 'block' : 'none'; }
  }
  boxes.forEach(b => { b.onchange = render; });
  rst.onclick = () => { boxes.forEach(b => { b.checked = false; }); render(); };
  render();
});
"""

def esc_text(t):
    return html.escape(str(t)).replace("\n", "<br>")

def render_component(comp, idx):
    """Render one interactive component spec to static HTML wired by IX_JS."""
    t = comp.get("type")
    title = comp.get("title", "")
    note = comp.get("note", "")
    head = f'<div class="ix-title">{esc_text(title)}</div>' if title else ""
    note_h = f'<p class="ix-note">{esc_text(note)}</p>' if note else ""
    cap = '<p class="ix-cap">ChatGPTにあった要素を、記録された全状態の内容で操作できる形に再現したものです。</p>'
    if t in ("tabs", "selector"):
        cls = "ix-tabs" if t == "tabs" else "ix-selector"
        items = comp.get("tabs") or comp.get("options") or []
        btns, panels = [], []
        for it in items:
            btns.append(f'<button class="ix-tab">{esc_text(it.get("label", ""))}</button>')
            inner = ""
            if it.get("diagram"):
                inner += f'<div class="ix-diagram">{esc_text(it["diagram"])}</div>'
            inner += f'<div>{esc_text(it.get("body", it.get("text", "")))}</div>'
            panels.append(f'<div class="ix-panel">{inner}</div>')
        return (f'<div class="ix {cls}" data-initial="{comp.get("initial", 0)}">{head}'
                f'<div class="ix-tabbar">{"".join(btns)}</div>{"".join(panels)}{note_h}{cap}</div>')
    if t == "slider":
        scale = f'<span>{esc_text(comp.get("left_label", ""))}</span>'
        if comp.get("mid_label"):
            scale += f'<span class="mid">{esc_text(comp["mid_label"])}</span>'
        scale += f'<span>{esc_text(comp.get("right_label", ""))}</span>'
        formula = f'<p class="ix-note">{esc_text(comp["formula"])}</p>' if comp.get("formula") else ""
        return (f'<div class="ix ix-slider" data-ix="{idx}">{head}'
                f'<input type="range" min="{comp.get("min", 0)}" max="{comp.get("max", 0)}" step="1" value="{comp.get("initial", 0)}">'
                f'<div class="ix-scale">{scale}</div><div class="ix-disp"></div>'
                f'<div class="ix-state"><span class="ix-slabel"></span><p class="ix-stext"></p></div>'
                f'{formula}{note_h}{cap}</div>')
    if t == "simulation":
        if comp.get("mode") == "send_sim":
            return (f'<div class="ix ix-send" data-ix="{idx}">{head}'
                    '<div class="ix-tabbar"><button class="ix-tab ix-mode">一括送付</button>'
                    '<button class="ix-tab ix-mode">五月雨式</button></div>'
                    '<div class="ix-status"></div><div class="ix-items">'
                    '<span class="ix-chip"></span><span class="ix-chip"></span><span class="ix-chip"></span><span class="ix-chip"></span></div>'
                    '<div class="ix-foot"><button class="act ix-act"></button>'
                    '<button class="act ix-rst">最初からやり直す</button></div>'
                    f'<div class="ix-msg"></div>{note_h}{cap}</div>')
        groups = []
        for g in comp.get("selectors", []):
            btns = "".join(f'<button class="ix-tab">{esc_text(o)}</button>' for o in g.get("options", []))
            groups.append(f'<div class="ix-sgroup"><div>{esc_text(g.get("name", ""))}</div><div class="ix-tabbar">{btns}</div></div>')
        return (f'<div class="ix ix-sim" data-ix="{idx}">{head}{"".join(groups)}'
                f'<div class="ix-state ix-out"></div>{note_h}{cap}</div>')
    if t == "checklist":
        items = "".join(f'<label><input type="checkbox"> {esc_text(x)}</label>' for x in comp.get("items", []))
        return (f'<div class="ix ix-check" data-ix="{idx}">{head}{items}'
                '<div class="ix-foot"><span class="ix-count"></span>'
                '<button class="act ix-rst">リセット</button></div>'
                f'<div class="ix-msg"></div>{note_h}{cap}</div>')
    return ""

def insert_components(body, components):
    """Insert rendered components after the heading/paragraph their anchor names."""
    rendered = []
    for idx, comp in enumerate(components):
        rendered.append((comp, render_component(comp, idx)))
    for comp, comp_html in rendered:
        if not comp_html:
            continue
        anchor = (comp.get("anchor") or "").lstrip("#").strip()
        placed = False
        if anchor:
            m = re.search(r"<h[23]>" + re.escape(anchor) + r"</h[23]>", body)
            if m:
                body = body[:m.end()] + "\n" + comp_html + body[m.end():]
                placed = True
            else:
                key = anchor[:24]
                pos = body.find(key)
                if pos >= 0:
                    end = body.find("</p>", pos)
                    if end >= 0:
                        body = body[:end + 4] + "\n" + comp_html + body[end + 4:]
                        placed = True
        if not placed:
            print(f"WARNING: anchor not found for component {comp.get('type')} anchor={anchor!r}", file=sys.stderr)
            body += "\n" + comp_html
    return body

ABCD = ["A｜要点", "B｜詳しい解説", "C｜イメージ理解", "D｜具体例"]

def abcd_tabs(body):
    """Wrap the A/B/C/D <h2> sections (tab-era entries) into a tab switcher."""
    parts = re.split(r"(?=<h2>)", body)
    idxs = []
    for k, part in enumerate(parts):
        m = re.match(r"<h2>(.*?)</h2>", part)
        if m:
            label = re.sub(r"^[🅰🅱🅲🅳]\s*", "", m.group(1)).strip()
            if label in ABCD:
                idxs.append((ABCD.index(label), k))
    if [i for i, _ in idxs] != [0, 1, 2, 3]:
        return body, False
    ks = [k for _, k in idxs]
    if ks != [ks[0], ks[0] + 1, ks[0] + 2, ks[0] + 3]:
        return body, False
    btns = "".join(f'<button class="ix-tab">{html.escape(ABCD[i])}</button>' for i in range(4))
    panels = []
    for i in range(4):
        part = parts[ks[i]]
        content = part[part.find("</h2>") + 5:]
        panels.append(f'<div class="ix-panel">{content}</div>')
    widget = (f'<div class="ix ix-tabs" data-initial="0"><div class="ix-tabbar">{btns}</div>'
              + "".join(panels)
              + '<p class="ix-cap">ChatGPTと同じタブ切り替え形式で再現しています。</p></div>')
    new_parts = parts[:ks[0]] + [widget] + parts[ks[0] + 4:]
    return "\n".join(new_parts), True


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
    # copy images into docs/images/ so GitHub Pages (served from docs/) can serve them
    src_images = os.path.join(BASE, "images")
    if os.path.isdir(src_images):
        dst_images = os.path.join(DOCS, "images")
        os.makedirs(dst_images, exist_ok=True)
        import shutil
        for f in os.listdir(src_images):
            shutil.copyfile(os.path.join(src_images, f), os.path.join(dst_images, f))
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
        # Pages is served from docs/, so repo-root images/ is outside the site;
        # the build copies images into docs/images/ and rewrites the paths.
        body = body.replace("../images/", "images/")
        # interactive components recorded for this entry, if any
        components = []
        spec_path = os.path.join(BASE, "interactive", e["num"] + ".json")
        if os.path.exists(spec_path):
            with open(spec_path, encoding="utf-8") as fh:
                components = json.load(fh).get("components", [])
        if components:
            body = insert_components(body, components)
        # Only the tab-era entries (011-016) were A/B/C/D tabs in ChatGPT;
        # other entries show the same headings as a normal scroll.
        if e["num"] in ("011", "012", "013", "014", "015", "016"):
            body, has_abcd = abcd_tabs(body)
        else:
            has_abcd = False
        has_ix = bool(components) or has_abcd
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
        if has_ix:
            ix_script = "<script>\n" + IX_JS.replace("__IX_JSON__", json.dumps(components, ensure_ascii=False)) + "\n</script>"
            script = (script + "\n" + ix_script) if script else ix_script
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
<p>ChatGPTの会話「メルクマール解説」の全文を収めた単語帳です。各ページに、ChatGPTと同じ形式の理解確認クイズ（選択肢を押すと正解と解説が表示され、正解数とリセット付き）が付いています。また、ChatGPT側にあったタブ切り替え・スライダー・選択式・シミュレーション・チェックリストなどの要素も、記録された全状態の内容で操作できる形に再現しています。</p>
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
