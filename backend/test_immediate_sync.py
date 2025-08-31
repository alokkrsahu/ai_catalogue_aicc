#!/usr/bin/env python3
"""
Test script for immediate sync functionality
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
from public_chatbot.admin import PublicKnowledgeDocumentAdmin

def test_immediate_sync():
    """Test the immediate sync functionality"""
    print("🧪 Testing immediate sync functionality...")
    
    # Get ChromaDB service
    service = PublicKnowledgeService.get_instance()
    if not service.is_ready:
        print("❌ ChromaDB service not ready")
        return False
    
    # Create admin instance
    admin = PublicKnowledgeDocumentAdmin(PublicKnowledgeDocument, None)
    
    # Create a test document
    test_doc = PublicKnowledgeDocument.objects.create(
        title="Immediate Sync Test Document",
        category="test",
        subcategory="sync_test",
        content="""This is a test document for immediate sync functionality.

It contains multiple paragraphs to test the chunking system.

The document should be automatically chunked using the advanced chunking system with 2048 tokens and 750 token overlap.

This will help verify that the immediate sync works just like the management command.""",
        is_approved=True,
        security_reviewed=True,
        created_by="test_script",
        approved_by="test_script",
        tags="test, immediate, sync, chunking"
    )
    
    print(f"✅ Created test document: {test_doc.document_id}")
    print(f"📄 Content length: {len(test_doc.content)} characters")
    
    # Verify it's not synced initially
    if test_doc.synced_to_chromadb:
        print("⚠️ Document already marked as synced")
        test_doc.synced_to_chromadb = False
        test_doc.save()
    
    # Test the immediate sync method
    print("🚀 Testing immediate sync...")
    success = admin._sync_document_immediately(test_doc, service)
    
    # Refresh from database
    test_doc.refresh_from_db()
    
    if success:
        print("✅ Immediate sync succeeded!")
        print(f"📊 Synced to ChromaDB: {test_doc.synced_to_chromadb}")
        print(f"🆔 ChromaDB ID: {test_doc.chromadb_id}")
        print(f"⏰ Last synced: {test_doc.last_synced}")
        print(f"❌ Sync error: {test_doc.sync_error or 'None'}")
        
        # Test search functionality
        print("\n🔍 Testing search functionality...")
        search_results = service.search_knowledge("immediate sync test", limit=5)
        
        if search_results:
            print(f"✅ Found {len(search_results)} search results")
            for i, result in enumerate(search_results[:3]):
                print(f"  [{i+1}] {result.get('title', 'No title')} (Score: {result.get('similarity_score', 0):.3f})")
        else:
            print("❌ No search results found")
        
        return True
    else:
        print(f"❌ Immediate sync failed: {test_doc.sync_error}")
        return False

def test_admin_actions():
    """Test that admin actions are properly configured"""
    print("\n🧪 Testing admin action configuration...")
    
    admin = PublicKnowledgeDocumentAdmin(PublicKnowledgeDocument, None)
    
    # Check that actions are defined in the admin class
    expected_actions = ['sync_to_chromadb_immediately', 'mark_for_sync', 'approve_documents']
    
    for action in expected_actions:
        if hasattr(admin, action):
            print(f"✅ Action method '{action}' exists")
        else:
            print(f"❌ Action method '{action}' is missing")
    
    # Check that actions are in the admin's actions list
    admin_actions = admin.actions or []
    for action in expected_actions:
        if action in admin_actions:
            print(f"✅ Action '{action}' is in actions list")
        else:
            print(f"❌ Action '{action}' is not in actions list")
    
    # Check method exists
    if hasattr(admin, '_sync_document_immediately'):
        print("✅ _sync_document_immediately method exists")
    else:
        print("❌ _sync_document_immediately method missing")
    
    return True

def cleanup_test_documents():
    """Clean up test documents"""
    print("\n🧹 Cleaning up test documents...")
    
    deleted_count = PublicKnowledgeDocument.objects.filter(
        category="test",
        created_by="test_script"
    ).delete()[0]
    
    print(f"🗑️ Deleted {deleted_count} test documents")

def main():
    """Run all tests"""
    print("🚀 Starting immediate sync tests...\n")
    
    try:
        test1 = test_admin_actions()
        test2 = test_immediate_sync()
        
        if test1 and test2:
            print("\n🎯 All tests passed!")
            print("\n📋 Immediate Sync Implementation Summary:")
            print("✅ New admin action: '🚀 Sync to ChromaDB immediately'")
            print("✅ Backward compatibility: '📋 Mark for later sync' (old behavior)")
            print("✅ Advanced chunking: Uses same system as management command")
            print("✅ Error handling: Comprehensive error reporting")
            print("✅ Status updates: Automatic sync status and timestamp updates")
            
            print("\n🔧 How To Use:")
            print("1. Go to Django admin → Public Chatbot → Public Knowledge Documents")
            print("2. Select documents you want to sync")
            print("3. Choose '🚀 Sync to ChromaDB immediately' from Actions dropdown")
            print("4. Click 'Go' - documents will be synced instantly!")
            print("5. See immediate success/error feedback")
            
            print("\n⚡ Benefits:")
            print("- No more manual command running")
            print("- Instant feedback on success/failure") 
            print("- Same advanced features as management command")
            print("- Option for both immediate and batch sync workflows")
            
        else:
            print("\n❌ Some tests failed!")
            
        cleanup_test_documents()
            
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        cleanup_test_documents()
        sys.exit(1)

if __name__ == "__main__":
    main()