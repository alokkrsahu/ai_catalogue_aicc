#!/usr/bin/env python3
"""
Enhanced DocAware search diagnostics
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import IntelliDocProject
from django_milvus_search import MilvusSearchService
from django_milvus_search.models import SearchRequest, IndexType, MetricType, SearchParams

def diagnose_docaware_search():
    """Diagnose why DocAware search returns 0 results"""
    
    project_id = "8660355a-7fd0-4434-a380-7cf80442603c"
    print(f"🔍 DIAGNOSING: DocAware search for project {project_id}")
    
    try:
        # 1. Check project exists
        print("\n📋 Step 1: Check project exists...")
        project = IntelliDocProject.objects.get(project_id=project_id)
        collection_name = project.generate_collection_name()
        print(f"✅ Found project: {project.name}")
        print(f"✅ Collection name: {collection_name}")
        
        # 2. Check Milvus service
        print("\n📋 Step 2: Check Milvus service...")
        milvus_service = MilvusSearchService()
        print(f"✅ Milvus service initialized")
        
        # 3. List all collections
        print("\n📋 Step 3: List all collections...")
        try:
            collections = milvus_service.list_collections()
            print(f"✅ Found {len(collections)} collections:")
            for i, col in enumerate(collections, 1):
                print(f"   {i}. {col}")
                
            # Check if our collection exists
            if collection_name in collections:
                print(f"✅ Target collection '{collection_name}' EXISTS")
            else:
                print(f"❌ Target collection '{collection_name}' NOT FOUND")
                print("🔧 This is likely the issue - collection doesn't exist")
                return
                
        except Exception as e:
            print(f"❌ Failed to list collections: {e}")
            return
        
        # 4. Check collection statistics
        print(f"\n📋 Step 4: Check collection '{collection_name}' statistics...")
        try:
            # Try to get collection info
            # Note: This may need to be adjusted based on MilvusSearchService API
            print(f"ℹ️  Collection exists, checking contents...")
            
            # Try a simple search to see if there are any vectors
            from agent_orchestration.docaware.embedding_service import DocAwareEmbeddingService
            
            embedding_service = DocAwareEmbeddingService()
            test_query = "test query"
            query_vector = embedding_service.encode_query(test_query)
            print(f"✅ Generated query embedding: {len(query_vector)} dimensions")
            
            # Create search request
            search_request = SearchRequest(
                collection_name=collection_name,
                query_vectors=[query_vector],
                index_type=IndexType.AUTOINDEX,
                metric_type=MetricType.COSINE,
                limit=1  # Just get 1 result to test
            )
            
            print(f"🔍 Performing test search...")
            search_result = milvus_service.search(search_request)
            
            print(f"📊 Search result type: {type(search_result)}")
            print(f"📊 Search result: {search_result}")
            
            if hasattr(search_result, 'hits'):
                hits = search_result.hits
                print(f"📊 Number of hits: {len(hits)}")
                if hits:
                    print(f"📊 First hit: {hits[0]}")
                    print("✅ Collection has data!")
                else:
                    print("❌ Collection exists but has NO DATA")
                    print("🔧 The collection is empty - documents need to be processed/indexed")
            else:
                print(f"❌ Unexpected search result format: {search_result}")
                
        except Exception as e:
            print(f"❌ Failed to search collection: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return
        
        # 5. Check document processing status
        print(f"\n📋 Step 5: Check document processing status...")
        try:
            documents = project.documents.all()
            print(f"📄 Project has {len(documents)} documents:")
            for doc in documents:
                print(f"   - {doc.title} (processed: {doc.processing_status})")
                
            if not documents:
                print("❌ Project has NO DOCUMENTS")
                print("🔧 You need to upload and process documents first")
            elif all(doc.processing_status != 'completed' for doc in documents):
                print("❌ No documents are fully processed")
                print("🔧 Documents need to be processed before search works")
            else:
                processed_docs = [doc for doc in documents if doc.processing_status == 'completed']
                print(f"✅ {len(processed_docs)} documents are processed and should be searchable")
                
        except Exception as e:
            print(f"❌ Failed to check documents: {e}")
            
        print(f"\n🎯 SUMMARY:")
        print(f"   - Project: ✅ {project.name}")
        print(f"   - Collection: {'✅' if collection_name in collections else '❌'} {collection_name}")
        print(f"   - Documents: {len(documents)} total")
        print(f"   - Search: Testing completed above")
        
    except IntelliDocProject.DoesNotExist:
        print(f"❌ Project {project_id} not found in database")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    diagnose_docaware_search()
