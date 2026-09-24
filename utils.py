import os
import random
import csv
import shutil
from twilio.rest import Client
from flask import current_app
from werkzeug.utils import secure_filename
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_file(file):
    if file and allowed_file(file.filename):
        # Secure the filename and add timestamp to make it unique
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(original_filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        
        # Ensure upload directory exists
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save the file
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        return unique_filename
    return None

def send_whatsapp_message(to_number, message_body, media_url=None):
    """Send a WhatsApp message using Twilio"""
    if not to_number:
        return None
        
    # Ensure number starts with whatsapp:
    if not to_number.startswith('whatsapp:'):
        to_number = f'whatsapp:{to_number}'
        
    try:
        client = Client(
            current_app.config['TWILIO_ACCOUNT_SID'],
            current_app.config['TWILIO_AUTH_TOKEN']
        )
        
        message_args = {
            'from_': current_app.config['TWILIO_WHATSAPP_NUMBER'],
            'body': message_body,
            'to': to_number
        }
        
        if media_url:
            message_args['media_url'] = [media_url]
            print(f"🖼️ Attached media URL: {media_url}")
            
        print(f"📤 Attempting to send WhatsApp to {to_number}...")
        message = client.messages.create(**message_args)
        print(f"✅ WhatsApp message sent to {to_number}: SID {message.sid}, Status: {message.status}")
        return message.sid
    except Exception as e:
        print(f"❌ WhatsApp message failed to {to_number}: {e}")
        return None

def send_sms_alert(to_number, hazard_type, risk_level, lat, lng):
    """Send an SMS alert using Twilio"""
    if not to_number:
        return None
        
    try:
        client = Client(
            current_app.config['TWILIO_ACCOUNT_SID'],
            current_app.config['TWILIO_AUTH_TOKEN']
        )
        
        message_body = (
            f"ALERT: {hazard_type} near {lat},{lng}. "
            f"Risk: {risk_level}. Evacuate!"
        )
        
        message_args = {
            'from_': current_app.config.get('TWILIO_PHONE_NUMBER'),
            'body': message_body,
            'to': to_number
        }
        
        if not message_args['from_']:
            print("❌ Twilio Phone Number not configured in config.py")
            return None
            
        print(f"📤 Attempting to send SMS to {to_number}...")
        message = client.messages.create(**message_args)
        print(f"✅ SMS sent to {to_number}: SID {message.sid}, Status: {message.status}")
        return message.sid
    except Exception as e:
        print(f"❌ SMS failed to {to_number}: {e}")
        return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points 
    on the Earth's surface using the Haversine formula.
    
    Returns distance in kilometers.
    """
    # Earth radius in kilometers
    R = 6371.0
    
    # Convert degrees to radians
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Differences
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Haversine formula
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c

def get_hazard_alert_radius(hazard_type):
    """
    Get the alert radius for a specific hazard type.
    
    Returns radius in kilometers.
    """
    hazard_radii = {
        'tsunami': 10.0,        # 10 km radius for tsunamis
        'storm_surge': 15.0,    # 15 km radius for storm surges  
        'high_waves': 2.0,      # 2 km radius for high waves
        'swell_surge': 2.0,     # 2 km radius for swell surges
        'coastal_flooding': 5.0, # 5 km radius for coastal flooding
        'abnormal_tide': 2.0,   # 2 km radius for abnormal tides
        'other': 5.0            # 5 km radius for other hazards
    }
    
    return hazard_radii.get(hazard_type, 5.0)  # Default to 5 km if not found

def get_hazard_alert_message(hazard_type, distance=None):
    """
    Get the alert message for a specific hazard type.
    
    Optionally includes distance information.
    """
    hazard_messages = {
        'tsunami': '🌊 Tsunami Alert! Can travel hundreds to thousands of kilometers inland. Evacuate to higher ground if within 5-10 km of coast or below 30 m elevation.',
        'storm_surge': '🌪 Storm Surge Alert! Usually affects 5-15 km inland. Can push water 30+ km inland in flat areas. Evacuate if in low-lying coastal regions.',
        'high_waves': '🌊 High Wave Alert! Dangerous mainly along immediate coast and beaches (up to 1-2 km inland). Avoid beach activities.',
        'swell_surge': '🌊 Swell Surge Alert! Hazard limited to surf zone (few hundred meters from shore). Exercise caution near water.',
        'coastal_flooding': '⚠️ Coastal Flooding Alert! Affects areas within 5 km of coast. Move to higher ground if in flood-prone areas.',
        'abnormal_tide': '⚠️ Abnormal Tide Alert! Affects coastal areas within 2 km. Be cautious of unusual water levels.',
        'other': '⚠️ Hazard Alert! A verified hazard has been reported in your area. Exercise caution and follow local authorities instructions.'
    }
    
    message = hazard_messages.get(hazard_type, '⚠️ Hazard Alert! A verified hazard has been reported in your area.')
    
    if distance is not None:
        message += f" - {distance:.1f}km away"
    
    return message

def format_distance(distance_km):
    """
    Format distance in a user-friendly way.
    """
    if distance_km < 1:
        return f"{distance_km * 1000:.0f}m"
    elif distance_km < 10:
        return f"{distance_km:.1f}km"
    else:
        return f"{distance_km:.0f}km"

def is_within_alert_radius(user_lat, user_lon, report_lat, report_lon, hazard_type):
    """
    Check if a user is within the alert radius of a report.
    
    Returns (is_within_radius, distance_km)
    """
    if user_lat is None or user_lon is None:
        return False, 0
    
    distance = calculate_distance(user_lat, user_lon, report_lat, report_lon)
    alert_radius = get_hazard_alert_radius(hazard_type)
    
    return distance <= alert_radius, distance

def should_receive_alert(user, report):
    """
    Determine if a user should receive an alert for a report.
    
    Checks:
    1. User has location set
    2. User is within alert radius
    3. User has alerts enabled for this hazard type
    """
    if not user.home_latitude or not user.home_longitude:
        return False, 0
    
    # Check if user has alerts enabled for this hazard type
    alert_prefs = user.get_alert_preferences()
    if not alert_prefs.get(report.hazard_type, True):
        return False, 0
    
    # Check if user is within alert radius
    is_within, distance = is_within_alert_radius(
        user.home_latitude, user.home_longitude,
        report.latitude, report.longitude,
        report.hazard_type
    )
    
    return is_within, distance

def generate_alert_message(report, distance_km):
    """
    Generate an alert message for a report with distance information.
    """
    hazard_type = report.hazard_type
    formatted_distance = format_distance(distance_km)
    
    base_messages = {
        'tsunami': f'🌊 Tsunami Alert at {report.location}! Evacuate to higher ground immediately. You are {formatted_distance} away.',
        'storm_surge': f'🌪 Storm Surge Alert at {report.location}! Seek shelter away from the coast. You are {formatted_distance} away.',
        'high_waves': f'🌊 High Wave Alert at {report.location}! Avoid beach activities. You are {formatted_distance} away.',
        'swell_surge': f'🌊 Swell Surge Alert at {report.location}! Exercise caution near water. You are {formatted_distance} away.',
        'coastal_flooding': f'⚠️ Coastal Flooding Alert at {report.location}! Move to higher ground. You are {formatted_distance} away.',
        'abnormal_tide': f'⚠️ Abnormal Tide Alert at {report.location}! Be cautious of unusual water levels. You are {formatted_distance} away.',
        'other': f'⚠️ Hazard Alert at {report.location}! Exercise caution. You are {formatted_distance} away.'
    }
    
    return base_messages.get(hazard_type, f'⚠️ Hazard Alert at {report.location}! You are {formatted_distance} away.')

# =============================================================================
# PLASTIC REDUCTION & CARBON SAVINGS UTILITIES
# =============================================================================

def analyze_plastic_image(image_path):
    """
    Analyze plastic reduction proof image using AI
    Returns confidence score and analysis
    """
    try:
        # Simulate AI analysis - in production, integrate with Google Vision AI, AWS Rekognition, etc.
        # This would analyze if the image shows plastic reduction evidence
        
        # For demo purposes, return simulated analysis
        analysis_results = {
            'confidence_score': random.uniform(0.7, 0.95),
            'plastic_type_detected': True,
            'reduction_verified': True,
            'analysis': 'Image shows plastic reduction evidence with good clarity'
        }
        
        return analysis_results
        
    except Exception as e:
        print(f"Plastic image analysis error: {e}")
        return {
            'confidence_score': 0.5,
            'plastic_type_detected': False,
            'reduction_verified': False,
            'analysis': 'Image analysis failed'
        }

def calculate_carbon_savings(plastic_type, quantity, unit):
    """
    Calculate carbon savings based on plastic reduction
    Conversion factors based on environmental studies
    """
    # Carbon equivalent factors (kg CO2 per unit)
    carbon_factors = {
        'plastic_bottle': 0.082,  # kg CO2 per bottle
        'plastic_bag': 0.006,    # kg CO2 per bag
        'straw': 0.001,          # kg CO2 per straw
        'food_container': 0.045,  # kg CO2 per container
        'cutlery': 0.008,        # kg CO2 per piece
        'packaging': 0.002,      # kg CO2 per gram
        'other': 0.001           # kg CO2 per gram (default)
    }
    
    # Convert to standard units if needed
    if unit == 'grams':
        quantity_kg = quantity / 1000
    elif unit == 'pieces':
        # Use piece-based calculation
        factor = carbon_factors.get(plastic_type, carbon_factors['other'])
        return quantity * factor
    else:  # kg
        quantity_kg = quantity
    
    # For weight-based items
    if plastic_type in ['packaging', 'other']:
        return quantity_kg * carbon_factors[plastic_type]
    else:
        # For piece-based items, convert to approximate weight first
        piece_weights = {
            'plastic_bottle': 20,  # grams per bottle
            'plastic_bag': 5,      # grams per bag
            'straw': 0.5,          # grams per straw
            'food_container': 15,  # grams per container
            'cutlery': 3           # grams per piece
        }
        weight_grams = quantity * piece_weights.get(plastic_type, 10)
        return (weight_grams / 1000) * carbon_factors.get(plastic_type, carbon_factors['other'])

def calculate_points_for_activity(carbon_saved, activity_type, verified=True):
    """
    Calculate points earned for eco-friendly activities
    """
    base_points = int(carbon_saved * 10)  # 10 points per kg CO2 saved
    
    if not verified:
        base_points = base_points // 2  # Half points for unverified
    
    # Bonus points for specific activities
    bonus_points = {
        'plastic_reduction': 5,
        'public_transport': 3,
        'cycling': 8,
        'tree_planting': 15,
        'energy_saving': 4,
        'water_saving': 3,
        'waste_recycling': 6
    }
    
    bonus = bonus_points.get(activity_type, 2)
    return max(5, base_points + bonus)  # Minimum 5 points

def get_plastic_type_name(plastic_type_code):
    """
    Convert plastic type code to human-readable name
    """
    plastic_names = {
        'plastic_bottle': 'Plastic Bottle',
        'plastic_bag': 'Plastic Bag',
        'straw': 'Plastic Straw',
        'food_container': 'Food Container',
        'cutlery': 'Plastic Cutlery',
        'packaging': 'Product Packaging',
        'other': 'Other Plastic'
    }
    return plastic_names.get(plastic_type_code, 'Plastic Item')

def get_activity_type_name(activity_type_code):
    """
    Convert activity type code to human-readable name
    """
    activity_names = {
        'plastic_reduction': 'Plastic Reduction',
        'public_transport': 'Public Transport',
        'cycling': 'Cycling',
        'energy_saving': 'Energy Saving',
        'water_saving': 'Water Conservation',
        'waste_recycling': 'Waste Recycling',
        'tree_planting': 'Tree Planting',
        'other': 'Other Eco Activity'
    }
    return activity_names.get(activity_type_code, 'Eco Activity')

def calculate_environmental_impact(plastic_reduced_kg, carbon_saved_kg):
    """
    Calculate comprehensive environmental impact metrics
    """
    # Environmental equivalents based on EPA and environmental studies
    impact_metrics = {
        'trees_equivalent': carbon_saved_kg / 21.77,  # kg CO2 absorbed by one tree per year
        'car_miles_equivalent': carbon_saved_kg * 0.621371 / 0.404,  # miles not driven
        'energy_equivalent': carbon_saved_kg * 0.000163,  # MWh of electricity
        'water_bottles_saved': plastic_reduced_kg * 50,  # approximate bottles per kg
        'landfill_space_saved': plastic_reduced_kg * 0.0015  # cubic meters per kg
    }
    
    return impact_metrics

def get_eco_achievement_level(total_carbon_saved):
    """
    Determine user's eco achievement level based on total carbon savings
    """
    if total_carbon_saved >= 1000:
        return {'level': 'Eco Champion', 'icon': '🏆', 'description': 'Saved over 1 ton of CO2!'}
    elif total_carbon_saved >= 500:
        return {'level': 'Climate Hero', 'icon': '🦸', 'description': 'Saved 500+ kg of CO2'}
    elif total_carbon_saved >= 100:
        return {'level': 'Green Guardian', 'icon': '🌿', 'description': 'Saved 100+ kg of CO2'}
    elif total_carbon_saved >= 50:
        return {'level': 'Eco Warrior', 'icon': '♻️', 'description': 'Saved 50+ kg of CO2'}
    elif total_carbon_saved >= 10:
        return {'level': 'Planet Protector', 'icon': '🌎', 'description': 'Saved 10+ kg of CO2'}
    else:
        return {'level': 'Eco Beginner', 'icon': '🌱', 'description': 'Getting started with eco actions'}

def validate_plastic_quantity(plastic_type, quantity, unit):
    """
    Validate plastic quantity input with reasonable limits
    """
    # Maximum reasonable quantities by type
    max_quantities = {
        'plastic_bottle': {'pieces': 100, 'grams': 2000, 'kg': 2},
        'plastic_bag': {'pieces': 200, 'grams': 1000, 'kg': 1},
        'straw': {'pieces': 500, 'grams': 250, 'kg': 0.25},
        'food_container': {'pieces': 50, 'grams': 750, 'kg': 0.75},
        'cutlery': {'pieces': 100, 'grams': 300, 'kg': 0.3},
        'packaging': {'pieces': 100, 'grams': 5000, 'kg': 5},
        'other': {'pieces': 100, 'grams': 5000, 'kg': 5}
    }
    
    max_qty = max_quantities.get(plastic_type, max_quantities['other'])
    max_allowed = max_qty.get(unit, max_qty['pieces'])
    
    if quantity > max_allowed:
        return False, f"Quantity seems too high for {get_plastic_type_name(plastic_type)}. Maximum allowed: {max_allowed} {unit}"
    
    if quantity <= 0:
        return False, "Quantity must be greater than zero"
    
    return True, "Valid quantity"

def generate_eco_tips(activity_type):
    """
    Generate eco tips based on activity type
    """
    tips_library = {
        'plastic_reduction': [
            "Use reusable bags instead of plastic bags",
            "Carry a reusable water bottle",
            "Say no to plastic straws",
            "Choose products with minimal packaging",
            "Use reusable containers for food storage"
        ],
        'public_transport': [
            "Plan your route in advance",
            "Use transit apps for real-time schedules",
            "Combine multiple errands in one trip",
            "Consider walking or cycling for short distances",
            "Use off-peak hours for less crowded travel"
        ],
        'cycling': [
            "Wear a helmet for safety",
            "Use bike lanes when available",
            "Maintain your bike regularly",
            "Use lights and reflectors at night",
            "Plan safe routes away from heavy traffic"
        ],
        'energy_saving': [
            "Turn off lights when leaving rooms",
            "Use energy-efficient LED bulbs",
            "Unplug electronics when not in use",
            "Use natural light during daytime",
            "Set thermostat to efficient temperatures"
        ],
        'water_saving': [
            "Take shorter showers",
            "Fix leaky faucets promptly",
            "Use water-efficient fixtures",
            "Collect rainwater for plants",
            "Turn off tap while brushing teeth"
        ],
        'waste_recycling': [
            "Separate recyclables properly",
            "Clean containers before recycling",
            "Compost food waste when possible",
            "Donate usable items instead of throwing away",
            "Learn local recycling guidelines"
        ]
    }
    
    tips = tips_library.get(activity_type, [
        "Every small eco-action makes a difference!",
        "Share your eco achievements to inspire others",
        "Track your progress regularly",
        "Set achievable eco goals"
    ])
    
    return random.choice(tips)

def calculate_community_impact_stats(users_data):
    """
    Calculate community-wide environmental impact statistics
    """
    total_plastic_reduced = sum(user.get('total_plastic_reduced', 0) for user in users_data)
    total_carbon_saved = sum(user.get('total_carbon_saved', 0) for user in users_data)
    total_activities = sum(user.get('activity_count', 0) for user in users_data)
    
    # Calculate environmental equivalents
    community_impact = {
        'total_plastic_reduced_kg': total_plastic_reduced,
        'total_carbon_saved_kg': total_carbon_saved,
        'total_activities': total_activities,
        'equivalent_trees': total_carbon_saved / 21.77,
        'equivalent_car_miles': total_carbon_saved * 0.621371 / 0.404,
        'equivalent_energy_saved': total_carbon_saved * 0.000163,
        'plastic_bottles_saved': total_plastic_reduced * 50
    }
    
    return community_impact

def format_environmental_metric(value, metric_type):
    """
    Format environmental metrics in a user-friendly way
    """
    if metric_type == 'carbon':
        if value >= 1000:
            return f"{value/1000:.1f} tons CO2"
        else:
            return f"{value:.1f} kg CO2"
    
    elif metric_type == 'plastic':
        if value >= 1000:
            return f"{value/1000:.1f} tons"
        elif value >= 1:
            return f"{value:.1f} kg"
        else:
            return f"{value*1000:.0f} g"
    
    elif metric_type == 'trees':
        return f"{value:.0f} trees"
    
    elif metric_type == 'distance':
        if value >= 1000:
            return f"{value/1000:.1f}k miles"
        else:
            return f"{value:.0f} miles"
    
    elif metric_type == 'energy':
        return f"{value:.1f} MWh"
    
    else:
        return f"{value:.1f}"

# =============================================================================
# AI ACCURACY VALIDATION - 4 PARAMETER SYSTEM
# =============================================================================

_HAZARD_BASELINE_SEVERITY = {
    'tsunami': 0.95,
    'storm_surge': 0.80,
    'coastal_flooding': 0.75,
    'high_waves': 0.55,
    'swell_surge': 0.50,
    'abnormal_tide': 0.35,
}


def _severity_label(score):
    if score >= 0.85:
        return 'critical'
    elif score >= 0.60:
        return 'high'
    elif score >= 0.35:
        return 'medium'
    return 'low'


def validate_report_accuracy_4params(report, weather_data=None, heatmap_data=None):
    """
    Validate report accuracy using 4 key parameters:
    1. Weather & Early Warnings - Check if report hazard is confirmed in heatmap/active hazards
    2. Live Climate Data - Check if report aligns with current weather conditions
    3. User Quality Score - Check user's historical credibility and track record
    4. Image Processing (NVIDIA NIM) - Check if the uploaded photo visually matches the claimed hazard

    Returns accuracy score (0-1), a severity assessment, and detailed breakdown
    """

    # Parameter 1: Weather & Early Warnings Heatmap Match (25% weight)
    heatmap_accuracy = _validate_heatmap_match(report, heatmap_data)

    # Parameter 2: Live Climate Data Alignment (25% weight)
    climate_accuracy = _validate_climate_alignment(report, weather_data)

    # Parameter 3: User Quality/Credibility Score (25% weight)
    user_quality = _calculate_user_quality_score(report.author)

    # Parameter 4: Image Processing via NVIDIA NIM vision model (25% weight)
    image_processing = _validate_image_processing(report)

    # Calculate weighted average accuracy
    weights = [0.25, 0.25, 0.25, 0.25]
    accuracy_scores = [
        heatmap_accuracy['score'],
        climate_accuracy['score'],
        user_quality['score'],
        image_processing['score'],
    ]
    overall_accuracy = sum(s * w for s, w in zip(accuracy_scores, weights))

    # Severity: prefer what the photo actually shows (image parameter), since
    # that reflects this specific incident rather than just the hazard label;
    # fall back to a per-hazard-type baseline when there's no usable image.
    baseline_severity = _HAZARD_BASELINE_SEVERITY.get(report.hazard_type, 0.5)
    if image_processing.get('severity') != 'unknown' and image_processing.get('severity_score', 0) > 0:
        severity_score = (image_processing['severity_score'] * 0.7) + (baseline_severity * 0.3)
    else:
        severity_score = baseline_severity
    severity_score = max(0.0, min(1.0, severity_score))
    severity = _severity_label(severity_score)

    # An image that is a photograph OF A SCREEN blocks auto-approval outright,
    # rather than merely scoring low enough to miss the bar. Today the capped
    # image score happens to hold the blended total to ~0.81 against an 0.85
    # threshold - but that is arithmetic coincidence across two weighted
    # averages, and reweighting any parameter would silently re-open the hole.
    # A provenance failure is a categorical "a human must look at this", so it
    # is carried as a flag and enforced as one.
    rephotographed = bool(image_processing.get('rephotographed'))

    return {
        'overall_accuracy': overall_accuracy,
        'accuracy_percent': int(overall_accuracy * 100),
        'rephotographed': rephotographed,
        'requires_human_review': rephotographed,
        'severity': severity,
        'severity_score': severity_score,
        'severity_percent': int(severity_score * 100),
        'parameter_1_heatmap': heatmap_accuracy,
        'parameter_2_climate': climate_accuracy,
        'parameter_3_user_quality': user_quality,
        'parameter_4_image_processing': image_processing,
        'detailed_analysis': (
            f"Heatmap Match: {int(heatmap_accuracy['score']*100)}% | "
            f"Climate Alignment: {int(climate_accuracy['score']*100)}% | "
            f"User Quality: {int(user_quality['score']*100)}% | "
            f"Image Processing: {int(image_processing['score']*100)}%"
        )
    }


# Backwards-compatible alias for the old 3-parameter name
validate_report_accuracy_3params = validate_report_accuracy_4params

def _validate_heatmap_match(report, heatmap_data=None):
    """
    Parameter 1: Check if report hazard type matches active hazards in heatmap area
    Returns score 0-1 based on hazard type match and incident density
    """
    try:
        from models import Report
        
        # Find similar hazards in same location (within 5km) in last 24 hours
        from datetime import datetime, timedelta
        time_window = timedelta(hours=24)
        location_threshold = 0.05  # ~5.5 km
        
        if report.latitude is None or report.longitude is None:
            return {'score': 0.50, 'analysis': 'Heatmap unavailable: No coordinates provided'}
        
        # This runs before the report is added/committed, so its column
        # defaults (timestamp) and autoincrement id are still None. Centre the
        # time window on "now" and skip the self-exclusion clause when there is
        # no id yet - `Report.id != NULL` is NULL in SQL and matches no rows.
        reference_time = report.timestamp or datetime.utcnow()
        filters = [
            Report.hazard_type == report.hazard_type,
            Report.timestamp.between(reference_time - time_window, reference_time + time_window),
            Report.latitude.between(report.latitude - location_threshold, report.latitude + location_threshold),
            Report.longitude.between(report.longitude - location_threshold, report.longitude + location_threshold),
            Report.verification_status.in_(['approved', 'pending'])
        ]
        if report.id is not None:
            filters.insert(0, Report.id != report.id)

        similar_hazards = Report.query.filter(*filters).count()
        
        # Calculate heatmap density score
        if similar_hazards >= 5:
            score = 0.95  # Strong hazard hotspot confirmed
            analysis = f"Strong heatmap confirmation: {similar_hazards} reports of {report.hazard_type} in area"
        elif similar_hazards >= 3:
            score = 0.85  # Moderate hotspot
            analysis = f"Moderate heatmap confirmation: {similar_hazards} similar reports detected"
        elif similar_hazards >= 1:
            score = 0.70  # Some corroboration
            analysis = f"Partial heatmap match: {similar_hazards} corroborating report(s)"
        else:
            score = 0.50  # No heatmap corroboration but plausible
            analysis = "No active heatmap data for this hazard type in area"
        
        return {'score': score, 'analysis': analysis}
    except Exception as e:
        print(f"Heatmap validation error: {e}")
        return {'score': 0.50, 'analysis': 'Heatmap data unavailable'}

def _validate_climate_alignment(report, weather_data=None):
    """
    Parameter 2: Check if report aligns with live climate conditions
    Uses hazard type to verify weather conditions support the report
    Returns score 0-1 based on weather alignment
    """
    try:
        import requests
        from datetime import datetime
        
        # Get live weather data from Open-Meteo API for report location
        lat, lon = report.latitude, report.longitude
        
        if lat is None or lon is None:
            return {'score': 0.50, 'analysis': 'Climate data unavailable: No coordinates provided'}
            
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m"
        
        # A failed lookup must not be dressed up as a reading: substituting
        # placeholder numbers here used to surface in the report analysis as
        # real observed weather (and quietly drove the hazard scoring off
        # fabricated values). Report the outage instead.
        temp = humidity = wind_speed = None
        weather_error = None
        try:
            response = requests.get(weather_url, timeout=5)
            if response.status_code == 200:
                weather = response.json().get('current', {})
                temp = weather.get('temperature_2m')
                humidity = weather.get('relative_humidity_2m')
                wind_speed = weather.get('wind_speed_10m')
                if temp is None or humidity is None or wind_speed is None:
                    weather_error = 'weather API returned no current conditions'
            else:
                weather_error = f'weather API returned HTTP {response.status_code}'
        except Exception as e:
            weather_error = f'weather API unreachable ({type(e).__name__})'

        if weather_error:
            print(f"Climate validation: {weather_error}")
            return {'score': 0.50, 'analysis': f'Climate data unavailable: {weather_error}'}
        
        # Validate hazard against weather conditions
        hazard_type = report.hazard_type.lower()
        
        if hazard_type == 'tsunami':
            # Tsunami usually caused by underwater earthquakes, not weather
            score = 0.75
            analysis = f"Tsunami report noted. Weather: {temp}°C, Wind: {wind_speed}km/h"
        elif hazard_type == 'storm_surge':
            # Storm surge: high winds expected
            if wind_speed >= 25:
                score = 0.90
                analysis = f"Storm conditions confirmed: High winds {wind_speed}km/h detected"
            elif wind_speed >= 15:
                score = 0.75
                analysis = f"Moderate wind conditions: {wind_speed}km/h matches storm surge pattern"
            else:
                score = 0.45
                analysis = f"Low wind speed {wind_speed}km/h - unexpected for storm surge"
        elif hazard_type == 'high_waves':
            # High waves: wind + humidity
            if wind_speed >= 20 or humidity >= 70:
                score = 0.85
                analysis = f"Wave conditions supported: Wind {wind_speed}km/h, Humidity {humidity}%"
            else:
                score = 0.60
                analysis = f"Borderline conditions: Wind {wind_speed}km/h, Humidity {humidity}%"
        elif hazard_type == 'coastal_flooding':
            # Flooding: high humidity/rainfall
            if humidity >= 75:
                score = 0.80
                analysis = f"Flood conditions likely: High humidity {humidity}% detected"
            else:
                score = 0.65
                analysis = f"Moderate flood risk: Humidity {humidity}%"
        elif hazard_type == 'abnormal_tide':
            # Tides: temperature/humidity indicators
            score = 0.70
            analysis = f"Abnormal tide reported. Current conditions: {temp}°C, Humidity {humidity}%"
        elif hazard_type == 'swell_surge':
            # Swell: wind patterns
            if wind_speed >= 15:
                score = 0.80
                analysis = f"Swell surge conditions: Wind {wind_speed}km/h supports report"
            else:
                score = 0.60
                analysis = f"Swell report noted: Wind {wind_speed}km/h"
        else:
            score = 0.65
            analysis = f"General hazard: Weather {temp}°C, Wind {wind_speed}km/h, Humidity {humidity}%"
        
        return {'score': score, 'analysis': analysis}
    except Exception as e:
        print(f"Climate validation error: {e}")
        return {'score': 0.65, 'analysis': 'Climate data validation partial'}

def _calculate_user_quality_score(user):
    """
    Parameter 3: Calculate user's credibility score based on:
    - User role (official > analyst > regular users)
    - History of verified reports
    - Report accuracy track record
    - Activity level
    
    Returns score 0-1
    """
    try:
        from models import Report
        
        # Base score by role
        role_scores = {
            'official': 0.95,
            'analyst': 0.90,
            'agency': 0.88,
            'citizen': 0.50
        }
        base_role_score = role_scores.get(user.role, 0.50)
        
        # Get user's report history
        user_reports = Report.query.filter_by(user_id=user.id).all()
        total_reports = len(user_reports)
        
        if total_reports == 0:
            # New user - reduce score
            history_multiplier = 0.6
            analysis = f"New user (no reports). Base credibility: {int(base_role_score*100)}%"
        else:
            # Calculate approval rate
            approved = sum(1 for r in user_reports if r.verification_status == 'approved')
            approval_rate = approved / total_reports if total_reports > 0 else 0
            
            if approval_rate >= 0.8:
                history_multiplier = 1.0
                analysis = f"Excellent track record: {approved}/{total_reports} reports approved ({int(approval_rate*100)}%)"
            elif approval_rate >= 0.6:
                history_multiplier = 0.85
                analysis = f"Good track record: {approved}/{total_reports} reports approved ({int(approval_rate*100)}%)"
            elif approval_rate >= 0.4:
                history_multiplier = 0.70
                analysis = f"Moderate track record: {approved}/{total_reports} reports approved ({int(approval_rate*100)}%)"
            else:
                history_multiplier = 0.50
                analysis = f"Low accuracy: {approved}/{total_reports} reports approved ({int(approval_rate*100)}%)"
        
        # Calculate user points/level factor (higher level = more experienced)
        user_level_factor = min(1.0, (user.level / 10.0) * 0.3 + 0.7)  # Scales from 0.7 to 1.0
        
        # Combined quality score
        quality_score = base_role_score * history_multiplier * user_level_factor
        quality_score = min(1.0, quality_score)  # Cap at 1.0
        
        return {
            'score': quality_score,
            'analysis': analysis,
            'role': user.role,
            'level': user.level,
            'total_reports': total_reports
        }
    except Exception as e:
        print(f"User quality score error: {e}")
        return {'score': 0.50, 'analysis': 'User quality assessment unavailable'}

# Hard wall-clock cap (seconds) on a single image-processing API call. Kept
# short since this call blocks report submission - see _post_with_deadline.
# Measured free-tier latency is ~3.5s typical, but a queued request can sit
# well past that, and 9s was tight enough to time out real answers. 18s gives
# queueing headroom; VISION_TOTAL_BUDGET_SECONDS stops the retry/fallback
# combinations (2 attempts x 2 models) from multiplying into a minute-long wait.
HARD_DEADLINE_SECONDS = 18
VISION_TOTAL_BUDGET_SECONDS = 30
# The free Nemotron endpoint flips between ~2.5s and fully saturated ("worker
# local total request limit reached"). When it hangs there is no reason to wait
# the full cap, because a second model is queued behind it - so non-final
# candidates get this shorter leash instead.
VISION_FIRST_TRY_DEADLINE = 8


def _post_with_deadline(request_kwargs, deadline_seconds):
    """
    requests.post() with a real total-time cap. Plain `timeout=` on requests
    only bounds the gap between chunks of a response, not its overall
    duration - a reply that trickles in slowly can sail past it while still
    taking 30-40s wall-clock. Running the call in a worker thread and giving
    up on `future.result()` after `deadline_seconds` enforces an actual cap;
    the abandoned thread is left to finish or error out on its own (daemon
    executor, not joined) rather than blocking the caller.
    """
    import concurrent.futures
    import requests

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(requests.post, **request_kwargs)
    try:
        return future.result(timeout=deadline_seconds)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"Request exceeded {deadline_seconds}s hard deadline")
    finally:
        executor.shutdown(wait=False)


def _downscale_image_for_upload(image_path, max_dimension=768, jpeg_quality=75):
    """
    Shrink+re-encode the image before sending it to the vision API. Uploaded
    photos can be several MB straight off a phone camera; the model doesn't
    need that resolution to judge a hazard, and a smaller payload is the
    single biggest lever on request latency (upload time + tokens the model
    has to chew through). Falls back to the raw file bytes if Pillow can't
    open it for any reason.
    """
    import io
    from PIL import Image

    try:
        with Image.open(image_path) as img:
            img = img.convert('RGB')
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=jpeg_quality, optimize=True)
            return buf.getvalue(), 'image/jpeg'
    except Exception as e:
        print(f"Image downscale failed, sending original file: {e}")
        with open(image_path, 'rb') as f:
            return f.read(), None


def _extract_json_object(text):
    """
    Pull the JSON object out of a VLM reply, tolerating the three things these
    models actually do despite being told to emit bare JSON: wrap it in ```json
    fences, surround it with prose, and put chain-of-thought in <think> tags.

    Scans with a brace counter rather than a regex because the non-greedy
    pattern this replaced (\{.*?\}) stops at the FIRST closing brace, so any
    nested object silently yielded a truncated fragment. Candidates are tried
    newest-first: when a model reasons out loud and then states its answer, the
    last complete object is the answer.

    Returns a dict, or None if nothing parseable is present (including the case
    where the reply was cut off mid-JSON by the token limit).
    """
    import json as _json
    import re as _re

    if not text:
        return None

    text = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL)
    text = _re.sub(r'```(?:json)?', '', text).strip()

    spans = []
    depth = 0
    start = None
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    spans.append(text[start:i + 1])

    for span in reversed(spans):
        try:
            obj = _json.loads(span)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None



# --- vision providers and model candidates ------------------------------------
# Two providers, tried in that order. All timings verified directly against a
# real KartaView street photo on 2026-09-24 with the production prompt:
#
#   OpenAI (OPENAI_API_KEY, a real sk-proj- key, billed)
#     gpt-4.1-mini    200, 2.2s,   539 tokens, clean JSON   <- default
#     gpt-5.4-nano    200, 4.6s,   446 tokens, clean JSON
#     gpt-4o-mini     200, 4.1s, 14316 tokens  - works, but ~26x the tokens
#                     of gpt-4.1-mini for the same picture, so it is not used
#
#   OpenRouter free tier (KIMI_API_KEY; NVIDIA_API_KEY is EXPIRED - verified
#   HTTP 401 "API key expired" against /api/v1/key)
#     nex-agi/nex-n2.5-mini:free          200, 4.3s, clean JSON
#     nvidia/nemotron-3-nano-...:free     200, 4.5s, clean JSON
#     google/gemma-4-31b-it:free          200, 5.3s, clean JSON
#
# Checked and rejected, each for a specific reason:
#   inclusionai/ling-3.0-flash-vl:free   404, retired to paid-only. This was
#                                        the old fallback and is exactly what
#                                        produced the "HTTP 404 ... use this
#                                        slug instead" error an analyst saw.
#   thinkingmachines/inkling-small:free  403, agentic harnesses only.
#   dots-studio/dots-3-note-preview:free 200 but never parseable JSON.
#   nex-agi/nex-n2.5-pro:free            200 but 37s, past every deadline here.
#   qwen/qwen3.8-27b:free                429 while testing; kept as a late
#   google/gemma-4-26b-a4b-it:free       fallback since free-pool saturation
#                                        is transient, unlike a 404.
#
# The free models stay in the chain behind OpenAI deliberately: they cost
# nothing, and they are what keeps captions working if the OpenAI key hits a
# billing or quota wall. A paid key failing should degrade to free, not to
# no caption at all.
OPENAI_VISION_MODELS = tuple(
    m.strip() for m in os.environ.get(
        'OPENAI_VISION_MODELS', 'gpt-4.1-mini,gpt-5.4-nano').split(',') if m.strip())

OPENROUTER_VISION_MODELS = (
    'nex-agi/nex-n2.5-mini:free',
    'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free',
    'google/gemma-4-31b-it:free',
    'qwen/qwen3.8-27b:free',
    'google/gemma-4-26b-a4b-it:free',
)

# How sure the model must be that a photo is a re-capture of a screen or
# printout before it is penalised. Measured on a real submission with a macOS
# dock and keyboard in frame: gpt-4.1-mini said 0.95, gpt-5.4-nano 0.95, and
# both named the specific evidence. A genuine outdoor photo scored
# direct_photo at 0.9. 0.70 sits well clear of both.
REPHOTOGRAPH_MIN_CONFIDENCE = float(os.environ.get('REPHOTOGRAPH_MIN_CONFIDENCE', '0.70'))
# Capped, not zeroed: the hazard depicted may be perfectly real and worth an
# analyst's eye. What a photo of a screen cannot do is prove the reporter was
# there, so it must never carry enough weight to clear an auto-approval bar.
REPHOTOGRAPH_SCORE_CAP = float(os.environ.get('REPHOTOGRAPH_SCORE_CAP', '0.25'))

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
OPENROUTER_CHAT_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Models that answered 404/403 in THIS process. A retired or gated model
# answers the same way every time, so re-asking only burns the budget that
# the next, working candidate needs.
_DEAD_VISION_MODELS = set()


def vision_routes():
    """[(provider, api_key, model_id)] in the order they should be tried.

    OpenAI first because its key is verified live and billed, so it is not
    subject to the free tier's per-model saturation. OpenRouter's free models
    follow as a genuine fallback rather than as decoration.

    NVIDIA_VISION_MODEL / VISION_FALLBACK_MODEL still win when set, so an
    operator can pin a model without editing code.
    """
    routes = []

    openai_key = os.environ.get('OPENAI_API_KEY')
    if openai_key:
        for model_id in OPENAI_VISION_MODELS:
            routes.append(('openai', openai_key, model_id))

    # Every configured OpenRouter key is tried, not just the first present
    # one: a plain `A or B` only falls through when A is unset, which never
    # helps when A is set but expired - exactly the NVIDIA_API_KEY case.
    or_keys = []
    for candidate in (os.environ.get('OPENROUTER_API_KEY'),
                      os.environ.get('KIMI_API_KEY'),
                      os.environ.get('NVIDIA_API_KEY')):
        if candidate and candidate not in or_keys:
            or_keys.append(candidate)

    pinned = [v for v in (os.environ.get('NVIDIA_VISION_MODEL'),
                          os.environ.get('VISION_FALLBACK_MODEL')) if v]
    or_models = pinned + [m for m in OPENROUTER_VISION_MODELS if m not in pinned]
    for key in or_keys:
        for model_id in or_models:
            routes.append(('openrouter', key, model_id))

    return [r for r in routes if r[2] not in _DEAD_VISION_MODELS]


def mark_vision_model_dead(model_id):
    """Remember a 404/403 so the rest of this process stops asking."""
    _DEAD_VISION_MODELS.add(model_id)


def vision_request_kwargs(provider, api_key, model_id, prompt, mime_type,
                          image_b64, timeout):
    """One provider-shaped request for the same vision question.

    The two APIs differ in three ways that each cause a silent failure if got
    wrong: OpenAI's reasoning models (gpt-5*) reject `max_tokens` and require
    `max_completion_tokens`, they reject a non-default `temperature`, and
    OpenRouter needs the `reasoning` block to keep a reasoning model from
    spending its whole allowance thinking and returning empty content.
    """
    body = {
        'model': model_id,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url',
                 'image_url': {'url': 'data:%s;base64,%s' % (mime_type, image_b64)}},
            ],
        }],
    }

    if provider == 'openai':
        # gpt-5 and o-series are reasoning models with a different parameter
        # contract; sending the older pair is a 400, not a warning.
        if model_id.startswith(('gpt-5', 'o1', 'o3', 'o4')):
            body['max_completion_tokens'] = 1200
        else:
            body['max_tokens'] = 1200
            body['temperature'] = 0.1
        url = OPENAI_CHAT_URL
        headers = {'Authorization': 'Bearer %s' % api_key,
                   'Content-Type': 'application/json'}
    else:
        # Reasoning tokens are billed against max_tokens. At 300 a reasoning
        # model spent the entire allowance on its chain and returned
        # content=None - which surfaced to an analyst as "Vision model call
        # failed or timed out". Verified: same model, same image, 300 -> empty,
        # 1200 -> a clean caption in 4.5s.
        body['max_tokens'] = 1200
        body['temperature'] = 0.1
        body['reasoning'] = {'effort': 'low'}
        url = OPENROUTER_CHAT_URL
        headers = {'Authorization': 'Bearer %s' % api_key,
                   'Accept': 'application/json',
                   'HTTP-Referer': 'https://sentinel-ai.local',
                   'X-Title': 'Sentinel AI'}

    return dict(url=url, headers=headers, json=body, timeout=timeout)

