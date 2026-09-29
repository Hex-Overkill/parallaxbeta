from app import app, db, User  # Replace with your actual app, db, and User model imports
from werkzeug.security import generate_password_hash

def modify_admin():
    # 1. Establish the Flask application context so db can connect
    with app.app_context():
        
        # 2. Find the admin user by email or username
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            print(u" Updating existing admin user...")
            # Modify the field you need (e.g., changing password or making them an admin)
            admin.password = generate_password_hash("new_secure_password_123")
            admin.is_admin = True  # If you use a boolean role flag
            
            # 3. Commit the changes to the database file
            db.session.commit()
            print(u" Admin updated successfully!")
        else:
            print(u" Admin user not found.")

if __name__ == '__main__':
    modify_admin()