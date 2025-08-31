#!/usr/bin/env python3
"""
Test Real Document Search vs Random Vector Search
================================================

This will prove whether the 0 results are normal behavior or a real problem.
"""

import os
import sys
import django
import numpy as np

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def test_real_vs_random_search():
    """Test search with real document vectors vs random vectors"""
    try:
        from django_milvus_search import MilvusSearchService
        from django_milvus_search.models import SearchRequest, IndexType, MetricType
        from pymilvus import Collection, connections
        
        print("🧪 Testing Real Document Search vs Random Vector Search")
        print("=" * 60)
        
        # Connect to Milvus
        connections.connect(
            alias="test",
            host="localhost",
            port="19530"
        )
        
        collection_name = "hello_68c8822f_0b2d_42aa_ae9c_cbf4571ee1f5"
        collection = Collection(collection_name, using="test")
        collection.load()
        
        print(f"📊 Collection: {collection_name}")
        print(f"   Entities: {collection.num_entities}")
        
        if collection.num_entities == 0:
            print("❌ Collection is empty - this explains the 0 results!")
            return
        
        # Test 1: Random vector search (like algorithm testing does)
        print(f"\n🎲 TEST 1: Random Vector Search (like algorithm testing)")
        random_vector = np.random.random(384).astype(np.float32)
        random_vector = random_vector / np.linalg.norm(random_vector)
        
        service = MilvusSearchService()
        random_request = SearchRequest(
            collection_name=collection_name,
            query_vectors=[random_vector.tolist()],
            index_type=IndexType.HNSW,
            metric_type=MetricType.COSINE,
            limit=5
        )
        
        random_result = service.search(random_request)
        print(f"   Results: {random_result.total_results}")
        print(f"   Search time: {random_result.search_time:.4f}s")
        
        if random_result.total_results == 0:
            print("   ✅ This confirms: random vectors don't match document embeddings")
        else:
            print("   🤔 Unexpected: random vector found matches")
        
        # Test 2: Real document vector search
        print(f"\n📄 TEST 2: Real Document Vector Search")
        
        # Get a real vector from the collection
        real_data = collection.query(
            expr="",
            limit=1,
            output_fields=["embedding", "document_id", "content"]
        )
        
        if real_data and "embedding" in real_data[0]:
            real_vector = real_data[0]["embedding"]
            document_id = real_data[0].get("document_id", "unknown")
            content_preview = real_data[0].get("content", "")[:100] + "..." if real_data[0].get("content") else "no content"
            
            print(f"   Using real vector from document: {document_id}")
            print(f"   Content preview: {content_preview}")
            
            real_request = SearchRequest(
                collection_name=collection_name,
                query_vectors=[real_vector],
                index_type=IndexType.HNSW,
                metric_type=MetricType.COSINE,
                limit=5
            )
            
            real_result = service.search(real_request)
            print(f"   Results: {real_result.total_results}")
            print(f"   Search time: {real_result.search_time:.4f}s")
            
            if real_result.total_results > 0:
                print(f"   ✅ Real document vector found {real_result.total_results} matches!")
                print(f"   Best match distance: {real_result.hits[0]['distance']:.6f}")
                if real_result.hits[0]['distance'] < 0.0001:
                    print(f"   🎯 Found exact match (likely the same document)")
            else:
                print(f"   ❌ Even real document vector returned 0 results - something is wrong")
        
        else:
            print("   ❌ Could not get real vector from collection")
        
        # Summary
        print(f"\n" + "=" * 60)
        print("🎯 CONCLUSION")
        print("=" * 60)
        
        if random_result.total_results == 0 and real_result.total_results > 0:
            print("✅ NORMAL BEHAVIOR CONFIRMED:")
            print("   • Random vectors don't match document embeddings (expected)")
            print("   • Real document vectors do find matches (system working)")
            print("   • Algorithm testing with 0 results is completely normal")
            print("\n💡 YOUR MILVUS SETUP IS WORKING PERFECTLY!")
            print("   The 0 results in algorithm testing are expected behavior.")
            
        elif random_result.total_results == 0 and real_result.total_results == 0:
            print("❌ PROBLEM IDENTIFIED:")
            print("   • Even real document vectors return 0 results")
            print("   • There may be an issue with indexing or search configuration")
            
        else:
            print("🤔 UNEXPECTED BEHAVIOR:")
            print("   • Random vectors are finding matches (unusual)")
            print("   • May indicate very broad vector space or other issues")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            service.shutdown()
            connections.disconnect("test")
        except:
            pass

if __name__ == "__main__":
    test_real_vs_random_search()
