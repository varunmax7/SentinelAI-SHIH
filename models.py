from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import os
import json

db = SQLAlchemy()

# Association table for followers/following
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='citizen')
    profile_image = db.Column(db.String(100), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    push_token = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(10), default='en')
    whatsapp_number = db.Column(db.String(20), nullable=True, unique=True)
    whatsapp_session = db.Column(db.Text, nullable=True) # Used for multi-step WhatsApp login/interactions
    
    # Location fields for alert system
    home_latitude = db.Column(db.Float, nullable=True)
    home_longitude = db.Column(db.Float, nullable=True)
    alert_preferences = db.Column(db.JSON, default=lambda: json.dumps({
        'tsunami': True,
        'storm_surge': True,
        'high_waves': True,
        'swell_surge': True,
        'coastal_flooding': True,
        'abnormal_tide': True,
        'other': True
    }))
    
    # Followers/Following system
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    )
    
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
    
    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
    
    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id
        ).count() > 0
    
    def get_alert_preferences(self):
        """Get alert preferences as a dictionary - always returns a valid dict"""
        default_preferences = {
            'tsunami': True,
            'storm_surge': True,
            'high_waves': True,
            'swell_surge': True,
            'coastal_flooding': True,
            'abnormal_tide': True,
            'other': True
        }
        
        if self.alert_preferences is None:
            return default_preferences
            
        if isinstance(self.alert_preferences, str):
            try:
                # Try to parse JSON string
                parsed = json.loads(self.alert_preferences)
                if isinstance(parsed, dict):
                    # Ensure all expected keys are present
                    for key in default_preferences.keys():
                        if key not in parsed:
                            parsed[key] = default_preferences[key]
                    return parsed
                else:
                    return default_preferences
            except (json.JSONDecodeError, TypeError):
                return default_preferences
        elif isinstance(self.alert_preferences, dict):
            # Ensure all expected keys are present
            result = self.alert_preferences.copy()
            for key in default_preferences.keys():
                if key not in result:
                    result[key] = default_preferences[key]
            return result
        else:
            return default_preferences
    
    def set_alert_preferences(self, preferences):
        """Set alert preferences from a dictionary"""
        # Ensure we have all the required keys
        default_preferences = {
            'tsunami': True,
            'storm_surge': True,
            'high_waves': True,
            'swell_surge': True,
            'coastal_flooding': True,
            'abnormal_tide': True,
            'other': True
        }
        
        # Merge with defaults to ensure all keys are present
        merged_preferences = default_preferences.copy()
        if preferences:
            merged_preferences.update(preferences)
        
        self.alert_preferences = json.dumps(merged_preferences)
    
    def to_dict(self):
        """Convert user object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'profile_image': self.profile_image,
            'points': self.points,
            'level': self.level,
            'bio': self.bio,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'home_latitude': self.home_latitude,
            'home_longitude': self.home_longitude,
            'language': self.language,
            'alert_preferences': self.get_alert_preferences()
        }
    
    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    hazard_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    image_file = db.Column(db.String(100), nullable=True)
    video_file = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, resolved
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical

    # Alert system fields
    alert_radius = db.Column(db.Float, default=0.0)  # Radius in kilometers
    alert_sent = db.Column(db.Boolean, default=False)
    alert_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Verification system fields
    verified = db.Column(db.Boolean, default=False)
    confidence_score = db.Column(db.Float, default=0.0)
    ai_analysis = db.Column(db.Text, nullable=True)
    verification_status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    rejection_reason = db.Column(db.Text, nullable=True)
    scheduled_deletion = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    
    # Social engagement metrics
    likes_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    shares_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    is_local_verified = db.Column(db.Boolean, default=False)
    
    # Define relationships
    author = db.relationship('User', backref='reports', foreign_keys=[user_id])
    verifier = db.relationship('User', backref='verified_reports', foreign_keys=[verified_by])
    
    def to_dict(self):
        """Convert report object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'hazard_type': self.hazard_type,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'image_file': self.image_file,
            'video_file': self.video_file,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'author_username': self.author.username if self.author else 'Unknown',
            'verified': self.verified,
            'confidence_score': self.confidence_score,
            'ai_analysis': self.ai_analysis,
            'verification_status': self.verification_status,
            'status': self.status,
            'priority': self.priority,
            'rejection_reason': self.rejection_reason,
            'scheduled_deletion': self.scheduled_deletion.isoformat() if self.scheduled_deletion else None,
            'verified_by': self.verified_by,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'likes_count': self.likes_count,
            'comments_count': self.comments_count,
            'shares_count': self.shares_count,
            'views_count': self.views_count,
            'is_local_verified': self.is_local_verified,
            'alert_radius': self.alert_radius,
            'alert_sent': self.alert_sent,
            'alert_sent_at': self.alert_sent_at.isoformat() if self.alert_sent_at else None
        }
    
    def __repr__(self):
        return f"Report('{self.title}', '{self.timestamp}')"

