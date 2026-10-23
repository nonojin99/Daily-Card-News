// 오디오 릴스(1080×1920 MP4) 만들기 — 브리프 카드 + 낭독 MP3 를 문단 구간에 맞춰 넘긴다.
//
//   node tools/make_reel.js <spec.json>            구간을 직접 지정 (spec 형식은 아래)
//   node tools/make_reel.js --auto <브리프.html>     구간 자동 계산 → reels/YYYY-MM/<날짜>_<종류>.mp4 + .reel.json
//   node tools/make_reel.js --recent                 Actions 용: 최근 3일 릴스 대상 브리프 중 없거나 재료가 바뀐 것만 (REELS_OUT 에 만든 파일 목록)
//
//   spec = { "brief", "audio", "out", "title", ("bgm": {"src", "credit"}), "segments": [[시작초, 끝초, 슬라이드 번호(1=표지, 마지막=출처 장), (1이면 다음 구간과 쉼 없이 이어짐)], …] }
//
// 구간 규칙(README '릴스'): 문단 단위로만 자르고 문단 안은 자르지 않는다. 180초 이하 — 넘으면 가장 긴 본문 문단부터 통째로 뺀다
// (끝인사·날씨 문단은 남긴다).
// 2026-10-23~ 첫 문단("M월 D일 X요일, ○○ 브리프입니다")은 릴스에서 뺀다 — 영상은 첫 프레임부터 카드 1번(그림 포함)과 그 카드의 낭독으로 시작한다.
// 이유: 주말 릴스 평균 시청 1초 — 날짜·인사 구간에서 다 넘겼다. 본문 문단이 하나뿐인 원고(여행·액티비티)는 그 문단을 카드 수만큼 나눠 넘기고, 출처 장은 끝에 2초 무음으로 붙인다. 문단 시간은 make_audio.py 가 남긴 audio/…/<이름>.json, 없으면 원고 글자 수 비율 → 가까운 긴 쉼.
// '맥락 읽기'(사건·사고·재난) 카드가 있는 브리프는 만들지 않는다. 카드는 쪽수 칩을 숨기고 다시 렌더한다(문단을 빼도 번호가 안 건너뛰게).
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), crypto = require("crypto");
const { execFileSync, execSync, spawnSync } = require("child_process");
let pw; try { pw = require("playwright"); } catch { pw = require(path.join(execSync("npm root -g").toString().trim(), "playwright")); }
const ROOT = path.resolve(__dirname, "..");
const GAP = 0.35, MAX = 180, FIT = 178, OUTRO = 2;   // 문단 사이 쉼 0.6 → 0.35초(2026-10-23, 빨리 넘기기)
// 재생 속도(2026-10-23 사용자 요청: 1.2배로 빨리 읽고 빨리 넘기기). atempo 라 음높이는 그대로. 원고 시간 × 1/SPEED = 영상 시간.
const SPEED = +(process.env.REEL_SPEED || 1.2);
const BRIEF = /^(\d{4})-(\d{2})-(\d{2})_([a-z]+)-brief\.html$/;
const TITLE = { ai: "듣는 AI", sports: "듣는 스포츠", football: "주말 축구 결산", baseball: "듣는 야구", science: "듣는 우주", activity: "듣는 주말", travel: "듣는 여행",
  daily: "듣는 뉴스", culture: "듣는 문화", music: "듣는 음악" };
