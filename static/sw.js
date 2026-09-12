/**
 * WeatherGPT - Official IMD Meteorological Service Worker
 * Ministry of Earth Sciences (MoES / SIH26068)
 * 
 * Provides background push notification handling, native meteorological alert dispatch,
 * and resilient caching for offline decision support.
 */

const CACHE_NAME = 'weathergpt-v2-cache';
const ASSETS_TO_CACHE = [
    '/',
    '/static/index.html',
    '/manifest.json'
];

// Install Event: Pre-cache shell assets
self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
                console.warn('[SW] Cache addAll warning:', err);
            });
        })
    );
});

// Activate Event: Clean old caches and claim immediate client control
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((name) => {
                    if (name !== CACHE_NAME) {
                        return caches.delete(name);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Push Event: Handle incoming web push notifications
self.addEventListener('push', (event) => {
    let payload = {
        title: 'IMD Meteorological Alert | MoES',
        body: 'New weather telemetry and disaster bulletin available for your district.',
        icon: '/static/favicon.svg',
        badge: '/static/favicon.svg',
        tag: 'imd-weather-alert',
        data: { url: '/' }
    };

    if (event.data) {
        try {
            const data = event.data.json();
            payload = Object.assign(payload, data);
        } catch (e) {
            payload.body = event.data.text();
        }
    }

    const options = {
        body: payload.body,
        icon: payload.icon || '/static/favicon.svg',
        badge: payload.badge || '/static/favicon.svg',
        tag: payload.tag || 'imd-weather-alert',
        renotify: true,
        vibrate: [200, 100, 200, 100, 300],
        data: payload.data || { url: '/' },
        actions: [
            { action: 'open', title: 'View IMD Bulletin' },
            { action: 'dismiss', title: 'Dismiss' }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(payload.title, options)
    );
});

// Notification Click Handler: Focus existing tab or open portal
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    if (event.action === 'dismiss') {
        return;
    }

    const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});

// Message Handler for direct client-to-worker notification triggers
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'TRIGGER_NOTIFICATION') {
        const { title, options } = event.data;
        self.registration.showNotification(title, options);
    }
});
