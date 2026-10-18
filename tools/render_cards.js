// 카드 검토 하네스 1단계 준비 — 브리프를 app/cards.html 로 열어 인스타 카드(1080×1350)를 PNG 로 굽는다.
// 사용: node tools/render_cards.js 2026-10-18_science-brief.html [출력폴더]
//       node tools/render_cards.js "mix=weekend&d=2026-10-17" [출력폴더]   ← 인스타 시리즈 묶음(week7·weekend)
// Actions 의 make_cards.js 와 같은 렌더러를 쓰므로, push 전에 실제 게시될 모습을 미리 본다.
// 작성 환경에서 ESA 호스트가 막혀 있으면 이미지 자리에 회색 안내 그림을 넣는다(레이아웃만 확인, 2단계 보고에 명시).
const http = require("http"), fs = require("fs"), path = require("path"), { execSync } = require("child_process");
let pw; try { pw = require("playwright"); } catch { pw = require(path.join(execSync("npm root -g").toString().trim(), "playwright")); }
const ROOT = path.resolve(__dirname, ".."), F = process.argv[2];
const MIXQ = /^mix=(week7|weekend)&d=\d{4}-\d{2}-\d{2}$/.test(F || "");
const OUT = path.resolve(process.argv[3] || path.join(require("os").tmpdir(), "card-review", (F || "").replace(/\.html$/, "").replace(/[=&]/g, "_")));
if (!F || (!MIXQ && !fs.existsSync(path.join(ROOT, F)))) { console.error("브리프 파일명(레포 루트 기준) 또는 mix=week7|weekend&d=YYYY-MM-DD 를 주세요"); process.exit(2); }
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".css": "text/css",
  ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json" };
const PH = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="#3a3a44"/>' +
  '<text x="640" y="350" fill="#fff" font-size="44" text-anchor="middle">이미지 자리 (작성 환경에서 ESA 호스트 차단)</text>' +
  '<text x="640" y="410" fill="#ccc" font-size="30" text-anchor="middle">push 뒤 Actions 가 실제 이미지로 굽는다</text></svg>';
const srv = http.createServer((q, r) => {
  const p = path.join(ROOT, decodeURIComponent(q.url.split("?")[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": TYPES[path.extname(p)] || "application/octet-stream" }); fs.createReadStream(p).pipe(r);
}).listen(0, async () => {
  const exe = ["/opt/pw-browsers/chromium"].find(x => fs.existsSync(x));
  const b = await pw.chromium.launch(exe ? { executablePath: exe } : {});
  const pg = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  let blocked = 0;
  await pg.route(/https:\/\/cdn\.(esawebb|esahubble)\.org\//, async rt => {
    try { await rt.fulfill({ response: await rt.fetch({ timeout: 8000 }) }); }
    catch { blocked++; await rt.fulfill({ contentType: "image/svg+xml", body: PH }); }
  });
  await pg.goto(`http://localhost:${srv.address().port}/app/cards.html?${MIXQ ? F : "f=" + encodeURIComponent(F)}&png=1`, { waitUntil: "networkidle" });
  await pg.waitForTimeout(1500);
  fs.mkdirSync(OUT, { recursive: true });
  const els = await pg.$$(".slide");
  // 넘침 검사 — 카드 안의 글자·그림이 카드(4:5) 밖으로 나가거나 잘리면 FAIL
  const over = await pg.evaluate(() => [...document.querySelectorAll(".slide")].flatMap((sl, i) => {
    const R = sl.getBoundingClientRect();
    return [...sl.querySelectorAll("*")].filter(e => {
      const r = e.getBoundingClientRect(); if (!r.width || !r.height) return false;
      if (e.closest("svg") && e.tagName !== "svg") return false;
      return r.bottom > R.bottom + 1 || r.right > R.right + 1 || r.left < R.left - 1 || r.top < R.top - 1;
    }).slice(0, 3).map(e => `${i + 1}장: <${e.tagName.toLowerCase()} class="${e.className.baseVal ?? e.className}"> "${(e.textContent || "").trim().slice(0, 30)}"`);
  }));
  if (over.length) { console.log("FAIL 넘침:\n  " + over.join("\n  ")); process.exitCode = 1; }
  for (let i = 0; i < els.length; i++) await els[i].screenshot({ path: path.join(OUT, String(i + 1).padStart(2, "0") + ".png") });
  console.log(`${els.length}장 → ${OUT}${blocked ? ` (ESA 이미지 ${blocked}건 차단 → 안내 그림으로 대체)` : ""}`);
  await b.close(); srv.close();
});
