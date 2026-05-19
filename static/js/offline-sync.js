// offline-sync.js
// Offline-First Reporting System for Sentinel AI

class OfflineSyncManager {
    constructor() {
        this.dbName = 'sentinel_offline_db';
        this.storeName = 'pending_reports';
        this.db = null;
        this.indicator = null;
        this.banner = null;
        
        this.init();
    }

    async init() {
        await this.initDB();
        this.setupUI();
        this.bindEvents();
        this.updateOnlineStatus();
        this.updatePendingCount();
    }

    initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, 1);
            
            request.onerror = (event) => {
                console.error("IndexedDB error:", event.target.error);
                reject(event.target.error);
            };

            request.onsuccess = (event) => {
                this.db = event.target.result;
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(this.storeName)) {
                    db.createObjectStore(this.storeName, { keyPath: '_id' });
                }
            };
        });
    }

    setupUI() {
        // Create Offline Banner
        this.banner = document.createElement('div');
        this.banner.id = 'offline-banner';
        this.banner.className = 'alert alert-danger fixed-top mb-0 text-center rounded-0';
        this.banner.style.display = 'none';
        this.banner.style.zIndex = '9999';
        this.banner.innerHTML = '<i class="fas fa-wifi-slash me-2"></i><strong>You are currently offline.</strong> Reports will be saved locally and synced automatically when connection is restored.';
        document.body.prepend(this.banner);

        // Create Pending Sync Indicator
        this.indicator = document.createElement('div');
        this.indicator.id = 'sync-indicator';
        this.indicator.style.position = 'fixed';
        this.indicator.style.bottom = '20px';
        this.indicator.style.left = '20px';
        this.indicator.style.zIndex = '9998';
        this.indicator.style.display = 'none';
        this.indicator.style.background = '#f59e0b';
        this.indicator.style.color = '#fff';
        this.indicator.style.padding = '10px 15px';
        this.indicator.style.borderRadius = '20px';
        this.indicator.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
        this.indicator.style.alignItems = 'center';
        this.indicator.style.gap = '10px';
        
        this.indicator.innerHTML = `
            <div style="display: flex; align-items: center;">
                <i class="fas fa-cloud-upload-alt fa-bounce me-2"></i>
                <strong id="sync-count">0</strong>&nbsp;Pending Sync
            </div>
            <button id="sync-retry-btn" class="btn btn-sm btn-light py-0 px-2" style="font-weight: bold; margin-left:10px;">Retry Now</button>
        `;
        document.body.appendChild(this.indicator);

        document.getElementById('sync-retry-btn').addEventListener('click', () => this.syncReports());
    }

    bindEvents() {
        window.addEventListener('online', () => {
            this.updateOnlineStatus();
            this.syncReports();
        });
        
        window.addEventListener('offline', () => {
            this.updateOnlineStatus();
        });

        const reportForm = document.getElementById('reportForm');
        if (reportForm) {
            // Need to intercept before other submit handlers or inside them.
            // Since there is already a submit listener in report.html validating terms,
            // we attach a listener to 'submit' that runs in capturing or bubbling phase.
            reportForm.addEventListener('submit', async (e) => {
                if (!navigator.onLine) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    await this.captureAndQueue(reportForm);
                }
            });
        }
    }

    updateOnlineStatus() {
        if (navigator.onLine) {
            if(this.banner) this.banner.style.display = 'none';
        } else {
            if(this.banner) this.banner.style.display = 'block';
        }
    }

    async captureAndQueue(form) {
        const submitBtn = form.querySelector('[type="submit"]') || document.getElementById('submitButton');
        if(submitBtn) {
            submitBtn.disabled = true;
            const originalHtml = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Saving Offline...';
        }

        try {
            const formData = new FormData(form);
            const dataFields = {};
            const fileFields = {};

            // Separate plain text data from files/blobs
            for (let [key, value] of formData.entries()) {
                if (value instanceof File || value instanceof Blob) {
                    if(value.size > 0 && value.name) {
                        fileFields[key] = { blob: value, name: value.name };
                    }
                } else {
                    dataFields[key] = value;
                }
            }

            const reportEntry = {
                _id: 'report_' + Date.now(),
                _timestamp: new Date().toISOString(),
                data: dataFields,
                files: fileFields
            };

            await this.saveToDB(reportEntry);
            
            // UI Feedback
            this.updatePendingCount();
            alert('🟢 You are offline. Your report has been saved locally and will securely sync when connection is restored.');
            
            // Navigate away or reset form
            form.reset();
            window.location.href = '/dashboard';
        } catch (error) {
            console.error('Error queuing offline report:', error);
            alert('🔴 Failed to save report offline. Please try again.');
        } finally {
            if(submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Submit Report';
            }
        }
    }

    saveToDB(entry) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.storeName], 'readwrite');
            const store = transaction.objectStore(this.storeName);
            const request = store.add(entry);
            
            request.onsuccess = () => resolve();
            request.onerror = (e) => reject(e.target.error);
        });
    }

    async updatePendingCount() {
        try {
            const reports = await this.getAllFromDB();
            const count = reports.length;
            const countEl = document.getElementById('sync-count');
            
            if (count > 0) {
                if(countEl) countEl.innerText = count;
                if(this.indicator) this.indicator.style.display = 'flex';
            } else {
                if(this.indicator) this.indicator.style.display = 'none';
            }
        } catch (err) {
            console.error("Failed to update pending count", err);
        }
    }

    getAllFromDB() {
        return new Promise((resolve, reject) => {
            if(!this.db) { resolve([]); return; }
            const transaction = this.db.transaction([this.storeName], 'readonly');
            const store = transaction.objectStore(this.storeName);
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = (e) => reject(e.target.error);
        });
    }

    deleteFromDB(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.storeName], 'readwrite');
            const store = transaction.objectStore(this.storeName);
            const request = store.delete(id);
            
            request.onsuccess = () => resolve();
            request.onerror = (e) => reject(e.target.error);
        });
    }

    async syncReports() {
        if (!navigator.onLine) return;

        const syncBtn = document.getElementById('sync-retry-btn');
        if(syncBtn) {
            syncBtn.disabled = true;
            syncBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }

        try {
            const reports = await this.getAllFromDB();
            if (reports.length === 0) return;

            console.log(`[Offline Sync] Found ${reports.length} pending reports. Attempting sync...`);

            for (const report of reports) {
                // Reconstruct FormData
                const formData = new FormData();
                
                // Append text data
                for (let key in report.data) {
                    formData.append(key, report.data[key]);
                }
                
                // Append file data
                for (let key in report.files) {
                    const fileObj = report.files[key];
                    formData.append(key, fileObj.blob, fileObj.name || 'offline_capture.jpg');
                }

                // Append an offline identifier if backend wants to track it
                formData.append('_offline_synced', 'true');
                formData.append('_original_timestamp', report._timestamp);

                try {
                    // Send to backend endpoint
                    const response = await fetch('/report', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok || response.redirected) {
                        console.log(`[Offline Sync] Successfully synced report ${report._id}`);
                        await this.deleteFromDB(report._id);
                    } else {
                        console.error(`[Offline Sync] Server responded with error for report ${report._id}: ${response.status}`);
                    }
                } catch (netErr) {
                    console.error(`[Offline Sync] Network failure during sync:`, netErr);
                    // Stop trying to process the rest if network fails mid-way
                    break;
                }
            }

        } catch (error) {
            console.error('[Offline Sync] Global sync error:', error);
        } finally {
            this.updatePendingCount();
            if(syncBtn) {
                syncBtn.disabled = false;
                syncBtn.innerText = 'Retry Now';
            }
            if(this.banner) this.banner.style.display = 'none';
        }
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    window.offlineSyncManager = new OfflineSyncManager();
});
