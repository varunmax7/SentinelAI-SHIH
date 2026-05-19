from app import app, db
from models import User
with app.app_context():
    admins = User.query.filter(User.role.in_(['official', 'analyst'])).all()
    for a in admins:
        print(f"Username: {a.username}, Email: {a.email}, Role: {a.role}")