// 릴스 대상: 인스타 게시일에 맞춘다 — 월 ai · 화 sports · 금(전날 목 activity) · 토 music(2026-10-21~, 메인 대신) · 일 science (README '인스타그램 운영')
// 스포츠는 매일 발행으로 바뀌어도(스포츠 계정) 릴스는 화(지금 주간)·월(주말 결산)만 — README '스포츠 계정'
const REEL_OF = (type, wd) => ["ai", "science", "activity"].includes(type) || (type === "sports" && (wd === 1 || wd === 2)) || (type === "football" && wd === 1) || (type === "music" && wd === 6);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".json": "application/json", ".css": "text/css",
  ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml" };
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const read = p => fs.readFileSync(path.join(ROOT, p));
const sha = (...xs) => { const h = crypto.createHash("sha1"); xs.forEach(x => h.update(x)); return h.digest("hex"); };
const kstToday = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
const wdOf = d => new Date(d + "T00:00:00Z").getUTCDay();
// 배경음(README '음악 브리프 — 음원'): <div class="reel-bgm" hidden data-src="…" data-credit="…"> — 퍼블릭 도메인·CC0·CC BY 녹음만.
// data-src 는 Wikimedia Commons 원본(upload.wikimedia.org) 또는 저장소 안 audio/pd/ 경로. 낭독 아래에 작게 깐다.
const BGM_OK = /^(https:\/\/upload\.wikimedia\.org\/wikipedia\/commons\/|audio\/pd\/)/;
const BGM_VOL = 0.12;
function bgmOf(html) {
  const t = (html.match(/<div class="reel-bgm"[^>]*>/) || [])[0]; if (!t) return null;
  const at = k => ((t.match(new RegExp(`${k}="([^"]*)"`)) || [])[1] || "").replace(/&amp;/g, "&");
  const src = at("data-src"), credit = at("data-credit");
  return BGM_OK.test(src) && credit ? { src, credit } : null;
}
async function bgmFile(bgm, tmp) {
  if (!/^https:/.test(bgm.src)) return path.join(ROOT, bgm.src);
  const r = await fetch(bgm.src, { headers: { "User-Agent": "Daily-Card-News reel maker (https://github.com/nonojin99/Daily-Card-News)" } });
  if (!r.ok) throw new Error(`배경음 내려받기 실패 ${r.status}`);
  const f = path.join(tmp, "bgm" + (path.extname(new URL(bgm.src).pathname) || ".ogg"));
  fs.writeFileSync(f, Buffer.from(await r.arrayBuffer()));
  return f;
}

// 원고 문단(낭독 원고 <details class="audio-script"> 의 <p>)
function scriptParas(html) {
  const m = html.match(/<details class="audio-script">([\s\S]*?)<\/details>/);
  if (!m) return [];
  return [...m[1].matchAll(/<p>([\s\S]*?)<\/p>/g)].map(x => x[1].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim()).filter(Boolean);
}
// 첫 장면 '훅 카드' 재료 — 첫 카드의 짧은 제목(cn-t 2줄) + 큰 숫자(cn-num, 제목에 이미 있는 값이면 뺀다).
// 2026-10-19 인사이트: 릴스 3편 모두 평균 시청 2초·건너뛰기 85~91% → 첫 화면을 작은 표지 대신 꽉 찬 큰 글씨로 바꾼다.
function hookOf(html) {
  const a = html.match(/<article class="card"[^>]*>([\s\S]*?)<\/article>/); if (!a) return null;
  const strip = x => x.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();
  const t = a[1].match(/<p class="cn-t">([\s\S]*?)<\/p>/); if (!t) return null;
  const lines = t[1].split(/<br\s*\/?>/).map(strip).filter(Boolean);
  const n = a[1].match(/<p class="cn-num">([\s\S]*?)<\/p>/);
  let num = null, label = "";
  if (n) { [num, label = ""] = strip(n[1]).split("|"); if (lines.join("").replace(/\s/g, "").includes(num.replace(/\s/g, ""))) num = null; }
  return { lines, num, label: num ? label : "" };
}
// 문단 [시작, 끝]: make_audio 기록 → 없으면 글자 수 비율 추정 + 가장 가까운 긴 쉼
function paraSpans(mp3, paras) {
  const side = mp3.replace(/\.mp3$/, ".json");
  if (fs.existsSync(path.join(ROOT, side))) {
    const j = JSON.parse(read(side));
    if (j.paras && j.paras.length === paras.length) return j.paras;
  }
  const T = +execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path.join(ROOT, mp3)]).toString();
  const err = spawnSync("ffmpeg", ["-v", "info", "-i", path.join(ROOT, mp3), "-af", "silencedetect=noise=-40dB:d=0.35", "-f", "null", "-"]).stderr.toString();
  const st = [...err.matchAll(/silence_start: ([\d.]+)/g)].map(x => +x[1]), en = [...err.matchAll(/silence_end: ([\d.]+)/g)].map(x => +x[1]);
  const sil = st.map((s, i) => [s, en[i] ?? T]);
  const chars = paras.map(p => p.replace(/\s/g, "").length), tot = chars.reduce((a, b) => a + b, 0);
  const cuts = []; let cum = 0;
  chars.slice(0, -1).forEach(c => { cum += c; const est = T * cum / tot;
    cuts.push(sil.reduce((b, s) => Math.abs((s[0] + s[1]) / 2 - est) < Math.abs((b[0] + b[1]) / 2 - est) ? s : b, sil[0] || [est, est])); });
  const lead = sil[0] && sil[0][0] < 0.05 ? sil[0][1] : 0;
  return paras.map((_, i) => [i === 0 ? lead : cuts[i - 1][1], i === paras.length - 1 ? T : cuts[i][0]]);
}

