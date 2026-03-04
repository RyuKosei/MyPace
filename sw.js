const CACHE_NAME = "mypace-v1";

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

  // 其它资源：缓存优先，回退网络并缓存
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        if (res.ok && event.request.method === "GET") {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
        }
        return res;
      });
    })
  );
});
