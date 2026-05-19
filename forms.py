from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, SelectField, FloatField, IntegerField, DateTimeField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange
from models import User

class MultilingualForm(FlaskForm):
    """Base form class that provides multilingual support"""
    
    def get_translated_label(self, field_name, default_label):
        """Get translated label for form field"""
        try:
            # Import translate here to avoid circular imports
            from app import translate
            
            # Try to get translation for the specific field
            translation_key = f'form_{self.__class__.__name__.lower()}_{field_name}'
            translated = translate(translation_key)
            if translated != translation_key:  # If translation exists
                return translated
        except:
            pass
        
        # Fallback to general field translation
        try:
            from app import translate
            general_key = f'form_field_{field_name}'
            translated = translate(general_key)
            if translated != general_key:
                return translated
        except:
            pass
        
        # If no translation found, return the default label
        return default_label

class RegistrationForm(MultilingualForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.username.label.text = self.get_translated_label('username', 'Username')
            self.email.label.text = self.get_translated_label('email', 'Email')
            self.password.label.text = self.get_translated_label('password', 'Password')
            self.confirm_password.label.text = self.get_translated_label('confirm_password', 'Confirm Password')
            self.submit.label.text = translate('register')
        except ImportError:
            # Fallback to English if translation system not available
            pass

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            try:
                from app import translate
                raise ValidationError(translate('username_taken'))
            except ImportError:
                raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            try:
                from app import translate
                raise ValidationError(translate('email_taken'))
            except ImportError:
                raise ValidationError('That email is taken. Please choose a different one.')

class LoginForm(MultilingualForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.email.label.text = self.get_translated_label('email', 'Email')
            self.password.label.text = self.get_translated_label('password', 'Password')
            self.remember.label.text = translate('remember_me')
            self.submit.label.text = translate('login')
        except ImportError:
            pass

class ReportForm(MultilingualForm):
    # Hazard types with translations
    hazard_types = [
        ('tsunami', 'Tsunami'),
        ('storm_surge', 'Storm Surge'),
        ('high_waves', 'High Waves'),
        ('swell_surge', 'Swell Surge'),
        ('coastal_flooding', 'Coastal Flooding'),
        ('abnormal_tide', 'Abnormal Tide'),
        ('other', 'Other')
    ]
    
    def get_translated_hazard_types(self):
        """Get hazard types with translated labels"""
        try:
            from app import translate
            return [
                (hazard_type, translate(hazard_type)) 
                for hazard_type, _ in self.hazard_types
            ]
        except ImportError:
            return self.hazard_types
    
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    hazard_type = SelectField('Hazard Type', choices=[], validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired()])
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    photo = FileField('Upload Photo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'])])
    video = FileField('Upload Video', validators=[FileAllowed(['mp4', 'mov', 'avi'])])
    submit = SubmitField('Submit Report')

    def __init__(self, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        # Set translated choices for hazard type
        self.hazard_type.choices = self.get_translated_hazard_types()
        
        # Set translated labels
        try:
            from app import translate
            self.title.label.text = self.get_translated_label('title', 'Title')
            self.description.label.text = self.get_translated_label('description', 'Description')
            self.hazard_type.label.text = self.get_translated_label('hazard_type', 'Hazard Type')
            self.location.label.text = self.get_translated_label('location', 'Location')
            self.latitude.label.text = self.get_translated_label('latitude', 'Latitude')
            self.longitude.label.text = self.get_translated_label('longitude', 'Longitude')
            self.photo.label.text = self.get_translated_label('photo', 'Upload Photo')
            self.video.label.text = self.get_translated_label('video', 'Upload Video')
            self.submit.label.text = translate('submit_report')
        except ImportError:
            pass

class ProfileForm(MultilingualForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    profile_image = FileField('Profile Photo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'])])
    submit = SubmitField('Update Profile')

    def __init__(self, original_username, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        
        # Set translated labels
        try:
            from app import translate
            self.username.label.text = self.get_translated_label('username', 'Username')
            self.bio.label.text = self.get_translated_label('bio', 'Bio')
            self.profile_image.label.text = self.get_translated_label('profile_image', 'Profile Photo')
            self.submit.label.text = translate('update_profile')
        except ImportError:
            pass

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                try:
                    from app import translate
                    raise ValidationError(translate('username_taken'))
                except ImportError:
                    raise ValidationError('That username is taken. Please choose a different one.')
            
class LocationForm(MultilingualForm):
    home_latitude = FloatField('Home Latitude', validators=[Optional()])
    home_longitude = FloatField('Home Longitude', validators=[Optional()])
    submit = SubmitField('Save Location')

    def __init__(self, *args, **kwargs):
        super(LocationForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.home_latitude.label.text = self.get_translated_label('home_latitude', 'Home Latitude')
            self.home_longitude.label.text = self.get_translated_label('home_longitude', 'Home Longitude')
            self.submit.label.text = translate('save_location')
        except ImportError:
            pass

class AlertPreferencesForm(MultilingualForm):
    tsunami = BooleanField('Tsunami Alerts', default=True)
    storm_surge = BooleanField('Storm Surge Alerts', default=True)
    high_waves = BooleanField('High Waves Alerts', default=True)
    swell_surge = BooleanField('Swell Surge Alerts', default=True)
    coastal_flooding = BooleanField('Coastal Flooding Alerts', default=True)
    abnormal_tide = BooleanField('Abnormal Tide Alerts', default=True)
    other = BooleanField('Other Hazards Alerts', default=True)
    submit = SubmitField('Save Preferences')

    def __init__(self, *args, **kwargs):
        super(AlertPreferencesForm, self).__init__(*args, **kwargs)
        # Set translated labels using hazard type translations
        try:
            from app import translate
            self.tsunami.label.text = translate('tsunami') + ' ' + translate('alerts')
            self.storm_surge.label.text = translate('storm_surge') + ' ' + translate('alerts')
            self.high_waves.label.text = translate('high_waves') + ' ' + translate('alerts')
            self.swell_surge.label.text = translate('swell_surge') + ' ' + translate('alerts')
            self.coastal_flooding.label.text = translate('coastal_flooding') + ' ' + translate('alerts')
            self.abnormal_tide.label.text = translate('abnormal_tide') + ' ' + translate('alerts')
            self.other.label.text = translate('other') + ' ' + translate('alerts')
            self.submit.label.text = translate('save_preferences')
        except ImportError:
            pass




# =============================================================================
# GOVERNMENT-NGO COORDINATION PLATFORM FORMS
# =============================================================================

class AgencyForm(MultilingualForm):
    """Form for registering and managing agencies"""
    name = StringField('Agency Name', validators=[DataRequired(), Length(max=100)])
    type = SelectField('Agency Type', choices=[
        ('government', 'Government'),
        ('ngo', 'NGO'),
        ('medical', 'Medical'),
        ('rescue', 'Rescue'),
        ('logistics', 'Logistics'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    contact_email = StringField('Contact Email', validators=[Optional(), Email()])
    contact_phone = StringField('Contact Phone', validators=[Optional()])
    resources = TextAreaField('Available Resources', validators=[Optional()])
    capabilities = TextAreaField('Capabilities', validators=[Optional()])
    submit = SubmitField('Register Agency')

    def __init__(self, *args, **kwargs):
        super(AgencyForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.name.label.text = self.get_translated_label('name', 'Agency Name')
            self.type.label.text = self.get_translated_label('type', 'Agency Type')
            self.contact_email.label.text = self.get_translated_label('contact_email', 'Contact Email')
            self.contact_phone.label.text = self.get_translated_label('contact_phone', 'Contact Phone')
            self.resources.label.text = self.get_translated_label('resources', 'Available Resources')
            self.capabilities.label.text = self.get_translated_label('capabilities', 'Capabilities')
            self.submit.label.text = translate('register_agency')
            
            # Set translated choices
            self.type.choices = [
                ('government', translate('government_agency')),
                ('ngo', translate('ngo_agency')),
                ('medical', translate('medical_agency')),
                ('rescue', translate('rescue_agency')),
                ('logistics', translate('logistics_agency')),
                ('other', translate('other_agency'))
            ]
        except ImportError:
            pass

class EmergencyEventForm(MultilingualForm):
    """Form for creating emergency events"""
    title = StringField('Event Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired()])
    hazard_type = SelectField('Hazard Type', choices=[
        ('tsunami', 'Tsunami'),
        ('storm_surge', 'Storm Surge'),
        ('high_waves', 'High Waves'),
        ('coastal_flooding', 'Coastal Flooding'),
        ('cyclone', 'Cyclone'),
        ('earthquake', 'Earthquake'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    severity = SelectField('Severity', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired()])
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    radius_km = FloatField('Affected Radius (km)', default=10.0, validators=[NumberRange(min=1)])
    submit = SubmitField('Create Emergency Event')

    def __init__(self, *args, **kwargs):
        super(EmergencyEventForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.title.label.text = self.get_translated_label('title', 'Event Title')
            self.description.label.text = self.get_translated_label('description', 'Description')
            self.hazard_type.label.text = self.get_translated_label('hazard_type', 'Hazard Type')
            self.severity.label.text = self.get_translated_label('severity', 'Severity')
            self.location.label.text = self.get_translated_label('location', 'Location')
            self.latitude.label.text = self.get_translated_label('latitude', 'Latitude')
            self.longitude.label.text = self.get_translated_label('longitude', 'Longitude')
            self.radius_km.label.text = self.get_translated_label('radius_km', 'Affected Radius (km)')
            self.submit.label.text = translate('create_emergency_event')
            
            # Set translated choices
            self.hazard_type.choices = [
                ('tsunami', translate('tsunami')),
                ('storm_surge', translate('storm_surge')),
                ('high_waves', translate('high_waves')),
                ('coastal_flooding', translate('coastal_flooding')),
                ('cyclone', translate('cyclone')),
                ('earthquake', translate('earthquake')),
                ('other', translate('other'))
            ]
            self.severity.choices = [
                ('low', translate('low_severity')),
                ('medium', translate('medium_severity')),
                ('high', translate('high_severity')),
                ('critical', translate('critical_severity'))
            ]
        except ImportError:
            pass

class ResourceAllocationForm(MultilingualForm):
    """Form for allocating resources to emergency events"""
    emergency_event_id = SelectField('Emergency Event', coerce=int, validators=[DataRequired()])
    agency_id = SelectField('Agency', coerce=int, validators=[DataRequired()])
    resource_type = SelectField('Resource Type', choices=[
        ('medical', 'Medical Supplies'),
        ('food', 'Food & Water'),
        ('shelter', 'Shelter Materials'),
        ('rescue', 'Rescue Equipment'),
        ('communication', 'Communication Equipment'),
        ('transport', 'Transportation'),
        ('personnel', 'Personnel'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    quantity = IntegerField('Quantity', default=1, validators=[NumberRange(min=1)])
    units = StringField('Units', validators=[Optional()])
    submit = SubmitField('Allocate Resources')

    def __init__(self, *args, **kwargs):
        super(ResourceAllocationForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.emergency_event_id.label.text = self.get_translated_label('emergency_event_id', 'Emergency Event')
            self.agency_id.label.text = self.get_translated_label('agency_id', 'Agency')
            self.resource_type.label.text = self.get_translated_label('resource_type', 'Resource Type')
            self.quantity.label.text = self.get_translated_label('quantity', 'Quantity')
            self.units.label.text = self.get_translated_label('units', 'Units')
            self.submit.label.text = translate('allocate_resources')
            
            # Set translated choices
            self.resource_type.choices = [
                ('medical', translate('medical_supplies')),
                ('food', translate('food_water')),
                ('shelter', translate('shelter_materials')),
                ('rescue', translate('rescue_equipment')),
                ('communication', translate('communication_equipment')),
                ('transport', translate('transportation')),
                ('personnel', translate('personnel')),
                ('other', translate('other_resources'))
            ]
        except ImportError:
            pass

class VolunteerRegistrationForm(MultilingualForm):
    """Form for volunteers to register their skills and availability"""
    skills = TextAreaField('Skills & Expertise', validators=[DataRequired()])
    experience_level = SelectField('Experience Level', choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert')
    ], validators=[DataRequired()])
    certifications = TextAreaField('Certifications', validators=[Optional()])
    location = StringField('Current Location', validators=[Optional()])
    latitude = FloatField('Latitude', validators=[Optional()])
    longitude = FloatField('Longitude', validators=[Optional()])
    availability = SelectField('Availability', choices=[
        ('available_24_7', 'Available 24/7'),
        ('available_weekdays', 'Available Weekdays'),
        ('available_weekends', 'Available Weekends'),
        ('available_evenings', 'Available Evenings'),
        ('available_limited', 'Limited Availability'),
        ('unavailable', 'Unavailable')
    ], validators=[DataRequired()])
    submit = SubmitField('Register as Volunteer')

    def __init__(self, *args, **kwargs):
        super(VolunteerRegistrationForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.skills.label.text = self.get_translated_label('skills', 'Skills & Expertise')
            self.experience_level.label.text = self.get_translated_label('experience_level', 'Experience Level')
            self.certifications.label.text = self.get_translated_label('certifications', 'Certifications')
            self.location.label.text = self.get_translated_label('location', 'Current Location')
            self.latitude.label.text = self.get_translated_label('latitude', 'Latitude')
            self.longitude.label.text = self.get_translated_label('longitude', 'Longitude')
            self.availability.label.text = self.get_translated_label('availability', 'Availability')
            self.submit.label.text = translate('register_volunteer')
            
            # Set translated choices
            self.experience_level.choices = [
                ('beginner', translate('beginner_level')),
                ('intermediate', translate('intermediate_level')),
                ('expert', translate('expert_level'))
            ]
            self.availability.choices = [
                ('available_24_7', translate('available_24_7') or 'Available 24/7'),
                ('available_weekdays', translate('available_weekdays') or 'Available Weekdays'),
                ('available_weekends', translate('available_weekends') or 'Available Weekends'),
                ('available_evenings', translate('available_evenings') or 'Available Evenings'),
                ('available_limited', translate('available_limited') or 'Limited Availability'),
                ('unavailable', translate('unavailable_status') or 'Unavailable')
            ]
        except ImportError:
            pass

class VolunteerAssignmentForm(MultilingualForm):
    """Form for assigning volunteers to emergency events"""
    volunteer_id = SelectField('Volunteer', coerce=int, validators=[DataRequired()])
    emergency_event_id = SelectField('Emergency Event', coerce=int, validators=[DataRequired()])
    role = StringField('Role/Assignment', validators=[DataRequired()])
    submit = SubmitField('Assign Volunteer')

    def __init__(self, *args, **kwargs):
        super(VolunteerAssignmentForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.volunteer_id.label.text = self.get_translated_label('volunteer_id', 'Volunteer')
            self.emergency_event_id.label.text = self.get_translated_label('emergency_event_id', 'Emergency Event')
            self.role.label.text = self.get_translated_label('role', 'Role/Assignment')
            self.submit.label.text = translate('assign_volunteer')
        except ImportError:
            pass

class SituationReportForm(MultilingualForm):
    """Form for creating situation reports"""
    emergency_event_id = SelectField('Emergency Event', coerce=int, validators=[DataRequired()])
    title = StringField('Report Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Report Content', validators=[DataRequired()])
    priority = SelectField('Priority', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], validators=[DataRequired()])
    report_type = SelectField('Report Type', choices=[
        ('damage_assessment', 'Damage Assessment'),
        ('resource_status', 'Resource Status'),
        ('weather', 'Weather Update'),
        ('evacuation', 'Evacuation Status'),
        ('medical', 'Medical Update'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Situation Report')

    def __init__(self, *args, **kwargs):
        super(SituationReportForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.emergency_event_id.label.text = self.get_translated_label('emergency_event_id', 'Emergency Event')
            self.title.label.text = self.get_translated_label('title', 'Report Title')
            self.content.label.text = self.get_translated_label('content', 'Report Content')
            self.priority.label.text = self.get_translated_label('priority', 'Priority')
            self.report_type.label.text = self.get_translated_label('report_type', 'Report Type')
            self.submit.label.text = translate('create_situation_report')
            
            # Set translated choices
            self.priority.choices = [
                ('low', translate('low_priority')),
                ('medium', translate('medium_priority')),
                ('high', translate('high_priority')),
                ('critical', translate('critical_priority'))
            ]
            self.report_type.choices = [
                ('damage_assessment', translate('damage_assessment')),
                ('resource_status', translate('resource_status')),
                ('weather', translate('weather_update')),
                ('evacuation', translate('evacuation_status')),
                ('medical', translate('medical_update')),
                ('other', translate('other_report_type'))
            ]
        except ImportError:
            pass

class CoordinationSettingsForm(MultilingualForm):
    """Form for coordination platform settings"""
    auto_assign_volunteers = BooleanField('Auto-assign Volunteers by Skills', default=True)
    notify_all_agencies = BooleanField('Notify All Agencies for Critical Events', default=True)
    enable_resource_tracking = BooleanField('Enable Real-time Resource Tracking', default=True)
    enable_volunteer_matching = BooleanField('Enable Volunteer Skill Matching', default=True)
    submit = SubmitField('Save Settings')

    def __init__(self, *args, **kwargs):
        super(CoordinationSettingsForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.auto_assign_volunteers.label.text = translate('auto_assign_volunteers')
            self.notify_all_agencies.label.text = translate('notify_all_agencies')
            self.enable_resource_tracking.label.text = translate('enable_resource_tracking')
            self.enable_volunteer_matching.label.text = translate('enable_volunteer_matching')
            self.submit.label.text = translate('save_settings')
        except ImportError:
            pass

# =============================================================================
# ADDITIONAL UTILITY FORMS
# =============================================================================

class LanguageSelectionForm(MultilingualForm):
    language = SelectField('Language', choices=[
        ('en', 'English'),
        ('ta', 'Tamil'),
        ('hi', 'Hindi'),
        ('te', 'Telugu'),
        ('ml', 'Malayalam'),
        ('kn', 'Kannada')
    ], validators=[DataRequired()])
    submit = SubmitField('Change Language')

    def __init__(self, *args, **kwargs):
        super(LanguageSelectionForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.language.label.text = translate('language')
            self.submit.label.text = translate('change_language')
            
            # Set translated choices
            self.language.choices = [
                ('en', translate('english')),
                ('ta', translate('tamil')),
                ('hi', translate('hindi')),
                ('te', translate('telugu')),
                ('ml', translate('malayalam')),
                ('kn', translate('kannada'))
            ]
        except ImportError:
            pass

class SearchForm(MultilingualForm):
    query = StringField('Search', validators=[DataRequired()])
    submit = SubmitField('Search')

    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.query.label.text = translate('search')
            self.submit.label.text = translate('search')
        except ImportError:
            pass

class CommentForm(MultilingualForm):
    text = TextAreaField('Comment', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Post Comment')

    def __init__(self, *args, **kwargs):
        super(CommentForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.text.label.text = translate('comment')
            self.submit.label.text = translate('post_comment')
        except ImportError:
            pass

class NotificationSettingsForm(MultilingualForm):
    email_notifications = BooleanField('Email Notifications', default=True)
    push_notifications = BooleanField('Push Notifications', default=True)
    sms_notifications = BooleanField('SMS Notifications', default=False)
    submit = SubmitField('Save Settings')

    def __init__(self, *args, **kwargs):
        super(NotificationSettingsForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.email_notifications.label.text = translate('email_notifications')
            self.push_notifications.label.text = translate('push_notifications')
            self.sms_notifications.label.text = translate('sms_notifications')
            self.submit.label.text = translate('save_settings')
        except ImportError:
            pass

class RequestResetForm(MultilingualForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

    def __init__(self, *args, **kwargs):
        super(RequestResetForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.email.label.text = self.get_translated_label('email', 'Email')
            self.submit.label.text = translate('request_password_reset')
        except ImportError:
            pass

class ResetPasswordForm(MultilingualForm):
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

    def __init__(self, *args, **kwargs):
        super(ResetPasswordForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.password.label.text = self.get_translated_label('password', 'Password')
            self.confirm_password.label.text = self.get_translated_label('confirm_password', 'Confirm Password')
            self.submit.label.text = translate('reset_password')
        except ImportError:
            pass


# Add these new forms

class PlasticUsageForm(FlaskForm):
    plastic_type = SelectField('Plastic Type', choices=[
        ('plastic_bottle', 'Plastic Bottle'),
        ('plastic_bag', 'Plastic Bag'),
        ('straw', 'Plastic Straw'),
        ('food_container', 'Food Container'),
        ('cutlery', 'Plastic Cutlery'),
        ('packaging', 'Product Packaging'),
        ('other', 'Other Plastic')
    ], validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0.1)])
    unit = SelectField('Unit', choices=[
        ('pieces', 'Pieces'),
        ('grams', 'Grams'),
        ('kg', 'Kilograms')
    ], validators=[DataRequired()])
    image_proof = FileField('Upload Proof Photo', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    description = TextAreaField('Additional Details')
    submit = SubmitField('Submit Plastic Reduction')

class CarbonSavingsForm(FlaskForm):
    activity_type = SelectField('Eco-Friendly Activity', choices=[
        ('plastic_reduction', 'Plastic Usage Reduction'),
        ('public_transport', 'Used Public Transport'),
        ('cycling', 'Cycling Instead of Driving'),
        ('energy_saving', 'Energy Saving'),
        ('water_saving', 'Water Conservation'),
        ('waste_recycling', 'Waste Recycling'),
        ('tree_planting', 'Tree Planting'),
        ('other', 'Other Eco Activity')
    ], validators=[DataRequired()])
    carbon_saved = FloatField('Carbon Saved (kg CO2)', validators=[DataRequired(), NumberRange(min=0.1)])
    description = TextAreaField('Activity Description', validators=[DataRequired()])
    proof_type = SelectField('Proof Type', choices=[
        ('photo', 'Photo Evidence'),
        ('receipt', 'Receipt/Bill'),
        ('tracking', 'App Tracking'),
        ('other', 'Other Proof')
    ])
    proof_file = FileField('Upload Proof', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'pdf'])])
    submit = SubmitField('Submit Carbon Savings')

class EmergencyExportForm(MultilingualForm):
    """Form for exporting emergency coordination data"""
    export_format = SelectField(
        'Export Format',
        choices=[
            ('json', 'JSON Data'),
            ('csv', 'CSV Spreadsheet'),
            ('pdf', 'PDF Report'),
            ('excel', 'Excel Spreadsheet')
        ],
        default='json',
        validators=[DataRequired()]
    )
    include_agencies = BooleanField('Include Agency Data', default=True)
    include_resources = BooleanField('Include Resource Allocations', default=True)
    include_volunteers = BooleanField('Include Volunteer Assignments', default=True)
    include_reports = BooleanField('Include Situation Reports', default=True)
    submit = SubmitField('Export Coordination Data')

    def __init__(self, *args, **kwargs):
        super(EmergencyExportForm, self).__init__(*args, **kwargs)
        # Set translated labels
        try:
            from app import translate
            self.export_format.label.text = self.get_translated_label('export_format', 'Export Format')
            self.include_agencies.label.text = translate('include_agencies')
            self.include_resources.label.text = translate('include_resources')
            self.include_volunteers.label.text = translate('include_volunteers')
            self.include_reports.label.text = translate('include_reports')
            self.submit.label.text = translate('export_coordination_data')
            
            # Set translated choices
            self.export_format.choices = [
                ('json', translate('json_data')),
                ('csv', translate('csv_spreadsheet')),
                ('pdf', translate('pdf_report')),
                ('excel', translate('excel_spreadsheet'))
            ]
        except ImportError:
            pass
class CommunityEventForm(FlaskForm):
    title = StringField('Event Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    event_type = SelectField('Event Type', choices=[
        ('disaster_prep', 'Disaster Prep (e.g., Sandbag filling)'),
        ('environment', 'Environment (e.g., Beach cleanup)'),
        ('social', 'Social (e.g., Food distribution)')
    ], validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired()])
    latitude = FloatField('Latitude', validators=[Optional()])
    longitude = FloatField('Longitude', validators=[Optional()])
    # HTML5 datetime-local returns YYYY-MM-DDTHH:MM
    date_time = DateTimeField('Date & Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    image = FileField('Event Image', validators=[FileAllowed(['jpg', 'jpeg', 'png'])])
    submit = SubmitField('Create Event')

class ResourceListingForm(FlaskForm):
    listing_type = SelectField('Listing Type', choices=[
        ('have', 'Donor (I Have Spare Resources)'),
        ('need', 'Requester (I Need Help/Resources)')
    ], validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('medical', 'Medical (Medicine, First Aid, Insulin)'),
        ('food', 'Food (Meals, Baby Formula, Dry Fruits)'),
        ('water', 'Water (Drinking Water, Filtration)'),
        ('shelter', 'Shelter (Blankets, Tents, Sleeping Bags)'),
        ('gear', 'Gear (Generator, Flashlights, Batteries)'),
        ('transport', 'Transport (Boat, 4x4 Vehicle, Drone)'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    title = StringField('Resource Title', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[DataRequired()])
    quantity = StringField('Quantity', validators=[Optional()])
    location = StringField('Location', validators=[DataRequired()])
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    urgent = BooleanField('Critical / Urgent')
    submit = SubmitField('Post to LifeLine')