def _validate_image_processing(report):
    """
    Parameter 4: Run the report's uploaded photo through the NVIDIA Nemotron
    vision-reasoning model (served via OpenRouter) and check whether the
    image visually matches the reporter's claimed hazard_type.

    Returns score 0-1 based on the model's confidence that the photo shows
    the claimed hazard, plus a 'caption' of what the model actually saw in
    the image (kept so it can be surfaced/stored alongside the report) and
    a 'severity'/'severity_score' assessment of how bad the hazard looks.
    Falls back to a neutral 0.5 whenever no image, no API key, or the API
    call fails - this is a scoring signal, not a gate.
    """
    import base64
    import json
    import mimetypes
    import re
    import time
    import requests

    if not report.image_file:
        return {'score': 0.30, 'analysis': 'Image processing skipped: No photo attached to report', 'severity': 'unknown', 'severity_score': 0.0}

    # NVIDIA_API_KEY is an OpenRouter key (format sk-or-...) and was found
    # expired on OpenRouter's side (verified directly - HTTP 401 "API key
    # expired" against https://openrouter.ai/api/v1/key). KIMI_API_KEY, used
    # elsewhere in this app for the twin's triage/forecast agent, is a
    # separate, live OpenRouter key that reaches the same free vision
    # models. A plain `A or B` only falls through when A is unset - it never
    # helps when A is set but invalid, which is exactly this case - so every
    # configured key is tried in turn below, not just resolved once here.
    routes = vision_routes()
    if not routes:
        return {'score': 0.50,
                'analysis': ('Image processing unavailable: no vision key configured '
                             '(set OPENAI_API_KEY, or an OpenRouter key)'),
                'severity': 'unknown', 'severity_score': 0.0}

    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
        image_path = os.path.join(upload_folder, report.image_file)

        if not os.path.exists(image_path):
            return {'score': 0.30, 'analysis': 'Image processing skipped: Photo file not found on disk', 'severity': 'unknown', 'severity_score': 0.0}

        image_bytes, mime_type = _downscale_image_for_upload(image_path)
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(image_path)
            mime_type = mime_type or 'image/jpeg'
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        hazard_type = report.hazard_type
        prompt = (
            "Coastal disaster verification. Claimed hazard: "
            f"'{hazard_type}' (one of: tsunami, storm_surge, high_waves, swell_surge, coastal_flooding, abnormal_tide). "
            "Answer TWO independent questions. Do not let either answer influence the other.\n"
            "A) PROVENANCE - how was this FILE produced? Look for a monitor, laptop "
            "or phone screen in frame, device bezels, desktop or browser UI, "
            "taskbars or docks, a visible keyboard, moire or scanline patterns, "
            "screen glare, a printed page or paper texture. If ANY of that is "
            "present, this is a re-photograph of existing media and NOT a direct "
            "photo of a real scene. Judge the FILE, not the scene inside it - a "
            "genuine-looking flood displayed on a laptop is still a screen capture.\n"
            "B) HAZARD - what hazard, if any, is visible in the depicted scene.\n"
            "Reply with ONLY this compact JSON object, no prose, no markdown fencing: "
            '{"capture_medium": "direct_photo" or "screen" or "printout" or "unclear", '
            '"capture_confidence": 0-1, '
            '"provenance_evidence": "what specifically you saw, or null", '
            '"caption": "one short sentence on exactly what the image shows", '
            '"matches_hazard": true or false, "confidence": 0-1, '
            '"detected_hazard": "short label of what the image actually shows", '
            '"severity": "low", "medium", "high" or "critical" - how dangerous the scene looks, '
            '"severity_score": 0-1, '
            '"reasoning": "one short sentence"}'
        )

        # One wall-clock budget shared by every attempt and candidate below, so
        # report submission cannot block for retries x models x per-call cap.
        overall_deadline = time.monotonic() + VISION_TOTAL_BUDGET_SECONDS

        def call_model(provider, model_id, api_key, is_last_candidate):
            """Try one model on one key, retrying once on a fast transient
            failure. Returns (parsed_dict, error_message, key_is_dead) -
            key_is_dead signals the caller to skip this key's remaining
            model candidates (invalid key, or its quota is exhausted).

            The request body differs per provider - see
            vision_request_kwargs, where the three parameter differences that
            each cause a silent failure are handled."""
            # requests' own `timeout=` only bounds the gap between chunks of a
            # slow-trickling response, not total wall-clock time. The
            # ThreadPoolExecutor deadline in _post_with_deadline enforces the
            # real cap; this is only the per-socket floor.
            request_kwargs = vision_request_kwargs(
                provider, api_key, model_id, prompt, mime_type, image_b64,
                HARD_DEADLINE_SECONDS)

            last_err = None
            for attempt in range(2):
                # Spend at most what is left of the shared budget, so a slow
                # first attempt cannot push the total past the overall cap.
                remaining = overall_deadline - time.monotonic()
                if remaining < 2:
                    return None, last_err or f'image analysis budget of {VISION_TOTAL_BUDGET_SECONDS}s exhausted', False
                # Give up quickly on a saturated earlier candidate - its whole
                # point is that another model can answer - but let the LAST
                # candidate use the full cap, since nothing follows it.
                cap = HARD_DEADLINE_SECONDS if is_last_candidate else VISION_FIRST_TRY_DEADLINE
                attempt_deadline = min(cap, remaining)
                request_kwargs['timeout'] = attempt_deadline

                try:
                    response = _post_with_deadline(request_kwargs, attempt_deadline)
                except TimeoutError:
                    return None, f'{model_id} did not respond within {attempt_deadline:.0f}s', False

                if response.status_code != 200:
                    detail = response.text[:200]
                    if response.status_code == 401:
                        return None, f'{model_id} auth failed - key expired or invalid', True
                    # The free-tier daily cap is account-wide, not per-model, so
                    # flag it: trying the fallback would just burn another request
                    # from the same exhausted quota. It IS per-key though, so a
                    # different key is still worth trying.
                    if response.status_code == 429 and 'free-models-per-day' in detail:
                        return None, ('OpenRouter free-model daily limit reached (50 requests/day '
                                      'on a free-tier key) - resets 00:00 UTC, or add credits to raise it'), True
                    # 404 = retired (this is how ling-3.0-flash-vl broke), 403 =
                    # gated. Neither changes on a retry, and re-asking spends
                    # budget the next working candidate needs.
                    if response.status_code in (403, 404):
                        mark_vision_model_dead(model_id)
                    return None, f'{model_id} returned HTTP {response.status_code} - {detail}', False

                body = response.json()
                if 'choices' not in body:
                    last_err = f"{model_id} upstream error: {body.get('error', {}).get('message', 'unknown error')}"
                    continue  # this failure mode returns in ~1-2s, cheap to retry once

                choice = body['choices'][0]
                message = choice.get('message') or {}
                # Parse here rather than after the candidate loop: a truncated or
                # prose-only reply is a failure of THIS model, so returning it as a
                # success would skip the fallback model that could still answer.
                parsed = _extract_json_object(message.get('content'))
                if parsed is None:
                    # Reasoning models sometimes emit the JSON only inside their
                    # chain-of-thought field, so it is worth a look before giving up.
                    parsed = _extract_json_object(message.get('reasoning'))
                if parsed is not None:
                    return parsed, None, False

                if choice.get('finish_reason') == 'length':
                    last_err = f'{model_id} ran out of output tokens before finishing the JSON answer'
                else:
                    last_err = f'{model_id} returned no parseable JSON object'
                continue  # retry once; a different sample usually lands a clean answer

            return None, last_err, False

        # Routes are already ordered provider-first (see vision_routes): the
        # billed OpenAI key leads, the free OpenRouter models back it up. A
        # key that fails one model fails every model on that provider
        # identically, so a dead key skips the rest of its own routes.
        dead_keys = set()

        parsed = None
        last_error = None
        model_used = None
        for index, (provider, key, candidate) in enumerate(routes):
            if key in dead_keys:
                continue
            parsed, err, key_dead = call_model(
                provider, candidate, key, index == len(routes) - 1)
            if parsed is not None:
                model_used = candidate
                break
            last_error = err
            if key_dead:
                dead_keys.add(key)

        if parsed is None:
            return {'score': 0.50, 'analysis': f'Image processing unavailable: {last_error}', 'severity': 'unknown', 'severity_score': 0.0}

        model = model_used
        caption = parsed.get('caption', '').strip()
        matches_hazard = bool(parsed.get('matches_hazard', False))
        model_confidence = float(parsed.get('confidence', 0.5))
        model_confidence = max(0.0, min(1.0, model_confidence))
        detected_hazard = parsed.get('detected_hazard', 'unknown')
        reasoning = parsed.get('reasoning', '')
        severity = str(parsed.get('severity', 'unknown')).lower()
        if severity not in ('low', 'medium', 'high', 'critical'):
            severity = 'unknown'
        severity_score = max(0.0, min(1.0, float(parsed.get('severity_score', 0.0))))
        # A hazard that doesn't even match the photo can't be scored as severe off that photo
        if not matches_hazard:
            severity_score *= 0.3

        # If the model thinks it's a different hazard, discount the confidence
        score = model_confidence if matches_hazard else model_confidence * 0.3
        score = max(0.0, min(1.0, score))

        # --- provenance ------------------------------------------------------
        # A photo OF A SCREEN is not evidence from the scene. The hazard in it
        # may be entirely real - and the model will happily describe it as
        # "people in waist-deep floodwater", which is what it shows - but the
        # file proves nothing about where the reporter was or when. Verified on
        # a real submission whose bottom third was a macOS dock, Touch Bar and
        # the F4-F9 keys: the grader scored it 'coastal_flooding, high' and
        # never mentioned the laptop, because nothing had asked it to look.
        #
        # EXIF is deliberately NOT used as a corroborating signal. Checked
        # directly: every photo taken through this app's own camera widget has
        # zero EXIF tags, because the browser canvas capture path strips them.
        # An "absent EXIF means suspicious" rule would flag every legitimate
        # in-app capture while missing this case entirely - a phone photo of a
        # screen carries perfectly normal camera EXIF.
        capture_medium = str(parsed.get('capture_medium') or 'unclear').lower().strip()
        if capture_medium not in ('direct_photo', 'screen', 'printout', 'unclear'):
            capture_medium = 'unclear'
        try:
            capture_confidence = max(0.0, min(1.0, float(parsed.get('capture_confidence', 0.0))))
        except (TypeError, ValueError):
            capture_confidence = 0.0
        provenance_evidence = parsed.get('provenance_evidence')
        if isinstance(provenance_evidence, str) and provenance_evidence.strip().lower() in (
                '', 'null', 'none', 'n/a'):
            provenance_evidence = None

        rephotographed = (capture_medium in ('screen', 'printout')
                          and capture_confidence >= REPHOTOGRAPH_MIN_CONFIDENCE)

        provenance_note = ''
        if rephotographed:
            # Capped, not zeroed. The depicted hazard may be real and worth an
            # analyst's eye; what it cannot do is carry the reporter's own
            # verification weight. Auto-approval thresholds sit above this cap.
            score = min(score, REPHOTOGRAPH_SCORE_CAP)
            severity_score = min(severity_score, REPHOTOGRAPH_SCORE_CAP)
            medium_label = 'a screen' if capture_medium == 'screen' else 'a printed page'
            provenance_note = (
                f" \u26a0 NOT A DIRECT PHOTO: this file is a re-capture of {medium_label} "
                f"(confidence {capture_confidence:.0%}"
                + (f"; {provenance_evidence}" if provenance_evidence else '')
                + "). The hazard shown may be real, but this image cannot confirm the "
                  "reporter was at the scene. Confidence capped at "
                  f"{REPHOTOGRAPH_SCORE_CAP:.2f} pending human review."
            )
        elif capture_medium in ('screen', 'printout'):
            # Below the threshold: say so, change nothing. A weak suspicion is
            # worth an analyst's attention and is not worth auto-penalising a
            # genuine report over.
            provenance_note = (
                f" Note: possible re-capture of a screen/printout, but only "
                f"{capture_confidence:.0%} confident - not penalised."
            )

        analysis = (
            # Name the model that actually answered - the fallback credited its
            # analysis to Nemotron, which is misleading when Nemotron was down.
            f"Vision analysis ({model.split('/')[-1].replace(':free', '')}) - what it saw: \"{caption}\" | "
            f"detected '{detected_hazard}' ({'matches' if matches_hazard else 'does not match'} claimed '{hazard_type}'), "
            f"severity: {severity}. {reasoning}{provenance_note}"
        )

        return {
            'score': score,
            'analysis': analysis,
            'caption': caption,
            'matches_hazard': matches_hazard,
            'detected_hazard': detected_hazard,
            'severity': severity,
            'severity_score': severity_score,
            'model': model,
            # Structured so a reviewer UI can badge this rather than having to
            # parse it back out of the prose above.
            'capture_medium': capture_medium,
            'capture_confidence': capture_confidence,
            'provenance_evidence': provenance_evidence,
            'rephotographed': rephotographed,
        }

    except requests.exceptions.Timeout:
        return {'score': 0.50, 'analysis': 'Image processing timed out: model did not respond in time', 'severity': 'unknown', 'severity_score': 0.0}
    except Exception as e:
        print(f"Image processing error: {e}")
        return {'score': 0.50, 'analysis': 'Image processing unavailable: analysis failed', 'severity': 'unknown', 'severity_score': 0.0}

