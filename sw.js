const CACHE_NAME = "mypace-v2";

const PRE_CACHE = [
  "./",
  "./index.html",
  "./data/cities.json",
  "./assets/earth-blue-marble.jpg",
  "./vendor/tailwind.min.js",
  "./vendor/leaflet.css",
  "./vendor/leaflet.js",
  "./vendor/echarts.min.js",
  "./vendor/flatpickr.min.css",
  "./vendor/flatpickr.min.js",
  "./vendor/flatpickr-zh.js",
  "./vendor/chart.umd.min.js",
  "./vendor/three.min.js",
  "./vendor/globe.gl.min.js",
  "./vendor/html2canvas.min.js",
  "./vendor/images/marker-icon.png",
  "./vendor/images/marker-icon-2x.png",
  "./vendor/images/marker-shadow.png",
  "./vendor/images/layers.png",
  "./vendor/images/layers-2x.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRE_CACHE))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((n) => n !== CACHE_NAME)
          .map((n) => caches.delete(n))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // 地图瓦片：网络优先，失败则缓存
  if (url.hostname.includes("autonavi.com")) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  const req = event.request;
  if (req.method !== "GET") return;

  async function putCache(request, response) {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response);
  }

  async function networkFirst(request) {
    try {
      const res = await fetch(request);
      if (res && res.ok) {
        await putCache(request, res.clone());
      }
      return res;
    } catch (e) {
      const cached = await caches.match(request);
      if (cached) return cached;
      throw e;
    }
  }

  async function staleWhileRevalidate(request) {
    const cached = await caches.match(request);
    const fetchPromise = fetch(request)
      .then(async (res) => {
        if (res && res.ok) await putCache(request, res.clone());
        return res;
      })
      .catch(() => null);
    return cached || fetchPromise;
  }

  // 文档与关键数据：网络优先，确保每次刷新能拿到最新版本
  const isNav = req.mode === "navigate" || req.destination === "document";
  const isCitiesDB = url.pathname.endsWith("/data/cities.json");
  const isIndexHtml = url.pathname.endsWith("/index.html") || url.pathname.endsWith("/");
  if (isNav || isCitiesDB || isIndexHtml) {
    event.respondWith(networkFirst(req));
    return;
  }

  // 其它静态资源：缓存优先 + 后台更新（刷新后更容易看到新版本）
  event.respondWith(staleWhileRevalidate(req));
});
