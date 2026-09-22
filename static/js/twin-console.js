/*
 * twin-console.js - the controller.
 *
 * Owns all console state and the DOM; TwinMap owns the map. The important
 * consequence of that split: basemap, horizon and fill density live here, in
 * one object, and are applied *to* the map. A per-map callback that reads a
 * <select> directly is how two panes end up disagreeing, so nothing below ever
 * reads a control's value outside its own change handler.
 */

(function (global) {
    "use strict";

    var STORE_PREFIX = "twin.";

    /* One UI toggle can drive several MapLibre layers; `lazy` names the fetch
     * that has to happen the first time it is switched on. */
    var LAYER_GROUPS = {
        zones: { layers: ["zone-outline"], label: "Zones" },
        alerts: {
            layers: ["alert-areas", "alert-areas-outline"],
            label: "Official alerts", lazy: "alerts"
        },
        incidents: {
            layers: ["incidents", "incidents-detail", "incident-labels",
                     "incident-detail-labels", "incident-groups", "incident-group-count"],
            label: "Reports"
        },
        infrastructure: { layers: ["infrastructure"], label: "Critical assets" },
        cctv: {
            layers: ["cctv", "cctv-direction", "cctv-cone", "cctv-cone-edge"],
            label: "CCTV", lazy: "cameras"
        },
        water: {
            layers: ["water-bodies", "water-bodies-outline", "water-drains-glow", "water-drains"],
            label: "Water & drains", lazy: "water"
        },
        buildings: { layers: ["twin-buildings-3d"], label: "3D buildings" },
        radar: { layers: ["radar"], label: "Rain radar", lazy: "radar" },
        traffic: { layers: ["traffic"], label: "Traffic", lazy: "traffic" }
    };

    var DEFAULT_ON = ["incidents", "alerts"];

    function TwinConsole(root, options) {
        options = options || {};
        this.root = root;
        this.variant = root.getAttribute("data-variant") || "embedded";

        this.state = {
            city: store("city", null),
            zone: null,
            horizon: 0,
            basemap: store("basemap", "satellite"),
            fill: store("fill", "balanced"),
            showLowRisk: store("lowrisk", "1") === "1",
            layers: JSON.parse(store("layers", null) || "null") || DEFAULT_ON.slice()
        };

        this.meta = null;
        this.map = null;
        this.stream = null;
        this._lazyLoaded = {};
        this._drawerCell = null;
        this._searchTimer = null;
        this._resizeFrame = null;

        this.el = {
            map: q(root, "[data-twin-map]"),
            city: q(root, "[data-twin-city]"),
            zone: q(root, "[data-twin-zone]"),
            horizon: q(root, "[data-twin-horizon]"),
            basemap: q(root, "[data-twin-basemap]"),
            fill: q(root, "[data-twin-fill]"),
            layers: q(root, "[data-twin-layers]"),
            health: q(root, "[data-twin-health]"),
            refresh: q(root, "[data-twin-refresh]"),
            reset: q(root, "[data-twin-reset]"),
            search: q(root, "[data-twin-search]"),
            searchResults: q(root, "[data-twin-search-results]"),
            stats: q(root, "[data-twin-stats]"),
            drawer: q(root, "[data-twin-drawer]"),
            drawerTitle: q(root, "[data-twin-drawer-title]"),
            drawerBody: q(root, "[data-twin-drawer-body]"),
            drawerClose: q(root, "[data-twin-drawer-close]"),
            notice: q(root, "[data-twin-notice]"),
            footer: q(root, "[data-twin-footer]"),
            buildingsHint: q(root, "[data-twin-buildings-hint]"),
            flags: q(root, "[data-twin-flags]"),
            flagCount: q(root, "[data-twin-flag-count]"),
            alertNote: q(root, "[data-twin-alert-note]")
        };
        this._alertMeta = {};
        this._flags = [];
    }

    // ---- boot ------------------------------------------------------------
    TwinConsole.prototype.boot = function () {
        var self = this;
        this._buildLayerToggles();
        this._bindControls();
        this._observeResize();

        return fetchJSON("/api/twin/cities").then(function (meta) {
            self.meta = meta;
            if (!meta.cities || !meta.cities.length) {
                self.notice("No twin cities are configured yet. Run scripts/seed_twin.py to build the grid.");
                return;
            }
            var known = meta.cities.map(function (c) { return c.slug; });
            if (known.indexOf(self.state.city) < 0) self.state.city = known[0];

            self._fillCitySelect(meta.cities);
            self._renderFooter(meta);
            self._buildMap();
            self._startStream();
            self.refreshAll();
            self.refreshHealth();
            self.refreshFlags();
        }).catch(function (err) {
            self.notice("The digital twin API is unreachable: " + err.message +
                        ". The rest of this dashboard is unaffected.");
        });
    };

    TwinConsole.prototype.city = function () {
        if (!this.meta) return null;
        var slug = this.state.city;
        return this.meta.cities.filter(function (c) { return c.slug === slug; })[0] || null;
    };

    TwinConsole.prototype._buildMap = function () {
        var self = this;
        var city = this.city();

        this.map = new global.TwinMap(this.el.map, {
            citySlug: city.slug,
            variant: this.variant,
            camera: city.camera,
            basemap: this.state.basemap,
            fillMode: this.state.fill,
            onCellClick: function (props) { self.openCellDrawer(props.h3); },
            onCameraClick: function (props, lngLat) { self.openCameraDrawer(props, lngLat); },
            onIncidentClick: function (props) { self.openIncidentDrawer(props); },
            onAlertClick: function (props) { self.openAlertDrawer(props); },
            onError: function (err) { self.notice("Map error: " + err.message); }
        });

        this.map.whenLoaded(function () {
            // Re-apply from state unconditionally after load. It is idempotent
            // and it closes the race where the operator changes a control while
            // the map is still initialising.
            self.map.applyBasemap(self.state.basemap);
            self.map.setFillMode(self.state.fill);
            self._applyAllLayerVisibility();
            self._applyLowRiskFilter();
            self._updateBuildingsHint();
        });

        this.map.map.on("zoomend", function () { self._updateBuildingsHint(); });
    };

    // ---- data ------------------------------------------------------------
    TwinConsole.prototype.refreshAll = function () {
        var city = this.city();
        if (!city) return Promise.resolve();
        var self = this;

        var zoneParam = this.state.zone ? "&zone=" + encodeURIComponent(this.state.zone) : "";

        return Promise.all([
            fetchJSON("/api/twin/" + city.slug + "/state?horizon=" + this.state.horizon + zoneParam)
                .then(function (fc) { self.map.setState(fc); return fc; }),
            fetchJSON("/api/twin/" + city.slug + "/zones")
                .then(function (fc) { self.map.setZones(fc); }),
            fetchJSON("/api/twin/" + city.slug + "/incidents")
                .then(function (fc) { self.map.setIncidents(fc); }),
            fetchJSON("/api/twin/" + city.slug + "/summary?horizon=" + this.state.horizon)
                .then(function (summary) { self._renderStats(summary); })
        ]).then(function () {
            self.clearNotice();
            // Toggles switched on before the map existed still need their data.
            self._loadPendingLazyLayers();
        }).catch(function (err) {
            self.notice("Could not refresh the twin: " + err.message);
        });
    };

    TwinConsole.prototype.refreshState = function () {
        var city = this.city();
        if (!city || !this.map) return;
        var self = this;
        var zoneParam = this.state.zone ? "&zone=" + encodeURIComponent(this.state.zone) : "";
        fetchJSON("/api/twin/" + city.slug + "/state?horizon=" + this.state.horizon + zoneParam)
            .then(function (fc) { self.map.setState(fc); })
            .catch(function () { /* the poll will try again */ });
        // Reports are refetched on every live tick, not just at boot. A report
        // submitted from a phone has to appear on the operator's map without
        // anyone reloading the page - that is the whole point of the twin being
        // realtime, and the risk grid alone does not carry it, because a
        // pending report moves no score.
        fetchJSON("/api/twin/" + city.slug + "/incidents")
            .then(function (fc) { self.map.setIncidents(fc); })
            .catch(function () {});
        fetchJSON("/api/twin/" + city.slug + "/summary?horizon=" + this.state.horizon)
            .then(function (summary) { self._renderStats(summary); })
            .catch(function () {});
        // Official alerts expire on their own schedule, so the layer has to be
        // refetched rather than left to go stale on screen.
        if (this._lazyLoaded.alerts) {
            fetchJSON("/api/twin/" + city.slug + "/alerts")
                .then(function (fc) {
                    self.map.setAlerts(fc);
                    self._alertMeta = fc.meta || {};
                    self._renderAlertNote();
                })
                .catch(function () {});
        }
        this.refreshFlags();
    };

    // ---- agent flag queue -------------------------------------------------
    TwinConsole.prototype.refreshFlags = function () {
        var self = this;
        return fetchJSON("/api/twin/flags?status=pending").then(function (data) {
            self._flags = data.flags || [];
            self._agent = { enabled: data.agent_enabled, available: data.agent_available };
            self._renderFlagBadge(data.pending || 0);
        }).catch(function () {});
    };

    TwinConsole.prototype._renderFlagBadge = function (pending) {
        if (!this.el.flags) return;
        this.el.flags.style.display = "";
        this.el.flags.classList.toggle("has-pending", pending > 0);
        if (this.el.flagCount) this.el.flagCount.textContent = pending;
        this.el.flags.title = pending
            ? pending + " agent flag(s) awaiting review"
            : "No flags awaiting review";
    };

    TwinConsole.prototype._renderAlertNote = function () {
        if (!this.el.alertNote) return;
        var meta = this._alertMeta || {};
        if (!meta.total && !meta.live) {
            this.el.alertNote.style.display = "none";
            return;
        }
        this.el.alertNote.style.display = "";
        this.el.alertNote.textContent = meta.live
            ? meta.live + " official alert(s) in force"
            : "No official alert currently in force";
    };

    TwinConsole.prototype.openFlagQueue = function () {
        var self = this;
        this._drawerCell = null;
        this._showDrawer("Agent flags", '<p class="twin-muted">Loading…</p>');

        fetchJSON("/api/twin/flags?status=pending").then(function (data) {
            self._flags = data.flags || [];
            self.el.drawerBody.innerHTML = renderFlagQueue(data);
            // Delegated so the buttons keep working after every re-render.
            self.el.drawerBody.onclick = function (event) {
                var button = event.target.closest("[data-flag-decision]");
                if (!button) return;
                self.decideFlag(parseInt(button.getAttribute("data-flag-id"), 10),
                                button.getAttribute("data-flag-decision"));
            };
        }).catch(function (err) {
            self.el.drawerBody.innerHTML = '<p class="twin-error">Could not load the flag queue: ' +
                                           escapeHTML(err.message) + "</p>";
        });
    };

    TwinConsole.prototype.decideFlag = function (flagId, decision) {
        var self = this;
        postJSON("/api/twin/flags/" + flagId, { decision: decision })
            .then(function () {
                self.refreshFlags();
                self.openFlagQueue();
            })
            .catch(function (err) {
                self.notice("Could not " + decision + " that flag: " + err.message +
                            " (reviewing needs the official or admin role).");
            });
    };

    TwinConsole.prototype.refreshHealth = function () {
        var self = this;
        return fetchJSON("/api/twin/health").then(function (health) {
            self._renderHealth(health);
        }).catch(function () {
            self._renderHealth({ overall: "unknown", sources: [], failing: [] });
        });
    };

    TwinConsole.prototype._loadLazy = function (key) {
        if (this._lazyLoaded[key]) return Promise.resolve();
        var city = this.city();
        if (!city || !this.map) return Promise.resolve();
        var self = this;
        this._lazyLoaded[key] = true;

        if (key === "cameras") {
            return fetchJSON("/api/twin/" + city.slug + "/cameras").then(function (fc) {
                self.map.setCameras(fc);
                if (fc.pending) {
                    self.notice("Camera layer has not been ingested for " + city.name +
                                " yet. It is fetched in the background; try again shortly.");
                }
            }).catch(function () { self._lazyLoaded[key] = false; });
        }
        if (key === "alerts") {
            return fetchJSON("/api/twin/" + city.slug + "/alerts").then(function (fc) {
                self.map.setAlerts(fc);
                self._alertMeta = fc.meta || {};
                self._renderAlertNote();
            }).catch(function () { self._lazyLoaded[key] = false; });
        }
        if (key === "water") {
            return fetchJSON("/api/twin/" + city.slug + "/water").then(function (fc) {
                self.map.setWater(fc);
                if (fc.pending) {
                    self.notice("Hydrology layer has not been ingested for " + city.name + " yet.");
                }
            }).catch(function () { self._lazyLoaded[key] = false; });
        }
        if (key === "radar") {
            return fetchJSON("/api/twin/radar").then(function (radar) {
                if (radar.available) self.map.setOverlayRaster("radar", radar.tile_template, 0.6);
                else self.notice("Rain radar is unavailable right now.");
            }).catch(function () { self._lazyLoaded[key] = false; });
        }
        if (key === "traffic") {
            return fetchJSON("/api/twin/traffic").then(function (traffic) {
                if (traffic.available) self.map.setOverlayRaster("traffic", traffic.tile_template, 0.75);
                else self.notice("Traffic tiles need TOMTOM_API_KEY to be configured.");
            }).catch(function () { self._lazyLoaded[key] = false; });
        }
        return Promise.resolve();
    };

    TwinConsole.prototype._loadPendingLazyLayers = function () {
        var self = this;
        this.state.layers.forEach(function (key) {
            var group = LAYER_GROUPS[key];
            if (group && group.lazy) self._loadLazy(group.lazy);
        });
    };

    // ---- controls --------------------------------------------------------
    TwinConsole.prototype._buildLayerToggles = function () {
        if (!this.el.layers) return;
        var self = this;
        var html = Object.keys(LAYER_GROUPS).map(function (key) {
            var group = LAYER_GROUPS[key];
            var on = self.state.layers.indexOf(key) >= 0;
            return '<label class="twin-toggle" data-layer-label="' + key + '">' +
                   '<input type="checkbox" data-layer="' + key + '"' + (on ? " checked" : "") + ">" +
                   "<span>" + group.label + "</span></label>";
        }).join("");

        // Not a layer - a filter on the risk grid, so it gets its own control
        // rather than a LAYER_GROUPS entry. On by default: hiding calm cells
        // is for operators who want only actionable ones, not the default view.
        html += '<label class="twin-toggle" title="Show cells scoring under 25 as a faint wash">' +
                '<input type="checkbox" data-lowrisk' +
                (this.state.showLowRisk ? " checked" : "") + ">" +
                "<span>Low-risk cells</span></label>";

        this.el.layers.innerHTML = html;
    };

    TwinConsole.prototype._bindControls = function () {
        var self = this;

        on(this.el.city, "change", function (event) {
            self.state.city = event.target.value;
            store("city", self.state.city);
            self.state.zone = null;
            self._lazyLoaded = {};
            self.closeDrawer();
            var city = self.city();
            self._fillZoneSelect(city);
            self.map.citySlug = city.slug;
            self.map.clearSelection();
            self.map.resetView(city.camera);
            if (self.stream) self.stream.setCity(city.slug);
            self.refreshAll();
        });

        on(this.el.zone, "change", function (event) {
            self.state.zone = event.target.value || null;
            self.refreshAll();
            var city = self.city();
            var zone = (city.zones || []).filter(function (z) { return z.slug === self.state.zone; })[0];
            if (zone) self.map.flyToCell(zone.center, 12.5);
            else self.map.resetView(city.camera);
        });

        if (this.el.horizon) {
            on(this.el.horizon, "click", function (event) {
                var button = event.target.closest("[data-horizon]");
                if (!button) return;
                self.state.horizon = parseInt(button.getAttribute("data-horizon"), 10) || 0;
                Array.prototype.forEach.call(
                    self.el.horizon.querySelectorAll("[data-horizon]"),
                    function (el) {
                        el.classList.toggle("is-active",
                            el.getAttribute("data-horizon") === String(self.state.horizon));
                    });
                self.refreshState();
                if (self._drawerCell) self.openCellDrawer(self._drawerCell);
            });
        }

        on(this.el.basemap, "change", function (event) {
            self.setBasemap(event.target.value);
        });

        on(this.el.fill, "change", function (event) {
            self.state.fill = event.target.value;
            store("fill", self.state.fill);
            self.map.setFillMode(self.state.fill);
        });

        on(this.el.layers, "change", function (event) {
            var box = event.target;
            if (!box.hasAttribute) return;
            if (box.hasAttribute("data-lowrisk")) {
                self.state.showLowRisk = box.checked;
                store("lowrisk", box.checked ? "1" : "0");
                self._applyLowRiskFilter();
                return;
            }
            if (!box.hasAttribute("data-layer")) return;
            self.setLayerGroup(box.getAttribute("data-layer"), box.checked);
        });

        on(this.el.refresh, "click", function () {
            self.el.refresh.disabled = true;
            postJSON("/api/twin/refresh", { city: self.state.city })
                .then(function () { return self.refreshAll(); })
                .then(function () { return self.refreshHealth(); })
                .catch(function (err) {
                    self.notice("Refresh failed: " + err.message +
                                " (a recompute needs the official or admin role).");
                })
                .then(function () { self.el.refresh.disabled = false; });
        });

        on(this.el.reset, "click", function () {
            var city = self.city();
            if (city) self.map.resetView(city.camera);
        });

        on(this.el.drawerClose, "click", function () { self.closeDrawer(); });
        on(this.el.flags, "click", function () { self.openFlagQueue(); });

        if (this.el.search) {
            on(this.el.search, "input", function (event) {
                var text = event.target.value.trim();
                if (self._searchTimer) clearTimeout(self._searchTimer);
                if (text.length < 3) { self._renderSearch([]); return; }
                // Nominatim's usage policy requires throttling; 400 ms of quiet
                // is the documented minimum for type-ahead.
                self._searchTimer = setTimeout(function () { self._geocode(text); }, 400);
            });
        }
    };

    TwinConsole.prototype.setBasemap = function (choice) {
        this.state.basemap = choice;
        store("basemap", choice);
        var self = this;
        if (choice === "gibs") {
            fetchJSON("/api/twin/gibs").then(function (gibs) {
                self.map.applyBasemap("gibs", gibs);
                self.notice("NASA GIBS imagery is native to about zoom " +
                            gibs.native_max_zoom + "; above that it is over-zoomed, not sharper.");
            }).catch(function () { self.map.applyBasemap("satellite"); });
            return;
        }
        this.clearNotice();
        this.map.applyBasemap(choice);
    };

    TwinConsole.prototype.setLayerGroup = function (key, visible) {
        var group = LAYER_GROUPS[key];
        if (!group) return;

        var index = this.state.layers.indexOf(key);
        if (visible && index < 0) this.state.layers.push(key);
        if (!visible && index >= 0) this.state.layers.splice(index, 1);
        store("layers", JSON.stringify(this.state.layers));

        var self = this;
        var apply = function () {
            group.layers.forEach(function (layerId) {
                if (key === "buildings") self.map.showBuildings(visible);
                else self.map.setLayerVisible(layerId, visible);
            });
            self._updateBuildingsHint();
        };

        if (visible && group.lazy) this._loadLazy(group.lazy).then(apply);
        else apply();
    };

    TwinConsole.prototype._applyAllLayerVisibility = function () {
        var self = this;
        Object.keys(LAYER_GROUPS).forEach(function (key) {
            var on_ = self.state.layers.indexOf(key) >= 0;
            var group = LAYER_GROUPS[key];
            group.layers.forEach(function (layerId) {
                self.map.setLayerVisible(layerId, on_);
            });
        });
    };

    TwinConsole.prototype._applyLowRiskFilter = function () {
        // Calm cells live in their own flat layer, so the toggle is a plain
        // visibility switch rather than a filter rewrite. Default is on: hiding
        // them leaves an operator staring at an empty map on a quiet day,
        // unsure whether the twin is even running.
        if (!this.map) return;
        this.map.setLayerVisible("twin-hex-fill", this.state.showLowRisk);
    };

    // ---- drawer ----------------------------------------------------------
    TwinConsole.prototype.openCellDrawer = function (h3) {
        var city = this.city();
        if (!city) return;
        var self = this;
        this._drawerCell = h3;
        this._showDrawer("Cell " + h3.slice(0, 9) + "...", '<p class="twin-muted">Loading…</p>');

        fetchJSON("/api/twin/" + city.slug + "/cell/" + h3).then(function (detail) {
            self.el.drawerTitle.textContent = detail.zone
                ? detail.zone.name + " · " + h3.slice(0, 9)
                : "Cell " + h3.slice(0, 9);
            self.el.drawerBody.innerHTML = renderCellDetail(detail, self.state.horizon);

            // Ground imagery for the cell, not just for whichever camera the
            // operator managed to hit. A camera dot is a couple of pixels wide
            // at city zoom; the cell is the thing people actually click.
            var centre = detail.center || [];
            if (centre.length === 2) {
                var slot = self.el.drawerBody.querySelector("[data-cell-imagery]");
                fetchJSON("/api/twin/cctv/view?lat=" + centre[1] + "&lon=" + centre[0] +
                          "&city=" + encodeURIComponent(self.state.city))
                    .then(function (view) {
                        if (!slot) return;
                        slot.innerHTML = renderImagery(view, { hideNote: true });
                        bindImagery(slot, view);
                        self._watchLiveImagery(view, centre[1], centre[0], null);
                    })
                    .catch(function () {
                        if (slot) slot.innerHTML = '<p class="twin-muted twin-small">' +
                            "Imagery lookup failed.</p>";
                    });
            }
        }).catch(function (err) {
            self.el.drawerBody.innerHTML = '<p class="twin-error">Could not load this cell: ' +
                                           escapeHTML(err.message) + "</p>";
        });
    };

    TwinConsole.prototype.openCameraDrawer = function (props, lngLat) {
        var self = this;
        this._drawerCell = null;
        this._showDrawer("Camera " + (props.osm_id || ""), '<p class="twin-muted">Loading…</p>');

        var lat = lngLat ? lngLat.lat : null;
        var lon = lngLat ? lngLat.lng : null;
        var url = "/api/twin/cctv/view?lat=" + lat + "&lon=" + lon +
                  "&city=" + encodeURIComponent(this.state.city) +
                  (props.direction != null && props.direction !== "" ? "&direction=" + props.direction : "");

        fetchJSON(url).then(function (view) {
            self.el.drawerBody.innerHTML = renderCameraDetail(props, view);
            bindImagery(self.el.drawerBody, view);
            self._watchLiveImagery(view, lat, lon, props.direction);
        }).catch(function () {
            self.el.drawerBody.innerHTML = renderCameraDetail(props, {
                images: [], live: [], facing: null, nearest: null, best: null,
                best_kind: "none", caption: "Street-level imagery lookup failed." });
        });
    };

    TwinConsole.prototype.openAlertDrawer = function (props) {
        this._drawerCell = null;
        this._showDrawer(props.sender || "Official alert", renderAlertDetail(props));
    };

    TwinConsole.prototype.openIncidentDrawer = function (props) {
        this._drawerCell = null;
        this._showDrawer(props.title || "Incident", renderIncidentDetail(props));
    };

    /* Re-fetch a live webcam frame on an interval so "live" means live.
     * Only started when a live frame is actually present - polling an archival
     * photo that has not changed since 2020 would be pure noise. */
    TwinConsole.prototype._watchLiveImagery = function (view, lat, lon, direction) {
        this._stopLiveImagery();
        if (!view || !(view.live && view.live.length)) return;

        var self = this;
        var url = "/api/twin/cctv/view?lat=" + lat + "&lon=" + lon +
                  "&city=" + encodeURIComponent(this.state.city) +
                  (direction != null && direction !== "" ? "&direction=" + direction : "") +
                  "&fresh=true";
        this._liveTimer = setInterval(function () {
            // Drawer closed, or showing something else now: stop.
            if (!self.el.drawer.classList.contains("is-open")) { self._stopLiveImagery(); return; }
            fetchJSON(url).then(function (fresh) {
                (fresh.live || []).forEach(function (cam, i) {
                    var img = self.el.drawerBody.querySelector('[data-live-index="' + i + '"]');
                    var when = self.el.drawerBody.querySelector('[data-live-time="' + i + '"]');
                    // Cache-bust: the webcam URL is stable while the frame
                    // behind it changes, so without this the browser would keep
                    // showing the first frame for ever.
                    if (img && cam.thumb_url) {
                        img.src = cam.thumb_url + (cam.thumb_url.indexOf('?') < 0 ? '?' : '&') +
                                  '_t=' + Date.now();
                    }
                    if (when) when.textContent = _shortTime(cam.captured_at);
                });
            }).catch(function () {});
        }, 60000);
    };

    TwinConsole.prototype._stopLiveImagery = function () {
        if (this._liveTimer) { clearInterval(this._liveTimer); this._liveTimer = null; }
    };

    TwinConsole.prototype._showDrawer = function (title, html) {
        if (!this.el.drawer) return;
        this.el.drawerTitle.textContent = title;
        this.el.drawerBody.innerHTML = html;
        this.el.drawer.classList.add("is-open");
    };

    TwinConsole.prototype.closeDrawer = function () {
        if (!this.el.drawer) return;
        this._stopLiveImagery();
        this.el.drawer.classList.remove("is-open");
        this._drawerCell = null;
        if (this.map) this.map.clearSelection();
    };

    // ---- rendering -------------------------------------------------------
    TwinConsole.prototype._fillCitySelect = function (cities) {
        if (!this.el.city) return;
        var self = this;
        this.el.city.innerHTML = cities.map(function (c) {
            return '<option value="' + c.slug + '"' +
                   (c.slug === self.state.city ? " selected" : "") + ">" +
                   escapeHTML(c.name) + "</option>";
        }).join("");
        this._fillZoneSelect(this.city());
    };

    TwinConsole.prototype._fillZoneSelect = function (city) {
        if (!this.el.zone || !city) return;
        var options = ['<option value="">All zones</option>'];
        (city.zones || []).forEach(function (zone) {
            options.push('<option value="' + zone.slug + '">' + escapeHTML(zone.name) + "</option>");
        });
        this.el.zone.innerHTML = options.join("");
    };

    TwinConsole.prototype._renderStats = function (summary) {
        if (!this.el.stats) return;
        var counts = summary.status_counts || {};
        var cells = [
            { key: "critical", label: "Critical" },
            { key: "warning", label: "Warning" },
            { key: "watch", label: "Watch" },
            { key: "normal", label: "Normal" }
        ].map(function (band) {
            return '<span class="twin-stat twin-stat--' + band.key + '">' +
                   '<b>' + (counts[band.key] || 0) + "</b> " + band.label + "</span>";
        }).join("");

        var degraded = summary.degraded_cells
            ? '<span class="twin-stat twin-stat--degraded" title="These cells were scored from a stale or failed source">' +
              "<b>" + summary.degraded_cells + "</b> degraded</span>"
            : "";

        this.el.stats.innerHTML =
            cells + degraded +
            '<span class="twin-stat"><b>' + (summary.avg_risk || 0).toFixed(1) + "</b> avg risk</span>" +
            '<span class="twin-stat"><b>' + (summary.max_risk || 0).toFixed(1) + "</b> peak</span>" +
            '<span class="twin-stat"><b>' + (summary.incidents || 0) + "</b> reports</span>" +
            '<span class="twin-stat"><b>' + (summary.cameras || 0) + "</b> cameras</span>";
    };

    TwinConsole.prototype._renderHealth = function (health) {
        if (!this.el.health) return;
        var overall = health.overall || "unknown";
        var label = overall === "ok" ? "All sources OK"
                  : overall === "degraded" ? (health.failing || []).length + " source(s) degraded"
                  : "Source status unknown";
        this.el.health.className = "twin-health twin-health--" + overall;
        this.el.health.textContent = label;
        this.el.health.title = (health.sources || []).map(function (s) {
            return s.source + ": " + s.status + (s.error ? " (" + s.error + ")" : "");
        }).join("\n") || "No ingest has run yet.";
    };

    TwinConsole.prototype._renderFooter = function (meta) {
        if (!this.el.footer) return;
        this.el.footer.innerHTML = (meta.attributions || []).map(function (a) {
            return "<span>" + escapeHTML(a.text) + "</span>";
        }).join(" · ");
    };

    TwinConsole.prototype._updateBuildingsHint = function () {
        var hint = this.el.buildingsHint;
        var label = this.root.querySelector('[data-layer-label="buildings"]');
        if (!this.map) return;
        var box = this.root.querySelector('[data-layer="buildings"]');
        var tooFar = !this.map.buildingsAvailable();

        if (label) label.classList.toggle("is-limited", tooFar);
        if (box) {
            // Left enabled on purpose: ticking it while zoomed out flies to a
            // zoom where buildings exist, which is more useful than a disabled
            // control that explains nothing.
            box.title = tooFar
                ? "Building footprints are only published from zoom 13 — ticking this will zoom in"
                : "";
        }
        if (hint) {
            var wants = this.state.layers.indexOf("buildings") >= 0;
            hint.style.display = (wants && tooFar) ? "" : "none";
            hint.textContent = "Buildings appear from zoom 13 — zoom in to see them.";
        }
    };

    TwinConsole.prototype._renderSearch = function (results) {
        if (!this.el.searchResults) return;
        if (!results.length) { this.el.searchResults.innerHTML = ""; return; }
        var self = this;
        this.el.searchResults.innerHTML = results.map(function (r, i) {
            return '<button type="button" data-result="' + i + '">' +
                   escapeHTML(r.display_name) + "</button>";
        }).join("");
        this._searchResults = results;

        on(this.el.searchResults, "click", function (event) {
            var button = event.target.closest("[data-result]");
            if (!button) return;
            var hit = self._searchResults[parseInt(button.getAttribute("data-result"), 10)];
            if (!hit) return;
            self.map.flyToCell([parseFloat(hit.lon), parseFloat(hit.lat)], 15);
            self.el.searchResults.innerHTML = "";
            self.el.search.value = hit.display_name;
        }, true);
    };

    TwinConsole.prototype._geocode = function (text) {
        var city = this.city();
        var self = this;
        var url = "https://nominatim.openstreetmap.org/search?format=json&limit=5&q=" +
                  encodeURIComponent(text) +
                  (city && city.bbox
                      ? "&viewbox=" + city.bbox.join(",") + "&bounded=1"
                      : "");
        fetch(url, { headers: { "Accept": "application/json" } })
            .then(function (r) { return r.json(); })
            .then(function (results) { self._renderSearch(results || []); })
            .catch(function () { self._renderSearch([]); });
    };

    // ---- realtime & layout ----------------------------------------------
    TwinConsole.prototype._startStream = function () {
        var self = this;
        this.stream = new global.TwinStream({
            citySlug: this.state.city,
            onUpdate: function (message) {
                if (message && message.city && message.city !== self.state.city) return;
                self.refreshState();
                self.refreshHealth();
            },
            onStatus: function (status) {
                self.root.classList.toggle("is-live", !!status.connected);
            }
        }).start();
    };

    TwinConsole.prototype._observeResize = function () {
        if (typeof global.ResizeObserver === "undefined") return;
        var self = this;
        // Resize fires continuously while a window edge is dragged, and each
        // map.resize() is a full repaint. Coalescing to one per frame is the
        // difference between a smooth drag and a locked UI.
        var observer = new global.ResizeObserver(function () {
            if (self._resizeFrame) cancelAnimationFrame(self._resizeFrame);
            self._resizeFrame = requestAnimationFrame(function () {
                if (self.map) self.map.resize();
            });
        });
        observer.observe(this.root);
    };

    TwinConsole.prototype.notice = function (text) {
        if (!this.el.notice) return;
        this.el.notice.textContent = text;
        this.el.notice.style.display = "";
    };

    TwinConsole.prototype.clearNotice = function () {
        if (!this.el.notice) return;
        this.el.notice.style.display = "none";
    };

    // ---- detail renderers ------------------------------------------------
    function renderCellDetail(detail, horizon) {
        var horizonData = detail.horizons[String(horizon)] || detail.horizons["0"];
        if (!horizonData) return '<p class="twin-error">This cell has not been scored yet.</p>';

        var subs = horizonData.sub_scores;
        var inputs = horizonData.inputs || {};

        var bars = [
            ["Water hazard", subs.hydro, "#38bdf8"],
            ["Incidents", subs.incident, "#f97316"],
            ["Environment", subs.env, "#a78bfa"],
            ["Terrain", subs.terrain, "#34d399"],
            ["Critical infra", subs.infra, "#fbbf24"]
        ].map(function (row) {
            return '<div class="twin-bar"><span>' + row[0] + "</span>" +
                   '<div class="twin-bar-track"><i style="width:' + Math.max(2, row[1]) +
                   "%;background:" + row[2] + '"></i></div>' +
                   "<b>" + row[1].toFixed(0) + "</b></div>";
        }).join("");

        var assets = detail.assets.length
            ? "<ul class='twin-list'>" + detail.assets.slice(0, 12).map(function (a) {
                  return "<li><b>" + escapeHTML(a.asset_type.replace(/_/g, " ")) + "</b> " +
                         escapeHTML(a.name || "unnamed") + "</li>";
              }).join("") + "</ul>"
            : '<p class="twin-muted">No mapped critical assets in this cell.</p>';

        var reports = detail.reports.length
            ? "<ul class='twin-list'>" + detail.reports.map(function (r) {
                  return "<li><b>" + escapeHTML(r.title) + "</b> · " +
                         escapeHTML(r.hazard_type) + " · " + escapeHTML(r.status) +
                         " · confidence " + Math.round(r.confidence * 100) + "%</li>";
              }).join("") + "</ul>"
            : '<p class="twin-muted">No recent reports in this cell.</p>';

        var degraded = horizonData.degraded
            ? '<p class="twin-warn">Scored from a stale or failed source — treat this cell as an estimate. ' +
              escapeHTML((inputs.degraded_sources || []).join(", ")) + "</p>"
            : "";

        return '' +
            '<div class="twin-risk twin-risk--' + horizonData.status + '">' +
            "<b>" + horizonData.risk.toFixed(0) + "</b><span>" + horizonData.status +
            " · +" + horizonData.horizon_hours + "h</span></div>" +
            degraded +
            "<p class='twin-explain'>" + escapeHTML(horizonData.explanation) + "</p>" +
            "<h6>Contributing scores</h6>" + bars +
            "<h6>Terrain</h6><dl class='twin-dl'>" +
            dt("Elevation", detail.terrain.elevation_m != null ? detail.terrain.elevation_m + " m" : "unknown") +
            dt("Distance to water", detail.terrain.dist_to_water_m != null ? Math.round(detail.terrain.dist_to_water_m) + " m" : "unknown") +
            dt("Mapped drains", Math.round(detail.terrain.drain_length_m) + " m") +
            dt("Mapped cameras", detail.surveillance.camera_count) +
            "</dl>" +
            "<h6>Live inputs</h6><dl class='twin-dl'>" +
            dt("Rain now", fmt(inputs.rain_now_mm_h, " mm/h")) +
            dt("Rain forecast", fmt(inputs.rain_forecast_mm, " mm")) +
            dt("Temperature", fmt(inputs.temperature_c, " °C")) +
            dt("US AQI", fmt(inputs.aqi, "")) +
            dt("River discharge anomaly", fmt(inputs.river_discharge_anomaly, "/100") +
               " <em>(GloFAS model anomaly, not an official CWC gauge reading)</em>") +
            "</dl>" +
            "<h6>Ground imagery</h6>" +
            '<div data-cell-imagery><p class="twin-muted twin-small">Loading…</p></div>' +
            "<h6>Critical assets</h6>" + assets +
            "<h6>Reports</h6>" + reports;
    }

    /* Imagery panel, in two explicitly separate sections.
     *
     * They are separate because they are different claims. A live webcam frame
     * is current but is somewhere else in the city - there are three Windy
     * webcams across both modelled cities, so for almost every cell the nearest
     * one is kilometres away. The street-level photos genuinely show *this*
     * area but were taken years ago. Blending them into one ranked list, which
     * is what this used to do, meant a single city webcam led the panel for
     * every hexagon and buried the twelve photos that actually showed the place.
     */
    function renderImagery(view, options) {
        options = options || {};
        var live = view.live || [];
        var area = view.images || [];

        if (!live.length && !area.length) {
            return '<p class="twin-muted twin-small">' +
                   escapeHTML(view.caption || "No imagery available for this area.") + "</p>" +
                   (view.live_source_available
                       ? ""
                       : '<p class="twin-small twin-muted">No live-webcam source is ' +
                         "configured (WINDY_WEBCAMS_KEY).</p>");
        }

        var html = "";

        // --- live -----------------------------------------------------------
        if (live.length) {
            html += '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
                    '<span class="twin-imgbadge twin-imgbadge--live">● LIVE</span>' +
                    "<span>Current conditions in this city</span></div>";
            html += '<div class="twin-livegrid">' + live.slice(0, 3).map(function (cam, i) {
                return '<figure class="twin-livecam">' +
                       '<img data-live-index="' + i + '" src="' + escapeHTML(cam.thumb_url || "") +
                       '" alt="Live webcam" loading="lazy">' +
                       "<figcaption>" + escapeHTML(cam.title || cam.provider || "Webcam") +
                       " · <b>" + (cam.distance_m != null
                            ? (cam.distance_m / 1000).toFixed(1) + " km away" : "nearby") + "</b>" +
                       '<br><span data-live-time="' + i + '">' +
                       escapeHTML(_shortTime(cam.captured_at)) + "</span></figcaption></figure>";
            }).join("") + "</div>";
            // Said once, plainly. These frames are live but they are not this hexagon.
            html += '<p class="twin-small twin-muted">Live frames refresh automatically. ' +
                    "They show the city now, not this specific cell.</p></div>";
        }

        // --- this area ------------------------------------------------------
        if (area.length) {
            html += '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
                    '<span class="twin-imgbadge">THIS AREA</span>' +
                    "<span>" + area.length + " street-level photo" +
                    (area.length === 1 ? "" : "s") + " of this location</span></div>";
            html += '<div class="twin-areagrid">' + area.slice(0, 9).map(function (img, i) {
                var when = _shortDate(img.captured_at);
                return '<a class="twin-areashot" data-area-index="' + i + '" target="_blank"' +
                       ' rel="noopener" href="' + escapeHTML(img.page_url || img.full_url || "#") + '"' +
                       ' title="' + escapeHTML((img.provider || "") + " · " + when + " · " +
                                    Math.round(img.distance_m || 0) + " m away") + '">' +
                       '<img src="' + escapeHTML(img.thumb_url || "") + '" alt="" loading="lazy">' +
                       '<span class="twin-areashot-meta">' + Math.round(img.distance_m || 0) +
                       " m · " + escapeHTML(when) + "</span></a>";
            }).join("") + "</div>";
            html += '<p class="twin-small twin-muted">Archival street-level photography — ' +
                    "each frame carries its own capture date. Not a live feed.</p></div>";
        }

        if (!options.hideNote) {
            html += '<p class="twin-muted twin-small">Imagery from Windy Webcams, KartaView ' +
                    "and Mapillary. Sentinel never connects to a camera device and never " +
                    "proxies a stream.</p>";
        }
        return html;
    }

    function _shortTime(value) {
        if (!value) return "time unknown";
        var d = new Date(value);
        return isNaN(d) ? String(value) : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    function _shortDate(value) {
        if (!value) return "date unknown";
        var d = new Date(String(value).replace(" ", "T"));
        return isNaN(d) ? String(value).slice(0, 10) : d.toISOString().slice(0, 10);
    }

    /* Nothing to wire any more - the area grid is plain links and the live
     * frames are swapped in place by the refresh timer. Kept as a no-op so the
     * two call sites do not have to know that. */
    function bindImagery() {}

    function renderCameraDetail(props, view) {
        var head = "<dl class='twin-dl'>" +
            dt("Kind", escapeHTML(props.kind || "unknown")) +
            dt("Type", escapeHTML(props.camera_type || "unknown")) +
            dt("Mount", escapeHTML(props.mount || "unknown")) +
            dt("Bearing", props.direction != null && props.direction !== ""
                ? Math.round(props.direction) + "°"
                : "not recorded in OSM") +
            dt("Operator", escapeHTML(props.operator || "unknown")) +
            "</dl>";

        var coneNote = (props.direction != null && props.direction !== "")
            ? '<p class="twin-muted twin-small">The view cone is estimated from the ' +
              "camera type — field of view and range are almost never tagged in OSM — " +
              "not surveyed.</p>"
            : '<p class="twin-muted twin-small">No bearing is recorded for this camera, ' +
              "so no view cone is drawn.</p>";

        var links = "";
        if (props.stream_url) {
            links += '<p><a href="' + escapeHTML(props.stream_url) +
                     '" target="_blank" rel="noopener">Operator-published webcam ↗</a></p>';
        }
        if (props.osm_url) {
            links += '<p><a href="' + escapeHTML(props.osm_url) +
                     '" target="_blank" rel="noopener">View on OpenStreetMap ↗</a></p>';
        }

        return head + coneNote +
            "<h6>What this location looks like</h6>" + renderImagery(view) + links +
            '<p class="twin-muted twin-small">Camera locations from OpenStreetMap (ODbL).</p>';
    }

    function renderAlertDetail(props) {
        var live = props.live === true || props.live === "true";
        var district = props.geometry_kind === "district";
        return "" +
            '<div class="twin-risk twin-risk--' + (live ? "warning" : "normal") + '">' +
            "<b>" + escapeHTML(props.priority || "") + "</b><span>" +
            (live ? "in force" : "expired") + "</span></div>" +
            "<p class='twin-explain'>" + escapeHTML(props.headline || props.event || "") + "</p>" +
            "<dl class='twin-dl'>" +
            dt("Issued by", escapeHTML(props.sender || "unknown")) +
            dt("Source", escapeHTML(props.source || "")) +
            dt("Event", escapeHTML(props.event || "")) +
            dt("CAP severity", escapeHTML(props.severity || "n/a")) +
            dt("CAP certainty", escapeHTML(props.certainty || "n/a")) +
            dt("Urgency", escapeHTML(props.urgency || "n/a")) +
            dt("Effective", escapeHTML(String(props.effective_at || "unstated"))) +
            dt("Expires", escapeHTML(String(props.expires_at || "unstated"))) +
            dt("Area", escapeHTML(props.area_desc || "")) +
            "</dl>" +
            (props.instruction
                ? "<h6>Instruction</h6><p>" + escapeHTML(props.instruction) + "</p>"
                : "") +
            (district
                ? '<p class="twin-warn">Footprint is the whole district. This alert ' +
                  "carried no polygon, so the area shown is district-wide rather than " +
                  "a surveyed boundary.</p>"
                : "") +
            (live
                ? ""
                : '<p class="twin-muted">This alert has expired and no longer ' +
                  "contributes to any risk score.</p>") +
            (props.raw_url
                ? '<p><a href="' + escapeHTML(props.raw_url) +
                  '" target="_blank" rel="noopener">Original CAP document ↗</a></p>'
                : "") +
            '<p class="twin-muted twin-small">Source: NDMA SACHET (public domain), ' +
            "GDACS and USGS. Alerts are reproduced as issued and are not edited here.</p>";
    }

    function renderFlagQueue(data) {
        if (!data.agent_enabled) {
            return '<p class="twin-muted">The triage agent is switched off ' +
                   "(TWIN_AGENT_ENABLED=0). Alerts and the risk grid are unaffected.</p>";
        }
        var note = data.agent_available
            ? ""
            : '<p class="twin-warn twin-small">No language model API key is configured ' +
              "(KIMI_API_KEY / OPENROUTER_API_KEY), so the briefs below were generated " +
              "from database fields only, with no model involved.</p>";

        if (!data.flags.length) {
            return note + '<p class="twin-muted">Nothing awaiting review.</p>';
        }

        return note + data.flags.map(function (flag) {
            var citations = (flag.citations || []).map(function (c) {
                return "<li>" + escapeHTML(c.sender || c.kind || "source") + " — " +
                       escapeHTML((c.title || c.id || "").slice(0, 70)) +
                       (c.url ? ' <a href="' + escapeHTML(c.url) +
                                '" target="_blank" rel="noopener">↗</a>' : "") + "</li>";
            }).join("");

            return '<div class="twin-flag">' +
                '<div class="twin-flag-head">' +
                "<b>" + escapeHTML(flag.title || "Untitled flag") + "</b>" +
                '<span class="twin-flag-score">' + flag.risk_score + "</span></div>" +
                (flag.generated_offline
                    ? '<p class="twin-small twin-muted">Generated without a language model.</p>'
                    : "") +
                '<div class="twin-flag-brief">' + markdownish(flag.brief_md || "") + "</div>" +
                (citations ? "<h6>Cited sources</h6><ul class='twin-list'>" + citations + "</ul>" : "") +
                '<div class="twin-flag-actions">' +
                '<button type="button" class="twin-btn" data-flag-decision="approve" data-flag-id="' +
                flag.id + '">Approve</button>' +
                '<button type="button" class="twin-btn twin-btn--reject" data-flag-decision="reject" data-flag-id="' +
                flag.id + '">Reject</button></div></div>';
        }).join("");
    }

    /* Just enough markdown for the brief: bold, bullets and paragraphs. A full
     * parser is not worth the bytes, and everything is escaped first so a brief
     * can never inject markup. */
    function markdownish(text) {
        var escaped = escapeHTML(text);
        var lines = escaped.split("\n");
        var html = [];
        var inList = false;
        lines.forEach(function (line) {
            var trimmed = line.trim();
            if (trimmed.indexOf("- ") === 0) {
                if (!inList) { html.push("<ul class='twin-list'>"); inList = true; }
                html.push("<li>" + inline(trimmed.slice(2)) + "</li>");
                return;
            }
            if (inList) { html.push("</ul>"); inList = false; }
            if (trimmed) html.push("<p>" + inline(trimmed) + "</p>");
        });
        if (inList) html.push("</ul>");
        return html.join("");
    }

    function inline(text) {
        return text
            .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
            .replace(/_([^_]+)_/g, "<em>$1</em>");
    }

    function renderIncidentDetail(props) {
        return "<dl class='twin-dl'>" +
            dt("Hazard", escapeHTML(props.hazard_type || "")) +
            dt("Priority", escapeHTML(props.priority || "")) +
            dt("Verification", escapeHTML(props.status || "")) +
            dt("AI confidence", Math.round((props.confidence || 0) * 100) + "%") +
            dt("Reported", escapeHTML(String(props.timestamp || ""))) +
            dt("Location", escapeHTML(props.location || "")) +
            "</dl>" +
            (props.status !== "approved"
                ? '<p class="twin-muted">Unverified reports are shown for awareness but ' +
                  "contribute nothing to the risk score.</p>"
                : "") +
            '<p><a href="/report/' + encodeURIComponent(props.id) +
            '" target="_blank" rel="noopener">Open full report ↗</a></p>';
    }

    // ---- small helpers ---------------------------------------------------
    function q(root, selector) { return root.querySelector(selector); }

    function on(el, event, handler, replace) {
        if (!el) return;
        if (replace) el["on" + event] = handler;
        else el.addEventListener(event, handler);
    }

    function dt(label, value) {
        return "<dt>" + label + "</dt><dd>" + value + "</dd>";
    }

    function fmt(value, suffix) {
        if (value === null || value === undefined) return "n/a";
        var number = Number(value);
        return (Math.abs(number) < 10 ? number.toFixed(1) : Math.round(number)) + suffix;
    }

    function escapeHTML(text) {
        return String(text === null || text === undefined ? "" : text)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function store(key, value) {
        try {
            if (value === undefined) return global.localStorage.getItem(STORE_PREFIX + key);
            if (value === null) return global.localStorage.getItem(STORE_PREFIX + key);
            global.localStorage.setItem(STORE_PREFIX + key, value);
            return value;
        } catch (err) {
            return value === undefined || value === null ? null : value;
        }
    }

    function fetchJSON(url) {
        return fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status + " on " + url);
                }
                return response.json();
            });
    }

    function postJSON(url, body) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify(body || {})
        }).then(function (response) {
            if (!response.ok) throw new Error("HTTP " + response.status);
            return response.json();
        });
    }

    global.TwinConsole = TwinConsole;
    global.TwinLayerGroups = LAYER_GROUPS;
    // Exported so the render helpers can be exercised against a real API
    // payload without a browser, and inspected from the devtools console.
    global.TwinRender = {
        renderImagery: renderImagery,
        renderCameraDetail: renderCameraDetail,
        renderCellDetail: renderCellDetail,
        renderAlertDetail: renderAlertDetail,
        renderFlagQueue: renderFlagQueue,
        markdownish: markdownish
    };
})(typeof window !== "undefined" ? window : this);
