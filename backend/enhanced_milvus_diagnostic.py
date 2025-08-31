#!/usr/bin/env python3
"""
Enhanced Milvus Collection Schema Diagnostic Tool
================================================

This script will do a deeper inspection of your Milvus collections
to understand the exact data types and schema structure.
"""

import os
import sys
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from pymilvus import connections, Collection, utility, DataType
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

def get_data_type_name(dtype_value):
    """Convert Milvus data type number to readable name"""
    type_mapping = {
        1: "BOOL",
        2: "INT8", 
        3: "INT16",
        4: "INT32",
        5: "INT64",
        10: "FLOAT",
        11: "DOUBLE",
        20: "STRING",
        21: "VARCHAR",
        100: "BINARY_VECTOR",
        101: "FLOAT_VECTOR",
        102: "JSON",
        103: "ARRAY"
    }
    return type_mapping.get(dtype_value, f"UNKNOWN({dtype_value})")

def inspect_collection_detailed(collection_name):
    """Detailed inspection of a collection's schema"""
    try:
        print(f"\n🔍 DETAILED INSPECTION: {collection_name}")
        print("=" * 70)
        
        collection = Collection(collection_name, using="diagnostic")
        schema = collection.schema
        
        print(f"Collection: {collection_name}")
        print(f"Description: {schema.description if hasattr(schema, 'description') else 'No description'}")
        print(f"Total fields: {len(schema.fields)}")
        
        vector_fields = []
        embedding_fields = []
        
        print(f"\nDETAILED FIELD ANALYSIS:")
        print("-" * 70)
        
        for i, field in enumerate(schema.fields, 1):
            dtype_name = get_data_type_name(field.dtype)
            
            print(f"\n{i:2d}. Field: {field.name}")
            print(f"    Type Code: {field.dtype}")
            print(f"    Type Name: {dtype_name}")
            
            # Check for primary key
            if hasattr(field, 'is_primary') and field.is_primary:
                print(f"    Properties: PRIMARY KEY")
            elif hasattr(field, 'auto_id') and field.auto_id:
                print(f"    Properties: AUTO_ID")
            
            # Check parameters (important for vector fields)
            if hasattr(field, 'params') and field.params:
                print(f"    Parameters: {field.params}")
                if 'dim' in field.params:
                    print(f"    Dimension: {field.params['dim']}")
            
            # Identify vector fields
            if field.dtype == 101:  # FLOAT_VECTOR
                vector_fields.append(field.name)
                print(f"    >>> ✅ THIS IS A VECTOR FIELD! <<<")
            elif field.dtype == 100:  # BINARY_VECTOR
                vector_fields.append(field.name)
                print(f"    >>> ✅ THIS IS A BINARY VECTOR FIELD! <<<")
            elif 'embedding' in field.name.lower():
                embedding_fields.append(field.name)
                print(f"    >>> 🤔 EMBEDDING FIELD (but type {dtype_name}) <<<")
        
        # Try to get collection statistics
        try:
            num_entities = collection.num_entities
            print(f"\n📊 Collection Statistics:")
            print(f"    Total entities: {num_entities}")
        except Exception as e:
            print(f"\n⚠️  Could not get collection statistics: {e}")
        
        # Try to get index information
        try:
            indexes = collection.indexes
            if indexes:
                print(f"\n🔧 Indexes:")
                for idx in indexes:
                    print(f"    {idx}")
            else:
                print(f"\n🔧 No indexes found")
        except Exception as e:
            print(f"\n⚠️  Could not get index information: {e}")
        
        # Summary for this collection
        print(f"\n📋 SUMMARY FOR {collection_name}:")
        if vector_fields:
            print(f"    ✅ Vector fields found: {vector_fields}")
        elif embedding_fields:
            print(f"    🤔 Embedding-named fields found: {embedding_fields}")
            print(f"    ⚠️  But they're not typed as vector fields in Milvus schema")
        else:
            print(f"    ❌ No vector or embedding fields found")
        
        return vector_fields, embedding_fields
        
    except Exception as e:
        print(f"❌ Error inspecting {collection_name}: {e}")
        import traceback
        traceback.print_exc()
        return [], []

