"""When a hazard signal starts, when it peaks, and when it is expected to pass.

The watch list answers "how strong is this right now". It could not answer the
question an analyst asks next - *how long does this last?* - because the
projection only ever scored the current hour. A card saying "Hyderabad, Flood,
40/100" gives no basis for deciding whether to alert now or wait.

**The method, and why it is defensible:** Open-Meteo returns an hourly forecast
of exactly the fields `advect.source_strengths()` already consumes - rain,
cloud, wind, pressure, temperature, humidity. So the same scoring function is
re-run against each forecast hour, producing a strength timeline instead of a
single number. The window is then read straight off that timeline:

  starts_at   first hour of the run at or above the alert threshold
  peaks_at    the hour with the highest strength inside that run
  ends_at     the first hour that falls back below the threshold

No new model, no new coefficients and no extrapolation: the numbers come from
the same forecast and the same formula that produce the headline score, so a
window can never disagree with the score it sits under.

**What it refuses to say.** The forecast is finite (FORECAST_DAYS). If the
signal is still above threshold in the last forecast hour, there is no
end time in the data and none is invented - the window is flagged
`open_ended` and the UI must say "still elevated at the end of the forecast"
rather than quietly reporting the horizon's edge as an all-clear. That
distinction is the whole reason this module exists rather than a subtraction
in the template.
"""

from datetime import datetime, timedelta

from . import advect, config as agent_config

# Rain contribution in `source_strengths` is "this hour plus the next three",
# so each forecast hour is scored with its own three-hour look-ahead. Keeping
# it identical to the live path is what makes the timeline's first entry equal
# the headline score rather than merely close to it.
RAIN_LOOKAHEAD_H = 3


def _parse(stamp):
    try:
        return datetime.strptime(stamp[:16], '%Y-%m-%dT%H:%M')
    except (TypeError, ValueError):
        return None


def hourly_signals(signal):
    """`signal` replayed as one pseudo-signal dict per forecast hour.

    Each carries the same keys `advect.source_strengths()` reads, so it can be
    scored by the identical function with no special-casing.
    """
    hourly = signal.get('hourly') or {}
    times = hourly.get('time') or []
    if not times:
        return []

    from .ingest import fosberg_fire_weather_index

    temps = hourly.get('temperature_2m') or []
    humidity = hourly.get('relative_humidity_2m') or []
    winds = hourly.get('wind_speed_10m') or []
    dirs = hourly.get('wind_direction_10m') or []
    clouds = hourly.get('cloud_cover') or []
    rain = hourly.get('precipitation') or []
    pressure = hourly.get('surface_pressure') or []

    def at(series, i):
        return series[i] if i < len(series) else None

    out = []
    for i, stamp in enumerate(times):
        when = _parse(stamp)
        if when is None:
            continue
        temperature_c = at(temps, i)
        humidity_pct = at(humidity, i)
        wind_speed_kmh = at(winds, i)
        ahead = [v or 0.0 for v in rain[i + 1:i + 1 + RAIN_LOOKAHEAD_H]]
        out.append({
            'at': when,
            'hazard_bias': signal.get('hazard_bias'),
            'temperature_c': temperature_c,
            'humidity_pct': humidity_pct,
            'wind_speed_kmh': wind_speed_kmh,
            'wind_dir_deg': at(dirs, i),
            'cloud_cover_pct': at(clouds, i),
            'precipitation_mm': at(rain, i) or 0.0,
            'rain_forecast_3h_mm': float(sum(ahead)),
            'surface_pressure_hpa': at(pressure, i),
            'fire_weather_index': fosberg_fire_weather_index(
                temperature_c, humidity_pct, wind_speed_kmh),
        })
    return out


def strength_timeline(signal, hazard_type, now=None):
    """[(datetime, strength)] for one hazard, from now to the forecast's end.

    Hours already in the past are dropped - an analyst deciding what to do at
    17:00 does not need this morning's scores, and including them would let a
    window claim to have "started" at a time the forecast has since revised.
    """
    now = now or datetime.utcnow()
    floor = now.replace(minute=0, second=0, microsecond=0)
    series = []
    for hour in hourly_signals(signal):
        if hour['at'] < floor:
            continue
        strength = advect.source_strengths(hour).get(hazard_type)
        if strength is None:
            continue
        series.append((hour['at'], round(strength, 1)))
    return series


