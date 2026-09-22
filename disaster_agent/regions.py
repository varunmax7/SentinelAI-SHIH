"""The regions the agent watches.

The three Windy panels on the analyst dashboard (temperature/wind, satellite,
fire danger) are national-scale views centred on India, not scoped to any one
city - so the agent's monitoring grid is a curated set of points across the
country rather than the twin's two-city H3 grid.

`hazard_bias` is a **declared susceptibility prior**, not a live measurement:
it is what keeps the projection step from ever saying "cyclone risk in
Rajasthan" or "wildfire risk in the Sundarbans mangroves" just because the
wind happened to blow that way. A region only receives a projected hazard of a
type it is geographically capable of experiencing. This is the same kind of
static prior real early-warning systems combine with live weather - it is
argued with by editing this list, not by retuning a threshold.

Each entry: (slug, name, state, lat, lon, hazard_bias, terrain)
"""

REGIONS = [
    # --- Coastal: cyclone / storm surge / coastal flooding ------------------
    ('bhubaneswar', 'Bhubaneswar', 'Odisha', 20.2961, 85.8245,
     ('cyclone', 'storm_surge', 'flood'), 'coastal'),
    ('puri', 'Puri', 'Odisha', 19.8135, 85.8312,
     ('cyclone', 'storm_surge'), 'coastal'),
    ('visakhapatnam', 'Visakhapatnam', 'Andhra Pradesh', 17.6868, 83.2185,
     ('cyclone', 'storm_surge'), 'coastal'),
    ('chennai', 'Chennai', 'Tamil Nadu', 13.0827, 80.2707,
     ('cyclone', 'flood', 'storm_surge'), 'coastal'),
    ('kochi', 'Kochi', 'Kerala', 9.9312, 76.2673,
     ('flood', 'cyclone'), 'coastal'),
    ('mumbai', 'Mumbai', 'Maharashtra', 19.0760, 72.8777,
     ('flood', 'cyclone', 'storm_surge'), 'coastal'),
    ('surat', 'Surat', 'Gujarat', 21.1702, 72.8311,
     ('flood', 'cyclone'), 'coastal'),
    ('bhuj', 'Bhuj', 'Gujarat', 23.2420, 69.6669,
     ('cyclone', 'heat_wave'), 'coastal_arid'),
    ('kolkata', 'Kolkata', 'West Bengal', 22.5726, 88.3639,
     ('cyclone', 'flood', 'storm_surge'), 'coastal_delta'),
    ('port_blair', 'Port Blair', 'Andaman & Nicobar', 11.6234, 92.7265,
     ('cyclone', 'tsunami', 'earthquake'), 'coastal_seismic'),

    # --- Himalayan / hill: landslide / flash flood / earthquake -------------
    ('dehradun', 'Dehradun', 'Uttarakhand', 30.3165, 78.0322,
     ('landslide', 'flood', 'wildfire'), 'himalayan_foothill'),
    ('shimla', 'Shimla', 'Himachal Pradesh', 31.1048, 77.1734,
     ('landslide', 'flood'), 'himalayan'),
    ('srinagar', 'Srinagar', 'Jammu & Kashmir', 34.0837, 74.7973,
     ('flood', 'landslide'), 'himalayan'),
    ('gangtok', 'Gangtok', 'Sikkim', 27.3389, 88.6065,
     ('landslide', 'flood', 'earthquake'), 'himalayan'),
    ('itanagar', 'Itanagar', 'Arunachal Pradesh', 27.0844, 93.6053,
     ('landslide', 'flood'), 'ne_hills'),
    ('guwahati', 'Guwahati', 'Assam', 26.1445, 91.7362,
     ('flood', 'landslide'), 'ne_floodplain'),

    # --- Plains: heat wave / dust / air quality ------------------------------
    ('delhi_ncr', 'Delhi NCR', 'Delhi', 28.6139, 77.2090,
     ('heat_wave', 'air_quality'), 'igp_plain'),
    ('jaipur', 'Jaipur', 'Rajasthan', 26.9124, 75.7873,
     ('heat_wave', 'other'), 'arid_plain'),
    ('lucknow', 'Lucknow', 'Uttar Pradesh', 26.8467, 80.9462,
     ('heat_wave', 'flood'), 'gangetic_plain'),
    ('patna', 'Patna', 'Bihar', 25.5941, 85.1376,
     ('flood', 'heat_wave'), 'gangetic_plain'),

    # --- Central India / Western Ghats: wildfire / heat --------------------
    ('nagpur', 'Nagpur', 'Maharashtra', 21.1458, 79.0882,
     ('heat_wave', 'wildfire'), 'central_dry_forest'),
    ('bhopal', 'Bhopal', 'Madhya Pradesh', 23.2599, 77.4126,
     ('wildfire', 'heat_wave'), 'central_forest'),
    ('raipur', 'Raipur', 'Chhattisgarh', 21.2514, 81.6296,
     ('wildfire', 'heat_wave'), 'central_forest'),
    ('pune', 'Pune', 'Maharashtra', 18.5204, 73.8567,
     ('wildfire', 'flood'), 'western_ghats'),

    # --- Plateau: twin-covered cities, kept as anchors -----------------------
    ('hyderabad', 'Hyderabad', 'Telangana', 17.3850, 78.4867,
     ('heat_wave', 'flood'), 'deccan_plateau'),
    ('bengaluru', 'Bengaluru', 'Karnataka', 12.9716, 77.5946,
     ('flood', 'other'), 'deccan_plateau'),
]

# The full set of hazard types the agent will ever emit. Keep in sync with the
# `hazard_bias` tags above and with the host app's Report.hazard_type
# vocabulary (see twin/agent/schemas.py HAZARD_TYPES) so a prediction and a
# citizen report use the same word for the same thing.
HAZARD_TYPES = (
    'cyclone', 'storm_surge', 'flood', 'landslide', 'heat_wave',
    'wildfire', 'air_quality', 'tsunami', 'earthquake', 'other',
)


def region_by_slug(slug):
    for row in REGIONS:
        if row[0] == slug:
            return row
    return None


def as_dicts():
    """REGIONS in the dict shape every downstream step consumes."""
    return [
        {
            'slug': r[0], 'name': r[1], 'state': r[2],
            'lat': r[3], 'lon': r[4],
            'hazard_bias': r[5], 'terrain': r[6],
        }
        for r in REGIONS
    ]
