import os
from dotenv import load_dotenv

# override=True so values in .env always win over stale variables already
# exported in the launching shell (a stale TWILIO_AUTH_TOKEN silently made
# every WhatsApp alert fail with a 401 while TwiML bot replies kept working).
load_dotenv(override=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-demo-only'
    
    # Database Configuration
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = db_url or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # The background scheduler (twin ingest/scoring jobs) writes to the same
    # sqlite file as web requests. Sqlite's default busy timeout is effectively
    # 0-5s, so a request and a scheduled job writing at the same moment raised
    # "database is locked". Give connections a generous busy timeout so they
    # wait for each other instead of failing immediately.
    if not db_url:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {'timeout': 30},
        }
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
    FIREBASE_SERVER_KEY = os.environ.get('FIREBASE_SERVER_KEY')
    
    # Multilingual support
    LANGUAGES = ['en', 'ta', 'hi', 'te', 'ml', 'kn']  # English, Tamil, Hindi, Telugu, Malayalam, Kannada
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'UTC'
    
    # Twilio WhatsApp Configuration
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    
    # Twilio SMS Configuration
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')