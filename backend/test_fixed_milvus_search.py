#!/usr/bin/env python3
"""
Quick Test - Now that we know your collections have proper 'embedding' fields
"""

import os
import sys
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def test_milvus_search_with_embedding_field():
    """Test the fixed Django Milvus Search with embedding fields"""
    print("🧪 Testing Django Milvus Search with 'embedding' fields")
    print("=" * 60)
    
    try:
        from django_milvus_search import MilvusSearchService
        from django_milvus_search.models import SearchRequest, IndexType, MetricType
        from django_milvus_search.utils import generate_random_vector
        
        # Initialize service
        service = MilvusSearchService()
        
        # Get collections
        collections = service.list_collections()
        print(f"✅ Found {len(collections)} collections")
        
        # Test with first collection that has embedding field
        test_collection = "hello_68c8822f_0b2d_42aa_ae9c_cbf4571ee1f5"  # From your diagnostic
        
        print(f"🔍 Testing with collection: {test_collection}")
        
        # Generate test vector (384 dimensions based on your setup)
        test_vector = generate_random_vector(384)
        
        # Create search request
        request = SearchRequest(
            collection_name=test_collection,
            query_vectors=[test_vector],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType.L2,
            limit=3
        )
        
        print("⚡ Performing search...")
        
        # Perform search
        result = service.search(request)
        
        print(f"✅ SUCCESS! Search completed in {result.search_time:.4f}s")
        print(f"📊 Found {result.total_results} results")
        print(f"🔧 Algorithm used: {result.algorithm_used}")
        
        if result.hits:
            print(f"📝 Sample result: ID={result.hits[0].get('id')}, Distance={result.hits[0].get('distance', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            service.shutdown()
        except:
            pass

def main():
    print("🎯 Testing Fixed Django Milvus Search")
    print("=" * 45)
    
    success = test_milvus_search_with_embedding_field()
    
    if success:
        print("\n🎉 SUCCESS! The Django Milvus Search package is working!")
        print("\n🚀 Next steps:")
        print("1. Run full algorithm testing: python manage.py test_milvus_algorithms")
        print("2. Use the package in your applications")
        print("3. Clean up helper files: ./cleanup_milvus_files.sh")
    else:
        print("\n❌ Still having issues. Let's debug further...")

if __name__ == "__main__":
    main()
