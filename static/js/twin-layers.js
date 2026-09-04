/*
 * twin-layers.js - layer specifications and paint expressions.
 *
 * Pure data and pure functions. Nothing here touches a map instance, which is
 * what makes the paint expressions testable and keeps the one genuinely
 * fiddly part of the console - MapLibre expression syntax - in one file.
 *
 * MapLibre rules encoded here, learned the hard way:
 *   - There is no z-index. Order comes from addLayer(layer, beforeId) alone,
 *     so LAYER_ORDER below is the single source of truth for stacking.
 *   - fill-extrusion-opacity rejects data-driven expressions. Per-band opacity
 *     is therefore baked into the rgba() colour.
 *   - A bare null inside coalesce throws and the layer silently fails to add.
 *     Use ["case", ["has", k], ..., fallback] instead.
 */

(function (global) {
    "use strict";

    // ---- stacking -------------------------------------------------------
    // Bottom to top. The OpenFreeMap Liberty vector style is always beneath
    // all of this and is NEVER swapped - basemap changes add and remove raster
    // layers on top of it, because setStyle() destroys every custom layer.
    var LAYER_ORDER = [
        "satellite",
        "satellite-labels",
        "gibs",
        "twin-buildings-3d",
        "water-bodies",
        "water-bodies-outline",
        "water-drains-glow",
        "water-drains",
        "radar",
        "traffic",
        "twin-hex-fill",
        "twin-hexes",
        "twin-hex-outline",
        "twin-hexes-degraded",
        "twin-hex-interaction-glow",
        "twin-hex-interaction",
        "zone-outline",
        "cctv-cone",
        "cctv-cone-edge",
        "infrastructure",
        "cctv",
        "cctv-direction",
        "incidents",
        "incidents-detail",
        "incident-labels",
        "incident-detail-labels",
        "incident-groups",
        "incident-group-count"
    ];

    /* The layer this one must sit *below*: the first layer above it in
     * LAYER_ORDER that the map already has. Returns undefined to mean "put it
     * on top", which is what addLayer expects. */
    function beforeIdFor(map, layerId) {
        var index = LAYER_ORDER.indexOf(layerId);
        if (index < 0) return undefined;
        for (var i = index + 1; i < LAYER_ORDER.length; i++) {
            if (map.getLayer(LAYER_ORDER[i])) return LAYER_ORDER[i];
        }
        return undefined;
    }

    // ---- risk bands -----------------------------------------------------
    var STATUS_COLORS = {
        normal: [56, 189, 130],   // green
        watch: [250, 204, 21],    // amber
        warning: [249, 115, 22],  // orange
        critical: [239, 68, 68]   // red
    };

    var STATUS_FLOORS = { normal: 0, watch: 25, warning: 50, critical: 75 };

    /* Three fill densities rather than one compromise opacity.
     *
     * `balanced` is the default. `normal` carries a deliberately faint wash
     * rather than zero: on a calm day every cell in the city is normal, and an
     * alpha of 0 leaves the operator staring at bare imagery with no way to
     * tell whether the twin is running or broken. 0.07 reads as "measured, and
     * fine" while leaving roads and building footprints legible underneath.
     * `outline` is the mode for someone who wants only actionable cells, and
     * `solid` exists for projecting onto a wall, where ambient light eats the
     * low alphas. */
    var FILL_MODES = {
        solid: { normal: 0.14, watch: 0.30, warning: 0.42, critical: 0.55 },
        balanced: { normal: 0.07, watch: 0.18, warning: 0.28, critical: 0.38 },
        outline: { normal: 0.00, watch: 0.00, warning: 0.06, critical: 0.10 }
    };

    /* Below this risk score a cell gets no outline. On an ordinary day most of
     * a city sits in `normal`; outlining all ~900 of them draws a honeycomb
     * instead of a city. */
    var OUTLINE_MIN_RISK = 25;

    function rgba(triple, alpha) {
        return "rgba(" + triple[0] + "," + triple[1] + "," + triple[2] + "," + alpha + ")";
    }

    /* Step expression over risk, with per-band alpha baked into the colour -
     * fill-extrusion-opacity cannot take a data expression. */
    function riskColorExpression(mode) {
        var alphas = FILL_MODES[mode] || FILL_MODES.balanced;
        return [
            "step", ["coalesce", ["get", "risk"], 0],
            rgba(STATUS_COLORS.normal, alphas.normal),
            STATUS_FLOORS.watch, rgba(STATUS_COLORS.watch, alphas.watch),
            STATUS_FLOORS.warning, rgba(STATUS_COLORS.warning, alphas.warning),
            STATUS_FLOORS.critical, rgba(STATUS_COLORS.critical, alphas.critical)
        ];
    }

    function riskOutlineColorExpression() {
        return [
            "step", ["coalesce", ["get", "risk"], 0],
            rgba(STATUS_COLORS.normal, 0.5),
            STATUS_FLOORS.watch, rgba(STATUS_COLORS.watch, 0.75),
            STATUS_FLOORS.warning, rgba(STATUS_COLORS.warning, 0.85),
            STATUS_FLOORS.critical, rgba(STATUS_COLORS.critical, 0.95)
        ];
    }

    /* Extrusion height in metres. Purely a readability device: it separates
     * adjacent bands at an oblique angle far better than colour alone.
     *
     * Flat below the watch threshold, on purpose. A linear height meant that on
     * a calm day every one of ~900 cells grew a short column, and with
     * fill-extrusion-vertical-gradient shading each column's walls the whole
     * grid read as a dark opaque honeycomb over the imagery. Cells that are
     * merely fine should lie flat and let the city show through; height is
     * reserved for cells that are actually doing something. */
    function riskHeightExpression(scale) {
        var factor = scale == null ? 18 : scale;
        return [
            "interpolate", ["linear"], ["coalesce", ["get", "risk"], 0],
            STATUS_FLOORS.watch, 120,
            100, 100 * factor
        ];
    }

    // ---- risk grid ------------------------------------------------------
    /* The grid is drawn by TWO layers over the same source, split at the watch
     * threshold, and the split is not cosmetic.
     *
     * A fill-extrusion of zero height does not render as a flat translucent
     * fill - MapLibre still lights and vertically shades it, and 900 of them
     * stack into a near-black mass no matter how low the alpha is. On a calm
     * day, when every cell is `normal`, that blacked out the entire city.
     *
     * So calm cells get a plain `fill` (predictable alpha, no lighting) and
     * only cells that have actually risen to watch or above become extrusions,
     * where the height is carrying real information. The filters are exclusive,
     * so no cell is ever painted twice. */
    function twinHexFlatLayer(sourceId, mode) {
        return {
            id: "twin-hex-fill",
            type: "fill",
            source: sourceId,
            filter: ["<", ["coalesce", ["get", "risk"], 0], STATUS_FLOORS.watch],
            paint: { "fill-color": riskColorExpression(mode) }
        };
    }

    function twinHexLayer(sourceId, mode, heightScale) {
        return {
            id: "twin-hexes",
            type: "fill-extrusion",
            source: sourceId,
            filter: [">=", ["coalesce", ["get", "risk"], 0], STATUS_FLOORS.watch],
            paint: {
                "fill-extrusion-color": riskColorExpression(mode),
                "fill-extrusion-height": riskHeightExpression(heightScale),
                "fill-extrusion-base": 0,
                // A flat number, never an expression - see the file header.
                "fill-extrusion-opacity": 1.0,
                // Darkens the base of each column; this is what visually
                // separates neighbouring cells when the camera is pitched.
                "fill-extrusion-vertical-gradient": true
            }
        };
    }

    function twinHexOutlineLayer(sourceId) {
        return {
            id: "twin-hex-outline",
            type: "line",
            source: sourceId,
            filter: [">=", ["coalesce", ["get", "risk"], 0], OUTLINE_MIN_RISK],
            layout: { "line-join": "round" },
            paint: {
                "line-color": riskOutlineColorExpression(),
                "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.6, 14, 1.6],
                "line-opacity": 0.9
            }
        };
    }

    /* Cells whose inputs came from a failed or stale source. Dashed amber, so
     * an official can see at a glance where the twin is guessing. */
    function twinHexDegradedLayer(sourceId) {
        return {
            id: "twin-hexes-degraded",
            type: "line",
            source: sourceId,
            // From z12 only. When a shared upstream (the weather feed, say) is
            // down, *every* cell in the city is degraded at once, and outlining
            // all ~900 of them paints an amber honeycomb over the map that
            // hides the very imagery the operator is checking against. The
            // count is already reported in the stat bar and the health pill;
            // this layer's job is to show *which* cells once you are close
            // enough for that to be an actionable distinction.
            minzoom: 12,
            filter: ["==", ["coalesce", ["get", "degraded"], false], true],
            paint: {
                "line-color": "#fbbf24",
                "line-width": 1.1,
                "line-dasharray": [2, 2],
                "line-opacity": 0.55
            }
        };
    }

    /* Hover and selection are outline-only and driven entirely by feature
     * state, drawing nothing at all when neither is set. Tinting the fill
     * instead would hide the imagery exactly where the operator is looking,
     * and on a dense grid it is hard to tell which cell is actually selected. */
    function twinHexInteractionLayer(sourceId) {
        return {
            id: "twin-hex-interaction",
            type: "line",
            source: sourceId,
            layout: { "line-join": "round", "line-cap": "round" },
            paint: {
                "line-color": [
                    "case",
                    ["boolean", ["feature-state", "selected"], false], "#38d9ff",
                    ["boolean", ["feature-state", "hover"], false], "#a5f3fc",
                    "rgba(0,0,0,0)"
                ],
                "line-width": [
                    "case",
                    ["boolean", ["feature-state", "selected"], false], 2.5,
                    ["boolean", ["feature-state", "hover"], false], 1.5,
                    0
                ],
                "line-opacity": 0.95
            }
        };
    }

    /* A soft glow under the selection outline so it still reads over bright
     * satellite imagery. */
    function twinHexInteractionGlowLayer(sourceId) {
        return {
            id: "twin-hex-interaction-glow",
            type: "line",
            source: sourceId,
            paint: {
                "line-color": "#38d9ff",
                "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 9, 0],
                "line-blur": 6,
                "line-opacity": 0.4
            }
        };
    }

    function zoneOutlineLayer(sourceId) {
        return {
            id: "zone-outline",
            type: "line",
            source: sourceId,
            paint: {
                "line-color": "rgba(148, 197, 255, 0.75)",
                "line-width": 1.4,
                "line-dasharray": [3, 2]
            }
        };
    }

    // ---- 3D buildings ---------------------------------------------------
    var BUILDINGS_MINZOOM = 13;

    /* OSM height coverage is sparse across Indian cities, and a flat default
     * turns every ward into identical slabs. Falling back through the building
     * type recovers most of the real variation.
     *
     * Note the ["case", ["has", k], ...] wrapper: to-number must never be
     * evaluated on an absent property, and a bare null inside coalesce makes
     * the whole layer fail to add with no console error. */
    var STOREY_HEIGHT_M = 3.2;
    var STOREYS_BY_TYPE = [
        "apartments", 4,
        "commercial", 3,
        "retail", 2,
        "industrial", 2,
        "warehouse", 2,
        "hospital", 5,
        "school", 3,
        "college", 4,
        "university", 4,
        "hotel", 5,
        "office", 4,
        "house", 2,
        "residential", 3,
        "hut", 1
    ];

    function buildingHeightExpression() {
        var typeMatch = ["match", ["get", "building"]];
        for (var i = 0; i < STOREYS_BY_TYPE.length; i += 2) {
            typeMatch.push(STOREYS_BY_TYPE[i], STOREYS_BY_TYPE[i + 1]);
        }
        typeMatch.push(2); // default storeys for anything untagged

        return [
            "case",
            ["has", "render_height"], ["to-number", ["get", "render_height"]],
            ["has", "building:levels"],
                ["*", ["to-number", ["get", "building:levels"]], STOREY_HEIGHT_M],
            ["*", typeMatch, STOREY_HEIGHT_M]
        ];
    }

    function buildingMinHeightExpression() {
        return [
            "case",
            ["has", "render_min_height"], ["to-number", ["get", "render_min_height"]],
            0
        ];
    }

    /* Named twin-buildings-3d, not buildings-3d: the Liberty style ships its
     * own `building-3d` layer and reusing the id would collide. */
    function buildings3dLayer() {
        return {
            id: "twin-buildings-3d",
            type: "fill-extrusion",
            source: "openmaptiles",
            "source-layer": "building",
            minzoom: BUILDINGS_MINZOOM,
            paint: {
                "fill-extrusion-color": [
                    "interpolate", ["linear"], buildingHeightExpression(),
                    0, "#5b6b82",
                    20, "#7b8ca6",
                    60, "#9db0cc"
                ],
                "fill-extrusion-height": [
                    "interpolate", ["linear"], ["zoom"],
                    BUILDINGS_MINZOOM, 0,
                    BUILDINGS_MINZOOM + 0.5, buildingHeightExpression()
                ],
                "fill-extrusion-base": buildingMinHeightExpression(),
                "fill-extrusion-opacity": 0.85,
                "fill-extrusion-vertical-gradient": true
            }
        };
    }

    // ---- hydrology ------------------------------------------------------
    function waterBodyLayers(sourceId) {
        return [
            {
                id: "water-bodies",
                type: "fill",
                source: sourceId,
                filter: ["==", ["geometry-type"], "Polygon"],
                paint: { "fill-color": "#1d4ed8", "fill-opacity": 0.35 }
            },
            {
                id: "water-bodies-outline",
                type: "line",
                source: sourceId,
                filter: ["==", ["geometry-type"], "Polygon"],
                paint: { "line-color": "#60a5fa", "line-width": 0.8, "line-opacity": 0.7 }
            },
            {
                // A blurred wide line under the drains: a 1 px hairline over
                // satellite imagery is effectively invisible.
                id: "water-drains-glow",
                type: "line",
                source: sourceId,
                filter: ["==", ["geometry-type"], "LineString"],
                paint: {
                    "line-color": "#22d3ee",
                    "line-width": ["interpolate", ["linear"], ["zoom"], 11, 2, 16, 7],
                    "line-blur": 3,
                    "line-opacity": 0.28
                }
            },
            {
                id: "water-drains",
                type: "line",
                source: sourceId,
                filter: ["==", ["geometry-type"], "LineString"],
                paint: {
                    "line-color": [
                        "match", ["get", "kind"],
                        "drain", "#67e8f9",
                        "ditch", "#67e8f9",
                        "river", "#3b82f6",
                        "canal", "#38bdf8",
                        "#7dd3fc"
                    ],
                    "line-width": [
                        "interpolate", ["linear"], ["zoom"],
                        11, ["match", ["get", "kind"], "river", 1.6, 0.7],
                        16, ["match", ["get", "kind"], "river", 4.5, 2.2]
                    ],
                    "line-opacity": 0.85
                }
            }
        ];
    }

    // ---- incidents & assets --------------------------------------------
    /* Report pins come in three layers because reports cluster hard in real
     * data - one campus accounted for twenty-one of the twenty-three in this
     * database, all inside ~200 m.
     *
     * The grouping itself is done server-side, per H3 cell (see
     * serializers.incidents_collection). MapLibre's own `cluster: true` is not
     * used: a clustered geojson source created during style.load silently
     * never produces tiles, and the H3 cell is the unit the operator already
     * has on screen, so a group pin can open that cell's drawer and list every
     * report inside it.
     *
     *   incidents        - reports that are alone in their cell, at all zooms
     *   incidents-detail - members of a group, only once zoomed in far enough
     *                      for them to visibly separate
     *   incident-groups  - one badge per crowded cell, carrying the count
     */
    var GROUP_SPLIT_ZOOM = 16;

    function incidentPriorityColor() {
        return [
            "match", ["get", "priority"],
            "critical", "#ef4444",
            "high", "#f97316",
            "medium", "#facc15",
            "#38bdf8"
        ];
    }

    function incidentCirclePaint() {
        return {
            "circle-radius": [
                "interpolate", ["linear"], ["zoom"],
                9, 4,
                14, ["+", 6, ["*", 6, ["coalesce", ["get", "confidence"], 0.5]]]
            ],
            "circle-color": incidentPriorityColor(),
            // Pending reports are drawn hollow. They are shown so an operator
            // can see them, but they contribute nothing to the risk score and
            // must not read as confirmed ground truth.
            "circle-opacity": ["case", ["==", ["get", "status"], "approved"], 0.9, 0.35],
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": ["case", ["==", ["get", "status"], "approved"], 1.4, 1.0],
            "circle-stroke-opacity": 0.85
        };
    }

    function incidentLayers(sourceId) {
        return [
            {
                id: "incidents",
                type: "circle",
                source: sourceId,
                filter: ["all",
                    ["==", ["get", "kind"], "report"],
                    ["!", ["get", "grouped"]]
                ],
                paint: incidentCirclePaint()
            },
            {
                // The individual reports behind a group badge, revealed only
                // when the map is close enough that they no longer land on top
                // of each other.
                id: "incidents-detail",
                type: "circle",
                source: sourceId,
                minzoom: GROUP_SPLIT_ZOOM,
                filter: ["all",
                    ["==", ["get", "kind"], "report"],
                    ["get", "grouped"]
                ],
                paint: incidentCirclePaint()
            },
            // Two label layers rather than one with a zoom test in its filter:
            // MapLibre rejects ["zoom"] inside a filter expression, and a layer
            // whose filter fails to compile is skipped with no console error at
            // all. minzoom/maxzoom are the supported way to say this.
            labelLayer("incident-labels", sourceId, 12, undefined,
                       ["!", ["get", "grouped"]]),
            labelLayer("incident-detail-labels", sourceId, GROUP_SPLIT_ZOOM, undefined,
                       ["get", "grouped"])
        ];
    }

    function labelLayer(id, sourceId, minzoom, maxzoom, groupedTest) {
        var layer = {
            id: id,
            type: "symbol",
            source: sourceId,
            minzoom: minzoom,
            filter: ["all", ["==", ["get", "kind"], "report"], groupedTest],
            layout: {
                "text-field": ["get", "hazard_type"],
                "text-size": 10,
                "text-offset": [0, 1.3],
                "text-anchor": "top",
                "text-allow-overlap": false
            },
            paint: {
                "text-color": "#e2e8f0",
                "text-halo-color": "rgba(2,6,23,0.85)",
                "text-halo-width": 1.4
            }
        };
        if (maxzoom !== undefined) layer.maxzoom = maxzoom;
        return layer;
    }

    function incidentGroupLayers(sourceId) {
        return [
            {
                id: "incident-groups",
                type: "circle",
                source: sourceId,
                maxzoom: GROUP_SPLIT_ZOOM,
                filter: ["==", ["get", "kind"], "group"],
                paint: {
                    "circle-radius": [
                        "interpolate", ["linear"], ["get", "count"],
                        2, 11,
                        10, 15,
                        50, 22
                    ],
                    // Coloured by the worst report in the group, never an
                    // average - a critical report must not be diluted by the
                    // low-priority ones filed beside it.
                    "circle-color": incidentPriorityColor(),
                    "circle-opacity": 0.85,
                    "circle-stroke-color": "#ffffff",
                    "circle-stroke-width": 1.6,
                    "circle-stroke-opacity": 0.9
                }
            },
            {
                id: "incident-group-count",
                type: "symbol",
                source: sourceId,
                maxzoom: GROUP_SPLIT_ZOOM,
                filter: ["==", ["get", "kind"], "group"],
                layout: {
                    "text-field": ["to-string", ["get", "count"]],
                    "text-size": 12,
                    "text-allow-overlap": true,
                    "text-ignore-placement": true
                },
                paint: {
                    "text-color": "#0b1220",
                    "text-halo-color": "rgba(255,255,255,0.6)",
                    "text-halo-width": 0.9
                }
            }
        ];
    }

    function infrastructureLayer(sourceId) {
        return {
            id: "infrastructure",
            type: "circle",
            source: sourceId,
            minzoom: 12,
            paint: {
                "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 2.5, 16, 5.5],
                "circle-color": [
                    "match", ["get", "asset_type"],
                    "hospital", "#f87171",
                    "clinic", "#fca5a5",
                    "fire_station", "#fb923c",
                    "police", "#60a5fa",
                    "power_substation", "#fbbf24",
                    "water_works", "#22d3ee",
                    "pumping_station", "#22d3ee",
                    "#a78bfa"
                ],
                "circle-opacity": 0.85,
                "circle-stroke-color": "rgba(2,6,23,0.7)",
                "circle-stroke-width": 0.8
            }
        };
    }

    // ---- CCTV -----------------------------------------------------------
    /* Assumed optics by camera type. OSM almost never tags field of view or
     * range, so these are declared assumptions and the legend says so. They
     * must never be presented as surveyed coverage. */
    var CAMERA_OPTICS = {
        fixed: { fov: 60, range: 45 },
        panning: { fov: 180, range: 60 },  // a PTZ sweeps; show the whole envelope
        dome: { fov: 360, range: 30 },
        default: { fov: 60, range: 45 }
    };

    function cameraColorExpression() {
        return [
            "match", ["get", "kind"],
            "traffic", "#38bdf8",
            "public", "#a78bfa",
            "outdoor", "#34d399",
            "indoor", "#94a3b8",
            "#e879f9"
        ];
    }

    function cctvLayers(pointSourceId, coneSourceId) {
        return [
            {
                // Cones only from z15. A few thousand wedges at city zoom is a
                // solid smear that tells an operator nothing.
                id: "cctv-cone",
                type: "fill",
                source: coneSourceId,
                minzoom: 15,
                paint: { "fill-color": cameraColorExpression(), "fill-opacity": 0.18 }
            },
            {
                id: "cctv-cone-edge",
                type: "line",
                source: coneSourceId,
                minzoom: 15,
                paint: {
                    "line-color": cameraColorExpression(),
                    "line-width": 0.8,
                    "line-opacity": 0.5
                }
            },
            {
                id: "cctv",
                type: "circle",
                source: pointSourceId,
                minzoom: 12,
                paint: {
                    "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 1.8, 17, 4.5],
                    "circle-color": cameraColorExpression(),
                    "circle-opacity": 0.9,
                    "circle-stroke-color": "rgba(2,6,23,0.8)",
                    "circle-stroke-width": 0.6
                }
            },
            {
                id: "cctv-direction",
                type: "symbol",
                source: pointSourceId,
                minzoom: 16,
                // Cameras with no recorded bearing are excluded here entirely
                // rather than drawn pointing north.
                filter: ["all", ["has", "direction"], ["!=", ["get", "direction"], null]],
                layout: {
                    "text-field": "▲",
                    "text-size": 9,
                    "text-rotate": ["get", "direction"],
                    "text-rotation-alignment": "map",
                    "text-offset": [0, -0.9],
                    "text-allow-overlap": true,
                    "text-ignore-placement": true
                },
                paint: {
                    "text-color": cameraColorExpression(),
                    "text-halo-color": "rgba(2,6,23,0.8)",
                    "text-halo-width": 1
                }
            }
        ];
    }

    /* Forward geodesic point. Accurate to well under a metre at camera ranges. */
    function destination(lat, lon, bearingDeg, distanceM) {
        var R = 6371000, d = distanceM / R;
        var br = bearingDeg * Math.PI / 180;
        var p1 = lat * Math.PI / 180, l1 = lon * Math.PI / 180;
        var p2 = Math.asin(Math.sin(p1) * Math.cos(d) + Math.cos(p1) * Math.sin(d) * Math.cos(br));
        var l2 = l1 + Math.atan2(Math.sin(br) * Math.sin(d) * Math.cos(p1),
                                 Math.cos(d) - Math.sin(p1) * Math.sin(p2));
        return [l2 * 180 / Math.PI, p2 * 180 / Math.PI];
    }

    /* Build the view-cone FeatureCollection client-side from the /cameras
     * payload. Sending cones over the wire would multiply an already-large
     * response by roughly fourteen. */
    function buildConeCollection(cameraCollection) {
        var features = [];
        var rows = (cameraCollection && cameraCollection.features) || [];
        for (var i = 0; i < rows.length; i++) {
            var cone = viewCone(rows[i]);
            if (cone) features.push(cone);
        }
        return { type: "FeatureCollection", features: features };
    }

    function viewCone(feature) {
        var props = feature.properties || {};
        var direction = props.direction;
        // No bearing recorded means no cone. Never assume north.
        if (direction === null || direction === undefined || direction === "") return null;

        var optics = CAMERA_OPTICS[props.camera_type] || CAMERA_OPTICS.default;
        // A dome sees all round; a 360-degree wedge is a circle and is better
        // left to the point symbol than drawn as a fake direction.
        if (optics.fov >= 360) return null;

        var coords = feature.geometry && feature.geometry.coordinates;
        if (!coords) return null;
        var lon = coords[0], lat = coords[1];

        var start = Number(direction) - optics.fov / 2;
        var ring = [[lon, lat]];
        for (var i = 0; i <= 12; i++) {
            ring.push(destination(lat, lon, start + (optics.fov * i) / 12, optics.range));
        }
        ring.push([lon, lat]);

        return {
            type: "Feature",
            properties: {
                kind: props.kind,
                camera_type: props.camera_type,
                osm_id: props.osm_id,
                estimated: true
            },
            geometry: { type: "Polygon", coordinates: [ring] }
        };
    }

    // ---- raster basemaps -------------------------------------------------
    var ESRI_IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
    var ESRI_PLACES = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";

    function rasterSource(tiles, options) {
        var source = {
            type: "raster",
            tiles: [tiles],
            tileSize: 256,
            attribution: (options && options.attribution) || ""
        };
        // maxzoom on a raster source makes MapLibre over-zoom the last valid
        // tile instead of requesting tiles that do not exist. Required for
        // NASA GIBS, whose imagery is native to about zoom 9.
        if (options && options.maxzoom) source.maxzoom = options.maxzoom;
        return source;
    }

    global.TwinLayers = {
        LAYER_ORDER: LAYER_ORDER,
        beforeIdFor: beforeIdFor,
        STATUS_COLORS: STATUS_COLORS,
        STATUS_FLOORS: STATUS_FLOORS,
        FILL_MODES: FILL_MODES,
        OUTLINE_MIN_RISK: OUTLINE_MIN_RISK,
        BUILDINGS_MINZOOM: BUILDINGS_MINZOOM,
        CAMERA_OPTICS: CAMERA_OPTICS,
        ESRI_IMAGERY: ESRI_IMAGERY,
        ESRI_PLACES: ESRI_PLACES,
        rgba: rgba,
        riskColorExpression: riskColorExpression,
        riskHeightExpression: riskHeightExpression,
        twinHexFlatLayer: twinHexFlatLayer,
        twinHexLayer: twinHexLayer,
        twinHexOutlineLayer: twinHexOutlineLayer,
        twinHexDegradedLayer: twinHexDegradedLayer,
        twinHexInteractionLayer: twinHexInteractionLayer,
        twinHexInteractionGlowLayer: twinHexInteractionGlowLayer,
        zoneOutlineLayer: zoneOutlineLayer,
        buildings3dLayer: buildings3dLayer,
        buildingHeightExpression: buildingHeightExpression,
        waterBodyLayers: waterBodyLayers,
        incidentLayers: incidentLayers,
        incidentGroupLayers: incidentGroupLayers,
        GROUP_SPLIT_ZOOM: GROUP_SPLIT_ZOOM,
        infrastructureLayer: infrastructureLayer,
        cctvLayers: cctvLayers,
        buildConeCollection: buildConeCollection,
        viewCone: viewCone,
        destination: destination,
        rasterSource: rasterSource
    };
})(typeof window !== "undefined" ? window : this);
