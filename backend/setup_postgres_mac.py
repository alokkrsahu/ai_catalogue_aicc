#!/usr/bin/env python3
"""
PostgreSQL Setup Script for AI Catalogue Backend (macOS Homebrew)
This script sets up PostgreSQL database for Homebrew installations on macOS.
"""

import os
import sys
import subprocess
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import django
from django.core.management import execute_from_command_line

# Database configuration
DB_NAME = os.getenv('DB_NAME', 'ai_catalogue_db')
DB_USER = os.getenv('DB_USER', 'ai_catalogue_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ai_catalogue_password')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

def get_current_user():
    """Get current system user for PostgreSQL connection"""
    import getpass
    return getpass.getuser()

def check_postgresql_connection():
    """Check PostgreSQL connection using current user"""
    try:
        current_user = get_current_user()
        print(f"🔄 Trying to connect as user: {current_user}")
        
        # Try connecting as current user (Homebrew default)
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=current_user,
            dbname='postgres'  # Connect to default postgres database
        )
        conn.close()
        return current_user
    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {str(e)}")
        
        # Try with 'postgres' user
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user='postgres',
                dbname='postgres'
            )
            conn.close()
            return 'postgres'
        except psycopg2.OperationalError:
            return None

def create_database_and_user(admin_user):
    """Create database and user"""
    try:
        # Connect as admin user
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=admin_user,
            dbname='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=%s", (DB_USER,)
        )
        user_exists = cursor.fetchone()
        
        if not user_exists:
            # Create user
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s CREATEDB").format(
                    sql.Identifier(DB_USER)
                ), [DB_PASSWORD]
            )
            print(f"✅ Created user: {DB_USER}")
        else:
            # Update password
            cursor.execute(
                sql.SQL("ALTER USER {} WITH PASSWORD %s CREATEDB").format(
                    sql.Identifier(DB_USER)
                ), [DB_PASSWORD]
            )
            print(f"ℹ️  Updated user: {DB_USER}")
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,)
        )
        db_exists = cursor.fetchone()
        
        if not db_exists:
            # Create database
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DB_NAME),
                    sql.Identifier(DB_USER)
                )
            )
            print(f"✅ Created database: {DB_NAME}")
        else:
            print(f"ℹ️  Database {DB_NAME} already exists")
        
        # Grant privileges
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(DB_NAME),
                sql.Identifier(DB_USER)
            )
        )
        print(f"✅ Granted privileges to {DB_USER} on {DB_NAME}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database/user: {str(e)}")
        return False

def test_django_connection():
    """Test Django database connection"""
    try:
        # Set up Django environment
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
        django.setup()
        
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result[0] == 1:
                print("✅ Django PostgreSQL connection successful")
                return True
    except Exception as e:
        print(f"❌ Django connection failed: {str(e)}")
        return False

def create_django_migrations():
    """Create and run Django migrations"""
    try:
        print("🔄 Creating Django migrations...")
        
        # Make migrations for all apps
        execute_from_command_line(['manage.py', 'makemigrations', 'users'])
        execute_from_command_line(['manage.py', 'makemigrations', 'templates'])
        execute_from_command_line(['manage.py', 'makemigrations'])
        
        print("✅ Django migrations created")
        
        # Run migrations
        print("🔄 Running Django migrations...")
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ Django migrations applied")
        
        return True
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        return False

def create_superuser():
    """Create Django superuser"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if not User.objects.filter(email='admin@example.com').exists():
            User.objects.create_superuser(
                email='admin@example.com',
                password='admin123',
                first_name='Admin',
                last_name='User'
            )
            print("✅ Created superuser: admin@example.com / admin123")
        else:
            print("ℹ️  Superuser already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating superuser: {str(e)}")
        return False

def create_env_file():
    """Create .env file with database configuration"""
    env_content = f"""# PostgreSQL Database Configuration
DB_NAME={DB_NAME}
DB_USER={DB_USER}
DB_PASSWORD={DB_PASSWORD}
DB_HOST={DB_HOST}
DB_PORT={DB_PORT}

# Other environment variables
DEBUG=True
SECRET_KEY=django-insecure-change-this-in-production
"""
    
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        with open(env_path, 'w') as f:
            f.write(env_content)
        print(f"✅ Created .env file at {env_path}")
    else:
        print("ℹ️  .env file already exists")

def main():
    """Main setup function"""
    print("🚀 Starting PostgreSQL setup for AI Catalogue Backend (macOS)...")
    print("=" * 60)
    
    # Step 1: Create .env file
    create_env_file()
    
    # Step 2: Check PostgreSQL connection
    print("🔄 Checking PostgreSQL connection...")
    admin_user = check_postgresql_connection()
    if not admin_user:
        print("❌ Cannot connect to PostgreSQL")
        print("Please ensure PostgreSQL is running:")
        print("   brew services start postgresql")
        return False
    print(f"✅ PostgreSQL is accessible as user: {admin_user}")
    
    # Step 3: Create database and user
    if not create_database_and_user(admin_user):
        print("❌ Setup failed at database/user creation")
        return False
    
    # Step 4: Test Django connection
    if not test_django_connection():
        print("❌ Setup failed at Django connection test")
        return False
    
    # Step 5: Create and run migrations
    if not create_django_migrations():
        print("❌ Setup failed at migrations")
        return False
    
    # Step 6: Create superuser
    if not create_superuser():
        print("❌ Setup failed at superuser creation")
        return False
    
    print("=" * 60)
    print("🎉 PostgreSQL setup completed successfully!")
    print(f"📊 Database: {DB_NAME}")
    print(f"👤 User: {DB_USER}")
    print(f"🌐 Host: {DB_HOST}:{DB_PORT}")
    print(f"🔑 Admin login: admin@example.com / admin123")
    print("\nYou can now start the Django development server:")
    print("   python manage.py runserver")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)