function server() {
  return new Promise(res => {
    const srv = http.createServer((q, r) => {
      const p = path.join(ROOT, decodeURIComponent(q.url.split("?")[0]));
      if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end(); }
      r.writeHead(200, { "Content-Type": TYPES[path.extname(p)] || "application/octet-stream" }); fs.createReadStream(p).pipe(r);
    }).listen(0, () => res(srv));
  });
}
async function browser() {
  const exe = ["/opt/pw-browsers/chromium"].find(x => fs.existsSync(x));
  return pw.chromium.launch(exe ? { executablePath: exe } : {});
}
// 카드 렌더(쪽수 칩 숨김) → PNG 경로들 + 분야 이름·색
async function renderCards(b, base, brief, tmp) {
  const pg = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  await pg.route(/https:\/\/(cdn\.(esawebb|esahubble)\.org|(upload|thumb)\.wikimedia\.org)\//, async rt => {
    try { await rt.fulfill({ response: await rt.fetch({ timeout: 8000 }) }); } catch { await rt.abort(); }
  });
  await pg.goto(`${base}/app/cards.html?f=${encodeURIComponent(brief)}&png=1`, { waitUntil: "networkidle" });
  await pg.addStyleTag({ content: ".count{display:none!important}" });
  await pg.waitForTimeout(1200);
  const slides = await pg.$$(".slide");
  const meta = await pg.evaluate(() => ({ cat: document.querySelector(".cover .cat")?.textContent || "",
    ac: getComputedStyle(document.querySelector(".slide.cover")).backgroundColor }));
  const files = [];
  for (let i = 0; i < slides.length; i++) { const f = path.join(tmp, `card${i + 1}.png`); await slides[i].screenshot({ path: f }); files.push(f); }
  await pg.close();
  return { files, meta };
}

// 자동 구간(2026-10-23~): 첫 문단(날짜·인사)은 뺀다 → 본문 문단→카드(개수가 같으면 1:1, 다르면 비율), 날씨 문단→표지, 끝인사→출처 장.
// 본문 문단이 없으면(원고가 '오프닝 + 한 문단'뿐인 여행·액티비티) 마지막 문단을 본문으로 보고 카드에 나눠 싣고, 출처 장은 끝에 OUTRO 초 무음으로 붙인다.
function autoSegments(paras, spans, nSlides) {
  const n = paras.length, K = nSlides - 2;
  const weather = paras.findIndex(p => /^끝으로 오늘 서울 날씨/.test(p));
  let body = [...Array(n).keys()].filter(i => i > 0 && i < n - 1 && i !== weather);
  const closing = body.length ? n - 1 : -1;
  if (!body.length) body = [n - 1];
  const slideOf = i => i === weather ? 1 : i === closing ? nSlides : 2 + Math.min(K - 1, Math.floor(body.indexOf(i) * K / body.length));
  // 2026-10-23 사용자 결정: 날씨·끝인사 문단도 릴스에서 뺀다(날씨는 캡션에) → 본문만 + 출처 장 OUTRO 초
  let keep = body.slice();
  const len = ks => (ks.reduce((t, i) => t + spans[i][1] - spans[i][0], 0) + GAP * (ks.length - 1) + OUTRO) / SPEED;
  const dropped = [...Array(n).keys()].filter(i => !body.includes(i));
  while (len(keep) > FIT) {
    const cand = keep.filter(i => body.includes(i) && body.length > 1);
    if (!cand.length) break;
    const longest = cand.reduce((a, i) => spans[i][1] - spans[i][0] > spans[a][1] - spans[a][0] ? i : a, cand[0]);
    keep = keep.filter(i => i !== longest); dropped.push(longest);
  }
  // 본문 문단이 카드보다 적으면 한 문단이 카드 여러 장을 맡는다 → 그 문단 시간을 나눠 차례로 넘긴다(문단 안은 쉼 없이 이어짐 = 4번째 값 1)
  const range = i => { const j = body.indexOf(i); if (j < 0 || body.length >= K) return [slideOf(i)];
    const a = Math.floor(j * K / body.length), z = Math.max(a + 1, Math.floor((j + 1) * K / body.length));
    return [...Array(z - a).keys()].map(x => 2 + a + x); };
  const segments = keep.flatMap(i => { const r = range(i), [s0, e0] = spans[i], d = (e0 - s0) / r.length;
    return r.map((sl, x) => [+(s0 + d * x).toFixed(3), +(s0 + d * (x + 1)).toFixed(3), sl, x < r.length - 1 ? 1 : 0]); });
  return { segments, dropped: dropped.sort((a, b) => a - b), total: len(keep), outro: nSlides };
}