# =============================================================================
# PLASTIC REDUCTION & CARBON SAVINGS MODELS
# =============================================================================

class PlasticUsage(db.Model):
    __tablename__ = 'plastic_usage'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    plastic_type = db.Column(db.String(100), nullable=False)  # bottle, bag, straw, etc.
    quantity = db.Column(db.Float, nullable=False)  # in grams or pieces
    unit = db.Column(db.String(20), default='pieces')  # pieces, grams, kg
    image_proof = db.Column(db.String(200))  # filename of uploaded proof
    description = db.Column(db.Text)
    verified = db.Column(db.Boolean, default=False)
    verification_score = db.Column(db.Float, default=0.0)  # AI confidence score
    points_earned = db.Column(db.Integer, default=0)
    
    user = db.relationship('User', backref=db.backref('plastic_usage', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_username': self.user.username if self.user else 'Unknown',
            'date': self.date.isoformat(),
            'plastic_type': self.plastic_type,
            'quantity': self.quantity,
            'unit': self.unit,
            'image_proof': self.image_proof,
            'description': self.description,
            'verified': self.verified,
            'verification_score': self.verification_score,
            'points_earned': self.points_earned
        }
    
    def __repr__(self):
        return f"PlasticUsage('{self.plastic_type}', '{self.quantity} {self.unit}')"

class CarbonSavings(db.Model):
    __tablename__ = 'carbon_savings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activity_type = db.Column(db.String(100), nullable=False)  # plastic_reduced, public_transport, etc.
    carbon_saved = db.Column(db.Float, nullable=False)  # in kg CO2
    description = db.Column(db.Text)
    proof_type = db.Column(db.String(50))  # photo, receipt, tracking
    proof_file = db.Column(db.String(200))
    verified = db.Column(db.Boolean, default=False)
    points_earned = db.Column(db.Integer, default=0)
    
    user = db.relationship('User', backref=db.backref('carbon_savings', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_username': self.user.username if self.user else 'Unknown',
            'date': self.date.isoformat(),
            'activity_type': self.activity_type,
            'carbon_saved': self.carbon_saved,
            'description': self.description,
            'proof_type': self.proof_type,
            'proof_file': self.proof_file,
            'verified': self.verified,
            'points_earned': self.points_earned
        }
    
    def __repr__(self):
        return f"CarbonSavings('{self.activity_type}', '{self.carbon_saved} kg CO2')"

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate likes
    __table_args__ = (db.UniqueConstraint('user_id', 'report_id', name='unique_like'),)
    
    # Define relationships
    user = db.relationship('User', backref='likes', foreign_keys=[user_id])
    report = db.relationship('Report', backref=db.backref('likes', cascade='all, delete-orphan'), foreign_keys=[report_id])
    
    def to_dict(self):
        """Convert like object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_username': self.user.username if self.user else 'Unknown',
            'report_id': self.report_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def __repr__(self):
        return f"Like('{self.user_id}', '{self.report_id}')"

class LocalApproval(db.Model):
    __tablename__ = 'local_approval'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate approvals
    __table_args__ = (db.UniqueConstraint('user_id', 'report_id', name='unique_local_approval'),)
    
    # Define relationships
    user = db.relationship('User', backref='local_approvals', foreign_keys=[user_id])
    report = db.relationship('Report', backref=db.backref('local_approvals_list', cascade='all, delete-orphan'), foreign_keys=[report_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_username': self.user.username if self.user else 'Unknown',
            'report_id': self.report_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def __repr__(self):
        return f"LocalApproval('{self.user_id}', '{self.report_id}')"

class ReportView(db.Model):
    __tablename__ = 'report_view'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint per user/report
    __table_args__ = (db.UniqueConstraint('user_id', 'report_id', name='unique_report_view'),)
    
    # Define relationships
    user = db.relationship('User', backref='report_views', foreign_keys=[user_id])
    report = db.relationship('Report', backref=db.backref('report_views_list', cascade='all, delete-orphan'), foreign_keys=[report_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'report_id': self.report_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def __repr__(self):
        return f"ReportView('{self.user_id}', '{self.report_id}')"

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationships
    user = db.relationship('User', backref='comments', foreign_keys=[user_id])
    report = db.relationship('Report', backref=db.backref('comments', cascade='all, delete-orphan'), foreign_keys=[report_id])
    
    def to_dict(self):
        """Convert comment object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_username': self.user.username if self.user else 'Unknown',
            'report_id': self.report_id,
            'text': self.text,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def __repr__(self):
        return f"Comment('{self.user_id}', '{self.report_id}', '{self.timestamp}')"

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(50), nullable=False)
    points_required = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        """Convert badge object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'points_required': self.points_required
        }
    
    def __repr__(self):
        return f"Badge('{self.name}')"

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('volunteer_assignments.id'), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    is_alert = db.Column(db.Boolean, default=False)  # New field to distinguish hazard alerts
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Define relationships
    user = db.relationship('User', backref='notifications', foreign_keys=[user_id])
    report = db.relationship('Report', backref=db.backref('notifications', cascade='all, delete-orphan'), foreign_keys=[report_id])
    assignment = db.relationship('VolunteerAssignment', backref='notifications', foreign_keys=[assignment_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'message': self.message,
            'report_id': self.report_id,
            'assignment_id': self.assignment_id,
            'is_read': self.is_read,
            'is_alert': self.is_alert,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    def __repr__(self):
        return f"Notification('{self.user_id}', '{self.message[:50]}...')"

# =============================================================================
# GOVERNMENT-NGO COORDINATION PLATFORM MODELS
# =============================================================================

class Agency(db.Model):
    __tablename__ = 'agencies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # government, ngo, emergency, medical, etc.
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    resources = db.Column(db.Text)  # JSON string of available resources
    capabilities = db.Column(db.Text)  # JSON string of capabilities
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'contact_email': self.contact_email,
            'contact_phone': self.contact_phone,
            'resources': json.loads(self.resources) if self.resources else [],
            'capabilities': json.loads(self.capabilities) if self.capabilities else [],
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"Agency('{self.name}', '{self.type}')"

class EmergencyEvent(db.Model):
    __tablename__ = 'emergency_events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    hazard_type = db.Column(db.String(50))
    severity = db.Column(db.String(20))  # low, medium, high, critical
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    radius_km = db.Column(db.Float, default=10.0)
    status = db.Column(db.String(20), default='active')  # active, resolved, cancelled
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationships
    coordinator = db.relationship('User', backref='managed_events', foreign_keys=[created_by])
    resources = db.relationship('ResourceAllocation', backref='event', lazy=True)
    volunteers = db.relationship('VolunteerAssignment', backref='event', lazy=True)
    situation_reports = db.relationship('SituationReport', backref='event', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'hazard_type': self.hazard_type,
            'severity': self.severity,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'radius_km': self.radius_km,
            'status': self.status,
            'created_by': self.created_by,
            'coordinator_username': self.coordinator.username if self.coordinator else 'Unknown',
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"EmergencyEvent('{self.title}', '{self.status}')"

class ResourceAllocation(db.Model):
    __tablename__ = 'resource_allocations'
    id = db.Column(db.Integer, primary_key=True)
    emergency_event_id = db.Column(db.Integer, db.ForeignKey('emergency_events.id'))
    agency_id = db.Column(db.Integer, db.ForeignKey('agencies.id'))
    resource_type = db.Column(db.String(100), nullable=False)  # medical, food, shelter, equipment
    quantity = db.Column(db.Integer, default=1)
    units = db.Column(db.String(50))  # units, people, kg, etc.
    status = db.Column(db.String(20), default='allocated')  # allocated, deployed, used, returned
    allocated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationships
    agency = db.relationship('Agency', backref='allocations', foreign_keys=[agency_id])
    allocator = db.relationship('User', backref='created_allocations', foreign_keys=[allocated_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'emergency_event_id': self.emergency_event_id,
            'agency_id': self.agency_id,
            'agency_name': self.agency.name if self.agency else 'Unknown',
            'resource_type': self.resource_type,
            'quantity': self.quantity,
            'units': self.units,
            'status': self.status,
            'allocated_by': self.allocated_by,
            'allocator_username': self.allocator.username if self.allocator else 'Unknown',
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"ResourceAllocation('{self.resource_type}', '{self.status}')"

class Volunteer(db.Model):
    __tablename__ = 'volunteers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    skills = db.Column(db.Text)  # JSON string of skills
    availability = db.Column(db.String(20), default='available')  # available, busy, unavailable
    experience_level = db.Column(db.String(20))  # beginner, intermediate, expert
    certifications = db.Column(db.Text)  # JSON string of certifications
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    is_verified = db.Column(db.Boolean, default=False)
    points = db.Column(db.Integer, default=0)  # Points earned from completed rescues
    total_rescues = db.Column(db.Integer, default=0)  # Total completed rescues
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationship
    user = db.relationship('User', backref='volunteer_profile', foreign_keys=[user_id], uselist=False)
    assignments = db.relationship('VolunteerAssignment', backref='volunteer', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_username': self.user.username if self.user else 'Unknown',
            'skills': json.loads(self.skills) if self.skills else [],
            'availability': self.availability,
            'experience_level': self.experience_level,
            'certifications': json.loads(self.certifications) if self.certifications else [],
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_verified': self.is_verified,
            'points': self.points,
            'total_rescues': self.total_rescues,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f"Volunteer('{self.user_id}', '{self.availability}')"

class VolunteerAssignment(db.Model):
    __tablename__ = 'volunteer_assignments'
    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteers.id'))
    emergency_event_id = db.Column(db.Integer, db.ForeignKey('emergency_events.id'))
    hazard_type = db.Column(db.String(20), default='emergency')  # emergency or report
    role = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, accepted, deployed, completed, declined, cancelled
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    distance_km = db.Column(db.Float)  # Distance from volunteer to hazard in km
    completion_photo = db.Column(db.String(500))  # Photo path/URL of completed rescue
    completion_notes = db.Column(db.Text)  # Notes from volunteer about the rescue
    points_earned = db.Column(db.Integer, default=0)  # Points awarded for this completion
    
    # Define relationships
    assigner = db.relationship('User', backref='created_assignments', foreign_keys=[assigned_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'volunteer_id': self.volunteer_id,
            'volunteer_username': self.volunteer.user.username if self.volunteer and self.volunteer.user else 'Unknown',
            'emergency_event_id': self.emergency_event_id,
            'hazard_type': getattr(self, 'hazard_type', 'emergency'),
            'event_title': (self.event.title if getattr(self, 'hazard_type', 'emergency') == 'emergency' and self.event else ('Unknown Report' if getattr(self, 'hazard_type', 'emergency') == 'report' else 'Unknown')),
            'role': self.role,
            'status': self.status,
            'assigned_by': self.assigned_by,
            'assigner_username': self.assigner.username if self.assigner else 'Unknown',
            'assigned_at': self.assigned_at.isoformat(),
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'distance_km': self.distance_km,
            'completion_photo': self.completion_photo,
            'completion_notes': self.completion_notes,
            'points_earned': self.points_earned
        }
    
    def __repr__(self):
        return f"VolunteerAssignment('{self.role}', '{self.status}')"

class SituationReport(db.Model):
    __tablename__ = 'situation_reports'
    id = db.Column(db.Integer, primary_key=True)
    emergency_event_id = db.Column(db.Integer, db.ForeignKey('emergency_events.id'))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    report_type = db.Column(db.String(50))  # damage_assessment, resource_status, weather, evacuation
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationship
    author = db.relationship('User', backref='authored_situation_reports', foreign_keys=[created_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'emergency_event_id': self.emergency_event_id,
            'event_title': self.event.title if self.event else 'Unknown',
            'title': self.title,
            'content': self.content,
            'priority': self.priority,
            'report_type': self.report_type,
            'created_by': self.created_by,
            'author_username': self.author.username if self.author else 'Unknown',
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f"SituationReport('{self.title}', '{self.priority}')"

class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationships
    user = db.relationship('User', backref='user_badges', foreign_keys=[user_id])
    badge = db.relationship('Badge', backref='user_badges', foreign_keys=[badge_id])
    
    def to_dict(self):
        """Convert user_badge object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_username': self.user.username if self.user else 'Unknown',
            'badge_id': self.badge_id,
            'badge_name': self.badge.name if self.badge else 'Unknown',
            'earned_at': self.earned_at.isoformat() if self.earned_at else None
        }
    
    def __repr__(self):
        return f"UserBadge('{self.user_id}', '{self.badge_id}')"

