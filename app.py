from flask import Flask, render_template, url_for, flash, redirect, request, jsonify, send_from_directory, session, g
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from models import (
    db, User, Report, Badge, UserBadge, followers, Like, Comment, Notification,
    Agency, EmergencyEvent, ResourceAllocation, Volunteer, 
    VolunteerAssignment, SituationReport, PlasticUsage, CarbonSavings, LocalApproval, ReportView,
    CommunityEvent, EventParticipant, ResourceListing, ResourceMatch
)
from config import Config
from forms import (
    RegistrationForm, LoginForm, ReportForm, ProfileForm, LocationForm, AlertPreferencesForm,
    AgencyForm, EmergencyEventForm, ResourceAllocationForm, VolunteerRegistrationForm,
    VolunteerAssignmentForm, SituationReportForm, CoordinationSettingsForm,
    PlasticUsageForm, CarbonSavingsForm, CommunityEventForm, ResourceListingForm
)
from utils import (
    save_file, calculate_distance, analyze_plastic_image, 
    calculate_carbon_savings, calculate_points_for_activity, 
    validate_report_accuracy_3params, send_whatsapp_message,
    sync_reports_to_csv
)  # UPDATED
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import time
from datetime import datetime, timedelta
from sqlalchemy import func, cast 
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
from flask_migrate import Migrate
import json
from threading import Thread
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import io
import base64
from flask import Response
import numpy as np
import random
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)
app.config.from_object(Config)

migrate = Migrate(app, db)

db.init_app(app)

# Ensure database tables exist (CRITICAL for Render deployment)
with app.app_context():
    db.create_all()

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize scheduler for background tasks
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Sample data for dashboard (would be replaced with real data)
sample_reports = [
    {
        'id': 1,
        'title': 'High Waves at Marina Beach',
        'description': 'Severe high waves observed at Marina Beach with heights up to 8 feet',
        'hazard_type': 'high_waves',
        'location': 'Marina Beach, Chennai',
        'latitude': 13.0566,
        'longitude': 80.2783,
        'image_file': 'wave1.jpg',
        'timestamp': '2026-01-24 10:30:00',
        'author': 'coast_watcher_1',
        'confidence_score': 0.85,
        'verification_status': 'approved',
        'ai_analysis': 'High waves detected with strong correlation to reported weather patterns',
        'status': 'active',
        'priority': 'high'
    },
    {
        'id': 2,
        'title': 'Storm Surge Warning - Mumbai',
        'description': 'Potential storm surge developing near Mumbai coast',
        'hazard_type': 'storm_surge',
        'location': 'Mumbai Port Area',
        'latitude': 19.0760,
        'longitude': 72.8777,
        'image_file': 'storm1.jpg',
        'timestamp': '2026-01-24 09:15:00',
        'author': 'port_observer',
        'confidence_score': 0.78,
        'verification_status': 'pending',
        'ai_analysis': 'Storm pattern analysis indicates moderate storm surge risk',
        'status': 'active',
        'priority': 'critical'
    },
    {
        'id': 3,
        'title': 'Coastal Flooding - Kochi',
        'description': 'High tide combined with heavy rainfall causing coastal flooding',
        'hazard_type': 'coastal_flooding',
        'location': 'Kochi Waterfront',
        'latitude': 9.9312,
        'longitude': 76.2673,
        'image_file': 'flood1.jpg',
        'timestamp': '2026-01-24 08:45:00',
        'author': 'weather_spotter',
        'confidence_score': 0.92,
        'verification_status': 'approved',
        'ai_analysis': 'Verified flooding event with multiple supporting data sources',
        'status': 'active',
        'priority': 'critical'
    },
    {
        'id': 4,
        'title': 'Tsunami Alert - Andaman Sea',
        'description': 'Potential tsunami risk detected in Andaman Sea region',
        'hazard_type': 'tsunami',
        'location': 'Andaman Islands',
        'latitude': 11.7401,
        'longitude': 92.6586,
        'image_file': 'tsunami1.jpg',
        'timestamp': '2026-01-23 22:30:00',
        'author': 'seismic_monitor',
        'confidence_score': 0.65,
        'verification_status': 'pending',
        'ai_analysis': 'Seismic data analysis suggests low probability of significant tsunami',
        'status': 'active',
        'priority': 'high'
    },
    {
        'id': 5,
        'title': 'Abnormal Tide - Thiruvananthapuram',
        'description': 'Unusually high tide observed compared to normal patterns',
        'hazard_type': 'abnormal_tide',
        'location': 'Thiruvananthapuram Beach',
        'latitude': 8.5241,
        'longitude': 76.9366,
        'image_file': None,
        'timestamp': '2026-01-23 15:20:00',
        'author': 'tide_tracker',
        'confidence_score': 0.72,
        'verification_status': 'approved',
        'ai_analysis': 'Tidal anomaly confirmed by multiple sensors',
        'status': 'active',
        'priority': 'medium'
    },
    {
        'id': 6,
        'title': 'Swell Surge - Goa Coast',
        'description': 'Strong swell from southwest monsoon creating hazardous conditions',
        'hazard_type': 'swell_surge',
        'location': 'Goa Beach',
        'latitude': 15.2993,
        'longitude': 73.8243,
        'image_file': None,
        'timestamp': '2026-01-23 14:00:00',
        'author': 'ocean_monitor',
        'confidence_score': 0.81,
        'verification_status': 'approved',
        'ai_analysis': 'Swell patterns match predicted monsoon activity',
        'status': 'active',
        'priority': 'medium'
    },
    {
        'id': 7,
        'title': 'Coastal Hazard - Mangalore',
        'description': 'Combined weather effects creating coastal hazard conditions',
        'hazard_type': 'coastal_flooding',
        'location': 'Mangalore Port',
        'latitude': 12.9141,
        'longitude': 74.8560,
        'image_file': None,
        'timestamp': '2026-01-23 12:30:00',
        'author': 'marine_observer',
        'confidence_score': 0.68,
        'verification_status': 'rejected',
        'ai_analysis': 'Data inconsistency detected',
        'status': 'resolved',
        'priority': 'low'
    },
    {
        'id': 8,
        'title': 'High Waves - Visakhapatnam',
        'description': 'Bay of Bengal cyclone generating high waves',
        'hazard_type': 'high_waves',
        'location': 'Visakhapatnam Harbor',
        'latitude': 17.6868,
        'longitude': 83.2185,
        'image_file': None,
        'timestamp': '2026-01-23 11:00:00',
        'author': 'harbor_admin',
        'confidence_score': 0.88,
        'verification_status': 'approved',
        'ai_analysis': 'Wave height measurements confirmed by multiple sources',
        'status': 'active',
        'priority': 'high'
    }
]

# =============================================================================
# MULTILINGUAL SUPPORT - Enhanced Language Detection
# =============================================================================

TRANSLATIONS = {
    'en': {
        # Navigation
        'home': 'Home',
        'about': 'About',
        'report': 'Report Hazard',
        'dashboard': 'Dashboard',
        'profile': 'Profile',
        'community': 'Community',
        'leaderboard': 'Leaderboard',
        'login': 'Login',
        'register': 'Register',
        'logout': 'Logout',
        'search': 'Search',
        'notifications': 'Notifications',
        'reels': 'Hazard Feed',
        'share_app': 'Share App',
        'set_location': 'Set Location',
        'my_location': 'My Location',
        'use_current_location': 'Use Current Location',
        'capture_photo': 'Capture Photo',
        'start_recording': 'Start Recording',
        'stop_recording': 'Stop Recording',
        'settings': 'Settings',
        'quick_access': 'Quick Access',
        'all_leaderboards': 'All Leaderboards',
        'alert_preferences': 'Alert Preferences',
        
        # Common
        'submit': 'Submit',
        'save': 'Save',
        'cancel': 'Cancel',
        'edit': 'Edit',
        'delete': 'Delete',
        'confirm': 'Confirm',
        'back': 'Back',
        'next': 'Next',
        'previous': 'Previous',
        'follow': 'Follow',
        'unfollow': 'Unfollow',
        'view': 'View',
        'verify': 'Verify',
        
        # Hazard Types
        'tsunami': 'Tsunami',
        'storm_surge': 'Storm Surge',
        'high_waves': 'High Waves',
        'swell_surge': 'Swell Surge',
        'coastal_flooding': 'Coastal Flooding',
        'abnormal_tide': 'Abnormal Tide',
        'other': 'Other',
        
        # Messages
        'report_submitted': 'Your report has been submitted! +10 points! AI Confidence: {confidence}%',
        'login_success': 'Welcome back! Thank you for contributing to Sentinel AI.',
        'official_login': 'Welcome back, Officer! Thank you for keeping our community safe.',
        'analyst_login': 'Welcome back, Analyst! Your insights help protect our community.',
        'registration_success': 'Your account has been created! You can now log in.',
        'profile_updated': 'Your profile has been updated!',
        'location_saved': 'Your location has been saved!',
        'report_approved': 'Report approved successfully! User awarded +20 points.',
        'report_rejected': 'Report rejected successfully.',
        'language_changed': 'Language changed successfully.',
        'level_up': 'Level up! You reached level {level}!',
        'badge_earned': '🏆 Earned badge: {badge_name}!',
        'follow_success': 'You are now following {username}!',
        'unfollow_success': 'You have unfollowed {username}.',
        
        # Alert Messages
        'tsunami_alert': '🌊 Tsunami Alert! Evacuate to higher ground immediately.',
        'storm_surge_alert': '🌪 Storm Surge Alert! Seek shelter away from the coast.',
        'high_waves_alert': '🌊 High Wave Alert! Avoid beach activities.',
        'swell_surge_alert': '🌊 Swell Surge Alert! Exercise caution near water.',
        'coastal_flooding_alert': '⚠️ Coastal Flooding Alert! Move to higher ground.',
        'abnormal_tide_alert': '⚠️ Abnormal Tide Alert! Be cautious of unusual water levels.',
        'general_alert': '⚠️ Hazard Alert! A verified hazard has been reported in your area.',
        
        # Forms
        'username': 'Username',
        'email': 'Email',
        'password': 'Password',
        'confirm_password': 'Confirm Password',
        'remember_me': 'Remember Me',
        'title': 'Title',
        'description': 'Description',
        'basic_information': 'Basic Information',
        'location_details': 'Location Details',
        'severity_assessment': 'Severity Assessment',
        'location': 'Location',
        'latitude': 'Latitude',
        'longitude': 'Longitude',
        'hazard_type': 'Hazard Type',
        'photo': 'Upload Photo',
        'video': 'Upload Video',
        'bio': 'Bio',
        'home_latitude': 'Home Latitude',
        'home_longitude': 'Home Longitude',
        
        # Stats
        'total_reports': 'Total Reports',
        'verified_reports': 'Verified Reports',
        'pending_reports': 'Pending Reports',
        'points': 'Points',
        'level': 'Level',
        
        # Tools & Dashboards
        'coordination_platform': 'Coordination Platform',
        'basic_dashboard': 'Basic Dashboard',
        'tools': 'Tools',
        'analyst_dashboard': 'Analyst Dashboard',
        'risk_simulator': 'Risk Simulator',
        'emergency_management': 'Emergency Management',
        'resource_management': 'Resource Management',
        'volunteer_management': 'Volunteer Management',
        'situation_reports': 'Situation Reports',
        'user_analytics': 'User Analytics',
        'ai_support_assistant': 'AI Support Assistant',
        'ai_powered_analytics': 'AI-Powered Disaster Analytics',
        'run_risk_simulation': 'Run Risk Simulation',
        'global_alert': 'Global Alert',
        'export_pdf': 'Export PDF',
        'total_incidents': 'Total Incidents',
        'verification_rate': 'Verification Rate',
        'personnel': 'Personnel',
        'pending': 'Pending',
        'incident_hotspots': 'Incident Hotspots Heatmap',
        'weather_warnings': 'Weather & Early Warnings',
        'incident_velocity': 'Incident Velocity',
        'network_participation': 'Network Participation',
        'incident_intelligence_log': 'Incident Intelligence Log',
        'load_more': 'Load More',
        
        # Errors
        'required_field': 'This field is required.',
        'invalid_email': 'Invalid email address.',
        'password_mismatch': 'Passwords must match.',
        'file_too_large': 'File too large. Maximum file size is 16MB.',
        'unauthorized': 'Unauthorized action.',
        'user_not_found': 'User not found.',

        # Brand Keys
        'coastal_alert': 'Sentinel AI',
        'coastal_safety_network': 'Sentinel AI',
        'coastal_safety_ai_assistant': 'Sentinel AI Assistant',
        'protecting_coastal_communities': 'Protecting communities worldwide',
        'maximum_intelligence': 'Maximum Intelligence, Maximum Safety',
        'active': 'ACTIVE',
        'quick_search': 'Quick Search',
        'report_hazard_description': 'Spotted a hazard? Report it now and help protect your community.',
        'submit_report': 'Submit Report',
        'register_to_report': 'Register to Report',
        'analytics_description': 'View real-time disaster insights and data visualizations.',
        'view_dashboard': 'View Dashboard',
        'your_contribution': 'Your Contribution',
        'community_activity': 'Community Activity',
        'reports_submitted': 'Reports Submitted',
        'view_leaderboard': 'View Leaderboard',
    },
    
    'ta': {  # Tamil
        'home': 'முகப்பு',
        'about': 'விவரம்',
        'report': 'அபாயத்தைப் பதிவு செய்க',
        'dashboard': 'டாஷ்போர்டு',
        'profile': 'சுயவிவரம்',
        'leaderboard': 'முன்னணி வாரியம்',
        'login': 'உள்நுழைக',
        'register': 'பதிவு செய்க',
        'logout': 'வெளியேறுக',
        'search': 'தேடுக',
        'notifications': 'அறிவிப்புகள்',
        'reels': 'அபாய ஊட்டம்',
        'community_hub': 'சமூக மையம்',
        'lifeline': 'லைஃப்லைன் P2P',
        
        'submit': 'சமர்ப்பி',
        'save': 'சேமி',
        'cancel': 'ரத்து செய்',
        
        'tsunami': 'ஆழிப்பேரலை',
        'storm_surge': 'புயல் அலை',
        'high_waves': 'உயர் அலைகள்',
        'coastal_flooding': 'கடற்கரை வெள்ளம்',
        
        'username': 'பயனர் பெயர்',
        'email': 'மின்னஞ்சல்',
        'password': 'கடவுச்சொல்',
        'confirm_password': 'கடவுச்சொல்லை உறுதிப்படுத்து',
        'remember_me': 'என்னை நினைவில் கொள்',
        'title': 'தலைப்பு',
        'description': 'விளக்கம்',
        'location': 'இடம்',
        'latitude': 'அட்சரேகை',
        'longitude': 'தீர்க்கரேகை',
        'hazard_type': 'அபாய வகை',
        'photo': 'புகைப்படத்தைப் பதிவேற்று',
        'video': 'வீடியோவைப் பதிவேற்று',
        'bio': 'சுயசரிதை',
        
        'points': 'புள்ளிகள்',
        'level': 'நிலை',
        
        'report_submitted': 'உங்கள் புகாரை சமர்ப்பித்துள்ளோம்! +10 புள்ளிகள்! AI நம்பகத்தன்மை: {confidence}%',
        'login_success': 'மீண்டும் வரவேற்கிறோம்! Sentinel AI-க்கு பங்களித்தமைக்கு நன்றி.',
        'registration_success': 'உங்கள் கணக்கு உருவாக்கப்பட்டது! இப்போது நீங்கள் உள்நுழையலாம்.',
        'coastal_alert': 'Sentinel AI',
        'coastal_safety_network': 'Sentinel AI',
        'coastal_safety_ai_assistant': 'Sentinel AI உதவியாளர்',
        'maximum_intelligence': 'அதிகபட்ச அறிவுத்திறன், அதிகபட்ச பாதுகாப்பு',
        'search_placeholder': 'தேடுக...',
        'active': 'செயலில்',
        'quick_search': 'விரைவான தேடல்',
        'report_hazard_description': 'ஒரு ஆபத்தைக் கண்டீர்களா? இப்போதே அதைப் புகாரளிப்பதன் மூலம் உங்கள் சமூகத்தைப் பாதுகாக்கவும்.',
        'submit_report': 'புகாரைச் சமர்ப்பிக்கவும்',
        'register_to_report': 'புகார் அளிக்கப் பதிவு செய்யவும்',
        'analytics_description': 'நிஜ நேர பேரிடர் நுண்ணறிவுகள் மற்றும் தரவு காட்சிப்படுத்தல்களைக் காணுங்கள்.',
        'view_dashboard': 'டாஷ்போர்டைப் பார்',
        'your_contribution': 'உங்கள் பங்களிப்பு',
        'community_activity': 'சமூக செயல்பாடு',
        'reports_submitted': 'சமர்ப்பிக்கப்பட்ட அறிக்கைகள்',
        'view_leaderboard': 'முன்னணி வாரியத்தைப் பார்',
        'coordination_platform': 'ஒருங்கிணைப்பு தளம்',
        'basic_dashboard': 'அடிப்படை டாஷ்போர்டு',
        'analyst_dashboard': 'ஆய்வாளர் டாஷ்போர்டு',
        'risk_simulator': 'இடர் சிமுலேட்டர்',
        'emergency_management': 'அவசரகால மேலாண்மை',
        'resource_management': 'வள மேலாண்மை',
        'volunteer_management': 'தன்னார்வலர் மேலாண்மை',
        'situation_reports': 'நிலைமை அறிக்கைகள்',
        'ai_support_assistant': 'AI ஆதரவு உதவியாளர்',
    },
    
    'hi': {  # Hindi
        'home': 'होम',
        'about': 'बारे में',
        'report': 'खतरा रिपोर्ट करें',
        'dashboard': 'डैशबोर्ड',
        'profile': 'प्रोफाइल',
        'leaderboard': 'लीडरबोर्ड',
        'login': 'लॉगिन',
        'register': 'रजिस्टर',
        'logout': 'लॉगआउट',
        'search': 'खोजें',
        'notifications': 'सूचनाएं',
        'reels': 'खतरा फ़ीड',
        'community_hub': 'सामुदायिक केंद्र',
        'lifeline': 'लाइफलाइन P2P',
        
        'submit': 'जमा करें',
        'save': 'सहेजें',
        'cancel': 'रद्द करें',
        'edit': 'संपादित करें',
        'delete': 'मिटाएं',
        
        'tsunami': 'सुनामी',
        'storm_surge': 'तूफान की लहर',
        'high_waves': 'उच्च लहरें',
        'coastal_flooding': 'तटीय बाढ़',
        
        'username': 'उपयोगकर्ता नाम',
        'email': 'ईमेल',
        'password': 'पासवर्ड',
        'confirm_password': 'पासवर्ड की पुष्टि करें',
        'remember_me': 'मुझे याद रखें',
        'title': 'शीर्षक',
        'description': 'विवरण',
        'basic_information': 'बुनियादी जानकारी',
        'location_details': 'स्थान का विवरण',
        'severity_assessment': 'गंभीरता का आकलन',
        'location': 'स्थान',
        'latitude': 'अक्षांश',
        'longitude': 'देशांतर',
        'hazard_type': 'खतरे का प्रकार',
        'photo': 'फोटो अपलोड करें',
        'video': 'वीडियो अपलोड करें',
        'bio': 'परिचय',
        
        'points': 'अंक',
        'level': 'स्तर',
        'total_reports': 'कुल रिपोर्ट',
        
        'report_submitted': 'आपकी रिपोर्ट सबमिट कर दी गई है! +10 अंक! AI विश्वास: {confidence}%',
        'login_success': 'वापसी पर स्वागत है! Sentinel AI में योगदान देने के लिए धन्यवाद।',
        'registration_success': 'आपका खाता बन गया है! अब आप लॉगिन कर सकते हैं।',
        'coastal_alert': 'Sentinel AI',
        'coastal_safety_network': 'Sentinel AI',
        'coastal_safety_ai_assistant': 'Sentinel AI सहायक',
        'maximum_intelligence': 'अधिकतम इंटेलिजेंस, अधिकतम सुरक्षा',
        'search_placeholder': 'उपयोगकर्ता, रिपोर्ट, स्थान खोजें...',
        'active': 'सक्रिय',
        'quick_search': 'त्वरित खोज',
        'report_hazard_description': 'कोई खतरा दिखा? अभी रिपोर्ट करें और अपने समुदाय की रक्षा करें।',
        'submit_report': 'रिपोर्ट सबमिट करें',
        'register_to_report': 'रिपोर्ट करने के लिए पंजीकरण करें',
        'analytics_description': 'वास्तविक समय के आपदा अंतर्दृष्टि और डेटा विज़ुअलाइज़ेशन देखें।',
        'view_dashboard': 'डैशबोर्ड देखें',
        'your_contribution': 'आपका योगदान',
        'community_activity': 'सामुदायिक गतिविधि',
        'reports_submitted': 'रिपोर्ट सबमिट की गई',
        'view_leaderboard': 'लीडरबोर्ड देखें',
        'coordination_platform': 'समन्वय मंच',
        'basic_dashboard': 'बुनियादी डैशबोर्ड',
        'analyst_dashboard': 'विश्लेषक डैशबोर्ड',
        'risk_simulator': 'जोखिम सिम्युलेटर',
        'emergency_management': 'आपातकालीन प्रबंधन',
        'resource_management': 'संसाधन प्रबंधन',
        'volunteer_management': 'स्वयंसेवक प्रबंधन',
        'situation_reports': 'स्थिति रिपोर्ट',
        'user_analytics': 'उपयोगकर्ता विश्लेषण',
        'ai_support_assistant': 'AI सहायता सहायक',
    },
    
    'te': {  # Telugu
        'home': 'హోమ్',
        'about': 'గురించి',
        'report': 'హాజర్డ్ నివేదించండి',
        'dashboard': 'డాష్బోర్డ్',
        'profile': 'ప్రొఫైల్',
        'leaderboard': 'లీడర్బోర్డ్',
        'login': 'లాగిన్',
        'register': 'నమోదు',
        'logout': 'లాగౌట్',
        'search': 'శోధించు',
        'notifications': 'నోటిఫికేషన్లు',
        'reels': 'హాజర్డ్ ఫీడ్',
        'community_hub': 'కమ్యూనిటీ హబ్',
        'lifeline': 'లైఫ్‌లైన్ P2P',
        
        'submit': 'సమర్పించు',
        'save': 'సేవ్ చేయండి',
        'cancel': 'రద్దు చేయండి',
        
        'tsunami': 'సునామీ',
        'storm_surge': 'స్టార్మ్ సర్జ్',
        'high_waves': 'అధిక అలలు',
        'coastal_flooding': 'తీర ప్రాంతం వరద',
        
        'username': 'వినియోగదారు పేరు',
        'email': 'ఈమెయిల్',
        'password': 'పాస్వర్డ్',
        'confirm_password': 'పాస్వర్డ్ ధృవీకరించండి',
        'remember_me': 'నన్ను గుర్తుంచుకో',
        'title': 'శీర్షిక',
        'description': 'వివరణ',
        'location': 'స్థానం',
        'latitude': 'అక్షాంశం',
        'longitude': 'రేఖాంశం',
        'hazard_type': 'ప్రమాద రకం',
        'photo': 'ఫోటో అప్‌లోడ్',
        'video': 'వీడియో అప్‌లోడ్',
        'bio': 'బయో',
        
        'points': 'పాయింట్లు',
        'level': 'స్థాయి',
        
        'report_submitted': 'మీ నివేదిక సమర్పించబడింది! +10 పాయింట్లు! AI నమ్మకం: {confidence}%',
        'login_success': 'మళ్లీ స్వాగతం! Sentinel AI పట్ల మీ కృషికి ధన్యవాదాలు.',
        'registration_success': 'మీ ఖాతా సృష్టించబడింది! మీరు ఇప్పుడు లాగిన్ చేయవచ్చు.',
        'coastal_alert': 'Sentinel AI',
        'coastal_safety_network': 'Sentinel AI',
        'coastal_safety_ai_assistant': 'Sentinel AI అసిస్టెంట్',
        'maximum_intelligence': 'గరిష్ట మేధస్సు, గరిష్ట భద్రత',
        'search_placeholder': 'శోధించండి...',
        'active': 'క్రియాశీలకంగా ఉంది',
        'quick_search': 'త్వరిత శోధన',
        'report_hazard_description': 'ప్రమాదాన్ని గుర్తించారా? ఇప్పుడే నివేదించండి మరియు మీ కమ్యూనిటీని రక్షించండి.',
        'submit_report': 'నివేదికను సమర్పించండి',
        'register_to_report': 'నివేదించడానికి నమోదు చేసుకోండి',
        'analytics_description': 'నిజ-సమయ విపత్తు అంతర్దృష్టులు మరియు డేటా విజువలైజేషన్లను చూడండి.',
        'view_dashboard': 'డాష్‌బోర్డ్ చూడండి',
        'your_contribution': 'మీ సహకారం',
        'community_activity': 'కమ్యూనిటీ కార్యాచరణ',
        'reports_submitted': 'నివేదికలు సమర్పించబడ్డాయి',
        'view_leaderboard': 'లీడర్‌బోర్డ్ చూడండి',
        'coordination_platform': 'సమన్వయ వేదిక',
        'basic_dashboard': 'ప్రాథమిక డాష్‌బోర్డ్',
        'analyst_dashboard': 'అనలిస్ట్ డాష్‌బోర్డ్',
        'risk_simulator': 'రిస్క్ సిమ్యులేటర్',
        'emergency_management': 'అత్యవసర నిర్వహణ',
        'resource_management': 'వనరుల నిర్వహణ',
        'volunteer_management': 'వాలంటీర్ నిర్వహణ',
        'situation_reports': 'పరిస్థితి నివేదికలు',
        'ai_support_assistant': 'AI మద్దతు అసిస్టెంట్',
    },
    
    'ml': {  # Malayalam
        'home': 'ഹോം',
        'about': 'വിവരണം',
        'report': 'അപകടം റിപ്പോർട്ട് ചെയ്യുക',
        'dashboard': 'ഡാഷ്ബോർഡ്',
        'profile': 'പ്രൊഫൈൽ',
        'leaderboard': 'ലീഡർബോർഡ്',
        'login': 'ലോഗിൻ',
        'register': 'രജിസ്റ്റർ',
        'logout': 'ലോഗൗട്ട്',
        'search': 'തിരയുക',
        'notifications': 'അറിയിപ്പുകൾ',
        'reels': 'ഹാസാർഡ് ഫീഡ്',
        'community_hub': 'കമ്മ്യൂണിറ്റി ഹബ്',
        'lifeline': 'ലൈഫ്‌ലൈൻ P2P',
        
        'submit': 'സമർപ്പിക്കുക',
        'save': 'സേവ് ചെയ്യുക',
        'cancel': 'റദ്ദാക്കുക',
        
        'tsunami': 'സുനാമി',
        'storm_surge': 'കൊടുങ്കാറ്റ് തിര',
        'high_waves': 'ഉയർന്ന തിരമാലകൾ',
        
        'username': 'യൂസർനെയിം',
        'email': 'ഇമെയിൽ',
        'password': 'പാസ്‌വേഡ്',
        'confirm_password': 'പാസ്‌വേഡ് ഉറപ്പിക്കുക',
        'remember_me': 'എന്നെ ഓർമ്മിക്കുക',
        
        'points': 'പോയിന്റുകൾ',
        'level': 'ലെവൽ',
        
        'report_submitted': 'നിങ്ങളുടെ റിപ്പോർട്ട് സമർപ്പിച്ചു! +10 പോയിന്റുകൾ! AI ആത്മവിശ്വാസം: {confidence}%',
        'login_success': 'വീണ്ടും സ്വാഗതം! Sentinel AI-ലേക്ക് സംഭാവന ചെയ്തതിന് നന്ദി.',
        'coastal_alert': 'Sentinel AI',
        'coastal_safety_network': 'Sentinel AI',
        'maximum_intelligence': 'പരമാവധി ഇന്റലിജൻസ്, പരമാവധി സുരക്ഷ',
        'active': 'സജീവം',
        'quick_search': '്രുത തിരയൽ',
        'coordination_platform': 'കോർഡിനേഷൻ പ്ലാറ്റ്ഫോം',
        'basic_dashboard': 'ബേസിക് ഡാഷ്ബോർഡ്',
        'analyst_dashboard': 'അനലിസ്റ്റ് ഡാഷ്ബോർഡ്',
        'risk_simulator': 'റിസ്ക് സിമുലേറ്റർ',
        'emergency_management': 'അടിയന്തര മാനേജ്‌മെന്റ്',
        'resource_management': 'വിഭവ മാനേജ്‌മെന്റ്',
        'volunteer_management': 'വളണ്ടിയർ മാനേജ്‌മെന്റ്',
        'situation_reports': 'സിറ്റുവേഷൻ റിപ്പോർട്ടുകൾ',
        'ai_support_assistant': 'AI സപ്പോർട്ട് അസിസ്റ്റന്റ്',
    },
    
    'kn': {  # Kannada
        'home': 'ಹೋಮ್',
        'about': 'ವಿವರಣೆ',
        'report': 'ಅಪಾಯವನ್ನು ವರದಿ ಮಾಡಿ',
        'dashboard': 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
        'profile': 'ಪ್ರೊಫೈಲ್',
        'leaderboard': 'ಲೀಡರ್‌ಬೋರ್ಡ್',
        'login': 'ಲಾಗಿನ್',
        'register': 'ನೋಂದಾಯಿಸಿ',
        'logout': 'ಲಾಗ್‌ಔಟ್',
        'search': 'ಹುಡುಕು',
        'notifications': 'ಅಧಿಸೂಚನೆಗಳು',
        'reels': 'ಹಜಾರ್ಡ್ ಫೀಡ್',
        'community_hub': 'ಕಮ್ಯುನಿಟಿ ಹಬ್',
        'lifeline': 'ಲೈಫ್‌ಲೈನ್ P2P',
        
        'submit': 'ಸಲ್ಲಿಸು',
        'save': 'ಉಳಿಸು',
        'cancel': 'ರದ್ದುಮಾಡು',
        
        'tsunami': 'ಸುನಾಮಿ',
        'storm_surge': 'ಬಿರುಗಾಳಿ ಅಲೆ',
        'high_waves': 'ಎತ್ತರದ ಅಲೆಗಳು',
        
        'username': 'ಬಳಕೆದಾರಹೆಸರು',
        'email': 'ಇಮೇಲ್',
        'password': 'ಪಾಸ್ವರ್ಡ್',
        'confirm_password': 'ಪಾಸ್ವರ್ಡ್ ದೃಢೀಕರಿಸಿ',
        'remember_me': 'ನನ್ನನ್ನು ನೆನಪಿಡಿ',
        
        'points': 'ಪಾಯಿಂಟ್ಗಳು',
        'level': 'ಹಂತ',
        
        'report_submitted': 'ನಿಮ್ಮ ವರದಿಯನ್ನು ಸಲ್ಲಿಸಲಾಗಿದೆ! +10 ಅಂಕಗಳು! AI ವಿಶ್ವಾಸ: {confidence}%',
        'login_success': 'ಮತ್ತೆ ಸ್ವಾಗತ! Sentinel AI ಗೆ ಕೊಡುಗೆ ನೀಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು.',
        'coastal_alert': 'Sentinel AI',
        'coastal_safety_network': 'Sentinel AI',
        'coastal_safety_ai_assistant': 'Sentinel AI Assistant',
        'protecting_coastal_communities': 'Protecting communities worldwide',
        'maximum_intelligence': 'ಗರಿಷ್ಠ ಬುದ್ಧಿವಂತಿಕೆ, ಗರಿಷ್ಠ ಸುರಕ್ಷತೆ',
        'active': 'ಸಕ್ರಿಯ',
        'quick_search': 'ತ್ವರಿತ ಹುಡುಕಾಟ',
        'coordination_platform': 'ಸಮನ್ವಯ ವೇದಿಕೆ',
        'basic_dashboard': 'ಮೂಲ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
        'analyst_dashboard': 'ವಿಶ್ಲೇಷಕ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
        'risk_simulator': 'ರಿಸ್ಕ್ ಸಿಮ್ಯುಲೇಟರ್',
        'emergency_management': 'ತುರ್ತು ನಿರ್ವಹಣೆ',
        'resource_management': 'ಸಂಪನ್ಮೂಲ ನಿರ್ವಹಣೆ',
        'volunteer_management': 'ಸ್ವಯಂಸೇವಕ ನಿರ್ವಹಣೆ',
        'situation_reports': 'ಪರಿಸ್ಥಿತಿ ವರದಿಗಳು',
        'ai_support_assistant': 'AI ಬೆಂಬಲ ಸಹಾಯಕ',
    }
}

