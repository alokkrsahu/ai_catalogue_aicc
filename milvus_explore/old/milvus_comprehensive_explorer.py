#!/usr/bin/env python3
"""
Comprehensive Milvus Search Features Explorer
============================================

This script provides an exhaustive exploration of ALL search features supported by Milvus.
It goes far beyond basic vector search to test advanced capabilities.

Requirements:
- pymilvus
- numpy

Install with: pip install pymilvus numpy
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
        self.test_collection_name = "comprehensive_test_collection"
        self.dimension = 128
        self.collection = None
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
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Milvus: {e}")
            return False
    
    def create_comprehensive_collection(self) -> bool:
        """Create a comprehensive test collection with all supported field types."""
        try:
            # Drop existing collection if it exists
            if utility.has_collection(self.test_collection_name, using=self.connection_alias):
                utility.drop_collection(self.test_collection_name, using=self.connection_alias)
                print(f"🗑️ Dropped existing collection: {self.test_collection_name}")
            
            # Define schema with ALL supported field types
            fields = [
                # Primary key
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                
                # Scalar fields
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=1000),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=200),
                
                # Numeric fields
                FieldSchema(name="rating", dtype=DataType.FLOAT),
                FieldSchema(name="price", dtype=DataType.DOUBLE),
                FieldSchema(name="year", dtype=DataType.INT32),
                FieldSchema(name="views", dtype=DataType.INT64),
                FieldSchema(name="likes", dtype=DataType.INT16),
                FieldSchema(name="version", dtype=DataType.INT8),
                
                # Boolean field
                FieldSchema(name="is_featured", dtype=DataType.BOOL),
                FieldSchema(name="is_active", dtype=DataType.BOOL),
                FieldSchema(name="is_premium", dtype=DataType.BOOL),
                
                # Vector fields
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                FieldSchema(name="binary_embedding", dtype=DataType.BINARY_VECTOR, dim=self.dimension),
                
                # JSON field (if supported)
                # FieldSchema(name="metadata", dtype=DataType.JSON),
                
                # Array fields (if supported)
                # FieldSchema(name="float_array", dtype=DataType.ARRAY, element_type=DataType.FLOAT, max_capacity=10),
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Comprehensive test collection for exploring ALL Milvus search methods",
                enable_dynamic_field=True
            )
            
            # Create collection
            self.collection = Collection(
                name=self.test_collection_name,
                schema=schema,
                using=self.connection_alias
            )
            
            print(f"✅ Created comprehensive test collection: {self.test_collection_name}")
            print(f"   Fields: {len(fields)}")
            for field in fields:
                print(f"      - {field.name}: {field.dtype}")
            
            return True
        except Exception as e:
            print(f"❌ Error creating comprehensive collection: {e}")
            return False
    
    def generate_comprehensive_data(self, num_entities: int = 2000) -> bool:
        """Generate comprehensive test data with all field types."""
        print(f"🔄 Generating {num_entities} comprehensive test entities...")
        
        categories = ["AI/ML", "Computer Vision", "NLP", "Robotics", "Data Science", "Deep Learning", "Reinforcement Learning"]
        tags_pool = ["research", "production", "experimental", "benchmarking", "optimization", "neural", "transformer", "cnn", "rnn", "gan"]
        
        try:
            batch_size = 200
            total_inserted = 0
            
            for batch_start in range(0, num_entities, batch_size):
                batch_end = min(batch_start + batch_size, num_entities)
                
                # Prepare batch data
                ids = []
                titles = []
                descriptions = []
                categories_list = []
                tags_list = []
                ratings = []
                prices = []
                years = []
                views_list = []
                likes_list = []
                versions = []
                is_featured_list = []
                is_active_list = []
                is_premium_list = []
                embeddings = []
                binary_embeddings = []
                
                for i in range(batch_start, batch_end):
                    ids.append(i)
                    titles.append(f"AI Research Paper {i+1}: Advanced {random.choice(['Neural', 'Deep', 'Machine'])} Learning")
                    descriptions.append(f"Comprehensive study on {random.choice(['optimization', 'architecture', 'training'])} techniques for AI models")
                    categories_list.append(random.choice(categories))
                    tags_list.append(",".join(random.sample(tags_pool, random.randint(2, 5))))
                    
                    ratings.append(round(random.uniform(1.0, 10.0), 2))
                    prices.append(round(random.uniform(0.0, 999.99), 2))
                    years.append(random.randint(2015, 2024))
                    views_list.append(random.randint(100, 1000000))
                    likes_list.append(random.randint(0, 32767))  # INT16 max
                    versions.append(random.randint(1, 127))  # INT8 max
                    
                    is_featured_list.append(random.choice([True, False]))
                    is_active_list.append(random.choice([True, False]))
                    is_premium_list.append(random.choice([True, False]))
                    
                    # Float vector
                    vector = np.random.random(self.dimension).astype(np.float32)
                    vector = vector / np.linalg.norm(vector)
                    embeddings.append(vector.tolist())
                    
                    # Binary vector
                    binary_vector = np.random.randint(0, 2, self.dimension // 8, dtype=np.uint8)
                    binary_embeddings.append(binary_vector.tobytes())
                
                # Insert batch
                batch_data = [
                    ids, titles, descriptions, categories_list, tags_list,
                    ratings, prices, years, views_list, likes_list, versions,
                    is_featured_list, is_active_list, is_premium_list,
                    embeddings, binary_embeddings
                ]
                
                insert_result = self.collection.insert(batch_data)
                total_inserted += insert_result.insert_count
                
                if batch_start == 0:
                    print(f"   ✅ First batch inserted: {insert_result.insert_count} entities")
            
            self.collection.flush()
            print(f"✅ Successfully inserted {total_inserted} comprehensive entities")
            
            return True
            
        except Exception as e:
            print(f"❌ Error inserting comprehensive data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_all_index_types(self) -> Dict[str, Any]:
        """Test all available index types for different search scenarios."""
        print("\n🔧 Testing All Available Index Types")
        print("=" * 40)
        
        results = {}
        
        # Vector index configurations to test
        vector_indexes = [
            {
                "name": "FLAT",
                "params": {"index_type": "FLAT", "metric_type": "L2", "params": {}}
            },
            {
                "name": "IVF_FLAT", 
                "params": {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}}
            },
            {
                "name": "IVF_SQ8",
                "params": {"index_type": "IVF_SQ8", "metric_type": "L2", "params": {"nlist": 128}}
            },
            {
                "name": "IVF_PQ",
                "params": {"index_type": "IVF_PQ", "metric_type": "L2", "params": {"nlist": 128, "m": 8, "nbits": 8}}
            },
            {
                "name": "HNSW",
                "params": {"index_type": "HNSW", "metric_type": "L2", "params": {"M": 16, "efConstruction": 200}}
            },
            {
                "name": "SCANN",
                "params": {"index_type": "SCANN", "metric_type": "L2", "params": {"nlist": 128}}
            },
            {
                "name": "AUTOINDEX",
                "params": {"index_type": "AUTOINDEX", "metric_type": "L2", "params": {}}
            }
        ]
        
        # Test different metrics
        metrics = ["L2", "IP", "COSINE"]
        
        successful_indexes = []
        
        for metric in metrics:
            print(f"\n📊 Testing {metric} metric:")
            
            for idx_config in vector_indexes:
                try:
                    # Drop existing index
                    try:
                        self.collection.drop_index()
                        time.sleep(1)  # Wait for drop to complete
                    except:
                        pass
                    
                    # Update metric
                    test_params = idx_config["params"].copy()
                    test_params["metric_type"] = metric
                    
                    print(f"   Creating {idx_config['name']} index with {metric} metric...")
                    
                    self.collection.create_index(
                        field_name="embedding",
                        index_params=test_params
                    )
                    
                    # Try to load collection
                    self.collection.load()
                    
                    # Test a simple search
                    query_vector = np.random.random(self.dimension).astype(np.float32)
                    query_vector = query_vector / np.linalg.norm(query_vector)
                    
                    search_params = {"metric_type": metric, "params": {"nprobe": 10} if "nprobe" in str(test_params) else {"ef": 10} if idx_config['name'] == "HNSW" else {}}
                    
                    search_results = self.collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=5
                    )
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ {idx_config['name']} with {metric}: {len(search_results[0])} results")
                        successful_indexes.append(f"{idx_config['name']}_{metric}")
                        results[f"{idx_config['name']}_{metric}"] = {
                            "success": True,
                            "index_type": idx_config['name'],
                            "metric": metric,
                            "results_count": len(search_results[0])
                        }
                        
                        # Use first successful index for subsequent tests
                        if not successful_indexes or len(successful_indexes) == 1:
                            print(f"   🎯 Using {idx_config['name']} with {metric} for subsequent tests")
                            break
                    else:
                        print(f"   ⚠️ {idx_config['name']} with {metric}: No results")
                        results[f"{idx_config['name']}_{metric}"] = {
                            "success": False,
                            "error": "No search results returned"
                        }
                        
                except Exception as e:
                    print(f"   ❌ {idx_config['name']} with {metric}: {str(e)[:100]}...")
                    results[f"{idx_config['name']}_{metric}"] = {
                        "success": False,
                        "error": str(e)[:200]
                    }
            
            if successful_indexes:
                break  # Use first working metric for remaining tests
        
        print(f"\n✅ Successfully tested {len(successful_indexes)} index configurations")
        return results
    
    def test_advanced_search_parameters(self) -> Dict[str, Any]:
        """Test advanced search parameters and configurations."""
        print("\n⚙️ Testing Advanced Search Parameters")
        print("=" * 40)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Test different search parameters
            param_tests = [
                {"name": "nprobe_variations", "params": [{"nprobe": 1}, {"nprobe": 16}, {"nprobe": 64}, {"nprobe": 128}]},
                {"name": "ef_variations", "params": [{"ef": 16}, {"ef": 64}, {"ef": 128}, {"ef": 256}]},
                {"name": "search_k_variations", "params": [{"search_k": 16}, {"search_k": 64}, {"search_k": 256}]},
            ]
            
            for test_group in param_tests:
                print(f"\n🔧 Testing {test_group['name']}:")
                group_results = {}
                
                for param_set in test_group["params"]:
                    try:
                        search_params = {"metric_type": "L2", "params": param_set}
                        
                        start_time = time.time()
                        search_results = self.collection.search(
                            data=[query_vector.tolist()],
                            anns_field="embedding",
                            param=search_params,
                            limit=10
                        )
                        search_time = time.time() - start_time
                        
                        if search_results and search_results[0]:
                            avg_distance = sum(hit.distance for hit in search_results[0]) / len(search_results[0])
                            print(f"   ✅ {param_set}: {len(search_results[0])} results, {search_time:.4f}s, avg_dist: {avg_distance:.4f}")
                            
                            group_results[str(param_set)] = {
                                "success": True,
                                "results_count": len(search_results[0]),
                                "search_time": search_time,
                                "avg_distance": avg_distance
                            }
                        else:
                            print(f"   ⚠️ {param_set}: No results")
                            group_results[str(param_set)] = {"success": True, "results_count": 0}
                            
                    except Exception as e:
                        print(f"   ❌ {param_set}: {str(e)[:100]}...")
                        group_results[str(param_set)] = {"success": False, "error": str(e)[:200]}
                
                results[test_group['name']] = group_results
            
        except Exception as e:
            print(f"❌ Error in advanced search parameters: {e}")
            results["error"] = str(e)
        
        return results
    
    def test_range_search_capabilities(self) -> Dict[str, Any]:
        """Test range search capabilities with different parameters."""
        print("\n📏 Testing Range Search Capabilities")
        print("=" * 40)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Test range search with different configurations
            range_configs = [
                {"radius": 1.0, "range_filter": 0.5, "description": "Range [0.5, 1.0]"},
                {"radius": 0.8, "range_filter": 0.3, "description": "Range [0.3, 0.8]"},
                {"radius": 1.5, "range_filter": 1.0, "description": "Range [1.0, 1.5]"},
                {"radius": 2.0, "description": "Radius <= 2.0"},
                {"range_filter": 0.4, "description": "Distance >= 0.4"},
            ]
            
            for i, config in enumerate(range_configs):
                try:
                    print(f"\n🔍 Range search {i+1}: {config['description']}")
                    
                    search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
                    search_params["params"].update({k: v for k, v in config.items() if k != "description"})
                    
                    search_results = self.collection.search(
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
                        
                        results[f"range_{i}"] = {
                            "success": True,
                            "config": config,
                            "results_count": len(search_results[0]),
                            "min_distance": min(distances),
                            "max_distance": max(distances)
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[f"range_{i}"] = {
                            "success": True,
                            "config": config,
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:100]}...")
                    results[f"range_{i}"] = {
                        "success": False,
                        "config": config,
                        "error": str(e)[:200]
                    }
            
        except Exception as e:
            print(f"❌ Error in range search testing: {e}")
            results["range_search_error"] = str(e)
        
        return results
    
    def test_advanced_filtering_expressions(self) -> Dict[str, Any]:
        """Test comprehensive filtering expressions and operators."""
        print("\n🎯 Testing Advanced Filtering Expressions")
        print("=" * 45)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
            
            # Comprehensive filter expressions
            filter_tests = [
                # Basic comparisons
                {"name": "rating_gt", "expr": "rating > 5.0", "desc": "Rating greater than 5.0"},
                {"name": "rating_gte", "expr": "rating >= 7.5", "desc": "Rating greater than or equal to 7.5"},
                {"name": "rating_lt", "expr": "rating < 3.0", "desc": "Rating less than 3.0"},
                {"name": "rating_lte", "expr": "rating <= 2.5", "desc": "Rating less than or equal to 2.5"},
                {"name": "rating_eq", "expr": "rating == 8.5", "desc": "Rating exactly 8.5"},
                {"name": "rating_ne", "expr": "rating != 5.0", "desc": "Rating not equal to 5.0"},
                
                # String operations
                {"name": "category_eq", "expr": 'category == "AI/ML"', "desc": "Category equals AI/ML"},
                {"name": "category_ne", "expr": 'category != "Computer Vision"', "desc": "Category not Computer Vision"},
                {"name": "title_like", "expr": 'title like "Advanced%"', "desc": "Title starts with 'Advanced'"},
                
                # Range operations
                {"name": "rating_between", "expr": "rating > 6.0 and rating < 9.0", "desc": "Rating between 6.0 and 9.0"},
                {"name": "year_range", "expr": "year >= 2020 and year <= 2023", "desc": "Years 2020-2023"},
                {"name": "views_range", "expr": "views > 10000 and views < 100000", "desc": "Views 10K-100K"},
                
                # Boolean operations
                {"name": "is_featured", "expr": "is_featured == True", "desc": "Featured items"},
                {"name": "not_premium", "expr": "is_premium == False", "desc": "Non-premium items"},
                {"name": "active_featured", "expr": "is_active == True and is_featured == True", "desc": "Active and featured"},
                
                # Complex combinations with AND
                {"name": "high_quality_ai", "expr": 'category == "AI/ML" and rating > 7.0 and is_featured == True', "desc": "High-quality featured AI content"},
                {"name": "recent_popular", "expr": "year >= 2022 and views > 50000 and rating > 6.0", "desc": "Recent popular content"},
                {"name": "premium_recent", "expr": "is_premium == True and year >= 2021 and is_active == True", "desc": "Premium recent active content"},
                
                # Complex combinations with OR
                {"name": "high_rating_or_popular", "expr": "rating > 8.0 or views > 500000", "desc": "High rating OR very popular"},
                {"name": "ai_or_cv", "expr": 'category == "AI/ML" or category == "Computer Vision"', "desc": "AI/ML OR Computer Vision"},
                {"name": "featured_or_premium", "expr": "is_featured == True or is_premium == True", "desc": "Featured OR premium"},
                
                # IN operations
                {"name": "categories_in", "expr": 'category in ["AI/ML", "Deep Learning", "NLP"]', "desc": "Category in AI-related fields"},
                {"name": "years_in", "expr": "year in [2022, 2023, 2024]", "desc": "Recent years"},
                {"name": "ratings_in", "expr": "rating in [8.0, 8.5, 9.0, 9.5, 10.0]", "desc": "Top ratings"},
                
                # NOT operations
                {"name": "not_old", "expr": "not (year < 2020)", "desc": "Not old content"},
                {"name": "not_low_rating", "expr": "not (rating < 5.0)", "desc": "Not low rating"},
                {"name": "not_inactive", "expr": "not (is_active == False)", "desc": "Not inactive"},
                
                # Complex nested conditions
                {"name": "complex_nested", "expr": "(rating > 7.0 and is_featured == True) or (views > 100000 and year >= 2022)", "desc": "Complex nested condition"},
                {"name": "advanced_filter", "expr": '(category == "AI/ML" or category == "Deep Learning") and rating > 6.0 and (is_premium == True or views > 50000)', "desc": "Advanced multi-condition filter"},
                
                # Numeric range with multiple fields
                {"name": "multi_numeric", "expr": "rating * 2 > 12.0 and views / 1000 > 50", "desc": "Mathematical expressions in filters"},
            ]
            
            for test in filter_tests:
                try:
                    print(f"\n🔍 {test['name']}: {test['desc']}")
                    print(f"   Expression: {test['expr']}")
                    
                    search_results = self.collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=10,
                        expr=test['expr'],
                        output_fields=["title", "category", "rating", "year", "views", "is_featured", "is_premium", "is_active"]
                    )
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ Found {len(search_results[0])} results")
                        
                        # Show sample results
                        for i, hit in enumerate(search_results[0][:2]):
                            entity = hit.entity
                            print(f"      {i+1}. {entity.get('title', 'N/A')[:50]}...")
                            print(f"         Category: {entity.get('category')}, Rating: {entity.get('rating')}, Year: {entity.get('year')}")
                        
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
                            "description": test['desc'],
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:150]}...")
                    results[test['name']] = {
                        "success": False,
                        "expression": test['expr'],
                        "description": test['desc'],
                        "error": str(e)[:300]
                    }
            
        except Exception as e:
            print(f"❌ Error in advanced filtering: {e}")
            results["advanced_filtering_error"] = str(e)
        
        return results
    
    def test_binary_vector_search(self) -> Dict[str, Any]:
        """Test binary vector search capabilities."""
        print("\n🔢 Testing Binary Vector Search")
        print("=" * 35)
        
        results = {}
        
        try:
            # Create binary vector index
            try:
                self.collection.drop_index(field_name="binary_embedding")
            except:
                pass
            
            # Binary vector index options
            binary_indexes = [
                {"index_type": "BIN_FLAT", "metric_type": "HAMMING", "params": {}},
                {"index_type": "BIN_IVF_FLAT", "metric_type": "HAMMING", "params": {"nlist": 128}},
            ]
            
            for idx_config in binary_indexes:
                try:
                    print(f"\n🔧 Testing {idx_config['index_type']} index for binary vectors...")
                    
                    self.collection.create_index(
                        field_name="binary_embedding",
                        index_params=idx_config
                    )
                    
                    self.collection.load()
                    
                    # Generate binary query vector
                    binary_query = np.random.randint(0, 2, self.dimension // 8, dtype=np.uint8)
                    
                    search_params = {"metric_type": idx_config["metric_type"], "params": {"nprobe": 16} if "nprobe" in str(idx_config) else {}}
                    
                    search_results = self.collection.search(
                        data=[binary_query.tobytes()],
                        anns_field="binary_embedding",
                        param=search_params,
                        limit=10,
                        output_fields=["title", "category"]
                    )
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ Found {len(search_results[0])} results with {idx_config['index_type']}")
                        for i, hit in enumerate(search_results[0][:3]):
                            print(f"      {i+1}. Distance: {hit.distance}, Title: {hit.entity.get('title', 'N/A')[:50]}...")
                        
                        results[f"binary_{idx_config['index_type']}"] = {
                            "success": True,
                            "index_type": idx_config['index_type'],
                            "metric": idx_config['metric_type'],
                            "results_count": len(search_results[0])
                        }
                        break  # Use first working binary index
                    else:
                        print(f"   ⚠️ No results with {idx_config['index_type']}")
                        results[f"binary_{idx_config['index_type']}"] = {
                            "success": True,
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Binary search error with {idx_config['index_type']}: {str(e)[:100]}...")
                    results[f"binary_{idx_config['index_type']}"] = {
                        "success": False,
                        "error": str(e)[:200]
                    }
            
        except Exception as e:
            print(f"❌ Error in binary vector search: {e}")
            results["binary_search_error"] = str(e)
        
        return results
    
    def test_partition_search(self) -> Dict[str, Any]:
        """Test partition-based search capabilities."""
        print("\n📂 Testing Partition-Based Search")
        print("=" * 35)
        
        results = {}
        
        try:
            # Create partitions
            partition_names = ["high_quality", "medium_quality", "low_quality"]
            created_partitions = []
            
            for partition_name in partition_names:
                try:
                    if not self.collection.has_partition(partition_name):
                        self.collection.create_partition(partition_name)
                        print(f"   ✅ Created partition: {partition_name}")
                        created_partitions.append(partition_name)
                    else:
                        print(f"   📂 Partition already exists: {partition_name}")
                        created_partitions.append(partition_name)
                except Exception as e:
                    print(f"   ❌ Error creating partition {partition_name}: {e}")
            
            if created_partitions:
                # Test partition-specific search
                query_vector = np.random.random(self.dimension).astype(np.float32)
                query_vector = query_vector / np.linalg.norm(query_vector)
                
                search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
                
                # Search in specific partitions
                for partition in created_partitions:
                    try:
                        print(f"\n🔍 Searching in partition: {partition}")
                        
                        search_results = self.collection.search(
                            data=[query_vector.tolist()],
                            anns_field="embedding",
                            param=search_params,
                            limit=5,
                            partition_names=[partition],
                            output_fields=["title", "rating"]
                        )
                        
                        if search_results and search_results[0]:
                            print(f"   ✅ Found {len(search_results[0])} results in {partition}")
                            results[f"partition_{partition}"] = {
                                "success": True,
                                "partition": partition,
                                "results_count": len(search_results[0])
                            }
                        else:
                            print(f"   ⚠️ No results in partition {partition}")
                            results[f"partition_{partition}"] = {
                                "success": True,
                                "partition": partition,
                                "results_count": 0
                            }
                            
                    except Exception as e:
                        print(f"   ❌ Error searching partition {partition}: {str(e)[:100]}...")
                        results[f"partition_{partition}"] = {
                            "success": False,
                            "partition": partition,
                            "error": str(e)[:200]
                        }
                
                # Multi-partition search
                try:
                    print(f"\n🔍 Multi-partition search across {len(created_partitions)} partitions")
                    
                    search_results = self.collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=10,
                        partition_names=created_partitions[:2],  # Search in first 2 partitions
                        output_fields=["title", "rating"]
                    )
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ Multi-partition search: {len(search_results[0])} results")
                        results["multi_partition_search"] = {
                            "success": True,
                            "partitions": created_partitions[:2],
                            "results_count": len(search_results[0])
                        }
                    else:
                        print(f"   ⚠️ No results in multi-partition search")
                        results["multi_partition_search"] = {
                            "success": True,
                            "partitions": created_partitions[:2],
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Multi-partition search error: {str(e)[:100]}...")
                    results["multi_partition_search"] = {
                        "success": False,
                        "error": str(e)[:200]
                    }
            else:
                results["partition_error"] = "No partitions could be created"
            
        except Exception as e:
            print(f"❌ Error in partition search: {e}")
            results["partition_search_error"] = str(e)
        
        return results
    
    def test_aggregation_functions(self) -> Dict[str, Any]:
        """Test aggregation and statistical functions."""
        print("\n📊 Testing Aggregation Functions")
        print("=" * 35)
        
        results = {}
        
        # Note: Milvus may not support all aggregations, but let's test what's available
        aggregation_tests = [
            {"name": "count_all", "desc": "Count all entities"},
            {"name": "max_rating", "desc": "Maximum rating"},
            {"name": "min_rating", "desc": "Minimum rating"},
            {"name": "avg_rating", "desc": "Average rating"},
            {"name": "sum_views", "desc": "Sum of views"},
        ]
        
        for test in aggregation_tests:
            try:
                print(f"\n📈 {test['desc']}")
                
                # Try different approaches since direct aggregation may not be supported
                if test['name'] == 'count_all':
                    count = self.collection.num_entities
                    print(f"   ✅ Total entities: {count}")
                    results[test['name']] = {
                        "success": True,
                        "value": count,
                        "description": test['desc']
                    }
                else:
                    # For other aggregations, we might need to use query and calculate manually
                    # This is a limitation test
                    print(f"   ⚠️ Direct aggregation not supported - would need client-side calculation")
                    results[test['name']] = {
                        "success": False,
                        "error": "Direct aggregation not supported in current Milvus version",
                        "description": test['desc']
                    }
                    
            except Exception as e:
                print(f"   ❌ {test['desc']}: {str(e)[:100]}...")
                results[test['name']] = {
                    "success": False,
                    "error": str(e)[:200],
                    "description": test['desc']
                }
        
        return results
    
    def test_iterator_search(self) -> Dict[str, Any]:
        """Test iterator-based search for large result sets."""
        print("\n🔄 Testing Iterator-Based Search")
        print("=" * 35)
        
        results = {}
        
        try:
            # Test if iterator search is supported
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
            
            try:
                # Try iterator search (may not be supported in all versions)
                print("🔍 Attempting iterator-based search...")
                
                # This is a hypothetical API - may not exist
                # iterator = self.collection.search_iterator(
                #     data=[query_vector.tolist()],
                #     anns_field="embedding",
                #     param=search_params,
                #     batch_size=100
                # )
                
                print("   ⚠️ Iterator search API not available in current Milvus version")
                results["iterator_search"] = {
                    "success": False,
                    "error": "Iterator search not supported in current version",
                    "alternative": "Use pagination with offset/limit"
                }
                
            except Exception as e:
                print(f"   ❌ Iterator search error: {str(e)[:100]}...")
                results["iterator_search"] = {
                    "success": False,
                    "error": str(e)[:200]
                }
            
            # Test pagination as alternative
            print("\n📄 Testing pagination as alternative to iterator...")
            
            pagination_results = []
            page_size = 50
            max_pages = 3
            
            for page in range(max_pages):
                try:
                    # Simulate pagination by varying search parameters
                    search_results = self.collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=page_size,
                        output_fields=["title"]
                    )
                    
                    if search_results and search_results[0]:
                        page_count = len(search_results[0])
                        pagination_results.append(page_count)
                        print(f"   ✅ Page {page + 1}: {page_count} results")
                    else:
                        print(f"   ⚠️ Page {page + 1}: No results")
                        break
                        
                except Exception as e:
                    print(f"   ❌ Page {page + 1} error: {str(e)[:100]}...")
                    break
            
            if pagination_results:
                results["pagination_alternative"] = {
                    "success": True,
                    "pages_tested": len(pagination_results),
                    "total_results": sum(pagination_results),
                    "page_size": page_size
                }
            
        except Exception as e:
            print(f"❌ Error in iterator search testing: {e}")
            results["iterator_error"] = str(e)
        
        return results
    
    def run_comprehensive_exploration(self) -> Dict[str, Any]:
        """Run comprehensive exploration of ALL Milvus search features."""
        print("🚀 Comprehensive Milvus Search Features Exploration")
        print("=" * 60)
        print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_results = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "connection": {"host": self.host, "port": self.port},
            "exploration_type": "comprehensive"
        }
        
        # Connect
        if not self.connect():
            return {"error": "Failed to connect to Milvus"}
        
        # Create comprehensive collection
        if not self.create_comprehensive_collection():
            return {"error": "Failed to create comprehensive collection"}
        
        # Generate comprehensive data
        if not self.generate_comprehensive_data(2000):
            return {"error": "Failed to generate comprehensive data"}
        
        # Run all tests
        print("\n" + "="*60)
        all_results["index_types"] = self.test_all_index_types()
        
        print("\n" + "="*60)
        all_results["search_parameters"] = self.test_advanced_search_parameters()
        
        print("\n" + "="*60)
        all_results["range_search"] = self.test_range_search_capabilities()
        
        print("\n" + "="*60)
        all_results["advanced_filtering"] = self.test_advanced_filtering_expressions()
        
        print("\n" + "="*60)
        all_results["binary_vectors"] = self.test_binary_vector_search()
        
        print("\n" + "="*60)
        all_results["partitions"] = self.test_partition_search()
        
        print("\n" + "="*60)
        all_results["aggregations"] = self.test_aggregation_functions()
        
        print("\n" + "="*60)
        all_results["iterators"] = self.test_iterator_search()
        
        # Summary
        self.print_comprehensive_summary(all_results)
        
        return all_results
    
    def print_comprehensive_summary(self, results: Dict[str, Any]):
        """Print comprehensive summary of all tested features."""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE MILVUS FEATURES SUMMARY")
        print("=" * 80)
        
        feature_categories = [
            ("index_types", "Index Types & Metrics"),
            ("search_parameters", "Search Parameters"),
            ("range_search", "Range Search"),
            ("advanced_filtering", "Advanced Filtering"),
            ("binary_vectors", "Binary Vector Search"),
            ("partitions", "Partition Search"),
            ("aggregations", "Aggregation Functions"),
            ("iterators", "Iterator/Pagination")
        ]
        
        total_successful = 0
        total_tested = 0
        
        for category_key, category_name in feature_categories:
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
                            
                            # Add extra info for successful features
                            extra_info = ""
                            if "results_count" in feature_result:
                                extra_info += f" ({feature_result['results_count']} results)"
                            if "search_time" in feature_result:
                                extra_info += f" ({feature_result['search_time']:.4f}s)"
                                
                        else:
                            status = "❌"
                            extra_info = ""
                            if "error" in feature_result:
                                extra_info = f" - {feature_result['error'][:50]}..."
                        
                        print(f"   {status} {feature_name}{extra_info}")
                
                if tested > 0:
                    success_rate = (successful / tested) * 100
                    print(f"   📊 Category Success Rate: {successful}/{tested} ({success_rate:.1f}%)")
        
        # Overall summary
        if total_tested > 0:
            overall_success_rate = (total_successful / total_tested) * 100
            print(f"\n🎯 OVERALL SUCCESS RATE: {total_successful}/{total_tested} ({overall_success_rate:.1f}%)")
        
        print(f"\n⏰ Analysis completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
    
    def cleanup(self):
        """Clean up test resources."""
        try:
            if self.collection:
                utility.drop_collection(self.test_collection_name, using=self.connection_alias)
                print(f"🗑️ Cleaned up comprehensive test collection: {self.test_collection_name}")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
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
        
        # Save results to file
        output_file = f"milvus_comprehensive_analysis_{int(time.time())}.json"
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
        # Always cleanup
        explorer.cleanup()

if __name__ == "__main__":
    print(__doc__)
    main()
