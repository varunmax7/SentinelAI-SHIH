// Analyst Dashboard - Real Data Version
(function () {
    'use strict';

    console.log('🚀 Dashboard script starting...');

    let hMap, wMap;
    let weatherMarkers = [];
    let hazardMarkers = [];
    let hazardHeatLayer = null;

    // Wait for everything to load
    window.addEventListener('load', function () {
        console.log('✅ Window loaded, initializing dashboard...');

        // Check if DASHBOARD_DATA exists
        if (typeof DASHBOARD_DATA === 'undefined') {
            console.error('❌ DASHBOARD_DATA not found!');
            return;
        }

        console.log('📊 DASHBOARD_DATA:', DASHBOARD_DATA);

        // Initialize maps
        setTimeout(initializeMaps, 500);

        // Initialize charts
        setTimeout(initializeCharts, 800);

        // Track the currently selected district path so auto-refresh always uses the right one
        let currentDistrictPath = 'livejsp/Yadadri.jsp';

        // Handle District Dropdown Selection - update IMMEDIATELY on change
        const districtSelect = document.getElementById('districtSelect');
        const districtMap = document.getElementById('districtMap');
        if (districtSelect && districtMap) {
            districtSelect.addEventListener('change', function(e) {
                currentDistrictPath = e.target.value;
                districtMap.src = `/api/proxy/tgdps_map?path=${currentDistrictPath}`;
            });
        }

        // Start TGDPS Map auto-refresh (30 seconds - long enough for slow govt server)
        setInterval(() => {
            const tgdpsMap = document.getElementById('tgdpsMap');
            if (tgdpsMap) {
                const url = new URL(tgdpsMap.src);
                url.searchParams.set('_t', new Date().getTime());
                tgdpsMap.src = url.toString();
            }
            
            // Always refresh district map using the CURRENTLY selected district
            if (districtMap) {
                districtMap.src = `/api/proxy/tgdps_map?path=${currentDistrictPath}&_t=${new Date().getTime()}`;
            }
        }, 30000);
    });

    function initializeMaps() {
        console.log('🗺️ Starting map initialization...');

        // Check if Leaflet is loaded
        if (typeof L === 'undefined') {
            console.error('❌ Leaflet not loaded!');
            return;
        }

        try {
            // ===== INCIDENT HOTSPOTS HEATMAP =====
            const heatmapEl = document.getElementById('heatmapMap');
            if (heatmapEl) {
                console.log('📍 Creating incident heatmap...');
                hMap = L.map('heatmapMap').setView([20.5, 78.9], 5);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap'
                }).addTo(hMap);

                setTimeout(() => hMap.invalidateSize(), 200);

                // Add heatmap layer if we have reports
                if (DASHBOARD_DATA.reports && DASHBOARD_DATA.reports.length > 0) {
                    console.log(`🔥 Adding ${DASHBOARD_DATA.reports.length} reports to heatmap`);

                    if (typeof L.heatLayer !== 'undefined') {
                        const heatPoints = DASHBOARD_DATA.reports.map(r => [
                            r.latitude,
                            r.longitude,
                            r.confidence_score || 0.5
                        ]);

                        L.heatLayer(heatPoints, {
                            radius: 35,
                            blur: 15,
                            maxOpacity: 0.8,
                            gradient: {
                                0.0: '#3b82f6',
                                0.25: '#06b6d4',
                                0.5: '#eab308',
                                0.75: '#f59e0b',
                                1.0: '#ef4444'
                            }
                        }).addTo(hMap);

                        // Fit bounds to show all reports
                        const bounds = L.latLngBounds(heatPoints.map(p => [p[0], p[1]]));
                        hMap.fitBounds(bounds.pad(0.2));
                    } else {
                        console.warn('⚠️ Leaflet.heat not loaded, showing markers instead');
                        // Fallback to markers
                        DASHBOARD_DATA.reports.forEach(r => {
                            L.circleMarker([r.latitude, r.longitude], {
                                radius: 8,
                                fillColor: '#ef4444',
                                color: '#fff',
                                weight: 1,
                                opacity: 1,
                                fillOpacity: 0.6
                            }).bindPopup(`<b>${r.hazard_type}</b><br>${r.location}`).addTo(hMap);
                        });
                    }
                } else {
                    console.log('ℹ️ No reports to display on heatmap');
                }

                console.log('✅ Incident heatmap created');
            }

            // ===== WEATHER & EARLY WARNINGS (Live Hazard Heatmap) =====
            const warningEl = document.getElementById('warningMap');
            if (warningEl) {
                console.log('📍 Creating live hazard map...');
                wMap = L.map('warningMap').setView([20.5, 78.9], 5);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap'
                }).addTo(wMap);

                setTimeout(() => wMap.invalidateSize(), 200);

                // Start live hazard updates
                updateLiveHazards();
                setInterval(updateLiveHazards, 5000); // Update every 5 seconds

                console.log('✅ Live hazard map created');
            }
        } catch (error) {
            console.error('❌ Map error:', error);
        }
    }

    async function updateLiveHazards() {
        if (!wMap) return;

        try {
            // Clear existing layers
            if (hazardHeatLayer) {
                wMap.removeLayer(hazardHeatLayer);
            }
            weatherMarkers.forEach(m => wMap.removeLayer(m));
            hazardMarkers.forEach(m => wMap.removeLayer(m));
            weatherMarkers = [];
            hazardMarkers = [];

            // Fetch live hazard data
            const [incidentsRes, govtHazardsRes] = await Promise.all([
                fetch('/api/live_hazard_incidents'),
                fetch('/api/live_govt_hazards')
            ]);

            const incidents = await incidentsRes.json();
            const govtHazards = await govtHazardsRes.json();

            // Add incident heatmap
            if (incidents.incidents && incidents.incidents.length > 0 && typeof L.heatLayer !== 'undefined') {
                const heatPoints = incidents.incidents.map(i => [
                    i.latitude,
                    i.longitude,
                    i.confidence_score || 0.5
                ]);

                hazardHeatLayer = L.heatLayer(heatPoints, {
                    radius: 35,
                    blur: 20,
                    maxOpacity: 0.8,
                    gradient: {
                        0.0: '#3b82f6',
                        0.25: '#06b6d4',
                        0.5: '#eab308',
                        0.75: '#f59e0b',
                        1.0: '#ef4444'
                    }
                });
                hazardHeatLayer.addTo(wMap);

                console.log(`🔥 Live hazards: ${incidents.count} incidents`);
            }

            // Add government hazard alerts
            if (govtHazards.hazards && govtHazards.hazards.length > 0) {
                govtHazards.hazards.forEach(h => {
                    const color = h.severity === 'critical' ? '#dc2626' :
                        h.severity === 'high' ? '#ea580c' :
                            h.severity === 'medium' ? '#f59e0b' : '#06b6d4';

                    const marker = L.circle([h.latitude, h.longitude], {
                        radius: h.radius * 1000,
                        color: color,
                        fillColor: color,
                        fillOpacity: 0.15,
                        weight: 3,
                        dashArray: '10, 5'
                    }).bindPopup(`
                        <b>⚠️ ${h.type}</b><br>
                        Severity: <strong>${h.severity.toUpperCase()}</strong><br>
                        ${h.description}
                    `);
                    marker.addTo(wMap);
                    hazardMarkers.push(marker);
                });

                console.log(`⚠️ Government alerts: ${govtHazards.count} hazards`);
            }
        } catch (error) {
            console.error('❌ Error updating live hazards:', error);
        }
    }

    function initializeCharts() {
        console.log('📊 Starting chart initialization...');

        if (typeof Chart === 'undefined') {
            console.error('❌ Chart.js not loaded!');
            return;
        }

        if (typeof DASHBOARD_DATA === 'undefined') {
            console.error('❌ DASHBOARD_DATA not found!');
            return;
        }

        try {
            // ===== HAZARD DISTRIBUTION CHART =====
            const hazardEl = document.getElementById('hazardDistributionChart');
            if (hazardEl && DASHBOARD_DATA.hazards) {
                console.log('📈 Creating hazard distribution chart...');

                const labels = Object.keys(DASHBOARD_DATA.hazards);
                const data = Object.values(DASHBOARD_DATA.hazards);
                const colors = ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6'];

                new Chart(hazardEl, {
                    type: 'pie',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: data,
                            backgroundColor: colors.slice(0, labels.length)
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: '#fff', font: { size: 10 } }
                            }
                        }
                    }
                });
                console.log('✅ Hazard distribution chart created');
            }

            // ===== INCIDENT VELOCITY (TIMELINE) CHART =====
            const timelineEl = document.getElementById('reportsTimelineChart');
            if (timelineEl && DASHBOARD_DATA.timeline) {
                console.log('📈 Creating incident velocity chart...');

                new Chart(timelineEl, {
                    type: 'line',
                    data: {
                        labels: DASHBOARD_DATA.timeline.labels,
                        datasets: [{
                            data: DASHBOARD_DATA.timeline.data,
                            borderColor: '#0ea5e9',
                            backgroundColor: 'rgba(14, 165, 233, 0.2)',
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: { ticks: { color: '#fff' }, grid: { display: false } },
                            y: { ticks: { color: '#fff' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                        }
                    }
                });
                console.log('✅ Incident velocity chart created');
            }

            // ===== NETWORK PARTICIPATION CHART =====
            const userEl = document.getElementById('userEngagementChart');
            if (userEl && DASHBOARD_DATA.users) {
                console.log('📈 Creating network participation chart...');

                new Chart(userEl, {
                    type: 'bar',
                    data: {
                        labels: ['Total Users', 'Active Users'],
                        datasets: [{
                            data: [DASHBOARD_DATA.users.total, DASHBOARD_DATA.users.active],
                            backgroundColor: ['#0ea5e9', '#10b981']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: { ticks: { color: '#fff' }, grid: { display: false } },
                            y: { ticks: { color: '#fff' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                        }
                    }
                });
                console.log('✅ Network participation chart created');
            }

            console.log('✅ All charts initialized with real data');
        } catch (error) {
            console.error('❌ Chart error:', error);
        }
    }
})();