def get_translation(lang, key, default=None):
    """Get translation for a key in specified language with better fallback"""
    # First try the requested language
    if lang in TRANSLATIONS and key in TRANSLATIONS[lang]:
        return TRANSLATIONS[lang][key]
    
    # Fallback to English
    if key in TRANSLATIONS['en']:
        return TRANSLATIONS['en'][key]
    
    # Final fallback - return a formatted version of the key
    return default or key.replace('_', ' ').title()

def get_available_languages():
    """Return list of available language codes"""
    return list(TRANSLATIONS.keys())

def detect_preferred_language(latitude, longitude):
    """
    Enhanced language detection based on geographic location
    Focuses on Indian coastal regions where different languages are spoken
    """
    if latitude is None or longitude is None:
        return 'en'
    
    # Language regions with their geographic centers and radius
    language_regions = [
        # Tamil Nadu (Tamil)
        {'lang': 'ta', 'center': (11.1271, 78.6569), 'radius': 300, 'coastal': True},
        # Kerala (Malayalam)
        {'lang': 'ml', 'center': (10.8505, 76.2711), 'radius': 200, 'coastal': True},
        # Andhra Pradesh/Telangana (Telugu)
        {'lang': 'te', 'center': (15.9129, 79.7400), 'radius': 350, 'coastal': True},
        # Karnataka (Kannada)
        {'lang': 'kn', 'center': (12.9716, 77.5946), 'radius': 300, 'coastal': True},
        # Maharashtra (Hindi/Marathi influenced)
        {'lang': 'hi', 'center': (19.0760, 72.8777), 'radius': 400, 'coastal': True},
        # Gujarat (Hindi influenced)
        {'lang': 'hi', 'center': (22.2587, 71.1924), 'radius': 400, 'coastal': True},
        # West Bengal (Hindi influenced)
        {'lang': 'hi', 'center': (22.5726, 88.3639), 'radius': 400, 'coastal': True},
        # Odisha (Hindi influenced)
        {'lang': 'hi', 'center': (20.9517, 85.0985), 'radius': 300, 'coastal': True},
    ]
    
    # Special coastal city mappings for more accuracy
    coastal_cities = {
        'ta': [  # Tamil - Tamil Nadu coastal cities
            (13.0827, 80.2707),  # Chennai
            (8.7139, 77.7567),   # Thirunelveli
            (9.9252, 78.1198),   # Madurai
            (10.7905, 78.7047),  # Trichy
        ],
        'ml': [  # Malayalam - Kerala coastal cities
            (9.9312, 76.2673),   # Kochi
            (11.2588, 75.7804),  # Kozhikode
            (8.5241, 76.9366),   # Thiruvananthapuram
        ],
        'te': [  # Telugu - Andhra Pradesh coastal cities
            (16.5062, 80.6480),  # Vijayawada
            (17.6868, 83.2185),  # Visakhapatnam
        ],
        'kn': [  # Kannada - Karnataka coastal cities
            (12.9141, 74.8560),  # Mangalore
            (13.3409, 74.7421),  # Udupi
        ],
        'hi': [  # Hindi influenced coastal cities
            (19.0760, 72.8777),  # Mumbai
            (22.5726, 88.3639),  # Kolkata
            (21.1458, 79.0882),  # Nagpur
        ]
    }
    
    # First check if it's near specific coastal cities (more accurate)
    for lang, cities in coastal_cities.items():
        for city in cities:
            distance = calculate_distance(latitude, longitude, city[0], city[1])
            if distance < 50:  # Within 50km of coastal city
                print(f"🌍 Language detected: {lang} (near coastal city, distance: {distance:.1f}km)")
                return lang
    
    # Then check regional centers
    for region in language_regions:
        distance = calculate_distance(latitude, longitude, region['center'][0], region['center'][1])
        if distance < region['radius']:
            print(f"🌍 Language detected: {region['lang']} (regional center, distance: {distance:.1f}km)")
            return region['lang']
    
    # Default to English if no match
    print("🌍 Language defaulted to: English (no regional match)")
    return 'en'

def get_locale():
    """Get the current locale from session or user preference"""
    # Check session first
    if 'language' in session:
        return session['language']
    
    # Check user preference if logged in
    if current_user.is_authenticated and hasattr(current_user, 'language'):
        return current_user.language
    
    # Try to detect from browser (for new users)
    browser_lang = request.accept_languages.best_match(app.config['LANGUAGES'])
    return browser_lang or 'en'

@app.before_request
def before_request():
    """Set global language context before each request"""
    g.language = get_locale()
    g.available_languages = get_available_languages()

def translate(key, **kwargs):
    """Translation helper function"""
    lang = get_locale()
    translation = get_translation(lang, key)
    
    # Format with kwargs if provided
    if kwargs and isinstance(translation, str):
        try:
            return translation.format(**kwargs)
        except:
            return translation
    return translation

# Make translate function available to all templates
@app.context_processor
def inject_translations():
    def translate(key, **kwargs):
        """Translation helper available in all templates"""
        lang = get_locale()
        translation = get_translation(lang, key)
        
        # Format with kwargs if provided
        if kwargs and isinstance(translation, str):
            try:
                return translation.format(**kwargs)
            except:
                return translation
        return translation
    
    return dict(
        translate=translate,
        current_language=get_locale(),
        available_languages=get_available_languages()
    )

@app.route('/set_language/<lang>')
def set_language(lang):
    """Set the language preference"""
    if lang in app.config['LANGUAGES']:
        session['language'] = lang
        
        # Update user preference if logged in
        if current_user.is_authenticated:
            current_user.language = lang
            db.session.commit()
        
        flash(f'Language changed to {lang.upper()}', 'success')
    else:
        flash('Selected language is not supported.', 'warning')
    
    # Redirect to the same page or home
    return redirect(request.referrer or url_for('home'))

# =============================================================================
# END OF MULTILINGUAL SUPPORT
# =============================================================================

def init_badges():
    badges = [
        {'name': 'first_reporter', 'description': 'Submitted your first report', 'icon': '🚀', 'points_required': 0},
        {'name': 'storm_watcher', 'description': 'Reported 3 storm surges', 'icon': '⛈️', 'points_required': 0},
        {'name': 'community_guardian', 'description': 'Reached 100 points', 'icon': '🛡️', 'points_required': 100},
        {'name': 'verified_observer', 'description': 'Had 5 reports verified', 'icon': '✅', 'points_required': 0},
        {'name': 'ai_verified', 'description': 'Submitted a high-confidence AI-verified report', 'icon': '🤖', 'points_required': 0},
    ]
    
    for badge_data in badges:
        if not Badge.query.filter_by(name=badge_data['name']).first():
            badge = Badge(
                name=badge_data['name'],
                description=badge_data['description'],
                icon=badge_data['icon'],
                points_required=badge_data['points_required']
            )
            db.session.add(badge)
    
    db.session.commit()

def check_and_award_badges(user):
    # First Reporter badge
    if len(user.reports) == 1:
        award_badge(user, 'first_reporter')
    
    # Storm Watcher badge
    storm_reports = Report.query.filter_by(user_id=user.id, hazard_type='storm_surge').count()
    if storm_reports >= 3:
        award_badge(user, 'storm_watcher')
    
    # Community Guardian badge
    if user.points >= 100:
        award_badge(user, 'community_guardian')
    
    # Verified Observer badge
    verified_reports = Report.query.filter_by(user_id=user.id, verification_status='approved').count()
    if verified_reports >= 5:
        award_badge(user, 'verified_observer')
    
    # AI Verified badge
    high_confidence_reports = Report.query.filter(
        Report.user_id == user.id,
        Report.confidence_score >= 0.8,
        Report.verification_status == 'approved'
    ).count()
    if high_confidence_reports >= 1:
        award_badge(user, 'ai_verified')
    
    # Level up system
    new_level = user.points // 50 + 1
    if new_level > user.level:
        user.level = new_level
        flash(translate('level_up', level=new_level), 'success')

def award_badge(user, badge_name):
    badge = Badge.query.filter_by(name=badge_name).first()
    if badge and not UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first():
        user_badge = UserBadge(user_id=user.id, badge_id=badge.id)
        db.session.add(user_badge)
        flash(translate('badge_earned', badge_name=badge.name), 'success')

def analyze_report_with_ai(report):
    """Analyze a report using AI to generate confidence score and analysis
    
    Uses 3-parameter validation system:
    1. Weather & Early Warnings - Heatmap match (33%)
    2. Live Climate Data - Weather alignment (33%)
    3. User Quality - Credibility score (34%)
    """
    try:
        # NEW: Use 3-parameter validation system
        accuracy_result = validate_report_accuracy_3params(report)
        
        # Initialize analysis components with legacy method
        analysis_parts = []
        confidence_factors = []
        
        # 1. Source Reliability Analysis (User Quality from 3-param system)
        user_quality = accuracy_result['parameter_3_user_quality']
        analysis_parts.append(f"User Quality: {user_quality['analysis']}")
        confidence_factors.append(user_quality['score'])
        
        # 2. Corroboration Analysis (Heatmap Match from 3-param system)
        heatmap_match = accuracy_result['parameter_1_heatmap']
        analysis_parts.append(f"Heatmap Match: {heatmap_match['analysis']}")
        confidence_factors.append(heatmap_match['score'])
        
        # 3. Climate Data Analysis (Weather Alignment from 3-param system)
        climate_align = accuracy_result['parameter_2_climate']
        analysis_parts.append(f"Climate Alignment: {climate_align['analysis']}")
        confidence_factors.append(climate_align['score'])
        
        # 4. Media Analysis (if available)
        if report.image_file:
            media_analysis = analyze_media(report)
            analysis_parts.append(f"Media Analysis: {media_analysis['analysis']}")
            confidence_factors.append(media_analysis['score'])
        else:
            confidence_factors.append(0.3)
            analysis_parts.append("Media Analysis: No visual evidence provided")
        
        # 5. Linguistic Analysis
        linguistic_analysis = analyze_text(report.description, report.title)
        analysis_parts.append(f"Linguistic Analysis: {linguistic_analysis['analysis']}")
        confidence_factors.append(linguistic_analysis['score'])
        
        # Calculate overall confidence score (weighted average)
        weights = [0.25, 0.25, 0.25, 0.15, 0.10]  # Adjusted weights to include all factors
        weighted_scores = [score * weight for score, weight in zip(confidence_factors, weights)]
        confidence_score = sum(weighted_scores) / sum(weights)
        
        # Blend with 3-parameter accuracy for final score
        final_confidence_score = (confidence_score * 0.5) + (accuracy_result['overall_accuracy'] * 0.5)
        
        # Generate comprehensive analysis text
        analysis_text = f"3-PARAM ACCURACY: {accuracy_result['accuracy_percent']}% | {accuracy_result['detailed_analysis']} | " + " | ".join(analysis_parts)
        
        return {
            'confidence_score': final_confidence_score,
            'analysis': analysis_text,
            'accuracy_3param': accuracy_result  # Include full 3-param breakdown
        }
        
    except Exception as e:
        print(f"AI Analysis Error: {e}")
        return {
            'confidence_score': 0.5,
            'analysis': "AI analysis temporarily unavailable. Manual review required.",
            'accuracy_3param': None
        }

def analyze_user_reliability(user):
    """Analyze user reliability based on history"""
    user_reports = Report.query.filter_by(user_id=user.id).all()
    verified_reports = [r for r in user_reports if r.verification_status == 'approved']
    
    reliability_score = 0.5  # Default neutral score
    
    if user.role in ['official', 'analyst']:
        reliability_score = 0.9
        analysis = "High reliability: Verified official user"
    elif len(verified_reports) >= 5:
        reliability_score = 0.8
        analysis = "High reliability: Multiple verified reports"
    elif len(verified_reports) >= 1:
        reliability_score = 0.7
        analysis = "Good reliability: Some verified reports"
    elif len(user_reports) == 0:
        reliability_score = 0.4
        analysis = "New user: No report history"
    else:
        reliability_score = 0.5
        analysis = "Average reliability: Limited history"
    
    return {'score': reliability_score, 'analysis': analysis}

def analyze_corroboration(report):
    """Check for corroborating reports in same area and time"""
    # Find reports in similar location and time window
    time_window = timedelta(hours=2)
    location_threshold = 0.01  # ~1.1 km
    
    similar_reports = Report.query.filter(
        Report.id != report.id,
        Report.timestamp.between(report.timestamp - time_window, report.timestamp + time_window),
        Report.latitude.between(report.latitude - location_threshold, report.latitude + location_threshold),
        Report.longitude.between(report.longitude - location_threshold, report.longitude + location_threshold),
        Report.hazard_type == report.hazard_type
    ).all()
    
    if len(similar_reports) >= 3:
        score = 0.9
        analysis = f"Strong corroboration: {len(similar_reports)} similar reports"
    elif len(similar_reports) >= 1:
        score = 0.7
        analysis = f"Moderate corroboration: {len(similar_reports)} similar reports"
    else:
        score = 0.3
        analysis = "No corroborating reports found"
    
    return {'score': score, 'analysis': analysis}

def analyze_media(report):
    """Analyze uploaded media using AI"""
    try:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], report.image_file)
        
        # Basic check if file exists and is valid
        if not os.path.exists(image_path):
            return {'score': 0.3, 'analysis': 'Media file not available for analysis'}
        
        # For demo purposes - simulate AI analysis
        # In production, integrate with Google Vision AI, AWS Rekognition, etc.
        
        # Simulate different analysis based on hazard type
        hazard_analysis = {
            'tsunami': {'score': 0.7, 'analysis': 'Image shows large wave patterns consistent with tsunami warnings'},
            'storm_surge': {'score': 0.8, 'analysis': 'Weather patterns and water levels indicate potential storm surge'},
            'high_waves': {'score': 0.6, 'analysis': 'Wave height appears elevated compared to normal conditions'},
            'oil_spill': {'score': 0.9, 'analysis': 'Visual patterns consistent with oil slick formation'},
        }
        
        result = hazard_analysis.get(report.hazard_type, {'score': 0.5, 'analysis': 'Media appears relevant to reported hazard type'})
        return result
        
    except Exception as e:
        print(f"Media analysis error: {e}")
        return {'score': 0.3, 'analysis': 'Media analysis failed'}

def analyze_text(description, title):
    """Analyze text content for urgency and credibility"""
    text = f"{title} {description}".lower()
    
    # Keywords indicating urgency/first-hand observation
    urgency_keywords = ['just saw', 'right now', 'currently', 'urgent', 'emergency', 
                       'witness', 'observed', 'seeing', 'happening now', 'personal observation']
    
    # Keywords indicating hearsay/uncertainty
    uncertainty_keywords = ['heard', 'maybe', 'possibly', 'might', 'could be', 
                           'someone said', 'rumor', 'not sure', 'probably', 'think']
    
    urgency_count = sum(1 for word in urgency_keywords if word in text)
    uncertainty_count = sum(1 for word in uncertainty_keywords if word in text)
    
    if urgency_count > 1 and uncertainty_count == 0:
        score = 0.8
        analysis = "High urgency: First-hand observation language detected"
    elif urgency_count > 0:
        score = 0.6
        analysis = "Moderate urgency: Some urgent language detected"
    elif uncertainty_count > 0:
        score = 0.3
        analysis = "Low urgency: Hearsay or uncertain language detected"
    else:
        score = 0.5
        analysis = "Neutral: Standard reporting language"
    
    return {'score': score, 'analysis': analysis}

def delete_scheduled_reports():
    """Delete reports that are scheduled for deletion and past their deletion time"""
    with app.app_context():
        try:
            reports_to_delete = Report.query.filter(
                Report.scheduled_deletion.isnot(None),
                Report.scheduled_deletion <= datetime.utcnow()
            ).all()
            
            deleted_count = 0
            for report in reports_to_delete:
                # Delete associated media files
                if report.image_file:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], report.image_file))
                    except:
                        pass
                
                if report.video_file:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], report.video_file))
                    except:
                        pass
                
                # Delete the report
                db.session.delete(report)
                deleted_count += 1
            
            if deleted_count > 0:
                db.session.commit()
                print(f"Deleted {deleted_count} scheduled reports at {datetime.utcnow()}")
                
        except Exception as e:
            print(f"Error in scheduled deletion: {e}")

# Schedule the deletion task to run every 30 minutes
scheduler.add_job(
    func=delete_scheduled_reports,
    trigger=IntervalTrigger(minutes=30),
    id='delete_scheduled_reports',
    name='Delete scheduled reports every 30 minutes',
    replace_existing=True
)

# Notification System Functions
@app.route('/api/notifications')
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).order_by(Notification.created_at.desc()).all()
    
    notifications_data = []
    for notification in notifications:
        time_remaining = None
        if notification.expires_at:
            time_remaining = max(0, (notification.expires_at - datetime.utcnow()).total_seconds())
        
        notifications_data.append({
            'id': notification.id,
            'message': notification.message,
            'report_id': notification.report_id,
            'created_at': notification.created_at.isoformat(),
            'expires_at': notification.expires_at.isoformat() if notification.expires_at else None,
            'time_remaining': time_remaining
        })
    
    return jsonify(notifications_data)

@app.route('/api/notification/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': 'Notification marked as read',
            'notification_id': notification_id
        })
    
    # For regular form submissions, redirect
    return redirect(url_for('notifications'))

@app.route("/")
@app.route("/home")
def home():
    # Get recent reports for homepage
    reports = Report.query.order_by(Report.timestamp.desc()).limit(3).all()
    
    # If no reports, use sample data
    if not reports:
        sample_with_datetime = []
        for report in sample_reports[:3]:
            report_copy = report.copy()
            report_copy['timestamp'] = datetime.strptime(report['timestamp'], '%Y-%m-%d %H:%M:%S')
            sample_with_datetime.append(report_copy)
        reports = sample_with_datetime
    
    return render_template('index.html', reports=reports)

