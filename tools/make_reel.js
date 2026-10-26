// 오디오 릴스(1080×1920 MP4) 만들기 — 브리프 카드 + 낭독 MP3 를 문단 구간에 맞춰 넘긴다.
//
//   node tools/make_reel.js <spec.json>            구간을 직접 지정 (spec 형식은 아래)
//   node tools/make_reel.js --auto <브리프.html>     구간 자동 계산 → reels/YYYY-MM/<날짜>_<종류>.mp4 + .reel.json
//   node tools/make_reel.js --lib <음악 브리프.html>   음악 라이브러리판(소리 없음, 카드 전부) → reels/YYYY-MM/<날짜>_music_lib.mp4 (2026-10-24~, 사람이 앱에서 음악을 붙여 게시)
//   node tools/make_reel.js --short <브리프.html>    15초 '핵심 3장' 릴스(낭독 없음, 배경음악) → reels/YYYY-MM/<날짜>_<종류>_short.mp4 (2026-10-23~ A/B)
//   node tools/make_reel.js --deep <브리프.html> <카드 번호>   깊게 파는 릴스 '페이지 전환형'(2026-10-26~ 사용자 결정): <details class="reel-script" data-card="N"> 의 data-k 요점 장 + 배경음악, 낭독 없음 → reels/YYYY-MM/<날짜>_<종류>_cN.mp4
//   node tools/make_reel.js --deep-narr <브리프.html> <카드 번호>   (옛 낭독형 — 원고 MP3 필요, 지금은 자동으로 만들지 않는다)
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
// 축구 프리뷰(2026-10-24~): 토 주말 프리뷰·화 챔피언스리그 프리뷰는 짧은판만(14초 이내, 표지 빼고 본문 카드부터) — 낭독판은 만들지 않는다
// 10초판(2026-10-26~ 사용자 결정 — 스포츠 데이터 릴스 9.2초가 조회 121·평균 시청 23초·건너뛰기 0%): 축구 모닝·야구 나이트는 발행일마다
// '첫 카드 천천히 확대 5.5초 → 둘째 카드 4초', 낭독 없음·배경음악, 출처 장 없음(카드에 출처 칩). 낭독판·13초 짧은판은 만들지 않는다.
const FAST_OF = type => ["football", "baseball"].includes(type);
const SHORT_ONLY = (type, wd) => FAST_OF(type) || (type === "football" && (wd === 6 || wd === 2));
const REEL_OF = (type, wd) => ["ai", "science", "activity"].includes(type) || (type === "sports" && (wd === 1 || wd === 2)) || SHORT_ONLY(type, wd);   // 음악(토)은 2026-10-24 브리프 폐지로 뺐다
// 스포츠 시리즈는 @hannun.sports 로 올라간다(app/cards.html SPORTS_HANDLE 과 같게)
const HANDLE_OF = type => ["sports", "baseball", "football", "event", "esports"].includes(type) ? "@hannun.sports" : "@hannun.brief";
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
const articleOf = (html, idx = 0) => [...html.matchAll(/<article class="card"[^>]*>([\s\S]*?)<\/article>/g)][idx] || null;
function hookOf(html, idx = 0) {
  const a = articleOf(html, idx); if (!a) return null;
  const strip = x => x.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();
  const t = a[1].match(/<p class="cn-t">([\s\S]*?)<\/p>/); if (!t) return null;
  const lines = t[1].split(/<br\s*\/?>/).map(strip).filter(Boolean);
  const n = a[1].match(/<p class="cn-num">([\s\S]*?)<\/p>/);
  let num = null, label = "";
  if (n) { [num, label = ""] = strip(n[1]).split("|"); if (lines.join("").replace(/\s/g, "").includes(num.replace(/\s/g, ""))) num = null; }
  const tp = html.match(/class="kicker"[^>]*data-topic="([^"]+)"/);
  return { lines, num, label: num ? label : "", topic: tp ? strip(tp[1]) : "" };
}
// ── 오프닝 A/B (2026-10-25 사용자 결정): 첫 2초 '정지(static)' vs '움직임(motion)' ──
// 근거: 릴스 5편 평균 시청 2.3~2.8초 — 길이(34~176초)·첫 장면 종류(표지·큰 글씨·카드 1번)와 무관. 세 가지 모두 첫 3초가 완전히 정지 화면이었다.
// motion = 카드 1번 그림이 화면 위쪽을 꽉 채우고 천천히 확대 + 큰 숫자·제목이 아래에서 올라오는 2초 → 카드로 바로 넘어감(장면 변화).
// 고르기: 같은 코너는 2주마다 번갈아(낭독판/짧은판 A/B 는 1주마다 — publish_ig.py pick_variant) → 코너마다 4주에 2×2 가 고르게 돈다.
// REEL_OPENING=motion|static 으로 강제. OPENING_FROM 이전 날짜 브리프는 모두 static(실험 전 기준선).
const OPENING_FROM = process.env.REEL_OPENING_FROM || "2026-10-26", INTRO = 2.0, IFPS = 30;
const OPEN_SLOT = { ai: 0, activity: 1, science: 2, sports: 1, football: 1, music: 1 };
function isoWeek(d) { const t = new Date(d + "T00:00:00Z"), w = (t.getUTCDay() + 6) % 7; t.setUTCDate(t.getUTCDate() - w + 3);
  const y = new Date(Date.UTC(t.getUTCFullYear(), 0, 4)); return 1 + Math.round(((t - y) / 864e5 - 3 + ((y.getUTCDay() + 6) % 7)) / 7); }
