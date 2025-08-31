#!/usr/bin/env python3
"""
Milvus Search Methods Analyzer - Fixed Version
==============================================

This script explores all search methods and techniques supported by Milvus vector database.
It connects to your existing Milvus instance and demonstrates various search capabilities.

Requirements:
- pymilvus
- numpy

Install with: pip install pymilvus numpy
"""

import json
import random
import time
from typing import List, Dict, Any
import numpy as np
from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility
)

class MilvusSearchAnalyzer:
    """Comprehensive analyzer for Milvus search methods and techniques."""
    
    def __init__(self, host: str = "localhost", port: str = "19530"):
        """Initialize connection to Milvus."""
        self.host = host
        self.port = port
        self.connection_alias = "search_analyzer"
        self.test_collection_name = "search_test_collection_v2"
        self.dimension = 128
        self.collection = None
        
    def connect(self) -> bool:
        """Establish connection to Milvus."""
        try:
            connections.connect(
                alias=self.connection_alias,
                host=self.host,
                port=self.port
            )
            print(f"✅ Connected to Milvus at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Milvus: {e}")
            return False
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get detailed server information."""
        try:
            version = utility.get_server_version(using=self.connection_alias)
            collections = utility.list_collections(using=self.connection_alias)
            
            info = {
                "version": version,
                "collections": collections,
                "collection_count": len(collections)
            }
            
            print(f"🔍 Milvus Server Info:")
            print(f"   Version: {version}")
            print(f"   Collections: {len(collections)}")
            if collections:
                print(f"   Collection names: {', '.join(collections[:5])}{'...' if len(collections) > 5 else ''}")
            
            return info
        except Exception as e:
            print(f"❌ Error getting server info: {e}")
            return {}
    
    def create_test_collection(self) -> bool:
        """Create a test collection with various field types for comprehensive testing."""
        try:
            # Drop existing collection if it exists
            if utility.has_collection(self.test_collection_name, using=self.connection_alias):
                utility.drop_collection(self.test_collection_name, using=self.connection_alias)
                print(f"🗑️ Dropped existing collection: {self.test_collection_name}")
            
            # Define schema with multiple field types
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="rating", dtype=DataType.FLOAT),
                FieldSchema(name="year", dtype=DataType.INT32),
                FieldSchema(name="is_popular", dtype=DataType.BOOL),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Test collection for exploring Milvus search methods"
            )
            
            # Create collection
            self.collection = Collection(
                name=self.test_collection_name,
                schema=schema,
                using=self.connection_alias
            )
            
            print(f"✅ Created test collection: {self.test_collection_name}")
            print(f"   Dimension: {self.dimension}")
            print(f"   Fields: {[field.name for field in fields]}")
            
            return True
        except Exception as e:
            print(f"❌ Error creating test collection: {e}")
            return False
    
    def generate_and_insert_test_data(self, num_entities: int = 1000) -> bool:
        """Generate and insert test data in the correct format."""
        print(f"🔄 Generating and inserting {num_entities} test entities...")
        
        categories = ["Technology", "Science", "Entertainment", "Sports", "News", "Education"]
        
        try:
            # Generate data in batches to avoid memory issues
            batch_size = 100
            total_inserted = 0
            
            for batch_start in range(0, num_entities, batch_size):
                batch_end = min(batch_start + batch_size, num_entities)
                current_batch_size = batch_end - batch_start
                
                # Prepare batch data as separate lists for each field
                ids = []
                titles = []
                category_list = []
                ratings = []
                years = []
                popularities = []
                embeddings = []
                
                for i in range(batch_start, batch_end):
                    ids.append(i)
                    titles.append(f"Test Document {i+1}")
                    category_list.append(random.choice(categories))
                    ratings.append(round(random.uniform(1.0, 10.0), 1))
                    years.append(random.randint(2000, 2024))
                    popularities.append(random.choice([True, False]))
                    
                    # Generate normalized random vector
                    vector = np.random.random(self.dimension).astype(np.float32)
                    vector = vector / np.linalg.norm(vector)  # Normalize
                    embeddings.append(vector.tolist())
                
                # Insert batch data
                batch_data = [ids, titles, category_list, ratings, years, popularities, embeddings]
                
                insert_result = self.collection.insert(batch_data)
                total_inserted += insert_result.insert_count
                
                if batch_start == 0:  # Print details for first batch
                    print(f"   ✅ First batch inserted: {insert_result.insert_count} entities")
                    print(f"   Data types check:")
                    print(f"   - IDs: {type(ids[0])}")
                    print(f"   - Titles: {type(titles[0])}")
                    print(f"   - Embeddings: {len(embeddings[0])} dims")
            
            # Flush to ensure data is persisted
            self.collection.flush()
            print(f"✅ Successfully inserted {total_inserted} entities total")
            
            return True
            
        except Exception as e:
            print(f"❌ Error inserting test data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_indexes(self) -> Dict[str, bool]:
        """Create vector index for search operations."""
        print("🔧 Creating indexes...")
        results = {}
        
        try:
            # Create a simple IVF_FLAT index
            index_params = {
                "index_type": "IVF_FLAT",
                "metric_type": "L2",
                "params": {"nlist": 100}
            }
            
            print(f"   Creating IVF_FLAT index...")
            self.collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            results["vector_IVF_FLAT"] = True
            print(f"   ✅ IVF_FLAT index created successfully")
            
            # Load collection to memory
            print("🔄 Loading collection to memory...")
            self.collection.load()
            print("✅ Collection loaded to memory")
            
            return results
            
        except Exception as e:
            print(f"❌ Error creating indexes: {e}")
            results["vector_index"] = False
            return results
    
    def demonstrate_basic_vector_search(self) -> Dict[str, Any]:
        """Demonstrate basic vector similarity search."""
        print("\n🔍 Basic Vector Similarity Search")
        print("=" * 40)
        
        results = {}
        
        try:
            # Generate query vector
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            
            # Basic search
            search_results = self.collection.search(
                data=[query_vector.tolist()],
                anns_field="embedding",
                param=search_params,
                limit=10,
                output_fields=["title", "category", "rating"]
            )
            
            print(f"✅ Found {len(search_results[0])} results")
            for i, hit in enumerate(search_results[0][:5]):  # Show top 5
                print(f"   {i+1}. ID: {hit.id}, Distance: {hit.distance:.4f}")
                print(f"      Title: {hit.entity.get('title')}")
                print(f"      Category: {hit.entity.get('category')}")
                print(f"      Rating: {hit.entity.get('rating')}")
            
            results["basic_search"] = {
                "success": True,
                "count": len(search_results[0]),
                "avg_distance": sum(hit.distance for hit in search_results[0]) / len(search_results[0])
            }
            
        except Exception as e:
            print(f"❌ Error in basic vector search: {e}")
            results["basic_search"] = {"success": False, "error": str(e)}
        
        return results
    
    def demonstrate_filtered_search(self) -> Dict[str, Any]:
        """Demonstrate vector search with scalar filtering."""
        print("\n🎯 Filtered Vector Search")
        print("=" * 30)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            
            # Test different filter expressions
            filters = [
                'rating > 7.0',
                'category == "Technology"',
                'year >= 2020',
                'is_popular == True',
                'rating > 5.0 and category == "Science"'
            ]
            
            for filter_expr in filters:
                try:
                    print(f"\n🔍 Filter: {filter_expr}")
                    
                    search_results = self.collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=5,
                        expr=filter_expr,
                        output_fields=["title", "category", "rating", "year", "is_popular"]
                    )
                    
                    if search_results[0]:
                        print(f"   ✅ Found {len(search_results[0])} results")
                        for hit in search_results[0][:3]:  # Show top 3
                            print(f"      ID: {hit.id}, Distance: {hit.distance:.4f}")
                            print(f"      {hit.entity.get('title')} | {hit.entity.get('category')} | Rating: {hit.entity.get('rating')}")
                        
                        results[f"filter_{len(results)}"] = {
                            "expression": filter_expr,
                            "success": True,
                            "count": len(search_results[0])
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[f"filter_{len(results)}"] = {
                            "expression": filter_expr,
                            "success": True,
                            "count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error with filter '{filter_expr}': {e}")
                    results[f"filter_{len(results)}"] = {
                        "expression": filter_expr,
                        "success": False,
                        "error": str(e)
                    }
            
        except Exception as e:
            print(f"❌ Error in filtered search: {e}")
            results["filtered_search_error"] = str(e)
        
        return results
    
    def demonstrate_batch_search(self) -> Dict[str, Any]:
        """Demonstrate batch vector search."""
        print("\n📦 Batch Vector Search")
        print("=" * 25)
        
        results = {}
        
        try:
            # Generate multiple query vectors
            batch_size = 5
            query_vectors = []
            for _ in range(batch_size):
                vector = np.random.random(self.dimension).astype(np.float32)
                vector = vector / np.linalg.norm(vector)
                query_vectors.append(vector.tolist())
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            
            print(f"🔍 Searching with {batch_size} query vectors...")
            
            start_time = time.time()
            search_results = self.collection.search(
                data=query_vectors,
                anns_field="embedding",
                param=search_params,
                limit=5,
                output_fields=["title", "category", "rating"]
            )
            search_time = time.time() - start_time
            
            print(f"✅ Batch search completed in {search_time:.4f}s")
            print(f"📊 Results per query:")
            
            total_results = 0
            for i, query_result in enumerate(search_results):
                print(f"   Query {i+1}: {len(query_result)} results")
                if query_result:
                    best_hit = query_result[0]
                    print(f"      Best match: {best_hit.entity.get('title')} (distance: {best_hit.distance:.4f})")
                total_results += len(query_result)
            
            results["batch_search"] = {
                "success": True,
                "batch_size": batch_size,
                "total_results": total_results,
                "search_time": search_time,
                "avg_time_per_query": search_time / batch_size
            }
            
        except Exception as e:
            print(f"❌ Error in batch search: {e}")
            results["batch_search"] = {"success": False, "error": str(e)}
        
        return results
    
    def analyze_collection_stats(self) -> Dict[str, Any]:
        """Analyze collection statistics and performance."""
        print("\n📈 Collection Analysis")
        print("=" * 25)
        
        stats = {}
        
        try:
            # Get collection info
            print("📊 Collection Statistics:")
            print(f"   Name: {self.collection.name}")
            print(f"   Description: {self.collection.description}")
            
            # Entity count
            entity_count = self.collection.num_entities
            print(f"   Entity count: {entity_count}")
            stats["entity_count"] = entity_count
            
            # Schema info
            schema = self.collection.schema
            print(f"   Fields: {len(schema.fields)}")
            for field in schema.fields:
                print(f"      - {field.name}: {field.dtype}")
            
            stats["schema"] = {
                "field_count": len(schema.fields),
                "fields": [{"name": f.name, "type": str(f.dtype)} for f in schema.fields]
            }
            
            # Index info
            try:
                indexes = self.collection.indexes
                print(f"   Indexes: {len(indexes)}")
                for idx in indexes:
                    print(f"      - Field: {idx.field_name}")
                    print(f"        Type: {idx.params.get('index_type', 'Unknown')}")
                    print(f"        Metric: {idx.params.get('metric_type', 'Unknown')}")
                
                stats["indexes"] = [
                    {
                        "field": idx.field_name,
                        "type": idx.params.get('index_type'),
                        "metric": idx.params.get('metric_type')
                    } for idx in indexes
                ]
            except Exception as e:
                print(f"   Index info unavailable: {e}")
                stats["indexes"] = []
            
        except Exception as e:
            print(f"❌ Error analyzing collection: {e}")
            stats["error"] = str(e)
        
        return stats
    
    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run comprehensive analysis of all Milvus search methods."""
        print("🚀 Milvus Search Methods Comprehensive Analysis - Fixed Version")
        print("=" * 65)
        print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_results = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "connection": {"host": self.host, "port": self.port}
        }
        
        # Step 1: Connect
        if not self.connect():
            return {"error": "Failed to connect to Milvus"}
        
        # Step 2: Server info
        all_results["server_info"] = self.get_server_info()
        
        # Step 3: Create test collection
        if not self.create_test_collection():
            return {"error": "Failed to create test collection"}
        
        # Step 4: Generate and insert test data
        if not self.generate_and_insert_test_data(1000):
            return {"error": "Failed to insert test data"}
        
        # Step 5: Create indexes
        all_results["index_creation"] = self.create_indexes()
        
        # Step 6: Collection analysis
        all_results["collection_stats"] = self.analyze_collection_stats()
        
        # Step 7: Search method demonstrations
        all_results["search_methods"] = {}
        
        all_results["search_methods"]["basic_vector"] = self.demonstrate_basic_vector_search()
        all_results["search_methods"]["filtered"] = self.demonstrate_filtered_search()
        all_results["search_methods"]["batch"] = self.demonstrate_batch_search()
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 ANALYSIS SUMMARY")
        print("=" * 60)
        
        successful_methods = 0
        total_methods = 0
        
        for method_name, method_results in all_results["search_methods"].items():
            print(f"\n🔍 {method_name.replace('_', ' ').title()}:")
            if isinstance(method_results, dict):
                for sub_method, result in method_results.items():
                    if isinstance(result, dict) and "success" in result:
                        total_methods += 1
                        if result["success"]:
                            successful_methods += 1
                            status = "✅"
                        else:
                            status = "❌"
                        print(f"   {status} {sub_method}")
        
        success_rate = (successful_methods/total_methods*100) if total_methods > 0 else 0
        print(f"\n📊 Overall Success Rate: {successful_methods}/{total_methods} ({success_rate:.1f}%)")
        
        all_results["summary"] = {
            "successful_methods": successful_methods,
            "total_methods": total_methods,
            "success_rate": success_rate
        }
        
        return all_results
    
    def cleanup(self):
        """Clean up test resources."""
        try:
            if self.collection:
                utility.drop_collection(self.test_collection_name, using=self.connection_alias)
                print(f"🗑️ Cleaned up test collection: {self.test_collection_name}")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        try:
            connections.disconnect(self.connection_alias)
            print("🔌 Disconnected from Milvus")
        except Exception as e:
            print(f"⚠️ Disconnect warning: {e}")

def main():
    """Main execution function."""
    analyzer = MilvusSearchAnalyzer()
    
    try:
        # Run comprehensive analysis
        results = analyzer.run_comprehensive_analysis()
        
        # Save results to file
        output_file = f"milvus_search_analysis_fixed_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        return results
        
    except KeyboardInterrupt:
        print("\n⚠️ Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always cleanup
        analyzer.cleanup()

if __name__ == "__main__":
    print(__doc__)
    main()