@app.route("/about")
def about():
    return render_template('about.html', title=translate('about'))

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Detect language based on location if provided in form
        preferred_lang = 'en'
        
        # If location data is provided in registration, use it for language detection
        if hasattr(form, 'latitude') and form.latitude.data and hasattr(form, 'longitude') and form.longitude.data:
            preferred_lang = detect_preferred_language(form.latitude.data, form.longitude.data)
            print(f"🌍 Detected language for new user: {preferred_lang}")
        
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user = User(
            username=form.username.data.strip(), 
            email=form.email.data, 
            password=hashed_password,
            role='citizen',
            language=preferred_lang  # Set detected language
        )
        db.session.add(user)
        db.session.commit()
        
        flash(translate('registration_success'), 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', title=translate('register'), form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash(translate('login_success'), 'info')
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            
            # Welcome message based on user role
            if user.role == 'official':
                flash(translate('official_login'), 'success')
            elif user.role == 'analyst':
                flash(translate('analyst_login'), 'success')
            else:
                flash(translate('login_success'), 'success')
            
            # Check for new notifications or achievements
            check_and_notify_user(user)
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    
    return render_template('login.html', title=translate('login'), form=form)

def check_and_notify_user(user):
    """Check for new notifications and achievements to display to user"""
    # Get the comparison timestamp first
    comparison_time = user.last_login if hasattr(user, 'last_login') and user.last_login else datetime.utcnow()
    
    # Check for new approved reports
    new_approved = Report.query.filter(
        Report.user_id == user.id,
        Report.verification_status == 'approved',
        Report.verified_at >= comparison_time
    ).count()
    
    if new_approved > 0:
        flash(f'🎉 Great news! {new_approved} of your reports have been approved by officials!', 'success')
    
    # Check for new rejected reports
    new_rejected = Report.query.filter(
        Report.user_id == user.id,
        Report.verification_status == 'rejected',
        Report.verified_at >= comparison_time
    ).count()
    
    if new_rejected > 0:
        flash(f'⚠️ {new_rejected} of your reports were rejected. Check notifications for details.', 'warning')
    
    # Check for new badges earned
    new_badges = UserBadge.query.filter(
        UserBadge.user_id == user.id,
        UserBadge.earned_at >= comparison_time
    ).count()
    
    if new_badges > 0:
        flash(f'🏆 Congratulations! You earned {new_badges} new badge(s)!', 'success')
    
    # Update last login time if the field exists
    if hasattr(user, 'last_login'):
        user.last_login = datetime.utcnow()
        db.session.commit()

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/profile/<username>")
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    reports = Report.query.filter_by(user_id=user.id).order_by(Report.timestamp.desc()).all()
    
    # Calculate stats
    total_reports = len(reports)
    verified_reports = sum(1 for report in reports if report.verification_status == 'approved')
    pending_reports = sum(1 for report in reports if report.verification_status == 'pending')
    rejected_reports = sum(1 for report in reports if report.verification_status == 'rejected')
    total_points = user.points
    
    # Calculate volunteer stats if applicable
    volunteer = Volunteer.query.filter_by(user_id=user.id).first()
    completed_rescues = 0
    if volunteer:
        completed_rescues = VolunteerAssignment.query.filter_by(
            volunteer_id=volunteer.id, 
            status='completed'
        ).count()
        
    return render_template('profile.html', 
                         title=f'{user.username} Profile',
                         user=user,
                         reports=reports,
                         total_reports=total_reports,
                         verified_reports=verified_reports,
                         pending_reports=pending_reports,
                         rejected_reports=rejected_reports,
                         total_points=total_points,
                         completed_rescues=completed_rescues)

@app.route("/edit_profile", methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(original_username=current_user.username)
    
    if form.validate_on_submit():
        if form.profile_image.data:
            filename = save_file(form.profile_image.data)
            current_user.profile_image = filename
        
        current_user.username = form.username.data
        current_user.bio = form.bio.data
        db.session.commit()
        
        flash(translate('profile_updated'), 'success')
        return redirect(url_for('profile', username=current_user.username))
    
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.bio.data = current_user.bio
    
    return render_template('edit_profile.html', title=translate('edit'), form=form)

@app.route("/follow/<username>")
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(translate('user_not_found'), 'danger')
        return redirect(url_for('home'))
    
    if user == current_user:
        flash('You cannot follow yourself!', 'danger')
        return redirect(url_for('profile', username=username))
    
    current_user.follow(user)
    db.session.commit()
    flash(translate('follow_success', username=username), 'success')
    return redirect(url_for('profile', username=username))

@app.route("/unfollow/<username>")
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(translate('user_not_found'), 'danger')
        return redirect(url_for('home'))
    
    current_user.unfollow(user)
    db.session.commit()
    flash(translate('unfollow_success', username=username), 'success')
    return redirect(url_for('profile', username=username))

@app.route("/user_followers/<username>")
@login_required
def user_followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    followers_list = user.followers.paginate(page=page, per_page=20, error_out=False)
    return render_template('user_followers.html', user=user, followers=followers_list)

@app.route("/user_following/<username>")
@login_required
def user_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    following_list = user.followed.paginate(page=page, per_page=20, error_out=False)
    return render_template('user_following.html', user=user, following=following_list)

@app.route("/rescue-complete")
@login_required
def rescue_complete():
    """Page for volunteers to mark rescue as complete with photo proof"""
    assignment_id = request.args.get('assignment_id', type=int)
    
    if not assignment_id:
        flash('Assignment ID is required', 'danger')
        return redirect(url_for('notifications'))
    
    assignment = VolunteerAssignment.query.get_or_404(assignment_id)
    
    # Check that current user is the assigned volunteer
    if assignment.volunteer.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check that assignment is accepted
    if assignment.status != 'accepted':
        flash('Assignment must be accepted to complete', 'danger')
        return redirect(url_for('notifications'))
    
    return render_template('rescue_completion.html', title='Mark Rescue Complete', assignment=assignment, assignment_id=assignment_id)

@app.route("/leaderboards")
@login_required
def leaderboards():
    """Unified Leaderboards - Community, Rescue Heroes, and Eco"""
    return render_template('leaderboards.html', title=translate('leaderboard'))

@app.route("/leaderboard")
def leaderboard():
    # Get top users by points
    top_users = User.query.order_by(User.points.desc()).limit(20).all()
    return render_template('leaderboard.html', title=translate('leaderboard'), top_users=top_users)

@app.route("/community_leaderboard")
@login_required
def community_leaderboard():
    """Community Leaderboard - All users ranked by total combined points"""
    return render_template('community_leaderboard.html', title=translate('leaderboard'))

@app.route("/certificate/<int:user_id>")
@login_required
def view_certificate(user_id):
    user = User.query.get_or_404(user_id)
    
    # Logic for certification eligibility
    # Must have points >= 2000
    volunteer = Volunteer.query.filter_by(user_id=user.id).first()
    completed_rescues = 0
    if volunteer:
        completed_rescues = VolunteerAssignment.query.filter_by(
            volunteer_id=volunteer.id, 
            status='completed'
        ).count()
        
    is_eligible = (user.points >= 500)
    
    if not is_eligible and current_user.id == user.id:
        flash("You need 500 points to unlock your Government Certificate. Keep going!", "info")
        return redirect(url_for('profile', username=user.username))
    elif not is_eligible:
        flash("This user is not yet eligible for certification.", "warning")
        return redirect(url_for('profile', username=user.username))
        
    return render_template('certificate_view.html', 
                          user=user, 
                          completed_rescues=completed_rescues,
                          date=datetime.utcnow().strftime('%B %d, %Y'),
                          cert_id=f"SH-CRT-{user.id}-{datetime.utcnow().strftime('%Y%m%d')}")

@app.route("/certificate/download/<int:user_id>")
@login_required
def download_certificate(user_id):
    """Render a beautiful printable certificate page for eligible users"""
    user = User.query.get_or_404(user_id)
    
    # Only allow the user themselves or admins
    if current_user.id != user.id and not current_user.is_admin:
        flash("You can only download your own certificate.", "danger")
        return redirect(url_for('leaderboards'))
    
    if user.points < 500:
        flash("You need 500 points to download your Government Certificate!", "warning")
        return redirect(url_for('leaderboards'))
    
    volunteer = Volunteer.query.filter_by(user_id=user.id).first()
    completed_rescues = 0
    if volunteer:
        completed_rescues = VolunteerAssignment.query.filter_by(
            volunteer_id=volunteer.id,
            status='completed'
        ).count()
    
    return render_template('certificate_download.html',
                           user=user,
                           completed_rescues=completed_rescues,
                           date=datetime.utcnow().strftime('%B %d, %Y'),
                           cert_id=f"MAXALERT-{user.id}-{datetime.utcnow().strftime('%Y%m%d')}",
                           points=user.points)

@app.route("/report", methods=['GET', 'POST'])
@login_required
def report():
    form = ReportForm()
    if form.validate_on_submit():
        # Handle file uploads
        image_filename = save_file(form.photo.data) if form.photo.data else None
        video_filename = save_file(form.video.data) if form.video.data else None
        
        report = Report(
            title=form.title.data, 
            description=form.description.data,
            hazard_type=form.hazard_type.data,
            location=form.location.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            image_file=image_filename,
            video_file=video_filename,
            author=current_user,
            status='active',
            priority='critical' if form.hazard_type.data == 'tsunami' else 'high' if form.hazard_type.data in ['storm_surge', 'earthquake'] else 'medium'
        )
        
        # Run AI analysis on the new report
        ai_result = analyze_report_with_ai(report)
        report.confidence_score = ai_result['confidence_score']
        report.ai_analysis = ai_result['analysis']
        
        # --- AI AUTO-APPROVAL SYSTEM (SH-SVA-03) ---
        # Automatically approve reports with extremely high confidence (>= 85%)
        is_auto_approved = False
        if report.confidence_score >= 0.85:
            report.verification_status = 'approved'
            report.verified = True
            report.verified_at = datetime.utcnow()
            # Set a high priority since AI is very certain
            report.priority = 'critical'
            is_auto_approved = True
            
            # Auto-assign initial points for verified reporting
            current_user.points += 20 # 10 base + 20 bonus for verified report
            
            # Create notification for the reporter
            db.session.add(Notification(
                user_id=current_user.id,
                message=f'🚀 AI AUTO-APPROVED: Your report "{report.title}" was verified instantly. +30 points total rewarded!',
                report_id=report.id
            ))
        else:
            # Standard points for reporting
            current_user.points += 10
            
        db.session.add(report)
        check_and_award_badges(current_user)
        db.session.commit()
        
        # Sync to CSV for real-time persistence
        sync_reports_to_csv(Report)
        
        # Trigger INSTANT alerts for auto-approved reports (Pulse of the City)
        if is_auto_approved:
            print(f"⚡ AUTO-DEPLOY: Triggering instant alerts for highly reliable hazard (Confidence: {report.confidence_score*100:.1f}%)")
            # Auto-assign volunteers within 10km (Pulse of the coordination engine)
            send_hazard_alerts(report, auto_assign_volunteers=True)
        
        # Show AI confidence in flash message with 3-parameter breakdown
        confidence_percent = report.confidence_score * 100
        if is_auto_approved:
            flash(f"🛡️ AUTO-VERIFIED: {translate('report_submitted', confidence=int(confidence_percent))} (Status: APPROVED)", "success")
        elif ai_result.get('accuracy_3param'):
            param_breakdown = f" [Heatmap: {int(ai_result['accuracy_3param']['parameter_1_heatmap']['score']*100)}% | Climate: {int(ai_result['accuracy_3param']['parameter_2_climate']['score']*100)}% | User: {int(ai_result['accuracy_3param']['parameter_3_user_quality']['score']*100)}%]"
            flash(f"{translate('report_submitted', confidence=int(confidence_percent))}{param_breakdown}", 'success')
        else:
            flash(translate('report_submitted', confidence=int(confidence_percent)), 'success')
        return redirect(url_for('home'))
    
    return render_template('report.html', title=translate('report'), form=form)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    upload_folder = os.path.join(os.path.dirname(__file__), app.config['UPLOAD_FOLDER'])
    return send_from_directory(upload_folder, filename)

@app.route("/get_location")
def get_location():
    return jsonify({'status': 'success'})

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to access the dashboard.', 'warning')
        return redirect(url_for('home'))
    
    reports = Report.query.order_by(Report.timestamp.desc()).all()
    
    # Statistics for dashboard
    total_reports = len(reports)
    pending_reports = sum(1 for r in reports if r.verification_status == 'pending')
    approved_reports = sum(1 for r in reports if r.verification_status == 'approved')
    rejected_reports = sum(1 for r in reports if r.verification_status == 'rejected')
    high_confidence_reports = sum(1 for r in reports if r.confidence_score >= 0.8)
    
    # New statistics requested
    reports_with_media = sum(1 for r in reports if r.image_file or r.video_file)
    
    # Calculate top hazard type
    hazard_counts = {}
    for r in reports:
        hazard_counts[r.hazard_type] = hazard_counts.get(r.hazard_type, 0) + 1
    
    top_hazard_type = "None"
    top_hazard_count = 0
    if hazard_counts:
        top_hazard_type = max(hazard_counts, key=hazard_counts.get)
        top_hazard_count = hazard_counts[top_hazard_type]
    
    report_data = []
    for report in reports:
        report_data.append({
            'id': report.id,
            'title': report.title,
            'description': report.description,
            'hazard_type': report.hazard_type,
            'location': report.location,
            'latitude': float(report.latitude),
            'longitude': float(report.longitude),
            'image_file': report.image_file,
            'video_file': report.video_file,
            'timestamp': report.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'author': report.author.username,
            'confidence_score': report.confidence_score,
            'verification_status': report.verification_status,
            'ai_analysis': report.ai_analysis,
            'status': report.status or 'active',
            'priority': report.priority or 'medium'
        })
    
    if not report_data:
        report_data = sample_reports
    
    return render_template('dashboard.html', 
                         title=translate('dashboard'), 
                         reports=report_data,
                         total_reports=total_reports,
                         pending_reports=pending_reports,
                         approved_reports=approved_reports,
                         rejected_reports=rejected_reports,
                         high_confidence_reports=high_confidence_reports,
                         reports_with_media=reports_with_media,
                         top_hazard_type=top_hazard_type,
                         top_hazard_count=top_hazard_count)

@app.route("/api/reports")
def api_reports():
    reports = Report.query.order_by(Report.timestamp.desc()).all() or sample_reports
    report_data = []
    for report in reports:
        report_data.append({
            'id': report.id,
            'title': report.title,
            'hazard_type': report.hazard_type,
            'location': report.location,
            'latitude': report.latitude,
            'longitude': report.longitude,
            'image_file': report.image_file,
            'video_file': report.video_file,
            'timestamp': report.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'author': report.author.username,
            'confidence_score': report.confidence_score,
            'verification_status': report.verification_status
        })
    return jsonify(report_data)

@app.route("/view_report/<int:report_id>")
@login_required
def view_report(report_id):
    report = Report.query.get_or_404(report_id)
    return render_template('view_report.html', 
                         title='Report Details', 
                         report=report)

# Hazard type alert radii (in kilometers)
HAZARD_ALERT_RADII = {
    'tsunami': 15.0,        # 15 km radius for tsunamis
    'storm_surge': 15.0,    # 15 km radius for storm surges  
    'high_waves': 10.0,      # 10 km radius for high waves
    'swell_surge': 10.0,     # 10 km radius for swell surges
    'coastal_flooding': 10.0, # 10 km radius for coastal flooding
    'abnormal_tide': 10.0,   # 10 km radius for abnormal tides
    'other': 10.0            # 10 km radius for other hazards
}

@app.route('/verify_report/<int:report_id>', methods=['POST'])
@login_required
def verify_report(report_id):
    print(f"🔍 verify_report called for report {report_id} by user {current_user.username}")
    
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to verify reports.', 'warning')
        return redirect(url_for('view_report', report_id=report_id))
    
    report = Report.query.get_or_404(report_id)
    action = request.form.get('action')
    print(f"📋 Action: {action} for report '{report.title}' (Hazard: {report.hazard_type})")
    
    if action == 'approve':
        report.verification_status = 'approved'
        report.verified_by = current_user.id
        report.verified_at = datetime.utcnow()
        report.scheduled_deletion = None
        report.verified = True
        
        # Set alert radius based on hazard type
        report.alert_radius = HAZARD_ALERT_RADII.get(report.hazard_type, 5.0)
        print(f"📏 Alert radius set to {report.alert_radius}km for {report.hazard_type}")
        
        # Award extra points for verified report
        report.author.points += 20
        check_and_award_badges(report.author)
        print(f"⭐ Awarded 20 points to {report.author.username}")
        
        # Create notification for the report author
        author_notification = Notification(
            user_id=report.user_id,
            message=f'🎉 Your report "{report.title}" has been approved by an official! +20 points awarded!',
            report_id=report.id
        )
        db.session.add(author_notification)
        print(f"📨 Created approval notification for report author")
        
        db.session.commit()
        print("💾 Approval changes committed")
        
        flash(f'Report "{report.title}" has been approved successfully!', 'success')
        
        # --- UNIFIED ALERTING & AUTOMATION ---
        # This sends alerts to all users in the radius and auto-assigns nearby volunteers
        print(f"🚀 Triggering unified alerts and assignments for report: {report.title}")
        try:
            users_alerted = send_hazard_alerts(report, auto_assign_volunteers=True, assigner_id=current_user.id)
            print(f"✅ Unified alerting completed. Total users reached: {users_alerted}")
            
            # Flash status message based on results
            if users_alerted > 0:
                flash(f'✅ Report verified! Alerts sent to {users_alerted} users via WhatsApp.', 'success')
            else:
                flash(f'⚠️ Report verified, but no WhatsApp alerts could be delivered. Ensure users have active sessions by messaging "hi" to the bot.', 'warning')
            
        except Exception as e:
            db.session.rollback()
            print(f"[ALERT ERROR] Failed to complete unified alerting: {e}")
            flash('Verification successful, but there was an error sending automated alerts.', 'warning')
        # --- END UNIFIED ALERTING ---
        
        db.session.commit()
        print("💾 Database changes committed and alerts sent")
        
    elif action == 'resolve':
        report.status = 'resolved'
        db.session.commit()
        flash(f'Report "{report.title}" has been marked as resolved.', 'success')
        return redirect(url_for('dashboard'))
        
    elif action == 'reject':
        print("🔄 Processing rejection...")
        
        # Get form data
        rejection_reason = request.form.get('rejection_reason', 'No reason provided')
        schedule_deletion = 'schedule_deletion' in request.form
        notify_user = 'notify_user' in request.form
        
        print(f"📝 Rejection reason: {rejection_reason}")
        print(f"🗑️ Schedule deletion: {schedule_deletion}")
        print(f"🔔 Notify user: {notify_user}")
        
        # Update report status
        report.verification_status = 'rejected'
        report.verified_by = current_user.id
        report.verified_at = datetime.utcnow()
        report.rejection_reason = rejection_reason
        report.verified = False
        
        # Handle deletion scheduling
        if schedule_deletion:
            # Schedule for deletion in 24 hours (not 7 days as before)
            report.scheduled_deletion = datetime.utcnow() + timedelta(hours=24)
            print(f"⏰ Scheduled for deletion at: {report.scheduled_deletion}")
        else:
            report.scheduled_deletion = None
            print("⏰ No deletion scheduled")
        
        # Create notification for the report author if requested
        if notify_user:
            author_notification = Notification(
                user_id=report.user_id,
                message=f'⚠️ Your report "{report.title}" was rejected. Reason: {rejection_reason}',
                report_id=report.id,
                expires_at=report.scheduled_deletion if schedule_deletion else None
            )
            db.session.add(author_notification)
            print(f"📨 Created rejection notification for report author")
        else:
            print("🔕 No notification sent to user")
        
        db.session.commit()
        print("💾 Rejection changes committed")
        
        flash('Report rejected successfully.', 'success')
        
    elif action == 'pending':
        print("🔄 Returning report to pending status...")
        
        # Reset verification status
        report.verification_status = 'pending'
        report.verified_by = None
        report.verified_at = None
        report.rejection_reason = None
        report.scheduled_deletion = None
        report.verified = False
        
        db.session.commit()
        print("💾 Pending status changes committed")
        
        flash('Report returned to pending status.', 'success')
    
    else:
        print(f"❌ Unknown action: {action}")
        flash('Invalid action.', 'error')
    
    return redirect(url_for('view_report', report_id=report_id))

def send_hazard_alerts(report, auto_assign_volunteers=False, assigner_id=None):
    """
    Unified pass to alert citizens and assign nearby volunteers.
    """
    # ALERT RADIUS UPDATE: Set to 5000km to effectively broadcast to ALL users for the demo
    # This ensures "all users should get the alert message" as requested
    hazard_radius = HAZARD_ALERT_RADII.get(report.hazard_type, 10.0)
    alert_radius = 5000.0 
    
    # The volunteer assignment radius is also 5000km for the demo
    max_radius = 5000.0
    
    print(f"🔔 BROADCAST: Hazard '{report.title}' ({report.hazard_type})")
    print(f"📏 Radii: Citizen={alert_radius}km, Volunteer=50.0km")
    
    # Get all users (we'll filter in Python to handle the complex fallback logic)
    users = User.query.all()
    
    # Setup media URL
    base_url = None
    try: base_url = request.url_root.rstrip('/')
    except: base_url = "http://localhost:5001"
    
    # Fallback for local testing to ensure WhatsApp links work
    is_local = any(x in base_url for x in ['localhost', '127.0.0.1', '192.168.'])
    if is_local:
        # Known public ngrok URL from NGROK_PUBLIC_ACCESS.md
        base_url = "https://adele-unfocused-scientistically.ngrok-free.dev"
        is_public_url = True
    else:
        is_public_url = True
    
    media_url = f"{base_url}/static/uploads/{report.image_file}" if report.image_file else None

    users_alerted = 0
    volunteers_assigned = 0
    
    for user in users:
        # Determine best location for this user
        u_lat, u_lon = user.home_latitude, user.home_longitude
        
        # Fallback to volunteer location if user location is missing
        volunteer = Volunteer.query.filter_by(user_id=user.id).first()
        if (u_lat is None or u_lon is None) and volunteer:
            u_lat, u_lon = volunteer.latitude, volunteer.longitude
            
        if u_lat is None or u_lon is None:
            # Only log for users with WhatsApp numbers to keep it clean
            if user.whatsapp_number:
                print(f"⏭️ Skipping {user.username} (missing coordinates)")
            continue
            
        distance = calculate_distance(report.latitude, report.longitude, u_lat, u_lon)
        
        # Check if user is in any zone of interest
        is_in_citizen_zone = distance <= alert_radius
        is_in_volunteer_zone = distance <= max_radius and volunteer is not None
        
        if not is_in_citizen_zone and not is_in_volunteer_zone:
            if user.whatsapp_number:
                print(f"📏 User {user.username} is too far ({distance:.1f}km)")
            continue
            
        print(f"🎯 User {user.username} is in range ({distance:.1f}km)!")
            
        is_nearby_volunteer = False
        assignment_id = None
        message_sid = None
        
        if auto_assign_volunteers and is_in_volunteer_zone:
            # Check for existing assignment
            existing = VolunteerAssignment.query.filter_by(
                volunteer_id=volunteer.id,
                emergency_event_id=report.id,
                hazard_type='report'
            ).filter(VolunteerAssignment.status.in_(['pending', 'accepted', 'deployed'])).first()
            
            if not existing:
                assignment = VolunteerAssignment(
                    volunteer_id=volunteer.id,
                    emergency_event_id=report.id,
                    hazard_type='report',
                    assigned_by=assigner_id,
                    status='pending',
                    distance_km=distance
                )
                db.session.add(assignment)
                db.session.flush()
                assignment_id = assignment.id
                is_nearby_volunteer = True
                volunteers_assigned += 1

        # We only send citizen alerts if they are in the zone AND have preferences enabled
        send_citizen_alert = is_in_citizen_zone
        if send_citizen_alert:
            user_prefs = user.get_alert_preferences()
            if not user_prefs.get(report.hazard_type, True):
                send_citizen_alert = False
        
        # If not volunteer and citizen alert disabled, skip
        if not is_nearby_volunteer and not send_citizen_alert:
            continue

        # 5. Construct Notification
        notif_msg = f"⚠️ Hazard alert near you! - {distance:.1f}km away"
        if is_nearby_volunteer:
            notif_msg = f"🤝 HELP REQUEST: You have been assigned to assist with verified hazard \"{report.title}\" ({distance:.1f}km away)."
            
        alert_notification = Notification(
            user_id=user.id,
            message=notif_msg,
            report_id=report.id,
            assignment_id=assignment_id,
            is_alert=True
        )
        db.session.add(alert_notification)

        # 6. Send WhatsApp
        # 6. Send WhatsApp
        if user.whatsapp_number:
            # We send the full hazard details (text + picture) to both citizens AND volunteers
            # so volunteers have full context (photo + details) before they accept the mission.
            should_send_details = send_citizen_alert or is_nearby_volunteer
            
            main_sid = None
            if should_send_details:
                alert_body = (
                    f"🚨 *Sentinel AI: HAZARD ALERT*\n\n"
                    f"⚠️ *{report.hazard_type.upper().replace('_', ' ')} ALERT*\n"
                    f"A hazard has been verified {distance:.1f}km from your location.\n\n"
                    f"📝 *Title:* {report.title}\n"
                    f"ℹ️ *Details:* {report.description[:400] + '...' if len(report.description) > 400 else report.description}\n"
                    f"📍 *Location:* {report.location}\n\n"
                    f"🔗 *Dashboard:* {base_url}/dashboard\n\n"
                    f"Stay safe! 🛡️"
                )
                # NEW: Combined message (Image + Text) for better UX and reliability
                # Add ngrok bypass to ensure Twilio can fetch the image through the tunnel
                bypass = "?ngrok-skip-browser-warning=true"
                media_link = f"{base_url}/static/uploads/{report.image_file}{bypass}" if report.image_file else None
                
                # Send the alert with image attached
                main_sid = send_whatsapp_message(user.whatsapp_number, alert_body, media_url=media_link)
                
                if not main_sid:
                    # Fallback: try sending without image if combined message fails
                    print("⚠️ Combined message failed, trying text-only fallback...")
                    main_sid = send_whatsapp_message(user.whatsapp_number, alert_body)

            # Send the Volunteer Mission / Help Request
            if is_nearby_volunteer:
                mission_body = (
                    f"🤝 *Sentinel AI: HELP REQUEST*\n\n"
                    f"You have been assigned to assist with this hazard ({distance:.1f}km away).\n"
                    f"Your help is vital! Please review the details above.\n\n"
                    f"*Action REQUIRED:* Reply with:\n"
                    f"1️⃣ to *Accept & Get Location*\n"
                    f"2️⃣ to *Reject*"
                )
                v_sid = send_whatsapp_message(user.whatsapp_number, mission_body)
                if not main_sid: main_sid = v_sid
                
            if main_sid:
                users_alerted += 1
                print(f"📤 Notified {user.username} ({distance:.1f}km) {'(Citizen + Volunteer)' if (send_citizen_alert and is_nearby_volunteer) else '(Alert Only)' if send_citizen_alert else '(Mission Only)'}")
            else:
                print(f"❌ Failed to notify {user.username}. They may need to restart their sandbox session (send 'hi').")

    report.alert_sent = True
    report.alert_sent_at = datetime.utcnow()
    db.session.commit()
    return users_alerted

@app.route('/delete_report/<int:report_id>', methods=['POST'])
@login_required
def delete_report(report_id):
    report = Report.query.get_or_404(report_id)
    
    # Check if user owns the report or is admin
    if report.user_id != current_user.id and current_user.role not in ['official', 'analyst']:
        flash('You can only delete your own reports.', 'danger')
        return redirect(url_for('view_report', report_id=report_id))
    
    # Delete associated media files
    if report.image_file:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], report.image_file))
        except:
            pass
    
    if report.video_file:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], report.video_file))
        except:
            pass
    
    # Delete the report
    # Manually delete related VolunteerAssignments since they use a shared ID field
    VolunteerAssignment.query.filter_by(emergency_event_id=report.id, hazard_type='report').delete()
    
    db.session.delete(report)
    db.session.commit()
    
    # Sync to CSV for real-time persistence
    sync_reports_to_csv(Report)
    
    flash('Report deleted successfully.', 'success')
    
    if current_user.role in ['official', 'analyst']:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('profile', username=current_user.username))

