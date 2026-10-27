// 릴스 요점 장용 라인 차트 장(2026-10-27 사용자 요청: "오르락 내리락 데이터 라인그래프, 전후 속보 움직임이 한눈에")
// 브리프 reel-script 문단: <p data-k="…" data-sub="…" data-dur="3.5" data-chart='{…JSON…}'>…</p>
//   chart = { yMin, yMax, ticks:[…], pts:[[x라벨, 값, (슬롯 번호)], …], marks:[{i, t, pos:"above"|"below", c:"hot"|"strong"}], events:[{slot, n}], legend:["① …", …], foot:"…" }
//   pts 의 슬롯 번호를 주면 그 칸에 찍는다(휴장일 칸을 비워 둘 수 있다). 값은 모두 브리프 카드 본문·스펙 표에 있는 것만.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function lineSvg(ch, ac) {
  const W = 920, H = ch.legend ? 560 : 700, L = 120, R = 40, T = 70, B = 70, iw = W - L - R, ih = H - T - B;
  const slots = ch.slots || ch.pts.length, sx = i => slots === 1 ? L + iw / 2 : L + iw * i / (slots - 1);
  const sy = v => T + ih * (1 - (v - ch.yMin) / (ch.yMax - ch.yMin));
  const xs = ch.pts.map((p, i) => sx(p[2] != null ? p[2] : i)), ys = ch.pts.map(p => sy(p[1]));
  const fmt = v => Number.isInteger(v) ? v.toLocaleString("en-US") : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="'Noto Sans KR',sans-serif">`;
  for (const t of ch.ticks) s += `<line x1="${L}" x2="${W - R}" y1="${sy(t).toFixed(1)}" y2="${sy(t).toFixed(1)}" stroke="#d6d2c6" stroke-width="2"/>` +
    `<text x="${L - 16}" y="${(sy(t) + 9).toFixed(1)}" font-size="28" font-weight="500" fill="#77776f" text-anchor="end">${fmt(t)}</text>`;
  for (const e of ch.events || []) {
    const x = sx(e.slot);
    s += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${T - 6}" y2="${T + ih}" stroke="#b9b5a8" stroke-width="3" stroke-dasharray="8 8"/>` +
      `<circle cx="${x.toFixed(1)}" cy="${T - 30}" r="22" fill="#1a1a18"/><text x="${x.toFixed(1)}" y="${T - 20}" font-size="28" font-weight="900" fill="#fff" text-anchor="middle">${esc(e.n)}</text>`;
  }
  s += `<polyline fill="none" stroke="${ac}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round" points="${xs.map((x, i) => `${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ")}"/>`;
  ch.pts.forEach((p, i) => { s += `<circle cx="${xs[i].toFixed(1)}" cy="${ys[i].toFixed(1)}" r="11" fill="#f1efe8" stroke="${ac}" stroke-width="6"/>`;
    s += `<text x="${xs[i].toFixed(1)}" y="${H - 22}" font-size="26" font-weight="500" fill="#55554f" text-anchor="middle">${esc(p[0])}</text>`; });
  for (const m of ch.marks || []) {
    const x = xs[m.i], y = ys[m.i], col = m.c === "hot" ? "#c0392b" : "#1a1a18", up = m.pos !== "below", anchor = m.a || "middle";
    if (m.c === "hot") s += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="15" fill="${col}"/>`;
    s += `<text x="${(x + (m.dx || 0)).toFixed(1)}" y="${(y + (up ? -26 : 48)).toFixed(1)}" font-size="${m.fs || 32}" font-weight="900" fill="${col}" text-anchor="${anchor}">${esc(m.t)}</text>`;
  }
  return s + "</svg>";
}

// 장 전체(1080×1350 패널) HTML
function chartPage({ k, sub, chart }, { ac, i, n, title }) {
  const legend = (chart.legend || []).map(t => `<div class="lg">${esc(t)}</div>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1350px;background:#f1efe8;font-family:'Noto Sans KR',sans-serif;position:relative;overflow:hidden;color:#1a1a18}
.k{position:absolute;left:80px;right:80px;top:70px;font-weight:900;font-size:76px;line-height:1.14;letter-spacing:-.03em;color:${ac};word-break:keep-all}
.sub{position:absolute;left:80px;right:80px;top:${k.length > 13 ? 255 : 175}px;font-size:36px;font-weight:700;line-height:1.35;color:#55554f;word-break:keep-all}
.ch{position:absolute;left:80px;top:${k.length > 13 ? 400 : 330}px}
.lgs{position:absolute;left:80px;right:80px;bottom:150px;display:flex;flex-direction:column;gap:12px}.lg{font-size:33px;font-weight:700;line-height:1.3;color:#1a1a18}
.foot{position:absolute;left:80px;right:80px;bottom:100px;font-size:27px;font-weight:500;color:#77776f}
.n{position:absolute;left:80px;bottom:44px;right:80px;font-size:28px;font-weight:700;color:#55554f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}</style></head>
<body><div class="k">${esc(k)}</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}<div class="ch">${lineSvg(chart, ac)}</div>
${legend ? `<div class="lgs">${legend}</div>` : ""}${chart.foot ? `<div class="foot">${esc(chart.foot)}</div>` : ""}<div class="n">${i + 1} / ${n} · ${esc(title)}</div></body></html>`;
}
module.exports = { chartPage, lineSvg };
