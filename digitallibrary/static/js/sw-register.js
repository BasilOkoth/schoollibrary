// Service Worker Registration
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(function(registration) {
                console.log('[SW] Registered successfully:', registration.scope);
                
                // Check for updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    console.log('[SW] Update found!');
                    
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            console.log('[SW] Update available, refresh to load');
                            // Show update notification
                            showUpdateNotification();
                        }
                    });
                });
            })
            .catch(function(error) {
                console.log('[SW] Registration failed:', error);
            });
        
        // Handle offline status
        window.addEventListener('online', function() {
            console.log('Back online!');
            document.body.classList.remove('offline-mode');
            showToast('Connected to internet', 'success');
        });
        
        window.addEventListener('offline', function() {
            console.log('Offline mode activated');
            document.body.classList.add('offline-mode');
            showToast('Working offline - Some features may be limited', 'warning');
        });
    });
}

function showUpdateNotification() {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg z-50 animate-bounce';
    toast.innerHTML = `
        <div class="flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            <span>New version available! Refresh to update.</span>
            <button onclick="location.reload()" class="ml-4 bg-white text-blue-600 px-2 py-1 rounded">Refresh</button>
        </div>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 10000);
}

function showToast(message, type = 'info') {
    const colors = {
        success: 'bg-green-600',
        warning: 'bg-yellow-600',
        error: 'bg-red-600',
        info: 'bg-blue-600'
    };
    
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 ${colors[type]} text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Queue offline actions
window.queueOfflineAction = async function(action, data) {
    if (!navigator.onLine) {
        const cache = await caches.open('somazone-queue');
        const request = new Request('/api/queue/', {
            method: 'POST',
            body: JSON.stringify({ action, data, timestamp: new Date().toISOString() }),
            headers: { 'Content-Type': 'application/json' }
        });
        await cache.put(request, request.clone());
        console.log('Action queued for later sync');
        showToast('Saved offline - Will sync when online', 'info');
        return false;
    }
    return true;
};