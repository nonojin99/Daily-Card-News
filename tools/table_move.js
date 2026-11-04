// 순위 변동 릴스 장면(2026-10-30 사용자 요청: "월~화 주말 경기 끝나고 리뷰할 때 금요일 대비 변한 순위표를 애니메이션으로")
// 금요일 리더보드의 순위표(.cn-table data-league="EPL")와 월·화 브리프의 주말 뒤 순위표(<div class="table-move" hidden data-league="EPL" …>)를
// 팀 이름으로 맞춰, 행이 금요일 자리 → 새 자리로 미끄러지고 승점이 올라가며 ▲▼ 변동이 뜬다. 한 리그 = 한 장면.
// movePage(scene, opts) 가 1080×1920 HTML 을 돌려주고, 페이지의 window.setP(p)(0~1)로 프레임마다 진행도를 맞춘다.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ZONE_C = [[/예선/, "#86b3d9"], [/직행|챔스|챔피언스|UCL/, "#2f6d9e"], [/유로파|UEL/, "#c06a24"], [/컨퍼런스|UECL/, "#3a8a7a"], [/플레이오프/, "#de9a8f"], [/강등|탈락/, "#b8433a"]];

// 순위표 행 문자열("팀|경기|승|무|패|득실|승점 / …") → [{team, gp, gd, pts}]
function parseRows(s) {
  return s.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").split(/\s+\/\s+/).map(r => r.split("|").map(x => x.trim())).filter(r => r.length >= 7)
    .map(r => ({ team: r[0], gp: +r[1], gd: r[5].replace("−", "-"), pts: +r[6] }));
}
function zonesOf(z) {
  return (z || "").split("|").map(x => x.split(":").map(y => y.trim())).filter(x => x.length === 2).map(([r, name], k) => {
    const [lo, hi] = r.split("-").map(Number);
    return { lo, hi: hi || lo, name, c: (ZONE_C.find(([re]) => re.test(name)) || [0, ["#2f6d9e", "#c06a24", "#3a8a7a", "#b8433a"][k % 4]])[1] };
  });
}
// 두 순위표를 팀 이름으로 맞춘다. 팀 구성이 다르면 오류(이름 표기를 금요일과 같게).
function pairUp(before, after) {
  const map = new Map(before.map((r, i) => [r.team, { ...r, rank: i + 1 }]));
  const miss = after.filter(r => !map.has(r.team)).map(r => r.team);
  if (miss.length || before.length !== after.length) throw new Error(`순위표 팀 이름이 금요일과 다름: ${miss.join(", ") || "팀 수 " + before.length + " → " + after.length}`);
  return after.map((r, i) => { const b = map.get(r.team); return { team: r.team, from: b.rank, to: i + 1, p0: b.pts, p1: r.pts, g0: b.gp, gp: r.gp, gd: r.gd }; });
}

// 36팀처럼 긴 표(챔스·유로파)는 한 화면에 다 못 읽는다 → 구간(직행·플레이오프·탈락)마다 한 장면, 그 구간에 '들어간' 팀만 큰 글씨로(2026-11-04 사용자 결정: 구간별 3장 + 한국 선수 팀 강조).
// rows = pairUp 결과, zones = zonesOf, hl = {팀: "김민재"} — 장면 안 자리는 장면에 보이는 팀끼리의 상대 순서, 표시 숫자는 실제 순위.
function zoneScenes(rows, zones, hl, base) {
  return zones.map(z => {
    const sel = rows.filter(r => r.to >= z.lo && r.to <= z.hi);
    const byF = [...sel].sort((a, b) => a.from - b.from), byT = [...sel].sort((a, b) => a.to - b.to);
    const out = byT.map((r, i) => ({ ...r, from: byF.indexOf(r) + 1, to: i + 1, f0: r.from, t0: r.to, hl: (hl || {})[r.team] || "" }));
    const hs = out.filter(r => r.hl).map(r => `${r.team}(${r.hl}) ${r.f0}→${r.t0}위`);   // 첫 프레임부터 결론이 보이게 부제에 한국 선수 팀 변동을 쓴다
    return { ...base, title: `${z.name} ${z.lo}~${z.hi}위`, sub: hs.length ? hs.join(' · ') : base.sub, t: { hold0: 0.3, anim: 1.3, hold1: 2.9, fps: 30 }, rows: out, zones: [{ lo: 1, hi: out.length, name: z.name, c: z.c }] };
  }).filter(sc => sc.rows.length);
}

