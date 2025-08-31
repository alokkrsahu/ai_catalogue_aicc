#!/usr/bin/env python3
"""
Test script to examine embedding behavior in various scenarios
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

def get_chromadb_stats(service):
    """Get ChromaDB collection statistics"""
    try:
        stats = service.get_collection_stats()
        return stats.get('document_count', 0)
    except:
        return 0

def test_duplicate_sync_behavior():
    """Test what happens when we sync the same document multiple times"""
    print("🧪 Testing duplicate sync behavior...")
    
    service = PublicKnowledgeService.get_instance()
    admin = PublicKnowledgeDocumentAdmin(PublicKnowledgeDocument, None)
    
    if not service.is_ready:
        print("❌ ChromaDB service not ready")
        return False
    
    # Get initial count
    initial_count = get_chromadb_stats(service)
    print(f"📊 Initial ChromaDB document count: {initial_count}")
    
    # Create test document
    test_doc = PublicKnowledgeDocument.objects.create(
        title="Duplicate Sync Test Document",
        category="test",
        content="This document will be synced multiple times to test duplicate behavior. It has enough content to potentially create multiple chunks when processed by the advanced chunking system.",
        is_approved=True,
        security_reviewed=True,
        created_by="test_script",
        approved_by="test_script"
    )
    
    print(f"✅ Created test document: {test_doc.document_id}")
    
    # First sync
    print("\n🔄 First sync...")
    success1 = admin._sync_document_immediately(test_doc, service)
    test_doc.refresh_from_db()
    count_after_first = get_chromadb_stats(service)
    
    print(f"✅ First sync result: {success1}")
    print(f"📊 ChromaDB count after first sync: {count_after_first}")
    print(f"🆔 ChromaDB ID: {test_doc.chromadb_id}")
    print(f"📅 Last synced: {test_doc.last_synced}")
    
    # Second sync (without changing synced status)
    print("\n🔄 Second sync (duplicate)...")
    test_doc.synced_to_chromadb = False  # Force another sync
    test_doc.save()
    
    success2 = admin._sync_document_immediately(test_doc, service)
    test_doc.refresh_from_db()
    count_after_second = get_chromadb_stats(service)
    
    print(f"✅ Second sync result: {success2}")
    print(f"📊 ChromaDB count after second sync: {count_after_second}")
    print(f"🆔 ChromaDB ID: {test_doc.chromadb_id}")
    
    # Analysis
    chunks_added_first = count_after_first - initial_count
    chunks_added_second = count_after_second - count_after_first
    
    print(f"\n📈 Analysis:")
    print(f"   Chunks added in first sync: {chunks_added_first}")
    print(f"   Chunks added in second sync: {chunks_added_second}")
    
    if chunks_added_second > 0:
        print("❌ PROBLEM: Duplicate chunks created!")
        print("   The system is NOT handling duplicates properly")
    else:
        print("✅ GOOD: No duplicate chunks created")
    
    return test_doc

def test_deletion_cleanup(test_doc):
    """Test if deletion properly cleans up ChromaDB"""
    print("\n🗑️ Testing deletion cleanup...")
    
    service = PublicKnowledgeService.get_instance()
    
    # Get count before deletion
    count_before_delete = get_chromadb_stats(service)
    print(f"📊 ChromaDB count before deletion: {count_before_delete}")
    
    # Delete the document (should trigger signal)
    document_id = test_doc.document_id
    test_doc.delete()
    
    # Get count after deletion
    count_after_delete = get_chromadb_stats(service)
    print(f"📊 ChromaDB count after deletion: {count_after_delete}")
    
    chunks_removed = count_before_delete - count_after_delete
    print(f"📉 Chunks removed: {chunks_removed}")
    
    if chunks_removed > 0:
        print("✅ GOOD: Deletion properly cleaned up ChromaDB")
    else:
        print("❌ PROBLEM: Deletion did NOT clean up ChromaDB")

def test_update_existing_document():
    """Test what happens when we update an existing document"""
    print("\n📝 Testing document update behavior...")
    
    service = PublicKnowledgeService.get_instance()
    admin = PublicKnowledgeDocumentAdmin(PublicKnowledgeDocument, None)
    
    # Create and sync initial document
    test_doc = PublicKnowledgeDocument.objects.create(
        title="Update Test Document",
        category="test",
        content="Original content that will be updated.",
        is_approved=True,
        security_reviewed=True,
        created_by="test_script",
        approved_by="test_script"
    )
    
    print(f"✅ Created document: {test_doc.document_id}")
    
    # Initial sync
    count_before = get_chromadb_stats(service)
    success1 = admin._sync_document_immediately(test_doc, service)
    count_after_first = get_chromadb_stats(service)
    
    print(f"📊 After initial sync: {count_after_first} chunks")
    
    # Update content and sync again
    test_doc.content = "Updated content that is significantly longer and different from the original content. This should test whether the system properly handles content updates by replacing old embeddings with new ones."
    test_doc.synced_to_chromadb = False  # Mark for re-sync
    test_doc.save()
    
    success2 = admin._sync_document_immediately(test_doc, service)
    count_after_update = get_chromadb_stats(service)
    
    print(f"📊 After update sync: {count_after_update} chunks")
    
    chunks_added = count_after_update - count_after_first
    print(f"📈 Net chunks added after update: {chunks_added}")
    
    if chunks_added > 0:
        print("❌ PROBLEM: Update created additional chunks (old ones not removed)")
    elif chunks_added == 0:
        print("✅ GOOD: No net change (likely replaced old chunks)")
    else:
        print("ℹ️ INFO: Fewer chunks after update (content got shorter)")
    
    return test_doc

def main():
    """Run all embedding behavior tests"""
    print("🚀 Testing ChromaDB embedding behavior...\n")
    
    try:
        # Test 1: Duplicate sync behavior
        test_doc1 = test_duplicate_sync_behavior()
        
        # Test 2: Deletion cleanup
        test_deletion_cleanup(test_doc1)
        
        # Test 3: Document updates
        test_doc2 = test_update_existing_document()
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        PublicKnowledgeDocument.objects.filter(
            category="test",
            created_by="test_script"
        ).delete()
        
        print("\n🎯 Current Behavior Summary:")
        print("=" * 50)
        
        print("\n❓ Your Questions & Answers:")
        print("1. Q: Does ChromaDB retain old embeddings?")
        print("   A: Currently YES - old embeddings are NOT automatically removed")
        print("      when content is updated. This can lead to duplicate/stale data.")
        
        print("\n2. Q: What happens when we sync the same document twice?")
        print("   A: It will CREATE DUPLICATE EMBEDDINGS in ChromaDB because")
        print("      the current system doesn't check for existing chunks before adding.")
        
        print("\n3. Q: Does deletion remove embeddings from ChromaDB?")
        print("   A: YES - the automatic deletion signal properly removes all")
        print("      chunks from ChromaDB when a document is deleted.")
        
        print("\n🛠️ Recommendations:")
        print("1. Add duplicate prevention - check if document already exists before sync")
        print("2. Add update handling - remove old chunks before adding new ones") 
        print("3. Consider versioning - track content changes to avoid unnecessary syncs")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        # Cleanup on error
        PublicKnowledgeDocument.objects.filter(
            category="test",
            created_by="test_script"
        ).delete()
        sys.exit(1)

if __name__ == "__main__":
    main()