@app.route('/cancel_deletion/<int:report_id>', methods=['POST'])
@login_required
def cancel_deletion(report_id):
    report = Report.query.get_or_404(report_id)
    
    # Check if user owns the report or is admin
    if report.user_id != current_user.id and current_user.role not in ['official', 'analyst']:
        flash('You can only modify your own reports.', 'danger')
        return redirect(url_for('view_report', report_id=report_id))
    
    report.scheduled_deletion = None
    
    # Also mark any related notifications as read
    Notification.query.filter_by(
        report_id=report_id, 
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    flash('Scheduled deletion cancelled.', 'success')
    return redirect(url_for('view_report', report_id=report_id))

@app.errorhandler(413)
def too_large(e):
    flash(translate('file_too_large'), 'danger')
    return redirect(request.url)

@app.route('/repair-database-2026')
def repair_database():
    """Drops old tables and creates new ones with correct column lengths"""
    try:
        db.drop_all()
        db.create_all()
        return '''
        <div style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #4CAF50;">✅ Database Repaired!</h1>
            <p>Old small tables deleted. New large tables created successfully.</p>
            <p>Now go to: <a href="/create-official-account">Create Official Account</a></p>
        </div>
        '''
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/create-official-account')
def create_official_account():
    existing_user = User.query.filter_by(email='varunmax9989@gmail.com').first()
    if existing_user:
        existing_user.role = 'official'
        existing_user.password = generate_password_hash('Rvarun9989@', method='pbkdf2:sha256')
        db.session.commit()
        msg = "Existing account upgraded to Official."
    else:
        # Create new official user
        new_user = User(
            username='varunmax7', 
            email='varunmax9989@gmail.com',
            password=generate_password_hash('Rvarun9989@', method='pbkdf2:sha256'),
            role='official'
        )
        db.session.add(new_user)
        db.session.commit()
        msg = "New Official account created successfully."

    return f'''
    <div style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #2196F3;">🛡️ Official Account System</h1>
        <p style="font-size: 18px;">{msg}</p>
        <p>You can now login at <a href="{url_for('login')}">Login Page</a></p>
        <div style="margin-top: 20px; color: #666;">
            <strong>Email:</strong> varunmax9989@gmail.com<br>
            <strong>Role:</strong> Official
        </div>
    </div>
    '''



@app.route('/check-users')
def check_users():
    users = User.query.all()
    user_list = []
    for user in users:
        user_list.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'points': user.points,
            'level': user.level,
            'language': user.language
        })
    return jsonify(user_list)

@app.route('/force-logout')
def force_logout():
    logout_user()
    flash('You have been logged out. Please log in with official credentials.', 'info')
    return redirect(url_for('login'))

@app.route('/elevate-user/<email>/<role>')
def elevate_user(email, role):
    if role not in ['citizen', 'official', 'analyst']:
        return 'Invalid role. Use citizen, official, or analyst.'
    
    user = User.query.filter_by(email=email).first()
    if user:
        user.role = role
        db.session.commit()
        return f'User {email} elevated to {role} role successfully!'
    return f'User with email {email} not found.'

