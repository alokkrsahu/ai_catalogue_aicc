#!/usr/bin/env python3
"""
Milvus Collection Schema Diagnostic Tool
========================================

This script will inspect your Milvus collections and show their schemas,
helping us understand the correct field names to use.
"""

import os
import sys
import django

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

def inspect_collection_schema(collection_name):
    """Inspect a single collection's schema"""
    try:
        print(f"\n🔍 Inspecting collection: {collection_name}")
        print("-" * 50)
        
        collection = Collection(collection_name, using="diagnostic")
        schema = collection.schema
        
        print(f"Collection: {collection_name}")
        print(f"Description: {schema.description if hasattr(schema, 'description') else 'No description'}")
        print(f"Total fields: {len(schema.fields)}")
        
        vector_fields = []
        print(f"\nFields:")
        
        for i, field in enumerate(schema.fields, 1):
            field_info = f"  {i}. {field.name}"
            field_info += f" (type: {field.dtype})"
            
            if hasattr(field, 'is_primary') and field.is_primary:
                field_info += " [PRIMARY]"
            
            if hasattr(field, 'auto_id') and field.auto_id:
                field_info += " [AUTO_ID]"
            
            # Check if it's a vector field
            if str(field.dtype).upper() in ['FLOAT_VECTOR', 'BINARY_VECTOR']:
                vector_fields.append(field.name)
                field_info += " [VECTOR]"
                
                # Get dimension info
                if hasattr(field, 'params') and field.params and 'dim' in field.params:
                    field_info += f" [DIM: {field.params['dim']}]"
            
            print(field_info)
        
        # Summary
        if vector_fields:
            print(f"\n✅ Vector fields found: {vector_fields}")
            return vector_fields[0], schema.fields
        else:
            print(f"\n⚠️  No vector fields found in {collection_name}")
            return None, schema.fields
        
    except Exception as e:
        print(f"❌ Error inspecting {collection_name}: {e}")
        return None, []

def main():
    print("🔍 Milvus Collection Schema Diagnostic Tool")
    print("=" * 55)
    
    if not connect_to_milvus():
        return
    
    try:
        # List all collections
        collections = utility.list_collections(using="diagnostic")
        print(f"\n📁 Found {len(collections)} collections:")
        for i, col in enumerate(collections, 1):
            print(f"  {i}. {col}")
        
        # Inspect each collection
        all_vector_fields = {}
        all_schemas = {}
        
        for collection_name in collections:
            vector_field, fields = inspect_collection_schema(collection_name)
            if vector_field:
                all_vector_fields[collection_name] = vector_field
            all_schemas[collection_name] = fields
        
        # Summary report
        print("\n" + "=" * 55)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 55)
        
        print(f"\nCollections with vector fields:")
        if all_vector_fields:
            for collection, vector_field in all_vector_fields.items():
                print(f"  ✅ {collection} → vector field: '{vector_field}'")
        else:
            print("  ❌ No collections with vector fields found")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if all_vector_fields:
            print("1. The Django Milvus Search package will now auto-detect these vector fields")
            print("2. You can run the algorithm test again:")
            print("   python manage.py test_milvus_algorithms")
            
            # Show example usage
            first_collection = list(all_vector_fields.keys())[0]
            vector_field = all_vector_fields[first_collection]
            print(f"\n3. Example manual search (if needed):")
            print(f"   Collection: {first_collection}")
            print(f"   Vector field: {vector_field}")
        else:
            print("1. No vector fields found - check if your collections have vector data")
            print("2. Common vector field names: vector, embedding, embeddings, vec")
            print("3. Make sure your collections are properly created with vector fields")
        
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
