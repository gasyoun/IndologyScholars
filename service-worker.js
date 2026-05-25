const CACHE_VERSION = "2026-05-25-pwa-v2";
const CACHE_PREFIX = "indology-scholars-";
const CORE_CACHE = `${CACHE_PREFIX}core-${CACHE_VERSION}`;
const RUNTIME_CACHE = `${CACHE_PREFIX}runtime-${CACHE_VERSION}`;
const BASE = "/IndologyScholars/";

const CORE_URLS = [
    BASE,
    `${BASE}index.html`,
    `${BASE}en.html`,
    `${BASE}offline.html`,
    `${BASE}search.html`,
    `${BASE}site_data.json`,
    `${BASE}search-index.json`,
    `${BASE}s/`,
    `${BASE}p/`,
    `${BASE}generations/`,
    `${BASE}conferences/`,
    `${BASE}themes/`,
    `${BASE}site.webmanifest`,
    `${BASE}assets/favicon.svg`,
    `${BASE}assets/icon-192.png`,
    `${BASE}assets/icon-512.png`,
    `${BASE}assets/apple-touch-icon.png`,
    `${BASE}assets/pwa.js`,
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CORE_CACHE)
            .then((cache) => cache.addAll(CORE_URLS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(
                keys
                    .filter((key) => key.startsWith(CACHE_PREFIX) && ![CORE_CACHE, RUNTIME_CACHE].includes(key))
                    .map((key) => caches.delete(key))
            ))
            .then(() => self.clients.claim())
    );
});

async function cacheMatch(request, fallbackUrl) {
    const cached = await caches.match(request, { ignoreSearch: true });
    if (cached) {
        return cached;
    }
    return fallbackUrl ? caches.match(fallbackUrl) : undefined;
}

async function networkFirst(request, fallbackUrl) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(RUNTIME_CACHE);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        return cacheMatch(request, fallbackUrl);
    }
}

async function cacheFirst(request) {
    const cached = await cacheMatch(request);
    if (cached) {
        return cached;
    }
    const response = await fetch(request);
    if (response.ok || response.type === "opaque") {
        const cache = await caches.open(RUNTIME_CACHE);
        cache.put(request, response.clone());
    }
    return response;
}

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }

    const url = new URL(event.request.url);
    if (url.origin === self.location.origin && url.pathname.startsWith(BASE)) {
        if (event.request.mode === "navigate") {
            event.respondWith(networkFirst(event.request, `${BASE}offline.html`));
            return;
        }
        if (url.pathname.endsWith(".json") || url.pathname.endsWith(".html") || url.pathname.endsWith("/")) {
            event.respondWith(networkFirst(event.request));
            return;
        }
        event.respondWith(cacheFirst(event.request));
        return;
    }

    if (["style", "font"].includes(event.request.destination)) {
        event.respondWith(cacheFirst(event.request));
    }
});
