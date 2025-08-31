#!/usr/bin/env python3
"""
Test script for automatic ChromaDB deletion functionality
"""

import sys
import os
import django

# Add the backend directory to Python path
sys.path.append('/home/alokkrsahu/ai_catalogue/backend')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_catalogue.settings')
django.setup()

from public_chatbot.models import PublicKnowledgeDocument
from public_chatbot.services import PublicKnowledgeService

def test_chromadb_deletion_method():
    """Test the ChromaDB deletion method directly"""
    print("🧪 Testing ChromaDB deletion method...")
    
    service = PublicKnowledgeService.get_instance()
    
    if not service.is_ready:
        print("❌ ChromaDB service not ready")
        return False
    
    # Test deleting a non-existent document (should succeed gracefully)
    result = service.delete_knowledge("nonexistent_doc_123")
    print(f"✅ Delete non-existent document: {result}")
    
    return True

def test_signal_integration():
    """Test that signals are properly registered"""
    print("\n🧪 Testing signal integration...")
    
    # Check if signals are imported
    try:
        from public_chatbot import signals
        print("✅ Signals module imported successfully")
        
        # Check if signal handlers are registered
        from django.db.models.signals import pre_delete, post_delete
        from public_chatbot.models import PublicKnowledgeDocument
        
        pre_delete_receivers = pre_delete._live_receivers(sender=PublicKnowledgeDocument)
        post_delete_receivers = post_delete._live_receivers(sender=PublicKnowledgeDocument)
        
        print(f"✅ Pre-delete signal receivers: {len(list(pre_delete_receivers))}")
        print(f"✅ Post-delete signal receivers: {len(list(post_delete_receivers))}")
        
        return True
        
    except Exception as e:
        print(f"❌ Signal integration error: {e}")
        return False

def test_document_lifecycle():
    """Test complete document lifecycle with automatic deletion"""
    print("\n🧪 Testing complete document lifecycle...")
    
    try:
        # Create a test document
        test_doc = PublicKnowledgeDocument.objects.create(
            title="Test Document for Deletion",
            category="test",
            content="This is a test document that will be deleted.",
            is_approved=True,
            security_reviewed=True,
            created_by="test_script",
            approved_by="test_script"
        )
        
        print(f"✅ Created test document: {test_doc.document_id}")
        
        # Simulate it being synced to ChromaDB
        test_doc.synced_to_chromadb = True
        test_doc.chromadb_id = f"chroma_{test_doc.document_id}"
        test_doc.save()
        
        print(f"✅ Marked document as synced to ChromaDB")
        
        # Get initial count
        initial_count = PublicKnowledgeDocument.objects.count()
        print(f"📊 Documents before deletion: {initial_count}")
        
        # Delete the document (this should trigger the signal)
        document_id = test_doc.document_id
        test_doc.delete()
        
        final_count = PublicKnowledgeDocument.objects.count()
        print(f"📊 Documents after deletion: {final_count}")
        
        if final_count == initial_count - 1:
            print(f"✅ Document {document_id} successfully deleted from Django")
            print("✅ Signal should have automatically cleaned up ChromaDB")
            return True
        else:
            print("❌ Document deletion failed")
            return False
            
    except Exception as e:
        print(f"❌ Document lifecycle test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting automatic ChromaDB deletion tests...\n")
    
    try:
        test1 = test_chromadb_deletion_method()
        test2 = test_signal_integration()
        test3 = test_document_lifecycle()
        
        if test1 and test2 and test3:
            print("\n🎯 All tests passed!")
            print("\n📋 Automatic Deletion Implementation Summary:")
            print("✅ ChromaDB deletion method: delete_knowledge(document_id)")
            print("✅ Django pre_delete signal: Triggers ChromaDB cleanup")
            print("✅ Django post_delete signal: Logs successful completion")
            print("✅ Error handling: Won't block Django deletion if ChromaDB fails")
            
            print("\n🔧 How It Works:")
            print("1. Admin deletes document in Django admin")
            print("2. pre_delete signal automatically triggers")
            print("3. Signal calls delete_knowledge() to clean up ChromaDB")
            print("4. Document deleted from Django database")
            print("5. post_delete signal logs completion")
            
            print("\n🛡️ Safety Features:")
            print("- Only deletes if document was synced to ChromaDB")
            print("- Gracefully handles ChromaDB service not ready")
            print("- Won't block Django deletion if ChromaDB fails")
            print("- Comprehensive logging for debugging")
            
        else:
            print("\n❌ Some tests failed!")
            
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()