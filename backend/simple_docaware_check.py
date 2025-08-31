#!/usr/bin/env python3
"""
Simple DocAware diagnostics
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import IntelliDocProject

# Check project documents
project_id = "8660355a-7fd0-4434-a380-7cf80442603c"
print(f"🔍 Checking project {project_id}...")

try:
    project = IntelliDocProject.objects.get(project_id=project_id)
    print(f"✅ Project: {project.name}")
    print(f"✅ Collection name: {project.generate_collection_name()}")
    
    documents = project.documents.all()
    print(f"📄 Documents: {len(documents)} total")
    
    for doc in documents:
        print(f"   - {doc.title}")
        print(f"     Status: {doc.processing_status}")
        print(f"     Created: {doc.created_at}")
        print(f"     File: {doc.file.name if doc.file else 'No file'}")
        print()
        
    processed_docs = [doc for doc in documents if doc.processing_status == 'completed']
    print(f"✅ Processed documents: {len(processed_docs)}")
    
    if len(processed_docs) == 0:
        print("❌ NO PROCESSED DOCUMENTS FOUND!")
        print("🔧 This explains why search returns 0 results")
        print("🔧 You need to process documents before search will work")
    else:
        print("✅ Documents are processed - issue may be elsewhere")
        
except IntelliDocProject.DoesNotExist:
    print(f"❌ Project {project_id} not found")
except Exception as e:
    print(f"❌ Error: {e}")