// scene = {league, title, sub, rows: pairUp 결과, zones}, opts = {ac, cat, label, date, handle, credit, i, n}
function movePage(sc, o) {
  const N = sc.rows.length, top = 470, H = 1230, rh = H / N;
  const PH = sc.ph || ["금요일 순위", "주말 경기 반영 중…", "주말 경기 뒤"];   // 챔스·유로파 등은 scene.ph 로 바꾼다(2026-11-03)
  const zoneOf = r => sc.zones.find(z => r >= z.lo && r <= z.hi);
  const data = JSON.stringify(sc.rows.map(r => [r.from, r.to, r.p0, r.p1, r.g0, r.gp, r.f0 || r.from, r.t0 || r.to, r.g0 === r.gp ? 1 : 0]));   // 마지막 = 아직 이번 라운드 경기 전(미경기) 표시   // 구간 장면(2026-11-04): from/to = 장면 안 자리, f0/t0 = 실제 순위(표시·▲▼)
  return `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;background:#f1efe8;font-family:'Noto Sans KR',sans-serif;color:#1a1a18;position:relative;overflow:hidden}
.top{position:absolute;left:72px;right:72px;top:150px;display:flex;align-items:center;gap:22px}
.cat{background:${o.ac};color:#fff;font-weight:900;font-size:36px;padding:10px 26px;border-radius:99px;white-space:nowrap}
.lb{font-weight:900;font-size:46px;letter-spacing:-.02em;white-space:nowrap}.dt{margin-left:auto;font-size:30px;color:#55554f;font-weight:500;white-space:nowrap}
.ttl{position:absolute;left:72px;right:72px;top:262px;font-weight:900;font-size:62px;letter-spacing:-.03em}
.sub{position:absolute;left:72px;right:72px;top:352px;font-size:30px;color:#55554f;font-weight:500;display:flex;justify-content:space-between}
.sub b{color:${o.ac};font-weight:700}
.zs{position:absolute;left:72px;top:${top}px;width:8px;height:${H}px}
.zs i{position:absolute;left:0;width:8px;border-radius:4px}
.box{position:absolute;left:96px;right:72px;top:${top - 14}px;height:${H + 28}px;background:#fff;border-radius:28px}
.r{position:absolute;left:96px;right:72px;height:${rh}px;display:grid;grid-template-columns:96px 1fr 120px 150px;align-items:center;padding:0 28px;font-size:${Math.min(36, rh * 0.55).toFixed(0)}px;font-weight:700;will-change:transform}
.r .k{color:#9a9a94;font-weight:900;text-align:center}.r .p{text-align:right;font-weight:900;font-size:1.12em}
.r .g{color:#9a9a94;font-weight:500;text-align:center;font-size:.8em}
.r .d{text-align:right;font-weight:900;font-size:.9em;opacity:0}
.r.up .d{color:#2f8a4f}.r.dn .d{color:#c0392b}.r.eq .d{color:#b9b5a8}
.r.mv{background:${o.ac}14;border-radius:14px}
.r.hl{background:#fff4d6;border-radius:14px;box-shadow:inset 0 0 0 3px #e3b341}.chip{display:inline-block;margin-left:14px;padding:2px 16px;border-radius:99px;background:#e3b341;color:#3b2a00;font-size:.62em;font-weight:900;vertical-align:2px}
.bar{position:absolute;left:72px;right:72px;top:1745px;height:8px;border-radius:9px;background:#e1ddd2}
.bar i{display:block;height:100%;width:${((o.i + 1) / o.n * 100).toFixed(1)}%;border-radius:9px;background:${o.ac}}
.ft{position:absolute;left:72px;right:72px;top:1776px;font-size:25px;color:#55554f;line-height:1.45;display:flex;justify-content:space-between;align-items:flex-start}
.ft b{color:#3d5a4c;font-size:29px}.lg{display:flex;gap:16px;font-size:22px;white-space:nowrap;flex-wrap:nowrap}.ft>span:first-child{min-width:0}.lg i{display:inline-block;width:16px;height:16px;border-radius:4px;margin-right:6px;vertical-align:-1px}</style></head>
<body><div class="top"><span class="cat">${esc(o.cat)}</span><span class="lb">${esc(o.label)}</span><span class="dt">${esc(o.date)}</span></div>
<div class="ttl">${esc(sc.title)}</div><div class="sub"><span>${esc(sc.sub)}</span><b id="ph">${esc(PH[0])}</b></div>
<div class="box"></div>
<div class="zs">${sc.zones.map(z => `<i style="top:${((z.lo - 1) * rh + rh * .18).toFixed(1)}px;height:${((z.hi - z.lo + 1) * rh - rh * .36).toFixed(1)}px;background:${z.c}"></i>`).join("")}</div>
${sc.rows.map((r, k) => `<div class="r${r.hl ? " hl" : ""}" id="r${k}"><span class="k">${r.f0 || r.from}</span><span>${esc(r.team)}${r.hl ? `<span class="chip">${esc(r.hl)}</span>` : ""}</span><span class="g">${r.g0}경기</span><span class="p"><span class="d"></span> <span class="v">${r.p0}</span></span></div>`).join("")}
<div class="bar"><i></i></div>
<div class="ft"><span><b>${esc(o.handle)}</b>${o.credit ? `<br>♪ ${esc(o.credit)}` : ""}${sc.note ? `<br>${esc(sc.note)}` : ""}</span><span class="lg">${sc.zones.filter((z, k, a) => a.findIndex(y => y.name === z.name) === k).map(z => `<span><i style="background:${z.c}"></i>${esc(z.name)}</span>`).join("")}</span></div>
<script>
(() => {   // 장면마다 같은 탭에 다시 그리므로 전역 const 를 두지 않는다(두 번째 장면의 선언이 실패해 앞 장면 데이터가 남았다)
const D=${data}, Y0=${top}, RH=${rh};
const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
window.setP=p=>{ const e=ease(Math.min(1,Math.max(0,p)));
  D.forEach(([f,t,p0,p1,g0,g1,F,T,W],k)=>{ const el=document.getElementById("r"+k), y=Y0+((f-1)+(t-f)*e)*RH;
    el.style.top=y.toFixed(1)+"px"; el.querySelector(".k").textContent=p<1?F:T;
    el.querySelector(".v").textContent=Math.round(p0+(p1-p0)*e); el.querySelector(".g").textContent=(p<.5?g0:g1)+"경기";
    el.classList.toggle("mv",!W&&F!==T&&p>0&&p<1);
    const d=el.querySelector(".d"); d.style.opacity=p>=1?1:0;
    el.className=el.className.replace(/ (up|dn|eq)/g,"")+(T<F?" up":T>F?" dn":" eq");
    d.textContent=W?"미경기":T<F?"▲"+(F-T):T>F?"▼"+(T-F):"–"; if(W){el.className=el.className.replace(/ (up|dn)/g,"")+" eq";d.style.fontSize=".62em";} });
  document.getElementById("ph").textContent=p<=0?${JSON.stringify(PH[0])}:p<1?${JSON.stringify(PH[1])}:${JSON.stringify(PH[2])}; };
window.setP(0);
})();
</script></body></html>`;
}
// 리더보드 릴스용 '큰 글씨 순위표' 장면(2026-10-30 사용자 결정 — "리더보드 세로 전체 쓰는 큰 글씨로"): 카드(1080×1350)를 줄여 넣지 않고
// 1080×1920 화면 전체에 표를 그린다. sc = {title, note, zones, raw: [[팀,경기,승,무,패,득실,승점], …]}, o = movePage 와 같은 opts
function boardPage(sc, o) {
  const N = sc.raw.length, top = 476, H = 1240, rh = H / N, fs = Math.min(40, rh * 0.56);
  const zoneOf = r => sc.zones.find(z => r >= z.lo && r <= z.hi);
  const cuts = new Set(sc.zones.flatMap(z => [z.lo - 1, z.hi]));
  const sv = v => esc(String(v).replace(/^-/, "−"));
  return `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;background:#f1efe8;font-family:'Noto Sans KR',sans-serif;color:#1a1a18;position:relative;overflow:hidden}
.top{position:absolute;left:56px;right:56px;top:150px;display:flex;align-items:center;gap:22px}
.cat{background:${o.ac};color:#fff;font-weight:900;font-size:36px;padding:10px 26px;border-radius:99px;white-space:nowrap}
.lb{font-weight:900;font-size:46px;letter-spacing:-.02em;white-space:nowrap}.dt{margin-left:auto;font-size:30px;color:#55554f;font-weight:500;white-space:nowrap}
.ttl{position:absolute;left:56px;right:56px;top:252px;font-weight:900;font-size:64px;letter-spacing:-.03em}
.sub{position:absolute;left:56px;right:56px;top:344px;font-size:29px;color:#55554f;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.box{position:absolute;left:56px;right:56px;top:${top - 62}px;height:${H + 76}px;background:#fff;border-radius:28px}
.hd,.r{position:absolute;left:56px;right:56px;display:grid;grid-template-columns:14px 70px 1fr 80px 64px 64px 64px 104px 112px;align-items:center;padding:0 24px 0 18px}
.hd{top:${top - 56}px;height:50px;font-size:24px;font-weight:700;color:#9a9a94}
.r{height:${rh.toFixed(1)}px;font-size:${fs.toFixed(0)}px;font-weight:700;border-top:1px solid #ebe8e0}
.r.cut{border-top:3px dashed #b9b5a8}
.z{width:9px;height:62%;border-radius:5px}.k{text-align:center;color:#77776f;font-weight:900}.t{padding-left:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.s{text-align:center;color:#55554f;font-weight:500;font-size:.82em}.p{text-align:center;font-weight:900;font-size:1.12em}
.bar{position:absolute;left:56px;right:56px;top:1745px;height:8px;border-radius:9px;background:#e1ddd2}
.bar i{display:block;height:100%;width:${((o.i + 1) / o.n * 100).toFixed(1)}%;border-radius:9px;background:${o.ac}}
.ft{position:absolute;left:56px;right:56px;top:1776px;font-size:25px;color:#55554f;line-height:1.45;display:flex;justify-content:space-between;align-items:flex-start;gap:20px}
.ft b{color:#3d5a4c;font-size:29px}.lg{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:6px 16px;font-size:22px;max-width:560px}.lg span{white-space:nowrap}.lg i{display:inline-block;width:16px;height:16px;border-radius:4px;margin-right:6px;vertical-align:-1px}</style></head>
<body><div class="top"><span class="cat">${esc(o.cat)}</span><span class="lb">${esc(o.label)}</span><span class="dt">${esc(o.date)}</span></div>
<div class="ttl">${esc(sc.title)}</div><div class="sub">${esc(sc.note)}</div><div class="box"></div>
<div class="hd"><span></span><span class="k" style="color:#9a9a94">#</span><span class="t">팀</span><span class="s">경기</span><span class="s">승</span><span class="s">무</span><span class="s">패</span><span class="s">득실</span><span class="p" style="font-size:24px">승점</span></div>
${sc.raw.map((r, k) => { const z = zoneOf(k + 1); return `<div class="r${cuts.has(k) && k > 0 ? " cut" : ""}" style="top:${(top + k * rh).toFixed(1)}px"><span class="z" style="background:${z ? z.c : "transparent"}"></span><span class="k">${k + 1}</span><span class="t">${esc(r[0])}</span><span class="s">${sv(r[1])}</span><span class="s">${sv(r[2])}</span><span class="s">${sv(r[3])}</span><span class="s">${sv(r[4])}</span><span class="s">${sv(r[5])}</span><span class="p">${sv(r[6])}</span></div>`; }).join("")}
<div class="bar"><i></i></div>
<div class="ft"><span><b>${esc(o.handle)}</b>${o.credit ? `<br>♪ ${esc(o.credit)}` : ""}</span><span class="lg">${sc.zones.map(z => `<span><i style="background:${z.c}"></i>${esc(z.name)}</span>`).join("")}</span></div></body></html>`;
}
module.exports = { movePage, boardPage, parseRows, zonesOf, pairUp, zoneScenes };