# =============================================================================
# LIVE FLOOD GAUGE DATA (Open-Meteo Flood API / GloFAS)
# =============================================================================
# Open-Meteo's Flood API is free, keyless, and returns real river-discharge
# forecasts (GloFAS model, ~5km grid, updated daily). Important caveat found
# during testing: at India's exact station coordinates the model often snaps
# to a small tributary pixel rather than the actual main channel, so absolute
# discharge numbers (e.g. "0.27 m3/s" at Kaleswaram on the Godavari) can look
# nonsensical if shown as a literal reading. To stay honest while still being
# genuinely live, classification below is RELATIVE - today's discharge is
# compared against that same pixel's own historical mean/p75/max - which is a
# real anomaly signal regardless of whether the pixel is the named river or a
# nearby tributary in the same watershed.

TELANGANA_GAUGE_STATIONS = [
    {'name': 'Bhadrachalam', 'river': 'Godavari', 'lat': 17.67, 'lon': 80.89},
    {'name': 'Mancherial', 'river': 'Godavari', 'lat': 18.87, 'lon': 79.46},
    {'name': 'Kaleswaram', 'river': 'Godavari', 'lat': 18.55, 'lon': 79.90},
    {'name': 'Nandikonda', 'river': 'Krishna', 'lat': 16.95, 'lon': 79.32},
    {'name': 'Jogulamba', 'river': 'Krishna', 'lat': 16.58, 'lon': 78.08},
    {'name': 'Dummugudem', 'river': 'Godavari', 'lat': 17.78, 'lon': 80.57},
    {'name': 'Asifabad', 'river': 'Godavari', 'lat': 19.37, 'lon': 79.28},
    {'name': 'Yellandu', 'river': 'Godavari', 'lat': 17.60, 'lon': 80.32},
    {'name': 'Nalgonda', 'river': 'Musi', 'lat': 17.06, 'lon': 79.27},
    {'name': 'Hyderabad (Musi)', 'river': 'Musi', 'lat': 17.38, 'lon': 78.48},
    {'name': 'Nizamabad', 'river': 'Manjira', 'lat': 18.67, 'lon': 78.10},
    {'name': 'Wanaparthy', 'river': 'Krishna', 'lat': 16.36, 'lon': 78.07},
    {'name': 'Jadcherla', 'river': 'Krishna', 'lat': 16.76, 'lon': 78.17},
    {'name': 'Medak', 'river': 'Manjira', 'lat': 18.05, 'lon': 78.26},
    {'name': 'Adilabad', 'river': 'Godavari', 'lat': 19.66, 'lon': 78.53},
    {'name': 'Khammam', 'river': 'Krishna', 'lat': 17.25, 'lon': 80.15},
    {'name': 'Suryapet', 'river': 'Musi', 'lat': 17.14, 'lon': 79.62},
]

