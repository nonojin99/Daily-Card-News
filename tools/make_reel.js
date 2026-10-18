// 오디오 릴스(1080×1920 MP4) 만들기 — 브리프 카드 + 낭독 MP3 를 문단 구간에 맞춰 넘긴다.
// 사용: node tools/make_reel.js <spec.json>
//   spec = {
//     "brief": "2026-10-18_science-brief.html",
//     "audio": "audio/2026-10/2026-10-18_science.mp3",
//     "out":   "reels/2026-10/2026-10-18_science.mp4",
//     "title": "3분 듣는 우주",             // 분야별 고정 이름(README '릴스')
//     "segments": [[0.59, 6.88, 1], [7.81, 38.66, 2], ...]   // [시작초, 끝초, 카드 번호(1=표지, 마지막=출처 장)]
//   }
// 구간은 낭독 원고의 문단 경계(긴 쉼)에 맞춘다. 문단을 빼서 길이를 줄일 수 있지만 문단 안을 자르지는 않는다.
// 릴스는 3분(180초) 이하 — 넘으면 멈춘다. 카드는 쪽수 칩을 숨기고 다시 렌더한다(문단을 빼도 번호가 건너뛰지 않게).
// 작성 환경에서 ESA 이미지가 막히면 로컬 보존본(img/…)을 쓰고, 그것도 없으면 렌더 도구와 같은 안내 그림이 들어간다.
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), { execFileSync, execSync } = require("child_process");
let pw; try { pw = require("playwright"); } catch { pw = require(path.join(execSync("npm root -g").toString().trim(), "playwright")); }
const ROOT = path.resolve(__dirname, "..");
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const GAP = 0.6, MAX = 180;
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "reel-"));
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".css": "text/css",
  ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml" };
const total = spec.segments.reduce((n, [s, e]) => n + (e - s), 0) + GAP * (spec.segments.length - 1);
if (total > MAX) { console.error(`FAIL 길이 ${total.toFixed(1)}초 > ${MAX}초 — 문단을 더 빼세요`); process.exit(1); }

const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const srv = http.createServer((q, r) => {
  const p = path.join(ROOT, decodeURIComponent(q.url.split("?")[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": TYPES[path.extname(p)] || "application/octet-stream" }); fs.createReadStream(p).pipe(r);
}).listen(0, async () => {
  const exe = ["/opt/pw-browsers/chromium"].find(x => fs.existsSync(x));
  const b = await pw.chromium.launch(exe ? { executablePath: exe } : {});
  const base = `http://localhost:${srv.address().port}`;
  // 1) 카드 렌더(쪽수 칩 숨김)
  const pg = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  await pg.route(/https:\/\/cdn\.(esawebb|esahubble)\.org\//, async rt => {
    try { await rt.fulfill({ response: await rt.fetch({ timeout: 8000 }) }); } catch { await rt.abort(); }
  });
  await pg.goto(`${base}/app/cards.html?f=${encodeURIComponent(spec.brief)}&png=1`, { waitUntil: "networkidle" });
  await pg.addStyleTag({ content: ".count{display:none!important}" });
  await pg.waitForTimeout(1200);
  const slides = await pg.$$(".slide");
  const meta = await pg.evaluate(() => ({ cat: document.querySelector(".cover .cat")?.textContent || "",
    ac: getComputedStyle(document.querySelector(".slide.cover")).backgroundColor }));
  for (let i = 0; i < slides.length; i++) await slides[i].screenshot({ path: path.join(TMP, `card${i + 1}.png`) });
  // 2) 9:16 프레임 — 위: 분야 칩 + 제목 + 날짜, 가운데: 카드, 아래: 진행 막대 + 계정·AI 음성 표시
  const d = spec.brief.slice(0, 10), wd = "일월화수목금토"[new Date(d + "T00:00:00").getDay()];
  const fr = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  const N = spec.segments.length;
  for (let k = 0; k < N; k++) {
    const img = "data:image/png;base64," + fs.readFileSync(path.join(TMP, `card${spec.segments[k][2]}.png`)).toString("base64");
    await fr.setContent(`<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;background:#f1efe8;font-family:'Noto Sans KR',sans-serif;color:#1a1a18;position:relative}
.top{position:absolute;left:97px;right:97px;top:190px;display:flex;align-items:center;gap:22px}
.cat{background:${meta.ac};color:#fff;font-weight:900;font-size:38px;padding:10px 28px;border-radius:99px}
.t{font-weight:900;font-size:50px;letter-spacing:-.02em}.dt{margin-left:auto;font-size:32px;color:#55554f;font-weight:500}
.card{position:absolute;left:97px;top:330px;width:886px;border-radius:28px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.08)}
.card img{display:block;width:100%}
.bar{position:absolute;left:97px;right:97px;top:${330 + 1108 + 34}px;height:8px;border-radius:9px;background:#e1ddd2}
.bar i{display:block;height:100%;width:${((k + 1) / N * 100).toFixed(1)}%;border-radius:9px;background:${meta.ac}}
.ft{position:absolute;left:97px;top:${330 + 1108 + 70}px;font-size:32px;color:#55554f}.ft b{color:#3d5a4c}</style></head>
<body><div class="top">${meta.cat ? `<span class="cat">${esc(meta.cat)}</span>` : ""}<span class="t">🎧 ${esc(spec.title)}</span><span class="dt">${+d.slice(5, 7)}.${+d.slice(8, 10)} ${wd}</span></div>
<div class="card"><img src="${img}"></div><div class="bar"><i></i></div>
<div class="ft"><b>@hannun.brief</b> · AI 음성 낭독(Google TTS)</div></body></html>`, { waitUntil: "networkidle" });
    await fr.screenshot({ path: path.join(TMP, `f${k}.png`) });
  }
  await b.close(); srv.close();
  // 3) 오디오: 구간을 잘라 0.6초 쉼으로 잇는다 · 영상: 구간 길이만큼 프레임
  const parts = spec.segments.map(([s, e], k) => `[0:a]atrim=${s}:${e},asetpts=PTS-STARTPTS${k < N - 1 ? `,apad=pad_dur=${GAP}` : ""}[a${k}]`);
  const filter = parts.join(";") + ";" + spec.segments.map((_, k) => `[a${k}]`).join("") + `concat=n=${N}:v=0:a=1[a]`;
  const list = spec.segments.map(([s, e], k) => `file 'f${k}.png'\nduration ${(e - s + (k < N - 1 ? GAP : 0)).toFixed(3)}`).join("\n") + `\nfile 'f${N - 1}.png'\n`;
  fs.writeFileSync(path.join(TMP, "list.txt"), list);
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", path.join(ROOT, spec.audio), "-filter_complex", filter, "-map", "[a]", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", path.join(TMP, "a.m4a")]);
  const out = path.join(ROOT, spec.out); fs.mkdirSync(path.dirname(out), { recursive: true });
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", path.join(TMP, "list.txt"), "-i", path.join(TMP, "a.m4a"),
    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "copy", "-shortest", "-movflags", "+faststart", out]);
  const dur = execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out]).toString().trim();
  console.log(`${spec.out} — ${(+dur).toFixed(1)}초, 프레임 ${N}장, 작업 폴더 ${TMP}`);
});
