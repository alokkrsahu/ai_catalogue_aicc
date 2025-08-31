#!/usr/bin/env python3
"""
Container Data Setup Script
Runs during container initialization to set up required data including dashboard icons.
This script is cloud-ready and handles both development and production environments.
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_django():
    """Setup Django environment"""
    # Add the current directory to Python path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    
    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    try:
        import django
        django.setup()
        logger.info("✅ Django environment initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to setup Django: {e}")
        return False

def run_management_command(command_name, *args, **kwargs):
    """Run a Django management command with error handling"""
    try:
        from django.core.management import call_command
        logger.info(f"🔄 Running management command: {command_name}")
        call_command(command_name, *args, **kwargs)
        logger.info(f"✅ Successfully completed: {command_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to run {command_name}: {e}")
        return False

def setup_dashboard_icons():
    """Setup dashboard icons with error handling"""
    try:
        from users.models import DashboardIcon
        
        # Check if icons already exist
        current_count = DashboardIcon.objects.count()
        logger.info(f"📊 Current dashboard icons in database: {current_count}")
        
        if current_count == 0:
            logger.info("🎨 No dashboard icons found, creating them...")
            success = run_management_command('restore_icons')
            if success:
                final_count = DashboardIcon.objects.count()
                logger.info(f"✅ Successfully created {final_count} dashboard icons")
            return success
        else:
            logger.info("ℹ️  Dashboard icons already exist, skipping creation")
            
            # Show existing icons for verification
            icons = DashboardIcon.objects.all().order_by('order')
            logger.info("📋 Existing Dashboard Icons:")
            for icon in icons:
                logger.info(f"   🔹 {icon.name} ({icon.icon_class}) -> {icon.route}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error in dashboard icons setup: {e}")
        return False

def verify_critical_data():
    """Verify that critical application data is properly set up"""
    try:
        from users.models import DashboardIcon
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Check dashboard icons
        icon_count = DashboardIcon.objects.count()
        if icon_count == 0:
            logger.warning("⚠️  No dashboard icons found!")
            return False
        
        # Check for key icons
        required_icons = ['AICC-IntelliDoc', 'LLM Evaluation']
        for icon_name in required_icons:
            if not DashboardIcon.objects.filter(name=icon_name).exists():
                logger.warning(f"⚠️  Required icon '{icon_name}' not found!")
                return False
        
        logger.info(f"✅ Data verification passed - {icon_count} icons found")
        return True
        
    except Exception as e:
        logger.error(f"❌ Data verification failed: {e}")
        return False

def main():
    """Main setup function"""
    logger.info("🚀 Starting container data setup...")
    logger.info("=" * 60)
    
    # Setup Django
    if not setup_django():
        logger.error("❌ Failed to setup Django environment")
        sys.exit(1)
    
    # Track setup success
    setup_successful = True
    
    # Setup dashboard icons
    logger.info("🎨 Setting up dashboard icons...")
    if not setup_dashboard_icons():
        logger.error("❌ Dashboard icons setup failed")
        setup_successful = False
    
    # Verify critical data
    logger.info("🔍 Verifying critical application data...")
    if not verify_critical_data():
        logger.error("❌ Critical data verification failed")
        setup_successful = False
    
    # Final status
    logger.info("=" * 60)
    if setup_successful:
        logger.info("🎉 Container data setup completed successfully!")
        logger.info("💡 Application is ready for use")
        
        # Show next steps
        logger.info("\n🎯 Next Steps:")
        logger.info("1. Access frontend: http://localhost:5173 (dev) or http://localhost:3000 (prod)")
        logger.info("2. Access admin panel: http://localhost:8000/admin/")
        logger.info("3. Access dashboard to see the restored icons")
        
    else:
        logger.error("❌ Container data setup completed with errors!")
        logger.error("⚠️  Some functionality may not work correctly")
        sys.exit(1)

if __name__ == '__main__':
    main()