def hazard_window(signal, hazard_type, threshold=None, now=None):
    """The next stretch of time this hazard is at or above the alert threshold.

    `None` when the forecast carries nothing to say. Otherwise a dict whose
    `state` is one of:

      `active`    above threshold right now
      `upcoming`  below now, crosses the threshold later in the forecast
      `clear`     stays below the threshold for the whole forecast

    `open_ended` is True when the run is still above threshold in the final
    forecast hour - there is no measured end, so none is reported.
    """
    now = now or datetime.utcnow()
    threshold = threshold if threshold is not None else agent_config.SOURCE_SIGNAL_MIN
    series = strength_timeline(signal, hazard_type, now=now)
    if not series:
        return None

    horizon_end = series[-1][0]
    peak_at, peak_strength = max(series, key=lambda pair: pair[1])

    above = [i for i, (_when, strength) in enumerate(series) if strength >= threshold]
    if not above:
        return {
            'state': 'clear',
            'threshold': round(threshold, 1),
            'starts_at': None, 'ends_at': None, 'open_ended': False,
            'peak_at': peak_at, 'peak_strength': peak_strength,
            'forecast_until': horizon_end,
            'forecast_hours': len(series),
            'hours_until_start': None, 'duration_hours': None,
        }

    # The run containing the first above-threshold hour. A later, separate
    # spell is deliberately not merged into this one: two rain bands six hours
    # apart are two events, and reporting them as one long window would
    # overstate how long conditions stay bad.
    first = above[0]
    last = first
    for i in above:
        if i == last or i == last + 1:
            last = i
        elif i > last + 1:
            break

    starts_at = series[first][0]
    open_ended = last == len(series) - 1
    # `ends_at` is the first hour measured back below the threshold - the hour
    # conditions are expected to have eased, not the last bad hour.
    ends_at = None if open_ended else series[last + 1][0]

    run = series[first:last + 1]
    run_peak_at, run_peak_strength = max(run, key=lambda pair: pair[1])

    active = starts_at <= now.replace(minute=0, second=0, microsecond=0)
    return {
        'state': 'active' if active else 'upcoming',
        'threshold': round(threshold, 1),
        'starts_at': starts_at,
        'ends_at': ends_at,
        'open_ended': open_ended,
        'peak_at': run_peak_at,
        'peak_strength': run_peak_strength,
        'forecast_until': horizon_end,
        'forecast_hours': len(series),
        'hours_until_start': max(0, int((starts_at - now).total_seconds() // 3600)),
        'duration_hours': (None if open_ended
                           else max(1, int((ends_at - starts_at).total_seconds() // 3600))),
    }


def as_json(window):
    """The same window with datetimes as ISO strings, for the API layer."""
    if not window:
        return None
    out = dict(window)
    for key in ('starts_at', 'ends_at', 'peak_at', 'forecast_until'):
        value = out.get(key)
        out[key] = value.isoformat() + 'Z' if isinstance(value, datetime) else None
    return out


def describe(window, hazard_type=None):
    """One plain sentence, for the template narrative and the LLM prompt.

    Deliberately written here rather than in the LLM: these are times and
    durations, and a model is never allowed to produce those (see
    agent.py's system prompt).
    """
    if not window:
        return 'No hourly forecast is available for this region, so no timing can be given.'

    hazard = (hazard_type or 'hazard').replace('_', ' ')
    peak = '%s peaks at %.0f/100 around %s UTC' % (
        hazard, window['peak_strength'], _clock(window['peak_at']))

    if window['state'] == 'clear':
        return ('%s stays below the alert threshold of %.0f for the whole forecast '
                '(next %dh); %s.'
                % (hazard.capitalize(), window['threshold'], window['forecast_hours'], peak))

    if window['open_ended']:
        return ('%s is above the alert threshold of %.0f from %s UTC and is still above it '
                'at the end of the available forecast (%s UTC), so no end time can be given; '
                '%s.'
                % (hazard.capitalize(), window['threshold'], _clock(window['starts_at']),
                   _clock(window['forecast_until']), peak))

    if window['state'] == 'active':
        return ('%s has been above the alert threshold of %.0f since %s UTC and is expected '
                'to ease back below it by %s UTC, about %dh in total; %s.'
                % (hazard.capitalize(), window['threshold'], _clock(window['starts_at']),
                   _clock(window['ends_at']), window['duration_hours'], peak))

    return ('%s is below the alert threshold of %.0f now, is expected to cross it at %s UTC '
            '(in about %dh) and to ease back below it by %s UTC, about %dh in total; %s.'
            % (hazard.capitalize(), window['threshold'], _clock(window['starts_at']),
               window['hours_until_start'], _clock(window['ends_at']),
               window['duration_hours'], peak))


def _clock(value):
    if not isinstance(value, datetime):
        return 'an unknown time'
    return value.strftime('%d %b %H:%M')
