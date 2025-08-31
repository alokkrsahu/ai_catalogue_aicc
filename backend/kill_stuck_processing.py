#!/usr/bin/env python3
"""
Emergency script to kill stuck document processing
"""

import os
import sys
import signal
import psutil
import django

def setup_django():
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    django.setup()

def kill_stuck_processing():
    """Kill stuck processing threads and reset state"""
    print("🚨 Emergency Processing Reset")
    print("=" * 40)
    
    # Setup Django
    setup_django()
    
    # Import after Django setup
    from users.models import ProjectVectorCollection, VectorProcessingStatus
    
    # Reset any stuck processing status
    stuck_collections = ProjectVectorCollection.objects.filter(
        status=VectorProcessingStatus.PROCESSING
    )
    
    print(f"📊 Found {stuck_collections.count()} collections stuck in PROCESSING state")
    
    for collection in stuck_collections:
        print(f"🔄 Resetting: {collection.project.name} (ID: {collection.project.project_id})")
        collection.status = VectorProcessingStatus.PENDING
        collection.error_message = "Reset due to stuck processing"
        collection.save()
    
    # Find and kill high CPU Python processes
    high_cpu_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'cmdline']):
        try:
            if proc.info['name'] == 'Python' and proc.info['cpu_percent'] > 5.0:
                if 'manage.py' in ' '.join(proc.info['cmdline'] or []):
                    high_cpu_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    print(f"\n🔍 Found {len(high_cpu_processes)} high CPU Django processes")
    
    for proc in high_cpu_processes:
        print(f"⚠️  Process {proc.pid}: {proc.info['cpu_percent']:.1f}% CPU")
        print(f"   Command: {' '.join(proc.info['cmdline'][:3])}")
        
        # Send SIGTERM to gracefully stop
        try:
            proc.terminate()
            proc.wait(timeout=5)
            print(f"✅ Gracefully terminated process {proc.pid}")
        except psutil.TimeoutExpired:
            # Force kill if it doesn't respond
            proc.kill()
            print(f"🔥 Force killed process {proc.pid}")
    
    print("\n✅ Processing reset completed!")
    print("💡 Restart Django server: python manage.py runserver")

if __name__ == '__main__':
    kill_stuck_processing()