const CACHE_VERSION = "2026-06-30-pwa-v6";
const CACHE_PREFIX = "indology-scholars-";
const CORE_CACHE = `${CACHE_PREFIX}core-${CACHE_VERSION}`;
const RUNTIME_CACHE = `${CACHE_PREFIX}runtime-${CACHE_VERSION}`;
const BASE = "/IndologyScholars/";
const INDOLOGY_ARCHIVE_PATH = `${BASE}IndologyArchive`;
const INDOLOGY_ARCHIVE_BASE = `${BASE}IndologyArchive/`;
const INDOLOGY_ARCHIVE_FALLBACK = `${INDOLOGY_ARCHIVE_BASE}index.html`;

const CORE_URLS = [
    BASE,
    `${BASE}index.html`,
    `${BASE}en.html`,
    `${BASE}offline.html`,
    `${BASE}search.html`,
    `${BASE}search-index.json`,
    `${BASE}site_data.json`,
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
    INDOLOGY_ARCHIVE_FALLBACK,
    `${INDOLOGY_ARCHIVE_BASE}dashboard/index.html`,
    `${INDOLOGY_ARCHIVE_BASE}dashboard/search.html`,
    `${INDOLOGY_ARCHIVE_BASE}dashboard/curated.html`,
    `${INDOLOGY_ARCHIVE_BASE}datapackage.json`,
    `${INDOLOGY_ARCHIVE_BASE}CITATION.cff`,
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

function isIndologyArchivePath(pathname) {
    return pathname === INDOLOGY_ARCHIVE_PATH || pathname.startsWith(INDOLOGY_ARCHIVE_BASE);
}

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }

    const url = new URL(event.request.url);
    if (url.origin === self.location.origin && url.pathname.startsWith(BASE)) {
        if (event.request.mode === "navigate") {
            if (url.pathname === INDOLOGY_ARCHIVE_PATH) {
                event.respondWith(Response.redirect(`${url.origin}${INDOLOGY_ARCHIVE_BASE}${url.search}`, 302));
                return;
            }
            const fallbackUrl = isIndologyArchivePath(url.pathname)
                ? INDOLOGY_ARCHIVE_FALLBACK
                : `${BASE}offline.html`;
            event.respondWith(networkFirst(event.request, fallbackUrl));
            return;
        }
        if (url.pathname.endsWith(".json") || url.pathname.endsWith(".html") || url.pathname.endsWith("/")) {
            event.respondWith(networkFirst(event.request));
            return;
        }
        event.respondWith(cacheFirst(event.request));
        return;
    }

    if (["style", "font", "script"].includes(event.request.destination)) {
        event.respondWith(cacheFirst(event.request));
    }
});
