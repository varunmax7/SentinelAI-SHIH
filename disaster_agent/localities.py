"""Neighbourhood-level targets within each watched region.

`regions.py` monitors 26 points at city scale - the right resolution for
projecting wind/cloud/fire signal *between* cities. But an analyst deciding
who to alert needs to pick a neighbourhood, not just "Hyderabad" - a WhatsApp
alert centred on a single city-centre point can miss people on the far side of
a large city (see `/send_global_alert`'s 15 km radius in `app.py`).

These are named-locality centroids for alert targeting, the same kind of
approximation `twin/config.py`'s `zones` already makes for Hyderabad and
Bengaluru (administrative circles, not surveyed boundaries) - here extended to
every region this agent watches, and widened for Hyderabad/Bengaluru with a
few more widely-recognised neighbourhood names (Hitec City, Kondapur,
Koramangala, ...) alongside the administrative circle names, since those are
what an analyst is more likely to type into a search bar or recognise on
sight. Coordinates are approximate locality centres, not verified boundaries.
"""

LOCALITIES = {
    'bhubaneswar': [
        ('Patia', 20.3502, 85.8189),
        ('Chandrasekharpur', 20.3298, 85.8188),
        ('Khandagiri', 20.2599, 85.7797),
        ('Old Town', 20.2400, 85.8300),
    ],
    'puri': [
        ('Puri Town', 19.8047, 85.8312),
        ('Swargadwar', 19.8016, 85.8317),
        ('Sipasarubali', 19.7900, 85.8200),
    ],
    'visakhapatnam': [
        ('MVP Colony', 17.7326, 83.3247),
        ('Gajuwaka', 17.6650, 83.2050),
        ('Dwaraka Nagar', 17.7300, 83.3050),
        ('Rushikonda', 17.7800, 83.3800),
    ],
    'chennai': [
        ('T Nagar', 13.0418, 80.2341),
        ('Anna Nagar', 13.0850, 80.2101),
        ('Velachery', 12.9815, 80.2180),
        ('Adyar', 13.0067, 80.2570),
        ('Mylapore', 13.0339, 80.2619),
    ],
    'kochi': [
        ('Ernakulam', 9.9816, 76.2999),
        ('Fort Kochi', 9.9658, 76.2422),
        ('Kakkanad', 10.0159, 76.3419),
        ('Edappally', 10.0261, 76.3082),
    ],
    'mumbai': [
        ('Andheri', 19.1197, 72.8468),
        ('Bandra', 19.0596, 72.8295),
        ('Dadar', 19.0178, 72.8478),
        ('Powai', 19.1176, 72.9060),
        ('Colaba', 18.9067, 72.8147),
    ],
    'surat': [
        ('Adajan', 21.1959, 72.7933),
        ('Vesu', 21.1400, 72.7700),
        ('Katargam', 21.2200, 72.8300),
        ('Varachha', 21.2100, 72.8500),
    ],
    'bhuj': [
        ('Bhuj Town', 23.2420, 69.6669),
        ('Mundra Road', 23.2200, 69.6500),
    ],
    'kolkata': [
        ('Salt Lake', 22.5800, 88.4200),
        ('Howrah', 22.5958, 88.2636),
        ('Park Street', 22.5520, 88.3520),
        ('Behala', 22.5000, 88.3100),
        ('Dum Dum', 22.6400, 88.4200),
    ],
    'port_blair': [
        ('Aberdeen Bazaar', 11.6683, 92.7378),
        ('Haddo', 11.6800, 92.7300),
        ('Phoenix Bay', 11.6650, 92.7450),
    ],
    'dehradun': [
        ('Rajpur Road', 30.3450, 78.0700),
        ('Clement Town', 30.2800, 78.0100),
        ('Sahastradhara', 30.3800, 78.1300),
    ],
    'shimla': [
        ('Mall Road', 31.1041, 77.1734),
        ('Sanjauli', 31.1050, 77.1950),
        ('Chhota Shimla', 31.0950, 77.1800),
    ],
    'srinagar': [
        ('Lal Chowk', 34.0837, 74.7973),
        ('Rajbagh', 34.0700, 74.8100),
        ('Dal Lake', 34.1000, 74.8600),
        ('Soura', 34.1100, 74.8100),
    ],
    'gangtok': [
        ('MG Marg', 27.3314, 88.6138),
        ('Tadong', 27.3200, 88.6100),
        ('Deorali', 27.3200, 88.6000),
    ],
    'itanagar': [
        ('Itanagar Town', 27.0844, 93.6053),
        ('Naharlagun', 27.1050, 93.6950),
    ],
    'guwahati': [
        ('Fancy Bazaar', 26.1850, 91.7400),
        ('Paltan Bazaar', 26.1900, 91.7450),
        ('Dispur', 26.1433, 91.7898),
        ('Beltola', 26.1200, 91.8000),
        ('Six Mile', 26.1200, 91.8100),
    ],
    'delhi_ncr': [
        ('Connaught Place', 28.6315, 77.2167),
        ('Dwarka', 28.5921, 77.0460),
        ('Gurgaon', 28.4595, 77.0266),
        ('Noida', 28.5355, 77.3910),
        ('Rohini', 28.7495, 77.0565),
    ],
    'jaipur': [
        ('Malviya Nagar', 26.8500, 75.8100),
        ('Vaishali Nagar', 26.9150, 75.7400),
        ('C-Scheme', 26.9100, 75.8000),
        ('Mansarovar', 26.8500, 75.7600),
    ],
    'lucknow': [
        ('Hazratganj', 26.8500, 80.9430),
        ('Gomti Nagar', 26.8500, 81.0100),
        ('Aminabad', 26.8500, 80.9200),
        ('Alambagh', 26.8100, 80.9100),
    ],
    'patna': [
        ('Patna City', 25.6100, 85.1600),
        ('Boring Road', 25.6100, 85.1200),
        ('Kankarbagh', 25.5900, 85.1600),
        ('Danapur', 25.6300, 85.0500),
    ],
    'nagpur': [
        ('Sitabuldi', 21.1500, 79.0800),
        ('Dharampeth', 21.1400, 79.0600),
        ('Civil Lines', 21.1550, 79.0750),
        ('Sadar', 21.1600, 79.0700),
    ],
    'bhopal': [
        ('MP Nagar', 23.2350, 77.4350),
        ('New Market', 23.2350, 77.4020),
        ('Arera Colony', 23.2200, 77.4450),
        ('Kolar Road', 23.1500, 77.4200),
    ],
    'raipur': [
        ('Shankar Nagar', 21.2450, 81.6300),
        ('Telibandha', 21.2300, 81.6500),
        ('Civil Lines', 21.2400, 81.6350),
    ],
    'pune': [
        ('Kothrud', 18.5074, 73.8077),
        ('Hinjewadi', 18.5908, 73.7389),
        ('Viman Nagar', 18.5679, 73.9143),
        ('Camp', 18.5100, 73.8800),
        ('Baner', 18.5590, 73.7868),
    ],
    'hyderabad': [
        # Widely-recognised IT-corridor / commercial localities first ...
        ('Hitec City', 17.4435, 78.3772),
        ('Kondapur', 17.4615, 78.3688),
        ('Gachibowli', 17.4401, 78.3489),
        ('Madhapur', 17.4483, 78.3915),
        ('Banjara Hills', 17.4156, 78.4347),
        # ... plus the administrative circles twin/config.py already verified.
        ('Charminar', 17.3616, 78.4747),
        ('Secunderabad', 17.4399, 78.4983),
        ('Kukatpally', 17.4948, 78.3996),
        ('L. B. Nagar', 17.3457, 78.5522),
    ],
    'bengaluru': [
        ('Koramangala', 12.9352, 77.6245),
        ('Indiranagar', 12.9719, 77.6412),
        ('Whitefield', 12.9698, 77.7500),
        ('Electronic City', 12.8452, 77.6602),
        ('Jayanagar', 12.9308, 77.5838),
        ('Yelahanka', 13.1007, 77.5963),
        ('Mahadevapura', 12.9899, 77.6963),
        ('Rajarajeshwari Nagar', 12.9264, 77.5188),
    ],
}


def localities_for(region_slug):
    return [{'name': n, 'lat': lat, 'lon': lon} for n, lat, lon in LOCALITIES.get(region_slug, [])]


def as_json_map():
    return {slug: localities_for(slug) for slug in LOCALITIES}