BENGALURU_GAUGE_STATIONS = [
    {'name': 'Bellandur Lake', 'river': 'Koramangala-Challaghatta Valley', 'lat': 12.9350, 'lon': 77.6650},
    {'name': 'Varthur Lake', 'river': 'Koramangala-Challaghatta Valley', 'lat': 12.9400, 'lon': 77.7400},
    {'name': 'K R Puram Underpass Drain', 'river': 'Koramangala-Challaghatta Valley', 'lat': 12.9930, 'lon': 77.6950},
    {'name': 'Silk Board Junction Drain', 'river': 'Vrishabhavathi River', 'lat': 12.9170, 'lon': 77.6220},
    {'name': 'Hebbal Lake', 'river': 'Arkavathy River', 'lat': 13.0450, 'lon': 77.5950},
    {'name': 'Rachenahalli Lake', 'river': 'Arkavathy River', 'lat': 13.0450, 'lon': 77.6260},
    {'name': 'Ulsoor Lake', 'river': 'Vrishabhavathi River', 'lat': 12.9810, 'lon': 77.6220},
    {'name': 'Agara Lake', 'river': 'Koramangala-Challaghatta Valley', 'lat': 12.9210, 'lon': 77.6390},
    {'name': 'Madiwala Lake', 'river': 'Vrishabhavathi River', 'lat': 12.9190, 'lon': 77.6130},
    {'name': 'Puttenahalli Lake', 'river': 'Vrishabhavathi River', 'lat': 12.9010, 'lon': 77.5730},
    {'name': 'Yelahanka Lake', 'river': 'Arkavathy River', 'lat': 13.1005, 'lon': 77.5963},
    {'name': 'Sankey Tank', 'river': 'Arkavathy River', 'lat': 12.9990, 'lon': 77.5730},
]