@app.route("/share")
def share_app():
    app_url = request.url_root.rstrip('/')
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Share App</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body text-center">
                            <h3>🌊 Share Ocean Hazard App</h3>
                            <p>Copy this link and send it to friends:</p>
                            
                            <div class="input-group mb-3">
                                <input type="text" class="form-control" id="appLink" 
                                       value="{app_url}" readonly>
                                <button class="btn btn-primary" onclick="copyLink()">
                                    Copy
                                </button>
                            </div>
                            
                            <a href="/" class="btn btn-secondary">Back to Home</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        function copyLink() {{
            const linkInput = document.getElementById('appLink');
            linkInput.select();
            document.execCommand('copy');
            alert('✅ Link copied! Send this to your friends: {app_url}');
        }}
        </script>
    </body>
    </html>
    '''

@app.route("/search")
@login_required
def search():
    query = request.args.get('q', '')
    return render_template('search.html', title=translate('search'), query=query)

@app.route("/api/search")
@login_required
def api_search():
    query = request.args.get('q', '').strip().lower()
    
    results = {
        'users': [],
        'reports': [],
        'trending_hazards': []
    }
    
    # Search users
    if query:
        users = User.query.filter(
            (User.username.ilike(f'%{query}%')) | 
            (User.email.ilike(f'%{query}%'))
        ).limit(5).all()
        results['users'] = [user.to_dict() for user in users]
    
    # Search reports
    if query:
        reports = Report.query.filter(
            (Report.title.ilike(f'%{query}%')) | 
            (Report.location.ilike(f'%{query}%')) |
            (Report.hazard_type.ilike(f'%{query}%')) |
            (Report.description.ilike(f'%{query}%'))
        ).limit(10).all()
        results['reports'] = [report.to_dict() for report in reports]
    
    # Get trending hazards (most common hazard types)
    trending_hazards = get_trending_hazards(query)
    results['trending_hazards'] = trending_hazards
    
    return jsonify(results)

def get_trending_hazards(query=None):
    # Get most common hazard types from recent reports
    trending = db.session.query(
        Report.hazard_type,
        func.count(Report.id).label('count')
    ).group_by(Report.hazard_type).order_by(func.count(Report.id).desc()).limit(5).all()
    
    hazards = []
    for hazard_type, count in trending:
        if not query or query.lower() in hazard_type.lower():
            hazards.append({
                'name': hazard_type,
                'count': count,
                'icon': get_hazard_icon(hazard_type)
            })
    
    return hazards

def get_hazard_icon(hazard_type):
    icons = {
        'tsunami': '🌊',
        'storm_surge': '⛈️',
        'high_waves': '🌊',
        'swell_surge': '🌊',
        'coastal_flooding': '🌧️',
        'abnormal_tide': '🌕',
        'other': '⚠️'
    }
    return icons.get(hazard_type, '⚠️')

@app.route("/reels")
def reels():
    """Instagram Reels-style report viewing - accessible to everyone"""
    reports = Report.query.order_by(Report.timestamp.desc()).all()
    
    # Get IDs of reports the current user has locally approved (if authenticated)
    user_locally_approved_reports = []
    if current_user.is_authenticated:
        user_approvals = LocalApproval.query.filter_by(user_id=current_user.id).all()
        user_locally_approved_reports = [appr.report_id for appr in user_approvals]
    
    return render_template('reels.html', 
                         title=translate('reels'), 
                         reports=reports,
                         user_locally_approved_reports=user_locally_approved_reports)

@app.route("/api/report/<int:report_id>/local_approve", methods=['POST'])
@login_required
def local_approve(report_id):
    """Locally approve/unapprove a report"""
    report = Report.query.get_or_404(report_id)
    user_id = current_user.id
    
    # Check proximity (must be within 10km to be a "local")
    is_local = False
    if current_user.home_latitude and current_user.home_longitude:
        dist = calculate_distance(current_user.home_latitude, current_user.home_longitude, 
                                 report.latitude, report.longitude)
        if dist <= 10:  # 10km radius
            is_local = True
    
    # Check if user already approved this report
    existing_appr = LocalApproval.query.filter_by(user_id=user_id, report_id=report_id).first()
    
    if existing_appr:
        # Remove approval
        db.session.delete(existing_appr)
        liked = False
    else:
        # Add new approval
        new_appr = LocalApproval(user_id=user_id, report_id=report_id)
        db.session.add(new_appr)
        liked = True
        
    db.session.commit()
    
    # Count total local approvals (specifically from users within 10km)
    local_appr_count = 0
    all_approvals = LocalApproval.query.filter_by(report_id=report_id).all()
    
    for appr in all_approvals:
        if appr.user.home_latitude and appr.user.home_longitude:
            d = calculate_distance(appr.user.home_latitude, appr.user.home_longitude,
                                  report.latitude, report.longitude)
            if d <= 10:
                local_appr_count += 1
    
    # Auto-verify locally if threshold reached (e.g., 3 local people)
    if local_appr_count >= 3:
        report.is_local_verified = True
    else:
        report.is_local_verified = False
        
    db.session.commit()
    
    return jsonify({
        'approvals': len(all_approvals), 
        'local_approvals': local_appr_count,
        'approved': liked, 
        'is_local': is_local,
        'local_verified': report.is_local_verified
    })

@app.route("/api/report/<int:report_id>/view", methods=['POST'])
def view_report_item(report_id):
    """Increment view count for a report - uniquely per account"""
    report = Report.query.get_or_404(report_id)
    
    # If user is logged in, check for unique view
    if current_user.is_authenticated:
        existing_view = ReportView.query.filter_by(user_id=current_user.id, report_id=report_id).first()
        if not existing_view:
            # Create new view record
            new_view = ReportView(user_id=current_user.id, report_id=report_id)
            db.session.add(new_view)
            
            # Increment count
            report.views_count = (report.views_count or 0) + 1
            db.session.commit()
    else:
        # For non-logged in users, we just show the count without incrementing uniquely
        # unless you want to use IP/Session, but the user requested "for an account"
        pass
        
    return jsonify({'views': report.views_count or 0})

@app.route("/api/report/<int:report_id>/comment", methods=['POST'])
@login_required
def add_comment(report_id):
    """Add comment to a report"""
    report = Report.query.get_or_404(report_id)
    comment_text = request.json.get('comment', '').strip()
    
    if comment_text:
        # Create a new comment
        new_comment = Comment(
            user_id=current_user.id,
            report_id=report_id,
            text=comment_text
        )
        db.session.add(new_comment)
        report.comments_count = getattr(report, 'comments_count', 0) + 1
        db.session.commit()
    
    return jsonify({'comments': report.comments_count})

@app.route("/api/report/<int:report_id>/comments")
def get_comments(report_id):
    """Get all comments for a report"""
    report = Report.query.get_or_404(report_id)
    comments = Comment.query.filter_by(report_id=report_id).order_by(Comment.timestamp.desc()).all()
    
    comments_data = []
    for comment in comments:
        comments_data.append({
            'comment': comment.text,
            'author_username': comment.user.username,
            'author_profile_image': comment.user.profile_image,
            'timestamp': comment.timestamp.isoformat()
        })
        
    return jsonify(comments_data)

@app.route("/api/report/<int:report_id>/share", methods=['POST'])
@login_required
def share_report(report_id):
    """Share a report"""
    report = Report.query.get_or_404(report_id)
    report.shares_count = getattr(report, 'shares_count', 0) + 1
    db.session.commit()
    return jsonify({'shares': report.shares_count})

@app.route('/api/register_push_token', methods=['POST'])
@login_required
def register_push_token():
    token = request.json.get('token')
    if token:
        current_user.push_token = token
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route("/set_location", methods=['GET', 'POST'])
@login_required
def set_location():
    form = LocationForm()
    
    if form.validate_on_submit():
        current_user.home_latitude = form.home_latitude.data
        current_user.home_longitude = form.home_longitude.data
        
        # Auto-detect and update language based on new location
        if form.home_latitude.data and form.home_longitude.data:
            detected_lang = detect_preferred_language(
                form.home_latitude.data, 
                form.home_longitude.data
            )
            if detected_lang != current_user.language:
                current_user.language = detected_lang
                flash(f'Language auto-detected and set to {detected_lang.upper()} based on your location.', 'info')
        
        db.session.commit()
        flash(translate('location_saved'), 'success')
        return redirect(url_for('profile', username=current_user.username))
    
    elif request.method == 'GET':
        form.home_latitude.data = current_user.home_latitude
        form.home_longitude.data = current_user.home_longitude
    
    return render_template('set_location.html', title=translate('set_location'), form=form)

@app.route("/alert_preferences", methods=['GET', 'POST'])
@login_required
def alert_preferences():
    form = AlertPreferencesForm()
    
    if request.method == 'POST':
        # Update alert preferences
        preferences = {}
        for hazard_type in HAZARD_ALERT_RADII.keys():
            preferences[hazard_type] = request.form.get(hazard_type) == 'on'
        
        current_user.set_alert_preferences(preferences)
        db.session.commit()
        flash('Your alert preferences have been updated!', 'success')
        return redirect(url_for('profile', username=current_user.username))
    
    # Pre-populate form with current preferences for GET requests
    if request.method == 'GET':
        current_prefs = current_user.get_alert_preferences()
        # You'll need to set form data based on current_prefs
    
    return render_template('alert_preferences.html', 
                         title=translate('alert_preferences'), 
                         form=form,
                         hazard_types=HAZARD_ALERT_RADII)

@app.route("/notifications")
@login_required
def notifications():
    """Display unread notifications for the current user (by default)"""
    # Get query parameter to show all or only unread
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    
    if show_all:
        # Show all notifications (read and unread)
        user_notifications = Notification.query.filter_by(
            user_id=current_user.id
        ).order_by(Notification.created_at.desc()).all()
    else:
        # Show only unread notifications (default)
        user_notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).order_by(Notification.created_at.desc()).all()
    
    return render_template('notifications.html', 
                         title=translate('notifications'),
                         notifications=user_notifications,
                         show_all=show_all)

@app.route("/notification/<int:notification_id>/read", methods=['POST'])
@login_required
def mark_notification_read_web(notification_id):
    """Mark a notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        flash(translate('unauthorized'), 'danger')
        return redirect(url_for('notifications'))
    
    notification.is_read = True
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Notification marked as read.', 'success')
    return redirect(url_for('notifications'))

@app.route("/clear_all_notifications", methods=['POST'])
@login_required
def clear_all_notifications():
    """Clear all notifications for the current user"""
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    
    flash('All notifications cleared.', 'success')
    return redirect(url_for('notifications'))

@app.route("/api/notifications/unread-count")
@login_required
def unread_notifications_count():
    count = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).count()
    return jsonify({'count': count})

@app.route('/debug_users')
@login_required
def debug_users():
    """Debug page to check user locations and preferences"""
    if current_user.role not in ['official', 'analyst']:
        return "Unauthorized", 403
    
    users = User.query.all()
    user_data = []
    
    for user in users:
        user_data.append({
            'username': user.username,
            'location': f"({user.home_latitude}, {user.home_longitude})" if user.home_latitude else "Not set",
            'language': user.language,
            'alert_preferences': user.get_alert_preferences()
        })
    
    return render_template('debug_users.html', users=user_data)

@app.route('/user/<username>/reports')
def user_reports(username):
    """View all reports by a specific user"""
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    reports = Report.query.filter_by(author_id=user.id)\
        .order_by(Report.timestamp.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('user_reports.html', 
                         user=user, 
                         reports=reports)


@app.route("/analyst_dashboard")
@login_required
def analyst_dashboard():
    """Enhanced dashboard with weather data and analytics"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to access the analyst dashboard.', 'warning')
        return redirect(url_for('home'))
    
    reports = Report.query.order_by(Report.timestamp.desc()).all()
    
    # Statistics for dashboard
    total_reports = len(reports)
    pending_reports = sum(1 for r in reports if r.verification_status == 'pending')
    approved_reports = sum(1 for r in reports if r.verification_status == 'approved')
    rejected_reports = sum(1 for r in reports if r.verification_status == 'rejected')
    high_confidence_reports = sum(1 for r in reports if r.confidence_score >= 0.8)
    
    # Hazard type distribution
    hazard_counts = {}
    for report in reports:
        hazard_type = report.hazard_type
        hazard_counts[hazard_type] = hazard_counts.get(hazard_type, 0) + 1
    
    # Data for timeline chart (last 7 days)
    timeline_labels = []
    timeline_data = []
    
    # Get all reports from last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_reports_all = Report.query.filter(Report.timestamp >= seven_days_ago).all()
    
    # Group by date in Python for cross-DB compatibility
    counts_by_day = {}
    for r in recent_reports_all:
        d_str = r.timestamp.strftime('%Y-%m-%d')
        counts_by_day[d_str] = counts_by_day.get(d_str, 0) + 1
        
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        date_str = day.strftime('%Y-%m-%d')
        timeline_labels.append(day.strftime('%b %d'))
        timeline_data.append(counts_by_day.get(date_str, 0))
    
    # User engagement stats
    total_users = User.query.count()
    active_users = User.query.filter(User.points > 0).count()
    
    report_data = []
    for report in reports:
        report_data.append({
            'id': report.id,
            'title': report.title,
            'description': report.description,
            'hazard_type': report.hazard_type,
            'location': report.location,
            'latitude': float(report.latitude),
            'longitude': float(report.longitude),
            'image_file': report.image_file,
            'video_file': report.video_file,
            'timestamp': report.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'author': report.author.username,
            'confidence_score': report.confidence_score,
            'verification_status': report.verification_status,
            'ai_analysis': report.ai_analysis
        })
    
    if not report_data:
        report_data = sample_reports
    
    recent_reports_count = len(recent_reports_all)

    return render_template('analyst_dashboard.html', 
                         title='Analyst Dashboard', 
                         reports=report_data,
                         total_reports=total_reports,
                         pending_reports=pending_reports,
                         approved_reports=approved_reports,
                         rejected_reports=rejected_reports,
                         high_confidence_reports=high_confidence_reports,
                         hazard_counts=hazard_counts,
                         recent_reports=recent_reports_count,
                         total_users=total_users,
                         active_users=active_users,
                         timeline_labels=timeline_labels,
                         timeline_data=timeline_data)

@app.route("/simulation")
@login_required
def simulation():
    """Climate Risk & Disaster Impact Simulation Dashboard"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to access the Simulation Dashboard.', 'warning')
        return redirect(url_for('home'))
        
    reports = Report.query.all()
    return render_template('simulation.html', title='Disaster Simulation', reports=reports)

@app.route("/api/simulate_impact", methods=['POST'])
@login_required
def simulate_impact():
    """Predictive AI simulation logic based on climate parameters"""
    if current_user.role not in ['official', 'analyst']:
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    rainfall = float(data.get('rainfall', 0)) # mm/h
    sea_level = float(data.get('sea_level', 0)) # meters
    
    # SIMULATION LOGIC: 
    # Use existing historical hazard nodes as "vulnerable points"
    reports = Report.query.all()
    impact_zones = []
    
    # Deterministic but parameter-driven simulation
    import random
    random.seed(42) # For consistent simulation visuals
    
    for r in reports:
        # Base vulnerability varies by hazard history
        hazard_weight = {
            'tsunami': 0.8,
            'storm_surge': 0.7,
            'coastal_flooding': 0.6,
            'high_waves': 0.4,
            'other': 0.3
        }.get(r.hazard_type, 0.3)
        
        # Calculate risk based on input parameters
        rain_impact = (rainfall / 100.0) * 0.4
        sl_impact = (sea_level / 5.0) * 0.6
        
        risk_score = (hazard_weight * 0.3) + rain_impact + sl_impact
        # Add slight randomness for realism
        risk_score += random.uniform(-0.05, 0.05)
        risk_score = max(0, min(1, risk_score))
        
        # Determine if this area is "affected" in this scenario
        if risk_score > 0.4:
            # Radius grows with severity
            radius = 200 + (rainfall * 5) + (sea_level * 100)
            
            impact_zones.append({
                'lat': float(r.latitude),
                'lng': float(r.longitude),
                'risk': round(risk_score, 2),
                'radius': radius,
                'hazard_type': r.hazard_type,
                'location': r.location
            })
            
    # Calculate Impact Assessment Metrics with Sectoral Breakdown
    affected_count = len(impact_zones)
    
    # Time Horizon Multiplier (simulating climate trend escalation)
    time_horizon = data.get('time_horizon', 'Current')
    horizon_mult = 1.0 if time_horizon == 'Current' else 1.25 if time_horizon == '2030' else 1.6
    
    # Sectoral Damage Estimation (%)
    sector_damage = {
        'power_grid': min(100, int((rainfall * 0.3) + (sea_level * 10) * horizon_mult)),
        'water_supply': min(100, int((rainfall * 0.4) + (sea_level * 5) * horizon_mult)),
        'telecom': min(100, int((rainfall * 0.1) + (sea_level * 15) * horizon_mult)),
        'housing': min(100, int((rainfall * 0.2) + (sea_level * 20) * horizon_mult))
    }
    
    stats = {
        'people_affected': int((affected_count * 150 + int(rainfall * 20)) * horizon_mult),
        'infra_count': int((int(affected_count * 0.4) + int(sea_level * 5)) * horizon_mult),
        'financial_risk': round((affected_count * 0.12 + (rainfall * 0.05)) * horizon_mult, 2),
        'evacuation_priority': 'Critical' if risk_score > 0.8 else 'High' if risk_score > 0.6 else 'Moderate',
        'sector_damage': sector_damage
    }
    
    # AI Summary Generation
    ai_summary = f"SCENARIO ANALYSIS ({time_horizon}): "
    if stats['evacuation_priority'] == 'Critical':
        ai_summary += "Severe systemic failure predicted. Power and Housing sectors show critical vulnerability. Immediate relocation of coastal populations recommended."
    elif stats['evacuation_priority'] == 'High':
        ai_summary += "Significant infrastructure stress detected. Water supply contamination risk is elevated. Activate secondary levee reinforcements."
    else:
        ai_summary += "Localized impact expected. Standard drainage protocols sufficient for current parameters."
    
    return jsonify({
        'success': True,
        'zones': impact_zones,
        'stats': stats,
        'ai_summary': ai_summary
    })

@app.route("/chart/hazard_distribution")
@login_required
def hazard_distribution_chart():
    """Generate hazard distribution chart"""
    if current_user.role not in ['official', 'analyst']:
        return "Unauthorized", 403
    
    reports = Report.query.all()
    hazard_counts = {}
    for report in reports:
        hazard_type = report.hazard_type
        hazard_counts[hazard_type] = hazard_counts.get(hazard_type, 0) + 1
    
    # Create pie chart
    plt.figure(figsize=(8, 6))
    if hazard_counts:
        labels = list(hazard_counts.keys())
        sizes = list(hazard_counts.values())
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        plt.title('Hazard Type Distribution')
    else:
        plt.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=plt.gca().transAxes)
    
    # Save to bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close()
    
    return Response(buf.getvalue(), mimetype='image/png')

@app.route("/chart/reports_timeline")
@login_required
def reports_timeline_chart():
    """Generate reports timeline chart"""
    if current_user.role not in ['official', 'analyst']:
        return "Unauthorized", 403
    
    # Get reports from last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    reports = Report.query.filter(Report.timestamp >= thirty_days_ago).all()
    
    # Group by date
    daily_counts = {}
    for report in reports:
        date_str = report.timestamp.strftime('%Y-%m-%d')
        daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
    
    # Create line chart
    plt.figure(figsize=(10, 6))
    if daily_counts:
        dates = sorted(daily_counts.keys())
        counts = [daily_counts[date] for date in dates]
        
        plt.plot(dates, counts, marker='o', linewidth=2, markersize=6)
        plt.xlabel('Date')
        plt.ylabel('Number of Reports')
        plt.title('Reports Timeline (Last 30 Days)')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
    else:
        plt.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=plt.gca().transAxes)
    
    # Save to bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close()
    
    return Response(buf.getvalue(), mimetype='image/png')

@app.route("/chart/user_engagement")
@login_required
def user_engagement_chart():
    """Generate user engagement chart"""
    if current_user.role not in ['official', 'analyst']:
        return "Unauthorized", 403
    
    users = User.query.all()
    
    # Categorize users by points
    categories = {
        '0-10': 0,
        '11-50': 0,
        '51-100': 0,
        '101-500': 0,
        '500+': 0
    }
    
    for user in users:
        points = user.points
        if points == 0:
            categories['0-10'] += 1
        elif points <= 10:
            categories['0-10'] += 1
        elif points <= 50:
            categories['11-50'] += 1
        elif points <= 100:
            categories['51-100'] += 1
        elif points <= 500:
            categories['101-500'] += 1
        else:
            categories['500+'] += 1
    
    # Create bar chart
    plt.figure(figsize=(10, 6))
    labels = list(categories.keys())
    values = list(categories.values())
    
    bars = plt.bar(labels, values, color=plt.cm.viridis(np.linspace(0, 1, len(labels))))
    plt.xlabel('Points Range')
    plt.ylabel('Number of Users')
    plt.title('User Engagement Distribution')
    
    # Add value labels on bars
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                str(value), ha='center', va='bottom')
    
    plt.tight_layout()
    
    # Save to bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close()
    
    return Response(buf.getvalue(), mimetype='image/png')

def get_weather_warnings():
    """Get weather warnings from external API (mock data for demo)"""
    # In production, integrate with actual weather APIs like:
    # - IMD (India Meteorological Department)
    # - OpenWeatherMap
    # - WeatherAPI
    
    # Mock weather warnings for demonstration
    warnings = [
        {
            'type': 'cyclone',
            'severity': 'high',
            'location': 'Bay of Bengal',
            'latitude': 15.0,
            'longitude': 88.0,
            'radius': 300,  # km
            'message': 'Cyclone warning: System developing in Bay of Bengal',
            'timestamp': datetime.utcnow().isoformat()
        },
        {
            'type': 'high_waves',
            'severity': 'medium',
            'location': 'Arabian Sea Coast',
            'latitude': 18.5,
            'longitude': 72.8,
            'radius': 100,
            'message': 'High wave warning: 3-4 meter waves expected',
            'timestamp': (datetime.utcnow() - timedelta(hours=2)).isoformat()
        },
        {
            'type': 'heavy_rain',
            'severity': 'medium',
            'location': 'Kerala Coast',
            'latitude': 10.0,
            'longitude': 76.2,
            'radius': 150,
            'message': 'Heavy rainfall alert: Coastal areas may experience flooding',
            'timestamp': (datetime.utcnow() - timedelta(hours=1)).isoformat()
        }
    ]
    
    return warnings

@app.route("/api/weather_data")
def api_weather_data():
    """API endpoint for live weather data with temperature and wind information"""
    try:
        # Get weather data from multiple sources
        # Using Open-Meteo API (free, no key required) for Indian coastal regions
        
        # Major coastal cities in India for weather monitoring
        coastal_cities = [
            {'name': 'Chennai', 'lat': 13.0827, 'lon': 80.2707},
            {'name': 'Mumbai', 'lat': 19.0760, 'lon': 72.8777},
            {'name': 'Kolkata', 'lat': 22.5726, 'lon': 88.3639},
            {'name': 'Kochi', 'lat': 9.9312, 'lon': 76.2673},
            {'name': 'Visakhapatnam', 'lat': 17.6868, 'lon': 83.2185},
            {'name': 'Mangalore', 'lat': 12.9141, 'lon': 74.8560},
            {'name': 'Thiruvananthapuram', 'lat': 8.5241, 'lon': 76.9366},
            {'name': 'Goa', 'lat': 15.2993, 'lon': 73.8243},
        ]
        
        alerts = []
        
        for city in coastal_cities:
            try:
                # Open-Meteo API - free weather data
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={city['lat']}&longitude={city['lon']}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m&timezone=Asia/Kolkata"
                
                response = requests.get(weather_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    current = data.get('current', {})
                    
                    alert = {
                        'city': city['name'],
                        'latitude': city['lat'],
                        'longitude': city['lon'],
                        'temperature': round(current.get('temperature_2m', 25), 1),
                        'humidity': current.get('relative_humidity_2m', 60),
                        'wind_speed': round(current.get('wind_speed_10m', 5), 1),
                        'wind_direction': current.get('wind_direction_10m', 0),
                        'weather_code': current.get('weather_code', 0),
                        'timestamp': datetime.utcnow().isoformat(),
                        'severity': 'high' if current.get('wind_speed_10m', 0) > 40 else 'medium' if current.get('wind_speed_10m', 0) > 25 else 'low'
                    }
                    alerts.append(alert)
            except Exception as e:
                print(f"Error fetching weather for {city['name']}: {e}")
                continue
        
        # If API fails, return realistic sample data
        if not alerts:
            alerts = [
                {
                    'city': 'Chennai',
                    'latitude': 13.0827,
                    'longitude': 80.2707,
                    'temperature': 28.5 + random.uniform(-2, 2),
                    'humidity': 75 + random.randint(-10, 10),
                    'wind_speed': 15 + random.uniform(-5, 5),
                    'wind_direction': random.randint(0, 360),
                    'weather_code': random.choice([0, 1, 45, 48, 51, 61, 80]),
                    'timestamp': datetime.utcnow().isoformat(),
                    'severity': 'medium'
                },
                {
                    'city': 'Mumbai',
                    'latitude': 19.0760,
                    'longitude': 72.8777,
                    'temperature': 32.0 + random.uniform(-2, 2),
                    'humidity': 70 + random.randint(-10, 10),
                    'wind_speed': 20 + random.uniform(-5, 5),
                    'wind_direction': random.randint(0, 360),
                    'weather_code': random.choice([0, 1, 45, 48, 51, 61, 80]),
                    'timestamp': datetime.utcnow().isoformat(),
                    'severity': 'low'
                },
                {
                    'city': 'Kochi',
                    'latitude': 9.9312,
                    'longitude': 76.2673,
                    'temperature': 26.5 + random.uniform(-2, 2),
                    'humidity': 85 + random.randint(-10, 10),
                    'wind_speed': 25 + random.uniform(-5, 5),
                    'wind_direction': random.randint(0, 360),
                    'weather_code': 80,
                    'timestamp': datetime.utcnow().isoformat(),
                    'severity': 'medium'
                }
            ]
        
        return jsonify({'alerts': alerts, 'count': len(alerts)})
    
    except Exception as e:
        print(f"Error in weather data endpoint: {e}")
        return jsonify({'alerts': [], 'error': str(e)}), 500

@app.route("/api/live_hazard_incidents")
def api_live_hazard_incidents():
    """API endpoint for live incident heatmap data - real-time hazard reports from users"""
    try:
        # Get all active/approved reports from the database
        reports = Report.query.filter(
            Report.status == 'active',
            Report.verification_status.in_(['approved', 'pending']),
            Report.latitude.isnot(None),
            Report.longitude.isnot(None)
        ).order_by(Report.timestamp.desc()).limit(500).all()
        
        incidents = []
        for report in reports:
            incidents.append({
                'id': report.id,
                'latitude': float(report.latitude),
                'longitude': float(report.longitude),
                'hazard_type': report.hazard_type,
                'title': report.title,
                'priority': report.priority,
                'confidence_score': float(report.confidence_score) if report.confidence_score else 0.5,
                'timestamp': report.timestamp.isoformat() if report.timestamp else None,
                'author': report.author.username if report.author else 'Unknown',
                'verified': report.verified,
                'verification_status': report.verification_status
            })
        
        return jsonify({
            'incidents': incidents,
            'count': len(incidents),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        print(f"Error in live hazard incidents endpoint: {e}")
        return jsonify({'incidents': [], 'count': 0, 'error': str(e)}), 500

@app.route("/api/live_govt_hazards")
def api_live_govt_hazards():
    """API endpoint for live government hazard alerts and disaster information"""
    try:
        import random
        from datetime import datetime, timedelta
        
        # Simulated government hazard data from NDMA, IMD, USGS, etc.
        # In production, this would integrate with actual government APIs
        govt_hazards = [
            {
                'type': 'Cyclone Warning',
                'severity': 'critical',
                'latitude': 13.0827,
                'longitude': 80.2707,
                'description': 'High probability of cyclone formation over Bay of Bengal',
                'radius': 200,  # km
                'source': 'IMD (India Meteorological Department)',
                'alert_level': 'Red',
                'wind_speed': '65-75 km/h',
                'rainfall': '150-200 mm'
            },
            {
                'type': 'Flood Alert',
                'severity': 'high',
                'latitude': 22.5726,
                'longitude': 88.3639,
                'description': 'Heavy rainfall warning for Kolkata region',
                'radius': 150,
                'source': 'NDMA (National Disaster Management Authority)',
                'alert_level': 'Orange',
                'rainfall': '100-150 mm',
                'river_level': 'Above normal'
            },
            {
                'type': 'Earthquake Risk',
                'severity': 'medium',
                'latitude': 19.0760,
                'longitude': 72.8777,
                'description': 'Seismic activity detected near Mumbai coast',
                'radius': 100,
                'source': 'USGS Earthquake Hazards Program',
                'alert_level': 'Yellow',
                'magnitude': '3.2 Richter',
                'depth': '35 km'
            },
            {
                'type': 'Landslide Warning',
                'severity': 'high',
                'latitude': 9.9312,
                'longitude': 76.2673,
                'description': 'Heavy rainfall triggered landslide risk in Western Ghats',
                'radius': 80,
                'source': 'GSI (Geological Survey of India)',
                'alert_level': 'Orange',
                'rainfall': '200+ mm',
                'slope_condition': 'Unstable'
            },
            {
                'type': 'Tsunami Warning',
                'severity': 'critical',
                'latitude': 8.5241,
                'longitude': 76.9366,
                'description': 'Potential tsunami threat in Indian Ocean',
                'radius': 300,
                'source': 'Indian Tsunami Early Warning System',
                'alert_level': 'Red',
                'wave_height': '1-3 meters',
                'eta': '2-4 hours'
            }
        ]
        
        # Add dynamic timestamp and randomize some severity levels
        for hazard in govt_hazards:
            hazard['id'] = hazard['type'].replace(' ', '_').lower()
            hazard['timestamp'] = (datetime.utcnow() - timedelta(minutes=random.randint(1, 30))).isoformat()
            hazard['confidence_score'] = round(0.7 + random.uniform(0, 0.3), 2)
        
        return jsonify({
            'hazards': govt_hazards,
            'count': len(govt_hazards),
            'timestamp': datetime.utcnow().isoformat(),
            'sources': ['IMD', 'NDMA', 'USGS', 'GSI', 'Indian Tsunami Early Warning System']
        })
    
    except Exception as e:
        print(f"Error in live govt hazards endpoint: {e}")
        return jsonify({'hazards': [], 'count': 0, 'error': str(e)}), 500

@app.route("/api/weather_warnings")
@login_required
def api_weather_warnings():
    """API endpoint for weather warnings"""
    if current_user.role not in ['official', 'analyst']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    warnings = get_weather_warnings()
    return jsonify(warnings)

@app.route("/api/report/<int:report_id>/accuracy_3param", methods=['GET'])
@login_required
def get_report_3param_accuracy(report_id):
    """Get 3-parameter accuracy breakdown for a report"""
    report = Report.query.get_or_404(report_id)
    
    # Calculate 3-parameter accuracy
    accuracy_result = validate_report_accuracy_3params(report)
    
    return jsonify({
        'report_id': report.id,
        'title': report.title,
        'hazard_type': report.hazard_type,
        'overall_accuracy_percent': accuracy_result['accuracy_percent'],
        'parameter_1_heatmap': {
            'name': 'Weather & Early Warnings - Heatmap Match',
            'score_percent': int(accuracy_result['parameter_1_heatmap']['score'] * 100),
            'analysis': accuracy_result['parameter_1_heatmap']['analysis'],
            'weight': '33%'
        },
        'parameter_2_climate': {
            'name': 'Live Climate Data - Weather Alignment',
            'score_percent': int(accuracy_result['parameter_2_climate']['score'] * 100),
            'analysis': accuracy_result['parameter_2_climate']['analysis'],
            'weight': '33%'
        },
        'parameter_3_user_quality': {
            'name': 'User Quality - Credibility Score',
            'score_percent': int(accuracy_result['parameter_3_user_quality']['score'] * 100),
            'analysis': accuracy_result['parameter_3_user_quality']['analysis'],
            'weight': '34%',
            'user_role': accuracy_result['parameter_3_user_quality'].get('role'),
            'user_level': accuracy_result['parameter_3_user_quality'].get('level'),
            'user_total_reports': accuracy_result['parameter_3_user_quality'].get('total_reports')
        },
        'detailed_breakdown': accuracy_result['detailed_analysis']
    })

def send_early_warning_alerts(warning):
    """Send early warning alerts to users in affected areas"""
    users = User.query.filter(
        User.home_latitude.isnot(None),
        User.home_longitude.isnot(None)
    ).all()
    
    users_alerted = 0
    
    for user in users:
        distance = calculate_distance(
            warning['latitude'], warning['longitude'],
            user.home_latitude, user.home_longitude
        )
        
        if distance <= warning['radius']:
            # Create early warning notification
            alert_message = f"🚨 EARLY WARNING: {warning['message']} - {distance:.1f}km from your location"
            
            alert_notification = Notification(
                user_id=user.id,
                message=alert_message,
                is_alert=True,
                is_read=False
            )
            db.session.add(alert_notification)
            
            # Send WhatsApp Alert if linked
            if user.whatsapp_number:
                whatsapp_body = f"🛡️ *Sentinel AI: EARLY WARNING*\n\n{alert_message}\n\n📍 *Area:* {warning.get('location', 'Your Region')}\n\n🔗 *Dashboard:* {request.url_root.rstrip('/')}/dashboard\n\nFollow safety protocols immediately."
                send_whatsapp_message(user.whatsapp_number, whatsapp_body)
                
            users_alerted += 1
    
    db.session.commit()
    return users_alerted

@app.route("/send_test_warning", methods=['POST'])
@login_required
def send_test_warning():
    """Endpoint to test early warning system"""
    if current_user.role not in ['official', 'analyst']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    test_warning = {
        'type': 'test',
        'severity': 'high',
        'location': 'Test Area',
        'latitude': current_user.home_latitude or 20.5937,
        'longitude': current_user.home_longitude or 78.9629,
        'radius': 50,
        'message': 'TEST: Early warning system test alert'
    }
    
    users_alerted = send_early_warning_alerts(test_warning)
    
    return jsonify({
        'success': True,
        'message': f'Test warning sent to {users_alerted} users',
        'users_alerted': users_alerted
    })

@app.route("/send_global_alert", methods=['POST'])
@login_required
def send_global_alert():
    """Send global alert to all users affected by incident hotspots and weather zones"""
    if current_user.role not in ['official', 'analyst']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        affected_locations = data.get('affected_locations', [])
        message = data.get('message', 'GLOBAL ALERT: Disaster Management Alert')
        
        # Collect all unique users to notify
        users_to_notify = set()
        
        # Get all users with location data
        users_with_location = User.query.filter(
            User.home_latitude.isnot(None),
            User.home_longitude.isnot(None)
        ).all()
        
        # Check each user against affected locations
        for user in users_with_location:
            for location in affected_locations:
                # Check if user is within 15km of any affected location
                distance = calculate_distance(
                    user.home_latitude, user.home_longitude,
                    location['latitude'], location['longitude']
                )
                if distance <= 15:  # 15km alert radius
                    users_to_notify.add(user.id)
                    break  # Don't need to check other locations for this user
        
        # Create notifications for all affected users
        notification_count = 0
        for user_id in users_to_notify:
            user = User.query.get(user_id)
            if not user: continue
            
            alert_message = f"🚨 GLOBAL ALERT: {message}"
            notification = Notification(
                user_id=user_id,
                message=alert_message,
                is_alert=True,
                is_read=False
            )
            db.session.add(notification)
            
            # Send WhatsApp Alert if linked
            if user.whatsapp_number:
                # Build detailed hazard information
                hazard_details = []
                for idx, location in enumerate(affected_locations[:3], 1):  # Show up to 3 locations
                    loc_name = location.get('name', 'Unknown Location')
                    loc_type = location.get('type', 'Alert')
                    loc_desc = location.get('description', 'No description available')
                    hazard_details.append(f"{idx}. *{loc_name}* ({loc_type})\n   _{loc_desc[:100]}_")
                
                # Create comprehensive WhatsApp message
                whatsapp_body = f"""⚡ *Sentinel AI: GLOBAL BROADCAST*

🚨 *EMERGENCY ALERT*

{message}

📍 *Affected Areas ({len(affected_locations)}):*
{chr(10).join(hazard_details)}
{f'...and {len(affected_locations) - 3} more areas' if len(affected_locations) > 3 else ''}

⚠️ *Action Required:*
• Follow safety protocols immediately
• Check dashboard for full details
• Stay alert for updates

🔗 *Dashboard:* {request.url_root.rstrip('/')}/dashboard

Stay safe! 🛡️"""
                
                send_whatsapp_message(user.whatsapp_number, whatsapp_body)
                
            notification_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Global alert sent successfully',
            'locations_count': len(affected_locations),
            'users_alerted': notification_count,
            'status': 'completed'
        })
    
    except Exception as e:
        print(f"Error in send_global_alert: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'users_alerted': 0,
            'locations_count': 0
        }), 500

@app.route('/reject_report/<int:report_id>', methods=['GET', 'POST'])
@login_required
def reject_report(report_id):
    print(f"🔍 reject_report called for report {report_id} by user {current_user.username}")
    
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to reject reports.', 'warning')
        return redirect(url_for('view_report', report_id=report_id))
    
    report = Report.query.get_or_404(report_id)
    
    if request.method == 'POST':
        rejection_reason = request.form.get('rejection_reason', 'No reason provided')
        schedule_deletion = 'schedule_deletion' in request.form
        notify_user = 'notify_user' in request.form
        
        print(f"📝 Rejection reason: {rejection_reason}")
        print(f"🗑️ Schedule deletion: {schedule_deletion}")
        print(f"🔔 Notify user: {notify_user}")
        
        if not rejection_reason or rejection_reason.strip() == '':
            flash('Please provide a reason for rejection.', 'error')
            return render_template('reject_report.html', report=report)
        
        # Update report status
        report.verification_status = 'rejected'
        report.verified_by = current_user.id
        report.verified_at = datetime.utcnow()
        report.rejection_reason = rejection_reason.strip()
        report.verified = False
        
        # Handle deletion scheduling
        if schedule_deletion:
            report.scheduled_deletion = datetime.utcnow() + timedelta(hours=24)
            print(f"⏰ Scheduled for deletion at: {report.scheduled_deletion}")
        else:
            report.scheduled_deletion = None
            print("⏰ No deletion scheduled")
        
        # Create notification for the report author if requested
        if notify_user:
            author_notification = Notification(
                user_id=report.user_id,
                message=f'⚠️ Your report "{report.title}" was rejected. Reason: {rejection_reason}',
                report_id=report.id,
                expires_at=report.scheduled_deletion if schedule_deletion else None
            )
            db.session.add(author_notification)
            print(f"📨 Created rejection notification for report author")
        else:
            print("🔕 No notification sent to user")
        
        db.session.commit()
        print("💾 Rejection changes committed")
        
        flash('Report rejected successfully.', 'success')
        return redirect(url_for('view_report', report_id=report_id))
    
    # GET request - show the rejection form
    return render_template('reject_report.html', report=report)





# Add this after: app = Flask(__name__)
# and before any routes

@app.template_filter('fromjson')
def fromjson_filter(value):
    """Convert a JSON string to a Python object"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value

# =============================================================================
# GOVERNMENT-NGO COORDINATION PLATFORM
# =============================================================================

@app.route("/coordination")
@login_required
def coordination_dashboard():
    """Unified command center dashboard"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to access the coordination platform.', 'warning')
        return redirect(url_for('home'))
    
    # Get active emergency events
    active_events = EmergencyEvent.query.filter_by(status='active').order_by(EmergencyEvent.created_at.desc()).all()
    
    # Get recent situation reports
    recent_reports = SituationReport.query.order_by(SituationReport.created_at.desc()).limit(5).all()
    
    # Get resource allocations
    resource_allocations = ResourceAllocation.query.join(EmergencyEvent).filter(
        EmergencyEvent.status == 'active'
    ).all()
    
    # Get available volunteers
    available_volunteers = Volunteer.query.filter_by(availability='available', is_verified=True).count()
    
    return render_template('coordination_dashboard.html',
                         title='Coordination Platform',
                         active_events=active_events,
                         recent_reports=recent_reports,
                         resource_allocations=resource_allocations,
                         available_volunteers=available_volunteers)

@app.route("/coordination/agencies")
@login_required
def agency_management():
    """Manage participating agencies"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to manage agencies.', 'warning')
        return redirect(url_for('home'))
    
    agencies = Agency.query.filter_by(is_active=True).order_by(Agency.name).all()
    return render_template('agency_management.html',
                         title='Agency Management',
                         agencies=agencies)

@app.route("/coordination/agencies/new", methods=['GET', 'POST'])
@login_required
def new_agency():
    """Register a new agency"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to register agencies.', 'warning')
        return redirect(url_for('home'))
    
    form = AgencyForm()
    
    if form.validate_on_submit():
        agency = Agency(
            name=form.name.data,
            type=form.type.data,
            contact_email=form.contact_email.data,
            contact_phone=form.contact_phone.data,
            resources=form.resources.data,
            capabilities=form.capabilities.data
        )
        db.session.add(agency)
        db.session.commit()
        
        flash(f'Agency {agency.name} registered successfully!', 'success')
        return redirect(url_for('agency_management'))
    
    return render_template('new_agency.html',
                         title='Register New Agency',
                         form=form)

@app.route("/coordination/emergencies")
@login_required
def emergency_management():
    """Manage emergency events"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to manage emergencies.', 'warning')
        return redirect(url_for('home'))
    
    emergencies = EmergencyEvent.query.order_by(EmergencyEvent.created_at.desc()).all()
    return render_template('emergency_management.html',
                         title='Emergency Management',
                         emergencies=emergencies)

@app.route("/coordination/emergencies/new", methods=['GET', 'POST'])
@login_required
def new_emergency():
    """Create a new emergency event"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to create emergency events.', 'warning')
        return redirect(url_for('home'))
    
    form = EmergencyEventForm()
    
    if form.validate_on_submit():
        emergency = EmergencyEvent(
            title=form.title.data,
            description=form.description.data,
            hazard_type=form.hazard_type.data,
            severity=form.severity.data,
            location=form.location.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            radius_km=form.radius_km.data,
            created_by=current_user.id
        )
        db.session.add(emergency)
        db.session.commit()
        
        # Create initial situation report
        initial_report = SituationReport(
            emergency_event_id=emergency.id,
            title=f"Initial Report: {emergency.title}",
            content=f"Emergency event created. {emergency.description}",
            priority=emergency.severity,
            report_type='damage_assessment',
            created_by=current_user.id
        )
        db.session.add(initial_report)
        db.session.commit()
        
        flash(f'Emergency event "{emergency.title}" created successfully!', 'success')
        return redirect(url_for('emergency_management'))
    
    return render_template('new_emergency.html',
                         title='Create Emergency Event',
                         form=form)

@app.route("/coordination/resources")
@login_required
def resource_management():
    """Manage resource allocation"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to manage resources.', 'warning')
        return redirect(url_for('home'))
    
    allocations = ResourceAllocation.query.order_by(ResourceAllocation.created_at.desc()).all()
    agencies = Agency.query.filter_by(is_active=True).all()
    emergencies = EmergencyEvent.query.filter_by(status='active').all()
    
    return render_template('resource_management.html',
                         title='Resource Management',
                         allocations=allocations,
                         agencies=agencies,
                         emergencies=emergencies)

@app.route("/coordination/resources/allocate", methods=['GET', 'POST'])
@login_required
def allocate_resources():
    """Allocate resources to emergency events"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to allocate resources.', 'warning')
        return redirect(url_for('home'))
    
    form = ResourceAllocationForm()
    
    # Populate dropdown choices
    form.emergency_event_id.choices = [(e.id, e.title) for e in EmergencyEvent.query.filter_by(status='active').all()]
    form.agency_id.choices = [(a.id, a.name) for a in Agency.query.filter_by(is_active=True).all()]
    
    if form.validate_on_submit():
        allocation = ResourceAllocation(
            emergency_event_id=form.emergency_event_id.data,
            agency_id=form.agency_id.data,
            resource_type=form.resource_type.data,
            quantity=form.quantity.data,
            units=form.units.data,
            allocated_by=current_user.id
        )
        db.session.add(allocation)
        db.session.commit()
        
        flash('Resources allocated successfully!', 'success')
        return redirect(url_for('resource_management'))
    
    return render_template('allocate_resources.html',
                         title='Allocate Resources',
                         form=form)

@app.route("/coordination/volunteers")
@login_required
def volunteer_management():
    """Manage volunteers and assignments"""
    if current_user.role not in ['official', 'analyst', 'admin', 'coordinator']:
        flash('You need elevated privileges to manage volunteers.', 'warning')
        return redirect(url_for('home'))
    
    volunteers = Volunteer.query.all()
    assignments = VolunteerAssignment.query.filter_by(status='assigned').all()
    emergencies = EmergencyEvent.query.filter_by(status='active').all()
    
    # Calculate stats
    total_volunteers = len(volunteers)
    available_volunteers = len([v for v in volunteers if v.availability == 'available'])
    assigned_volunteers = len([v for v in volunteers if v.availability == 'busy'])
    trained_volunteers = len([v for v in volunteers if v.experience_level in ['Advanced', 'Intermediate']])
    
    return render_template('volunteer_management.html',
                         title='Volunteer Management',
                         volunteers=volunteers,
                         assignments=assignments,
                         emergencies=emergencies,
                         total_volunteers=total_volunteers,
                         available_volunteers=available_volunteers,
                         assigned_volunteers=assigned_volunteers,
                         trained_volunteers=trained_volunteers)

@app.route("/coordination/volunteers/register", methods=['GET', 'POST'])
@login_required
def register_volunteer():
    """Register as a volunteer"""
    # Check if user already has a volunteer profile
    existing_volunteer = Volunteer.query.filter_by(user_id=current_user.id).first()
    if existing_volunteer:
        flash('You already have a volunteer profile!', 'info')
        return redirect(url_for('volunteer_management'))
    
    form = VolunteerRegistrationForm()
    
    if form.validate_on_submit():
        volunteer = Volunteer(
            user_id=current_user.id,
            skills=form.skills.data,
            experience_level=form.experience_level.data,
            certifications=form.certifications.data,
            location=form.location.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            availability=form.availability.data,
            is_verified=(current_user.role in ['official', 'analyst'])  # Auto-verify officials
        )
        db.session.add(volunteer)
        db.session.commit()
        
        flash('Volunteer profile created successfully!', 'success')
        return redirect(url_for('volunteer_management'))
    
    return render_template('register_volunteer.html',
                         title='Register as Volunteer',
                         form=form)

@app.route("/coordination/volunteers/assign", methods=['GET', 'POST'])
@login_required
def assign_volunteer():
    """Assign volunteers to emergency events"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to assign volunteers.', 'warning')
        return redirect(url_for('home'))
    
    form = VolunteerAssignmentForm()
    
    # Populate dropdown choices
    form.volunteer_id.choices = [(v.id, f"{v.user.username} - {v.skills}") 
                                for v in Volunteer.query.filter_by(availability='available', is_verified=True).all()]
    form.emergency_event_id.choices = [(e.id, e.title) for e in EmergencyEvent.query.filter_by(status='active').all()]
    
    if form.validate_on_submit():
        assignment = VolunteerAssignment(
            volunteer_id=form.volunteer_id.data,
            emergency_event_id=form.emergency_event_id.data,
            role=form.role.data,
            assigned_by=current_user.id
        )
        
        # Update volunteer availability
        volunteer = Volunteer.query.get(form.volunteer_id.data)
        volunteer.availability = 'busy'
        
        db.session.add(assignment)
        db.session.commit()
        
        flash('Volunteer assigned successfully!', 'success')
        return redirect(url_for('volunteer_management'))
    
    return render_template('assign_volunteer.html',
                         title='Assign Volunteer',
                         form=form)

@app.route("/coordination/situation-reports")
@login_required
def situation_reports():
    """View and create situation reports"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to access situation reports.', 'warning')
        return redirect(url_for('home'))
    
    reports = SituationReport.query.order_by(SituationReport.created_at.desc()).all()
    emergencies = EmergencyEvent.query.filter_by(status='active').all()
    
    return render_template('situation_reports.html',
                         title='Situation Reports',
                         reports=reports,
                         emergencies=emergencies)

@app.route("/coordination/situation-reports/new", methods=['GET', 'POST'])
@login_required
def new_situation_report():
    """Create a new situation report"""
    if current_user.role not in ['official', 'analyst']:
        flash('You need elevated privileges to create situation reports.', 'warning')
        return redirect(url_for('home'))
    
    form = SituationReportForm()
    
    # Populate emergency events dropdown
    form.emergency_event_id.choices = [(e.id, e.title) for e in EmergencyEvent.query.filter_by(status='active').all()]
    
    if form.validate_on_submit():
        report = SituationReport(
            emergency_event_id=form.emergency_event_id.data,
            title=form.title.data,
            content=form.content.data,
            priority=form.priority.data,
            report_type=form.report_type.data,
            created_by=current_user.id
        )
        db.session.add(report)
        db.session.commit()
        
        flash('Situation report created successfully!', 'success')
        return redirect(url_for('situation_reports'))
    
    return render_template('new_situation_report.html',
                         title='New Situation Report',
                         form=form)

@app.route("/api/coordination/volunteers/match")
@login_required
def match_volunteers():
    """API endpoint for skill-based volunteer matching"""
    if current_user.role not in ['official', 'analyst']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    emergency_id = request.args.get('emergency_id', type=int)
    required_skills = request.args.get('skills', '').split(',')
    
    if not emergency_id:
        return jsonify({'error': 'Emergency ID required'}), 400
    
    emergency = EmergencyEvent.query.get_or_404(emergency_id)
    
    # Find volunteers with matching skills near the emergency location
    volunteers = Volunteer.query.filter(
        Volunteer.availability == 'available',
        Volunteer.is_verified == True
    ).all()
    
    matched_volunteers = []
    for volunteer in volunteers:
        # Simple skill matching (in production, use more sophisticated matching)
        volunteer_skills = [s.strip().lower() for s in volunteer.skills.split(',')] if volunteer.skills else []
        matched_skills = set(volunteer_skills) & set([s.strip().lower() for s in required_skills])
        
        if matched_skills:
            # Calculate distance if location data available
            distance = None
            if volunteer.latitude and volunteer.longitude:
                distance = calculate_distance(
                    emergency.latitude, emergency.longitude,
                    volunteer.latitude, volunteer.longitude
                )
            
            matched_volunteers.append({
                'id': volunteer.id,
                'name': volunteer.user.username,
                'skills': volunteer.skills,
                'matched_skills': list(matched_skills),
                'experience_level': volunteer.experience_level,
                'distance_km': distance,
                'location': volunteer.location
            })
    
    # Sort by number of matched skills and distance
    matched_volunteers.sort(key=lambda x: (len(x['matched_skills']), x['distance_km'] or float('inf')))
    
    return jsonify({'matched_volunteers': matched_volunteers})

@app.route("/api/hazards/active")
@login_required
def get_active_hazards():
    """Get all approved hazards from both emergency events and approved reports"""
    hazards_data = []
    
    # Get emergency events (excluding cancelled)
    emergencies = EmergencyEvent.query.filter(
        EmergencyEvent.status != 'cancelled'
    ).order_by(EmergencyEvent.created_at.desc()).all()
    
    for emergency in emergencies:
        hazards_data.append({
            'id': emergency.id,
            'type': 'emergency',
            'title': emergency.title,
            'description': emergency.description,
            'hazard_type': emergency.hazard_type,
            'severity': emergency.severity,
            'location': emergency.location,
            'latitude': emergency.latitude,
            'longitude': emergency.longitude,
            'status': emergency.status,
            'created_at': emergency.created_at.isoformat() if emergency.created_at else None
        })
    
    # Get approved reports from hazard feed
    approved_reports = Report.query.filter_by(
        verification_status='approved'
    ).order_by(Report.timestamp.desc()).all()
    
    for report in approved_reports:
        hazards_data.append({
            'id': report.id,
            'type': 'report',
            'title': report.title,
            'description': report.description,
            'hazard_type': report.hazard_type,
            'severity': None,
            'location': report.location,
            'latitude': report.latitude,
            'longitude': report.longitude,
            'status': 'approved',
            'created_at': report.timestamp.isoformat() if report.timestamp else None,
            'author': report.author.username if report.author else 'Unknown'
        })
    
    # Sort all by date (newest first)
    hazards_data.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({'hazards': hazards_data})

@app.route("/api/coordination/resources/status")
@login_required
def resource_status():
    """API endpoint for real-time resource status"""
    if current_user.role not in ['official', 'analyst']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    emergency_id = request.args.get('emergency_id', type=int)
    
    if emergency_id:
        allocations = ResourceAllocation.query.filter_by(emergency_event_id=emergency_id).all()
    else:
        allocations = ResourceAllocation.query.all()
    
    resource_data = {}
    for allocation in allocations:
        if allocation.resource_type not in resource_data:
            resource_data[allocation.resource_type] = {
                'allocated': 0,
                'deployed': 0,
                'used': 0
            }
        
        resource_data[allocation.resource_type]['allocated'] += allocation.quantity
        if allocation.status == 'deployed':
            resource_data[allocation.resource_type]['deployed'] += allocation.quantity
        elif allocation.status == 'used':
            resource_data[allocation.resource_type]['used'] += allocation.quantity
    
    return jsonify(resource_data)

# =============================================================================
# VOLUNTEER ASSIGNMENT ENDPOINTS
# =============================================================================

@app.route("/api/coordination/assign-volunteer", methods=['POST'])
@login_required
def assign_volunteer_to_hazard():
    """Assign a volunteer to a hazard (emergency event or report) within 50km"""
    print(f"[ASSIGN] User {current_user.username} (role: {current_user.role}) is attempting assignment...")
    
    if current_user.role not in ['official', 'analyst', 'admin', 'coordinator']:
        print(f"[ASSIGN ERROR] Unauthorized role: {current_user.role}")
        return jsonify({'error': 'Unauthorized - You must have official, analyst, admin or coordinator role'}), 403
    
    data = request.get_json()
    volunteer_id = data.get('volunteer_id')
    emergency_event_id = data.get('emergency_event_id')
    hazard_type = data.get('hazard_type', 'emergency')
    
    print(f"[ASSIGN] Data: vol_id={volunteer_id}, hazard_id={emergency_event_id}, type={hazard_type}")
    
    if not volunteer_id or not emergency_event_id:
        return jsonify({'error': 'Missing required fields'}), 400
    
    volunteer = Volunteer.query.get_or_404(volunteer_id)
    print(f"[ASSIGN] Found volunteer: {volunteer.id}, user_id={volunteer.user_id}")
    
    # Verify volunteer has a user relationship
    if not volunteer.user:
        print(f"[ASSIGN ERROR] Volunteer {volunteer.id} has no associated user!")
        return jsonify({'error': 'Volunteer profile is not properly linked to a user account'}), 500
    
    # Get hazard based on type
    if hazard_type == 'report':
        hazard = Report.query.get_or_404(emergency_event_id)
    else:
        hazard = EmergencyEvent.query.get_or_404(emergency_event_id)
    
    print(f"[ASSIGN] Found hazard: {hazard.title} (type={hazard_type})")
    
    # Calculate distance
    distance_km = calculate_distance(
        hazard.latitude, hazard.longitude,
        volunteer.latitude, volunteer.longitude
    )
    
    print(f"[ASSIGN] Distance calculated: {distance_km:.2f}km")
    
    # Check if within 50km
    if distance_km > 50:
        return jsonify({'error': f'Volunteer is {distance_km:.1f}km away. Maximum distance is 50km'}), 400
    
    # Check if already assigned (check both ID and type)
    existing = VolunteerAssignment.query.filter_by(
        volunteer_id=volunteer_id,
        emergency_event_id=emergency_event_id,
        hazard_type=hazard_type
    ).filter(VolunteerAssignment.status.in_(['pending', 'accepted', 'deployed'])).first()
    
    if existing:
        print(f"[ASSIGN ERROR] Volunteer already has active assignment: id={existing.id}, status={existing.status}")
        return jsonify({'error': f'Volunteer already has an active {existing.status} assignment for this hazard'}), 400
    
    # Create assignment
    assignment = VolunteerAssignment(
        volunteer_id=volunteer_id,
        emergency_event_id=emergency_event_id,
        hazard_type=hazard_type,  # Store the type!
        assigned_by=current_user.id,
        status='pending',
        distance_km=distance_km
    )
    db.session.add(assignment)
    db.session.flush()  # Get the assignment ID before commit
    print(f"[ASSIGN] Created assignment: id={assignment.id}, status={assignment.status}, type={hazard_type}")
    
    # Send notification to volunteer
    volunteer_user = volunteer.user
    hazard_title = hazard.title
    notification_message = f'You have been assigned to help with hazard: {hazard_title}. Please accept or decline the assignment.'
    
    print(f"[ASSIGN] Creating notification for user_id={volunteer_user.id}, username={volunteer_user.username}")
    
    notification = Notification(
        user_id=volunteer_user.id,
        message=notification_message,
        assignment_id=assignment.id,
        is_alert=True,
        is_read=False
    )
    db.session.add(notification)
    
    # Send WhatsApp notification if volunteer user has linked their account
    if volunteer_user.whatsapp_number:
        whatsapp_body = f"🤝 *Sentinel AI: VOLUNTEER ASSIGNMENT*\n\n{notification_message}\n\n📍 *Hazard:* {hazard_title}\n📏 *Distance:* {distance_km:.1f}km\n\n🔗 *Dashboard:* {request.url_root.rstrip('/')}/dashboard\n\n*Reply:*\n1️⃣ to *Accept*\n2️⃣ to *Reject*"
        send_whatsapp_message(volunteer_user.whatsapp_number, whatsapp_body)
    
    db.session.commit()
    
    print(f"[ASSIGN] ✓ Notification created and message sent for user={volunteer_user.username}")
    print(f"[ASSIGN] ✓ Assignment complete! Notification sent to {volunteer_user.username}")
    
    return jsonify({
        'success': True,
        'message': 'Volunteer assigned successfully',
        'assignment_id': assignment.id,
        'distance_km': distance_km,
        'notification_id': notification.id,
        'volunteer_username': volunteer_user.username
    })

@app.route("/api/coordination/assignment/<int:assignment_id>", methods=['GET'])
@login_required
def get_assignment_details(assignment_id):
    """Get assignment details for rescue completion form"""
    assignment = VolunteerAssignment.query.get_or_404(assignment_id)
    
    # Check authorization
    if assignment.volunteer.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get hazard details based on type
    h_type = getattr(assignment, 'hazard_type', 'emergency')
    if h_type == 'report':
        hazard = Report.query.get(assignment.emergency_event_id)
    else:
        hazard = EmergencyEvent.query.get(assignment.emergency_event_id)
    
    if not hazard:
        # Debug: Return detailed error info
        return jsonify({
            'error': f'Hazard ({h_type}) not found',
            'debug': {
                'assignment_id': assignment.id,
                'emergency_event_id': assignment.emergency_event_id,
                'hazard_type': h_type,
                'volunteer_id': assignment.volunteer_id,
                'status': assignment.status
            }
        }), 404
    
    return jsonify({
        'id': assignment.id,
        'hazard_title': hazard.title or (f"Report #{hazard.id}" if h_type == 'report' else 'Emergency Event'),
        'hazard_description': hazard.description or '',
        'hazard_latitude': hazard.latitude,
        'hazard_longitude': hazard.longitude,
        'assigned_at': assignment.assigned_at.isoformat(),
        'status': assignment.status,
        'experience_level': assignment.volunteer.experience_level or 'beginner'
    })

@app.route("/api/upload", methods=['POST'])
@login_required
def upload_file():
    """API endpoint for file uploads"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
        return jsonify({'error': 'Only image files (JPG, PNG, GIF, WebP) are allowed'}), 400
    
    # Save file using the utility function
    try:
        filename = save_file(file)
        file_url = f'/uploads/{filename}'
        return jsonify({
            'success': True,
            'file_url': file_url,
            'url': file_url,
            'filename': filename
        }), 200
    except Exception as e:
        return jsonify({'error': f'File upload failed: {str(e)}'}), 500

@app.route("/api/coordination/assignment/respond", methods=['POST'])
@login_required
def respond_to_assignment():
    """Accept or decline a volunteer assignment"""
    data = request.get_json()
    notification_id = data.get('notification_id')
    action = data.get('action')  # 'accept' or 'decline'
    
    if not notification_id or action not in ['accept', 'decline']:
        return jsonify({'error': 'Invalid request'}), 400
    
    notification = Notification.query.get_or_404(notification_id)
    
    # Check that the current user is the recipient of the notification
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Try to get assignment from notification first
    assignment = None
    if notification.assignment_id:
        assignment = VolunteerAssignment.query.get(notification.assignment_id)
    
    if not assignment:
        # Fallback to old behavior if no assignment_id on notification (for older data)
        volunteer = Volunteer.query.filter_by(user_id=current_user.id).first()
        if not volunteer:
            return jsonify({'error': 'Volunteer profile not found'}), 404
        
        assignment = VolunteerAssignment.query.filter_by(
            volunteer_id=volunteer.id,
            status='pending'
        ).order_by(VolunteerAssignment.assigned_at.desc()).first()
    
    if not assignment:
        return jsonify({'error': 'No pending assignment found'}), 404
    
    # Check if assignment is already processed
    if assignment.status != 'pending':
        return jsonify({'error': f'Assignment is already {assignment.status}'}), 400
    
    # Get the volunteer object
    volunteer = assignment.volunteer
    if not volunteer:
        return jsonify({'error': 'Volunteer profile not found'}), 404
        
    # Update assignment status
    if action == 'accept':
        assignment.status = 'accepted'
        assignment.accepted_at = datetime.utcnow()
        # Set volunteer to busy on acceptance
        volunteer.availability = 'busy'
        message = f'{current_user.username} has accepted the assignment'
    else:  # decline
        assignment.status = 'declined'
        message = f'{current_user.username} has declined the assignment'
    
    db.session.commit()
    
    # Send notification to the person who assigned this volunteer
    assigner = User.query.get(assignment.assigned_by)
    if assigner:
        notification_msg = Notification(
            user_id=assigner.id,
            message=message,
            is_alert=True
        )
        db.session.add(notification_msg)
        db.session.commit()
    
    # Mark the original notification as read
    notification.is_read = True
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Assignment {action}ed successfully',
        'assignment_id': assignment.id,
        'new_status': assignment.status
    })

@app.route("/api/coordination/assignment/<int:assignment_id>/complete", methods=['POST'])
@login_required
def complete_rescue_assignment(assignment_id):
    """Mark a rescue as complete with photo proof and location verification"""
    data = request.get_json()
    photo_url = data.get('photo_url')
    notes = data.get('notes', '')
    volunteer_latitude = data.get('latitude')
    volunteer_longitude = data.get('longitude')
    
    if not photo_url:
        return jsonify({'error': 'Photo proof is required'}), 400
    
    if volunteer_latitude is None or volunteer_longitude is None:
        return jsonify({'error': 'Location coordinates required'}), 400
    
    assignment = VolunteerAssignment.query.get_or_404(assignment_id)
    
    # Check that current user is the volunteer
    if assignment.volunteer.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Check that assignment is accepted
    if assignment.status != 'accepted':
        return jsonify({'error': 'Only accepted assignments can be completed'}), 400
    
    # Get the hazard location (from EmergencyEvent or Report)
    h_type = getattr(assignment, 'hazard_type', 'emergency')
    print(f"[COMPLETE] Completing assignment {assignment_id} for hazard type: {h_type}")
    
    if h_type == 'report':
        hazard = Report.query.get(assignment.emergency_event_id)
    else:
        hazard = EmergencyEvent.query.get(assignment.emergency_event_id)
    
    if not hazard:
        print(f"[COMPLETE ERROR] Hazard with ID {assignment.emergency_event_id} and type {h_type} not found")
        return jsonify({'error': 'Hazard not found'}), 404
    
    # Calculate distance from volunteer to hazard
    distance_at_completion = calculate_distance(
        hazard.latitude, hazard.longitude,
        volunteer_latitude, volunteer_longitude
    )
    print(f"[COMPLETE] Distance at completion: {distance_at_completion:.4f}km")
    
    # Check if volunteer is within 10km of hazard location (for proof of presence)
    if distance_at_completion > 10.0:  # 10.0 km
        print(f"[COMPLETE ERROR] Volunteer too far away: {distance_at_completion:.2f}km")
        return jsonify({
            'error': f'You are {distance_at_completion:.2f}km away from the hazard location. You must be within 10km to complete.',
            'required_distance_km': 10.0,
            'current_distance_km': distance_at_completion
        }), 400
    
    # Update assignment status
    assignment.status = 'completed'
    assignment.completed_at = datetime.utcnow()
    assignment.completion_photo = photo_url
    assignment.completion_notes = notes
    
    # Award points based on volunteer experience level
    volunteer = assignment.volunteer
    base_points = 100
    
    if volunteer.experience_level == 'beginner':
        points_earned = base_points
    elif volunteer.experience_level == 'intermediate':
        points_earned = int(base_points * 1.5)  # 150 points
    else:  # expert
        points_earned = int(base_points * 2)   # 200 points
    
    # Add bonus for quick completion (5 points per hour under 24 hours)
    if assignment.accepted_at:
        try:
            time_taken = assignment.completed_at - assignment.accepted_at
            hours_taken = time_taken.total_seconds() / 3600
            if hours_taken < 24:
                bonus_points = int((24 - hours_taken) / 4)  # Up to 30 bonus points
                points_earned += bonus_points
        except Exception as e:
            print(f"[COMPLETE DEBUG] Error calculating bonus: {e}")
    else:
        print(f"[COMPLETE DEBUG] No accepted_at time for assignment {assignment_id}, skipping bonus")
    
    assignment.points_earned = points_earned
    
    # Update volunteer stats
    volunteer.points += points_earned
    volunteer.total_rescues += 1
    
    # Check if this volunteer has any other active accepted assignments
    other_active = VolunteerAssignment.query.filter(
        VolunteerAssignment.volunteer_id == volunteer.id,
        VolunteerAssignment.id != assignment.id,
        VolunteerAssignment.status == 'accepted'
    ).first()
    
    # Only set back to available if no other active tasks
    if not other_active:
        volunteer.availability = 'available'
        print(f"[COMPLETE] Volunteer {volunteer.id} is now available (no more tasks)")
    else:
        print(f"[COMPLETE] Volunteer {volunteer.id} remains busy with other tasks")
    
    db.session.commit()
    print(f"[COMPLETE SUCCESS] Assignment {assignment_id} marked as completed for volunteer {volunteer.id}")
    
    # Send notification to assigner about completion
    assigner = User.query.get(assignment.assigned_by)
    if assigner:
        notification = Notification(
            user_id=assigner.id,
            message=f'{current_user.username} has completed the rescue for {hazard.title}! Earned {points_earned} points.',
            assignment_id=assignment.id,
            is_alert=True
        )
        db.session.add(notification)
        
        # Send WhatsApp notification to assigner
        if assigner.whatsapp_number:
            whatsapp_body = f"✅ *RESCUE COMPLETED*\n\nVolunteer *{current_user.username}* has successfully completed the rescue operation for: *{hazard.title}*.\n\n🏆 Points Earned: {points_earned}"
            
            # Send photo proof if available
            media_url = None
            if photo_url:
                # Use current request URL root as base URL
                base_url = request.url_root.rstrip('/')
                if photo_url.startswith('http'):
                    media_url = photo_url
                else:
                    # Check if it's a relative path
                    if photo_url.startswith('/'):
                        media_url = f"{base_url}{photo_url}"
                    else:
                        media_url = f"{base_url}/{photo_url}"
            
            send_whatsapp_message(assigner.whatsapp_number, whatsapp_body, media_url)
            
        # Send WhatsApp confirmation to the volunteer (current_user)
        if current_user.whatsapp_number:
            vol_body = f"🎉 *GREAT WORK!*\n\nYou have successfully marked the rescue as *completed*.\n\n📍 *Hazard:* {hazard.title}\n🏆 *Points Earned:* {points_earned}\n\n🔗 *Dashboard:* {request.url_root.rstrip('/')}/dashboard\n\nThank you for your service! Stay safe."
            send_whatsapp_message(current_user.whatsapp_number, vol_body)
            
        db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Rescue completed successfully!',
        'assignment_id': assignment.id,
        'points_earned': points_earned,
        'total_points': volunteer.points,
        'total_rescues': volunteer.total_rescues
    })

@app.route("/api/coordination/assignment/<int:assignment_id>/cancel", methods=['POST'])
@login_required
def cancel_rescue_assignment(assignment_id):
    """Cancel an active accepted assignment"""
    assignment = VolunteerAssignment.query.get_or_404(assignment_id)
    
    # Check that current user is the volunteer
    if assignment.volunteer.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Check that assignment is accepted
    if assignment.status != 'accepted':
        return jsonify({'error': 'Only active accepted assignments can be cancelled'}), 400
    
    # Update status
    assignment.status = 'cancelled'
    
    # Reset volunteer availability
    assignment.volunteer.availability = 'available'
    
    # Notify coordinator
    if assignment.assigned_by:
        coordinator = User.query.get(assignment.assigned_by)
        if coordinator:
            coord_notif = Notification(
                user_id=coordinator.id,
                message=f"❌ Volunteer {current_user.username} has cancelled their assignment for {assignment.hazard_type} {assignment.emergency_event_id}.",
                assignment_id=assignment.id,
                is_alert=True
            )
            db.session.add(coord_notif)
            
            # WhatsApp to coordinator if available
            if coordinator.whatsapp_number:
                try:
                    send_whatsapp_message(
                        coordinator.whatsapp_number,
                        f"❌ *ASSIGNMENT CANCELLED*\n\nVolunteer *{current_user.username}* has cancelled their accepted task.\n\nPlease assign another volunteer."
                    )
                except Exception as e:
                    print(f"Error notifying coordinator via WhatsApp: {e}")
    
    db.session.commit()
    print(f"[CANCEL SUCCESS] Assignment {assignment_id} marked as cancelled by volunteer {current_user.username}")
    
    return jsonify({
        'success': True,
        'message': 'Assignment cancelled successfully'
    })

@app.route("/api/coordination/volunteers/nearby", methods=['GET'])
@login_required
def get_nearby_volunteers():
    """Get volunteers within 50km of a hazard (emergency event or report)"""
    if current_user.role not in ['official', 'analyst', 'admin', 'coordinator']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    hazard_id = request.args.get('emergency_event_id', type=int)
    hazard_type = request.args.get('hazard_type', 'emergency', type=str)
    
    if not hazard_id:
        return jsonify({'error': 'Hazard ID required'}), 400
    
    # Get hazard details based on type
    if hazard_type == 'report':
        hazard = Report.query.get_or_404(hazard_id)
    else:
        hazard = EmergencyEvent.query.get_or_404(hazard_id)
    
    # Get all potential volunteers (including busy ones so they can get multiple requests)
    volunteers = Volunteer.query.filter(
        Volunteer.availability.in_(['available', 'busy', 'available_24_7', 'available_weekdays', 'available_weekends', 'available_evenings', 'available_limited']),
        Volunteer.latitude.isnot(None),
        Volunteer.longitude.isnot(None)
    ).all()
    
    nearby_volunteers = []
    for volunteer in volunteers:
        distance = calculate_distance(
            hazard.latitude, hazard.longitude,
            volunteer.latitude, volunteer.longitude
        )
        
        # Only include volunteers within 50km
        if distance <= 50:
            # Check if not already assigned to this specific hazard
            existing = VolunteerAssignment.query.filter(
                VolunteerAssignment.volunteer_id == volunteer.id,
                VolunteerAssignment.emergency_event_id == hazard_id,
                VolunteerAssignment.status.in_(['pending', 'accepted', 'deployed'])
            ).first()
            
            if not existing:
                nearby_volunteers.append({
                    'id': volunteer.id,
                    'name': volunteer.user.username,
                    'user_id': volunteer.user_id,
                    'skills': volunteer.skills,
                    'experience_level': volunteer.experience_level,
                    'availability': volunteer.availability,
                    'certifications': volunteer.certifications,
                    'location': volunteer.location,
                    'distance_km': round(distance, 2),
                    'is_verified': volunteer.is_verified
                })
    
    # Sort by distance
    nearby_volunteers.sort(key=lambda x: x['distance_km'])
    
    return jsonify({
        'hazard': {
            'id': hazard.id,
            'title': hazard.title,
            'latitude': hazard.latitude,
            'longitude': hazard.longitude,
            'location': hazard.location
        },
        'volunteers': nearby_volunteers
    })

@app.route("/api/coordination/assignment/<int:assignment_id>/accept", methods=['POST'])
@login_required
def accept_volunteer_assignment(assignment_id):
    """Volunteer accepts an assignment"""
    assignment = VolunteerAssignment.query.get_or_404(assignment_id)
    
    # Verify that the current user is the assigned volunteer
    if assignment.volunteer.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    assignment.status = 'accepted'
    assignment.accepted_at = datetime.utcnow()
    db.session.commit()
    
    # Send notification to the assigner
    if assignment.assigner:
        notification = Notification(
            user_id=assignment.assigner.id,
            message=f'{current_user.username} has accepted assignment for {assignment.hazard_type.capitalize()}: {assignment.emergency_event_id}',
            is_alert=True
        )
        db.session.add(notification)
    
    # Send WhatsApp location to volunteer if linked
    if current_user.whatsapp_number:
        # Get hazard location
        hazard = None
        if assignment.hazard_type == 'report':
            hazard = Report.query.get(assignment.emergency_event_id)
        else:
            hazard = EmergencyEvent.query.get(assignment.emergency_event_id)
            
        if hazard:
            loc_msg = f"📍 *Sentinel AI: Mission Location*\n\nYou've accepted the assignment for: *{hazard.title}*\n\n🗺️ *Google Maps:* https://www.google.com/maps/search/?api=1&query={hazard.latitude},{hazard.longitude}\n\nProceed with caution!"
            send_whatsapp_message(current_user.whatsapp_number, loc_msg)
            
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Assignment accepted',
        'status': 'accepted'
    })

@app.route("/api/coordination/assignment/<int:assignment_id>/decline", methods=['POST'])
@login_required
def decline_volunteer_assignment(assignment_id):
    """Volunteer declines an assignment"""
    assignment = VolunteerAssignment.query.get_or_404(assignment_id)
    
    # Verify that the current user is the assigned volunteer
    if assignment.volunteer.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    assignment.status = 'declined'
    db.session.commit()
    
    # Send notification to the assigner
    if assignment.assigner:
        notification = Notification(
            user_id=assignment.assigner.id,
            message=f'{current_user.username} has declined assignment for {assignment.event.title}',
            is_alert=True
        )
        db.session.add(notification)
        db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Assignment declined',
        'status': 'declined'
    })

@app.route("/api/coordination/emergency/<int:emergency_id>/volunteers-count")
@login_required
def get_emergency_volunteers_count(emergency_id):
    """Get count of assigned volunteers for an emergency"""
    emergency = EmergencyEvent.query.get_or_404(emergency_id)
    
    # Count accepted assignments
    accepted_count = VolunteerAssignment.query.filter_by(
        emergency_event_id=emergency_id,
        status='accepted'
    ).count()
    
    # Get assigned volunteers details
    assignments = VolunteerAssignment.query.filter_by(
        emergency_event_id=emergency_id,
        status='accepted'
    ).all()
    
    volunteers = []
    for assignment in assignments:
        volunteers.append({
            'id': assignment.volunteer.id,
            'name': assignment.volunteer.user.username,
            'skills': assignment.volunteer.skills,
            'distance_km': assignment.distance_km
        })
    
    return jsonify({
        'emergency_id': emergency_id,
        'total_volunteers': accepted_count,
        'volunteers': volunteers
    })

@app.route("/api/coordination/hazard/<string:hazard_type>/<int:hazard_id>/volunteers-count")
@login_required
def get_hazard_volunteers_count(hazard_type, hazard_id):
    """Get count of assigned volunteers for a hazard (emergency event or report)"""
    # Count accepted assignments (same for both emergency and report)
    accepted_count = VolunteerAssignment.query.filter_by(
        emergency_event_id=hazard_id,
        status='accepted'
    ).count()
    
    # Get assigned volunteers details
    assignments = VolunteerAssignment.query.filter_by(
        emergency_event_id=hazard_id,
        status='accepted'
    ).all()
    
    volunteers = []
    for assignment in assignments:
        volunteers.append({
            'id': assignment.volunteer.id,
            'name': assignment.volunteer.user.username,
            'skills': assignment.volunteer.skills,
            'distance_km': assignment.distance_km
        })
    
    return jsonify({
        'hazard_type': hazard_type,
        'hazard_id': hazard_id,
        'total_volunteers': accepted_count,
        'volunteers': volunteers
    })

@app.route("/api/leaderboard", methods=['GET'])
@login_required
def get_leaderboard():
    """Get volunteer leaderboard sorted by points with regional support"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    district = request.args.get('district', 'all', type=str)
    
    # Base query
    volunteers_query = Volunteer.query
    
    # Regional filter
    if district and district != 'all':
        volunteers_query = volunteers_query.filter(Volunteer.location.ilike(f'%{district}%'))
        
    # Get all volunteers sorted by points descending
    volunteers_query = volunteers_query.order_by(
        Volunteer.points.desc(),
        Volunteer.total_rescues.desc(),
        Volunteer.created_at.asc()
    )
    
    paginated = volunteers_query.paginate(page=page, per_page=per_page)
    
    leaderboard = []
    for idx, volunteer in enumerate(paginated.items, start=(page - 1) * per_page + 1):
        title = ""
        if idx == 1:
            if district and district != 'all':
                title = f"{district} Guardian 🎖️"
            else:
                title = "Global Sentinel 🎖️"
                
        leaderboard.append({
            'rank': idx,
            'user_id': volunteer.user.id,
            'username': volunteer.user.username,
            'title': title,
            'points': volunteer.points,
            'rescues': volunteer.total_rescues,
            'experience': volunteer.experience_level,
            'is_verified': volunteer.is_verified,
            'location': volunteer.location or 'Unknown'
        })
    
    return jsonify({
        'leaderboard': leaderboard,
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page
    })

@app.route("/api/leaderboard/user/<int:user_id>", methods=['GET'])
@login_required
def get_user_rank(user_id):
    """Get a user's rank and stats on leaderboard"""
    volunteer = Volunteer.query.filter_by(user_id=user_id).first()
    
    if not volunteer:
        return jsonify({'error': 'Volunteer not found'}), 404
    
    # Count how many volunteers have more points
    rank = Volunteer.query.filter(
        Volunteer.points > volunteer.points
    ).count() + 1
    
    return jsonify({
        'user_id': user_id,
        'username': volunteer.user.username,
        'rank': rank,
        'points': volunteer.points,
        'rescues': volunteer.total_rescues,
        'experience': volunteer.experience_level,
        'is_verified': volunteer.is_verified
    })

@app.route("/api/community_leaderboard", methods=['GET'])
@login_required
def get_community_leaderboard():
    """Get community leaderboard - All users ranked by total combined points"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Get all users with their combined points
    # User.points (from reports, eco activities, etc.) + Volunteer.points (from rescues)
    from sqlalchemy import func, case
    
    users_query = db.session.query(
        User.id,
        User.username,
        User.profile_image,
        User.role,
        User.points.label('user_points'),
        Volunteer.points.label('volunteer_points'),
        Volunteer.experience_level,
        Volunteer.is_verified,
        Volunteer.total_rescues,
        (User.points + func.coalesce(Volunteer.points, 0)).label('total_points')
    ).outerjoin(Volunteer, User.id == Volunteer.user_id)\
     .order_by((User.points + func.coalesce(Volunteer.points, 0)).desc())\
     .filter(User.role != 'admin')
    
    paginated = users_query.paginate(page=page, per_page=per_page)
    
    leaderboard = []
    for idx, result in enumerate(paginated.items, start=(page - 1) * per_page + 1):
        total_pts = result.user_points + (result.volunteer_points or 0)
        leaderboard.append({
            'rank': idx,
            'user_id': result.id,
            'username': result.username,
            'profile_image': result.profile_image,
            'role': result.role,
            'total_points': total_pts,
            'user_points': result.user_points,
            'rescue_points': result.volunteer_points or 0,
            'rescues': result.total_rescues or 0,
            'experience': result.experience_level or 'N/A',
            'is_verified': result.is_verified or False
        })
    
    return jsonify({
        'leaderboard': leaderboard,
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page
    })

@app.route("/api/coordination/assignments/active", methods=['GET'])
@login_required
def get_active_assignment():
    """Get the active accepted assignment for current volunteer"""
    # Check if user is a volunteer
    volunteer = Volunteer.query.filter_by(user_id=current_user.id).first()
    if not volunteer:
        return jsonify({'assignment_id': None})
    
    # Get the most recent accepted assignment
    assignment = VolunteerAssignment.query.filter_by(
        volunteer_id=volunteer.id,
        status='accepted'
    ).order_by(VolunteerAssignment.accepted_at.desc()).first()
    
    if assignment:
        return jsonify({'assignment_id': assignment.id})
    else:
        return jsonify({'assignment_id': None})

@app.route("/api/coordination/emergency-map")
@login_required
def emergency_map_data():
    """API endpoint for emergency map visualization"""
    if current_user.role not in ['official', 'analyst']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    emergencies = EmergencyEvent.query.filter_by(status='active').all()
    
    map_data = {
        'type': 'FeatureCollection',
        'features': []
    }
    
    for emergency in emergencies:
        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [emergency.longitude, emergency.latitude]
            },
            'properties': {
                'id': emergency.id,
                'title': emergency.title,
                'severity': emergency.severity,
                'hazard_type': emergency.hazard_type,
                'radius_km': emergency.radius_km,
                'location': emergency.location,
                'created_at': emergency.created_at.isoformat()
            }
        }
        map_data['features'].append(feature)
    
    return jsonify(map_data)

# =============================================================================
# PLASTIC REDUCTION & CARBON SAVINGS FEATURE
# =============================================================================

@app.route("/eco_tracker")
@login_required
def eco_tracker():
    """Main eco tracker dashboard"""
    # Get user's plastic reduction history
    plastic_usage = PlasticUsage.query.filter_by(user_id=current_user.id)\
        .order_by(PlasticUsage.date.desc()).limit(10).all()
    
    # Get carbon savings history
    carbon_savings = CarbonSavings.query.filter_by(user_id=current_user.id)\
        .order_by(CarbonSavings.date.desc()).limit(10).all()
    
    # Calculate totals
    total_plastic_reduced = db.session.query(func.sum(PlasticUsage.quantity))\
        .filter(PlasticUsage.user_id == current_user.id, PlasticUsage.verified == True).scalar() or 0
    
    total_carbon_saved = db.session.query(func.sum(CarbonSavings.carbon_saved))\
        .filter(CarbonSavings.user_id == current_user.id, CarbonSavings.verified == True).scalar() or 0
    
    total_eco_points = db.session.query(func.sum(PlasticUsage.points_earned))\
        .filter(PlasticUsage.user_id == current_user.id).scalar() or 0
    total_eco_points += db.session.query(func.sum(CarbonSavings.points_earned))\
        .filter(CarbonSavings.user_id == current_user.id).scalar() or 0
    
    return render_template('eco_tracker.html',
                         title='Eco Tracker',
                         plastic_usage=plastic_usage,
                         carbon_savings=carbon_savings,
                         total_plastic_reduced=total_plastic_reduced,
                         total_carbon_saved=total_carbon_saved,
                         total_eco_points=total_eco_points)

@app.route("/plastic_reduction", methods=['GET', 'POST'])
@login_required
def plastic_reduction():
    """Log plastic reduction with proof"""
    form = PlasticUsageForm()
    
    if form.validate_on_submit():
        # Handle image upload
        image_filename = save_file(form.image_proof.data) if form.image_proof.data else None
        
        # Calculate carbon savings
        carbon_saved = calculate_carbon_savings(
            form.plastic_type.data,
            form.quantity.data,
            form.unit.data
        )
        
        # Analyze image with AI if provided
        verification_score = 0.0
        verified = False
        
        if image_filename:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            ai_analysis = analyze_plastic_image(image_path)
            verification_score = ai_analysis['confidence_score']
            verified = ai_analysis['reduction_verified']
        
        # Calculate points
        points = calculate_points_for_activity(carbon_saved, 'plastic_reduction', verified)
        
        # Create plastic usage record
        plastic_usage = PlasticUsage(
            user_id=current_user.id,
            plastic_type=form.plastic_type.data,
            quantity=form.quantity.data,
            image_proof=image_filename,
            verified=verified,
            verification_score=verification_score,
            points_earned=points
        )
        db.session.add(plastic_usage)
        
        # Also create carbon savings record
        carbon_saving = CarbonSavings(
            user_id=current_user.id,
            activity_type='plastic_reduction',
            carbon_saved=carbon_saved,
            description=f"Reduced {form.quantity.data} {form.unit.data} of {form.plastic_type.data}",
            proof_type='photo' if image_filename else 'other',
            proof_file=image_filename,
            verified=verified,
            points_earned=points
        )
        db.session.add(carbon_saving)
        
        # Award points to user
        current_user.points += points
        check_and_award_badges(current_user)
        
        db.session.commit()
        
        flash(f'✅ Plastic reduction logged! +{points} points earned. Carbon saved: {carbon_saved:.2f} kg CO2', 'success')
        return redirect(url_for('eco_tracker'))
    
    return render_template('plastic_reduction.html',
                         title='Log Plastic Reduction',
                         form=form)

@app.route("/carbon_savings", methods=['GET', 'POST'])
@login_required
def carbon_savings():
    """Log carbon savings from various activities"""
    form = CarbonSavingsForm()
    
    if form.validate_on_submit():
        # Handle proof file upload
        proof_filename = save_file(form.proof_file.data) if form.proof_file.data else None
        
        # Calculate points
        points = calculate_points_for_activity(form.carbon_saved.data, form.activity_type.data)
        
        # Create carbon savings record
        carbon_saving = CarbonSavings(
            user_id=current_user.id,
            activity_type=form.activity_type.data,
            carbon_saved=form.carbon_saved.data,
            description=form.description.data,
            proof_type=form.proof_type.data,
            proof_file=proof_filename,
            verified=True if proof_filename else False,
            points_earned=points
        )
        db.session.add(carbon_saving)
        
        # Award points to user
        current_user.points += points
        check_and_award_badges(current_user)
        
        db.session.commit()
        
        flash(f'✅ Carbon savings logged! +{points} points earned.', 'success')
        return redirect(url_for('eco_tracker'))
    
    return render_template('carbon_savings.html',
                         title='Log Carbon Savings',
                         form=form)

@app.route("/api/eco_stats")
@login_required
def api_eco_stats():
    """API endpoint for eco statistics"""
    # Weekly plastic reduction
    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_plastic = db.session.query(func.sum(PlasticUsage.quantity))\
        .filter(PlasticUsage.user_id == current_user.id, 
                PlasticUsage.date >= week_ago,
                PlasticUsage.verified == True).scalar() or 0
    
    # Weekly carbon savings
    weekly_carbon = db.session.query(func.sum(CarbonSavings.carbon_saved))\
        .filter(CarbonSavings.user_id == current_user.id,
                CarbonSavings.date >= week_ago,
                CarbonSavings.verified == True).scalar() or 0
    
    # Monthly totals
    month_ago = datetime.utcnow() - timedelta(days=30)
    monthly_plastic = db.session.query(func.sum(PlasticUsage.quantity))\
        .filter(PlasticUsage.user_id == current_user.id,
                PlasticUsage.date >= month_ago,
                PlasticUsage.verified == True).scalar() or 0
    
    monthly_carbon = db.session.query(func.sum(CarbonSavings.carbon_saved))\
        .filter(CarbonSavings.user_id == current_user.id,
                CarbonSavings.date >= month_ago,
                CarbonSavings.verified == True).scalar() or 0
    
    # Activity breakdown
    activity_types = db.session.query(
        CarbonSavings.activity_type,
        func.sum(CarbonSavings.carbon_saved),
        func.count(CarbonSavings.id)
    ).filter(
        CarbonSavings.user_id == current_user.id,
        CarbonSavings.verified == True
    ).group_by(CarbonSavings.activity_type).all()
    
    activity_breakdown = []
    for activity_type, carbon_total, count in activity_types:
        activity_breakdown.append({
            'type': activity_type,
            'carbon_saved': carbon_total,
            'activity_count': count
        })
    
    return jsonify({
        'weekly_plastic_reduced': weekly_plastic,
        'weekly_carbon_saved': weekly_carbon,
        'monthly_plastic_reduced': monthly_plastic,
        'monthly_carbon_saved': monthly_carbon,
        'activity_breakdown': activity_breakdown
    })

@app.route("/eco_leaderboard")
def eco_leaderboard():
    """Leaderboard for eco-friendly activities"""
    # Get top users by carbon savings
    top_carbon_savers = db.session.query(
        User.username,
        func.sum(CarbonSavings.carbon_saved).label('total_carbon_saved'),
        func.sum(CarbonSavings.points_earned).label('total_eco_points')
    ).join(CarbonSavings).filter(
        CarbonSavings.verified == True
    ).group_by(User.id).order_by(func.sum(CarbonSavings.carbon_saved).desc()).limit(20).all()
    
    # Get top plastic reducers
    top_plastic_reducers = db.session.query(
        User.username,
        func.sum(PlasticUsage.quantity).label('total_plastic_reduced'),
        func.sum(PlasticUsage.points_earned).label('total_eco_points')
    ).join(PlasticUsage).filter(
        PlasticUsage.verified == True
    ).group_by(User.id).order_by(func.sum(PlasticUsage.quantity).desc()).limit(20).all()
    
    return render_template('eco_leaderboard.html',
                         title='Eco Leaderboard',
                         top_carbon_savers=top_carbon_savers,
                         top_plastic_reducers=top_plastic_reducers)

# Update the badge system to include eco badges
def init_badges():
    badges = [
        # Existing badges...
        {'name': 'first_reporter', 'description': 'Submitted your first report', 'icon': '🚀', 'points_required': 0},
        {'name': 'storm_watcher', 'description': 'Reported 3 storm surges', 'icon': '⛈️', 'points_required': 0},
        {'name': 'community_guardian', 'description': 'Reached 100 points', 'icon': '🛡️', 'points_required': 100},
        
        # New eco badges
        {'name': 'plastic_warrior', 'description': 'Reduced 1kg of plastic', 'icon': '♻️', 'points_required': 0},
        {'name': 'carbon_neutral', 'description': 'Saved 100kg of CO2', 'icon': '🌱', 'points_required': 0},
        {'name': 'eco_champion', 'description': 'Earned 500 eco points', 'icon': '🏆', 'points_required': 500},
        {'name': 'green_commuter', 'description': 'Used eco transport 10 times', 'icon': '🚲', 'points_required': 0},
    ]
    
    for badge_data in badges:
        if not Badge.query.filter_by(name=badge_data['name']).first():
            badge = Badge(
                name=badge_data['name'],
                description=badge_data['description'],
                icon=badge_data['icon'],
                points_required=badge_data['points_required']
            )
            db.session.add(badge)
    
    db.session.commit()

def check_and_award_badges(user):
    # Existing badge checks...
    
    # New eco badge checks
    total_plastic_reduced = db.session.query(func.sum(PlasticUsage.quantity))\
        .filter(PlasticUsage.user_id == user.id, PlasticUsage.verified == True).scalar() or 0
    if total_plastic_reduced >= 1.0:  # 1kg plastic reduced
        award_badge(user, 'plastic_warrior')
    
    total_carbon_saved = db.session.query(func.sum(CarbonSavings.carbon_saved))\
        .filter(CarbonSavings.user_id == user.id, CarbonSavings.verified == True).scalar() or 0
    if total_carbon_saved >= 100.0:  # 100kg CO2 saved
        award_badge(user, 'carbon_neutral')
    
    total_eco_points = db.session.query(func.sum(PlasticUsage.points_earned))\
        .filter(PlasticUsage.user_id == user.id).scalar() or 0
    total_eco_points += db.session.query(func.sum(CarbonSavings.points_earned))\
        .filter(CarbonSavings.user_id == user.id).scalar() or 0
    if total_eco_points >= 500:
        award_badge(user, 'eco_champion')
    
    eco_commutes = CarbonSavings.query.filter_by(
        user_id=user.id, 
        activity_type='public_transport',
        verified=True
    ).count()
    eco_commutes += CarbonSavings.query.filter_by(
        user_id=user.id,
        activity_type='cycling', 
        verified=True
    ).count()
    if eco_commutes >= 10:
        award_badge(user, 'green_commuter')

# =============================================================================
# PWA ROUTES
# =============================================================================

@app.route('/sw.js')
def service_worker():
    """Serve the service worker file"""
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest():
    """Serve the manifest file"""
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Twilio WhatsApp Webhook: Authentication, Alerts, and Volunteer Coordination"""
    incoming_msg = request.values.get('Body', '').lower().strip()
    from_number = request.values.get('From', '') # Format: whatsapp:+123456789
    
    resp = MessagingResponse()
    msg = resp.message()
    
    # Extract phone number and normalize
    clean_number = from_number.replace('whatsapp:', '').strip()
    # Normalize by removing common variations if needed
    alt_number = clean_number.replace('+', '') if clean_number.startswith('+') else f"+{clean_number}"
    
    print(f"📱 WhatsApp Webhook from: {from_number} (Clean: {clean_number}) -> Msg: {incoming_msg}")
    
    # Check if user is already linked (try both variations)
    user = User.query.filter((User.whatsapp_number == clean_number) | (User.whatsapp_number == alt_number)).first()
    if user: print(f"👤 Linked User: {user.username}")
    
    if not user:
        # Check for active auth sessions from this number
        pending_user = User.query.filter(User.whatsapp_session.isnot(None)).filter(
            User.whatsapp_session.like(f'%{from_number}%')
        ).first()
        
        # If no user matches the number, and no session exists, initiate login
        if incoming_msg in ['hi', 'hello', 'hey', 'ji', 'start', 'login']:
            msg.body("🛡️ Welcome to *Sentinel AI*! \n\nPlease enter your *username* to link your account:")
            # Create a generic entry or mark existing if needed? Actually, since many users might try,
            # we need a way to track sessions by phone number. 
            # I'll use a dedicated static dictionary for sessions if database is too slow/complex for multi-step.
            # But the user asked to store it in the app. 
            # Let's search for a user by username if they sent a name.
            return str(resp)
        
        # Try to find a user who is currently in a session with this number
        # Or better: search all users for this session marker
        all_users = User.query.filter(User.whatsapp_session.isnot(None)).all()
        active_session_user = None
        for u in all_users:
            try:
                session_data = json.loads(u.whatsapp_session)
                if session_data.get('phone') == from_number:
                    active_session_user = u
                    break
            except: continue
            
        if not active_session_user:
            # First response after 'hi': Treat msg as username
            # Case-insensitive search for username with trimming to handle accidentally saved spaces
            target_user = User.query.filter(func.lower(func.trim(User.username)) == incoming_msg.lower()).first()
            if target_user:
                target_user.whatsapp_session = json.dumps({'phone': from_number, 'step': 'awaiting_password'})
                db.session.commit()
                msg.body(f"Hello {target_user.username}! Please enter your *password* to confirm:")
            else:
                msg.body("❌ Username not found. Please try again or type 'hi' to restart.")
            return str(resp)
        else:
            # Active session found: This must be the password
            try:
                session_data = json.loads(active_session_user.whatsapp_session)
                if session_data.get('step') == 'awaiting_password':
                    if check_password_hash(active_session_user.password, request.values.get('Body', '').strip()):
                        # Success! Link number and clear session
                        active_session_user.whatsapp_number = clean_number
                        active_session_user.whatsapp_session = None
                        db.session.commit()
                        msg.body(f"✅ Success! Your WhatsApp is now linked to *{active_session_user.username}*.\n\nYou will receive real-time hazard alerts and assignment requests here.")
                    else:
                        msg.body("❌ Incorrect password. Please try again or type 'hi' to restart.")
                return str(resp)
            except Exception as e:
                print(f"WS error: {e}")
                msg.body("An error occurred. Please try again later.")
                return str(resp)

    # USER IS LINKED - Handle commands
    if incoming_msg in ['hi', 'hello', 'hey', 'ji', 'status', 'start']:
        msg.body(
            f"🛡️ *SENTINEL AI ASSISTANT*\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 *User:* {user.username}\n"
            f"✅ *Status:* Monitoring Active\n"
            f"📍 *Zone:* Within 50km radius\n\n"
            f"You will receive verified hazard alerts and assignments automatically.\n\n"
            f"💡 *Commands:*\n"
            f"• Reply *1* to Accept assignments\n"
            f"• Reply *2* to Reject assignments\n\n"
            f"🔗 *Dashboard:* {request.url_root.rstrip('/')}/dashboard"
        )
        return str(resp)

    # Handle Volunteer Assignment Accept/Reject
    if incoming_msg in ['1', 'accept', 'yes', '1️⃣']:
        print(f"🤝 Attempting ACCEPT for {user.username}")
        # Find the latest assignment (either pending or already accepted)
        assignment = VolunteerAssignment.query.join(Volunteer).filter(
            Volunteer.user_id == user.id,
            VolunteerAssignment.status.in_(['pending', 'accepted'])
        ).order_by(VolunteerAssignment.assigned_at.desc()).first()
        
        if assignment:
            print(f"✅ Found assignment {assignment.id} (Status: {assignment.status}) for hazard {assignment.emergency_event_id}")
            
            # If it was pending, mark it accepted
            if assignment.status == 'pending':
                assignment.status = 'accepted'
                assignment.accepted_at = datetime.utcnow()
                db.session.commit()
                print(f"📝 Assignment {assignment.id} marked as ACCEPTED")
            
            # Get hazard details based on type
            # Using db.session.get for better compatibility with newer SQLAlchemy
            hazard = None
            if assignment.hazard_type == 'report':
                hazard = db.session.get(Report, assignment.emergency_event_id)
            else:
                hazard = db.session.get(EmergencyEvent, assignment.emergency_event_id)
            
            if hazard:
                # Create a very clear rescue instruction message
                desc_snippet = (hazard.description or "No description provided")[:100]
                loc_msg = (
                    f"✅ *MISSION ASSIGNED*\n\n"
                    f"🚀 *Title:* {hazard.title}\n"
                    f"📝 *Info:* {desc_snippet}...\n"
                    f"📍 *Location:* {hazard.location}\n"
                    f"🌐 *Coords:* `{hazard.latitude}, {hazard.longitude}`\n\n"
                    f"🏁 *START NAVIGATION:*\n"
                    f"https://www.google.com/maps/dir/?api=1&destination={hazard.latitude},{hazard.longitude}\n\n"
                    f"⚠️ *Stay Alert:* Report status via dashboard."
                )
                
                # Use the existing msg object created at the start of the webhook
                msg.body(loc_msg)
                
                # Also attach the image if it exists for the hazard
                if hasattr(hazard, 'image_file') and hazard.image_file:
                    bypass = "?ngrok-skip-browser-warning=true"
                    try: current_base = request.url_root.rstrip('/')
                    except: current_base = "https://adele-unfocused-scientistically.ngrok-free.dev"
                    
                    if any(x in current_base for x in ['localhost', '127.0.0.1', '192.168.']):
                        current_base = "https://adele-unfocused-scientistically.ngrok-free.dev"
                        
                    img_url = f"{current_base}/static/uploads/{hazard.image_file}{bypass}"
                    # Add media to the SAME message object
                    msg.media(img_url)
                
                print(f"📡 Sent location message back to {user.username}")
            else:
                print(f"❌ Hazard not found (ID: {assignment.emergency_event_id}, Type: {assignment.hazard_type})")
                msg.body("⚠️ Error: Mission details could not be retrieved from the database. Please check your dashboard.")
        else:
            # Debugging: Why was no assignment found?
            all_v_assignments = VolunteerAssignment.query.join(Volunteer).filter(
                Volunteer.user_id == user.id
            ).order_by(VolunteerAssignment.assigned_at.desc()).limit(3).all()
            
            print(f"DEBUG: No pending/accepted assignment found for user {user.username}. Recent assignments: {[a.status for a in all_v_assignments]}")
            
            if all_v_assignments:
                msg.body(f"ℹ️ Your latest assignment (Status: {all_v_assignments[0].status}) is not in a state where I can show the location. Please check your dashboard.")
            else:
                msg.body("ℹ️ No assignments found for your account. Please check your dashboard for active missions.")
        return str(resp)

    if incoming_msg in ['2', 'reject', 'decline', 'no', '2️⃣']:
        assignment = VolunteerAssignment.query.join(Volunteer).filter(
            Volunteer.user_id == user.id,
            VolunteerAssignment.status == 'pending'
        ).order_by(VolunteerAssignment.assigned_at.desc()).first()
        
        if assignment:
            assignment.status = 'declined'
            db.session.commit()
            msg.body("❌ Assignment declined. We will notify other volunteers.")
        else:
            msg.body("ℹ️ No pending assignments found.")
        return str(resp)

    # Handle Cancellation of Accepted Assignments
    if incoming_msg in ['cancel', 'abort']:
        print(f"🚫 Attempting CANCEL for {user.username}")
        # Find active accepted assignments
        assignment = VolunteerAssignment.query.join(Volunteer).filter(
            Volunteer.user_id == user.id,
            VolunteerAssignment.status == 'accepted'
        ).order_by(VolunteerAssignment.assigned_at.desc()).first()
        
        if assignment:
            print(f"🛑 Found accepted assignment {assignment.id} to cancel")
            assignment.status = 'cancelled'
            
            # Reset volunteer availability
            assignment.volunteer.availability = 'available'
            
            # Notify coordinator
            if assignment.assigned_by:
                coordinator = User.query.get(assignment.assigned_by)
                if coordinator:
                    coord_notif = Notification(
                        user_id=coordinator.id,
                        message=f"❌ Volunteer {user.username} has cancelled their assignment for {assignment.hazard_type} {assignment.emergency_event_id}.",
                        assignment_id=assignment.id,
                        is_alert=True
                    )
                    db.session.add(coord_notif)
                    
                    # WhatsApp to coordinator if available
                    if coordinator.whatsapp_number:
                        cancel_body = f"❌ *ASSIGNMENT CANCELLED*\n\nVolunteer *{user.username}* has cancelled their accepted task.\n\n🔗 *Dashboard:* {request.url_root.rstrip('/')}/dashboard\n\nPlease assign another volunteer."
                        send_whatsapp_message(
                            coordinator.whatsapp_number,
                            cancel_body
                        )
            
            db.session.commit()
            msg.body("✅ Assignment cancelled successfully. You are now marked as available.")
        else:
            msg.body("No active accepted assignments to cancel.")
        return str(resp)

    msg.body("🤖 *Sentinel AI Assistant*\n\nType 'status' to check your link.\nReply '1' to Accept or '2' to Reject pending assignments.")
    return str(resp)

@app.route('/whatsapp-setup')
def whatsapp_setup():
    """WhatsApp Integration Setup Guide"""
    return render_template('whatsapp_setup.html', title='WhatsApp Setup')

@app.route('/offline.html')
def offline():
    """Offline fallback page"""
    return render_template('offline.html', title='Offline')

        


@app.route('/api/submit_sos', methods=['POST'])
@login_required
def submit_sos():
    try:
        data = request.get_json()
        print(f"🎤 SOS Received: {data}")
        
        transcript = data.get('transcript', '').strip()
        
        # Get coordinates from request or fallback to user's home location
        latitude = data.get('latitude')
        if latitude is None and hasattr(current_user, 'home_latitude'):
            latitude = current_user.home_latitude
            
        longitude = data.get('longitude')
        if longitude is None and hasattr(current_user, 'home_longitude'):
            longitude = current_user.home_longitude
            
        if not transcript:
            return jsonify({'success': False, 'error': 'No audio transcript provided'}), 400

        # If still None, we cannot save the report due to DB constraints
        if latitude is None or longitude is None:
            return jsonify({
                'success': False, 
                'error': 'Location coordinates are required. Please enable location services or set a home location in your profile.'
            }), 400

        timestamp_str = data.get('timestamp') # ISO string
        
        # 1. Determine Hazard Type from Keywords
        text_lower = transcript.lower()
        hazard_type = 'other' 
        
        # Extended Keyword Mapping
        keywords = {
            'tsunami': ['tsunami', 'wave', 'sea', 'ocean', 'tide', 'harbor'],
            'storm_surge': ['surge', 'water rise', 'flood', 'overflow', 'inundation'],
            'high_waves': ['wave', 'swell', 'rough sea', 'high water'],
            'coastal_flooding': ['flood', 'water', 'rain', 'drowning', 'stuck', 'entering'],
            'cyclone': ['cyclone', 'storm', 'wind', 'hurricane', 'typhoon'],
            'fire': ['fire', 'smoke', 'burn', 'flame'],
            'medical': ['injured', 'blood', 'ambulance', 'hurt', 'pain', 'doctor', 'unconscious'],
            'accident': ['crash', 'accident', 'collision', 'hit'],
            'abnormal_tide': ['tide', 'low water', 'high water']
        }
        
        for h_type, keys in keywords.items():
            if any(k in text_lower for k in keys):
                hazard_type = h_type
                break
        
        # 2. Parse Timestamp
        try:
            if timestamp_str:
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str[:-1]
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.utcnow()
        except:
            timestamp = datetime.utcnow()

        # 3. Create Report
        report = Report(
            title=f"SOS: {transcript[:20]}..." if len(transcript) > 20 else f"SOS: {transcript}",
            description=f"[VOICE REPORT] {transcript}",
            hazard_type=hazard_type,
            latitude=latitude,
            longitude=longitude,
            location=f"SOS Coordinate ({float(latitude):.4f}, {float(longitude):.4f})",
            author=current_user,
            timestamp=timestamp,
            status='active',
            verification_status='pending',
            priority='critical' # Elevate priority for SOS
        )
        
        # 4. Run Advanced AI Analysis (3-Parameter Validation)
        ai_result = analyze_report_with_ai(report)
        report.confidence_score = ai_result['confidence_score']
        report.ai_analysis = ai_result['analysis']
        
        db.session.add(report)
        db.session.commit()
        
        # Sync to CSV for real-time persistence
        sync_reports_to_csv(Report)
        
        print(f"✅ SOS Report Created: ID {report.id}")
        
        return jsonify({'success': True, 'report_id': report.id})

    except Exception as e:
        print(f"❌ SOS Error: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# COMMUNITY ACTION HUB ROUTES
# =============================================================================

@app.route("/community_hub")
@login_required
def community_hub():
    """Main community action hub dashboard"""
    # Get all upcoming events
    events = CommunityEvent.query.filter(CommunityEvent.date_time >= datetime.utcnow())\
        .order_by(CommunityEvent.date_time.asc()).all()
    
    # Categorize events
    disaster_prep_events = [e for e in events if e.event_type == 'disaster_prep']
    environment_events = [e for e in events if e.event_type == 'environment']
    social_events = [e for e in events if e.event_type == 'social']
    
    # Get user's joined events
    my_events_ids = [p.event_id for p in current_user.events_joined]
    
    return render_template('community_hub.html',
                         title='Community Action Hub',
                         disaster_prep_events=disaster_prep_events,
                         environment_events=environment_events,
                         social_events=social_events,
                         my_events_ids=my_events_ids)

@app.route("/community/create", methods=['GET', 'POST'])
@login_required
def create_community_event():
    form = CommunityEventForm()
    if form.validate_on_submit():
        image_file = None
        # Check for captured image first, then uploaded image
        captured_image = request.files.get('image_captured')
        if captured_image:
            image_file = save_file(captured_image)
        elif form.image.data:
            image_file = save_file(form.image.data)
            
        event = CommunityEvent(
            title=form.title.data,
            description=form.description.data,
            event_type=form.event_type.data,
            location=form.location.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            date_time=form.date_time.data,
            image_file=image_file,
            organizer=current_user
        )
        db.session.add(event)
        db.session.commit()
        flash('Community event created successfully!', 'success')
        return redirect(url_for('community_hub'))
        
    return render_template('create_community_event.html', title='Create Event', form=form)

@app.route("/community/join/<int:event_id>")
@login_required
def join_community_event(event_id):
    event = CommunityEvent.query.get_or_404(event_id)
    
    # Check if already joined
    participant = EventParticipant.query.filter_by(
        user_id=current_user.id,
        event_id=event.id
    ).first()
    
    if participant:
        flash('You have already joined this event.', 'info')
    else:
        participant = EventParticipant(user=current_user, event=event)
        db.session.add(participant)
        
        # Award points for joining (gamification)
        current_user.points += 5
        check_and_award_badges(current_user)
        
        db.session.commit()
        flash('You have successfully joined the event! +5 Points', 'success')

        # Send WhatsApp Notification
        if current_user.whatsapp_number:
            try:
                import urllib.parse
                event_date = event.date_time.strftime('%b %d, %Y at %I:%M %p')
                
                # Generate Google Maps link
                if event.latitude and event.longitude:
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={event.latitude},{event.longitude}"
                else:
                    # Fallback to location search if coordinates aren't set
                    location_encoded = urllib.parse.quote(event.location)
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={location_encoded}"

                message = (
                    f"🌟 *Community Action Hub: Registration Confirmed!*\n\n"
                    f"Hi {current_user.username},\n"
                    f"You have successfully joined the event: *{event.title}*\n\n"
                    f"📍 *Location:* {event.location}\n"
                    f"🕒 *Date & Time:* {event_date}\n\n"
                    f"🗺️ *Navigate with Google Maps:*\n{maps_url}\n\n"
                    f"Thank you for being an active part of our community. Together we make a difference! 🛡️🍃"
                )
                
                # Attempt to send with event image if it exists
                media_url = None
                # ... media_url logic if needed ...
                
                send_whatsapp_message(current_user.whatsapp_number, message, media_url)
                print(f"✅ WhatsApp confirmation sent to {current_user.whatsapp_number} with map link for event '{event.title}'")
            except Exception as e:
                print(f"⚠️ Failed to send WhatsApp confirmation: {e}")
        
    return redirect(url_for('community_hub'))

@app.route("/community/leave/<int:event_id>")
@login_required
def leave_community_event(event_id):
    event = CommunityEvent.query.get_or_404(event_id)
    
    participant = EventParticipant.query.filter_by(
        user_id=current_user.id,
        event_id=event.id
    ).first()
    
    if participant:
        db.session.delete(participant)
        db.session.commit()
        flash('You have left the event.', 'info')
    
    return redirect(url_for('community_hub'))
# =============================================================================
# LIFELINE: P2P RESOURCE MARKETPLACE ROUTES
# =============================================================================

@app.route("/lifeline")
@login_required
def lifeline():
    """LifeLine P2P Marketplace Dashboard"""
    # Get all open listings
    haves = ResourceListing.query.filter_by(listing_type='have', status='open').order_by(ResourceListing.created_at.desc()).all()
    needs = ResourceListing.query.filter_by(listing_type='need', status='open').order_by(ResourceListing.created_at.desc()).all()
    
    # Get user's active matches
    # Find matches where EITHER the need or have listing belongs to current user
    my_matches = ResourceMatch.query.join(ResourceListing, (ResourceMatch.need_id == ResourceListing.id) | (ResourceMatch.have_id == ResourceListing.id))\
        .filter(ResourceListing.user_id == current_user.id).order_by(ResourceMatch.created_at.desc()).all()
        
    return render_template('lifeline.html', 
                         title='LifeLine - P2P Marketplace',
                         haves=haves, 
                         needs=needs,
                         my_matches=my_matches)

@app.route("/lifeline/create", methods=['GET', 'POST'])
@login_required
def create_resource_listing():
    form = ResourceListingForm()
    if form.validate_on_submit():
        listing = ResourceListing(
            user_id=current_user.id,
            listing_type=form.listing_type.data,
            category=form.category.data,
            title=form.title.data,
            description=form.description.data,
            quantity=form.quantity.data,
            location=form.location.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            urgent=form.urgent.data
        )
        db.session.add(listing)
        db.session.commit()
        
        # Trigger Smart Matching
        match_found = find_best_matches(listing)
        
        if match_found:
            flash(f'Listing created! We found potential matches for you nearby! Check the Map.', 'success')
        else:
            flash('Resource listed successfully on LifeLine.', 'success')
            
        return redirect(url_for('lifeline'))
        
    return render_template('create_listing.html', title='Post to LifeLine', form=form)

def find_best_matches(new_listing):
    """
    Search for nearby listings of opposite type in the same category.
    Returns True if matches are found.
    """
    # Look for opposites (Have vs Need) in the same category
    target_type = 'need' if new_listing.listing_type == 'have' else 'have'
    
    potential_matches = ResourceListing.query.filter_by(
        listing_type=target_type,
        category=new_listing.category,
        status='open'
    ).all()
    
    matches_found = False
    for potential in potential_matches:
        # Simple distance check (within 10km)
        dist = calculate_distance(new_listing.latitude, new_listing.longitude, 
                                potential.latitude, potential.longitude)
        
        if dist <= 10.0:  # 10km radius
            # Create a match entry
            match = ResourceMatch(
                need_id=new_listing.id if new_listing.listing_type == 'need' else potential.id,
                have_id=new_listing.id if new_listing.listing_type == 'have' else potential.id
            )
            db.session.add(match)
            matches_found = True
            
            # Create notifications for both
            notify_match(new_listing.user, new_listing, potential)
            notify_match(potential.user, potential, new_listing)
            
    if matches_found:
        db.session.commit()
        
    return matches_found

def notify_match(user, my_listing, match_listing):
    """Send Notification and WhatsApp about match"""
    msg = f"LifeLine Match Found! Someone nearby {match_listing.listing_type}s {match_listing.title}."
    notif = Notification(user_id=user.id, message=msg)
    db.session.add(notif)
    
    # WhatsApp if available
    if user.whatsapp_number:
        wa_msg = (
            f"🎁 *LifeLine Match Found!* 🤝\n\n"
            f"Good news! We found a nearby match for your resource: *{my_listing.title}*\n\n"
            f"*{match_listing.user.username}* is offering/requesting: *{match_listing.title}*\n"
            f"📍 Location: {match_listing.location}\n\n"
            f"Check the LifeLine Map to connect and coordinate delivery. Together, we save lives! 🛡️"
        )
        send_whatsapp_message(user.whatsapp_number, wa_msg)

@app.route("/lifeline/map")
@login_required
def lifeline_map():
    """Visual map show matching connections"""
    listings = ResourceListing.query.filter_by(status='open').all()
    # Also get matches to draw lines between them
    matches = ResourceMatch.query.filter_by(status='pending').all()
    
    return render_template('lifeline_map.html', 
                         title='LifeLine Connections Map',
                         listings=[l.to_dict() for l in listings],
                         matches=[m.to_dict() for m in matches])

@app.route("/lifeline/complete_match/<int:match_id>")
@login_required
def complete_resource_match(match_id):
    match = ResourceMatch.query.get_or_404(match_id)
    match.status = 'completed'
    match.need_listing.status = 'completed'
    match.have_listing.status = 'completed'
    
    # Award points to both!
    match.need_listing.user.points += 10
    match.have_listing.user.points += 20  # Donors get more
    
    db.session.commit()
    flash('Resource match completed! Thank you for supporting the community +20 Points.', 'success')
    return redirect(url_for('lifeline'))

@app.route('/api/proxy/tgdps_map')
def proxy_tgdps_map():
    path = request.args.get('path', 'aws.jsp')
    
    # Simple validation against path traversal
    if '..' in path or path.startswith('http'):
        path = 'aws.jsp'
        
    url = f'https://tgdps.telangana.gov.in/{path}'
    try:
        response = requests.get(url, timeout=5)
        html = response.text
        # Patch relative URLs to absolute so images and styles still work
        html = html.replace('href="', 'href="https://tgdps.telangana.gov.in/')
        html = html.replace("href='", "href='https://tgdps.telangana.gov.in/")
        html = html.replace('src="', 'src="https://tgdps.telangana.gov.in/')
        html = html.replace("src='", "src='https://tgdps.telangana.gov.in/")
        
        # Patch relative paths up one dir for `livejsp/` nested pages
        html = html.replace('href="https://tgdps.telangana.gov.in/../', 'href="https://tgdps.telangana.gov.in/')
        html = html.replace('src="https://tgdps.telangana.gov.in/../', 'src="https://tgdps.telangana.gov.in/')
        
        # Un-patch absolute urls that were accidentally broken
        html = html.replace('https://tgdps.telangana.gov.in/http', 'http')
        html = html.replace('https://tgdps.telangana.gov.in//', '//')
        
        # Inject custom CSS to hide all website headers, footers and menus to show ONLY the map
        css_injection = """
        <style>
            /* Hide the main headers, menus, links row, and dropdown controls */
            #header_color, 
            #heading_front, 
            #footer, 
            body > table:first-of-type,
            body > div#body > table[bgcolor="#FFFFFF"],
            #dp_content_map1 > div[align="left"] {
                display: none !important;
            }
            
            body, #body {
                background: white !important;
                background-color: white !important;
                padding-top: 20px;
            }
            
            #aws_ts {
                margin-top: 0 !important;
            }
        </style>
        """
        
        # Only inject jQuery if the page is missing it to prevent overwriting existing plugins like maphilight
        if 'jquery-3' not in html.lower() and 'jquery.min.js' not in html.lower() and 'code.jquery.com' not in html.lower():
            jquery_injection = '<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>\n'
            # Inject right at the beginning of the head so it exists before any mapping scripts run
            if '<head>' in html:
                html = html.replace('<head>', '<head>\n' + jquery_injection, 1)
            else:
                html = jquery_injection + html
            
        html = html.replace('</head>', css_injection + '\n</head>')
        
        return Response(html, mimetype='text/html')
    except Exception as e:
        return f"Error loading map: {str(e)}", 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_badges()  # Initialize badges
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5001)