async function build(spec, b, base) {
  const gapAfter = k => k < spec.segments.length - 1 && !spec.segments[k][3];   // 문단 사이에만 쉼
  const outro = spec.outro ? OUTRO : 0;   // 출처 장 무음 꼬리(본문이 끝인사까지 한 문단인 원고)
  const sp = spec.speed || SPEED;
  const total = (spec.segments.reduce((n, [s, e], k) => n + (e - s) + (gapAfter(k) ? GAP : 0), 0) + outro) / sp;
  if (total > MAX) throw new Error(`길이 ${total.toFixed(1)}초 > ${MAX}초 — 문단을 더 빼세요`);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "reel-"));
  const { files, meta } = spec._cards || await renderCards(b, base, spec.brief, tmp);
  const d = spec.brief.slice(0, 10), wd = "일월화수목금토"[wdOf(d)];
  const fr = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  const N = spec.segments.length;
  const hook = hookOf(read(spec.brief).toString());
  const bgmNote = spec.bgm ? ` · 배경음악 ${esc(spec.bgm.credit)}` : "";
  for (let k = 0; k < N + (outro ? 1 : 0); k++) {   // k === N: 출처 장 무음 꼬리
    // 맨 앞 표지 구간(첫 문단)은 훅 카드로 — 날씨 문단 등 뒤쪽 표지 구간은 그대로
    if (k < N && hook && spec.segments.slice(0, k + 1).every(g => g[2] === 1)) {
      const longest = Math.max(...hook.lines.map(l => l.length));
      const fs_ = Math.max(64, Math.min(132, Math.floor(860 / (Math.max(1, longest) * 0.82))));
      await fr.setContent(`<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;background:${meta.ac};font-family:'Noto Sans KR',sans-serif;color:#fff;position:relative}
.top{position:absolute;left:90px;right:90px;top:200px;display:flex;align-items:center;gap:22px}
.cat{background:#fff;color:${meta.ac};font-weight:900;font-size:38px;padding:10px 28px;border-radius:99px;white-space:nowrap}
.t{font-weight:700;font-size:44px;white-space:nowrap;opacity:.92}.dt{margin-left:auto;font-size:34px;font-weight:500;white-space:nowrap;opacity:.85}
.mid{position:absolute;left:90px;right:150px;top:470px}
.num{font-weight:900;font-size:190px;line-height:1;letter-spacing:-.03em}.lab{font-size:44px;font-weight:700;margin:18px 0 70px;opacity:.9}
.h{font-weight:900;font-size:${fs_}px;line-height:1.22;letter-spacing:-.03em;white-space:nowrap}
.ft{position:absolute;left:90px;right:90px;top:1500px;font-size:34px;opacity:.85}</style></head>
<body><div class="top">${meta.cat ? `<span class="cat">${esc(meta.cat)}</span>` : ""}<span class="t">🎧 ${esc(spec.title)}</span><span class="dt">${+d.slice(5, 7)}.${+d.slice(8, 10)} ${wd}</span></div>
<div class="mid">${hook.num ? `<div class="num">${esc(hook.num)}</div><div class="lab">${esc(hook.label)}</div>` : `<div style="height:40px"></div>`}
${hook.lines.map(l => `<div class="h">${esc(l)}</div>`).join("")}</div>
<div class="ft"><b>@hannun.brief</b> · AI 음성 낭독(Google TTS)${bgmNote}</div></body></html>`, { waitUntil: "networkidle" });
      await fr.screenshot({ path: path.join(tmp, `f${k}.png`) });
      continue;
    }
    const img = "data:image/png;base64," + fs.readFileSync(files[(k < N ? spec.segments[k][2] : spec.outro) - 1]).toString("base64");
    await fr.setContent(`<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;background:#f1efe8;font-family:'Noto Sans KR',sans-serif;color:#1a1a18;position:relative}
.top{position:absolute;left:97px;right:97px;top:190px;display:flex;align-items:center;gap:22px}
.cat{background:${meta.ac};color:#fff;font-weight:900;font-size:38px;padding:10px 28px;border-radius:99px;white-space:nowrap}
.t{font-weight:900;font-size:50px;letter-spacing:-.02em;white-space:nowrap}.dt{margin-left:auto;font-size:32px;color:#55554f;font-weight:500;white-space:nowrap}
.card{position:absolute;left:97px;top:330px;width:886px;border-radius:28px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.08)}
.card img{display:block;width:100%}
.bar{position:absolute;left:97px;right:97px;top:1472px;height:8px;border-radius:9px;background:#e1ddd2}
.bar i{display:block;height:100%;width:${(Math.min(1, (k + 1) / N) * 100).toFixed(1)}%;border-radius:9px;background:${meta.ac}}
.ft{position:absolute;left:97px;right:97px;top:1508px;font-size:32px;color:#55554f}.ft b{color:#3d5a4c}</style></head>
<body><div class="top">${meta.cat ? `<span class="cat">${esc(meta.cat)}</span>` : ""}<span class="t">🎧 ${esc(spec.title)}</span><span class="dt">${+d.slice(5, 7)}.${+d.slice(8, 10)} ${wd}</span></div>
<div class="card"><img src="${img}"></div><div class="bar"><i></i></div>
<div class="ft"><b>@hannun.brief</b> · AI 음성 낭독(Google TTS)${bgmNote}</div></body></html>`, { waitUntil: "networkidle" });
    await fr.screenshot({ path: path.join(tmp, k < N ? `f${k}.png` : "fo.png") });
  }
  await fr.close();
  const parts = spec.segments.map(([s, e], k) => `[0:a]atrim=${s}:${e},asetpts=PTS-STARTPTS${gapAfter(k) ? `,apad=pad_dur=${GAP}` : k === N - 1 && outro ? `,apad=pad_dur=${outro}` : ""}[a${k}]`);
  const filter = parts.join(";") + ";" + spec.segments.map((_, k) => `[a${k}]`).join("") + `concat=n=${N}:v=0:a=1${sp !== 1 ? `,atempo=${sp}` : ""}[a]`;
  const last = outro ? `fo.png` : `f${N - 1}.png`;
  const list = spec.segments.map(([s, e], k) => `file 'f${k}.png'\nduration ${((e - s + (gapAfter(k) ? GAP : 0)) / sp).toFixed(3)}`).join("\n")
    + (outro ? `\nfile 'fo.png'\nduration ${(outro / sp).toFixed(3)}` : "") + `\nfile '${last}'\n`;
  fs.writeFileSync(path.join(tmp, "list.txt"), list);
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", path.join(ROOT, spec.audio), "-filter_complex", filter, "-map", "[a]", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", path.join(tmp, "a.m4a")]);
  if (spec.bgm) {   // 낭독(첫 입력) 길이에 맞춰 배경음을 반복·자르고, 앞뒤를 부드럽게
    const f = await bgmFile(spec.bgm, tmp), fo = Math.max(0, total - 2.5).toFixed(2);
    execFileSync("ffmpeg", ["-v", "error", "-y", "-i", path.join(tmp, "a.m4a"), "-stream_loop", "-1", "-i", f, "-filter_complex",
      `[1:a]atrim=0:${total.toFixed(2)},asetpts=PTS-STARTPTS,volume=${BGM_VOL},afade=t=in:d=1.5,afade=t=out:st=${fo}:d=2.5[b];[0:a][b]amix=inputs=2:duration=first:normalize=0[m]`,
      "-map", "[m]", "-ar", "44100", "-c:a", "aac", "-b:a", "128k", path.join(tmp, "am.m4a")]);
    fs.renameSync(path.join(tmp, "am.m4a"), path.join(tmp, "a.m4a"));
  }
  const out = path.join(ROOT, spec.out); fs.mkdirSync(path.dirname(out), { recursive: true });
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", path.join(tmp, "list.txt"), "-i", path.join(tmp, "a.m4a"),
    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "copy", "-shortest", "-movflags", "+faststart", out]);
  const dur = +execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out]).toString();
  console.log(`reel: ${spec.out} — ${dur.toFixed(1)}초, 프레임 ${N}장`);
  return dur;
}