def fetch_live_flood_gauges(stations):
    """
    Fetch live river-discharge data for a list of {name, river, lat, lon}
    stations from Open-Meteo's Flood API in a single batched request, and
    classify each by how far today's discharge sits above its own historical
    mean/p75 (see module docstring above for why this is relative, not
    absolute). Returns the same stations enriched with level/discharge/trend,
    or 'level': 'UNKNOWN' per-station if the API call fails.
    """
    import requests

    lats = ','.join(str(s['lat']) for s in stations)
    lons = ','.join(str(s['lon']) for s in stations)
    url = (
        f"https://flood-api.open-meteo.com/v1/flood?latitude={lats}&longitude={lons}"
        f"&daily=river_discharge,river_discharge_mean,river_discharge_max,river_discharge_p75"
        f"&past_days=2&forecast_days=1"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data = [data]  # API returns a bare object (not a list) for a single station
    except Exception as e:
        print(f"Flood gauge fetch error: {e}")
        data = [None] * len(stations)

    results = []
    for station, loc in zip(stations, data):
        daily = (loc or {}).get('daily', {})
        discharges = daily.get('river_discharge') or []

        if not discharges:
            results.append({**station, 'level': 'UNKNOWN', 'discharge': None,
                             'pct_of_normal': None, 'trend': '—',
                             'analysis': 'Live data unavailable'})
            continue

        today = discharges[-1]
        yesterday = discharges[-2] if len(discharges) > 1 else today
        mean = (daily.get('river_discharge_mean') or [0])[-1]
        p75 = (daily.get('river_discharge_p75') or [mean])[-1]

        if p75 > 0 and today >= p75 * 1.3:
            level = 'DANGER'
        elif p75 > 0 and today >= p75:
            level = 'HIGH'
        elif mean > 0 and today >= mean:
            level = 'MODERATE'
        else:
            level = 'NORMAL'

        pct_change = ((today - yesterday) / yesterday * 100) if yesterday else 0
        if pct_change > 5:
            trend = '↑ Rising'
        elif pct_change < -5:
            trend = '↓ Falling'
        else:
            trend = '→ Steady'

        pct_of_normal = round((today / mean) * 100) if mean else 100

        results.append({
            **station,
            'level': level,
            'discharge': round(today, 3),
            'pct_of_normal': pct_of_normal,
            'trend': trend,
        })

    return results


def sync_reports_to_csv(Report):
    """Sync all reports from the database to all_reports.csv and all_reports_export.csv"""
    try:
        reports = Report.query.all()
        # Define the header based on the system fields and user requirements
        headers = [
            'id', 'title', 'description', 'hazard_type', 'location', 
            'latitude', 'longitude', 'image_file', 'video_file', 'timestamp', 
            'user_id', 'status', 'priority', 'alert_radius', 'alert_sent', 
            'alert_sent_at', 'verified', 'confidence_score', 'ai_analysis', 
            'verification_status', 'rejection_reason', 'scheduled_deletion', 
            'verified_by', 'verified_at', 'likes_count', 'comments_count', 
            'shares_count', 'views_count', 'is_local_verified'
        ]
        
        # Files are saved in the project root
        project_root = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(project_root, 'all_reports.csv')
        export_path = os.path.join(project_root, 'all_reports_export.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for r in reports:
                # Convert report object to dict
                row = {}
                for h in headers:
                    val = getattr(r, h, None)
                    # Helper for relationship objects if someone passes them
                    if h == 'author_username' and hasattr(r, 'author'):
                        val = r.author.username if r.author else 'Unknown'
                        
                    if isinstance(val, (datetime)):
                        row[h] = val.strftime('%Y-%m-%d %H:%M:%S.%f')
                    else:
                        row[h] = val
                writer.writerow(row)
        
        # Also update the export version
        shutil.copy2(file_path, export_path)
        
        print(f"✅ REAL-TIME SYNC: {len(reports)} reports exported to CSV.")
        return True
    except Exception as e:
        print(f"❌ CSV Sync Error: {e}")
        return False