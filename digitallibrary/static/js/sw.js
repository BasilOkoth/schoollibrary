// Service Worker for Somazone - Offline Support
const CACHE_NAME = 'somazone-v1.0';
const OFFLINE_URL = '/offline/';

// Assets to cache on install
const STATIC_CACHE_URLS = [
    '/',
    '/static/css/tailwind.min.css',
    '/static/js/alpine.min.js',
    '/static/js/sw-register.js',
    '/offline/',
];

// Install event - cache static assets
self.addEventListener('install', event => {
    console.log('[SW] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_CACHE_URLS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log('[SW] Activating...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        console.log('[SW] Deleting old cache:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }
    
    // Skip API calls - they need internet
    if (url.pathname.startsWith('/api/')) {
        return;
    }
    
    // Skip admin panel
    if (url.pathname.startsWith('/admin/')) {
        return;
    }
    
    event.respondWith(
        caches.match(request)
            .then(cachedResponse => {
                // Return cached response if found
                if (cachedResponse) {
                    console.log('[SW] Serving from cache:', url.pathname);
                    return cachedResponse;
                }
                
                // Otherwise fetch from network
                return fetch(request)
                    .then(networkResponse => {
                        // Don't cache non-successful responses
                        if (!networkResponse || networkResponse.status !== 200) {
                            return networkResponse;
                        }
                        
                        // Cache the fetched response
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(request, responseToCache);
                                console.log('[SW] Cached new resource:', url.pathname);
                            });
                        
                        return networkResponse;
                    })
                    .catch(() => {
                        // If both cache and network fail, show offline page
                        if (url.pathname === '/') {
                            return caches.match(OFFLINE_URL);
                        }
                        return caches.match(OFFLINE_URL);
                    });
            })
    );
});

// Background sync for offline actions
self.addEventListener('sync', event => {
    console.log('[SW] Sync event:', event.tag);
    if (event.tag === 'sync-feedback') {
        event.waitUntil(syncFeedback());
    }
});

// Function to sync feedback when online
async function syncFeedback() {
    const cache = await caches.open('somazone-queue');
    const requests = await cache.keys();
    
    for (const request of requests) {
        try {
            const response = await fetch(request);
            if (response.ok) {
                await cache.delete(request);
                console.log('[SW] Synced feedback successfully');
            }
        } catch (error) {
            console.log('[SW] Sync failed, will retry later');
        }
    }
}