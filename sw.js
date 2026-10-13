// Daily Brief 앱(app/)용 서비스 워커. 레포 루트에 있어야 브리프 HTML 까지 관리할 수 있다.
// 원칙: 최신 브리프가 우선(네트워크 먼저), 오프라인일 때만 저장본을 보여 준다.
//       오디오(mp3)·외부 도메인(폰트 등)은 건드리지 않는다 — Range 요청을 브라우저가 직접 처리하게.
const VERSION = "db-v1";
const SHELL = ["app/", "app/index.html", "app/app.webmanifest", "app/icons/icon-192.png", "app/icons/icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if(req.method !== "GET" || url.origin !== location.origin) return;
  if(/\.(mp3|m4a)$/i.test(url.pathname) || req.headers.has("range")) return;
  e.respondWith(
    fetch(req).then(res => {
      if(res.ok && res.type === "basic"){ const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req, {ignoreSearch: true}).then(r => r || Response.error()))
  );
});
