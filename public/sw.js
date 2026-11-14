// 流しナビ：オフラインでも開けるようにする Service Worker
// 地図の画像（tiles/）や、外から読む部品（d3・SheetJS）の版を変えたら VERSION を上げる（古いキャッシュが消えて取り直す）。
// index.html・config.js・geo.json は、開くたびに裏で新しいものを取りにいくので、VERSION を上げなくても次に開いたときに新しくなる。
const VERSION = 'v1';
const CACHE = 'nagashi-navi-' + VERSION;
const SHELL = ['./', 'config.js', 'geo.json', 'minna.json', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'];
const D3 = 'https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js';
const SHEETJS = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js';
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

// 外のサイトからは CORS つきで取る（中身の見えない返事をためると、端末の空き容量を大きく使った扱いになるため）
const get = (url, sameOrigin) => fetch(url, sameOrigin ? { cache: 'no-cache' } : { mode: 'cors', credentials: 'omit' });
const keep = (cache, url, res) => { if (res.ok) cache.put(url, res.clone()); return res; };

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await c.addAll(SHELL.map((u) => new Request(u, { cache: 'reload' })));
    // 地図の画像の一覧は geo.json に入っている
    const geo = await (await c.match('geo.json')).json();
    const tiles = geo.tiles.chunks.map((x) => x[2]).concat(geo.tiles.ov ? [geo.tiles.ov[2]] : []);
    await c.addAll(tiles);
    const d3 = await get(D3, false);
    if (!d3.ok) throw new Error('d3 ' + d3.status);
    await c.put(D3, d3);
    // Excelを読む部品は、取れなくてもアプリは動くので、失敗してもよい
    await get(SHEETJS, false).then((r) => keep(c, SHEETJS, r)).catch(() => {});
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n.startsWith('nagashi-navi-') && n !== CACHE).map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

// ためてあるものをすぐ返し、裏で新しいものに入れ替える
const fresh = (e, url, sameOrigin) => caches.open(CACHE).then(async (c) => {
  const hit = await c.match(url);
  const net = get(url, sameOrigin).then((r) => keep(c, url, r));
  if (hit) { e.waitUntil(net.catch(() => {})); return hit; }
  return net;
});
// ためてあればそれを返す（中身の変わらないもの）
const stored = (url, sameOrigin) => caches.open(CACHE).then(async (c) => (await c.match(url)) || get(url, sameOrigin).then((r) => keep(c, url, r)));

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return; // 記録の送信（POST）には触らない
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    if (!url.href.startsWith(self.registration.scope)) return;
    if (req.mode === 'navigate') { e.respondWith(fresh(e, self.registration.scope, true)); return; }
    if (url.pathname.includes('/tiles/')) { e.respondWith(stored(url.href, true)); return; }
    e.respondWith(fresh(e, url.href.split('?')[0], true));
    return;
  }
  if (url.href === D3 || url.href === SHEETJS) { e.respondWith(stored(url.href, false)); return; }
  if (FONT_HOSTS.includes(url.hostname)) { e.respondWith(fresh(e, url.href, false)); return; }
});