def test_embedding_field_search(collection_name, embedding_field):
    """Test if we can search using the embedding field even if it's not properly typed"""
    try:
        print(f"\n🧪 Testing search with field: {embedding_field}")
        
        collection = Collection(collection_name, using="diagnostic")
        
        # Try to load the collection
        collection.load()
        
        # Generate a test vector (assuming 384 dimensions based on your earlier output)
        import numpy as np
        test_vector = np.random.random(384).astype(np.float32)
        test_vector = test_vector / np.linalg.norm(test_vector)
        
        # Try a simple search
        results = collection.search(
            data=[test_vector.tolist()],
            anns_field=embedding_field,
            param={"metric_type": "L2"},
            limit=1
        )
        
        print(f"    ✅ Search successful with field '{embedding_field}'!")
        print(f"    Results found: {len(results[0]) if results else 0}")
        return True
        
    except Exception as e:
        print(f"    ❌ Search failed with field '{embedding_field}': {e}")
        return False

def main():
    print("🔍 ENHANCED Milvus Collection Schema Diagnostic")
    print("=" * 60)
    
    if not connect_to_milvus():
        return
    
    try:
        # List all collections
        collections = utility.list_collections(using="diagnostic")
        print(f"\n📁 Found {len(collections)} collections")
        
        all_vector_fields = {}
        all_embedding_fields = {}
        working_configs = {}
        
        # Inspect each collection in detail
        for collection_name in collections:
            vector_fields, embedding_fields = inspect_collection_detailed(collection_name)
            
            if vector_fields:
                all_vector_fields[collection_name] = vector_fields
            
            if embedding_fields:
                all_embedding_fields[collection_name] = embedding_fields
                
                # Test if we can search with embedding fields
                for embedding_field in embedding_fields:
                    if test_embedding_field_search(collection_name, embedding_field):
                        working_configs[collection_name] = embedding_field
                        break
        
        # Final summary
        print("\n" + "=" * 70)
        print("🎯 FINAL DIAGNOSTIC REPORT")
        print("=" * 70)
        
        if all_vector_fields:
            print(f"\n✅ PROPERLY TYPED VECTOR FIELDS:")
            for collection, fields in all_vector_fields.items():
                print(f"    {collection} → {fields}")
        
        if working_configs:
            print(f"\n🔧 WORKING EMBEDDING FIELDS (usable for search):")
            for collection, field in working_configs.items():
                print(f"    {collection} → '{field}'")
        
        if all_embedding_fields and not working_configs:
            print(f"\n⚠️  EMBEDDING FIELDS FOUND BUT NOT SEARCHABLE:")
            for collection, fields in all_embedding_fields.items():
                print(f"    {collection} → {fields}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        
        if working_configs:
            print("1. ✅ Found working embedding fields!")
            print("2. The Django Milvus Search package should work with these fields")
            print("3. Try running the algorithm test again:")
            print("   python manage.py test_milvus_algorithms")
            
            # Show the first working example
            first_collection = list(working_configs.keys())[0]
            first_field = working_configs[first_collection]
            print(f"\n4. Example working configuration:")
            print(f"   Collection: {first_collection}")
            print(f"   Vector field: '{first_field}'")
            
        elif all_embedding_fields:
            print("1. Found embedding fields but they may not be properly configured")
            print("2. Your collections might need to be recreated with proper vector field types")
            print("3. Check your vector_search app's collection creation code")
            
        else:
            print("1. No vector or embedding fields found")
            print("2. Your collections may not contain vector data")
            print("3. Check if your collections are being created properly")
        
    except Exception as e:
        print(f"❌ Enhanced diagnostic failed: {e}")
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
