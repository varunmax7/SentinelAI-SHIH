/*
 * digital-twin.js - TwinMap: one MapLibre instance and everything that goes on it.
 *
 * The console (twin-console.js) owns state and the DOM; this file owns the map.
 * The split matters for one specific bug: basemap choice lives in the console,
 * never in a per-map callback, so two maps can never disagree about it.
 *
 * Hard rule enforced throughout: setStyle() is never called. It destroys every
 * source and layer added on top, silently. Basemap changes add and remove
 * raster layers over a permanently loaded vector style instead.
 */

(function (global) {
    "use strict";

    var L = global.TwinLayers;

    var SRC = {
        hexes: "twin-hexes-src",
        zones: "twin-zones-src",
        incidents: "twin-incidents-src",
        infrastructure: "twin-infrastructure-src",
        cctv: "twin-cctv-src",
        cctvCones: "twin-cctv-cones-src",
        water: "twin-water-src"
    };

    var EMPTY_FC = { type: "FeatureCollection", features: [] };

    var VECTOR_STYLE = "https://tiles.openfreemap.org/styles/liberty";

    function TwinMap(container, options) {
        options = options || {};
        this.container = container;
        this.citySlug = options.citySlug || null;
        this.variant = options.variant || "embedded";
        this.onCellClick = options.onCellClick || function () {};
        this.onCameraClick = options.onCameraClick || function () {};
        this.onIncidentClick = options.onIncidentClick || function () {};
        this.onError = options.onError || function () {};

        this._selectedH3 = null;
        this._hoveredH3 = null;
        this._loaded = false;
        this._initialising = false;
        this._initTimer = null;
        this._queue = [];
        this._basemap = options.basemap || "satellite";
        this._fillMode = options.fillMode || "balanced";
        this._layerVisibility = {};
        this._rasterSources = {};

        var camera = options.camera || {};

        this.map = new global.maplibregl.Map({
            container: container,
            // Never swapped. 3D buildings name the `openmaptiles` source by
            // hand, and if the base style is ever replaced by a raster-only one
            // MapLibre skips that layer silently - no error, just no buildings.
            style: VECTOR_STYLE,
            center: camera.center || [78.4867, 17.3850],
            zoom: camera.zoom || 10.6,
            pitch: camera.pitch != null ? camera.pitch : 45,
            bearing: camera.bearing != null ? camera.bearing : -12.5,
            // An explicit range, so an operator always has a way back and the
            // +/- buttons visibly bottom out instead of appearing dead.
            minZoom: 8,
            maxZoom: 18,
            maxPitch: 70,
            // Embedded in a scrolling dashboard, the wheel must scroll the page;
            // Ctrl/Cmd+wheel zooms and MapLibre shows its own hint. On the
            // full-page variant the map owns the viewport, so it takes the wheel.
            cooperativeGestures: this.variant !== "page",
            attributionControl: false,
            antialias: true
        });

        this.map.addControl(new global.maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
        this.map.addControl(new global.maplibregl.AttributionControl({ compact: true }), "bottom-right");
        this.map.addControl(new global.maplibregl.ScaleControl({ maxWidth: 90, unit: "metric" }), "bottom-left");

        var self = this;

        /* "style.load", NOT "load".
         *
         * `load` waits for every source in the style to report loaded, and the
         * OpenFreeMap Liberty style ships a `ne2_shaded` Natural Earth raster
         * whose tiles 404 above roughly zoom 6. At city zoom that source never
         * settles, so `style.loaded()` stays false, `load` never fires, and the
         * entire console silently never initialises - a blank map with no error
         * anywhere. It presented as an intermittent failure because it is a
         * race against where the camera happens to settle first.
         *
         * `style.load` fires as soon as the style spec is parsed and ready to
         * accept addSource/addLayer, which is all this needs. */
        this.map.on("style.load", function () { self._initialise(); });
        // Older/edge cases where style.load has already fired before we bound.
        if (this.map.isStyleLoaded()) this._initialise();

        // Last resort. If neither path has run, say so rather than leaving the
        // operator looking at an empty rectangle.
        this._initTimer = setTimeout(function () {
            if (self._loaded) return;
            if (self.map.getStyle() && self.map.getStyle().layers) {
                self._initialise();
                return;
            }
            self.onError(new Error("the base map style did not load"));
        }, 12000);

        this.map.on("error", function (event) {
            // MapLibre surfaces tile 404s here too; only forward real failures.
            if (event && event.error && event.error.message) {
                console.warn("[twin] map error:", event.error.message);
            }
        });
    }

    TwinMap.prototype.whenLoaded = function (fn) {
        if (this._loaded) fn();
        else this._queue.push(fn);
        return this;
    };

    /* Build sources and layers, then drain anything that was queued while the
     * style was still parsing. Guarded so the several paths that can call it
     * (style.load, the already-loaded check, the timeout) only ever run it once. */
    TwinMap.prototype._initialise = function () {
        if (this._loaded || this._initialising) return;
        this._initialising = true;
        if (this._initTimer) { clearTimeout(this._initTimer); this._initTimer = null; }
        try {
            this._initSourcesAndLayers();
            this._bindInteractions();
            this._loaded = true;
            var queued = this._queue.slice();
            this._queue = [];
            queued.forEach(function (fn) { fn(); });
        } catch (err) {
            this._initialising = false;
            this.onError(err);
        }
    };

    // ---- sources & layers ----------------------------------------------
    TwinMap.prototype._initSourcesAndLayers = function () {
        var map = this.map;

        map.addSource(SRC.hexes, {
            type: "geojson",
            data: EMPTY_FC,
            // REQUIRED before setFeatureState can address features by string
            // key. h3_index is stable across setData(), which is what lets a
            // selection survive a live refresh.
            promoteId: "h3"
        });
        map.addSource(SRC.zones, { type: "geojson", data: EMPTY_FC });
        // Plain, NOT a MapLibre-clustered source. A geojson source created with
        // `cluster: true` during style.load never produces tiles here - the
        // supercluster worker is set up too early, isSourceLoaded() then lies
        // and returns true, and every layer on it silently draws nothing. The
        // grouping is done server-side instead, per H3 cell, which is the unit
        // the operator is already looking at.
        map.addSource(SRC.incidents, { type: "geojson", data: EMPTY_FC });
        map.addSource(SRC.infrastructure, { type: "geojson", data: EMPTY_FC });
        map.addSource(SRC.cctv, { type: "geojson", data: EMPTY_FC });
        map.addSource(SRC.cctvCones, { type: "geojson", data: EMPTY_FC });
        map.addSource(SRC.water, { type: "geojson", data: EMPTY_FC });

        this._addLayer(L.buildings3dLayer());
        L.waterBodyLayers(SRC.water).forEach(this._addLayer, this);
        this._addLayer(L.twinHexFlatLayer(SRC.hexes, this._fillMode));
        this._addLayer(L.twinHexLayer(SRC.hexes, this._fillMode));
        this._addLayer(L.twinHexOutlineLayer(SRC.hexes));
        this._addLayer(L.twinHexDegradedLayer(SRC.hexes));
        this._addLayer(L.twinHexInteractionGlowLayer(SRC.hexes));
        this._addLayer(L.twinHexInteractionLayer(SRC.hexes));
        this._addLayer(L.zoneOutlineLayer(SRC.zones));
        L.cctvLayers(SRC.cctv, SRC.cctvCones).forEach(this._addLayer, this);
        this._addLayer(L.infrastructureLayer(SRC.infrastructure));
        L.incidentLayers(SRC.incidents).forEach(this._addLayer, this);
        L.incidentGroupLayers(SRC.incidents).forEach(this._addLayer, this);

        // Layers that start hidden until the operator asks for them.
        ["water-bodies", "water-bodies-outline", "water-drains-glow", "water-drains",
         "cctv", "cctv-direction", "cctv-cone", "cctv-cone-edge",
         "infrastructure", "zone-outline"].forEach(function (id) {
            this.setLayerVisible(id, false);
        }, this);

        this.applyBasemap(this._basemap);
        this._verifyLayers();
    };

    /* MapLibre skips a layer whose source name or filter does not compile, with
     * no error anywhere - the layer simply never exists and nothing draws. That
     * failure mode cost hours once; this turns it into a console warning naming
     * the layers that went missing. */
    TwinMap.prototype._verifyLayers = function () {
        var expected = L.LAYER_ORDER.filter(function (id) {
            // Basemap rasters and lazily-added overlays are legitimately absent.
            return ["satellite", "satellite-labels", "gibs", "radar", "traffic"].indexOf(id) < 0;
        });
        var missing = expected.filter(function (id) { return !this.map.getLayer(id); }, this);
        if (missing.length) {
            console.warn("[twin] layers failed to add:", missing.join(", "));
        }
        return missing;
    };

    /* Insert respecting LAYER_ORDER. MapLibre has no z-index; the beforeId
     * argument is the only thing that controls stacking. */
    TwinMap.prototype._addLayer = function (spec) {
        if (this.map.getLayer(spec.id)) this.map.removeLayer(spec.id);
        this.map.addLayer(spec, L.beforeIdFor(this.map, spec.id));
    };

    TwinMap.prototype.setLayerVisible = function (layerId, visible) {
        this._layerVisibility[layerId] = visible;
        if (!this.map.getLayer(layerId)) return;
        this.map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
    };

    TwinMap.prototype.isLayerVisible = function (layerId) {
        return !!this._layerVisibility[layerId];
    };

    // ---- basemap (raster layers only, never setStyle) -------------------
    TwinMap.prototype.applyBasemap = function (choice, gibs) {
        this._basemap = choice;
        var map = this.map;

        ["satellite", "satellite-labels", "gibs"].forEach(function (id) {
            if (map.getLayer(id)) map.removeLayer(id);
        });
        Object.keys(this._rasterSources).forEach(function (id) {
            if (map.getSource(id)) map.removeSource(id);
            delete this._rasterSources[id];
        }, this);

        if (choice === "vector") return; // the Liberty style alone

        if (choice === "gibs" && gibs && gibs.tile_template) {
            this._addRaster("gibs", gibs.tile_template, {
                attribution: "NASA EOSDIS GIBS",
                // Native to ~z9. maxzoom makes MapLibre over-zoom the last
                // valid tile rather than request tiles that do not exist.
                maxzoom: gibs.native_max_zoom || 9
            });
            return;
        }

        this._addRaster("satellite", L.ESRI_IMAGERY, {
            attribution: "&copy; Esri, Maxar, Earthstar Geographics"
        });
        // Imagery alone has no place names; the labels raster is always paired
        // with it, and both sit below the buildings layer so satellite never
        // hides the 3D city.
        this._addRaster("satellite-labels", L.ESRI_PLACES, { attribution: "" });
    };

    TwinMap.prototype._addRaster = function (id, tiles, options) {
        var sourceId = id + "-raster-src";
        if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
        this.map.addSource(sourceId, L.rasterSource(tiles, options));
        this._rasterSources[sourceId] = true;
        this._addLayer({
            id: id,
            type: "raster",
            source: sourceId,
            paint: { "raster-opacity": id === "satellite-labels" ? 0.85 : 1 }
        });
    };

    TwinMap.prototype.setOverlayRaster = function (id, tiles, opacity) {
        var sourceId = id + "-raster-src";
        if (this.map.getLayer(id)) this.map.removeLayer(id);
        if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);
        if (!tiles) return;
        this.map.addSource(sourceId, L.rasterSource(tiles, {}));
        this._rasterSources[sourceId] = true;
        this._addLayer({
            id: id,
            type: "raster",
            source: sourceId,
            paint: { "raster-opacity": opacity == null ? 0.6 : opacity }
        });
    };

    // ---- fill density (D2) ----------------------------------------------
    TwinMap.prototype.setFillMode = function (mode) {
        this._fillMode = mode;
        var expression = L.riskColorExpression(mode);
        if (this.map.getLayer("twin-hex-fill")) {
            this.map.setPaintProperty("twin-hex-fill", "fill-color", expression);
        }
        if (this.map.getLayer("twin-hexes")) {
            this.map.setPaintProperty("twin-hexes", "fill-extrusion-color", expression);
        }
    };

    TwinMap.prototype.setExtrusionScale = function (scale) {
        if (!this.map.getLayer("twin-hexes")) return;
        this.map.setPaintProperty("twin-hexes", "fill-extrusion-height",
                                  L.riskHeightExpression(scale));
    };

    // ---- data ------------------------------------------------------------
    TwinMap.prototype.setState = function (collection) {
        this._setData(SRC.hexes, collection);
        // Feature state is dropped by setData(). Without this, every live
        // refresh would visually clear the operator's selection.
        this._reapplyFeatureState();
    };

    TwinMap.prototype.setZones = function (collection) { this._setData(SRC.zones, collection); };
    TwinMap.prototype.setIncidents = function (collection) { this._setData(SRC.incidents, collection); };
    TwinMap.prototype.setInfrastructure = function (collection) { this._setData(SRC.infrastructure, collection); };
    TwinMap.prototype.setWater = function (collection) { this._setData(SRC.water, collection); };

    TwinMap.prototype.setCameras = function (collection) {
        this._setData(SRC.cctv, collection);
        // Cones are derived on the client: sending them would multiply an
        // already-large payload by roughly fourteen.
        this._setData(SRC.cctvCones, L.buildConeCollection(collection));
    };

    TwinMap.prototype._setData = function (sourceId, collection) {
        var self = this;
        this.whenLoaded(function () {
            var source = self.map.getSource(sourceId);
            if (source) source.setData(collection || EMPTY_FC);
        });
    };

    // ---- selection & hover (D1) -----------------------------------------
    TwinMap.prototype._setHexState = function (h3, state) {
        if (h3 == null || !this.map.getSource(SRC.hexes)) return;
        // Silently no-ops when the feature is not in a loaded tile - which is
        // exactly why _reapplyFeatureState exists.
        this.map.setFeatureState({ source: SRC.hexes, id: h3 }, state);
    };

    TwinMap.prototype.selectHex = function (h3) {
        if (this._selectedH3 === h3) return;
        if (this._selectedH3) this._setHexState(this._selectedH3, { selected: false });
        this._selectedH3 = h3;
        this._setHexState(h3, { selected: true });
    };

    TwinMap.prototype.clearSelection = function () {
        if (this._selectedH3) this._setHexState(this._selectedH3, { selected: false });
        this._selectedH3 = null;
    };

    TwinMap.prototype._setHover = function (h3) {
        if (this._hoveredH3 === h3) return;
        if (this._hoveredH3) this._setHexState(this._hoveredH3, { hover: false });
        this._hoveredH3 = h3;
        if (h3) this._setHexState(h3, { hover: true });
    };

    TwinMap.prototype._reapplyFeatureState = function () {
        if (this._selectedH3) this._setHexState(this._selectedH3, { selected: true });
        if (this._hoveredH3) this._setHexState(this._hoveredH3, { hover: true });
    };

    TwinMap.prototype.selectedH3 = function () { return this._selectedH3; };

    // ---- interactions ----------------------------------------------------
    TwinMap.prototype._bindInteractions = function () {
        var self = this;
        var map = this.map;
        var canvas = map.getCanvas();

        // Both grid layers, not just the extrusion. The grid is split at the
        // watch threshold, so on a calm day every cell lives in twin-hex-fill
        // and binding only to twin-hexes would make the whole map unclickable
        // exactly when nothing is wrong.
        ["twin-hex-fill", "twin-hexes"].forEach(function (layerId) {
            map.on("mousemove", layerId, function (event) {
                if (!event.features || !event.features.length) return;
                canvas.style.cursor = "pointer";
                self._setHover(event.features[0].properties.h3);
            });
            map.on("mouseleave", layerId, function () {
                canvas.style.cursor = "";
                self._setHover(null);
            });
            map.on("click", layerId, function (event) {
                if (!event.features || !event.features.length) return;
                var props = event.features[0].properties;
                self.selectHex(props.h3);
                self.onCellClick(props, event.lngLat);
            });
        });

        ["cctv", "cctv-cone"].forEach(function (layerId) {
            map.on("click", layerId, function (event) {
                if (!event.features || !event.features.length) return;
                // Stop the hex underneath from also opening its drawer.
                event.originalEvent.stopPropagation();
                self.onCameraClick(event.features[0].properties, event.lngLat);
            });
            map.on("mouseenter", layerId, function () { canvas.style.cursor = "pointer"; });
            map.on("mouseleave", layerId, function () { canvas.style.cursor = ""; });
        });

        map.on("click", "incidents", function (event) {
            if (!event.features || !event.features.length) return;
            event.originalEvent.stopPropagation();
            self.onIncidentClick(event.features[0].properties, event.lngLat);
        });

        // A group pin stands for several reports at one spot, so clicking it
        // opens that H3 cell's drawer - which lists every report inside it -
        // rather than picking one arbitrarily.
        map.on("click", "incident-groups", function (event) {
            if (!event.features || !event.features.length) return;
            event.originalEvent.stopPropagation();
            var props = event.features[0].properties;
            if (props.h3) {
                self.selectHex(props.h3);
                self.onCellClick(props, event.lngLat);
            }
        });

        ["incidents", "incident-groups"].forEach(function (layerId) {
            map.on("mouseenter", layerId, function () { canvas.style.cursor = "pointer"; });
            map.on("mouseleave", layerId, function () { canvas.style.cursor = ""; });
        });
    };

    // ---- 3D buildings (D7) ----------------------------------------------
    TwinMap.prototype.buildingsAvailable = function () {
        return this.map.getZoom() >= L.BUILDINGS_MINZOOM;
    };

    TwinMap.prototype.showBuildings = function (visible) {
        this.setLayerVisible("twin-buildings-3d", visible);
        if (visible) {
            // Buildings only exist from z13, and an extrusion viewed straight
            // down is indistinguishable from a flat fill - so ticking the box
            // while zoomed out or flat has to move the camera, not silently
            // do nothing.
            if (this.map.getZoom() < L.BUILDINGS_MINZOOM) {
                this.map.easeTo({ zoom: L.BUILDINGS_MINZOOM + 0.5, duration: 900 });
            }
            if (this.map.getPitch() < 15) {
                this.map.easeTo({ pitch: 45, duration: 600 });
            }
        }
    };

    // ---- camera helpers --------------------------------------------------
    /* Beyond this, animate nothing and jump. Two reasons, one practical and one
     * cosmetic: MapLibre's easeTo/flyTo silently do nothing on a move this
     * large (a city switch is ~500 km and left the map sitting on the old city
     * with the new city's data loaded), and even when it works, watching a
     * 500 km glide between Bengaluru and Hyderabad helps nobody. */
    var ANIMATE_MAX_DEGREES = 0.75;

    function farApart(from, to) {
        if (!from || !to) return true;
        return Math.abs(from.lng - to[0]) > ANIMATE_MAX_DEGREES ||
               Math.abs(from.lat - to[1]) > ANIMATE_MAX_DEGREES;
    }

    TwinMap.prototype._moveCamera = function (target, duration) {
        if (!target || !target.center) return;
        if (farApart(this.map.getCenter(), target.center)) {
            this.map.jumpTo(target);
            return;
        }
        var options = {};
        for (var key in target) {
            if (Object.prototype.hasOwnProperty.call(target, key)) options[key] = target[key];
        }
        options.duration = duration;
        this.map.easeTo(options);
    };

    TwinMap.prototype.resetView = function (camera) {
        if (!camera) return;
        this._moveCamera({
            center: camera.center,
            zoom: camera.zoom,
            pitch: camera.pitch,
            bearing: camera.bearing
        }, 900);
    };

    TwinMap.prototype.flyToCell = function (center, zoom) {
        this._moveCamera({ center: center, zoom: zoom || 14.5 }, 1200);
    };

    TwinMap.prototype.fitBounds = function (bbox) {
        if (!bbox) return;
        var center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2];
        this.map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
            padding: 24,
            duration: farApart(this.map.getCenter(), center) ? 0 : 900
        });
    };

    TwinMap.prototype.resize = function () { this.map.resize(); };

    TwinMap.prototype.destroy = function () {
        if (this._initTimer) { clearTimeout(this._initTimer); this._initTimer = null; }
        try { this.map.remove(); } catch (err) { /* already gone */ }
    };

    global.TwinMap = TwinMap;
    global.TwinMapSources = SRC;
    global.TwinVectorStyle = VECTOR_STYLE;
})(typeof window !== "undefined" ? window : this);
