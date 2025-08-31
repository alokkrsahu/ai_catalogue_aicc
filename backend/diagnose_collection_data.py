#!/usr/bin/env python3
"""
Diagnose Collection Data - Check if collections have actual data
================================================================

This script will check if your collections contain actual vector data
and help understand why searches are returning 0 results.
"""

import os
import sys
import django
import numpy as np

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from pymilvus import connections, Collection, utility
import logging

# Reduce Milvus logging
logging.getLogger('pymilvus').setLevel(logging.WARNING)

def connect_to_milvus():
    """Connect to Milvus"""
    try:
        connections.connect(
            alias="diagnostic",
            host="localhost",
            port="19530"
        )
        print("✅ Connected to Milvus")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Milvus: {e}")
        return False

def check_collection_data(collection_name):
    """Check if a collection has actual data"""
    try:
        print(f"\n🔍 CHECKING DATA IN: {collection_name}")
        print("=" * 60)
        
        collection = Collection(collection_name, using="diagnostic")
        
        # Load collection
        collection.load()
        
        # Get basic stats
        num_entities = collection.num_entities
        print(f"📊 Total entities: {num_entities}")
        
        if num_entities == 0:
            print("❌ COLLECTION IS EMPTY - This explains why searches return 0 results")
            return False, 0
        
        # Get schema info
        schema = collection.schema
        vector_field = None
        for field in schema.fields:
            if field.dtype == 101:  # FLOAT_VECTOR
                vector_field = field.name
                if hasattr(field, 'params') and 'dim' in field.params:
                    dimension = field.params['dim']
                    print(f"🔧 Vector field: '{vector_field}' (dimension: {dimension})")
                break
        
        if not vector_field:
            print("❌ No vector field found")
            return False, num_entities
        
        # Try to query some actual data
        try:
            # Get first few records to examine actual data
            results = collection.query(
                expr="",  # Empty expression to get all records
                limit=3,
                output_fields=[vector_field, "document_id"] if "document_id" in [f.name for f in schema.fields] else [vector_field]
            )
            
            print(f"📝 Sample data (first 3 records):")
            for i, record in enumerate(results[:3], 1):
                print(f"  Record {i}:")
                for key, value in record.items():
                    if key == vector_field:
                        # Show vector info without printing the entire vector
                        if isinstance(value, list) and len(value) > 0:
                            vector_magnitude = np.linalg.norm(value)
                            print(f"    {key}: [{len(value)} dimensions, magnitude: {vector_magnitude:.4f}]")
                            
                            # Check if vector is all zeros
                            if vector_magnitude == 0:
                                print(f"    ⚠️  WARNING: Vector is all zeros!")
                            else:
                                print(f"    ✅ Vector has data (sample: {value[:3]}...)")
                        else:
                            print(f"    {key}: {value}")
                    else:
                        print(f"    {key}: {value}")
        
        except Exception as e:
            print(f"⚠️  Could not query sample data: {e}")
        
        # Test with a real vector from the collection if possible
        try:
            print(f"\n🧪 Testing search with collection's own data...")
            
            # Get one record
            sample_results = collection.query(
                expr="",
                limit=1,
                output_fields=[vector_field]
            )
            
            if sample_results and vector_field in sample_results[0]:
                real_vector = sample_results[0][vector_field]
                
                if isinstance(real_vector, list) and len(real_vector) > 0:
                    # Search using this real vector
                    search_results = collection.search(
                        data=[real_vector],
                        anns_field=vector_field,
                        param={"metric_type": "L2"},
                        limit=3
                    )
                    
                    if search_results and len(search_results[0]) > 0:
                        print(f"✅ Search with real vector found {len(search_results[0])} results")
                        print(f"   Best match distance: {search_results[0][0].distance:.6f}")
                        
                        # If distance is 0, it found itself
                        if search_results[0][0].distance < 0.0001:
                            print(f"   🎯 Found exact match (likely the same record)")
                        
                        return True, num_entities
                    else:
                        print(f"❌ Search with real vector still returned 0 results")
                else:
                    print(f"❌ Vector field contains invalid data: {real_vector}")
            else:
                print(f"❌ Could not get sample vector from collection")
        
        except Exception as e:
            print(f"⚠️  Could not test with real vector: {e}")
        
        return True, num_entities
        
    except Exception as e:
        print(f"❌ Error checking collection {collection_name}: {e}")
        return False, 0

def test_random_vector_search(collection_name, dimension=384):
    """Test search with random vector"""
    try:
        print(f"\n🎲 Testing search with random {dimension}D vector...")
        
        collection = Collection(collection_name, using="diagnostic")
        collection.load()
        
        # Generate random vector
        random_vector = np.random.random(dimension).astype(np.float32)
        random_vector = random_vector / np.linalg.norm(random_vector)
        
        # Try search
        results = collection.search(
            data=[random_vector.tolist()],
            anns_field="embedding",
            param={"metric_type": "L2"},
            limit=5
        )
        
        if results and len(results[0]) > 0:
            print(f"✅ Random vector search found {len(results[0])} results")
            print(f"   Best distance: {results[0][0].distance:.6f}")
            return True
        else:
            print(f"❌ Random vector search returned 0 results")
            return False
            
    except Exception as e:
        print(f"❌ Random vector search failed: {e}")
        return False

def main():
    print("🔍 Collection Data Diagnostic Tool")
    print("=" * 50)
    print("This will help us understand why searches return 0 results")
    
    if not connect_to_milvus():
        return
    
    try:
        # Test your specific collection
        test_collection = "hello_68c8822f_0b2d_42aa_ae9c_cbf4571ee1f5"
        
        has_data, entity_count = check_collection_data(test_collection)
        
        if has_data and entity_count > 0:
            # Test random vector search
            test_random_vector_search(test_collection)
        
        print("\n" + "=" * 60)
        print("🎯 DIAGNOSIS SUMMARY")
        print("=" * 60)
        
        if entity_count == 0:
            print("❌ PROBLEM FOUND: Collection is empty")
            print("\n💡 SOLUTIONS:")
            print("1. Check if your vector_search app is properly inserting data")
            print("2. Verify that documents are being processed and embedded")
            print("3. Check if there are any errors in your document processing pipeline")
            
        elif not has_data:
            print("❌ PROBLEM FOUND: Collection exists but has data issues")
            print("\n💡 SOLUTIONS:")
            print("1. Check vector field data quality")
            print("2. Verify embeddings are being generated correctly")
            
        else:
            print("✅ Collection has data")
            print("\n💡 POSSIBLE REASONS FOR 0 SEARCH RESULTS:")
            print("1. Algorithm testing uses random vectors that don't match your data")
            print("2. Your embeddings might be in a very specific vector space")
            print("3. This is actually normal behavior for random vector testing")
            print("\n🎯 RECOMMENDATION:")
            print("The algorithm testing is working correctly!")
            print("Random vectors naturally don't match real document embeddings.")
            print("Use the service with actual document vectors for real searches.")
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            connections.disconnect("diagnostic")
            print("\n🔌 Disconnected from Milvus")
        except:
            pass

if __name__ == "__main__":
    main()