// 브리프 하나 → 릴스(자동 구간). 만들 수 없으면 이유를 돌려준다.
async function autoOne(brief, b, base) {
  const m = brief.match(BRIEF); if (!m) return { skip: "파일명 형식 아님" };
  const html = read(brief).toString();
  if (/class="tag">\s*Context/.test(html)) return { skip: "맥락 읽기(사건·사고) 카드가 있어 릴스로 만들지 않음" };
  const mp3 = `audio/${m[1]}-${m[2]}/${m[1]}-${m[2]}-${m[3]}_${m[4]}.mp3`;
  if (!fs.existsSync(path.join(ROOT, mp3))) return { skip: "낭독 MP3 없음" };
  const paras = scriptParas(html); if (paras.length < 2) return { skip: "낭독 원고 없음" };
  const spans = paraSpans(mp3, paras);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "reel-"));
  const cards = await renderCards(b, base, brief, tmp);
  const a = autoSegments(paras, spans, cards.files.length);
  const base_ = `reels/${m[1]}-${m[2]}/${m[1]}-${m[2]}-${m[3]}_${m[4]}`;
  const spec = { brief, audio: mp3, out: base_ + ".mp4", title: `${a.total < 55 ? `${Math.max(10, Math.round(a.total / 5) * 5)}초` : `${Math.max(1, Math.round(a.total / 60))}분`} ${TITLE[m[4]] || "듣는 브리프"}`,
    ...(bgmOf(html) ? { bgm: bgmOf(html) } : {}),
    speed: SPEED, segments: a.segments, ...(a.outro ? { outro: a.outro } : {}), dropped_paragraphs: a.dropped.map(i => i + 1),
    note: `날짜·인사·날씨·끝인사 문단은 릴스에서 뺌(본문만, 출처 장 ${OUTRO}초)` + (a.dropped.length > paras.length - a.segments.length ? " — 3분을 넘어 본문 문단도 뺐다, 캡션에 '전체 낭독은 앱에서'" : "") };
  spec._cards = cards;
  await build(spec, b, base);
  delete spec._cards;
  spec.fp = fingerprint(brief, mp3);
  fs.writeFileSync(path.join(ROOT, base_ + ".reel.json"), JSON.stringify(spec, null, 2) + "\n");
  return { files: [spec.out, base_ + ".reel.json"], dropped: spec.dropped_paragraphs, title: spec.title };
}
const fingerprint = (brief, mp3) => sha(read(brief), read(mp3), read("tools/make_reel.js"), read("app/cards.html"));

