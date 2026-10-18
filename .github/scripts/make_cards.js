// 인스타용 카드 이미지(1080×1350 JPG)를 굽는다.
// app/cards.html?f=<브리프>&png=1 을 로컬 서버로 열어 .slide 를 한 장씩 캡처 → cards/YYYY-MM/<브리프 이름>/01.jpg …
// 대상: CARDS_TYPES(기본 daily) 브리프 중 최근 CARDS_DAYS(기본 3)일 안이고, 폴더가 없거나 **재료가 바뀐 것**.
//       재료 = 브리프 HTML + 렌더러(app/cards.html). 구울 때 지문을 <폴더>/source.sha1 에 남기고, 다음 실행에서 다르면 다시 굽는다
//       → 무인 실행이 카드를 고쳐 push 하면 사람이 Run workflow 를 누르지 않아도 된다(2026-10-18~).
//       CARDS_FORCE=<파일명> 이면 그 파일만 다시 굽는다.
// 실패해도 브리프·앱은 그대로 동작한다(카드 넘겨보기는 이미지 없이도 된다).
const fs = require("fs");
const path = require("path");
const http = require("http");
const crypto = require("crypto");
const { chromium } = require("playwright");

const ROOT = process.cwd();
const TYPES = (process.env.CARDS_TYPES || "daily").split(",").map(s => s.trim()).filter(Boolean);
const DAYS = Number(process.env.CARDS_DAYS || 3);
const FORCE = (process.env.CARDS_FORCE || "").trim();
const OUT = process.env.CARDS_OUT || "";
const VIS = (process.env.CARDS_VIS || "").trim();   // "ai" 면 AI 일러스트를 정보 그림보다 먼저(미리보기용)
const P = /^(\d{4})-(\d{2})-(\d{2})_([a-z]+)-brief\.html$/;

const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json" };
function serve(){
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      const u = decodeURIComponent(new URL(req.url, "http://x").pathname);
      let f = path.join(ROOT, u);
      if(!f.startsWith(ROOT)){ rsp.writeHead(403); return rsp.end(); }
      if(fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, "index.html");
      if(!fs.existsSync(f)){ rsp.writeHead(404); return rsp.end(); }
      rsp.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream" });
      fs.createReadStream(f).pipe(rsp);
    });
    srv.listen(0, "127.0.0.1", () => res(srv));
  });
}

(async () => {
  const today = new Date(Date.now() + 9 * 3600e3);   // KST
  const cutoff = new Date(today.getTime() - DAYS * 864e5).toISOString().slice(0, 10);
  const names = fs.readdirSync(ROOT);
  // 대상: {name, url, dir}. 브리프 한 편 또는 인스타 시리즈 묶음(금 week7 · 토 weekend)
  const brief = n => { const m = n.match(P); return {name: n, url: `f=${encodeURIComponent(n)}`, dir: path.join("cards", `${m[1]}-${m[2]}`, n.replace(/\.html$/, ""))}; };
  const mix = (kind, d) => ({name: `${d}_${kind}`, url: `mix=${kind}&d=${d}`, dir: path.join("cards", d.slice(0, 7), `${d}_${kind}`)});
  // 지문: 렌더러 + 재료 브리프. 묶음(week7·weekend)은 그 주(7일) 브리프 전체
  const read = n => { try { return fs.readFileSync(path.join(ROOT, n), "utf8"); } catch { return ""; } };
  const RENDER = read("app/cards.html");
  const sha = s => crypto.createHash("sha1").update(s).digest("hex");
  const fpOf = t => {
    const m = t.name.match(/^(\d{4}-\d{2}-\d{2})_(week7|weekend)$/);
    if(!m) return sha(RENDER + read(t.name));
    const lo = new Date(new Date(m[1] + "T00:00:00Z").getTime() - 6 * 864e5).toISOString().slice(0, 10);
    return sha(RENDER + names.filter(n => { const x = n.match(P); return x && `${x[1]}-${x[2]}-${x[3]}` >= lo && `${x[1]}-${x[2]}-${x[3]}` <= m[1]; }).sort().map(read).join("\n"));
  };
  const stale = t => read(path.join(t.dir, "source.sha1")).trim() !== fpOf(t);
  let targets = [];
  const FM = FORCE.match(/^(\d{4}-\d{2}-\d{2})_(week7|weekend)$/);
  if(FM) targets = [mix(FM[2], FM[1])];
  else if(FORCE) targets = names.filter(n => n === FORCE && P.test(n)).map(brief);
  else{
    names.forEach(n => {
      const m = n.match(P); if(!m) return;
      const d = `${m[1]}-${m[2]}-${m[3]}`; if(d < cutoff) return;
      if(TYPES.includes(m[4])) targets.push(brief(n));
      const wd = new Date(d + "T00:00:00Z").getUTCDay();
      // 2026-10-19~ : 토요일 메인 → 이번 주 숫자 · 금요일 여행 → 주말 뭐하지 (그 전: 금 메인 · 토 액티비티)
      const nu = d >= "2026-10-19";
      if(m[4] === "daily" && wd === (nu ? 6 : 5)) targets.push(mix("week7", d));
      if(m[4] === (nu ? "travel" : "activity") && wd === (nu ? 5 : 6)) targets.push(mix("weekend", d));
    });
    targets = targets.filter(t => !fs.existsSync(path.join(ROOT, t.dir)) || stale(t));
  }
  if(!targets.length){ console.log("cards: nothing to do"); return; }

  const srv = await serve();
  const base = `http://127.0.0.1:${srv.address().port}`;
  const browser = await chromium.launch();
  const made = [];
  try{
    for(const t of targets){
      const n = t.name, dir = t.dir;
      try{
        const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
        await page.goto(`${base}/app/cards.html?${t.url}&png=1${VIS ? "&vis=" + encodeURIComponent(VIS) : ""}`, { waitUntil: "networkidle", timeout: 60000 });
        await page.waitForSelector("body[data-ready]", { timeout: 30000 });
        const count = Number(await page.getAttribute("body", "data-ready"));
        if(!count) throw new Error("cards.html could not build cards");
        await page.waitForTimeout(500);
        fs.rmSync(path.join(ROOT, dir), { recursive: true, force: true });
        fs.mkdirSync(path.join(ROOT, dir), { recursive: true });
        const slides = await page.$$(".slide");
        for(let i = 0; i < slides.length; i++){
          const file = path.join(dir, String(i + 1).padStart(2, "0") + ".jpg");
          await slides[i].screenshot({ path: path.join(ROOT, file), type: "jpeg", quality: 88 });
        }
        fs.writeFileSync(path.join(ROOT, dir, "source.sha1"), fpOf(t) + "\n");
        // 폴더째 add — 다시 구워 장수가 줄면 옛 09.jpg 같은 파일의 삭제까지 커밋된다(게시 스크립트가 01.jpg 부터 차례로 세므로 필수)
        made.push(dir);
        console.log(`cards: ${n} → ${slides.length} images`);
        await page.close();
      }catch(e){
        console.log(`::warning::cards failed for ${n}: ${e.message}`);
      }
    }
  }finally{
    await browser.close();
    srv.close();
  }
  if(OUT && made.length) fs.writeFileSync(OUT, made.join("\n") + "\n");
})().catch(e => { console.log(`::warning::make_cards: ${e.message}`); });
