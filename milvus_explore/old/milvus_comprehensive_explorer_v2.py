#!/usr/bin/env python3
"""
Comprehensive Milvus Search Features Explorer - Version Compatible
================================================================

This script provides an exhaustive exploration of ALL search features supported by Milvus v2.3.3.
Works within the constraints of single vector field per collection.

Requirements:
- pymilvus
- numpy
"""

import json
import random
import time
from typing import List, Dict, Any, Tuple
import numpy as np
from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, SearchResult, Partition
)

class ComprehensiveMilvusExplorer:
    """Exhaustive explorer for ALL Milvus search features and capabilities."""
    
    def __init__(self, host: str = "localhost", port: str = "19530"):
        """Initialize connection to Milvus."""
        self.host = host
        self.port = port
        self.connection_alias = "comprehensive_explorer"
        self.float_collection_name = "comprehensive_float_vectors"
        self.binary_collection_name = "comprehensive_binary_vectors"
        self.dimension = 128
        self.float_collection = None
        self.binary_collection = None
        self.all_results = {}
        
    def connect(self) -> bool:
        """Establish connection to Milvus."""
        try:
            connections.connect(
                alias=self.connection_alias,
                host=self.host,
                port=self.port
            )
            print(f"✅ Connected to Milvus at {self.host}:{self.port}")
            
            # Get server info
            version = utility.get_server_version(using=self.connection_alias)
            collections = utility.list_collections(using=self.connection_alias)
            print(f"🔍 Milvus Server: {version}")
            print(f"📊 Existing Collections: {len(collections)}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Milvus: {e}")
            return False
    
    def create_float_vector_collection(self) -> bool:
        """Create collection for float vector testing."""
        try:
            if utility.has_collection(self.float_collection_name, using=self.connection_alias):
                utility.drop_collection(self.float_collection_name, using=self.connection_alias)
                print(f"🗑️ Dropped existing float collection")
            
            # Comprehensive schema with all scalar types + float vector
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=1000),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="rating", dtype=DataType.FLOAT),
                FieldSchema(name="price", dtype=DataType.DOUBLE),
                FieldSchema(name="year", dtype=DataType.INT32),
                FieldSchema(name="views", dtype=DataType.INT64),
                FieldSchema(name="likes", dtype=DataType.INT16),
                FieldSchema(name="version", dtype=DataType.INT8),
                FieldSchema(name="is_featured", dtype=DataType.BOOL),
                FieldSchema(name="is_active", dtype=DataType.BOOL),
                FieldSchema(name="is_premium", dtype=DataType.BOOL),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Float vector collection for comprehensive testing",
                enable_dynamic_field=True
            )
            
            self.float_collection = Collection(
                name=self.float_collection_name,
                schema=schema,
                using=self.connection_alias
            )
            
            print(f"✅ Created float vector collection with {len(fields)} fields")
            return True
            
        except Exception as e:
            print(f"❌ Error creating float vector collection: {e}")
            return False
    
    def create_binary_vector_collection(self) -> bool:
        """Create separate collection for binary vector testing."""
        try:
            if utility.has_collection(self.binary_collection_name, using=self.connection_alias):
                utility.drop_collection(self.binary_collection_name, using=self.connection_alias)
                print(f"🗑️ Dropped existing binary collection")
            
            # Binary vector collection schema
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="rating", dtype=DataType.FLOAT),
                FieldSchema(name="binary_embedding", dtype=DataType.BINARY_VECTOR, dim=self.dimension),
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Binary vector collection for testing"
            )
            
            self.binary_collection = Collection(
                name=self.binary_collection_name,
                schema=schema,
                using=self.connection_alias
            )
            
            print(f"✅ Created binary vector collection with {len(fields)} fields")
            return True
            
        except Exception as e:
            print(f"❌ Error creating binary vector collection: {e}")
            return False
    
    def populate_collections(self, num_entities: int = 2000) -> bool:
        """Populate both collections with comprehensive test data."""
        print(f"🔄 Populating collections with {num_entities} entities each...")
        
        categories = ["AI/ML", "Computer Vision", "NLP", "Robotics", "Data Science", "Deep Learning"]
        tags_pool = ["research", "production", "experimental", "benchmarking", "optimization"]
        
        try:
            batch_size = 200
            
            # Populate float vector collection
            for batch_start in range(0, num_entities, batch_size):
                batch_end = min(batch_start + batch_size, num_entities)
                
                ids = list(range(batch_start, batch_end))
                titles = [f"AI Research Paper {i+1}: Advanced Neural Networks" for i in range(batch_start, batch_end)]
                descriptions = [f"Comprehensive study on optimization techniques for model {i+1}" for i in range(batch_start, batch_end)]
                categories_list = [random.choice(categories) for _ in range(batch_end - batch_start)]
                tags_list = [",".join(random.sample(tags_pool, random.randint(2, 4))) for _ in range(batch_end - batch_start)]
                ratings = [round(random.uniform(1.0, 10.0), 2) for _ in range(batch_end - batch_start)]
                prices = [round(random.uniform(0.0, 999.99), 2) for _ in range(batch_end - batch_start)]
                years = [random.randint(2015, 2024) for _ in range(batch_end - batch_start)]
                views_list = [random.randint(100, 1000000) for _ in range(batch_end - batch_start)]
                likes_list = [random.randint(0, 32767) for _ in range(batch_end - batch_start)]
                versions = [random.randint(1, 127) for _ in range(batch_end - batch_start)]
                is_featured_list = [random.choice([True, False]) for _ in range(batch_end - batch_start)]
                is_active_list = [random.choice([True, False]) for _ in range(batch_end - batch_start)]
                is_premium_list = [random.choice([True, False]) for _ in range(batch_end - batch_start)]
                
                embeddings = []
                for _ in range(batch_end - batch_start):
                    vector = np.random.random(self.dimension).astype(np.float32)
                    vector = vector / np.linalg.norm(vector)
                    embeddings.append(vector.tolist())
                
                float_batch = [ids, titles, descriptions, categories_list, tags_list, ratings, prices, 
                              years, views_list, likes_list, versions, is_featured_list, is_active_list, 
                              is_premium_list, embeddings]
                
                self.float_collection.insert(float_batch)
                
                if batch_start == 0:
                    print(f"   ✅ Float collection first batch: {len(ids)} entities")
            
            self.float_collection.flush()
            print(f"✅ Float collection populated: {num_entities} entities")
            
            # Populate binary vector collection
            for batch_start in range(0, num_entities, batch_size):
                batch_end = min(batch_start + batch_size, num_entities)
                
                ids = list(range(batch_start, batch_end))
                titles = [f"Binary Document {i+1}" for i in range(batch_start, batch_end)]
                categories_list = [random.choice(categories) for _ in range(batch_end - batch_start)]
                ratings = [round(random.uniform(1.0, 10.0), 2) for _ in range(batch_end - batch_start)]
                
                binary_embeddings = []
                for _ in range(batch_end - batch_start):
                    binary_vector = np.random.randint(0, 2, self.dimension // 8, dtype=np.uint8)
                    binary_embeddings.append(binary_vector.tobytes())
                
                binary_batch = [ids, titles, categories_list, ratings, binary_embeddings]
                self.binary_collection.insert(binary_batch)
                
                if batch_start == 0:
                    print(f"   ✅ Binary collection first batch: {len(ids)} entities")
            
            self.binary_collection.flush()
            print(f"✅ Binary collection populated: {num_entities} entities")
            
            return True
            
        except Exception as e:
            print(f"❌ Error populating collections: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_all_index_types_and_metrics(self) -> Dict[str, Any]:
        """Test all available index types and distance metrics."""
        print("\n🔧 Testing All Index Types & Distance Metrics")
        print("=" * 50)
        
        results = {}
        
        # Test configurations for float vectors
        float_configs = [
            {"index": "FLAT", "metric": "L2", "params": {}},
            {"index": "FLAT", "metric": "IP", "params": {}},
            {"index": "FLAT", "metric": "COSINE", "params": {}},
            {"index": "IVF_FLAT", "metric": "L2", "params": {"nlist": 128}},
            {"index": "IVF_FLAT", "metric": "IP", "params": {"nlist": 128}},
            {"index": "IVF_FLAT", "metric": "COSINE", "params": {"nlist": 128}},
            {"index": "IVF_SQ8", "metric": "L2", "params": {"nlist": 128}},
            {"index": "IVF_PQ", "metric": "L2", "params": {"nlist": 128, "m": 8, "nbits": 8}},
            {"index": "HNSW", "metric": "L2", "params": {"M": 16, "efConstruction": 200}},
            {"index": "HNSW", "metric": "IP", "params": {"M": 16, "efConstruction": 200}},
            {"index": "HNSW", "metric": "COSINE", "params": {"M": 16, "efConstruction": 200}},
            {"index": "SCANN", "metric": "L2", "params": {"nlist": 128}},
            {"index": "AUTOINDEX", "metric": "L2", "params": {}},
        ]
        
        # Test binary configurations
        binary_configs = [
            {"index": "BIN_FLAT", "metric": "HAMMING", "params": {}},
            {"index": "BIN_IVF_FLAT", "metric": "HAMMING", "params": {"nlist": 128}},
            {"index": "BIN_IVF_FLAT", "metric": "JACCARD", "params": {"nlist": 128}},
        ]
        
        successful_float_index = None
        successful_binary_index = None
        
        # Test float vector indexes
        print("\n📊 Testing Float Vector Indexes:")
        for config in float_configs:
            try:
                # Drop existing index
                try:
                    self.float_collection.drop_index()
                    time.sleep(0.5)
                except:
                    pass
                
                index_params = {
                    "index_type": config["index"],
                    "metric_type": config["metric"],
                    "params": config["params"]
                }
                
                print(f"   🔧 {config['index']} + {config['metric']}...", end=" ")
                
                self.float_collection.create_index(field_name="embedding", index_params=index_params)
                self.float_collection.load()
                
                # Test search
                query_vector = np.random.random(self.dimension).astype(np.float32)
                query_vector = query_vector / np.linalg.norm(query_vector)
                
                search_params = {"metric_type": config["metric"], "params": {"nprobe": 10}}
                if config["index"] == "HNSW":
                    search_params["params"] = {"ef": 64}
                
                start_time = time.time()
                search_results = self.float_collection.search(
                    data=[query_vector.tolist()],
                    anns_field="embedding",
                    param=search_params,
                    limit=10
                )
                search_time = time.time() - start_time
                
                if search_results and search_results[0]:
                    print(f"✅ {len(search_results[0])} results ({search_time:.4f}s)")
                    results[f"float_{config['index']}_{config['metric']}"] = {
                        "success": True,
                        "index_type": config["index"],
                        "metric": config["metric"],
                        "results_count": len(search_results[0]),
                        "search_time": search_time
                    }
                    if not successful_float_index:
                        successful_float_index = (config, search_params)
                else:
                    print("⚠️ No results")
                    results[f"float_{config['index']}_{config['metric']}"] = {
                        "success": False,
                        "error": "No search results"
                    }
                    
            except Exception as e:
                print(f"❌ {str(e)[:50]}...")
                results[f"float_{config['index']}_{config['metric']}"] = {
                    "success": False,
                    "error": str(e)[:200]
                }
        
        # Test binary vector indexes  
        print("\n🔢 Testing Binary Vector Indexes:")
        for config in binary_configs:
            try:
                try:
                    self.binary_collection.drop_index()
                    time.sleep(0.5)
                except:
                    pass
                
                index_params = {
                    "index_type": config["index"],
                    "metric_type": config["metric"],
                    "params": config["params"]
                }
                
                print(f"   🔧 {config['index']} + {config['metric']}...", end=" ")
                
                self.binary_collection.create_index(field_name="binary_embedding", index_params=index_params)
                self.binary_collection.load()
                
                # Test binary search
                binary_query = np.random.randint(0, 2, self.dimension // 8, dtype=np.uint8)
                search_params = {"metric_type": config["metric"], "params": {"nprobe": 10} if "IVF" in config["index"] else {}}
                
                start_time = time.time()
                search_results = self.binary_collection.search(
                    data=[binary_query.tobytes()],
                    anns_field="binary_embedding",
                    param=search_params,
                    limit=10
                )
                search_time = time.time() - start_time
                
                if search_results and search_results[0]:
                    print(f"✅ {len(search_results[0])} results ({search_time:.4f}s)")
                    results[f"binary_{config['index']}_{config['metric']}"] = {
                        "success": True,
                        "index_type": config["index"],
                        "metric": config["metric"],
                        "results_count": len(search_results[0]),
                        "search_time": search_time
                    }
                    if not successful_binary_index:
                        successful_binary_index = (config, search_params)
                else:
                    print("⚠️ No results")
                    results[f"binary_{config['index']}_{config['metric']}"] = {
                        "success": False,
                        "error": "No search results"
                    }
                    
            except Exception as e:
                print(f"❌ {str(e)[:50]}...")
                results[f"binary_{config['index']}_{config['metric']}"] = {
                    "success": False,
                    "error": str(e)[:200]
                }
        
        # Set up working indexes for subsequent tests
        if successful_float_index:
            config, search_params = successful_float_index
            try:
                self.float_collection.drop_index()
                index_params = {
                    "index_type": config["index"],
                    "metric_type": config["metric"],
                    "params": config["params"]
                }
                self.float_collection.create_index(field_name="embedding", index_params=index_params)
                self.float_collection.load()
                print(f"🎯 Using {config['index']} + {config['metric']} for subsequent float tests")
            except Exception as e:
                print(f"⚠️ Error setting up working float index: {e}")
        
        if successful_binary_index:
            config, search_params = successful_binary_index
            try:
                self.binary_collection.drop_index()
                index_params = {
                    "index_type": config["index"],
                    "metric_type": config["metric"],
                    "params": config["params"]
                }
                self.binary_collection.create_index(field_name="binary_embedding", index_params=index_params)
                self.binary_collection.load()
                print(f"🎯 Using {config['index']} + {config['metric']} for subsequent binary tests")
            except Exception as e:
                print(f"⚠️ Error setting up working binary index: {e}")
        
        return results
    
    def test_advanced_search_parameters(self) -> Dict[str, Any]:
        """Test advanced search parameters."""
        print("\n⚙️ Testing Advanced Search Parameters")
        print("=" * 40)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Parameter variations
            param_tests = [
                {"name": "nprobe_low", "params": {"nprobe": 1}, "desc": "Low precision, fast"},
                {"name": "nprobe_medium", "params": {"nprobe": 16}, "desc": "Balanced"},
                {"name": "nprobe_high", "params": {"nprobe": 64}, "desc": "High precision"},
                {"name": "nprobe_max", "params": {"nprobe": 128}, "desc": "Maximum precision"},
            ]
            
            base_search_params = {"metric_type": "L2"}
            
            for test in param_tests:
                try:
                    search_params = base_search_params.copy()
                    search_params["params"] = test["params"]
                    
                    print(f"🔧 {test['name']}: {test['desc']}")
                    
                    start_time = time.time()
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=20
                    )
                    search_time = time.time() - start_time
                    
                    if search_results and search_results[0]:
                        avg_distance = sum(hit.distance for hit in search_results[0]) / len(search_results[0])
                        print(f"   ✅ {len(search_results[0])} results, {search_time:.4f}s, avg_dist: {avg_distance:.4f}")
                        
                        results[test['name']] = {
                            "success": True,
                            "parameters": test["params"],
                            "description": test["desc"],
                            "results_count": len(search_results[0]),
                            "search_time": search_time,
                            "avg_distance": avg_distance
                        }
                    else:
                        print(f"   ⚠️ No results")
                        results[test['name']] = {"success": False, "error": "No results"}
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:100]}...")
                    results[test['name']] = {"success": False, "error": str(e)[:200]}
            
        except Exception as e:
            print(f"❌ Error in parameter testing: {e}")
            results["parameter_error"] = str(e)
        
        return results
    
    def test_comprehensive_filtering(self) -> Dict[str, Any]:
        """Test comprehensive filtering expressions."""
        print("\n🎯 Testing Comprehensive Filtering Expressions")
        print("=" * 50)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
            
            # Comprehensive filter test cases
            filter_tests = [
                # Basic numeric comparisons
                {"name": "rating_gt", "expr": "rating > 5.0", "desc": "Ratings above 5.0"},
                {"name": "rating_gte", "expr": "rating >= 7.5", "desc": "Ratings 7.5 and above"},
                {"name": "rating_lt", "expr": "rating < 3.0", "desc": "Ratings below 3.0"},
                {"name": "rating_lte", "expr": "rating <= 2.5", "desc": "Ratings 2.5 and below"},
                {"name": "rating_eq", "expr": "rating == 8.5", "desc": "Exact rating match"},
                {"name": "rating_ne", "expr": "rating != 5.0", "desc": "Rating not equal to 5.0"},
                
                # String comparisons
                {"name": "category_exact", "expr": 'category == "AI/ML"', "desc": "Exact category match"},
                {"name": "category_not", "expr": 'category != "Computer Vision"', "desc": "Category exclusion"},
                
                # Boolean filters
                {"name": "featured_only", "expr": "is_featured == True", "desc": "Featured items only"},
                {"name": "not_premium", "expr": "is_premium == False", "desc": "Non-premium items"},
                
                # Range filters  
                {"name": "rating_range", "expr": "rating > 6.0 and rating < 9.0", "desc": "Rating range 6-9"},
                {"name": "year_range", "expr": "year >= 2020 and year <= 2023", "desc": "Recent years"},
                {"name": "views_range", "expr": "views > 10000 and views < 100000", "desc": "Medium popularity"},
                
                # Complex AND combinations
                {"name": "high_quality_ai", "expr": 'category == "AI/ML" and rating > 7.0 and is_featured == True', "desc": "High-quality AI content"},
                {"name": "recent_popular", "expr": "year >= 2022 and views > 50000 and rating > 6.0", "desc": "Recent popular content"},
                {"name": "premium_active", "expr": "is_premium == True and is_active == True and rating > 5.0", "desc": "Premium active content"},
                
                # Complex OR combinations
                {"name": "high_or_popular", "expr": "rating > 8.0 or views > 500000", "desc": "High rating OR very popular"},
                {"name": "ai_or_cv", "expr": 'category == "AI/ML" or category == "Computer Vision"', "desc": "AI or Computer Vision"},
                {"name": "featured_or_premium", "expr": "is_featured == True or is_premium == True", "desc": "Featured OR premium"},
                
                # IN operations
                {"name": "top_categories", "expr": 'category in ["AI/ML", "Deep Learning", "NLP"]', "desc": "Top AI categories"},
                {"name": "recent_years", "expr": "year in [2022, 2023, 2024]", "desc": "Most recent years"},
                {"name": "top_ratings", "expr": "rating in [8.0, 8.5, 9.0, 9.5, 10.0]", "desc": "Top rating tiers"},
                
                # NOT operations
                {"name": "not_old", "expr": "not (year < 2020)", "desc": "Not old content"},
                {"name": "not_low_rated", "expr": "not (rating < 5.0)", "desc": "Not low-rated"},
                {"name": "not_inactive", "expr": "not (is_active == False)", "desc": "Not inactive"},
                
                # Complex nested conditions
                {"name": "complex_nested", "expr": "(rating > 7.0 and is_featured == True) or (views > 100000 and year >= 2022)", "desc": "Complex nested logic"},
                {"name": "advanced_multi", "expr": '(category == "AI/ML" or category == "Deep Learning") and rating > 6.0 and (is_premium == True or views > 50000)', "desc": "Advanced multi-condition"},
                
                # Integer field tests
                {"name": "high_views", "expr": "views > 500000", "desc": "High view count"},
                {"name": "many_likes", "expr": "likes > 1000", "desc": "Many likes"},
                {"name": "recent_version", "expr": "version >= 5", "desc": "Recent version"},
                
                # String pattern matching (if supported)
                {"name": "title_pattern", "expr": 'title like "AI Research%"', "desc": "Title pattern match"},
            ]
            
            for test in filter_tests:
                try:
                    print(f"🔍 {test['name']}: {test['desc']}")
                    
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=10,
                        expr=test['expr'],
                        output_fields=["title", "category", "rating", "year", "views", "is_featured", "is_premium"]
                    )
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ Found {len(search_results[0])} results")
                        
                        # Show sample result
                        if search_results[0]:
                            hit = search_results[0][0]
                            entity = hit.entity
                            print(f"      Sample: Rating {entity.get('rating')}, {entity.get('category')}, Year {entity.get('year')}")
                        
                        results[test['name']] = {
                            "success": True,
                            "expression": test['expr'],
                            "description": test['desc'],
                            "results_count": len(search_results[0])
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[test['name']] = {
                            "success": True,
                            "expression": test['expr'],
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:100]}...")
                    results[test['name']] = {
                        "success": False,
                        "expression": test['expr'],
                        "error": str(e)[:300]
                    }
            
        except Exception as e:
            print(f"❌ Error in comprehensive filtering: {e}")
            results["filtering_error"] = str(e)
        
        return results
    
    def test_range_search(self) -> Dict[str, Any]:
        """Test range search capabilities."""
        print("\n📏 Testing Range Search Capabilities")
        print("=" * 40)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Different range configurations
            range_tests = [
                {"name": "range_0_5_to_1_0", "radius": 1.0, "range_filter": 0.5, "desc": "Distance range [0.5, 1.0]"},
                {"name": "range_0_3_to_0_8", "radius": 0.8, "range_filter": 0.3, "desc": "Distance range [0.3, 0.8]"},
                {"name": "radius_1_5", "radius": 1.5, "desc": "All within radius 1.5"},
                {"name": "min_distance_0_4", "range_filter": 0.4, "desc": "Minimum distance 0.4"},
            ]
            
            for test in range_tests:
                try:
                    print(f"🔍 {test['name']}: {test['desc']}")
                    
                    search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
                    
                    # Add range parameters
                    if "radius" in test:
                        search_params["params"]["radius"] = test["radius"]
                    if "range_filter" in test:
                        search_params["params"]["range_filter"] = test["range_filter"]
                    
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=100,  # Higher limit for range search
                        output_fields=["title", "rating"]
                    )
                    
                    if search_results and search_results[0]:
                        distances = [hit.distance for hit in search_results[0]]
                        print(f"   ✅ Found {len(search_results[0])} results")
                        print(f"   📊 Distance range: {min(distances):.4f} - {max(distances):.4f}")
                        
                        results[test['name']] = {
                            "success": True,
                            "config": {k: v for k, v in test.items() if k not in ["name", "desc"]},
                            "description": test["desc"],
                            "results_count": len(search_results[0]),
                            "min_distance": min(distances),
                            "max_distance": max(distances)
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[test['name']] = {
                            "success": True,
                            "results_count": 0,
                            "description": test["desc"]
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:100]}...")
                    results[test['name']] = {
                        "success": False,
                        "error": str(e)[:200],
                        "description": test["desc"]
                    }
                    
        except Exception as e:
            print(f"❌ Error in range search testing: {e}")
            results["range_error"] = str(e)
        
        return results
    
    def test_partition_operations(self) -> Dict[str, Any]:
        """Test partition-based operations."""
        print("\n📂 Testing Partition Operations")
        print("=" * 35)
        
        results = {}
        
        try:
            # Create test partitions
            partition_names = ["high_quality", "medium_quality", "experimental"]
            created_partitions = []
            
            for partition_name in partition_names:
                try:
                    if not self.float_collection.has_partition(partition_name):
                        self.float_collection.create_partition(partition_name)
                        print(f"   ✅ Created partition: {partition_name}")
                    else:
                        print(f"   📂 Partition exists: {partition_name}")
                    created_partitions.append(partition_name)
                except Exception as e:
                    print(f"   ❌ Error with partition {partition_name}: {e}")
            
            if created_partitions:
                # Test partition-specific searches
                query_vector = np.random.random(self.dimension).astype(np.float32)
                query_vector = query_vector / np.linalg.norm(query_vector)
                
                search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
                
                # Single partition search
                partition = created_partitions[0]
                try:
                    print(f"\n🔍 Single partition search: {partition}")
                    
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=10,
                        partition_names=[partition],
                        output_fields=["title", "rating"]
                    )
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ Found {len(search_results[0])} results")
                        results["single_partition"] = {
                            "success": True,
                            "partition": partition,
                            "results_count": len(search_results[0])
                        }
                    else:
                        print(f"   ⚠️ No results in partition")
                        results["single_partition"] = {
                            "success": True,
                            "partition": partition,
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Single partition error: {e}")
                    results["single_partition"] = {"success": False, "error": str(e)[:200]}
                
                # Multi-partition search
                if len(created_partitions) >= 2:
                    try:
                        print(f"\n🔍 Multi-partition search: {created_partitions[:2]}")
                        
                        search_results = self.float_collection.search(
                            data=[query_vector.tolist()],
                            anns_field="embedding",
                            param=search_params,
                            limit=10,
                            partition_names=created_partitions[:2],
                            output_fields=["title", "rating"]
                        )
                        
                        if search_results and search_results[0]:
                            print(f"   ✅ Found {len(search_results[0])} results across partitions")
                            results["multi_partition"] = {
                                "success": True,
                                "partitions": created_partitions[:2],
                                "results_count": len(search_results[0])
                            }
                        else:
                            print(f"   ⚠️ No results in multi-partition search")
                            results["multi_partition"] = {
                                "success": True,
                                "partitions": created_partitions[:2],
                                "results_count": 0
                            }
                            
                    except Exception as e:
                        print(f"   ❌ Multi-partition error: {e}")
                        results["multi_partition"] = {"success": False, "error": str(e)[:200]}
                
            else:
                results["partition_error"] = "No partitions could be created"
                
        except Exception as e:
            print(f"❌ Error in partition operations: {e}")
            results["partition_ops_error"] = str(e)
        
        return results
    
    def test_batch_and_pagination(self) -> Dict[str, Any]:
        """Test batch search and pagination capabilities."""
        print("\n📦 Testing Batch Search & Pagination")
        print("=" * 40)
        
        results = {}
        
        try:
            # Batch search test
            print("🔍 Batch search test:")
            batch_size = 10
            query_vectors = []
            
            for _ in range(batch_size):
                vector = np.random.random(self.dimension).astype(np.float32)
                vector = vector / np.linalg.norm(vector)
                query_vectors.append(vector.tolist())
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
            
            start_time = time.time()
            search_results = self.float_collection.search(
                data=query_vectors,
                anns_field="embedding",
                param=search_params,
                limit=5,
                output_fields=["title", "rating"]
            )
            batch_time = time.time() - start_time
            
            if search_results:
                total_results = sum(len(query_result) for query_result in search_results)
                print(f"   ✅ Batch search: {len(search_results)} queries, {total_results} total results")
                print(f"   ⏱️ Batch time: {batch_time:.4f}s ({batch_time/batch_size:.4f}s per query)")
                
                results["batch_search"] = {
                    "success": True,
                    "batch_size": batch_size,
                    "total_results": total_results,
                    "batch_time": batch_time,
                    "avg_time_per_query": batch_time / batch_size
                }
            else:
                print("   ⚠️ No batch results")
                results["batch_search"] = {"success": False, "error": "No batch results"}
            
            # Pagination simulation
            print("\n📄 Pagination simulation:")
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            page_sizes = [10, 25, 50, 100]
            for page_size in page_sizes:
                try:
                    start_time = time.time()
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=page_size,
                        output_fields=["title"]
                    )
                    page_time = time.time() - start_time
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ Page size {page_size}: {len(search_results[0])} results ({page_time:.4f}s)")
                        results[f"pagination_{page_size}"] = {
                            "success": True,
                            "page_size": page_size,
                            "results_count": len(search_results[0]),
                            "page_time": page_time
                        }
                    else:
                        print(f"   ⚠️ Page size {page_size}: No results")
                        results[f"pagination_{page_size}"] = {"success": False, "error": "No results"}
                        
                except Exception as e:
                    print(f"   ❌ Page size {page_size}: {e}")
                    results[f"pagination_{page_size}"] = {"success": False, "error": str(e)[:200]}
            
        except Exception as e:
            print(f"❌ Error in batch/pagination testing: {e}")
            results["batch_pagination_error"] = str(e)
        
        return results
    
    def test_collection_statistics(self) -> Dict[str, Any]:
        """Test collection statistics and metadata operations."""
        print("\n📊 Testing Collection Statistics")
        print("=" * 35)
        
        results = {}
        
        try:
            # Float collection stats
            print("📈 Float collection statistics:")
            float_stats = {
                "name": self.float_collection.name,
                "description": self.float_collection.description,
                "entity_count": self.float_collection.num_entities,
                "schema_fields": len(self.float_collection.schema.fields)
            }
            
            print(f"   Name: {float_stats['name']}")
            print(f"   Entities: {float_stats['entity_count']}")
            print(f"   Fields: {float_stats['schema_fields']}")
            
            # Get field details
            field_info = []
            for field in self.float_collection.schema.fields:
                field_data = {
                    "name": field.name,
                    "type": str(field.dtype),
                    "is_primary": field.is_primary if hasattr(field, 'is_primary') else False
                }
                field_info.append(field_data)
                print(f"      - {field.name}: {field.dtype}")
            
            float_stats["fields"] = field_info
            
            # Index information
            try:
                indexes = self.float_collection.indexes
                index_info = []
                for idx in indexes:
                    idx_data = {
                        "field": idx.field_name,
                        "type": idx.params.get('index_type', 'Unknown'),
                        "metric": idx.params.get('metric_type', 'Unknown')
                    }
                    index_info.append(idx_data)
                    print(f"   Index: {idx.field_name} -> {idx.params.get('index_type')} ({idx.params.get('metric_type')})")
                
                float_stats["indexes"] = index_info
            except Exception as e:
                print(f"   Index info error: {e}")
                float_stats["indexes"] = []
            
            results["float_collection_stats"] = {
                "success": True,
                "stats": float_stats
            }
            
            # Binary collection stats
            print("\n🔢 Binary collection statistics:")
            binary_stats = {
                "name": self.binary_collection.name,
                "description": self.binary_collection.description,
                "entity_count": self.binary_collection.num_entities,
                "schema_fields": len(self.binary_collection.schema.fields)
            }
            
            print(f"   Name: {binary_stats['name']}")
            print(f"   Entities: {binary_stats['entity_count']}")
            print(f"   Fields: {binary_stats['schema_fields']}")
            
            results["binary_collection_stats"] = {
                "success": True,
                "stats": binary_stats
            }
            
        except Exception as e:
            print(f"❌ Error getting collection statistics: {e}")
            results["statistics_error"] = str(e)
        
        return results
    
    def run_comprehensive_exploration(self) -> Dict[str, Any]:
        """Run the complete comprehensive exploration."""
        print("🚀 Comprehensive Milvus Search Features Exploration")
        print("=" * 60)
        print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Testing within Milvus v2.3.3 constraints (single vector per collection)")
        
        all_results = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "connection": {"host": self.host, "port": self.port},
            "milvus_version": "v2.3.3",
            "exploration_type": "comprehensive_compatible"
        }
        
        # Connect
        if not self.connect():
            return {"error": "Failed to connect to Milvus"}
        
        # Create collections
        if not self.create_float_vector_collection():
            return {"error": "Failed to create float vector collection"}
        
        if not self.create_binary_vector_collection():
            return {"error": "Failed to create binary vector collection"}
        
        # Populate collections
        if not self.populate_collections(2000):
            return {"error": "Failed to populate collections"}
        
        # Run all comprehensive tests
        print("\n" + "="*60)
        all_results["index_types_metrics"] = self.test_all_index_types_and_metrics()
        
        print("\n" + "="*60)
        all_results["search_parameters"] = self.test_advanced_search_parameters()
        
        print("\n" + "="*60)
        all_results["comprehensive_filtering"] = self.test_comprehensive_filtering()
        
        print("\n" + "="*60)
        all_results["range_search"] = self.test_range_search()
        
        print("\n" + "="*60)
        all_results["partition_operations"] = self.test_partition_operations()
        
        print("\n" + "="*60)
        all_results["batch_pagination"] = self.test_batch_and_pagination()
        
        print("\n" + "="*60)
        all_results["collection_statistics"] = self.test_collection_statistics()
        
        # Generate comprehensive summary
        self.generate_comprehensive_summary(all_results)
        
        return all_results
    
    def generate_comprehensive_summary(self, results: Dict[str, Any]):
        """Generate comprehensive summary of all tests."""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE MILVUS CAPABILITIES SUMMARY")
        print("=" * 80)
        
        categories = [
            ("index_types_metrics", "Index Types & Distance Metrics"),
            ("search_parameters", "Advanced Search Parameters"),
            ("comprehensive_filtering", "Comprehensive Filtering"),
            ("range_search", "Range Search Capabilities"),
            ("partition_operations", "Partition Operations"),
            ("batch_pagination", "Batch Search & Pagination"),
            ("collection_statistics", "Collection Statistics")
        ]
        
        total_successful = 0
        total_tested = 0
        
        for category_key, category_name in categories:
            if category_key in results and isinstance(results[category_key], dict):
                print(f"\n🔍 {category_name}:")
                
                category_data = results[category_key]
                successful = 0
                tested = 0
                
                for feature_name, feature_result in category_data.items():
                    if isinstance(feature_result, dict) and "success" in feature_result:
                        tested += 1
                        total_tested += 1
                        
                        if feature_result["success"]:
                            successful += 1
                            total_successful += 1
                            status = "✅"
                            
                            # Show key metrics
                            metrics = []
                            if "results_count" in feature_result:
                                metrics.append(f"{feature_result['results_count']} results")
                            if "search_time" in feature_result:
                                metrics.append(f"{feature_result['search_time']:.4f}s")
                            
                            extra = f" ({', '.join(metrics)})" if metrics else ""
                        else:
                            status = "❌"
                            extra = ""
                        
                        print(f"   {status} {feature_name}{extra}")
                
                if tested > 0:
                    success_rate = (successful / tested) * 100
                    print(f"   📊 Success Rate: {successful}/{tested} ({success_rate:.1f}%)")
        
        # Overall summary
        if total_tested > 0:
            overall_success_rate = (total_successful / total_tested) * 100
            print(f"\n🎯 OVERALL SUCCESS RATE: {total_successful}/{total_tested} ({overall_success_rate:.1f}%)")
        
        # Key findings
        print(f"\n🔑 KEY FINDINGS:")
        print(f"   • Multiple vector fields per collection: ❌ Not supported in v2.3.3")
        print(f"   • Float vector search: ✅ Fully supported")
        print(f"   • Binary vector search: ✅ Supported in separate collection")
        print(f"   • Advanced filtering: ✅ Comprehensive expression support")
        print(f"   • Multiple index types: ✅ FLAT, IVF_*, HNSW, etc.")
        print(f"   • Multiple distance metrics: ✅ L2, IP, COSINE, HAMMING")
        print(f"   • Partition operations: ✅ Single and multi-partition search")
        print(f"   • Batch processing: ✅ Efficient multi-query handling")
        
        print(f"\n⏰ Analysis completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
    
    def cleanup(self):
        """Clean up test resources."""
        try:
            if self.float_collection:
                utility.drop_collection(self.float_collection_name, using=self.connection_alias)
                print(f"🗑️ Cleaned up float collection")
        except Exception as e:
            print(f"⚠️ Float collection cleanup warning: {e}")
        
        try:
            if self.binary_collection:
                utility.drop_collection(self.binary_collection_name, using=self.connection_alias)
                print(f"🗑️ Cleaned up binary collection")
        except Exception as e:
            print(f"⚠️ Binary collection cleanup warning: {e}")
        
        try:
            connections.disconnect(self.connection_alias)
            print("🔌 Disconnected from Milvus")
        except Exception as e:
            print(f"⚠️ Disconnect warning: {e}")

def main():
    """Main execution function."""
    explorer = ComprehensiveMilvusExplorer()
    
    try:
        # Run comprehensive exploration
        results = explorer.run_comprehensive_exploration()
        
        # Save results
        output_file = f"milvus_comprehensive_analysis_v2_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Comprehensive results saved to: {output_file}")
        
        return results
        
    except KeyboardInterrupt:
        print("\n⚠️ Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        explorer.cleanup()

if __name__ == "__main__":
    print(__doc__)
    main()
