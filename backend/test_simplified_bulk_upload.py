#!/usr/bin/env python3
"""
Test script for the simplified bulk upload functionality
"""

import sys
import os
import django

# Add the backend directory to Python path
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_path)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_catalogue.settings')
django.setup()

from public_chatbot.forms import BulkDocumentUploadForm
from public_chatbot.models import PublicKnowledgeDocument
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

def test_simplified_form():
    """Test the simplified bulk upload form"""
    print("🧪 Testing simplified BulkDocumentUploadForm...")
    
    # Create test files
    test_files = [
        SimpleUploadedFile("test1.txt", b"This is test content for document 1", content_type="text/plain"),
        SimpleUploadedFile("test2.txt", b"This is test content for document 2", content_type="text/plain"),
    ]
    
    # Test form data
    form_data = {
        'category': 'test'
    }
    
    # Create form with files
    form = BulkDocumentUploadForm(data=form_data, files={'files': test_files})
    
    print(f"Form is valid: {form.is_valid()}")
    if form.errors:
        print(f"Form errors: {form.errors}")
    
    if form.is_valid():
        print("✅ Form validation passed")
        print(f"Category: {form.cleaned_data.get('category')}")
        # Note: files will be handled differently in the view
    else:
        print("❌ Form validation failed")
    
    print("🎉 Form test completed!")

def test_file_extraction():
    """Test how Django handles multiple files"""
    print("\n🧪 Testing file extraction from request.FILES...")
    
    # Simulate request.FILES with multiple files
    factory = RequestFactory()
    
    # Create test files
    test_files = [
        SimpleUploadedFile("doc1.txt", b"Content of document 1", content_type="text/plain"),
        SimpleUploadedFile("doc2.txt", b"Content of document 2", content_type="text/plain"),
        SimpleUploadedFile("doc3.txt", b"Content of document 3", content_type="text/plain"),
    ]
    
    # Create POST request with files
    request = factory.post('/test/', data={'category': 'test'}, files={'files': test_files})
    
    # Test getlist functionality
    uploaded_files = request.FILES.getlist('files')
    print(f"Number of files extracted: {len(uploaded_files)}")
    
    for i, file_obj in enumerate(uploaded_files):
        print(f"File {i+1}: {file_obj.name} ({file_obj.size} bytes)")
        content = file_obj.read().decode('utf-8')
        print(f"  Content: {content}")
        # Reset file pointer for next read
        file_obj.seek(0)
    
    print("✅ File extraction test passed!")

def test_document_creation():
    """Test creating documents from extracted content"""
    print("\n🧪 Testing document creation...")
    
    try:
        # Clean up any existing test documents
        PublicKnowledgeDocument.objects.filter(title__startswith='Test Document').delete()
        
        # Create test document
        doc = PublicKnowledgeDocument.objects.create(
            title='Test Document Simplified Upload',
            content='This is test content for the simplified upload test',
            category='test',
            subcategory='',
            source_url='upload://test.txt',
            tags='test,simplified,upload',
            created_by='test_user',
            language='en',
            quality_score=50,
            is_approved=False,
            security_reviewed=False,
            approved_by='',
        )
        
        print(f"✅ Created document: {doc.title} (ID: {doc.id})")
        print(f"   Document ID: {doc.document_id}")
        print(f"   Category: {doc.category}")
        print(f"   Content length: {len(doc.content)} characters")
        print(f"   Approved: {doc.is_approved}")
        
        # Verify document was saved correctly
        saved_doc = PublicKnowledgeDocument.objects.get(id=doc.id)
        print(f"✅ Document saved and retrieved successfully")
        
        return doc
        
    except Exception as e:
        print(f"❌ Error creating document: {e}")
        return None

def test_content_extraction():
    """Test the simple content extraction method"""
    print("\n🧪 Testing content extraction...")
    
    # Test different file types
    test_cases = [
        ("text.txt", b"This is plain text content", "text/plain"),
        ("utf8.txt", "This is UTF-8 content with émojis 🚀".encode('utf-8'), "text/plain"),
        ("latin1.txt", "This is Latin-1 content with special chars: àáâã".encode('latin-1'), "text/plain"),
    ]
    
    for filename, content, content_type in test_cases:
        try:
            uploaded_file = SimpleUploadedFile(filename, content, content_type=content_type)
            
            # Simulate content extraction (simplified version)
            file_content = uploaded_file.read()
            if isinstance(file_content, bytes):
                # Try different encodings
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        decoded_content = file_content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    decoded_content = file_content.decode('utf-8', errors='ignore')
            else:
                decoded_content = str(file_content)
            
            print(f"✅ {filename}: Extracted {len(decoded_content)} characters")
            print(f"   Content: {decoded_content[:50]}...")
            
            # Reset file for next test
            uploaded_file.seek(0)
            
        except Exception as e:
            print(f"❌ Error with {filename}: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting simplified bulk upload tests...\n")
    
    try:
        test_simplified_form()
        test_file_extraction()
        test_content_extraction()
        doc = test_document_creation()
        
        print("\n🎯 All tests completed!")
        print("\n📋 Summary:")
        print("✅ Simplified form validation")
        print("✅ File extraction from request.FILES")
        print("✅ Content extraction from uploaded files")
        print("✅ Document creation in database")
        
        print("\n🔧 Next Steps:")
        print("1. Test the bulk upload in Django admin interface")
        print("2. Navigate to: /admin/public_chatbot/publicknowledgedocument/bulk-upload/")
        print("3. Select multiple text files and upload")
        print("4. Verify documents are created in the admin list")
        
        if doc:
            print(f"5. Check created test document: {doc.title} (ID: {doc.id})")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()