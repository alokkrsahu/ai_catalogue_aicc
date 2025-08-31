#!/usr/bin/env python3
"""
Dashboard Icons Setup Script
Quick script to set up dashboard icons after PostgreSQL migration.
"""

import os
import sys
import django

def setup_django():
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    django.setup()

def main():
    """Main setup function"""
    print("🎨 Setting up Dashboard Icons...")
    print("=" * 50)
    
    # Setup Django
    setup_django()
    
    # Import after Django setup
    from django.core.management import call_command
    from users.models import DashboardIcon
    
    # Check current icon count
    current_count = DashboardIcon.objects.count()
    print(f"📊 Current icons in database: {current_count}")
    
    if current_count == 0:
        print("🔄 No icons found, creating default dashboard icons...")
        
        # Run the restore_icons command
        call_command('restore_icons')
        
        # Check final count
        final_count = DashboardIcon.objects.count()
        print(f"✅ Dashboard icons setup completed!")
        print(f"📊 Total icons created: {final_count}")
        
    else:
        print("ℹ️  Dashboard icons already exist")
        
        # Show existing icons
        icons = DashboardIcon.objects.all().order_by('order')
        print("\n📋 Existing Icons:")
        for icon in icons:
            print(f"   🔹 {icon.name} ({icon.icon_class}) -> {icon.route}")
    
    print("\n🎯 Next Steps:")
    print("1. Start Django server: python manage.py runserver")
    print("2. Visit admin panel: http://localhost:8000/admin/")
    print("3. Login with: admin@example.com / admin123")
    print("4. Access dashboard to see icons")

if __name__ == '__main__':
    main()