# =============================================================================
# URBAN RESILIENCE INDEX (URI) MODELS
# =============================================================================

class ResilienceZone(db.Model):
    """Defines geographic zones for resilience tracking"""
    __tablename__ = 'resilience_zones'
    id = db.Column(db.Integer, primary_key=True)
    zone_identifier = db.Column(db.String(100), unique=True, nullable=False)  # e.g., "grid_17.5_78.5"
    zone_type = db.Column(db.String(50), default='grid')  # grid, ward, city, coastal_segment
    center_latitude = db.Column(db.Float, nullable=False)
    center_longitude = db.Column(db.Float, nullable=False)
    bounds_geojson = db.Column(db.Text, nullable=True)  # JSON polygon coordinates
    display_name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to scores
    scores = db.relationship('ResilienceScore', backref='zone', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert zone object to dictionary for JSON serialization"""
        latest_score = ResilienceScore.query.filter_by(
            zone_id=self.id,
            calculation_period='30d'
        ).order_by(ResilienceScore.calculated_at.desc()).first()
        
        return {
            'id': self.id,
            'zone_identifier': self.zone_identifier,
            'zone_type': self.zone_type,
            'center_latitude': self.center_latitude,
            'center_longitude': self.center_longitude,
            'display_name': self.display_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'latest_score': latest_score.score if latest_score else None,
            'trend': latest_score.trend if latest_score else 'stable',
            'metrics': json.loads(latest_score.metrics_json) if latest_score and latest_score.metrics_json else {}
        }
    
    def __repr__(self):
        return f"ResilienceZone('{self.zone_identifier}', '{self.display_name}')"

class ResilienceScore(db.Model):
    """Stores historical URI scores for each zone"""
    __tablename__ = 'resilience_scores'
    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey('resilience_zones.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)  # 0-100
    trend = db.Column(db.String(20), default='stable')  # improving, stable, declining
    calculation_period = db.Column(db.String(20), default='30d')  # 30d, 90d
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    metrics_json = db.Column(db.Text, nullable=True)  # JSON breakdown of contributing factors
    
    def to_dict(self):
        """Convert score object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'zone_id': self.zone_id,
            'score': self.score,
            'trend': self.trend,
            'calculation_period': self.calculation_period,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None,
            'metrics': json.loads(self.metrics_json) if self.metrics_json else {}
        }
    
    def __repr__(self):
        return f"ResilienceScore(zone={self.zone_id}, score={self.score:.1f}, period={self.calculation_period})"
