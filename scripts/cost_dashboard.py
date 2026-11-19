"""LLM 비용 대시보드 생성기.

두 가지 사용량을 한 HTML 페이지로 모읍니다.
  1) 개발한 시스템(Legacy2Next)이 Bedrock에 보낸 요청 — logs/llm_usage.jsonl (src/usage_log.py가 기록)
  2) 이 프로젝트를 만들며 Claude Code가 쓴 토큰 — ~/.claude/projects/<프로젝트>/**/*.jsonl 대화 기록

금액은 config/pricing.yaml 단가로 계산한 "예상치"입니다. 외부 호출 없이 로컬 파일만 읽습니다.

실행:
    python scripts/cost_dashboard.py            # logs/cost_dashboard.html 생성
    python scripts/cost_dashboard.py --open     # 생성 후 브라우저로 열기
    python scripts/cost_dashboard.py --claude-dir <경로>   # Claude Code 기록 폴더를 직접 지정
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SYSTEM_LOG = ROOT / "logs" / "llm_usage.jsonl"
DEFAULT_OUT = ROOT / "logs" / "cost_dashboard.html"
PRICING_PATH = ROOT / "config" / "pricing.yaml"
M = 1_000_000


def _read_jsonl(path: Path):
    """깨진 줄은 건너뛰고 dict만 돌려줍니다."""
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def _local_day(ts: str | None) -> str:
    """ISO 시각(UTC)을 이 PC의 로컬 날짜(YYYY-MM-DD)로."""
    if not ts:
        return "unknown"
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d")
    except ValueError:
        return "unknown"


# ---------------------------------------------------------------------------
# 1) 개발한 시스템
# ---------------------------------------------------------------------------
def summarize_system(log_path: Path, prices: dict[str, dict]) -> dict[str, Any]:
    by_day: dict[str, dict] = defaultdict(lambda: {"requests": 0, "cost": 0.0})
    by_stage: dict[tuple, dict] = defaultdict(
        lambda: {"requests": 0, "errors": 0, "input": 0, "output": 0, "cost": 0.0, "latency": 0.0})
    unknown_models: set[str] = set()
    total = {"requests": 0, "errors": 0, "input": 0, "output": 0, "cost": 0.0, "chat": 0, "embedding": 0}

    for r in _read_jsonl(log_path):
        model = r.get("model", "unknown")
        price = prices.get(model)
        if price is None:
            unknown_models.add(model)
            price = {"input": 0.0, "output": 0.0}
        inp, out = int(r.get("input_tokens", 0)), int(r.get("output_tokens", 0))
        cost = inp * price.get("input", 0) / M + out * price.get("output", 0) / M
        err = r.get("status") == "error"

        day = by_day[_local_day(r.get("ts"))]
        day["requests"] += 1
        day["cost"] += cost

        key = (r.get("stage", "unknown"), r.get("kind", "chat"), model)
        s = by_stage[key]
        s["requests"] += 1
        s["errors"] += err
        s["input"] += inp
        s["output"] += out
        s["cost"] += cost
        s["latency"] += r.get("latency_s") or 0.0

        total["requests"] += 1
        total["errors"] += err
        total["input"] += inp
        total["output"] += out
        total["cost"] += cost
        total[r.get("kind", "chat") if r.get("kind") in ("chat", "embedding") else "chat"] += 1

    stages = [{"stage": k[0], "kind": k[1], "model": k[2], **v,
               "avg_latency": round(v["latency"] / v["requests"], 2) if v["requests"] else 0}
              for k, v in sorted(by_stage.items(), key=lambda kv: -kv[1]["cost"])]
    return {"log_path": str(log_path), "total": total,
            "days": [{"day": d, **v} for d, v in sorted(by_day.items())],
            "stages": stages, "unknown_models": sorted(unknown_models)}


# ---------------------------------------------------------------------------
# 2) Claude Code
# ---------------------------------------------------------------------------
def default_claude_dir() -> Path:
    """Claude Code는 프로젝트 경로의 ':' '\\' '/'를 '-'로 바꾼 폴더에 대화 기록을 둡니다."""
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    slug = "".join("-" if c in ":\\/" else c for c in str(ROOT))
    return base / slug


def summarize_claude_code(claude_dir: Path, prices: dict[str, dict]) -> dict[str, Any]:
    # 스트리밍 응답은 같은 message.id가 여러 줄로 기록됩니다. id별로 출력 토큰이 가장 큰 줄 하나만 씁니다.
    messages: dict[str, dict] = {}
    session_first_prompt: dict[str, str] = {}
    for path in sorted(claude_dir.glob("**/*.jsonl")):
        is_sub = "subagents" in path.parts
        for r in _read_jsonl(path):
            msg = r.get("message")
            if not isinstance(msg, dict):
                continue
            sid = r.get("sessionId") or path.stem
            if r.get("type") == "user" and not is_sub and sid not in session_first_prompt:
                content = msg.get("content")
                text = content if isinstance(content, str) else ""
                if text and not text.lstrip().startswith("<"):
                    session_first_prompt[sid] = " ".join(text.split())[:60]
            usage = msg.get("usage")
            model = msg.get("model")
            if not usage or not model or model.startswith("<"):
                continue
            mid = msg.get("id") or f"{path}:{r.get('uuid')}"
            prev = messages.get(mid)
            if prev is None or usage.get("output_tokens", 0) >= prev["usage"].get("output_tokens", 0):
                messages[mid] = {"usage": usage, "model": model, "ts": r.get("timestamp"),
                                 "session": sid, "sub": is_sub or bool(r.get("isSidechain"))}

    comp_names = ["input", "output", "cache_write", "cache_read"]
    by_day: dict[str, dict] = defaultdict(lambda: {**{c: 0.0 for c in comp_names}, "requests": 0, "tokens": 0})
    by_model: dict[str, dict] = defaultdict(lambda: {"requests": 0, "input": 0, "output": 0,
                                                       "cache_write": 0, "cache_read": 0, "cost": 0.0})
    by_session: dict[str, dict] = defaultdict(lambda: {"requests": 0, "sub_requests": 0, "tokens": 0,
                                                         "output": 0, "cost": 0.0, "first": None, "last": None})
    unknown_models: set[str] = set()
    total = {"requests": 0, "input": 0, "output": 0, "cache_write": 0, "cache_read": 0,
             "cost": 0.0, "sub_requests": 0, "thinking": 0}

    for m in messages.values():
        u, model = m["usage"], m["model"]
        p = prices.get(model)
        if p is None:
            unknown_models.add(model)
            p = {}
        cc = u.get("cache_creation") or {}
        w5 = int(cc.get("ephemeral_5m_input_tokens", 0))
        w1 = int(cc.get("ephemeral_1h_input_tokens", 0))
        cw = int(u.get("cache_creation_input_tokens", 0))
        if w5 + w1 < cw:  # 세부 항목이 없으면 5분 캐시로 간주
            w5 += cw - (w5 + w1)
        inp, out, cr = int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)), int(u.get("cache_read_input_tokens", 0))
        mult = p.get("fast_multiplier", 1.0) if u.get("speed") == "fast" else 1.0
        cost = {
            "input": inp * p.get("input", 0) / M * mult,
            "output": out * p.get("output", 0) / M * mult,
            "cache_write": (w5 * p.get("cache_write_5m", 0) + w1 * p.get("cache_write_1h", 0)) / M * mult,
            "cache_read": cr * p.get("cache_read", 0) / M * mult,
        }
        c_sum = sum(cost.values())
        tokens = inp + out + w5 + w1 + cr

        d = by_day[_local_day(m["ts"])]
        for k in comp_names:
            d[k] += cost[k]
        d["requests"] += 1
        d["tokens"] += tokens

        bm = by_model[model]
        bm["requests"] += 1
        bm["input"] += inp
        bm["output"] += out
        bm["cache_write"] += w5 + w1
        bm["cache_read"] += cr
        bm["cost"] += c_sum

        s = by_session[m["session"]]
        s["requests"] += 1
        s["sub_requests"] += m["sub"]
        s["tokens"] += tokens
        s["output"] += out
        s["cost"] += c_sum
        ts = m["ts"] or ""
        s["first"] = min(filter(None, [s["first"], ts]), default=None)
        s["last"] = max(filter(None, [s["last"], ts]), default=None)

        total["requests"] += 1
        total["sub_requests"] += m["sub"]
        total["input"] += inp
        total["output"] += out
        total["cache_write"] += w5 + w1
        total["cache_read"] += cr
        total["cost"] += c_sum
        total["thinking"] += int((u.get("output_tokens_details") or {}).get("thinking_tokens", 0))

    prompt_side = total["input"] + total["cache_write"] + total["cache_read"]
    total["cache_hit_rate"] = total["cache_read"] / prompt_side if prompt_side else 0.0

    def _fmt_ts(ts: str | None) -> str:
        if not ts:
            return ""
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M")

    sessions = [{"session": sid[:8], "title": session_first_prompt.get(sid, ""),
                 "start": _fmt_ts(v["first"]), "end": _fmt_ts(v["last"]), **{k: v[k] for k in
                 ("requests", "sub_requests", "tokens", "output", "cost")}}
                for sid, v in sorted(by_session.items(), key=lambda kv: kv[1]["first"] or "")]
    return {"dir": str(claude_dir), "found": claude_dir.exists(), "total": total,
            "days": [{"day": d, **v} for d, v in sorted(by_day.items())],
            "models": [{"model": k, **v} for k, v in sorted(by_model.items(), key=lambda kv: -kv[1]["cost"])],
            "sessions": sessions, "unknown_models": sorted(unknown_models)}


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA__", payload)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LLM 비용 대시보드</title>
<style>
:root{
  color-scheme: light;
  --bg:#f6f6f4; --surface:#fcfcfb; --border:#e4e3df; --grid:#ecebe7;
  --text:#0b0b0b; --text2:#52514e; --muted:#8a8984;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --warn:#b45309;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --bg:#121211; --surface:#1a1a19; --border:#2e2e2c; --grid:#262624;
    --text:#f0efec; --text2:#c3c2b7; --muted:#8f8e86;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --warn:#f59e0b;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --bg:#121211; --surface:#1a1a19; --border:#2e2e2c; --grid:#262624;
  --text:#f0efec; --text2:#c3c2b7; --muted:#8f8e86;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --warn:#f59e0b;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font:14px/1.5 system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif}
main{max-width:1120px;margin:0 auto;padding:24px 16px 48px}
header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:8px}
h1{font-size:22px;margin:0}
.meta{color:var(--muted);font-size:12px}
nav{display:flex;gap:4px;margin:16px 0 20px;border-bottom:1px solid var(--border)}
nav button{all:unset;cursor:pointer;padding:8px 14px;color:var(--text2);border-bottom:2px solid transparent;margin-bottom:-1px}
nav button[aria-selected="true"]{color:var(--text);border-color:var(--text);font-weight:600}
section[hidden]{display:none}
h2{font-size:16px;margin:28px 0 10px}
.desc{color:var(--text2);margin:0 0 16px;font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tile .label{color:var(--text2);font-size:12px}
.tile .value{font-size:24px;font-weight:600;font-variant-numeric:tabular-nums;margin-top:2px}
.tile .sub{color:var(--muted);font-size:12px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-top:12px}
.card h3{font-size:14px;margin:0 0 4px}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--text2);margin:4px 0 8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.chart{position:relative;width:100%}
.chart svg{display:block;width:100%;height:240px;overflow:visible}
.tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--border);
  border-radius:8px;padding:8px 10px;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);
  white-space:nowrap;display:none;z-index:2}
.tip b{display:block;margin-bottom:2px}
.tip .row{display:flex;justify-content:space-between;gap:14px;color:var(--text2)}
.tip .row span:last-child{color:var(--text);font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 8px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}
th{color:var(--text2);font-weight:500;font-size:12px}
th:first-child,td:first-child,td.l,th.l{text-align:left}
td{font-variant-numeric:tabular-nums}
td.title{white-space:normal;min-width:220px;color:var(--text2)}
.empty{color:var(--text2);padding:18px;text-align:center;border:1px dashed var(--border);border-radius:10px;background:var(--surface)}
.note{color:var(--muted);font-size:12px;margin-top:10px}
.warn{color:var(--warn);font-size:12px;margin-top:8px}
code{font-size:12px}
</style>
</head>
<body>
<main>
<header>
  <h1>LLM 비용 대시보드</h1>
  <span class="meta" id="gen"></span>
</header>
<nav role="tablist">
  <button role="tab" data-tab="sys" aria-selected="true">개발 시스템 (Bedrock)</button>
  <button role="tab" data-tab="cc" aria-selected="false">Claude Code (개발용)</button>
</nav>
<section id="tab-sys"></section>
<section id="tab-cc" hidden></section>
</main>
<script>
const DATA = __DATA__;
const $ = (s, el=document) => el.querySelector(s);
const usd = v => v >= 100 ? "$" + v.toFixed(0) : v >= 1 ? "$" + v.toFixed(2) : "$" + v.toFixed(4);
const num = v => v.toLocaleString("ko-KR");
const tok = v => v >= 1e6 ? (v/1e6).toFixed(2) + "M" : v >= 1e3 ? (v/1e3).toFixed(1) + "K" : String(v);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

$("#gen").textContent = "생성 " + DATA.generated_at + " · 금액은 config/pricing.yaml 기준 예상치";

document.querySelectorAll("nav button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("nav button").forEach(x => x.setAttribute("aria-selected", x === b));
  $("#tab-sys").hidden = b.dataset.tab !== "sys";
  $("#tab-cc").hidden = b.dataset.tab !== "cc";
  try { localStorage.setItem("costTab", b.dataset.tab); } catch (e) {}
}));
try { const t = localStorage.getItem("costTab"); if (t) document.querySelector(`nav button[data-tab="${t}"]`)?.click(); } catch (e) {}

function tiles(items) {
  return `<div class="tiles">${items.map(t => `<div class="tile"><div class="label">${t[0]}</div>
    <div class="value">${t[1]}</div>${t[2] ? `<div class="sub">${t[2]}</div>` : ""}</div>`).join("")}</div>`;
}
function table(cols, rows) {
  return `<div class="scroll"><table><thead><tr>${cols.map(c => `<th class="${c.cls||""}">${c.h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => `<tr>${cols.map(c => `<td class="${c.cls||""}">${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

// 일별 (누적) 막대 차트. series: [{key,label,color}], rows: [{day, ...}], tipExtra(row) -> [[label, value]]
function barChart(host, rows, series, tipExtra) {
  const W = 1000, H = 240, P = {l: 56, r: 8, t: 10, b: 28};
  const totals = rows.map(r => series.reduce((s, x) => s + r[x.key], 0));
  const max = Math.max(...totals, 1e-9);
  const step = niceStep(max / 4), top = Math.ceil(max / step) * step || 1;
  const iw = W - P.l - P.r, ih = H - P.t - P.b, bw = iw / rows.length;
  const barW = Math.min(48, bw * 0.6);
  const y = v => P.t + ih - v / top * ih;
  let g = "";
  for (let v = 0; v <= top + 1e-12; v += step) {
    g += `<line x1="${P.l}" x2="${W-P.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grid)"/>
      <text x="${P.l-8}" y="${y(v)+4}" text-anchor="end" font-size="11" fill="var(--muted)">${axisUsd(v, step)}</text>`;
  }
  rows.forEach((r, i) => {
    const cx = P.l + bw * i + bw / 2;
    let acc = 0;
    const segs = series.filter(s => r[s.key] > 0);
    segs.forEach((s, j) => {
      const y0 = y(acc), y1 = y(acc + r[s.key]); acc += r[s.key];
      const h = Math.max(0, y0 - y1 - (j < segs.length - 1 ? 2 : 0));
      const isTop = j === segs.length - 1;
      g += isTop
        ? `<path d="${roundTop(cx - barW/2, y0 - (y0 - y1), barW, Math.max(h, 1), 4)}" fill="${s.color}"/>`
        : `<rect x="${cx-barW/2}" y="${y0-h}" width="${barW}" height="${h}" fill="${s.color}"/>`;
    });
    if (rows.length <= 16) g += `<text x="${cx}" y="${H-8}" text-anchor="middle" font-size="11" fill="var(--muted)">${r.day.slice(5)}</text>`;
    g += `<rect x="${P.l + bw*i}" y="${P.t}" width="${bw}" height="${ih}" fill="transparent" data-i="${i}"/>`;
  });
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img">${g}</svg><div class="tip"></div>`;
  const tip = $(".tip", host), svg = $("svg", host);
  svg.addEventListener("mousemove", e => {
    const i = e.target.dataset?.i; if (i === undefined) { tip.style.display = "none"; return; }
    const r = rows[+i];
    const lines = series.length > 1 ? series.map(s => [`<i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${s.color};margin-right:5px"></i>${s.label}`, usd(r[s.key])]) : [];
    tip.innerHTML = `<b>${r.day} · ${usd(totals[+i])}</b>` + [...lines, ...tipExtra(r)].map(([a, b]) => `<div class="row"><span>${a}</span><span>${b}</span></div>`).join("");
    const box = host.getBoundingClientRect();
    tip.style.display = "block";
    let x = e.clientX - box.left + 12; if (x + tip.offsetWidth > box.width) x = e.clientX - box.left - tip.offsetWidth - 12;
    tip.style.left = Math.max(0, x) + "px"; tip.style.top = (e.clientY - box.top - 10) + "px";
  });
  svg.addEventListener("mouseleave", () => tip.style.display = "none");
}
function axisUsd(v, step) { const d = step >= 1 ? 0 : Math.min(4, Math.ceil(-Math.log10(step))); return "$" + v.toFixed(d); }
function niceStep(raw) { const p = Math.pow(10, Math.floor(Math.log10(raw || 1e-9))); const n = raw / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; }
function roundTop(x, y, w, h, r) { r = Math.min(r, w/2, h); return `M${x},${y+h}V${y+r}Q${x},${y} ${x+r},${y}H${x+w-r}Q${x+w},${y} ${x+w},${y+r}V${y+h}Z`; }
function legend(series) { return `<div class="legend">${series.map(s => `<span><i style="background:${s.color}"></i>${s.label}</span>`).join("")}</div>`; }
function warnUnknown(list) { return list.length ? `<div class="warn">단가 미등록 모델(비용 0으로 계산): ${list.map(esc).join(", ")} — config/pricing.yaml에 추가하세요.</div>` : ""; }

// ---- 1) 개발 시스템 ----
(function () {
  const S = DATA.system, T = S.total, el = $("#tab-sys");
  let h = `<p class="desc">Legacy2Next 파이프라인이 Amazon Bedrock에 보낸 LLM·임베딩 요청입니다. 출처 <code>${esc(S.log_path)}</code></p>`;
  if (!T.requests) {
    el.innerHTML = h + `<div class="empty">아직 기록된 요청이 없습니다.<br>파이프라인·평가를 실행하면 <code>default_llm()</code> / <code>default_embeddings()</code> 호출이 자동으로 기록됩니다.</div>`;
    return;
  }
  const avg = T.requests ? T.cost / T.requests : 0;
  h += tiles([
    ["요청 수", num(T.requests), `LLM ${num(T.chat)} · 임베딩 ${num(T.embedding)}`],
    ["예상 비용", usd(T.cost), `요청당 ${usd(avg)}`],
    ["입력 토큰", tok(T.input), "임베딩은 글자 수 어림"],
    ["출력 토큰", tok(T.output), ""],
    ["실패 요청", num(T.errors), T.errors ? "스로틀링·오류 포함" : "없음"],
  ]);
  h += `<div class="card"><h3>일별 예상 비용</h3><div class="chart" id="sys-chart"></div></div>`;
  h += `<h2>단계별 사용량</h2><div class="card">` + table([
    {h: "단계(모듈)", f: r => esc(r.stage), cls: "l"},
    {h: "종류", f: r => r.kind === "embedding" ? "임베딩" : "LLM", cls: "l"},
    {h: "요청", f: r => num(r.requests)},
    {h: "실패", f: r => num(r.errors)},
    {h: "입력", f: r => tok(r.input)},
    {h: "출력", f: r => tok(r.output)},
    {h: "평균 지연", f: r => r.kind === "embedding" ? "-" : r.avg_latency + "s"},
    {h: "예상 비용", f: r => usd(r.cost)},
  ], S.stages) + warnUnknown(S.unknown_models) + `</div>`;
  el.innerHTML = h;
  barChart($("#sys-chart"), S.days, [{key: "cost", label: "비용", color: "var(--s1)"}], r => [["요청", num(r.requests)]]);
})();

// ---- 2) Claude Code ----
(function () {
  const C = DATA.claude_code, T = C.total, el = $("#tab-cc");
  let h = `<p class="desc">이 프로젝트를 구현하면서 Claude Code가 사용한 토큰입니다 (서브에이전트 포함). 금액은 Anthropic API 정가로 환산한 값이라, 구독 요금제라면 실제 청구액과 다릅니다. 출처 <code>${esc(C.dir)}</code></p>`;
  if (!T.requests) {
    el.innerHTML = h + `<div class="empty">${C.found ? "기록된 사용량이 없습니다." : "Claude Code 기록 폴더를 찾지 못했습니다. <code>--claude-dir</code>로 지정하세요."}</div>`;
    return;
  }
  const totalTok = T.input + T.output + T.cache_write + T.cache_read;
  h += tiles([
    ["API 요청 수", num(T.requests), `세션 ${C.sessions.length}개 · 서브에이전트 ${num(T.sub_requests)}`],
    ["환산 비용", usd(T.cost), `요청당 ${usd(T.cost / T.requests)}`],
    ["총 토큰", tok(totalTok), `입력 ${tok(T.input)} · 출력 ${tok(T.output)}`],
    ["캐시 적중률", (T.cache_hit_rate * 100).toFixed(1) + "%", `읽기 ${tok(T.cache_read)} · 쓰기 ${tok(T.cache_write)}`],
    ["출력 중 사고 토큰", tok(T.thinking), T.output ? ((T.thinking / T.output) * 100).toFixed(0) + "% of 출력" : ""],
  ]);
  const series = [
    {key: "cache_read", label: "캐시 읽기", color: "var(--s1)"},
    {key: "cache_write", label: "캐시 쓰기", color: "var(--s2)"},
    {key: "output", label: "출력", color: "var(--s3)"},
    {key: "input", label: "입력", color: "var(--s4)"},
  ];
  h += `<div class="card"><h3>일별 환산 비용 (항목별)</h3>${legend(series)}<div class="chart" id="cc-chart"></div></div>`;
  h += `<h2>모델별</h2><div class="card">` + table([
    {h: "모델", f: r => esc(r.model), cls: "l"},
    {h: "요청", f: r => num(r.requests)},
    {h: "입력", f: r => tok(r.input)},
    {h: "출력", f: r => tok(r.output)},
    {h: "캐시 쓰기", f: r => tok(r.cache_write)},
    {h: "캐시 읽기", f: r => tok(r.cache_read)},
    {h: "환산 비용", f: r => usd(r.cost)},
  ], C.models) + warnUnknown(C.unknown_models) + `</div>`;
  h += `<h2>세션별</h2><div class="card">` + table([
    {h: "세션", f: r => `<code>${esc(r.session)}</code>`, cls: "l"},
    {h: "시작 요청", f: r => esc(r.title || "—"), cls: "l title"},
    {h: "기간", f: r => esc(r.start + (r.end && r.end !== r.start ? " ~ " + (r.end.slice(0, 5) === r.start.slice(0, 5) ? r.end.slice(-5) : r.end) : "")), cls: "l"},
    {h: "요청", f: r => num(r.requests) + (r.sub_requests ? ` <span style="color:var(--muted)">(서브 ${r.sub_requests})</span>` : "")},
    {h: "토큰", f: r => tok(r.tokens)},
    {h: "출력", f: r => tok(r.output)},
    {h: "환산 비용", f: r => usd(r.cost)},
  ], C.sessions) + `</div>`;
  h += `<p class="note">스트리밍 응답은 같은 메시지가 여러 줄로 기록되어 message.id 기준으로 중복 제거했습니다. 대시보드는 생성 시점 스냅샷이므로 최신 값은 스크립트를 다시 실행하세요.</p>`;
  el.innerHTML = h;
  barChart($("#cc-chart"), C.days, series, r => [["요청", num(r.requests)], ["토큰", tok(r.tokens)]]);
})();
</script>
</body>
</html>
"""


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """pricing.yaml 전용 간이 파서 (들여쓰기 2칸, `키: 값` 매핑만).

    대시보드는 가상환경 밖의 기본 Python으로도 돌아가야 해서 pyyaml 없이 읽을 수 있게 둡니다.
    """
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(": ") if ": " in line else (line.strip().rstrip(":"), "", "")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if val.strip():
            try:
                parent[key] = float(val)
            except ValueError:
                parent[key] = val.strip()
        else:
            parent[key] = {}
            stack.append((indent, parent[key]))
    return root


def load_pricing() -> dict[str, Any]:
    text = PRICING_PATH.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse_simple_yaml(text)


def build(system_log: Path, claude_dir: Path) -> dict[str, Any]:
    pricing = load_pricing()
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "system": summarize_system(system_log, pricing.get("system") or {}),
        "claude_code": summarize_claude_code(claude_dir, pricing.get("claude_code") or {}),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LLM 비용 대시보드(HTML) 생성")
    ap.add_argument("--system-log", type=Path, default=DEFAULT_SYSTEM_LOG)
    ap.add_argument("--claude-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--open", action="store_true", help="생성 후 브라우저로 열기")
    args = ap.parse_args(argv)

    data = build(args.system_log, args.claude_dir or default_claude_dir())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_html(data), encoding="utf-8")

    s, c = data["system"]["total"], data["claude_code"]["total"]
    print(f"[개발 시스템] 요청 {s['requests']}건 · 예상 ${s['cost']:.4f}")
    print(f"[Claude Code] 요청 {c['requests']}건 · 출력 {c['output']:,} 토큰 · 환산 ${c['cost']:.2f}")
    print(f"→ {args.out}")
    if args.open:
        webbrowser.open(args.out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
