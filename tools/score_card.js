// 경기 결과 알림 카드 — .github/scripts/score_alert.py 가 부른다(2026-10-23~, README '스포츠 계정 → 결과 알림').
//   node tools/score_card.js <games.json> <out.jpg>
// games.json = {"date","kicker","title","src","accent","story":true,"games":[{"away","home","as","hs","note"}]}
// story=true 면 스토리 비율 1080×1920(위 250px·아래 340px 는 인스타 UI 자리라 비운다), 아니면 1080×1350.
// AI 없이 공식 기록 값만 그린다. 사진·엠블럼 없음(README '스포츠 계정' — 팀 마크 금지).
const fs = require("fs"), path = require("path"), { execSync } = require("child_process");
let pw; try { pw = require("playwright"); } catch { pw = require(path.join(execSync("npm root -g").toString().trim(), "playwright")); }
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const [inp, out] = process.argv.slice(2);
const g = JSON.parse(fs.readFileSync(inp, "utf8"));
const H = g.story ? 1920 : 1350, TOP = g.story ? 270 : 84, BOT = g.story ? 360 : 80, AC = g.accent || "#1f5f8b";
const WD = "일월화수목금토", d = new Date(g.date + "T00:00:00Z"), md = `${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일(${WD[d.getUTCDay()]})${g.dawn ? " 새벽" : ""}`;   // 유럽·미국 경기는 KST 첫 경기 날짜 + 새벽
const one = g.games.length === 1, N = g.games.length, tight = N > 5, longT = (g.title || "").length > 20;   // 긴 제목은 두 줄 — 글자를 줄이고 목록을 내린다   // 6경기 넘으면 촘촘하게(스토리 하루 일정 8경기까지)
const pre = x => `<div class="g${one ? " one" : ""} pre">${["a", "h"].map(k => `<div class="pc">
  <span class="tm">${esc(k === "a" ? x.away : x.home)}</span>
  <span class="pn">${esc(k === "a" ? x.as : x.hs)}</span>
  ${((k === "a" ? x.ast : x.hst) || []).map(l => `<span class="st">${esc(l)}</span>`).join("")}</div>`).join(`<div class="vs">vs</div>`)}
  ${x.note ? `<div class="m">${esc(x.note)}</div>` : ""}</div>`;   // 경기 전 선발: 팀 이름은 작은 알약, 투수 이름은 크게, 시즌 기록은 그 아래
const row = x => {
  if (x.pre) return pre(x);
  const aw = !x.pending && (x.win ? x.win === "a" : +x.as > +x.hs), hw = !x.pending && (x.win ? x.win === "h" : +x.hs > +x.as);   // UFC 처럼 점수 대신 '승·패'면 win 값으로   // 남은 경기는 '- : -' 로 흐리게
  return `<div class="g${one ? " one" : ""}${x.pending && !x.live && !x.pre ? " p" : ""}${x.pre ? " pre" : ""}">
  <div class="t ${aw ? "w" : hw ? "l" : ""}"><span class="n">${esc(x.away)}</span><span class="s">${esc(x.as)}</span></div>
  <div class="vs">${x.pre ? "vs" : ":"}</div>
  <div class="t r ${hw ? "w" : aw ? "l" : ""}"><span class="s">${esc(x.hs)}</span><span class="n">${esc(x.home)}</span></div>
  ${x.note ? `<div class="m">${esc(x.note)}</div>` : ""}</div>`;
};
const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:${H}px;background:${AC};color:#fff;font-family:'Noto Sans KR',sans-serif;position:relative;overflow:hidden}
.k{position:absolute;left:84px;top:${TOP}px;font-size:38px;font-weight:900;background:#fff;color:${AC};padding:10px 30px;border-radius:99px}
.dt{position:absolute;right:84px;top:${TOP + 14}px;font-size:34px;font-weight:500;opacity:.85}
.h{position:absolute;left:84px;right:84px;top:${TOP + 110}px;font-size:${longT ? 46 : one ? 66 : 56}px;font-weight:900;letter-spacing:-.02em;line-height:1.2}
.list{position:absolute;left:84px;right:84px;top:${TOP + (one ? 330 : 250) + (longT ? 40 : 0)}px;display:flex;flex-direction:column;gap:${one ? 0 : tight ? 12 : 18}px}
.g{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;background:rgba(255,255,255,.1);border-radius:26px;padding:${one ? "64px 44px 48px" : tight ? "6px 28px 6px" : "18px 34px 14px"}}
.g.p{background:rgba(255,255,255,.05)}.g.p .s,.g.p .vs{opacity:.4}
.t{display:flex;align-items:center;gap:20px;min-width:0}.t.r{justify-content:flex-end}
.n{font-size:${one ? 56 : tight ? 32 : 38}px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.s{font-size:${one ? 180 : tight ? 46 : 62}px;font-weight:900;line-height:1;letter-spacing:-.03em}
.g.one .t{flex-direction:column;gap:10px}.g.one .t.r{flex-direction:column-reverse}.g.one .n{font-size:${(Math.max(...g.games.map(x => Math.max(String(x.away).length, String(x.home).length))) > 5) ? 40 : 52}px;white-space:normal;text-align:center;word-break:keep-all;max-width:330px}
.g.pre{align-items:start}.g.pre .vs{font-size:${one ? 44 : 26}px;align-self:center}
.pc{display:flex;flex-direction:column;align-items:center;gap:${one ? 14 : 6}px;min-width:0;text-align:center}
.tm{font-size:${one ? 32 : 22}px;font-weight:700;background:rgba(255,255,255,.92);color:${AC};padding:${one ? "6px 22px" : "3px 14px"};border-radius:99px;white-space:nowrap}
.pn{font-size:${one ? 64 : 34}px;font-weight:900;letter-spacing:-.02em;line-height:1.1;word-break:keep-all}
.st{font-size:${one ? 28 : 19}px;font-weight:500;opacity:.85;white-space:nowrap}
.t.l{opacity:.45}.vs{font-size:${one ? 90 : tight ? 34 : 44}px;opacity:.6;padding:0 18px;font-weight:700}
.m{grid-column:1/-1;line-height:1.3;margin-top:${one ? 40 : tight ? 2 : 6}px;font-size:${one ? 34 : tight ? 21 : 25}px;opacity:.85;text-align:center}
.src{position:absolute;left:84px;right:84px;bottom:${BOT + 56}px;font-size:26px;opacity:.65}
.ft{position:absolute;left:84px;right:84px;bottom:${BOT}px;display:flex;justify-content:space-between;font-size:30px;opacity:.9}.ft b{font-weight:900}</style></head><body>
<div class="k">${esc(g.kicker || "⚾ 경기 종료")}</div><div class="dt">${esc(md)}</div>
<div class="h">${esc(g.title)}</div>
<div class="list">${g.games.map(row).join("")}</div>
<div class="src">${esc(g.src || "")}</div>
<div class="ft"><b>@hannun.sports</b><span>${esc(g.foot || "결과 알림")}</span></div></body></html>`;
(async () => {
  const exe = ["/opt/pw-browsers/chromium"].find(x => fs.existsSync(x));
  const b = await pw.chromium.launch(exe ? { executablePath: exe } : {});
  const p = await b.newPage({ viewport: { width: 1080, height: H } });
  await p.setContent(html, { waitUntil: "networkidle" });
  await p.screenshot({ path: out, type: "jpeg", quality: 90 });
  await b.close();
})();
