#!/usr/bin/env python3
"""
Milvus Search Methods Analyzer
==============================

This script explores all search methods and techniques supported by Milvus vector database.
It connects to your existing Milvus instance and demonstrates various search capabilities.

Requirements:
- pymilvus
- numpy
- faker (for generating test data)

Install with: pip install pymilvus numpy faker
"""

import json
import random
import time
from typing import List, Dict, Any, Tuple
import numpy as np
from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, Index, SearchResult
)

try:
    from faker import Faker
    fake = Faker()
except ImportError:
    print("Warning: faker not installed. Using simple test data generation.")
    fake = None

class MilvusSearchAnalyzer:
    """Comprehensive analyzer for Milvus search methods and techniques."""
    
    def __init__(self, host: str = "localhost", port: str = "19530"):
        """Initialize connection to Milvus."""
        self.host = host
        self.port = port
        self.connection_alias = "search_analyzer"
        self.test_collection_name = "search_test_collection"
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
                print(f"   Collection names: {', '.join(collections)}")
            
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
                description="Test collection for exploring Milvus search methods",
                enable_dynamic_field=True
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
    
    def generate_test_data(self, num_entities: int = 1000) -> Dict[str, List]:
        """Generate test data for the collection."""
        print(f"🔄 Generating {num_entities} test entities...")
        
        categories = ["Technology", "Science", "Entertainment", "Sports", "News", "Education"]
        
        data = {
            "id": list(range(num_entities)),
            "title": [],
            "category": [],
            "rating": [],
            "year": [],
            "is_popular": [],
            "embedding": []
        }
        
        for i in range(num_entities):
            if fake:
                title = fake.sentence(nb_words=4).rstrip('.')
            else:
                title = f"Test Document {i+1}"
            
            data["title"].append(title)
            data["category"].append(random.choice(categories))
            data["rating"].append(round(random.uniform(1.0, 10.0), 1))
            data["year"].append(random.randint(2000, 2024))
            data["is_popular"].append(random.choice([True, False]))
            
            # Generate normalized random vector
            vector = np.random.random(self.dimension).astype(np.float32)
            vector = vector / np.linalg.norm(vector)  # Normalize
            data["embedding"].append(vector.tolist())
        
        print(f"✅ Generated test data with {len(data['id'])} entities")
        return data
    
    def insert_test_data(self, data: Dict[str, List]) -> bool:
        """Insert test data into the collection."""
        try:
            print("🔄 Inserting test data...")
            print(f"   Data format check:")
            print(f"   - IDs: {len(data['id'])} items, type: {type(data['id'][0]) if data['id'] else 'N/A'}")
            print(f"   - Titles: {len(data['title'])} items, type: {type(data['title'][0]) if data['title'] else 'N/A'}")
            print(f"   - Embeddings: {len(data['embedding'])} items, dim: {len(data['embedding'][0]) if data['embedding'] else 'N/A'}")
            
            # Convert data to proper format - each field should be a list
            formatted_data = [
                data["id"],
                data["title"],
                data["category"],
                data["rating"],
                data["year"],
                data["is_popular"],
                data["embedding"]
            ]
            
            insert_result = self.collection.insert(formatted_data)
            self.collection.flush()
            
            print(f"✅ Inserted {insert_result.insert_count} entities")
            print(f"   Primary keys: {len(insert_result.primary_keys)} generated")
            
            return True
        except Exception as e:
            print(f"❌ Error inserting test data: {e}")
            print(f"   Trying alternative data format...")
            try:
                # Alternative format: list of records
                records = []
                for i in range(len(data['id'])):
                    record = {
                        "id": data["id"][i],
                        "title": data["title"][i],
                        "category": data["category"][i],
                        "rating": data["rating"][i],
                        "year": data["year"][i],
                        "is_popular": data["is_popular"][i],
                        "embedding": data["embedding"][i]
                    }
                    records.append(record)
                
                print(f"   Trying with {len(records)} records...")
                insert_result = self.collection.insert(records)
                self.collection.flush()
                
                print(f"✅ Inserted {insert_result.insert_count} entities (alternative format)")
                return True
                
            except Exception as e2:
                print(f"❌ Alternative format also failed: {e2}")
                return False
    
    def create_indexes(self) -> Dict[str, bool]:
        """Create various types of indexes for different search scenarios."""
        print("🔧 Creating indexes...")
        results = {}
        
        # Vector index configurations to test
        vector_indexes = [
            {
                "name": "IVF_FLAT",
                "params": {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 100}}
            },
            {
                "name": "IVF_SQ8", 
                "params": {"index_type": "IVF_SQ8", "metric_type": "L2", "params": {"nlist": 100}}
            },
            {
                "name": "IVF_PQ",
                "params": {"index_type": "IVF_PQ", "metric_type": "L2", "params": {"nlist": 100, "m": 8, "nbits": 8}}
            },
            {
                "name": "HNSW",
                "params": {"index_type": "HNSW", "metric_type": "L2", "params": {"M": 16, "efConstruction": 200}}
            }
        ]
        
        # Try each vector index (only one can be active at a time)
        for idx_config in vector_indexes:
            try:
                # Drop existing index
                try:
                    self.collection.drop_index()
                except:
                    pass
                
                print(f"   Creating {idx_config['name']} index...")
                self.collection.create_index(
                    field_name="embedding",
                    index_params=idx_config["params"]
                )
                results[f"vector_{idx_config['name']}"] = True
                print(f"   ✅ {idx_config['name']} index created successfully")
                break  # Use the first successful index for testing
                
            except Exception as e:
                print(f"   ❌ Failed to create {idx_config['name']} index: {e}")
                results[f"vector_{idx_config['name']}"] = False
        
        # Load collection to memory
        try:
            self.collection.load()
            print("✅ Collection loaded to memory")
        except Exception as e:
            print(f"❌ Error loading collection: {e}")
        
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
            for i, hit in enumerate(search_results[0]):
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
                'rating > 5.0 and category == "Science"',
                'year >= 2015 and rating > 6.0 and is_popular == True'
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
                        
                        results[f"filter_{hash(filter_expr)}"] = {
                            "expression": filter_expr,
                            "success": True,
                            "count": len(search_results[0])
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[f"filter_{hash(filter_expr)}"] = {
                            "expression": filter_expr,
                            "success": True,
                            "count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error with filter '{filter_expr}': {e}")
                    results[f"filter_{hash(filter_expr)}"] = {
                        "expression": filter_expr,
                        "success": False,
                        "error": str(e)
                    }
            
        except Exception as e:
            print(f"❌ Error in filtered search: {e}")
            results["filtered_search_error"] = str(e)
        
        return results
    
    def demonstrate_range_search(self) -> Dict[str, Any]:
        """Demonstrate range search (if supported)."""
        print("\n📏 Range Search")
        print("=" * 20)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Range search parameters
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10, "radius": 1.0, "range_filter": 0.5}
            }
            
            print("🔍 Searching for vectors within distance range [0.5, 1.0]...")
            
            try:
                search_results = self.collection.search(
                    data=[query_vector.tolist()],
                    anns_field="embedding",
                    param=search_params,
                    limit=10,
                    output_fields=["title", "category", "rating"]
                )
                
                if search_results and search_results[0]:
                    print(f"✅ Found {len(search_results[0])} results in range")
                    for hit in search_results[0][:5]:
                        print(f"   ID: {hit.id}, Distance: {hit.distance:.4f}")
                        print(f"   Title: {hit.entity.get('title')}")
                    
                    results["range_search"] = {
                        "success": True,
                        "count": len(search_results[0]),
                        "supported": True
                    }
                else:
                    print("⚠️ No results in specified range")
                    results["range_search"] = {
                        "success": True,
                        "count": 0,
                        "supported": True
                    }
                    
            except Exception as e:
                if "range" in str(e).lower() or "radius" in str(e).lower():
                    print("❌ Range search not supported by current index type")
                    results["range_search"] = {
                        "success": False,
                        "supported": False,
                        "error": "Not supported by current index"
                    }
                else:
                    raise e
                    
        except Exception as e:
            print(f"❌ Error in range search: {e}")
            results["range_search"] = {
                "success": False,
                "error": str(e)
            }
        
        return results
    
    def demonstrate_hybrid_search(self) -> Dict[str, Any]:
        """Demonstrate hybrid search combining vector similarity and scalar filtering."""
        print("\n🔀 Hybrid Search (Vector + Scalar)")
        print("=" * 40)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            
            # Complex hybrid queries
            hybrid_queries = [
                {
                    "name": "High-rated Technology",
                    "expr": 'category == "Technology" and rating > 7.0',
                    "description": "Technology items with high ratings"
                },
                {
                    "name": "Recent Popular Content", 
                    "expr": 'year >= 2020 and is_popular == True',
                    "description": "Recent and popular content"
                },
                {
                    "name": "Premium Science Content",
                    "expr": 'category == "Science" and rating > 8.0 and year >= 2018',
                    "description": "High-quality recent science content"
                }
            ]
            
            for query_info in hybrid_queries:
                try:
                    print(f"\n🔍 {query_info['name']}")
                    print(f"   Description: {query_info['description']}")
                    print(f"   Filter: {query_info['expr']}")
                    
                    search_results = self.collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=5,
                        expr=query_info['expr'],
                        output_fields=["title", "category", "rating", "year", "is_popular"]
                    )
                    
                    if search_results[0]:
                        print(f"   ✅ Found {len(search_results[0])} matching results")
                        for i, hit in enumerate(search_results[0]):
                            print(f"      {i+1}. Distance: {hit.distance:.4f}")
                            print(f"         {hit.entity.get('title')}")
                            print(f"         {hit.entity.get('category')} | Rating: {hit.entity.get('rating')} | Year: {hit.entity.get('year')}")
                        
                        results[query_info['name']] = {
                            "success": True,
                            "count": len(search_results[0]),
                            "avg_distance": sum(hit.distance for hit in search_results[0]) / len(search_results[0])
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[query_info['name']] = {"success": True, "count": 0}
                        
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    results[query_info['name']] = {"success": False, "error": str(e)}
            
        except Exception as e:
            print(f"❌ Error in hybrid search: {e}")
            results["hybrid_search_error"] = str(e)
        
        return results
    
    def demonstrate_search_parameters(self) -> Dict[str, Any]:
        """Demonstrate different search parameters and their effects."""
        print("\n⚙️ Search Parameter Effects")
        print("=" * 35)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Test different search parameters
            param_tests = [
                {"nprobe": 10, "description": "Standard precision"},
                {"nprobe": 50, "description": "Higher precision"},
                {"nprobe": 100, "description": "Maximum precision"},
            ]
            
            for params in param_tests:
                try:
                    search_params = {"metric_type": "L2", "params": params}
                    
                    print(f"\n🔧 Testing nprobe={params['nprobe']} ({params['description']})")
                    
                    start_time = time.time()
                    search_results = self.collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding", 
                        param=search_params,
                        limit=10,
                        output_fields=["title", "rating"]
                    )
                    search_time = time.time() - start_time
                    
                    if search_results[0]:
                        avg_distance = sum(hit.distance for hit in search_results[0]) / len(search_results[0])
                        print(f"   ✅ Found {len(search_results[0])} results")
                        print(f"   ⏱️ Search time: {search_time:.4f}s")
                        print(f"   📊 Avg distance: {avg_distance:.4f}")
                        
                        results[f"nprobe_{params['nprobe']}"] = {
                            "success": True,
                            "time": search_time,
                            "avg_distance": avg_distance,
                            "count": len(search_results[0])
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[f"nprobe_{params['nprobe']}"] = {"success": True, "count": 0}
                        
                except Exception as e:
                    print(f"   ❌ Error with nprobe={params['nprobe']}: {e}")
                    results[f"nprobe_{params['nprobe']}"] = {"success": False, "error": str(e)}
            
        except Exception as e:
            print(f"❌ Error testing search parameters: {e}")
            results["parameter_test_error"] = str(e)
        
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
        print("🚀 Milvus Search Methods Comprehensive Analysis")
        print("=" * 55)
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
        test_data = self.generate_test_data(1000)
        if not self.insert_test_data(test_data):
            return {"error": "Failed to insert test data"}
        
        # Step 5: Create indexes
        all_results["index_creation"] = self.create_indexes()
        
        # Step 6: Collection analysis
        all_results["collection_stats"] = self.analyze_collection_stats()
        
        # Step 7: Search method demonstrations
        all_results["search_methods"] = {}
        
        all_results["search_methods"]["basic_vector"] = self.demonstrate_basic_vector_search()
        all_results["search_methods"]["filtered"] = self.demonstrate_filtered_search()
        all_results["search_methods"]["range"] = self.demonstrate_range_search()
        all_results["search_methods"]["hybrid"] = self.demonstrate_hybrid_search()
        all_results["search_methods"]["parameters"] = self.demonstrate_search_parameters()
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
        
        print(f"\n📊 Overall Success Rate: {successful_methods}/{total_methods} ({(successful_methods/total_methods*100):.1f}%)")
        
        all_results["summary"] = {
            "successful_methods": successful_methods,
            "total_methods": total_methods,
            "success_rate": successful_methods/total_methods if total_methods > 0 else 0
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
        output_file = f"milvus_search_analysis_{int(time.time())}.json"
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
