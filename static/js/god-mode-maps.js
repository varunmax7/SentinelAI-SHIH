class GodModeMap {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        
        // Wrapper default style checks
        if(this.container) {
            this.container.style.position = 'relative';
            this.container.style.overflow = 'hidden';
            
            // Add vignette effect (3D depth feeling) without harsh glows
            const vignette = document.createElement('div');
            vignette.style.position = 'absolute';
            vignette.style.top = '0';
            vignette.style.left = '0';
            vignette.style.width = '100%';
            vignette.style.height = '100%';
            vignette.style.pointerEvents = 'none';
            vignette.style.boxShadow = 'inset 0 0 80px rgba(0,0,0,0.4)';
            vignette.style.zIndex = '10';
            this.container.appendChild(vignette);

            // Remove any leaflet specific filters that make it dark/inverted
            this.container.style.filter = 'none';
            this.container.classList.remove('map-tiles');
        }

        this.map = new maplibregl.Map({
            container: containerId,
            style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
            center: options.center || [78.9, 20.5],
            zoom: options.zoom || 4,
            pitch: 55, // God mode default
            bearing: -12.5, // God mode default
            antialias: true,
            interactive: true
        });

        this.isLoaded = false;
        this.pendingOps = [];

        this.map.on('load', () => {
            this.isLoaded = true;
            this.addPulsingDot();
            
            while(this.pendingOps.length > 0) {
                this.pendingOps.shift()();
            }
        });

        if (options.showLiveUI) {
            this.addLiveUIBadge();
        }

        // Keep track of added sources/layers so we can clear them dynamically
        this.addedSources = [];
        this.addedLayers = [];
        this.popups = [];
    }

    executeWhenLoaded(fn) {
        if (this.isLoaded) fn();
        else this.pendingOps.push(fn);
    }

    addLiveUIBadge() {
        const liveBadge = document.createElement('div');
        liveBadge.style.position = 'absolute';
        liveBadge.style.top = '15px';
        liveBadge.style.right = '15px';
        liveBadge.style.zIndex = '20';
        liveBadge.style.background = 'rgba(15,23,42,0.9)';
        liveBadge.style.backdropFilter = 'blur(10px)';
        liveBadge.style.WebkitBackdropFilter = 'blur(10px)';
        liveBadge.style.borderRadius = '20px';
        liveBadge.style.padding = '8px 15px';
        liveBadge.style.display = 'flex';
        liveBadge.style.alignItems = 'center';
        liveBadge.style.gap = '8px';
        liveBadge.style.border = '1px solid rgba(255,255,255,0.1)';
        liveBadge.style.boxShadow = '0 4px 15px rgba(0,0,0,0.3)';
        
        let style = document.getElementById('godmap-styles');
        if (!style) {
            style = document.createElement('style');
            style.id = 'godmap-styles';
            style.innerHTML = `
                @keyframes mapLedPulse {
                    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); opacity: 0.8; }
                    70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); opacity: 1; }
                    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); opacity: 0.8; }
                }
            `;
            document.head.appendChild(style);
        }
        
        const dot = document.createElement('div');
        dot.style.width = '10px';
        dot.style.height = '10px';
        dot.style.backgroundColor = '#10b981';
        dot.style.borderRadius = '50%';
        dot.style.animation = 'mapLedPulse 1.5s infinite';
        
        const text = document.createElement('span');
        text.innerHTML = '<strong style="color:white; font-size:13px;">LIVE</strong> <span style="color:#9ca3af; font-size:12px;">Updates Every 1s</span>';
        
        liveBadge.appendChild(dot);
        liveBadge.appendChild(text);
        this.container.appendChild(liveBadge);
    }

    addPulsingDot() {
        if(this.map.hasImage('pulsing-dot')) return;
        
        const size = 150;
        const color = [239, 68, 68]; // Tailwind Deep Red
        const mapInstance = this.map;

        const pulsingDot = {
            width: size,
            height: size,
            data: new Uint8Array(size * size * 4),
            onAdd: function() {
                const canvas = document.createElement('canvas');
                canvas.width = this.width;
                canvas.height = this.height;
                this.context = canvas.getContext('2d', { willReadFrequently: true });
            },
            render: function() {
                const duration = 1500;
                const t = (performance.now() % duration) / duration;

                const radius = (size / 2) * 0.3;
                const outerRadius = (size / 2) * 0.8 * t + radius;
                const context = this.context;

                context.clearRect(0, 0, this.width, this.height);
                
                // Drop shadow
                context.shadowColor = 'rgba(0,0,0,0.5)';
                context.shadowBlur = 10;
                context.shadowOffsetX = 0;
                context.shadowOffsetY = 5;

                // Outer animated ring
                context.beginPath();
                context.arc(this.width / 2, this.height / 2, outerRadius, 0, Math.PI * 2);
                context.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${1 - t})`;
                context.fill();

                // Inner static dot
                context.beginPath();
                context.arc(this.width / 2, this.height / 2, radius, 0, Math.PI * 2);
                context.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 1)`;
                context.strokeStyle = 'white';
                context.lineWidth = 2 + 3 * (1 - t);
                context.fill();
                context.stroke();

                this.data = context.getImageData(0, 0, this.width, this.height).data;
                
                mapInstance.triggerRepaint();
                return true; 
            }
        };

        this.map.addImage('pulsing-dot', pulsingDot, { pixelRatio: 2 });
    }

    setHeatmapData(points, autoZoom = true) {
        this.executeWhenLoaded(() => {
            const geojson = {
                type: 'FeatureCollection',
                features: points.map(p => ({
                    type: 'Feature',
                    properties: { intensity: p[2] || 0.5 },
                    geometry: { type: 'Point', coordinates: [p[1], p[0]] }
                }))
            };

            const sourceId = 'heatmap-source';
            const layerId = 'heatmap-layer';

            if (this.map.getSource(sourceId)) {
                this.map.getSource(sourceId).setData(geojson);
            } else {
                this.map.addSource(sourceId, { type: 'geojson', data: geojson });
                this.addedSources.push(sourceId);

                this.map.addLayer({
                    id: layerId,
                    type: 'heatmap',
                    source: sourceId,
                    paint: {
                        'heatmap-weight': ['get', 'intensity'],
                        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 9, 3],
                        'heatmap-color': [
                            'interpolate', ['linear'], ['heatmap-density'],
                            0, 'rgba(255, 255, 255, 0)',
                            0.2, '#fcd34d',
                            0.4, '#f59e0b',
                            0.6, '#ea580c',
                            0.8, '#dc2626',
                            1, '#991b1b'
                        ],
                        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 8, 9, 35],
                        'heatmap-opacity': 0.85
                    }
                });
                this.addedLayers.push(layerId);
            }

            // Autofocus only if requested
            if (autoZoom && points.length > 0) {
                const bounds = new maplibregl.LngLatBounds();
                points.forEach(p => bounds.extend([p[1], p[0]]));
                if (!bounds.isEmpty()) {
                    this.map.fitBounds(bounds, {
                        padding: {top: 50, bottom: 50, left: 50, right: 50},
                        maxZoom: 8,
                        pitch: 55,
                        bearing: -12.5,
                        duration: 1500
                    });
                }
            }
        });
    }

    addShockwaveMarker(lat, lng, popupHtml = null) {
        this.executeWhenLoaded(() => {
            const id = `shockwave-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            
            this.map.addSource(id, {
                type: 'geojson',
                data: {
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [lng, lat] },
                    properties: { popupHtml }
                }
            });
            this.addedSources.push(id);

            this.map.addLayer({
                id: id,
                type: 'symbol',
                source: id,
                layout: {
                    'icon-image': 'pulsing-dot',
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true
                }
            });
            this.addedLayers.push(id);

            if (popupHtml) {
                this.map.on('click', id, (e) => {
                    const html = e.features[0].properties.popupHtml;
                    new maplibregl.Popup({ className: 'god-mode-popup' })
                        .setLngLat(e.features[0].geometry.coordinates)
                        .setHTML(html)
                        .addTo(this.map);
                });
                // Pointer cursor
                this.map.on('mouseenter', id, () => this.map.getCanvas().style.cursor = 'pointer');
                this.map.on('mouseleave', id, () => this.map.getCanvas().style.cursor = '');
            }
        });
    }

    addCirclePolygon(lat, lng, radiusMeters, color, fillOpacity, popupHtml) {
        this.executeWhenLoaded(() => {
            const id = `circle-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            
            // Generate circular polygon points manually for exact meters
            const points = 64;
            const km = radiusMeters / 1000;
            const ret = [];
            const distanceX = km / (111.320 * Math.cos(lat * Math.PI / 180));
            const distanceY = km / 110.574;

            for(let i=0; i<points; i++) {
                let theta = (i/points) * (2*Math.PI);
                let x = distanceX * Math.cos(theta);
                let y = distanceY * Math.sin(theta);
                ret.push([lng + x, lat + y]);
            }
            ret.push(ret[0]); // close loop

            this.map.addSource(id, {
                type: 'geojson',
                data: {
                    type: 'Feature',
                    properties: { popupHtml },
                    geometry: { type: 'Polygon', coordinates: [ret] }
                }
            });
            this.addedSources.push(id);

            this.map.addLayer({
                id: id + '-fill',
                type: 'fill',
                source: id,
                paint: {
                    'fill-color': color,
                    'fill-opacity': fillOpacity
                }
            });
            this.addedLayers.push(id + '-fill');
            
            this.map.addLayer({
                id: id + '-line',
                type: 'line',
                source: id,
                paint: {
                    'line-color': color,
                    'line-width': 2,
                    'line-dasharray': [2, 2]
                }
            });
            this.addedLayers.push(id + '-line');

            if (popupHtml) {
                const handlerId = id + '-fill';
                this.map.on('click', handlerId, (e) => {
                    new maplibregl.Popup({ className: 'god-mode-popup' })
                        .setLngLat(e.lngLat)
                        .setHTML(e.features[0].properties.popupHtml)
                        .addTo(this.map);
                });
                this.map.on('mouseenter', handlerId, () => this.map.getCanvas().style.cursor = 'pointer');
                this.map.on('mouseleave', handlerId, () => this.map.getCanvas().style.cursor = '');
            }
        });
    }

    // For the simulation engine
    renderSimulationZones(zones) {
        this.executeWhenLoaded(() => {
            this.clearDynamicData();
            const bounds = new maplibregl.LngLatBounds();
            
            zones.forEach(zone => {
                const color = zone.risk > 0.8 ? '#ef4444' : zone.risk > 0.6 ? '#f59e0b' : '#3b82f6';
                const html = `
                    <div style="color:#000; min-width: 200px; font-family:'Outfit',sans-serif;">
                        <div class="badge bg-dark mb-2 border border-secondary">RISK ZONE DETECTED</div>
                        <h6 class="fw-bold mb-1">${zone.location}</h6>
                        <hr class="my-1">
                        <p class="small mb-0">
                            <strong>Risk Score:</strong> ${(zone.risk * 100).toFixed(0)}%<br>
                            <strong>Type:</strong> ${zone.hazard_type.toUpperCase()}<br>
                            <strong>Radius:</strong> ${zone.radius.toFixed(0)}m
                        </p>
                    </div>
                `;
                
                this.addCirclePolygon(zone.lat, zone.lng, zone.radius, color, 0.4, html);
                this.addShockwaveMarker(zone.lat, zone.lng); // Plop a shockwave at epicenter
                
                bounds.extend([zone.lng, zone.lat]);
            });

            if (!bounds.isEmpty()) {
                this.map.fitBounds(bounds, {
                    padding: 100,
                    pitch: 55,
                    bearing: -12.5,
                    maxZoom: 10,
                    duration: 1500
                });
            }
        });
    }

    clearDynamicData() {
        this.executeWhenLoaded(() => {
            this.addedLayers.forEach(l => {
                if (this.map.getLayer(l)) this.map.removeLayer(l);
            });
            this.addedSources.forEach(s => {
                if (this.map.getSource(s)) this.map.removeSource(s);
            });
            
            this.addedLayers = [];
            this.addedSources = [];
            
            const popupsElement = document.getElementsByClassName('maplibregl-popup');
            while(popupsElement[0]) popupsElement[0].remove();
        });
    }

    setRainEffect(intensity) {
        if (!this.rainCanvas) {
            this.rainCanvas = document.createElement('canvas');
            this.rainCanvas.style.position = 'absolute';
            this.rainCanvas.style.top = '0';
            this.rainCanvas.style.left = '0';
            this.rainCanvas.style.width = '100%';
            this.rainCanvas.style.height = '100%';
            this.rainCanvas.style.pointerEvents = 'none';
            this.rainCanvas.style.zIndex = '15';
            this.container.appendChild(this.rainCanvas);
            
            this.rainCtx = this.rainCanvas.getContext('2d');
            this.raindrops = [];
            
            const resize = () => {
                if (this.container) {
                    this.rainCanvas.width = this.container.clientWidth;
                    this.rainCanvas.height = this.container.clientHeight;
                }
            };
            window.addEventListener('resize', resize);
            resize();
            
            const render = () => {
                if (!this.rainCanvas) return;
                requestAnimationFrame(render);
                
                this.rainCtx.clearRect(0, 0, this.rainCanvas.width, this.rainCanvas.height);
                
                if (this.currentRainIntensity <= 0) return;
                
                let dropsToCreate = Math.ceil(this.currentRainIntensity / 10);
                for(let i=0; i<dropsToCreate; i++) {
                    this.raindrops.push({
                        x: Math.random() * this.rainCanvas.width,
                        y: -30,
                        speed: 15 + Math.random() * 10,
                        length: 20 + Math.random() * 20
                    });
                }
                
                this.rainCtx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
                this.rainCtx.lineWidth = 1.5;
                this.rainCtx.lineCap = 'round';
                this.rainCtx.beginPath();
                
                for(let i=this.raindrops.length-1; i>=0; i--) {
                    const drop = this.raindrops[i];
                    this.rainCtx.moveTo(drop.x, drop.y);
                    this.rainCtx.lineTo(drop.x - drop.speed * 0.15, drop.y + drop.length);
                    
                    drop.y += drop.speed;
                    drop.x -= drop.speed * 0.15;
                    
                    if(drop.y > this.rainCanvas.height) {
                        this.raindrops.splice(i, 1);
                    }
                }
                this.rainCtx.stroke();
            };
            requestAnimationFrame(render);
        }
        this.currentRainIntensity = intensity;
    }
}
window.GodModeMap = GodModeMap;
