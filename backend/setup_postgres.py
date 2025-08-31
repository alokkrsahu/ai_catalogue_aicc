#!/usr/bin/env python3
"""
PostgreSQL Setup Script for AI Catalogue Backend
This script sets up PostgreSQL database and runs initial migrations.
"""

import os
import sys
import subprocess
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import django
from django.core.management import execute_from_command_line
from django.conf import settings

# Database configuration
DB_NAME = os.getenv('DB_NAME', 'ai_catalogue_db')
DB_USER = os.getenv('DB_USER', 'ai_catalogue_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ai_catalogue_password')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

def check_postgresql_running():
    """Check if PostgreSQL is running"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user='postgres',  # Default postgres user
            password=os.getenv('POSTGRES_PASSWORD', 'postgres')
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False

def create_database_and_user():
    """Create database and user if they don't exist"""
    try:
        # Connect as postgres superuser
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user='postgres',
            password=os.getenv('POSTGRES_PASSWORD', 'postgres')
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create user if not exists
        try:
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(DB_USER)
                ), [DB_PASSWORD]
            )
            print(f"✅ Created user: {DB_USER}")
        except psycopg2.errors.DuplicateObject:
            print(f"ℹ️  User {DB_USER} already exists")
        
        # Create database if not exists
        try:
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DB_NAME),
                    sql.Identifier(DB_USER)
                )
            )
            print(f"✅ Created database: {DB_NAME}")
        except psycopg2.errors.DuplicateDatabase:
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

def install_postgresql_dependencies():
    """Install required PostgreSQL Python packages"""
    try:
        print("🔄 Installing PostgreSQL dependencies...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'psycopg2-binary>=2.9.7'])
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'psycopg>=3.1.0'])
        print("✅ PostgreSQL dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {str(e)}")
        return False

def create_env_file():
    """Create .env file with database configuration"""
    env_content = f"""# PostgreSQL Database Configuration
DB_NAME={DB_NAME}
DB_USER={DB_USER}
DB_PASSWORD={DB_PASSWORD}
DB_HOST={DB_HOST}
DB_PORT={DB_PORT}

# PostgreSQL Admin Configuration (for setup only)
POSTGRES_PASSWORD=postgres

# Other environment variables (add as needed)
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
    print("🚀 Starting PostgreSQL setup for AI Catalogue Backend...")
    print("=" * 60)
    
    # Step 1: Create .env file
    create_env_file()
    
    # Step 2: Install dependencies
    if not install_postgresql_dependencies():
        print("❌ Setup failed at dependency installation")
        return False
    
    # Step 3: Check PostgreSQL is running
    print("🔄 Checking PostgreSQL connection...")
    if not check_postgresql_running():
        print("❌ PostgreSQL is not running or not accessible")
        print("Please ensure PostgreSQL is installed and running:")
        print("   macOS: brew services start postgresql")
        print("   Ubuntu: sudo systemctl start postgresql")
        print("   Windows: Start PostgreSQL service")
        return False
    print("✅ PostgreSQL is running")
    
    # Step 4: Create database and user
    if not create_database_and_user():
        print("❌ Setup failed at database/user creation")
        return False
    
    # Step 5: Test Django connection
    if not test_django_connection():
        print("❌ Setup failed at Django connection test")
        return False
    
    # Step 6: Create and run migrations
    if not create_django_migrations():
        print("❌ Setup failed at migrations")
        return False
    
    # Step 7: Create superuser
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