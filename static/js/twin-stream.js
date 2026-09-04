/*
 * twin-stream.js - live updates over Server-Sent Events, with polling underneath.
 *
 * The polling timer is not a fallback that switches on when SSE fails; it runs
 * the whole time, just slowly. The server's pub/sub is per-process, so under a
 * multi-worker deployment a browser can hold a perfectly healthy SSE connection
 * to a worker that never publishes the event it is waiting for. A slow poll is
 * the only thing that makes the console correct in that case.
 */

(function (global) {
    "use strict";

    function TwinStream(options) {
        options = options || {};
        this.citySlug = options.citySlug || null;
        this.onUpdate = options.onUpdate || function () {};
        this.onStatus = options.onStatus || function () {};
        // Poll interval while SSE is connected. Deliberately much slower than
        // the compute cadence: it is a safety net, not the main channel.
        this.slowPollMs = options.slowPollMs || 120000;
        // Poll interval when SSE is not available at all.
        this.fastPollMs = options.fastPollMs || 30000;

        this._source = null;
        this._timer = null;
        this._connected = false;
        this._stopped = false;
        this._retryDelay = 5000;
    }

    TwinStream.prototype.start = function () {
        this._stopped = false;
        this._connect();
        this._schedulePoll();
        return this;
    };

    TwinStream.prototype.stop = function () {
        this._stopped = true;
        if (this._source) { this._source.close(); this._source = null; }
        if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    };

    TwinStream.prototype.setCity = function (slug) {
        if (this.citySlug === slug) return;
        this.citySlug = slug;
        if (this._source) { this._source.close(); this._source = null; }
        if (!this._stopped) this._connect();
    };

    TwinStream.prototype.connected = function () { return this._connected; };

    TwinStream.prototype._connect = function () {
        if (typeof global.EventSource === "undefined") {
            this.onStatus({ connected: false, reason: "EventSource unsupported" });
            return;
        }
        var url = "/api/twin/stream" + (this.citySlug ? "?city=" + encodeURIComponent(this.citySlug) : "");
        var self = this;

        try {
            this._source = new global.EventSource(url);
        } catch (err) {
            this.onStatus({ connected: false, reason: String(err) });
            return;
        }

        this._source.addEventListener("hello", function () {
            self._connected = true;
            self._retryDelay = 5000;
            self.onStatus({ connected: true });
        });

        this._source.addEventListener("state", function (event) {
            var payload = null;
            try { payload = JSON.parse(event.data); } catch (err) { return; }
            self.onUpdate(payload);
        });

        this._source.onerror = function () {
            self._connected = false;
            self.onStatus({ connected: false, reason: "stream interrupted" });
            if (self._source) { self._source.close(); self._source = null; }
            if (self._stopped) return;
            // Back off to a minute so a server that is down does not get a
            // reconnect attempt every five seconds from every open dashboard.
            self._retryDelay = Math.min(self._retryDelay * 2, 60000);
            setTimeout(function () { if (!self._stopped) self._connect(); }, self._retryDelay);
        };
    };

    TwinStream.prototype._schedulePoll = function () {
        var self = this;
        if (this._timer) clearTimeout(this._timer);
        var delay = this._connected ? this.slowPollMs : this.fastPollMs;
        this._timer = setTimeout(function () {
            if (self._stopped) return;
            // A null payload means "refresh from the API", not "here is new
            // data" - the console decides what that costs.
            self.onUpdate(null);
            self._schedulePoll();
        }, delay);
    };

    global.TwinStream = TwinStream;
})(typeof window !== "undefined" ? window : this);
