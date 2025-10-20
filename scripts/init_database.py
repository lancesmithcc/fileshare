#!/usr/bin/env python3
"""Initialize the database and create the initial lanc3lot user."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.database import db
from app.models import User
from werkzeug.security import generate_password_hash

def init_db():
    """Initialize database tables and create lanc3lot user."""
    app = create_app()
    
    with app.app_context():
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        print("✓ Tables created")
        
        # Check if lanc3lot user already exists
        existing_user = User.query.filter_by(username='lanc3lot').first()
        if existing_user:
            print("✓ User 'lanc3lot' already exists")
            return
        
        # Create lanc3lot user
        print("Creating user 'lanc3lot'...")
        user = User(
            username='lanc3lot',
            email='lanc3lot@awen01.cc',
            password_hash=generate_password_hash('iamabanana777'),
            grove='Awen Circle',
            bio='Keeper of the Sacred Grove'
        )
        
        db.session.add(user)
        db.session.commit()
        print("✓ User 'lanc3lot' created successfully")
        print(f"  Username: lanc3lot")
        print(f"  Password: iamabanana777")
        print(f"  Email: lanc3lot@awen01.cc")

if __name__ == '__main__':
    init_db()
