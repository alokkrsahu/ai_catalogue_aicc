"""
Django management command to setup all required container data
Usage: python manage.py setup_container_data
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from users.models import DashboardIcon
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Setup all required container data including dashboard icons for cloud deployment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-recreate',
            action='store_true',
            help='Force recreate all data even if it exists',
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only verify existing data without creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Setting up container data for AI Catalogue')
        )
        self.stdout.write('=' * 60)
        
        success = True
        
        # Verify-only mode
        if options['verify_only']:
            return self.verify_data_only()
        
        # Setup dashboard icons
        if not self.setup_dashboard_icons(options['force_recreate']):
            success = False
        
        # Verify all critical data
        if not self.verify_critical_data():
            success = False
            
        # Final status
        self.stdout.write('=' * 60)
        if success:
            self.stdout.write(
                self.style.SUCCESS('🎉 Container data setup completed successfully!')
            )
            self.stdout.write(
                self.style.SUCCESS('💡 AI Catalogue is ready for use')
            )
            self.show_access_info()
        else:
            self.stdout.write(
                self.style.ERROR('❌ Container data setup completed with errors!')
            )
            self.stdout.write(
                self.style.WARNING('⚠️  Some functionality may not work correctly')
            )
            return
    
    def setup_dashboard_icons(self, force_recreate=False):
        """Setup dashboard icons"""
        try:
            self.stdout.write('🎨 Setting up dashboard icons...')
            
            current_count = DashboardIcon.objects.count()
            self.stdout.write(f'📊 Current dashboard icons: {current_count}')
            
            if current_count == 0 or force_recreate:
                if force_recreate and current_count > 0:
                    self.stdout.write('🔄 Force recreating dashboard icons...')
                    call_command('restore_icons', '--clear')
                else:
                    self.stdout.write('🎨 Creating dashboard icons...')
                    call_command('restore_icons')
                
                final_count = DashboardIcon.objects.count()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Dashboard icons setup completed: {final_count} icons')
                )
            else:
                self.stdout.write('ℹ️  Dashboard icons already exist')
                # Show existing icons briefly
                icons = DashboardIcon.objects.filter(is_active=True).order_by('order')
                self.stdout.write(f'📋 Active icons: {", ".join([icon.name for icon in icons])}')
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Dashboard icons setup failed: {e}')
            )
            return False
    
    def verify_critical_data(self):
        """Verify that critical application data is set up"""
        try:
            self.stdout.write('🔍 Verifying critical application data...')
            
            # Check dashboard icons
            icon_count = DashboardIcon.objects.count()
            active_icon_count = DashboardIcon.objects.filter(is_active=True).count()
            
            if icon_count == 0:
                self.stdout.write(
                    self.style.ERROR('❌ No dashboard icons found!')
                )
                return False
            
            # Check for key icons
            required_icons = ['AICC-IntelliDoc', 'LLM Evaluation']
            missing_icons = []
            
            for icon_name in required_icons:
                if not DashboardIcon.objects.filter(name=icon_name, is_active=True).exists():
                    missing_icons.append(icon_name)
            
            if missing_icons:
                self.stdout.write(
                    self.style.ERROR(f'❌ Required icons missing: {", ".join(missing_icons)}')
                )
                return False
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Data verification passed: {active_icon_count}/{icon_count} active icons')
            )
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Data verification failed: {e}')
            )
            return False
    
    def verify_data_only(self):
        """Only verify existing data without creating anything"""
        self.stdout.write('🔍 Verifying existing container data...')
        
        if self.verify_critical_data():
            self.stdout.write(
                self.style.SUCCESS('✅ All critical data verified successfully!')
            )
        else:
            self.stdout.write(
                self.style.ERROR('❌ Data verification failed!')
            )
            self.stdout.write(
                self.style.WARNING('💡 Run without --verify-only to setup missing data')
            )
    
    def show_access_info(self):
        """Show access information for the application"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🌐 Access Information:'))
        self.stdout.write('   📱 Frontend (Dev): http://localhost:5173')
        self.stdout.write('   📱 Frontend (Prod): http://localhost:3000') 
        self.stdout.write('   🔧 Backend API: http://localhost:8000')
        self.stdout.write('   👤 Admin Panel: http://localhost:8000/admin/')
        self.stdout.write('')
        self.stdout.write('💡 Use your superuser credentials to access the admin panel')
        self.stdout.write('🎯 Visit the dashboard to see all available AI tools and features')