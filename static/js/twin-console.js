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
            layers: ["alert-areas", "alert-areas-outline", "alert-wall"],
            label: "Official alerts", lazy: "alerts"
        },
        flags: {
            layers: ["flag-wall"],
            label: "Flag areas", lazy: "flags"
        },
        incidents: {
            layers: ["incidents", "incidents-detail", "incident-labels",
                     "incident-detail-labels", "incident-groups", "incident-group-count"],
            label: "Reports"
        },
        infrastructure: { layers: ["infrastructure", "twin-critical-buildings"], label: "Critical assets" },
        cctv: {
            layers: ["cctv", "cctv-direction", "cctv-cone", "cctv-cone-edge", "cctv-cone-3d"],
            label: "CCTV", lazy: "cameras"
        },
        water: {
            layers: ["water-bodies", "water-bodies-outline", "water-drains-glow", "water-drains"],
            label: "Water & drains", lazy: "water"
        },
        buildings: { layers: ["twin-buildings-3d"], label: "3D buildings" },
        terrain: { layers: [], label: "Terrain (3D relief)", lazy: "terrain" },
        radar: { layers: ["radar"], label: "Rain radar", lazy: "radar" },
        traffic: { layers: ["traffic"], label: "Traffic", lazy: "traffic" },
        osint: {
            layers: ["osint-points", "osint-aircraft", "osint-labels",
                     "osint-aircraft-labels"],
            label: "OSINT (live feeds)", lazy: "osint"
        }
    };

    var DEFAULT_ON = ["incidents", "alerts", "flags"];

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
            toggle3d: q(root, "[data-twin-3d]"),
            ground: q(root, "[data-twin-ground]"),
            osint: q(root, "[data-twin-osint]"),
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
            agent: q(root, "[data-twin-agent]"),
            agentLabel: q(root, "[data-twin-agent-label]"),
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
            self.refreshAgentStatus();
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
            onOsintClick: function (props) { self.openOsintDrawer(props); },
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
            self._startPerformanceGuard();
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
        this.refreshAgentStatus();
        // A flag's own status changes on its own schedule (approved,
        // dispatched, rejected), independent of this poll - refetched every
        // cycle once the layer has been asked for at least once, same rule
        // the alerts layer above follows.
        if (this._lazyLoaded.flags) this.refreshFlagAreas();
    };

    // ---- AI prediction agent -----------------------------------------------
    TwinConsole.prototype.refreshAgentStatus = function () {
        var self = this;
        return fetchJSON("/api/twin/agent/status").then(function (status) {
            self._agentStatus = status;
            self._renderAgentButton(status);
        }).catch(function () {
            self._renderAgentButton(null);
        });
    };

    TwinConsole.prototype._renderAgentButton = function (status) {
        if (!this.el.agent) return;
        this.el.agent.classList.remove("twin-agentbtn--live", "twin-agentbtn--fallback",
                                       "twin-agentbtn--off", "twin-agentbtn--unknown");
        if (!status) {
            this.el.agent.classList.add("twin-agentbtn--unknown");
            if (this.el.agentLabel) this.el.agentLabel.textContent = "Agent: unreachable";
            this.el.agent.title = "Could not reach the agent status endpoint.";
            return;
        }
        if (!status.enabled && !status.forecast_enabled) {
            this.el.agent.classList.add("twin-agentbtn--off");
            if (this.el.agentLabel) this.el.agentLabel.textContent = "Agent: off";
            this.el.agent.title = "Both the triage and forecast agents are switched off " +
                "(TWIN_AGENT_ENABLED=0, TWIN_FORECAST_ENABLED=0).";
            return;
        }
        if (status.llm_available) {
            this.el.agent.classList.add("twin-agentbtn--live");
            if (this.el.agentLabel) this.el.agentLabel.textContent = "Agent: " + (status.model || "live");
            this.el.agent.title = "Agent is on and using " + (status.model || "an LLM") +
                ". Click for status and a manual run.";
        } else {
            this.el.agent.classList.add("twin-agentbtn--fallback");
            if (this.el.agentLabel) this.el.agentLabel.textContent = "Agent: no LLM key";
            this.el.agent.title = "Agent is on but running on deterministic fallbacks only " +
                "(no LLM key configured). Click for status and a manual run.";
        }
    };

    TwinConsole.prototype.openAgentPanel = function () {
        var self = this;
        this._drawerCell = null;
        this._showDrawer("AI Disaster Prediction Agent", '<p class="twin-muted">Loading…</p>');
        this.refreshAgentStatus().then(function () {
            self.el.drawerBody.innerHTML = renderAgentPanel(self._agentStatus, self._lastAgentRun);
            self.el.drawerBody.onclick = function (event) {
                if (event.target.closest("[data-agent-run]")) self._runAgentNow();
            };
        });
    };

    TwinConsole.prototype._runAgentNow = function () {
        var self = this;
        var btn = this.el.drawerBody.querySelector("[data-agent-run]");
        if (btn) { btn.disabled = true; btn.textContent = "Running… (can take up to a minute)"; }
        postJSON("/api/twin/agent/run", { city: this.state.city })
            .then(function (result) {
                self._lastAgentRun = result;
                self.el.drawerBody.innerHTML = renderAgentPanel(self._agentStatus, result);
                self.el.drawerBody.onclick = function (event) {
                    if (event.target.closest("[data-agent-run]")) self._runAgentNow();
                };
                self.refreshFlags();
            })
            .catch(function (err) {
                if (btn) { btn.disabled = false; btn.textContent = "Run agent now"; }
                self.notice("Agent run failed: " + err.message +
                            " (a manual run needs the official or admin role).");
            });
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

    /* Areas are re-fetched whenever the layer is (re)loaded and on every
     * refreshAll() poll, same cadence as incidents/summary - a flag can be
     * approved, dispatched or rejected between polls and its wall must
     * track that, not just its first appearance. */
    TwinConsole.prototype.refreshFlagAreas = function () {
        var self = this;
        var city = this.city();
        if (!city || !this.map) return Promise.resolve();
        return fetchJSON("/api/twin/" + city.slug + "/flags/areas").then(function (data) {
            self.map.setFlagAreas(data.areas || []);
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

        Promise.all([
            fetchJSON("/api/twin/flags?status=pending"),
            fetchJSON("/api/twin/flags?status=approved"),
        ]).then(function (results) {
            var pending = results[0], approved = results[1];
            self._flags = (pending.flags || []).concat(approved.flags || []);
            self.el.drawerBody.innerHTML = renderFlagQueue(pending, approved);
            // Delegated so the buttons keep working after every re-render.
            self.el.drawerBody.onclick = function (event) {
                var decide = event.target.closest("[data-flag-decision]");
                if (decide) {
                    self.decideFlag(parseInt(decide.getAttribute("data-flag-id"), 10),
                                    decide.getAttribute("data-flag-decision"));
                    return;
                }
                var preview = event.target.closest("[data-flag-preview]");
                if (preview) {
                    self.previewDispatch(parseInt(preview.getAttribute("data-flag-preview"), 10));
                    return;
                }
                var send = event.target.closest("[data-flag-send]");
                if (send) {
                    self.sendDispatch(parseInt(send.getAttribute("data-flag-send"), 10));
                }
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

    // ---- dispatch (preview + send, for an already-approved flag) ---------
    TwinConsole.prototype.previewDispatch = function (flagId) {
        var panel = this.root.querySelector('[data-flag-dispatch-panel="' + flagId + '"]');
        if (panel) panel.innerHTML = '<p class="twin-muted twin-small">Checking who would be alerted…</p>';
        fetchJSON("/api/twin/flags/" + flagId + "/dispatch/preview").then(function (preview) {
            if (panel) panel.innerHTML = renderDispatchPanel(flagId, preview);
        }).catch(function (err) {
            if (panel) panel.innerHTML = '<p class="twin-error twin-small">' + escapeHTML(err.message) + "</p>";
        });
    };

    TwinConsole.prototype.sendDispatch = function (flagId) {
        var self = this;
        var note = this.root.querySelector('[data-flag-note="' + flagId + '"]');
        var btn = this.root.querySelector('[data-flag-send="' + flagId + '"]');
        if (btn) { btn.disabled = true; btn.textContent = "Sending…"; }

        postJSON("/api/twin/flags/" + flagId + "/dispatch", { note: note ? note.value.trim() : "" })
            .then(function (result) {
                var panel = self.root.querySelector('[data-flag-dispatch-panel="' + flagId + '"]');
                if (panel) {
                    panel.innerHTML = '<p class="twin-small">Dispatched to <b>' + result.recipients +
                        "</b> people (" + result.whatsapp_sent + " via WhatsApp" +
                        (result.whatsapp_failed ? ", " + result.whatsapp_failed + " failed" : "") +
                        ").</p>";
                }
            })
            .catch(function (err) {
                if (btn) { btn.disabled = false; btn.textContent = "Send Alert"; }
                self.notice("Dispatch failed: " + err.message);
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
        if (key === "terrain") {
            // No backend call - just registers the DEM sources and hillshade
            // layer the first time terrain is asked for. See section 15.8:
            // the compact card additionally gates this behind visibility and
            // a frame-rate check, applied in _startPerformanceGuard().
            self.map.enableTerrainSources();
            return Promise.resolve();
        }
        if (key === "flags") {
            return self.refreshFlagAreas();
        }
        if (key === "osint") {
            return self._loadOsint().catch(function () { self._lazyLoaded[key] = false; });
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

        on(this.el.toggle3d, "click", function () {
            var city = self.city();
            var pitch = city && city.camera ? city.camera.pitch : 55;
            var next = !self.map.is3D();
            self.map.set3D(next, pitch);
            self.el.toggle3d.classList.toggle("is-active", next);
            self.el.toggle3d.textContent = next ? "3D" : "2D";
        });

        on(this.el.drawerClose, "click", function () { self.closeDrawer(); });
        on(this.el.flags, "click", function () { self.openFlagQueue(); });
        on(this.el.agent, "click", function () { self.openAgentPanel(); });
        on(this.el.ground, "click", function () { self.openGroundBoard(); });
        on(this.el.osint, "click", function () { self.openOsintPanel(); });

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
            if (key === "buildings") {
                self.map.showBuildings(visible);
            } else if (key === "terrain") {
                self.map.setTerrainEnabled(visible);
            } else {
                group.layers.forEach(function (layerId) {
                    self.map.setLayerVisible(layerId, visible);
                });
            }
            self._updateBuildingsHint();
        };

        // OpenSky's anonymous tier is rate-limited, so the aircraft poll must
        // stop the moment nobody is looking at the layer.
        if (key === "osint" && !visible) this._stopOsintRefresh();
        if (key === "osint" && visible && this._osint) this._startOsintRefresh();

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

    // ---- performance guard (15.8) -----------------------------------------
    /* The compact dashboard card shares the page with eight other maps.
     * Terrain gets two independent safety valves here, neither of which
     * touches the operator's own on/off choice - it stays checked, this just
     * decides whether the expensive part actually renders right now: */
    TwinConsole.prototype._startPerformanceGuard = function () {
        var self = this;
        var map = this.map;
        if (!map || !map.map) return;

        // 1) Visibility: a card scrolled out of view pays the DEM/hillshade
        // cost for a mesh nobody is looking at. Paused, not torn down -
        // scrolling back into view resumes it with no re-fetch.
        if (this.variant !== "page" && typeof global.IntersectionObserver === "function") {
            var wasVisible = true;
            var observer = new global.IntersectionObserver(function (entries) {
                var visible = entries[entries.length - 1].isIntersecting;
                if (visible === wasVisible) return;
                wasVisible = visible;
                if (self.state.layers.indexOf("terrain") >= 0) map.setTerrainEnabled(visible);
            }, { threshold: 0.05 });
            observer.observe(this.root);
        }

        // 2) Frame budget: below 30 fps for a few consecutive seconds with
        // terrain on, it is switched off (and the checkbox with it) rather
        // than left silently dragging the whole dashboard down - the
        // operator is told why, via the same notice() every other degraded
        // condition uses.
        var frames = 0, windowStart = performance.now(), slowSeconds = 0, tripped = false;

        map.map.on("render", function () {
            if (tripped || !map.terrainEnabled()) return;
            frames++;
            var elapsed = performance.now() - windowStart;
            if (elapsed < 1000) return;
            var fps = frames / (elapsed / 1000);
            frames = 0;
            windowStart = performance.now();
            slowSeconds = fps < 30 ? slowSeconds + 1 : 0;

            if (slowSeconds >= 3) {
                tripped = true;
                self.setLayerGroup("terrain", false); // also updates + persists state.layers
                var box = self.root.querySelector('[data-layer="terrain"]');
                if (box) box.checked = false;
                self.notice("Terrain paused to keep the dashboard responsive.");
            }
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
                        self._loadVisionCaption(slot, centre[1], centre[0], null);
                    })
                    .catch(function () {
                        if (slot) slot.innerHTML = '<p class="twin-muted twin-small">' +
                            "Imagery lookup failed.</p>";
                    });

                self._loadCellOsint(centre[1], centre[0]);
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
            self._loadVisionCaption(self.el.drawerBody, lat, lon, props.direction);
            self._loadLiveFeeds(lat, lon);
        }).catch(function () {
            self.el.drawerBody.innerHTML = renderCameraDetail(props, {
                images: [], live: [], facing: null, nearest: null, best: null,
                best_kind: "none", caption: "Street-level imagery lookup failed." });
            self._loadLiveFeeds(lat, lon);
        });
    };

    /* One vision-model reading of the same 'best' image the drawer is already
     * showing, fetched lazily after the imagery itself renders so a slow or
     * unavailable model never blocks the photo from appearing. */
    TwinConsole.prototype._loadVisionCaption = function (container, lat, lon, direction) {
        var self = this;
        var el = container.querySelector("[data-vision-caption]");
        if (!el || lat == null || lon == null) return;

        var qs = new URLSearchParams({ lat: lat, lon: lon, city: this.state.city });
        if (direction != null && direction !== "") qs.set("direction", direction);

        fetchJSON("/api/twin/cctv/caption?" + qs.toString())
            .then(function (data) {
                if (!document.body.contains(el)) return;
                el.classList.remove("twin-vision-caption--loading");
                if (!data.available) {
                    el.textContent = "\u{1F9E0} AI reading unavailable: " + (data.reason || "not configured.");
                    el.classList.add("twin-vision-caption--muted");
                    return;
                }
                if (!data.caption) {
                    el.textContent = "\u{1F9E0} " + (data.reason || "No AI reading for this image.");
                    el.classList.add("twin-vision-caption--muted");
                    return;
                }
                var c = data.caption;
                var hazardTag = c.hazard_visible
                    ? '<span class="twin-vision-hazard">⚠ ' +
                      escapeHTML(c.hazard_label || "possible hazard") + "</span> "
                    : "";
                var modelName = (c.model || "").split("/").pop().replace(":free", "");
                el.innerHTML = "\u{1F9E0} " + hazardTag + escapeHTML(c.caption) +
                    '<span class="twin-vision-model"> · AI reading via ' +
                    escapeHTML(modelName || "vision model") + "</span>";
            })
            .catch(function () {
                if (!document.body.contains(el)) return;
                el.classList.remove("twin-vision-caption--loading");
                el.classList.add("twin-vision-caption--muted");
                el.textContent = "\u{1F9E0} AI reading failed to load.";
            });
    };

    TwinConsole.prototype._loadLiveFeeds = function (lat, lon) {
        var self = this;
        var container = this.el.drawerBody.querySelector("[data-twin-live-feeds]");
        if (!container) return;
        var params = new URLSearchParams({ city: this.state.city, radius: 3000 });
        if (lat != null) params.set("lat", lat);
        if (lon != null) params.set("lon", lon);

        fetchJSON("/api/twin/cctv/streams?" + params.toString())
            .then(function (data) { renderLiveFeeds(container, data.streams || []); })
            .catch(function () { renderLiveFeeds(container, []); });
    };

    /* OSINT for the clicked cell, not the whole city.
     *
     * Served from the same cached city collection the OSINT map layer uses,
     * so opening twenty drawers costs zero extra calls to OpenSky, EMSC,
     * EONET or FIRMS - which matters, because OpenSky's anonymous tier would
     * otherwise be exhausted by a couple of minutes of ordinary clicking.
     */
    TwinConsole.prototype._loadCellOsint = function (lat, lon) {
        var self = this;
        var slot = this.el.drawerBody.querySelector("[data-cell-osint]");
        if (!slot || lat == null || lon == null) return;
        var slug = this.state.city;

        fetchJSON("/api/twin/" + slug + "/osint/near?lat=" + lat + "&lon=" + lon)
            .then(function (data) {
                if (!document.body.contains(slot) || self.state.city !== slug) return;
                slot.innerHTML = renderCellOsint(data);
                slot.addEventListener("error", osintImageFailed, true);
            })
            .catch(function () {
                if (!document.body.contains(slot)) return;
                slot.innerHTML = '<p class="twin-muted twin-small">Open-source feeds ' +
                    "could not be reached for this point.</p>";
            });
    };

    /* ---- OSINT ----------------------------------------------------------
     *
     * Open-source intelligence for the selected city: live aircraft, regional
     * seismicity, open natural-event tracks, satellite thermal anomalies, and
     * a geocoded news list. See twin/osint.py for what each source is and
     * what was verified against its live endpoint.
     *
     * Aircraft are the only part that goes stale in seconds, so the whole
     * collection is re-fetched on a timer while the layer is on - and only
     * while it is on, because OpenSky's anonymous tier is rate-limited and
     * polling a layer nobody is looking at would spend that budget for
     * nothing.
     */
    TwinConsole.prototype._loadOsint = function () {
        var self = this;
        var city = this.city();
        if (!city || !this.map) return Promise.resolve();
        var slug = city.slug;

        return fetchJSON("/api/twin/" + slug + "/osint").then(function (fc) {
            // The operator may have switched city mid-flight; a stale answer
            // must not paint another city's aircraft onto this one.
            if (self.state.city !== slug) return;
            self._osint = fc;
            self.map.setOsint(fc);
            self._renderOsintNote(fc);
            self._startOsintRefresh();
        }).catch(function (err) {
            self.notice("OSINT feeds could not be loaded: " + err.message);
        });
    };

    TwinConsole.prototype._startOsintRefresh = function () {
        var self = this;
        this._stopOsintRefresh();
        var every = Math.max(30, (this._osint && this._osint.refresh_seconds) || 60) * 1000;
        this._osintTimer = setInterval(function () {
            if (self.state.layers.indexOf("osint") < 0) { self._stopOsintRefresh(); return; }
            var slug = self.state.city;
            fetchJSON("/api/twin/" + slug + "/osint").then(function (fc) {
                if (self.state.city !== slug || self.state.layers.indexOf("osint") < 0) return;
                self._osint = fc;
                self.map.setOsint(fc);
                self._renderOsintNote(fc);
            }).catch(function () { /* one missed refresh is not an outage */ });
        }, every);
    };

    TwinConsole.prototype._stopOsintRefresh = function () {
        if (this._osintTimer) { clearInterval(this._osintTimer); this._osintTimer = null; }
    };

    /* A one-line status under the map, in the existing notice slot. Says what
     * came back AND what did not - a source that is unkeyed or rate-limited is
     * a thing the owner can fix, and silently drawing nothing for it would
     * read as "there is no activity near this city". */
    TwinConsole.prototype._renderOsintNote = function (fc) {
        var counts = fc.counts || {};
        var live = [];
        if (counts.aircraft) live.push(counts.aircraft + " aircraft");
        if (counts.seismic) live.push(counts.seismic + " seismic");
        if (counts.events) live.push(counts.events + " natural event" + (counts.events > 1 ? "s" : ""));
        if (counts.fire) live.push(counts.fire + " thermal anomal" + (counts.fire > 1 ? "ies" : "y"));
        if (counts.news) live.push(counts.news + " news item" + (counts.news > 1 ? "s" : ""));

        var problems = (fc.sources || []).filter(function (s) {
            return s.status !== "ok" && s.status !== "cached";
        });
        var text = "OSINT within " + fc.radius_km + " km: " +
                   (live.length ? live.join(" · ") : "nothing reported right now");
        if (problems.length) {
            text += " · unavailable: " + problems.map(function (s) {
                return s.label + " (" + s.status + ")";
            }).join(", ");
        }
        this.notice(text + " — observations, not official warnings. Open ⓘ OSINT for detail.");
    };

    TwinConsole.prototype.openOsintDrawer = function (props) {
        this._drawerCell = null;
        this._showDrawer(props.title || "OSINT observation", renderOsintDetail(props));
    };

    /* The whole OSINT picture for the city, including the news list - which
     * has no coordinate and therefore never appears on the map. */
    TwinConsole.prototype.openOsintPanel = function () {
        var self = this;
        this._drawerCell = null;
        this._showDrawer("OSINT · " + (this.city() ? this.city().name : ""),
                         '<p class="twin-muted">Collecting open-source feeds…</p>');
        var slug = this.state.city;
        fetchJSON("/api/twin/" + slug + "/osint").then(function (fc) {
            if (self.state.city !== slug) return;
            self._osint = fc;
            self.map.setOsint(fc);
            self.el.drawerBody.innerHTML = renderOsintPanel(fc);
            self.el.drawerBody.addEventListener("error", osintImageFailed, true);
        }).catch(function (err) {
            self.el.drawerBody.innerHTML = '<p class="twin-error">OSINT feeds could not be ' +
                "loaded: " + escapeHTML(err.message) + "</p>";
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

    /* ---- city-wide ground imagery board --------------------------------
     *
     * The drawer's per-cell imagery answers "what does this hexagon look
     * like". This answers the question an operator asks first - show me the
     * city - by putting every location that has a picture side by side:
     * live webcam frames, photos attached to this app's own reports, and
     * archival street-level photography, each carrying its own source and
     * real age. See twin/ground.py for which sources are real and which are
     * blocked.
     *
     * Reuses the drawer rather than adding a panel: the layout is fixed, and
     * the drawer is the one surface already designed to hold a scrolling
     * detail view.
     */
    TwinConsole.prototype.openGroundBoard = function () {
        var self = this;
        this._drawerCell = null;
        this._stopGroundRefresh();
        this._groundFilter = this._groundFilter || "all";
        this._showDrawer("Ground imagery · " + (this.city() ? this.city().name : ""),
                         '<p class="twin-muted">Finding every camera and photo in this city…</p>');
        this._fetchGroundBoard(false);
    };

    TwinConsole.prototype._fetchGroundBoard = function (fresh) {
        var self = this;
        var city = this.state.city;
        return fetchJSON("/api/twin/" + encodeURIComponent(city) + "/ground-imagery" +
                         (fresh ? "?fresh=1" : ""))
            .then(function (board) {
                // The operator may have moved on while a cold build was
                // running; a board for a city that is no longer selected must
                // not overwrite whatever is on screen now.
                if (self.state.city !== city ||
                    !self.el.drawer.classList.contains("is-open")) return;
                self._groundBoard = board;
                self._renderGroundBoard();
                self._startGroundRefresh();
            })
            .catch(function (err) {
                if (self.state.city !== city) return;
                self.el.drawerBody.innerHTML = '<p class="twin-error">Could not load ground ' +
                    "imagery: " + escapeHTML(err.message) + "</p>";
            });
    };

    TwinConsole.prototype._renderGroundBoard = function () {
        var self = this;
        var board = this._groundBoard;
        if (!board) return;
        this.el.drawerTitle.textContent = "Ground imagery · " + (board.city_name || board.city);
        this.el.drawerBody.innerHTML = renderGroundBoard(board, this._groundFilter);
        // `error` does not bubble, so this listens in the capture phase. Added
        // once per render and torn down with the innerHTML that follows it.
        this.el.drawerBody.addEventListener("error", groundImageFailed, true);
        this.el.drawerBody.onclick = function (event) {
            var chip = event.target.closest("[data-ground-filter]");
            if (chip) {
                self._groundFilter = chip.getAttribute("data-ground-filter");
                self._renderGroundBoard();
                return;
            }
            var locate = event.target.closest("[data-ground-goto]");
            if (locate && self.map) {
                var parts = locate.getAttribute("data-ground-goto").split(",");
                self.map.flyToCell([parseFloat(parts[1]), parseFloat(parts[0])], 15.5);
            }
        };
    };

    /* Live frames only. The webcam URL is stable while the picture behind it
     * changes, so the server is re-asked (which bypasses only the 60-second
     * webcam cache, never the archival one) and each <img> is cache-busted. */
    TwinConsole.prototype._startGroundRefresh = function () {
        var self = this;
        this._stopGroundRefresh();
        var board = this._groundBoard;
        if (!board || !board.live_total) return;
        var every = Math.max(30, board.refresh_seconds || 60) * 1000;
        this._groundTimer = setInterval(function () {
            if (!self.el.drawer.classList.contains("is-open") ||
                !self.el.drawerBody.querySelector("[data-ground-board]")) {
                self._stopGroundRefresh();
                return;
            }
            fetchJSON("/api/twin/" + encodeURIComponent(self.state.city) +
                      "/ground-imagery?fresh=1")
                .then(function (fresh) {
                    if (!self.el.drawerBody.querySelector("[data-ground-board]")) return;
                    self._groundBoard = fresh;
                    (fresh.locations || []).forEach(function (loc) {
                        (loc.images || []).forEach(function (img) {
                            if (!img.live) return;
                            var node = self.el.drawerBody.querySelector(
                                '[data-ground-img="' + cssEscape(img.id) + '"]');
                            if (node && img.thumb_url) {
                                node.src = img.thumb_url +
                                    (img.thumb_url.indexOf("?") < 0 ? "?" : "&") + "_t=" + Date.now();
                            }
                            var age = self.el.drawerBody.querySelector(
                                '[data-ground-age="' + cssEscape(img.id) + '"]');
                            if (age) age.textContent = img.age_label;
                        });
                    });
                })
                .catch(function () { /* one missed refresh is not an outage */ });
        }, every);
    };

    TwinConsole.prototype._stopGroundRefresh = function () {
        if (this._groundTimer) { clearInterval(this._groundTimer); this._groundTimer = null; }
    };

    TwinConsole.prototype._showDrawer = function (title, html) {
        if (!this.el.drawer) return;
        // Every panel that needs one installs its own drawer-body click
        // handler. Clearing it here stops the previous panel's handler
        // outliving its markup, which is how a stale handler ends up running
        // against a different panel's DOM.
        this.el.drawerBody.onclick = null;
        this._stopGroundRefresh();
        this.el.drawerTitle.textContent = title;
        this.el.drawerBody.innerHTML = html;
        this.el.drawer.classList.add("is-open");
    };

    TwinConsole.prototype.closeDrawer = function () {
        if (!this.el.drawer) return;
        this._stopLiveImagery();
        this._stopGroundRefresh();
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
            '<div data-cell-imagery>' + renderAerialPlaceholder(detail.aerial) + "</div>" +
            "<h6>OSINT near this point</h6>" +
            '<div data-cell-osint><p class="twin-muted twin-small">Checking open ' +
            "feeds\u2026</p></div>" +
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
    /* Something true about THIS cell, on screen immediately.
     *
     * The imagery panel needs five to seventeen KartaView round trips on a
     * cold cell and can take twenty seconds. The satellite crop needs none -
     * it is a URL built from the cell centre that the browser fetches straight
     * from Esri - so the drawer can show a picture of the right place while
     * the ground-level search is still running, instead of a bare "Loading".
     */

    /* ---- OSINT rendering -------------------------------------------------
     *
     * Two views: one observation (clicked on the map) and the whole city's
     * picture (the header button). Both state the provider and the age on
     * every row, and both say plainly that none of this is an official
     * warning - that distinction is the difference between an IMD red alert
     * and a stranger's aircraft transponder.
     */
    var OSINT_KIND_LABEL = {
        aircraft: "Aircraft",
        seismic: "Seismic event",
        events: "Natural event",
        fire: "Thermal anomaly",
        news: "News"
    };

    function osintRow(label, value) {
        return value == null || value === "" ? "" : dt(label, value);
    }


    /* What open sources can see at ONE point.
     *
     * Three separate claims, kept separate on purpose:
     *
     *   cameras       is anything actually looking at this spot (almost never)
     *   observations  what OSINT detected within the radius of this spot
     *   city_news     reporting about the city, which is NOT about this street
     *
     * The section is never allowed to render empty. "Nothing within 25 km"
     * plus the real distance to the nearest thing is an answer; a blank panel
     * reads as a broken feed, which is the failure this whole section exists
     * to avoid.
     */

    /* News as cards that lead with the article's own image.
     *
     * GDELT carries each article's og:image as `socialimage`. It is hotlinked
     * straight from the publisher - the server never fetches or re-hosts it -
     * and a good share of articles have none at all, or have one whose URL is
     * already dead. So the card is built to read correctly with no image, and
     * a failed load removes the thumbnail rather than leaving a broken frame
     * with alt text sitting in the drawer.
     */
    function renderNewsCards(items, limit) {
        if (!items || !items.length) return "";
        return '<div class="twin-newsgrid">' + items.slice(0, limit || 12).map(function (a) {
            var hasImage = !!a.image_url;
            var thumb = hasImage
                ? '<img class="twin-newscard-thumb" data-news-img loading="lazy" alt="" src="' +
                  escapeHTML(a.image_url) + '">'
                : "";
            var body =
                '<div class="twin-newscard-body">' +
                '<span class="twin-newscard-title">' + escapeHTML(a.title || "Untitled") + "</span>" +
                '<span class="twin-newscard-meta">' + escapeHTML(a.domain || "") +
                (a.age_label ? " · " + escapeHTML(a.age_label) : "") + "</span></div>";
            var cls = "twin-newscard" + (hasImage ? "" : " twin-newscard--textonly");
            return a.page_url
                ? '<a class="' + cls + '" href="' + escapeHTML(a.page_url) +
                  '" target="_blank" rel="noopener">' + thumb + body + "</a>"
                : '<div class="' + cls + '">' + thumb + body + "</div>";
        }).join("") + "</div>";
    }

    /* `error` does not bubble, so this listens in the capture phase. A dead
     * publisher image drops to the text-only layout instead of showing a
     * broken-image glyph. */
    function osintImageFailed(event) {
        var img = event.target;
        if (!img || img.tagName !== "IMG" || !img.hasAttribute("data-news-img")) return;
        var card = img.closest(".twin-newscard");
        img.remove();
        if (card) card.classList.add("twin-newscard--textonly");
    }

    function renderCellOsint(data) {
        var html = "";
        var cams = data.cameras || {};

        // --- live cameras ------------------------------------------------
        if ((cams.covering || []).length) {
            html += '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
                '<span class="twin-imgbadge twin-imgbadge--live">● LIVE</span>' +
                "<span>" + cams.covering.length + " camera" +
                (cams.covering.length > 1 ? "s" : "") + " covering this point</span></div>" +
                '<ul class="twin-osint-list">' + cams.covering.map(function (c) {
                    return "<li>" + (c.url
                        ? '<a href="' + escapeHTML(c.url) + '" target="_blank" rel="noopener">' +
                          escapeHTML(c.name) + "</a>"
                        : "<b>" + escapeHTML(c.name) + "</b>") +
                        '<span class="twin-muted"> · ' + c.distance_km + " km · " +
                        escapeHTML(c.source || "") + "</span></li>";
                }).join("") + "</ul></div>";
        } else {
            html += '<p class="twin-small twin-muted">' +
                escapeHTML(cams.reason || "No live camera covers this point.") + "</p>";
        }

        // --- located observations ----------------------------------------
        var obs = data.observations || [];
        if (obs.length) {
            html += '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
                '<span class="twin-imgbadge twin-imgbadge--lead">DETECTED</span>' +
                "<span>" + obs.length + " open-source observation" +
                (obs.length > 1 ? "s" : "") + " within " + data.radius_km + " km</span></div>" +
                '<ul class="twin-osint-list">' + obs.slice(0, 10).map(function (o) {
                    return "<li><b>" + escapeHTML(o.title || "") + "</b>" +
                        '<span class="twin-muted"> · ' +
                        escapeHTML(OSINT_KIND_LABEL[o.kind] || o.kind) + " · " +
                        o.distance_km + " km · " + escapeHTML(o.age_label || "") +
                        "</span></li>";
                }).join("") + "</ul></div>";
        }

        // --- what is out there but not here ------------------------------
        var beyond = data.nearest_beyond || [];
        if (!obs.length && beyond.length) {
            html += '<p class="twin-small twin-muted">Nothing detected within ' +
                data.radius_km + " km of this point. Nearest: " +
                beyond.map(function (b) {
                    return escapeHTML((OSINT_KIND_LABEL[b.kind] || b.kind).toLowerCase()) +
                        " " + b.distance_km + " km" +
                        (b.total_in_city > 1 ? " (" + b.total_in_city + " in the city)" : "");
                }).join(", ") + ".</p>";
        } else if (beyond.length) {
            html += '<p class="twin-small twin-muted">Further out: ' +
                beyond.map(function (b) {
                    return escapeHTML((OSINT_KIND_LABEL[b.kind] || b.kind).toLowerCase()) +
                        " " + b.distance_km + " km";
                }).join(", ") + ".</p>";
        }

        if (!obs.length && !beyond.length && !(cams.covering || []).length) {
            html += '<p class="twin-small twin-muted">No open-source feed is reporting ' +
                "anything near this point right now.</p>";
        }

        // --- city-level news ---------------------------------------------
        if ((data.city_news || []).length) {
            html += "<h6>City news (not this street)</h6>" +
                renderNewsCards(data.city_news, 6) +
                '<p class="twin-small twin-muted">GDELT locates an article to the city and ' +
                "no further, so these are context for the city, not reports about this cell.</p>";
        }

        var problems = (data.sources || []).filter(function (s) {
            return s.status !== "ok" && s.status !== "cached";
        });
        if (problems.length) {
            html += '<p class="twin-small twin-muted">Unavailable: ' +
                problems.map(function (s) {
                    return escapeHTML(s.label) + " (" + escapeHTML(s.status) + ")";
                }).join(", ") + ".</p>";
        }

        return html + '<p class="twin-small twin-muted">Open-source observations — ' +
            "aircraft, seismicity, natural events, satellite heat. None of this is an " +
            "official warning.</p>";
    }

    function renderOsintDetail(p) {
        var rows = "";
        if (p.kind === "aircraft") {
            rows =
                osintRow("Callsign", escapeHTML(p.callsign || "not transmitted")) +
                osintRow("ICAO24", escapeHTML(p.icao24 || "")) +
                osintRow("Registered", escapeHTML(p.origin_country || "")) +
                osintRow("Altitude", p.altitude_m != null
                    ? Math.round(p.altitude_m) + " m" : null) +
                osintRow("Ground speed", p.velocity_ms != null
                    ? Math.round(p.velocity_ms * 3.6) + " km/h" : null) +
                osintRow("Heading", p.heading_deg != null
                    ? Math.round(p.heading_deg) + "°" : null) +
                osintRow("Vertical rate", p.vertical_rate_ms != null
                    ? (p.vertical_rate_ms > 0 ? "+" : "") + p.vertical_rate_ms + " m/s" : null) +
                osintRow("On ground", p.on_ground ? "yes" : "no");
        } else if (p.kind === "seismic") {
            rows =
                osintRow("Magnitude", p.magnitude != null ? "M" + p.magnitude : null) +
                osintRow("Depth", p.depth_km != null ? Math.round(p.depth_km) + " km" : null) +
                osintRow("Region", escapeHTML(p.region || ""));
        } else if (p.kind === "events") {
            rows =
                osintRow("Category", escapeHTML(p.category || "")) +
                osintRow("Track points", p.track_points);
        } else if (p.kind === "fire") {
            rows =
                osintRow("Confidence", escapeHTML(String(p.confidence || ""))) +
                osintRow("Brightness", p.brightness_k != null ? p.brightness_k + " K" : null) +
                osintRow("Radiative power", p.frp_mw != null ? p.frp_mw + " MW" : null) +
                osintRow("Satellite", escapeHTML(p.satellite || "")) +
                osintRow("Day / night", escapeHTML(p.daynight || ""));
        }

        var link = p.page_url
            ? '<p><a href="' + escapeHTML(p.page_url) + '" target="_blank" rel="noopener">' +
              "Open at source ↗</a></p>"
            : "";

        return '<span class="twin-imgbadge">' +
            escapeHTML(OSINT_KIND_LABEL[p.kind] || p.kind) + "</span>" +
            "<dl class='twin-dl'>" + rows +
            osintRow("Distance", p.distance_km != null
                ? p.distance_km + " km from the city centre" : null) +
            osintRow("Observed", escapeHTML(p.age_label || "")) +
            osintRow("Source", escapeHTML(p.source || "")) +
            "</dl>" + link +
            '<p class="twin-muted twin-small">' + escapeHTML(p.licence || "") +
            ". This is an open-source observation, not an official warning. " +
            "Official alerts are the separate SACHET/IMD layer.</p>";
    }

    function renderOsintPanel(fc) {
        var counts = fc.counts || {};
        var head = '<p class="twin-muted twin-small">Open-source intelligence within <b>' +
            fc.radius_km + " km</b> of the city centre, refreshed while the OSINT layer " +
            "is on. None of this is an official warning.</p>";

        var sources = (fc.sources || []).map(function (s) {
            return '<li class="twin-ground-src twin-ground-src--' + escapeHTML(s.status) + '">' +
                "<b>" + escapeHTML(s.label) + "</b><span>" + escapeHTML(s.status) +
                " · " + s.count + "</span>" +
                (s.detail ? "<em>" + escapeHTML(s.detail) + "</em>" : "") + "</li>";
        }).join("");

        // Located observations, grouped by kind and closest first. The map
        // already draws these; the list is what makes them readable when
        // twenty aircraft overlap at city zoom.
        var byKind = {};
        (fc.features || []).forEach(function (f) {
            var p = f.properties;
            (byKind[p.kind] = byKind[p.kind] || []).push(p);
        });

        var located = Object.keys(byKind).map(function (kind) {
            var rows = byKind[kind].slice(0, 12).map(function (p) {
                return '<li><b>' + escapeHTML(p.title || "") + "</b>" +
                       '<span class="twin-muted"> · ' + (p.distance_km != null
                            ? p.distance_km + " km · " : "") +
                       escapeHTML(p.age_label || "") + "</span></li>";
            }).join("");
            return "<h6>" + escapeHTML(OSINT_KIND_LABEL[kind] || kind) +
                   " <span class='twin-muted twin-small'>(" + byKind[kind].length +
                   ")</span></h6><ul class='twin-osint-list'>" + rows + "</ul>";
        }).join("");

        // News has no coordinate inside the city - GDELT says an article is
        // about this place, never where in it - so it lives here and is never
        // drawn as a pin. See twin/osint.py::_news_items.
        var news = "";
        if ((fc.news || []).length) {
            news = "<h6>Geocoded news <span class='twin-muted twin-small'>(" +
                counts.news + ", GDELT)</span></h6>" +
                renderNewsCards(fc.news, 20) +
                '<p class="twin-muted twin-small">Articles mentioning this city and a ' +
                "hazard term. They carry no coordinate inside the city, so they are " +
                "never drawn on the map.</p>";
        }

        if (!located && !news) {
            located = '<p class="twin-muted twin-small">No open-source observation within ' +
                fc.radius_km + " km right now. That is a real answer, not a failure — " +
                "check the source list below.</p>";
        }

        return head + located + news +
               "<h6>Sources</h6><ul class='twin-ground-srcs'>" + sources + "</ul>" +
               '<p class="twin-muted twin-small">' + escapeHTML(fc.note || "") + "</p>";
    }

    function renderAerialPlaceholder(aerial) {
        if (!aerial || !aerial.thumb_url) {
            return '<p class="twin-muted twin-small">Loading\u2026</p>';
        }
        return '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
            '<span class="twin-imgbadge twin-imgbadge--lead">SATELLITE</span>' +
            "<span>This exact cell from above, ~" + (aerial.span_m || 400) +
            " m across</span></div>" +
            '<a class="twin-aerialshot" target="_blank" rel="noopener" href="' +
            escapeHTML(aerial.full_url || aerial.thumb_url) + '">' +
            '<img src="' + escapeHTML(aerial.thumb_url) +
            '" alt="Satellite view of this cell" loading="lazy">' +
            '<span class="twin-areashot-meta">' + escapeHTML(aerial.provider || "") +
            " \u00b7 no capture date</span></a></div>" +
            '<p class="twin-muted twin-small">Searching ground-level imagery for this ' +
            "point\u2026 this can take a few seconds.</p>";
    }

    function renderImagery(view, options) {
        options = options || {};
        var live = view.live || [];
        var area = view.images || [];
        var reports = view.reports || [];
        var aerial = view.aerial || null;

        if (!live.length && !area.length && !reports.length && !aerial) {
            return '<p class="twin-muted twin-small">' +
                   escapeHTML(view.caption || "No imagery available for this area.") + "</p>" +
                   (view.live_source_available
                       ? ""
                       : '<p class="twin-small twin-muted">No live-webcam source is ' +
                         "configured (WINDY_WEBCAMS_KEY).</p>");
        }

        var html = "";

        // --- vision caption ---------------------------------------------------
        // Filled in by _loadVisionCaption() once the vision-model call returns.
        // It reads whatever the server chose as `best`, so it always describes
        // the image shown first below.
        html += '<div class="twin-vision-caption twin-vision-caption--loading" data-vision-caption>' +
                "&#129504; Reading this image&hellip;</div>";

        // Everything above the webcam is imagery of THIS place; the webcam is
        // the same frame in every cell of the city and is therefore never
        // allowed to lead, never allowed to be the biggest thing on the panel,
        // and always labelled with how far away it actually is. This ordering
        // mirrors routes.py::_best_view exactly.
        var hasLocal = reports.length > 0 || (area.length > 0 && !view.widened);

        // --- citizen report photos: recent AND this exact place --------------
        if (reports.length) {
            html += '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
                '<span class="twin-imgbadge twin-imgbadge--lead">REPORTED HERE</span>' +
                "<span>" + reports.length + " photo" + (reports.length === 1 ? "" : "s") +
                " from citizen report" + (reports.length === 1 ? "" : "s") +
                " at this location</span></div>";
            html += '<div class="twin-areagrid">' + reports.slice(0, 6).map(function (img) {
                return '<a class="twin-areashot" target="_blank" rel="noopener" href="' +
                    escapeHTML(img.page_url || img.full_url || "#") + '" title="' +
                    escapeHTML((img.title || "Report") + " · " +
                               (img.hazard_type || "") + " · " + (img.status || "")) + '">' +
                    '<img src="' + escapeHTML(img.thumb_url || "") + '" alt="" loading="lazy">' +
                    '<span class="twin-areashot-meta">' + Math.round(img.distance_m || 0) +
                    " m · " + escapeHTML(_shortDate(img.captured_at)) + "</span></a>";
            }).join("") + "</div>";
            html += '<p class="twin-small twin-muted">Submitted by reporters at these ' +
                "coordinates. Status is shown on hover; a pending report has not been " +
                "verified.</p></div>";
        }

        // --- street-level photography of this location -----------------------
        if (area.length) {
            var areaLabel = view.widened
                ? "nearest real photo found — further out than usual, nothing closer exists"
                : "street-level photo" + (area.length === 1 ? "" : "s") + " of this location";
            html += '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
                '<span class="twin-imgbadge' + (!view.widened && !reports.length
                    ? " twin-imgbadge--lead" : "") + '">THIS AREA</span>' +
                "<span>" + area.length + " " + areaLabel + "</span></div>";
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

        // --- satellite crop of this exact point ------------------------------
        // The floor under "show me this place". Ranked below every ground-level
        // source because looking straight down answers "what is here", not
        // "what does this look like" - but it is always of THIS cell, which is
        // precisely what the shared city webcam is not. Without it, a cell with
        // no street photography had the webcam as its only picture, and every
        // such cell looked identical.
        if (aerial) {
            var aerialLeads = !reports.length && !area.length;
            html += '<div class="twin-imgsec"><div class="twin-imgsec-head">' +
                '<span class="twin-imgbadge' + (aerialLeads ? " twin-imgbadge--lead" : "") +
                '">SATELLITE</span><span>' +
                (aerialLeads
                    ? "No ground-level photograph of this point exists in any open " +
                      "source — this is the view from above"
                    : "The same point from above, ~" + (aerial.span_m || 400) + " m across") +
                "</span></div>";
            html += '<a class="twin-aerialshot" target="_blank" rel="noopener" href="' +
                escapeHTML(aerial.full_url || aerial.thumb_url || "#") + '">' +
                '<img src="' + escapeHTML(aerial.thumb_url || "") +
                '" alt="Satellite view of this point" loading="lazy">' +
                '<span class="twin-areashot-meta">' + escapeHTML(aerial.provider || "") +
                " · no capture date</span></a>";
            html += '<p class="twin-small twin-muted">Esri World Imagery — the same ' +
                "service as the satellite basemap. It is a mosaic with no per-tile " +
                "capture date, so none is claimed.</p></div>";
        }

        // --- the shared city webcam ------------------------------------------
        // One strip, always last, always small, and the label says outright
        // that it is identical in every cell. Two Windy webcams cover all of
        // Hyderabad and one covers Bengaluru (verified against the API at radii
        // from 15 km to 60 km - the count does not grow), so this frame is the
        // same picture wherever the operator clicks. Presenting it any other
        // way is what made every location look like it had the same photo.
        if (live.length) {
            html += '<div class="twin-imgsec twin-imgsec--secondary">' +
                '<div class="twin-imgsec-head">' +
                '<span class="twin-imgbadge twin-imgbadge--live">● LIVE</span>' +
                "<span>City-wide webcam" + (live.length > 1 ? "s" : "") +
                " — the same frame" + (live.length > 1 ? "s" : "") +
                " in every cell of this city</span></div>";
            html += '<div class="twin-livegrid">' + live.slice(0, 2).map(function (cam, i) {
                return '<figure class="twin-livecam">' +
                       '<img data-live-index="' + i + '" src="' + escapeHTML(cam.thumb_url || "") +
                       '" alt="Live city webcam" loading="lazy">' +
                       "<figcaption>" + escapeHTML(cam.title || cam.provider || "Webcam") +
                       " · <b>" + (cam.distance_m != null
                            ? (cam.distance_m / 1000).toFixed(1) + " km from here" : "nearby") + "</b>" +
                       '<br><span data-live-time="' + i + '">' +
                       escapeHTML(_shortTime(cam.captured_at)) + "</span></figcaption></figure>";
            }).join("") + "</div>";
            html += '<p class="twin-small twin-muted">Refreshes automatically. This is ' +
                    "current weather and light for the city, not a view of this cell. " +
                    'Open <b>📷 Ground</b> in the header for every location in the ' +
                    "city side by side.</p></div>";
        }

        if (!options.hideNote) {
            html += '<p class="twin-muted twin-small">Imagery from citizen reports, ' +
                    "KartaView, Mapillary, Esri World Imagery and Windy Webcams. " +
                    "Sentinel never connects to a " +
                    "camera device and never proxies a stream.</p>";
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

    /* ---- city-wide ground imagery board (markup) ------------------------
     *
     * One tile per picture, grouped by the place it was taken, ordered live
     * first. Every tile states its provider and its real age, because the
     * whole board mixes frames that are seconds old with photographs from
     * 2019 and the difference between those two is the only thing that makes
     * the board worth looking at.
     */
    var GROUND_KIND = {
        webcam:   { badge: "● LIVE",  cls: "twin-ground-card--live",   note: "Publishing a current frame" },
        operator: { badge: "● LIVE",  cls: "twin-ground-card--live",   note: "Operator-supplied still" },
        report:   { badge: "REPORT",  cls: "twin-ground-card--report", note: "Photo attached to a citizen report" },
        zone:     { badge: "STREET",  cls: "",                         note: "Archival street-level photography" },
        centre:   { badge: "STREET",  cls: "",                         note: "Archival street-level photography" }
    };

    var GROUND_FILTERS = [
        ["all", "All"],
        ["live", "Live"],
        ["report", "Reports"],
        ["street", "Street"]
    ];

    function groundBucket(location) {
        if (location.kind === "webcam" || location.kind === "operator") return "live";
        if (location.kind === "report") return "report";
        return "street";
    }

    function renderGroundBoard(board, filter) {
        filter = filter || "all";
        var all = board.locations || [];
        var counts = { all: all.length, live: 0, report: 0, street: 0 };
        all.forEach(function (l) { counts[groundBucket(l)]++; });

        var chips = GROUND_FILTERS.map(function (pair) {
            return '<button type="button" data-ground-filter="' + pair[0] + '"' +
                   (filter === pair[0] ? ' class="is-active"' : "") + ">" +
                   pair[1] + " <span>" + counts[pair[0]] + "</span></button>";
        }).join("");

        var shown = all.filter(function (l) {
            return filter === "all" || groundBucket(l) === filter;
        });
        var shownLocations = shown.length;
        var shownTotal = shown.reduce(function (n, l) { return n + (l.images || []).length; }, 0);
        var shownLive = shown.reduce(function (n, l) {
            return n + (l.images || []).filter(function (i) { return i.live; }).length;
        }, 0);

        var head = '<div class="twin-ground-head">' +
            "<p><b data-ground-count>" + shownTotal + "</b> image" + (shownTotal === 1 ? "" : "s") +
            " across <b>" + shownLocations + "</b> location" +
            (shownLocations === 1 ? "" : "s") +
            (shownLive
                ? ' \u00b7 <span class="twin-imgbadge twin-imgbadge--live">\u25cf ' + shownLive +
                  " LIVE</span>"
                : "") + "</p>" +
            '<div class="twin-segment twin-ground-filters" role="group" ' +
            'aria-label="Filter ground imagery">' + chips + "</div></div>";

        var body = shown.length
            ? shown.map(renderGroundLocation).join("")
            : '<p class="twin-muted twin-small">No imagery in this category for ' +
              escapeHTML(board.city_name || board.city) + " right now.</p>";

        return '<div data-ground-board>' + head + body +
               renderGroundSources(board) +
               '<p class="twin-muted twin-small">' + escapeHTML(board.note || "") + "</p>" +
               (board.live_total
                   ? '<p class="twin-muted twin-small">Live frames refresh every ' +
                     (board.refresh_seconds || 60) + " s while this panel is open. " +
                     "Archival photography is cached for a day — it has not changed.</p>"
                   : "") +
               "</div>";
    }

    function renderGroundLocation(location) {
        var kind = GROUND_KIND[location.kind] || GROUND_KIND.zone;
        var goto = (location.lat != null && location.lon != null)
            ? ' data-ground-goto="' + location.lat + "," + location.lon + '"' +
              ' title="Show this place on the map"'
            : "";

        var tiles = (location.images || []).map(function (img) {
            var meta = escapeHTML(img.provider || "") +
                       (img.distance_m != null && img.distance_m >= 25
                            ? " · " + Math.round(img.distance_m) + " m"
                            : "");
            // KartaView serves some thumbnails from hosts that now 404 while the
            // full-size frame behind the same record still loads, so a dead
            // thumbnail retries the full frame once before the tile gives up.
            // A tile that cannot produce a picture is removed, never left
            // showing a broken-image glyph and its alt text.
            var fallback = (img.full_url && img.full_url !== img.thumb_url)
                ? ' data-ground-alt="' + escapeHTML(img.full_url) + '"' : "";
            var inner =
                '<img data-ground-img="' + escapeHTML(img.id) + '"' + fallback +
                ' loading="lazy" alt="' +
                escapeHTML(location.name + " \u2014 " + (img.provider || "ground image")) +
                '" src="' + escapeHTML(img.thumb_url || "") + '">' +
                '<span class="twin-ground-tile-meta">' +
                (img.live ? '<i class="twin-ground-dot"></i>' : "") +
                '<span data-ground-age="' + escapeHTML(img.id) + '">' +
                escapeHTML(img.age_label || "") + "</span>" +
                '<em>' + meta + "</em></span>";
            return img.page_url
                ? '<a class="twin-ground-tile" href="' + escapeHTML(img.page_url) +
                  '" target="_blank" rel="noopener">' + inner + "</a>"
                : '<figure class="twin-ground-tile">' + inner + "</figure>";
        }).join("");

        return '<section class="twin-ground-card ' + kind.cls + '">' +
            '<header><span class="twin-imgbadge' +
            (kind.badge.charAt(0) === "●" ? " twin-imgbadge--live" : "") + '">' +
            escapeHTML(kind.badge) + "</span>" +
            '<b' + goto + (goto ? ' class="twin-ground-goto"' : "") + ">" +
            escapeHTML(location.name || "Unnamed location") + "</b>" +
            "<span>" + escapeHTML(location.subtitle || kind.note) + "</span></header>" +
            '<div class="twin-ground-tiles">' + tiles + "</div></section>";
    }

    /* Every source, including the ones contributing nothing. A source that is
     * unkeyed or blocked is a thing the owner can fix; silently omitting it
     * makes the city look like it simply has no coverage. */
    function renderGroundSources(board) {
        var rows = (board.sources || []).map(function (src) {
            return '<li class="twin-ground-src twin-ground-src--' + escapeHTML(src.status) + '">' +
                   "<b>" + escapeHTML(src.label) + "</b>" +
                   "<span>" + escapeHTML(src.status) + " · " + src.count + "</span>" +
                   (src.detail ? "<em>" + escapeHTML(src.detail) + "</em>" : "") + "</li>";
        }).join("");
        return rows ? "<h6>Sources</h6><ul class='twin-ground-srcs'>" + rows + "</ul>" : "";
    }

    /* A provider URL that no longer resolves must not leave a broken-image
     * glyph and a line of alt text sitting on the board - that reads as a bug
     * in this app rather than a gap at the provider. The full-size frame is
     * tried once (KartaView's thumbnail hosts rot faster than its originals),
     * and a tile that still cannot produce a picture is removed. A card left
     * with no pictures at all says so plainly rather than going blank. */
    function groundImageFailed(event) {
        var img = event.target;
        if (!img || img.tagName !== "IMG" || !img.hasAttribute("data-ground-img")) return;

        var fallback = img.getAttribute("data-ground-alt");
        if (fallback) {
            img.removeAttribute("data-ground-alt");
            img.src = fallback;
            return;
        }

        var tile = img.closest(".twin-ground-tile");
        if (!tile) return;
        var card = tile.closest(".twin-ground-card");
        var board = tile.closest("[data-ground-board]");
        tile.remove();
        // The server counted what the provider listed; this counts what the
        // operator can actually see. They differ whenever a provider lists a
        // frame it no longer serves, and the visible number is the honest one.
        var counter = board && board.querySelector("[data-ground-count]");
        if (counter) {
            counter.textContent = board.querySelectorAll(".twin-ground-tile").length;
        }
        if (card && !card.querySelector(".twin-ground-tile")) {
            var tiles = card.querySelector(".twin-ground-tiles");
            if (tiles) {
                tiles.innerHTML = '<p class="twin-muted twin-small">' +
                    "The provider no longer serves the images it listed for this " +
                    "location.</p>";
            }
        }
    }

    /* Provider ids are digits and colons today, but they come from third
     * parties, so they are escaped before going into a querySelector. */
    function cssEscape(value) {
        var text = String(value);
        return (window.CSS && window.CSS.escape)
            ? window.CSS.escape(text)
            : text.replace(/["\\\]]/g, "\\$&");
    }



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
            '<p class="twin-muted twin-small">Camera locations from OpenStreetMap (ODbL).</p>' +
            '<h6>Live feeds</h6><div data-twin-live-feeds><p class="twin-muted twin-small">Checking…</p></div>';
    }

    /* Operator-supplied streams only - see twin/cameras.py. Almost always
     * empty (`data/twin/cctv_streams.json` ships as `[]`), and that renders
     * as an explicit "no feed yet" rather than an empty-looking block, so it
     * never reads as broken. */
    var LIVE_FEED_TYPE_LABEL = { hls: "Live video", mjpeg: "Live video", image: "Live snapshot" };
    var _hlsLoader = null;

    function loadHlsJs() {
        if (window.Hls) return Promise.resolve(window.Hls);
        if (!_hlsLoader) {
            _hlsLoader = new Promise(function (resolve, reject) {
                var script = document.createElement("script");
                script.src = "https://cdn.jsdelivr.net/npm/hls.js@1/dist/hls.min.js";
                script.onload = function () { resolve(window.Hls); };
                script.onerror = function () { reject(new Error("hls.js failed to load")); };
                document.head.appendChild(script);
            });
        }
        return _hlsLoader;
    }

    function renderLiveFeeds(container, streams) {
        if (!streams || !streams.length) {
            container.innerHTML = '<p class="twin-muted twin-small">' +
                "No live feed available for this city yet.</p>";
            return;
        }

        container.innerHTML = streams.map(function (s, i) {
            var label = LIVE_FEED_TYPE_LABEL[s.type] || "Live feed";
            return '<div class="twin-live-feed">' +
                '<div class="twin-small twin-muted">' + escapeHTML(label) + " — " +
                escapeHTML(s.name || s.id || "") + "</div>" +
                (s.type === "hls"
                    ? '<video data-live-feed-index="' + i + '" muted playsinline controls></video>'
                    : '<img data-live-feed-index="' + i + '" alt="' + escapeHTML(s.name || "live camera") + '">') +
                (s.operator ? '<div class="twin-small twin-muted">' + escapeHTML(s.operator) +
                              (s.attribution ? " · " + escapeHTML(s.attribution) : "") + "</div>" : "") +
                "</div>";
        }).join("");

        streams.forEach(function (s, i) {
            if (s.type === "hls") {
                var video = container.querySelector('[data-live-feed-index="' + i + '"]');
                if (!video) return;
                loadHlsJs().then(function (Hls) {
                    if (Hls && Hls.isSupported()) {
                        var hls = new Hls();
                        hls.loadSource(s.url);
                        hls.attachMedia(video);
                    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
                        video.src = s.url; // Safari plays HLS natively
                    }
                }).catch(function () {});
            } else {
                // MJPEG streams directly to an <img> tag; a static image just
                // gets refreshed periodically so "live" stays true to its name.
                var img = container.querySelector('[data-live-feed-index="' + i + '"]');
                if (!img) return;
                img.src = s.url;
                if (s.type === "image") {
                    setInterval(function () {
                        if (!document.body.contains(img)) return;
                        img.src = s.url + (s.url.indexOf("?") >= 0 ? "&" : "?") + "t=" + Date.now();
                    }, 15000);
                }
            }
        });
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

    function renderAgentPanel(status, lastRun) {
        status = status || {};
        var html = "";

        if (!status.enabled && !status.forecast_enabled) {
            return '<p class="twin-muted">Both agents are switched off ' +
                   "(TWIN_AGENT_ENABLED=0, TWIN_FORECAST_ENABLED=0). The risk grid and " +
                   "official alerts are unaffected - they need no LLM at all.</p>";
        }

        html += "<dl class='twin-dl'>" +
            dt("Triage agent", status.enabled ? "on" : "off") +
            dt("Forecast agent", status.forecast_enabled ? "on" : "off") +
            dt("LLM", status.llm_available
                ? "connected (" + escapeHTML(status.model || "model unknown") + ")"
                : "no key configured - running on deterministic fallbacks only") +
            dt("Flag threshold", (status.flag_threshold != null ? status.flag_threshold : "n/a") + "/100") +
            dt("RAG corpus", (status.rag_corpus_chunks || 0) + " chunk(s)") +
            "</dl>";

        html += '<p class="twin-small twin-muted">Both agents run on a schedule in the ' +
            "background and only call the LLM when something actually crosses a threshold " +
            "- a quiet cycle with zero flags and zero LLM calls means nothing dangerous was " +
            "found, not that the agent is broken. Use this button to run both agents once, " +
            "right now, and see exactly what each one did.</p>";

        html += '<button type="button" class="twin-agent-runbtn" data-agent-run>Run agent now</button>';

        if (lastRun) {
            html += renderAgentRun(lastRun);
        }

        return html;
    }

    function renderAgentRun(result) {
        var html = '<h6 style="margin-top:0.75rem;">Last manual run</h6>';
        if (result.error) {
            return html + '<p class="twin-error">' + escapeHTML(result.error) + "</p>";
        }
        ["triage", "forecast"].forEach(function (kind) {
            var run = result[kind];
            if (!run) return;
            html += '<div class="twin-agent-citycard"><h6>' +
                (kind === "triage" ? "Triage (what is true now)" : "Forecast (what wind is carrying in)") +
                "</h6>";
            if (run.enabled === false) {
                html += '<p class="twin-small">' + escapeHTML(run.note || "Switched off.") + "</p></div>";
                return;
            }
            if (run.error) {
                html += '<p class="twin-error twin-small">' + escapeHTML(run.error) + "</p></div>";
                return;
            }
            var cities = run.cities || {};
            Object.keys(cities).forEach(function (slug) {
                var c = cities[slug];
                if (c.error) {
                    html += "<p class='twin-small'><b>" + escapeHTML(slug) + ":</b> " +
                            '<span class="twin-error">' + escapeHTML(c.error) + "</span></p>";
                    return;
                }
                var bits = [];
                if (kind === "triage") {
                    bits.push((c.items || 0) + " item(s) read");
                    bits.push((c.clusters || 0) + " cluster(s)");
                } else {
                    bits.push((c.sample_points || 0) + " wind sample point(s)");
                    bits.push((c.projections || 0) + " projection(s)");
                    bits.push((c.events || 0) + " event(s)");
                }
                bits.push((c.flagged || 0) + " flagged");
                bits.push((c.briefs || 0) + " brief(s) written");
                var llm = c.llm || {};
                bits.push((llm.calls || 0) + " LLM call(s)");
                html += "<p class='twin-small'><b>" + escapeHTML(slug) + ":</b> " +
                        escapeHTML(bits.join(" · ")) + "</p>";
            });
            html += "</div>";
        });
        return html;
    }

    function renderFlagQueue(pending, approved) {
        if (!pending.agent_enabled) {
            return '<p class="twin-muted">The triage agent is switched off ' +
                   "(TWIN_AGENT_ENABLED=0). Alerts and the risk grid are unaffected.</p>";
        }
        var note = pending.agent_available
            ? ""
            : '<p class="twin-warn twin-small">No language model API key is configured ' +
              "(KIMI_API_KEY / OPENROUTER_API_KEY), so the briefs below were generated " +
              "from database fields only, with no model involved.</p>";

        var pendingFlags = pending.flags || [];
        var approvedFlags = (approved && approved.flags) || [];

        var pendingHtml = pendingFlags.length
            ? pendingFlags.map(renderReviewCard).join("")
            : '<p class="twin-muted twin-small">Nothing awaiting review.</p>';

        var approvedHtml = approvedFlags.length
            ? "<h6>Approved — ready to dispatch</h6>" + approvedFlags.map(renderDispatchCard).join("")
            : "";

        return note + pendingHtml + approvedHtml;
    }

    function renderCitations(flag) {
        var citations = (flag.citations || []).map(function (c) {
            return "<li>" + escapeHTML(c.sender || c.kind || "source") + " — " +
                   escapeHTML((c.title || c.id || "").slice(0, 70)) +
                   (c.url ? ' <a href="' + escapeHTML(c.url) +
                            '" target="_blank" rel="noopener">↗</a>' : "") + "</li>";
        }).join("");
        return citations ? "<h6>Cited sources</h6><ul class='twin-list'>" + citations + "</ul>" : "";
    }

    function renderReviewCard(flag) {
        return '<div class="twin-flag">' +
            '<div class="twin-flag-head">' +
            "<b>" + escapeHTML(flag.title || "Untitled flag") + "</b>" +
            '<span class="twin-flag-score">' + flag.risk_score + "</span></div>" +
            (flag.generated_offline
                ? '<p class="twin-small twin-muted">Generated without a language model.</p>'
                : "") +
            '<div class="twin-flag-brief">' + markdownish(flag.brief_md || "") + "</div>" +
            renderCitations(flag) +
            '<div class="twin-flag-actions">' +
            '<button type="button" class="twin-btn" data-flag-decision="approve" data-flag-id="' +
            flag.id + '">Approve</button>' +
            '<button type="button" class="twin-btn twin-btn--reject" data-flag-decision="reject" data-flag-id="' +
            flag.id + '">Reject</button></div></div>';
    }

    /* Nothing here sends anything by itself - Preview only fetches a
     * recipient count, and Send is a second, explicit click. This card
     * exists at all only because a flag already passed the approve/reject
     * gate above; dispatch is a second, independent human decision. */
    function renderDispatchCard(flag) {
        return '<div class="twin-flag">' +
            '<div class="twin-flag-head">' +
            "<b>" + escapeHTML(flag.title || "Untitled flag") + "</b>" +
            '<span class="twin-flag-score">' + flag.risk_score + "</span></div>" +
            '<div class="twin-flag-brief">' + markdownish(flag.brief_md || "") + "</div>" +
            renderCitations(flag) +
            '<textarea class="twin-note" data-flag-note="' + flag.id +
            '" placeholder="Optional note to include in the alert"></textarea>' +
            '<div class="twin-flag-actions">' +
            '<button type="button" class="twin-btn" data-flag-preview="' + flag.id +
            '">Preview dispatch</button></div>' +
            '<div data-flag-dispatch-panel="' + flag.id + '"></div>' +
            "</div>";
    }

    function renderDispatchPanel(flagId, preview) {
        var cooldown = preview.cooldown_active
            ? '<p class="twin-warn twin-small">Already dispatched in the last few minutes - ' +
              (preview.cooldown_remaining_minutes || 0) + " min remaining before it can resend.</p>"
            : "";
        var nearest = (preview.nearest || [])
            .map(function (n) { return n.username + " (" + n.distance_km + " km)"; })
            .join(", ");
        return '<div class="twin-dispatch-preview">' +
            "<p class='twin-small'>Would reach <b>" + preview.recipients + "</b> people within " +
            preview.radius_km + " km (" + preview.whatsapp_reachable + " reachable on WhatsApp).</p>" +
            (nearest ? "<p class='twin-muted twin-small'>Nearest: " + escapeHTML(nearest) + "</p>" : "") +
            cooldown +
            '<button type="button" class="twin-btn twin-btn--reject" data-flag-send="' + flagId +
            '"' + (preview.recipients === 0 ? " disabled" : "") + ">Send Alert</button>" +
            "</div>";
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