function openingOf(brief) {
  if (process.env.REEL_OPENING) return process.env.REEL_OPENING;
  const m = brief.match(BRIEF); if (!m) return "static";
  const d = `${m[1]}-${m[2]}-${m[3]}`; if (d < OPENING_FROM) return "static";
  return (Math.floor(isoWeek(d) / 2) + (OPEN_SLOT[m[4]] ?? 0)) % 2 === 0 ? "motion" : "static";
}
// 움직이는 오프닝 프레임(INTRO 초 × IFPS) — 카드 1번 PNG 위쪽(그림 영역)과 훅 문구. 첫 프레임부터 문구가 보인다(썸네일·자동재생 첫 장면).
// 카드 1번 그림의 표시(지우면 안 됨): 실제 사진이면 크레디트(CC BY — 그림에서 떼지 않는다), AI 그림이면 'AI 생성 이미지'(과학은 'AI 개념도')
function picNoteOf(html, type, idx = 0) {
  const a = articleOf(html, idx); if (!a) return "";
  const strip = x => x.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();
  const ph = a[1].match(/<figure class="photo"[\s\S]*?class="credit">([\s\S]*?)<\/span>/);
  if (ph) return strip(ph[1]).replace(/^이미지:\s*/, "이미지: ");
  if (/class="cn-gen"/.test(a[1])) return type === "science" ? "AI 개념도" : "AI 생성 이미지";
  return "";
}
// 카드의 AI 그림 원본(img/gen/…) — 오프닝 배경은 카드 PNG 대신 이걸 쓴다(카드 PNG 를 확대하면 카드 속 'AI 생성 이미지' 배지가 잘려 '지'만 남았다, 2026-10-26 검수)
function genOf(html, idx = 0) {
  const a = articleOf(html, idx), g = a && a[1].match(/<img class="cn-gen"[^>]*src="([^"]+)"/);
  return g && fs.existsSync(path.join(ROOT, g[1])) ? path.join(ROOT, g[1]) : "";
}
async function introFrames(b, card1, hook, meta, label, d, wd, handle, tmp, note = "", raw = "") {
  const img = raw ? "data:image/jpeg;base64," + fs.readFileSync(raw).toString("base64") : "data:image/png;base64," + fs.readFileSync(card1).toString("base64");
  const longest = Math.max(1, ...hook.lines.map(l => l.length));
  const fs_ = Math.max(64, Math.min(112, Math.floor(880 / (longest * 0.9))));
  // 사진·AI 그림이 없는 카드(도표·개념도)는 그림을 확대하면 잘리므로 → 액센트 바탕 큰 글씨(주제어·숫자·제목)만
  const pic = !!note;
  const pg = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await pg.setContent(`<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;background:${pic ? '#111' : meta.ac};font-family:'Noto Sans KR',sans-serif;color:#fff;position:relative;overflow:hidden}
.pic{position:absolute;left:0;top:0;width:1080px;height:1100px;overflow:hidden}
.pic div{position:absolute;inset:0;background:url(${img}) ${raw ? 'center/cover' : 'top center/auto 2200px'} no-repeat;transform-origin:50% 40%}
.fade{position:absolute;left:0;right:0;top:700px;height:420px;background:linear-gradient(180deg,rgba(17,17,17,0),#111)}
.top{position:absolute;left:80px;right:80px;top:150px;display:flex;align-items:center;gap:22px}
.cat{background:${pic ? meta.ac : '#fff'};color:${pic ? '#fff' : meta.ac};font-weight:900;font-size:40px;padding:10px 30px;border-radius:99px;white-space:nowrap}
.dt{margin-left:auto;font-size:36px;font-weight:700;white-space:nowrap;text-shadow:0 2px 12px rgba(0,0,0,.6)}
.txt{position:absolute;left:80px;right:80px;top:${pic ? (hook.topic ? 860 : 1060) : 520}px}
.tp{display:inline-block;background:${pic ? meta.ac : '#fff'};color:${pic ? '#fff' : meta.ac};font-weight:900;font-size:${Math.min(150, Math.floor(900 / Math.max(2, (hook.topic || '').length)))}px;line-height:1.1;padding:14px 36px 22px;border-radius:28px;margin-bottom:34px;letter-spacing:-.03em}
.num{font-weight:900;font-size:${Math.min(170, Math.floor(1500 / Math.max(1, (hook.num || '').length)))}px;line-height:1;letter-spacing:-.03em;color:#fff;white-space:nowrap}.lab{font-size:44px;font-weight:700;margin:34px 0 40px;opacity:.85}
.h{font-weight:900;font-size:${fs_}px;line-height:1.2;letter-spacing:-.03em;white-space:nowrap}
.ft{position:absolute;left:80px;right:80px;top:1640px;font-size:32px;opacity:.75}
.note{position:absolute;left:80px;top:250px;max-width:920px;background:rgba(0,0,0,.55);color:#fff;font-size:28px;font-weight:500;padding:6px 16px;border-radius:10px}</style></head>
<body>${pic ? '<div class="pic"><div id="z"></div></div><div class="fade"></div>' : '<div id="z"></div>'}${note ? `<div class="note">${esc(note)}</div>` : ""}
<div class="top">${meta.cat ? `<span class="cat">${esc(meta.cat)}</span>` : ""}<span class="dt">${esc(label)} · ${+d.slice(5, 7)}.${+d.slice(8, 10)} ${wd}</span></div>
<div class="txt">${hook.topic ? `<div class="tp" id="tp">${esc(hook.topic)}</div>` : ""}${hook.num ? `<div class="num" id="n">${esc(hook.num)}</div><div class="lab">${esc(hook.label)}</div>` : ""}
${hook.lines.map((l, i) => `<div class="h" id="h${i}">${esc(l)}</div>`).join("")}</div>
<div class="ft"><b>${handle}</b></div></body></html>`, { waitUntil: "networkidle" });
  const files = [], N = Math.round(INTRO * IFPS);
  for (let i = 0; i < N; i++) {
    const t = i / IFPS;
    await pg.evaluate(t => {
      const e = x => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);   // ease-out
      document.getElementById("z").style.transform = `scale(${1 + 0.10 * t / 2})`;
      const tp = document.getElementById("tp"); if (tp) { const k = e(t / 0.35); tp.style.transform = `scale(${1.12 - 0.12 * k})`; tp.style.transformOrigin = "0 50%"; }
      const n = document.getElementById("n"); if (n) { const k = e(t / 0.45); n.style.transform = `translateY(${(1 - k) * 24}px) scale(${0.94 + 0.06 * k})`; }
      document.querySelectorAll(".h").forEach((h, j) => { const k = e((t - 0.15 - 0.18 * j) / 0.4); h.style.transform = `translateX(${(1 - k) * 60}px)`; h.style.opacity = 0.6 + 0.4 * k; });
    }, t);
    const f = path.join(tmp, `in${String(i).padStart(3, "0")}.png`); await pg.screenshot({ path: f }); files.push(f);
  }
  await pg.close();
  return files;
}
// 문단 [시작, 끝]: make_audio 기록 → 없으면 글자 수 비율 추정 + 가장 가까운 긴 쉼
function paraSpans(mp3, paras) {
  const side = mp3.replace(/\.mp3$/, ".json");
  if (fs.existsSync(path.join(ROOT, side))) {
    const j = JSON.parse(read(side));
    if (j.paras && j.paras.length === paras.length) return j.paras;
    // 원고 문단을 합치거나 나눈 뒤 MP3 를 다시 만들지 않았으면(재생기가 있으면 make_audio 가 건너뜀) 문단 수가 다르다 — 2026-10-25 과학 릴스에서
    // 글자 수 추정으로 떨어져 '빠진 카드의 낭독 끝이 다음 카드 화면에 깔린' 사고. 사이드카 문단을 글자 수로 이어 붙여 원고 문단에 맞춘다(문단 안은 그대로).
    if (j.paras && j.chars && j.chars.length === j.paras.length) {
      const want = paras.map(p => p.replace(/\s/g, "").length), out = []; let k = 0;
      for (const w of want) {
        let acc = 0, a = k;
        while (k < j.chars.length && acc + j.chars[k] <= w + 3) { acc += j.chars[k]; k++; }
        if (k === a || Math.abs(acc - w) > 3) { out.length = 0; break; }
        out.push([j.paras[a][0], j.paras[k - 1][1]]);
      }
      if (out.length === paras.length && k === j.chars.length) return out;
    }
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
  const ci = spec.card ? spec.card - 1 : 0;   // 깊게 파는 릴스는 그 카드가 첫 장면
  const hook = hookOf(read(spec.brief).toString(), ci);
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
<div class="ft"><b>${HANDLE_OF((spec.brief.match(BRIEF) || [])[4])}</b> · AI 음성 낭독(Google TTS)${bgmNote}</div></body></html>`, { waitUntil: "networkidle" });
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
<div class="ft"><b>${HANDLE_OF((spec.brief.match(BRIEF) || [])[4])}</b> · AI 음성 낭독(Google TTS)${bgmNote}</div></body></html>`, { waitUntil: "networkidle" });
    await fr.screenshot({ path: path.join(tmp, k < N ? `f${k}.png` : "fo.png") });
  }
  await fr.close();
  // 오프닝 motion: 첫 구간(카드 1번) 앞 INTRO 초를 움직이는 프레임으로 바꾼다(전체 길이·소리는 그대로)
  const d0 = (spec.segments[0][1] - spec.segments[0][0] + (gapAfter(0) ? GAP : 0)) / sp;
  let intro = [];
  if (spec.opening === "motion" && hook && d0 > INTRO + 0.5 && spec.segments[0][2] === 2)
    intro = await introFrames(b, files[1], hook, meta, spec.title, d, wd, HANDLE_OF((spec.brief.match(BRIEF) || [])[4]), tmp, picNoteOf(read(spec.brief).toString(), (spec.brief.match(BRIEF) || [])[4], ci), genOf(read(spec.brief).toString(), ci));
  const parts = spec.segments.map(([s, e], k) => `[0:a]atrim=${s}:${e},asetpts=PTS-STARTPTS${gapAfter(k) ? `,apad=pad_dur=${GAP}` : k === N - 1 && outro ? `,apad=pad_dur=${outro}` : ""}[a${k}]`);
  const filter = parts.join(";") + ";" + spec.segments.map((_, k) => `[a${k}]`).join("") + `concat=n=${N}:v=0:a=1${sp !== 1 ? `,atempo=${sp}` : ""}[a]`;
  const last = outro ? `fo.png` : `f${N - 1}.png`;
  const list = intro.map(f => `file '${path.basename(f)}'\nduration ${(1 / IFPS).toFixed(5)}`).concat(
    spec.segments.map(([s, e], k) => `file 'f${k}.png'\nduration ${(((e - s + (gapAfter(k) ? GAP : 0)) / sp) - (k === 0 && intro.length ? INTRO : 0)).toFixed(3)}`)).join("\n")
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
    "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1", "-preset", "medium", "-crf", "23", "-c:a", "copy", "-shortest", "-movflags", "+faststart", out]);
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
    speed: SPEED, opening: openingOf(brief), segments: a.segments, ...(a.outro ? { outro: a.outro } : {}), dropped_paragraphs: a.dropped.map(i => i + 1),
    note: `날짜·인사·날씨·끝인사 문단은 릴스에서 뺌(본문만, 출처 장 ${OUTRO}초)` + (a.dropped.length > paras.length - a.segments.length ? " — 3분을 넘어 본문 문단도 뺐다, 캡션에 '전체 낭독은 앱에서'" : "") };
  spec._cards = cards;
  await build(spec, b, base);
  delete spec._cards;
  spec.fp = fingerprint(brief, mp3);
  fs.writeFileSync(path.join(ROOT, base_ + ".reel.json"), JSON.stringify(spec, null, 2) + "\n");
  return { files: [spec.out, base_ + ".reel.json"], dropped: spec.dropped_paragraphs, title: spec.title };
}
// ── 짧은 릴스(2026-10-23~ A/B 시험): 카드 앞 3장 × 4초 + 출처·공유 장 2.2초, 장면은 겹쳐 넘어감(머리말은 그대로 보이게), 낭독 대신 배경음악 ──
// 배경음악: Kevin MacLeod "Upbeat Forever" (incompetech.com) — Wikimedia Commons 파일 페이지 기준 CC BY 3.0. 저장소에는 앞 30초만 잘라 둔다(끝 2초 페이드).
// 어느 쪽(낭독판/짧은판)을 올릴지는 게시 스크립트가 날짜로 번갈아 고른다(.github/scripts/publish_ig.py `ab`).
// 짧은판 길이 = 3 × 4 + 2.2 − 0.35 × 3 = 13.15초 — 14초 이내(2026-10-24 사용자 요청). 값을 바꾸면 shortOne 의 max 검사가 막는다.
// 2026-10-26 본계정도 '페이지 전환형'(사용자 결정): 카드 1번 3초(오프닝 A/B 그대로) → 카드 2·3번 2.5초씩 → 출처 장 1.5초
// = 3 + 2.5 + 2.5 + 1.5 − 0.3 × 3 = 8.6초(10초 이내, 반복 재생 길이). 위 13.15초 계산은 기록.
const FLIP_BGM = "audio/cc/upbeat-forever_kevin-macleod_0-30.mp3", FLIP_CREDIT = "Upbeat Forever — Kevin MacLeod (incompetech.com) · CC BY 3.0";
const SHORT = { cards: 3, secs: [3, 2.5, 2.5], outro: 1.5, xf: 0.3, max: 10, bgm: FLIP_BGM, credit: FLIP_CREDIT, suffix: "_short", variant: "short" };
// 10초판: 카드 2장(5.5초 확대 + 4초), 출처 장 없음 → 5.5 + 4 − 0.35 = 9.15초. 파일 이름은 짧은판과 같은 _short(게시 "ab":"short" 그대로).
const FAST = { cards: 2, secs: [5.5, 4], outro: 0, xf: 0.35, max: 10.5, zoom: 0.08, bgm: SHORT.bgm, credit: SHORT.credit, suffix: "_short", variant: "fast" };
// 월요일 축구 주말 결산판(2026-10-26 사용자 결정 — "6개 슬라이드인데 쇼츠는 2개네"): 카드 6장 — 첫 장 4.5초 확대 → 나머지 1.8초씩 넘김, 출처 장 없음
// = 4.5 + 1.8 × 5 − 0.25 × 5 = 12.25초. 다른 요일 축구·야구는 위 10초판 그대로.
const RECAP = { cards: 6, secs: [4.5, 1.8], outro: 0, xf: 0.25, max: 14.5, zoom: 0.08, bgm: SHORT.bgm, credit: SHORT.credit, suffix: "_short", variant: "recap", label: "⚡ 주말 결산" };
// 야구 나이트 캐러셀판(2026-10-26 사용자 결정 — "야구도 캐러셀 내용을 쇼츠로, 페이지당 1.8초, TTS 없이 배경음"): 본문 카드 전부(최대 6장) 1.8초씩, 첫 장도 1.8초(살짝 확대),
// 표지·출처 장 없음(카드에 출처 칩) = 1.8 × N − 0.25 × (N − 1) — 4장 6.45초 · 6장 9.55초.
const NIGHT = { cards: 6, secs: [1.8], outro: 0, xf: 0.25, max: 10, zoom: 0.04, bgm: SHORT.bgm, credit: SHORT.credit, suffix: "_short", variant: "night", label: "⚾ 야구 나이트" };
const shortOptOf = (type, d) => type === "football" && wdOf(d) === 1 ? RECAP : type === "baseball" ? NIGHT : FAST_OF(type) ? FAST : SHORT;
// 음악 라이브러리판(2026-10-24~ 사용자 결정): 토요일 음악 릴스는 자동 게시하지 않고, 사람이 인스타 앱에서 음악 라이브러리 곡을 붙여 올린다.
// 그래서 소리 없는 영상으로 카드 전부 × 4초 + 출처 장. 곡은 그 주 플레이리스트에서 라이브러리에 있는 것을 고른다(캡션 파일에 후보).
const LIB = { cards: 7, sec: 4, outro: 2.2, xf: 0.35, bgm: null, credit: "", suffix: "_lib", variant: "lib", label: "🎵 이번 주 플레이리스트" };
const shortFp = brief => sha(read(brief), read(SHORT.bgm), read("tools/make_reel.js"), read("app/cards.html"));
async function shortOne(brief, b, base, O = SHORT) {
  const m = brief.match(BRIEF); if (!m) return { skip: "파일명 형식 아님" };
  const html = read(brief).toString();
  // 프리뷰 브리프(2026-10-24~ 사용자 요청): 머리말 '⚡ 핵심 N장' 대신 kicker 끝의 '… 프리뷰'(예: '⚡ 주말 프리뷰')
  const pv = html.match(/class="kicker">[^<]*·\s*([^<·]*프리뷰)\s*</);
  if (/class="tag">\s*Context/.test(html)) return { skip: "맥락 읽기(사건·사고) 카드가 있어 릴스로 만들지 않음" };
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "reel-s-"));
  const { files, meta } = await renderCards(b, base, brief, tmp);
  const n = Math.min(O.cards, files.length - 2); if (n < 1) return { skip: "카드 없음" };
  const label = O.label || (pv ? `⚡ ${pv[1].trim()}` : `⚡ 핵심 ${n}장`);
  const slides = [...Array(n).keys()].map(i => i + 2).concat(O.outro ? [files.length] : []);
  const d = `${m[1]}-${m[2]}-${m[3]}`;
  const durs = slides.map((_, k) => k < n ? (O.secs ? (O.secs[k] ?? O.secs[O.secs.length - 1]) : O.sec) : O.outro);
  const out_ = `reels/${m[1]}-${m[2]}/${d}_${m[4]}${O.suffix}`;
  const r = await flipReel(b, { m, d, imgs: slides.map(k => files[k - 1]), durs, xf: O.xf, max: O.max, zoom: O.zoom, label, meta, bgm: O.bgm, credit: O.credit, out_,
    opening: O.variant === "lib" || O.zoom ? "static" : openingOf(brief), card1: files[1], raw: genOf(html), hook: hookOf(html), note: picNoteOf(html, m[4]), tmp });
  const spec = { brief, variant: O.variant, opening: r.opening, out: out_ + ".mp4", cards: n, seconds: +r.total.toFixed(2), bgm: O.bgm, credit: O.credit, fp: shortFp(brief) };
  fs.writeFileSync(path.join(ROOT, out_ + ".reel.json"), JSON.stringify(spec, null, 2) + "\n");
  console.log(`reel: ${out_}.mp4 — ${r.total.toFixed(1)}초, 카드 ${n}장${O.outro ? " + 출처" : ""}`);
  return { files: [out_ + ".mp4", out_ + ".reel.json"] };
}
// 페이지 전환형 공통(짧은판·10초판·라이브러리판·깊게 파는 릴스): 장면 PNG(카드 비율)를 1080×1920 틀에 넣어 겹쳐 넘기고 배경음악을 깐다.
// 첫 장면: zoom 이면 천천히 확대(10초판), 아니면 오프닝 A/B(motion = 카드 그림 확대 INTRO 초 → 정지).
async function flipReel(b, o) {
  const { m, d, imgs, durs, meta, label, tmp } = o, wd = "일월화수목금토"[wdOf(d)];
  const fr = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  for (let k = 0; k < imgs.length; k++) {
    const img = "data:image/png;base64," + fs.readFileSync(imgs[k]).toString("base64");
    await fr.setContent(`<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1920px;background:#f1efe8;font-family:'Noto Sans KR',sans-serif;color:#1a1a18;position:relative}
.top{position:absolute;left:97px;right:97px;top:190px;display:flex;align-items:center;gap:22px}
.cat{background:${meta.ac};color:#fff;font-weight:900;font-size:38px;padding:10px 28px;border-radius:99px;white-space:nowrap}
.t{font-weight:900;font-size:50px;letter-spacing:-.02em;white-space:nowrap}.dt{margin-left:auto;font-size:32px;color:#55554f;font-weight:500;white-space:nowrap}
.card{position:absolute;left:97px;top:330px;width:886px;border-radius:28px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,.08)}
.card img{display:block;width:100%}
.bar{position:absolute;left:97px;right:97px;top:1472px;height:8px;border-radius:9px;background:#e1ddd2}
.bar i{display:block;height:100%;width:${((k + 1) / imgs.length * 100).toFixed(1)}%;border-radius:9px;background:${meta.ac}}
.ft{position:absolute;left:97px;right:97px;top:1508px;font-size:26px;color:#55554f;line-height:1.5;white-space:nowrap}.ft b{color:#3d5a4c;font-size:30px}</style></head>
<body><div class="top">${meta.cat ? `<span class="cat">${esc(meta.cat)}</span>` : ""}<span class="t">${esc(label)}</span><span class="dt">${+d.slice(5, 7)}.${+d.slice(8, 10)} ${wd}</span></div>
<div class="card"><img src="${img}"></div><div class="bar"><i></i></div>
<div class="ft"><b>${HANDLE_OF(m[4])}</b>${o.credit ? `<br>♪ ${esc(o.credit)}` : ""}</div></body></html>`, { waitUntil: "networkidle" });
    await fr.screenshot({ path: path.join(tmp, `s${k}.png`) });
  }
  await fr.close();
  const hk = o.hook;
  const intro = o.opening === "motion" && hk && durs[0] > INTRO + 0.5 ? await introFrames(b, o.card1, hk, meta, label, d, wd, HANDLE_OF(m[4]), tmp, o.note, o.raw || "") : [];
  const total = durs.reduce((a, c) => a + c, 0) - o.xf * (imgs.length - 1);
  if (o.max && total > o.max) throw new Error(`${label} ${total.toFixed(1)}초 — ${o.max}초 넘음`);
  const ins = imgs.flatMap((_, k) => ["-loop", "1", "-framerate", "30", "-t", String(durs[k]), "-i", path.join(tmp, `s${k}.png`)]);
  const extra = intro.length ? ["-framerate", String(IFPS), "-i", path.join(tmp, "in%03d.png")] : [];
  let f = imgs.map((_, k) => `[${k}:v]fps=30,format=yuv420p,setsar=1[i${k}]`), cur = "[i0]", off = 0;
  if (o.zoom) {   // 10초판: 첫 장면을 천천히 확대(첫 2초부터 움직임 — 스포츠 데이터 릴스와 같은 방식)
    const N = Math.round(durs[0] * 30);
    f[0] = `[0:v]scale=2160:-1,zoompan=z='1+${o.zoom}*on/${N}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,format=yuv420p,setsar=1[i0]`;
  }
  if (intro.length) {   // 첫 장면: 움직이는 INTRO 초 → 카드 정지(남은 시간)
    const I = imgs.length + (o.bgm ? 1 : 0);
    f[0] = `[0:v]fps=30,format=yuv420p,setsar=1,trim=0:${(durs[0] - INTRO).toFixed(3)},setpts=PTS-STARTPTS[s0];[${I}:v]fps=30,format=yuv420p,setsar=1[iv];[iv][s0]concat=n=2:v=1:a=0,fps=30,setsar=1[i0]`;
  }
  for (let k = 1; k < imgs.length; k++) { off += durs[k - 1] - o.xf; f.push(`${cur}[i${k}]xfade=transition=fade:duration=${o.xf}:offset=${off.toFixed(3)}[x${k}]`); cur = `[x${k}]`; }
  if (o.bgm) f.push(`[${imgs.length}:a]atrim=0:${total.toFixed(3)},asetpts=PTS-STARTPTS,afade=t=out:st=${Math.max(0, total - 1.2).toFixed(3)}:d=1.2,volume=0.9[a]`);
  fs.mkdirSync(path.join(ROOT, path.dirname(o.out_)), { recursive: true });
  const aud = o.bgm ? ["-i", path.join(ROOT, o.bgm)] : [], amap = o.bgm ? ["-map", "[a]", "-c:a", "aac", "-b:a", "128k"] : ["-an"];   // 라이브러리판은 소리 없음 — 음악은 인스타 앱에서
  // xfade 가 yuv444p(High 4:4:4)로 내보내 아이폰·인스타에서 재생이 안 됐다(2026-10-26) — 출력은 yuv420p·High 로 고정
  execFileSync("ffmpeg", ["-v", "error", "-y", ...ins, ...aud, ...extra, "-filter_complex", f.join(";"), "-map", cur, ...amap,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1", "-preset", "medium", "-crf", "21", "-t", total.toFixed(3), "-movflags", "+faststart", path.join(ROOT, o.out_ + ".mp4")]);
  return { total, opening: o.zoom ? "zoom" : intro.length ? "motion" : "static" };
}
// ── 깊게 파는 릴스(2026-10-26~ 사용자 승인, 같은 날 '페이지 전환형'으로 바꿈 — 아래 deepFlip): 그날 카드 하나를 더 자세히 — 점수(item-scorer) 80점 이상 카드마다, 하루 최대 3편(README '깊게 파는 릴스') ──
// 원고: 브리프 안 <details class="reel-script" data-card="N" data-score="86" data-type="손해형"><p data-k="화면에 크게 띄울 말">…</p>…</details>
// MP3: make_audio.py 가 블록마다 audio/YYYY-MM/<날짜>_<종류>_cN.mp3 (+ .json 문단 구간)
// 화면: 문단 1 = 카드 N(오프닝 A/B 그대로) → 문단 2~ = '요점 장'(카드 그림 + data-k 큰 글씨) → 출처 장 2초. 사건·사고(맥락 읽기) 카드는 만들지 않는다.
const DEEP_MAX = 90;
function reelBlocks(html) {
  return [...html.matchAll(/<details class="reel-script"([^>]*)>([\s\S]*?)<\/details>/g)].map(m => {
    const at = k => ((m[1].match(new RegExp(`data-${k}="([^"]*)"`)) || [])[1] || "");
    const ps = [...m[2].matchAll(/<p([^>]*)>([\s\S]*?)<\/p>/g)].map(x => ({ k: ((x[1].match(/data-k="([^"]*)"/) || [])[1] || "").replace(/&amp;/g, "&"),
      t: x[2].replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim() })).filter(x => x.t);
    return { card: +at("card"), score: +at("score") || 0, type: at("type"), paras: ps, raw: m[0] };
  }).filter(b => b.card > 0 && b.paras.length);
}
async function pointPanels(b, blk, card, note, meta, title, tmp, raw = "") {
  // 그림 띠: AI 그림 원본이 있으면 그것 + 표시 한 번. 없으면 카드 PNG 위쪽(카드에 이미 표시·크레디트가 있으니 덧씌우지 않는다 — 2026-10-26 검수 '표시 두 겹')
  const img = raw ? "data:image/jpeg;base64," + fs.readFileSync(raw).toString("base64") : "data:image/png;base64," + fs.readFileSync(card).toString("base64"), out = [];
  const pg = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  for (let i = 1; i < blk.paras.length; i++) {
    const k = blk.paras[i].k, f = path.join(tmp, `pt${i}.png`);
    if (!k) { fs.copyFileSync(card, f); out.push(f); continue; }   // 요점 문구가 없으면 카드를 한 번 더
    const fsz = Math.max(96, Math.min(160, Math.floor(1700 / Math.max(6, k.length))));   // 길면 두 줄로 — 카드보다 크게 읽히게
    await pg.setContent(`<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;box-sizing:border-box}body{width:1080px;height:1350px;background:${note ? "#fff" : meta.ac};font-family:'Noto Sans KR',sans-serif;position:relative;overflow:hidden}
.pic{position:absolute;left:0;top:0;width:1080px;height:520px;background:url(${img}) ${raw ? 'center/cover' : 'top center/1080px auto'} no-repeat}
.pic:after{content:"";position:absolute;left:0;right:0;bottom:0;height:120px;background:linear-gradient(180deg,rgba(255,255,255,0),#fff)}
.nt{position:absolute;left:40px;top:28px;background:rgba(0,0,0,.55);color:#fff;font-size:26px;padding:5px 14px;border-radius:10px}
.k{position:absolute;left:80px;right:80px;top:${note ? 600 : 400}px;font-weight:900;font-size:${fsz}px;line-height:1.15;letter-spacing:-.03em;color:${note ? meta.ac : "#fff"};word-break:keep-all}
.n{position:absolute;left:80px;bottom:70px;font-size:34px;font-weight:700;color:${note ? "#55554f" : "rgba(255,255,255,.85)"}}</style></head>
<body>${note ? `<div class="pic"></div>${raw ? `<div class="nt">${esc(note)}</div>` : ""}` : ""}<div class="k">${esc(k)}</div><div class="n">${i + 1} / ${blk.paras.length} · ${esc(title)}</div></body></html>`, { waitUntil: "networkidle" });
    await pg.screenshot({ path: f }); out.push(f);
  }
  await pg.close();
  return out;
}
async function deepOne(brief, cardNo, b, base) {
  const m = brief.match(BRIEF); if (!m) return { skip: "파일명 형식 아님" };
  const html = read(brief).toString(), blk = reelBlocks(html).find(x => x.card === cardNo);
  if (!blk) return { skip: `카드 ${cardNo} 릴스 원고 없음` };
  const art = articleOf(html, cardNo - 1); if (!art) return { skip: `카드 ${cardNo} 없음` };
  if (/class="tag">\s*(Context|맥락)/.test(art[1])) return { skip: "맥락 읽기(사건·사고) 카드 — 릴스 금지" };
  const d = `${m[1]}-${m[2]}-${m[3]}`, mp3 = `audio/${m[1]}-${m[2]}/${d}_${m[4]}_c${cardNo}.mp3`;
  if (!fs.existsSync(path.join(ROOT, mp3))) return { skip: "릴스 원고 MP3 없음" };
  const texts = blk.paras.map(x => x.t), spans = paraSpans(mp3, texts);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "reel-d-"));
  const cards = await renderCards(b, base, brief, tmp);
  const card = cards.files[cardNo], note = picNoteOf(html, m[4], cardNo - 1);
  const ttl = (hookOf(html, cardNo - 1)?.lines || []).join(" ");
  const pts = await pointPanels(b, blk, card, note, cards.meta, ttl, tmp);
  // 가상 슬라이드: 1 = 표지(안 씀), 2 = 카드 N, 3… = 요점 장, 마지막 = 출처 장
  const files = [cards.files[0], card, ...pts, cards.files[cards.files.length - 1]];
  const segments = texts.map((_, i) => [spans[i][0], spans[i][1], 2 + i, 0]);
  const total = (segments.reduce((t, [s, e]) => t + e - s, 0) + GAP * (segments.length - 1) + OUTRO) / SPEED;
  if (total > DEEP_MAX) return { skip: `길이 ${total.toFixed(0)}초 > ${DEEP_MAX}초 — 원고를 줄일 것` };
  const out_ = `reels/${m[1]}-${m[2]}/${d}_${m[4]}_c${cardNo}`;
  const spec = { brief, card: cardNo, kind: "deep", score: blk.score, type: blk.type, audio: mp3, out: out_ + ".mp4",
    title: `${Math.max(10, Math.round(total / 5) * 5)}초 깊게 보기`, speed: SPEED, opening: openingOf(brief), segments, outro: files.length,
    note: `깊게 파는 릴스 — 카드 ${cardNo} 원고 ${texts.length}문단` };
  spec._cards = { files, meta: cards.meta };
  await build(spec, b, base);
  delete spec._cards;
  spec.fp = deepFp(brief, blk, mp3);
  fs.writeFileSync(path.join(ROOT, out_ + ".reel.json"), JSON.stringify(spec, null, 2) + "\n");
  return { files: [spec.out, out_ + ".reel.json"] };
}
// 페이지 전환형(2026-10-26~ 기본): 카드 N 3초(오프닝 A/B) → data-k 요점 장 2.5초씩 → 출처 장 1.5초, 배경음악, 낭독 없음.
// 요점 문구(data-k)가 없는 문단은 장을 만들지 않는다 — 원고 문단은 앱·검수용 근거로 남는다.
const DEEP_FLIP = { first: 3, sec: 2.5, outro: 1.5, xf: 0.3, max: 20 };
async function deepFlip(brief, cardNo, b, base) {
  const m = brief.match(BRIEF); if (!m) return { skip: "파일명 형식 아님" };
  const html = read(brief).toString(), blk0 = reelBlocks(html).find(x => x.card === cardNo);
  if (!blk0) return { skip: `카드 ${cardNo} 릴스 원고 없음` };
  const art = articleOf(html, cardNo - 1); if (!art) return { skip: `카드 ${cardNo} 없음` };
  if (/class="tag">\s*(Context|맥락)/.test(art[1])) return { skip: "맥락 읽기(사건·사고) 카드 — 릴스 금지" };
  const blk = { ...blk0, paras: [blk0.paras[0], ...blk0.paras.slice(1).filter(x => x.k)] };
  if (blk.paras.length < 2) return { skip: "data-k 요점 문구가 없음" };
  const d = `${m[1]}-${m[2]}-${m[3]}`, tmp = fs.mkdtempSync(path.join(os.tmpdir(), "reel-f-"));
  const cards = await renderCards(b, base, brief, tmp);
  const card = cards.files[cardNo], note = picNoteOf(html, m[4], cardNo - 1), hook = hookOf(html, cardNo - 1);
  const pts = await pointPanels(b, blk, card, note, cards.meta, (hook?.lines || []).join(" "), tmp, genOf(html, cardNo - 1));
  const imgs = [card, ...pts, cards.files[cards.files.length - 1]];
  const durs = imgs.map((_, k) => k === 0 ? DEEP_FLIP.first : k === imgs.length - 1 ? DEEP_FLIP.outro : DEEP_FLIP.sec);
  const out_ = `reels/${m[1]}-${m[2]}/${d}_${m[4]}_c${cardNo}`, label = "🔎 깊게 보기";
  const r = await flipReel(b, { m, d, html, imgs, durs, xf: DEEP_FLIP.xf, max: DEEP_FLIP.max, label, meta: cards.meta, bgm: FLIP_BGM, credit: FLIP_CREDIT, out_,
    opening: openingOf(brief), card1: card, raw: genOf(html, cardNo - 1), hook, note, tmp });
  const spec = { brief, card: cardNo, kind: "deep", variant: "flip", score: blk.score, type: blk.type, out: out_ + ".mp4", opening: r.opening,
    pages: pts.length, seconds: +r.total.toFixed(2), bgm: FLIP_BGM, credit: FLIP_CREDIT, keys: blk.paras.slice(1).map(x => x.k),
    note: `깊게 파는 릴스(페이지 전환형) — 카드 ${cardNo} 요점 ${pts.length}장`, fp: deepFlipFp(brief, blk0) };
  fs.writeFileSync(path.join(ROOT, out_ + ".reel.json"), JSON.stringify(spec, null, 2) + "\n");
  console.log(`reel: ${spec.out} — ${r.total.toFixed(1)}초, 요점 ${pts.length}장`);
  return { files: [spec.out, out_ + ".reel.json"] };
}
const deepFlipFp = (brief, blk) => sha(read(brief), blk.raw, read(FLIP_BGM), read("tools/make_reel.js"), read("app/cards.html"));
const deepFp = (brief, blk, mp3) => sha(read(brief), blk.raw, read(mp3), read("tools/make_reel.js"), read("app/cards.html"));
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
    } else if (mode === "--lib") {
      const r = await shortOne(arg, b, base, LIB);
      if (r.skip) { console.log(`reel: ${arg} 건너뜀 — ${r.skip}`); code = 3; }
    } else if (mode === "--deep" || mode === "--deep-narr") {
      const r = await (mode === "--deep" ? deepFlip : deepOne)(arg, +process.argv[4], b, base);
      if (r.skip) { console.log(`reel: ${arg} 건너뜀 — ${r.skip}`); code = 3; }
    } else if (mode === "--short") {
      const bm = path.basename(arg).match(BRIEF) || [];
      const r = await shortOne(arg, b, base, bm[4] ? shortOptOf(bm[4], `${bm[1]}-${bm[2]}-${bm[3]}`) : SHORT);
      if (r.skip) { console.log(`reel: ${arg} 건너뜀 — ${r.skip}`); code = 3; }
    } else if (mode === "--recent") {
      const today = kstToday(), cutoff = new Date(Date.parse(today) - 3 * 864e5).toISOString().slice(0, 10), made = [];
      for (const n of fs.readdirSync(ROOT).sort()) {
        const m = n.match(BRIEF); if (!m) continue;
        const d = `${m[1]}-${m[2]}-${m[3]}`; if (d < cutoff) continue;
        // 깊게 파는 릴스(페이지 전환형) — 코너와 상관없이 원고 블록이 있는 카드마다. 낭독 MP3 는 쓰지 않는다(2026-10-26~)
        for (const blk of reelBlocks(read(n).toString())) {
          const js = `reels/${m[1]}-${m[2]}/${d}_${m[4]}_c${blk.card}.reel.json`;
          if (fs.existsSync(path.join(ROOT, js)) && JSON.parse(read(js)).fp === deepFlipFp(n, blk)) continue;
          try { const r = await deepFlip(n, blk.card, b, base); if (r.skip) console.log(`reel: ${n} 카드 ${blk.card} 건너뜀 — ${r.skip}`); else made.push(...r.files); }
          catch (e) { console.log(`::warning::deep reel failed for ${n} c${blk.card}: ${e.message}`); }
        }
        if (!REEL_OF(m[4], wdOf(d))) continue;
        const mp3 = `audio/${m[1]}-${m[2]}/${d}_${m[4]}.mp3`, spec = `reels/${m[1]}-${m[2]}/${d}_${m[4]}.reel.json`;
        // 짧은판(A/B). 음악 브리프는 짧은판 대신 라이브러리판(소리 없음 — 사람이 인스타 앱에서 음악을 붙여 게시, 2026-10-24~)
        const lib = m[4] === "music", sspec = `reels/${m[1]}-${m[2]}/${d}_${m[4]}${lib ? LIB.suffix : SHORT.suffix}.reel.json`;
        if (!(fs.existsSync(path.join(ROOT, sspec)) && JSON.parse(read(sspec)).fp === shortFp(n))) {
          try { const r = await shortOne(n, b, base, lib ? LIB : shortOptOf(m[4], d)); if (!r.skip) made.push(...r.files); }
          catch (e) { console.log(`::warning::short reel failed for ${n}: ${e.message}`); }
        }
        if (SHORT_ONLY(m[4], wdOf(d)) || !fs.existsSync(path.join(ROOT, mp3))) continue;
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
