// 순위 변동 릴스 장면(2026-10-30 사용자 요청: "월~화 주말 경기 끝나고 리뷰할 때 금요일 대비 변한 순위표를 애니메이션으로")
// 금요일 리더보드의 순위표(.cn-table data-league="EPL")와 월·화 브리프의 주말 뒤 순위표(<div class="table-move" hidden data-league="EPL" …>)를
// 팀 이름으로 맞춰, 행이 금요일 자리 → 새 자리로 미끄러지고 승점이 올라가며 ▲▼ 변동이 뜬다. 한 리그 = 한 장면.
// movePage(scene, opts) 가 1080×1920 HTML 을 돌려주고, 페이지의 window.setP(p)(0~1)로 프레임마다 진행도를 맞춘다.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ZONE_C = [[/예선/, "#86b3d9"], [/챔스|챔피언스|UCL/, "#2f6d9e"], [/유로파|UEL/, "#c06a24"], [/컨퍼런스|UECL/, "#3a8a7a"], [/플레이오프/, "#de9a8f"], [/강등/, "#b8433a"]];

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

// scene = {league, title, sub, rows: pairUp 결과, zones}, opts = {ac, cat, label, date, handle, credit, i, n}
function movePage(sc, o) {
  const N = sc.rows.length, top = 470, H = 1230, rh = H / N;
  const zoneOf = r => sc.zones.find(z => r >= z.lo && r <= z.hi);
  const data = JSON.stringify(sc.rows.map(r => [r.from, r.to, r.p0, r.p1, r.g0, r.gp]));
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
.bar{position:absolute;left:72px;right:72px;top:1745px;height:8px;border-radius:9px;background:#e1ddd2}
.bar i{display:block;height:100%;width:${((o.i + 1) / o.n * 100).toFixed(1)}%;border-radius:9px;background:${o.ac}}
.ft{position:absolute;left:72px;right:72px;top:1776px;font-size:25px;color:#55554f;line-height:1.45;display:flex;justify-content:space-between;align-items:flex-start}
.ft b{color:#3d5a4c;font-size:29px}.lg{display:flex;gap:16px;font-size:22px;white-space:nowrap;flex-wrap:nowrap}.ft>span:first-child{min-width:0}.lg i{display:inline-block;width:16px;height:16px;border-radius:4px;margin-right:6px;vertical-align:-1px}</style></head>
<body><div class="top"><span class="cat">${esc(o.cat)}</span><span class="lb">${esc(o.label)}</span><span class="dt">${esc(o.date)}</span></div>
<div class="ttl">${esc(sc.title)}</div><div class="sub"><span>${esc(sc.sub)}</span><b id="ph">금요일 순위</b></div>
<div class="box"></div>
<div class="zs">${sc.zones.map(z => `<i style="top:${((z.lo - 1) * rh + rh * .18).toFixed(1)}px;height:${((z.hi - z.lo + 1) * rh - rh * .36).toFixed(1)}px;background:${z.c}"></i>`).join("")}</div>
${sc.rows.map((r, k) => `<div class="r" id="r${k}"><span class="k">${r.to}</span><span>${esc(r.team)}</span><span class="g">${r.g0}경기</span><span class="p"><span class="d"></span> <span class="v">${r.p0}</span></span></div>`).join("")}
<div class="bar"><i></i></div>
<div class="ft"><span><b>${esc(o.handle)}</b>${o.credit ? `<br>♪ ${esc(o.credit)}` : ""}</span><span class="lg">${sc.zones.filter((z, k, a) => a.findIndex(y => y.name === z.name) === k).map(z => `<span><i style="background:${z.c}"></i>${esc(z.name)}</span>`).join("")}</span></div>
<script>
(() => {   // 장면마다 같은 탭에 다시 그리므로 전역 const 를 두지 않는다(두 번째 장면의 선언이 실패해 앞 장면 데이터가 남았다)
const D=${data}, Y0=${top}, RH=${rh};
const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
window.setP=p=>{ const e=ease(Math.min(1,Math.max(0,p)));
  D.forEach(([f,t,p0,p1,g0,g1],k)=>{ const el=document.getElementById("r"+k), y=Y0+((f-1)+(t-f)*e)*RH;
    el.style.top=y.toFixed(1)+"px"; el.querySelector(".k").textContent=p<1?f:t;
    el.querySelector(".v").textContent=Math.round(p0+(p1-p0)*e); el.querySelector(".g").textContent=(p<.5?g0:g1)+"경기";
    el.classList.toggle("mv",f!==t&&p>0&&p<1);
    const d=el.querySelector(".d"); d.style.opacity=p>=1?1:0;
    el.className=el.className.replace(/ (up|dn|eq)/g,"")+(t<f?" up":t>f?" dn":" eq");
    d.textContent=t<f?"▲"+(f-t):t>f?"▼"+(t-f):"–"; });
  document.getElementById("ph").textContent=p<=0?"금요일 순위":p<1?"주말 경기 반영 중…":"주말 경기 뒤"; };
window.setP(0);
})();
</script></body></html>`;
}
module.exports = { movePage, parseRows, zonesOf, pairUp };