# =============================================================================
# COMMUNITY ACTION HUB MODELS
# =============================================================================

class CommunityEvent(db.Model):
    __tablename__ = 'community_events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # disaster_prep, environment, social
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    date_time = db.Column(db.DateTime, nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='upcoming')  # upcoming, completed, cancelled
    image_file = db.Column(db.String(100), nullable=True) # Optional event image
    
    # Relationships
    organizer = db.relationship('User', backref='organized_events', foreign_keys=[organizer_id])
    participants = db.relationship('EventParticipant', backref='event', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'event_type': self.event_type,
            'location': self.location,
            'date_time': self.date_time.isoformat(),
            'organizer': self.organizer.username,
            'status': self.status,
            'participant_count': self.participants.count(),
            'image_file': self.image_file
        }

class EventParticipant(db.Model):
    __tablename__ = 'event_participants'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('community_events.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='registered')  # registered, attended
    
    user = db.relationship('User', backref='events_joined')

# =============================================================================
# LIFELINE: P2P RESOURCE MARKETPLACE MODELS
# =============================================================================

class ResourceListing(db.Model):
    __tablename__ = 'resource_listings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    listing_type = db.Column(db.String(20), nullable=False)  # 'have' (donor) or 'need' (requester)
    category = db.Column(db.String(50), nullable=False)  # medical, food, water, shelter, gear, transport
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='open')  # open, matched, completed, cancelled
    urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('resource_listings', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'listing_type': self.listing_type,
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'quantity': self.quantity,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'status': self.status,
            'urgent': self.urgent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ResourceMatch(db.Model):
    __tablename__ = 'resource_matches'
    id = db.Column(db.Integer, primary_key=True)
    need_id = db.Column(db.Integer, db.ForeignKey('resource_listings.id'), nullable=False)
    have_id = db.Column(db.Integer, db.ForeignKey('resource_listings.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    need_listing = db.relationship('ResourceListing', foreign_keys=[need_id], backref=db.backref('matches_as_need', lazy=True))
    have_listing = db.relationship('ResourceListing', foreign_keys=[have_id], backref=db.backref('matches_as_have', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'need_id': self.need_id,
            'have_id': self.have_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'need_title': self.need_listing.title,
            'have_title': self.have_listing.title,
            'requester': self.need_listing.user.username,
            'donor': self.have_listing.user.username
        }