(async () => {
  const [mode, arg] = process.argv.slice(2);
  const srv = await server(), base = `http://localhost:${srv.address().port}`, b = await browser();
  let code = 0;
  try {
    if (mode === "--auto") {
      const r = await autoOne(arg, b, base);
      if (r.skip) { console.log(`reel: ${arg} 건너뜀 — ${r.skip}`); code = 3; }
      else console.log(`reel: ${r.title} (뺀 문단 ${r.dropped.join("·")})`);
    } else if (mode === "--recent") {
      const today = kstToday(), cutoff = new Date(Date.parse(today) - 3 * 864e5).toISOString().slice(0, 10), made = [];
      for (const n of fs.readdirSync(ROOT).sort()) {
        const m = n.match(BRIEF); if (!m) continue;
        const d = `${m[1]}-${m[2]}-${m[3]}`; if (d < cutoff || !REEL_OF(m[4], wdOf(d))) continue;
        const mp3 = `audio/${m[1]}-${m[2]}/${d}_${m[4]}.mp3`, spec = `reels/${m[1]}-${m[2]}/${d}_${m[4]}.reel.json`;
        if (!fs.existsSync(path.join(ROOT, mp3))) continue;
        if (fs.existsSync(path.join(ROOT, spec)) && JSON.parse(read(spec)).fp === fingerprint(n, mp3)) continue;
        try { const r = await autoOne(n, b, base); if (r.skip) console.log(`reel: ${n} 건너뜀 — ${r.skip}`); else made.push(...r.files); }
        catch (e) { console.log(`::warning::reel failed for ${n}: ${e.message}`); }
      }
      if (process.env.REELS_OUT && made.length) fs.writeFileSync(process.env.REELS_OUT, made.join("\n") + "\n");
      if (!made.length) console.log("reel: nothing to do");
    } else {
      const spec = JSON.parse(fs.readFileSync(mode, "utf8"));
      await build(spec, b, base);
    }
  } catch (e) { console.error(`FAIL ${e.message}`); code = 1; }
  await b.close(); srv.close(); process.exit(code);
})();
