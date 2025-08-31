#!/usr/bin/env python3
"""
Comprehensive Milvus Search Techniques & Parameters Explorer
===========================================================

This script systematically investigates ALL search techniques, index types, 
distance metrics, and parameters supported by Milvus 2.4+.

It explores:
- All vector index types and their parameters
- All distance metrics for each index type
- All search parameters and their effects
- Range search capabilities
- Hybrid search configurations
- Sparse vector search (if supported)
- Binary vector search
- Advanced filtering techniques
- Iterator-based search patterns
- Performance characteristics

Requirements:
- pymilvus>=2.4.0
- numpy
"""

import json
import random
import time
import sys
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, AnnSearchRequest, RRFRanker, WeightedRanker
)

class ComprehensiveSearchExplorer:
    """Comprehensive explorer for ALL Milvus search techniques and parameters."""
    
    def __init__(self, host: str = "localhost", port: str = "19530"):
        """Initialize connection to Milvus."""
        self.host = host
        self.port = port
        self.connection_alias = "search_explorer"
        self.test_collection_name = "search_techniques_test"
        self.binary_collection_name = "binary_search_test"
        self.sparse_collection_name = "sparse_search_test"
        self.dimension = 128
        self.all_results = {}
        
        # Collections for different vector types
        self.float_collection = None
        self.binary_collection = None
        self.sparse_collection = None
        
    def connect(self) -> bool:
        """Establish connection to Milvus."""
        try:
            connections.connect(
                alias=self.connection_alias,
                host=self.host,
                port=self.port
            )
            version = utility.get_server_version(using=self.connection_alias)
            collections = utility.list_collections(using=self.connection_alias)
            
            print(f"✅ Connected to Milvus {version}")
            print(f"📊 Existing collections: {len(collections)}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Milvus: {e}")
            return False
    
    def create_test_collections(self) -> Dict[str, bool]:
        """Create test collections for different vector types."""
        print("\n🏗️ Creating Test Collections for Different Vector Types")
        print("=" * 60)
        
        results = {}
        
        # 1. Float vector collection with comprehensive schema
        try:
            if utility.has_collection(self.test_collection_name, using=self.connection_alias):
                utility.drop_collection(self.test_collection_name, using=self.connection_alias)
            
            float_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="rating", dtype=DataType.FLOAT),
                FieldSchema(name="year", dtype=DataType.INT32),
                FieldSchema(name="views", dtype=DataType.INT64),
                FieldSchema(name="is_featured", dtype=DataType.BOOL),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ]
            
            float_schema = CollectionSchema(
                fields=float_fields,
                description="Float vector collection for comprehensive search testing"
            )
            
            self.float_collection = Collection(
                name=self.test_collection_name,
                schema=float_schema,
                using=self.connection_alias
            )
            
            print("✅ Float vector collection created")
            results["float_collection"] = True
            
        except Exception as e:
            print(f"❌ Error creating float collection: {e}")
            results["float_collection"] = False
        
        # 2. Binary vector collection
        try:
            if utility.has_collection(self.binary_collection_name, using=self.connection_alias):
                utility.drop_collection(self.binary_collection_name, using=self.connection_alias)
            
            binary_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="binary_embedding", dtype=DataType.BINARY_VECTOR, dim=self.dimension),
            ]
            
            binary_schema = CollectionSchema(
                fields=binary_fields,
                description="Binary vector collection for testing"
            )
            
            self.binary_collection = Collection(
                name=self.binary_collection_name,
                schema=binary_schema,
                using=self.connection_alias
            )
            
            print("✅ Binary vector collection created")
            results["binary_collection"] = True
            
        except Exception as e:
            print(f"❌ Error creating binary collection: {e}")
            results["binary_collection"] = False
        
        # 3. Sparse vector collection (if supported)
        try:
            if utility.has_collection(self.sparse_collection_name, using=self.connection_alias):
                utility.drop_collection(self.sparse_collection_name, using=self.connection_alias)
            
            sparse_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="sparse_embedding", dtype=DataType.SPARSE_FLOAT_VECTOR),
            ]
            
            sparse_schema = CollectionSchema(
                fields=sparse_fields,
                description="Sparse vector collection for testing"
            )
            
            self.sparse_collection = Collection(
                name=self.sparse_collection_name,
                schema=sparse_schema,
                using=self.connection_alias
            )
            
            print("✅ Sparse vector collection created")
            results["sparse_collection"] = True
            
        except Exception as e:
            print(f"❌ Sparse vectors not supported or error: {e}")
            results["sparse_collection"] = False
        
        return results
    
    def populate_collections(self, num_entities: int = 2000) -> Dict[str, bool]:
        """Populate all test collections with comprehensive data."""
        print(f"\n🔄 Populating Collections with {num_entities} entities each")
        print("=" * 60)
        
        results = {}
        categories = ["AI/ML", "Computer Vision", "NLP", "Robotics", "Data Science", "Deep Learning"]
        
        # Populate float collection
        if self.float_collection:
            try:
                print("📊 Populating float vector collection...")
                float_data = []
                
                for i in range(num_entities):
                    vector = np.random.random(self.dimension).astype(np.float32)
                    vector = vector / np.linalg.norm(vector)
                    
                    entity = {
                        "id": i,
                        "title": f"AI Research Paper {i+1}: Advanced {random.choice(['Neural', 'Deep', 'Machine'])} Learning",
                        "category": random.choice(categories),
                        "tags": ",".join(random.sample(["research", "production", "experimental", "benchmark"], 2)),
                        "rating": round(random.uniform(1.0, 10.0), 2),
                        "year": random.randint(2018, 2024),
                        "views": random.randint(100, 100000),
                        "is_featured": random.choice([True, False]),
                        "embedding": vector.tolist()
                    }
                    float_data.append(entity)
                
                insert_result = self.float_collection.insert(float_data)
                self.float_collection.flush()
                print(f"   ✅ Float collection: {insert_result.insert_count} entities")
                results["float_data"] = True
                
            except Exception as e:
                print(f"   ❌ Error populating float collection: {e}")
                results["float_data"] = False
        
        # Populate binary collection
        if self.binary_collection:
            try:
                print("📊 Populating binary vector collection...")
                binary_data = []
                
                for i in range(min(num_entities, 1000)):  # Smaller for binary
                    binary_vector = np.random.randint(0, 2, self.dimension // 8, dtype=np.uint8)
                    
                    entity = {
                        "id": i,
                        "title": f"Binary Document {i+1}",
                        "category": random.choice(categories),
                        "binary_embedding": binary_vector.tobytes()
                    }
                    binary_data.append(entity)
                
                insert_result = self.binary_collection.insert(binary_data)
                self.binary_collection.flush()
                print(f"   ✅ Binary collection: {insert_result.insert_count} entities")
                results["binary_data"] = True
                
            except Exception as e:
                print(f"   ❌ Error populating binary collection: {e}")
                results["binary_data"] = False
        
        # Populate sparse collection
        if self.sparse_collection:
            try:
                print("📊 Populating sparse vector collection...")
                sparse_data = []
                
                for i in range(min(num_entities, 500)):  # Smaller for sparse
                    # Create sparse vector (indices and values)
                    indices = sorted(random.sample(range(1000), random.randint(5, 20)))
                    values = [random.random() for _ in indices]
                    sparse_vector = {idx: val for idx, val in zip(indices, values)}
                    
                    entity = {
                        "id": i,
                        "title": f"Sparse Document {i+1}",
                        "sparse_embedding": sparse_vector
                    }
                    sparse_data.append(entity)
                
                insert_result = self.sparse_collection.insert(sparse_data)
                self.sparse_collection.flush()
                print(f"   ✅ Sparse collection: {insert_result.insert_count} entities")
                results["sparse_data"] = True
                
            except Exception as e:
                print(f"   ❌ Error populating sparse collection: {e}")
                results["sparse_data"] = False
        
        return results
    
    def investigate_all_index_types(self) -> Dict[str, Any]:
        """Systematically test all available index types and their parameters."""
        print(f"\n🔧 Investigating ALL Index Types & Parameters")
        print("=" * 60)
        
        results = {}
        
        # Float vector index types to test
        float_index_configs = [
            # Basic indexes
            {"name": "FLAT", "params": {"index_type": "FLAT", "metric_type": "L2", "params": {}}},
            {"name": "IVF_FLAT", "params": {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}}},
            {"name": "IVF_SQ8", "params": {"index_type": "IVF_SQ8", "metric_type": "L2", "params": {"nlist": 128}}},
            {"name": "IVF_PQ", "params": {"index_type": "IVF_PQ", "metric_type": "L2", "params": {"nlist": 128, "m": 8, "nbits": 8}}},
            
            # Graph-based indexes
            {"name": "HNSW", "params": {"index_type": "HNSW", "metric_type": "L2", "params": {"M": 16, "efConstruction": 200}}},
            
            # Advanced indexes (may not be available in all versions)
            {"name": "SCANN", "params": {"index_type": "SCANN", "metric_type": "L2", "params": {"nlist": 128}}},
            {"name": "AUTOINDEX", "params": {"index_type": "AUTOINDEX", "metric_type": "L2", "params": {}}},
            
            # GPU indexes (if available)
            {"name": "GPU_IVF_FLAT", "params": {"index_type": "GPU_IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}}},
            {"name": "GPU_IVF_PQ", "params": {"index_type": "GPU_IVF_PQ", "metric_type": "L2", "params": {"nlist": 128, "m": 8, "nbits": 8}}},
            {"name": "CAGRA", "params": {"index_type": "CAGRA", "metric_type": "L2", "params": {"intermediate_graph_degree": 64, "graph_degree": 32}}},
        ]
        
        # Distance metrics to test with each index
        metrics_to_test = ["L2", "IP", "COSINE"]
        
        print("🔍 Testing Float Vector Indexes:")
        float_results = {}
        
        for idx_config in float_index_configs:
            for metric in metrics_to_test:
                test_name = f"{idx_config['name']}_{metric}"
                print(f"\n   🧪 Testing: {test_name}")
                
                try:
                    # Prepare index parameters with current metric
                    test_params = idx_config["params"].copy()
                    test_params["metric_type"] = metric
                    
                    # Drop existing index
                    try:
                        self.float_collection.release()
                        self.float_collection.drop_index()
                        time.sleep(0.5)
                    except:
                        pass
                    
                    # Create index
                    start_time = time.time()
                    self.float_collection.create_index(
                        field_name="embedding",
                        index_params=test_params
                    )
                    index_time = time.time() - start_time
                    
                    # Load collection
                    self.float_collection.load()
                    
                    # Test search
                    query_vector = np.random.random(self.dimension).astype(np.float32)
                    query_vector = query_vector / np.linalg.norm(query_vector)
                    
                    # Determine search parameters based on index type
                    search_params = {"metric_type": metric}
                    if "IVF" in idx_config['name'] or "SCANN" in idx_config['name']:
                        search_params["params"] = {"nprobe": 16}
                    elif "HNSW" in idx_config['name']:
                        search_params["params"] = {"ef": 64}
                    elif "CAGRA" in idx_config['name']:
                        search_params["params"] = {"search_width": 32}
                    else:
                        search_params["params"] = {}
                    
                    # Perform search
                    start_time = time.time()
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=10
                    )
                    search_time = time.time() - start_time
                    
                    if search_results and search_results[0]:
                        avg_distance = sum(hit.distance for hit in search_results[0]) / len(search_results[0])
                        
                        print(f"      ✅ Success: {len(search_results[0])} results")
                        print(f"         Index time: {index_time:.4f}s, Search time: {search_time:.4f}s")
                        print(f"         Avg distance: {avg_distance:.4f}")
                        
                        float_results[test_name] = {
                            "success": True,
                            "index_type": idx_config['name'],
                            "metric_type": metric,
                            "index_time": index_time,
                            "search_time": search_time,
                            "results_count": len(search_results[0]),
                            "avg_distance": avg_distance,
                            "index_params": test_params["params"]
                        }
                    else:
                        print(f"      ⚠️  No results returned")
                        float_results[test_name] = {
                            "success": False,
                            "error": "No results returned"
                        }
                        
                except Exception as e:
                    print(f"      ❌ Failed: {str(e)[:100]}...")
                    float_results[test_name] = {
                        "success": False,
                        "error": str(e)[:200]
                    }
        
        results["float_indexes"] = float_results
        
        # Binary vector indexes
        if self.binary_collection:
            print(f"\n🔍 Testing Binary Vector Indexes:")
            binary_results = {}
            
            binary_index_configs = [
                {"name": "BIN_FLAT", "params": {"index_type": "BIN_FLAT", "metric_type": "HAMMING", "params": {}}},
                {"name": "BIN_IVF_FLAT", "params": {"index_type": "BIN_IVF_FLAT", "metric_type": "HAMMING", "params": {"nlist": 128}}},
            ]
            
            binary_metrics = ["HAMMING", "JACCARD"]
            
            for idx_config in binary_index_configs:
                for metric in binary_metrics:
                    test_name = f"{idx_config['name']}_{metric}"
                    print(f"\n   🧪 Testing: {test_name}")
                    
                    try:
                        test_params = idx_config["params"].copy()
                        test_params["metric_type"] = metric
                        
                        # Drop existing index
                        try:
                            self.binary_collection.release()
                            self.binary_collection.drop_index()
                            time.sleep(0.5)
                        except:
                            pass
                        
                        # Create index
                        self.binary_collection.create_index(
                            field_name="binary_embedding",
                            index_params=test_params
                        )
                        self.binary_collection.load()
                        
                        # Test search
                        binary_query = np.random.randint(0, 2, self.dimension // 8, dtype=np.uint8)
                        search_params = {"metric_type": metric}
                        if "IVF" in idx_config['name']:
                            search_params["params"] = {"nprobe": 16}
                        else:
                            search_params["params"] = {}
                        
                        search_results = self.binary_collection.search(
                            data=[binary_query.tobytes()],
                            anns_field="binary_embedding",
                            param=search_params,
                            limit=5
                        )
                        
                        if search_results and search_results[0]:
                            print(f"      ✅ Success: {len(search_results[0])} results")
                            binary_results[test_name] = {
                                "success": True,
                                "index_type": idx_config['name'],
                                "metric_type": metric,
                                "results_count": len(search_results[0])
                            }
                        else:
                            print(f"      ⚠️  No results")
                            binary_results[test_name] = {"success": False, "error": "No results"}
                            
                    except Exception as e:
                        print(f"      ❌ Failed: {str(e)[:100]}...")
                        binary_results[test_name] = {"success": False, "error": str(e)[:200]}
            
            results["binary_indexes"] = binary_results
        
        return results
    
    def investigate_search_parameters(self) -> Dict[str, Any]:
        """Investigate all search parameters and their effects."""
        print(f"\n⚙️ Investigating Search Parameters & Their Effects")
        print("=" * 60)
        
        results = {}
        
        # Ensure we have a working index
        try:
            self.float_collection.release()
            self.float_collection.drop_index()
            
            index_params = {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}}
            self.float_collection.create_index(field_name="embedding", index_params=index_params)
            self.float_collection.load()
            
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
        except Exception as e:
            print(f"❌ Error setting up for parameter testing: {e}")
            return {"error": str(e)}
        
        # Parameter sets to test
        parameter_tests = [
            # nprobe variations (for IVF indexes)
            {"name": "nprobe_variations", "base_params": {"metric_type": "L2"}, 
             "param_sets": [
                 {"nprobe": 1}, {"nprobe": 4}, {"nprobe": 8}, {"nprobe": 16}, 
                 {"nprobe": 32}, {"nprobe": 64}, {"nprobe": 128}
             ]},
            
            # Different limits
            {"name": "limit_variations", "base_params": {"metric_type": "L2", "params": {"nprobe": 16}},
             "param_sets": [
                 {"limit": 1}, {"limit": 5}, {"limit": 10}, {"limit": 20}, 
                 {"limit": 50}, {"limit": 100}
             ]},
            
            # Different metrics with same index
            {"name": "metric_variations", "base_params": {"params": {"nprobe": 16}},
             "param_sets": [
                 {"metric_type": "L2"}, {"metric_type": "IP"}, {"metric_type": "COSINE"}
             ]},
        ]
        
        for test_group in parameter_tests:
            print(f"\n🔬 Testing {test_group['name']}:")
            group_results = {}
            
            for i, param_set in enumerate(test_group["param_sets"]):
                try:
                    # Merge base params with test params
                    search_params = test_group["base_params"].copy()
                    
                    # Handle limit separately
                    limit = param_set.pop("limit", 10)
                    
                    # Merge remaining params
                    for key, value in param_set.items():
                        if key == "metric_type":
                            search_params[key] = value
                        else:
                            if "params" not in search_params:
                                search_params["params"] = {}
                            search_params["params"][key] = value
                    
                    print(f"   🧪 Test {i+1}: {param_set} (limit={limit})")
                    
                    # Perform search
                    start_time = time.time()
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=limit
                    )
                    search_time = time.time() - start_time
                    
                    if search_results and search_results[0]:
                        avg_distance = sum(hit.distance for hit in search_results[0]) / len(search_results[0])
                        
                        print(f"      ✅ {len(search_results[0])} results, {search_time:.4f}s, avg_dist: {avg_distance:.4f}")
                        
                        group_results[f"test_{i}"] = {
                            "success": True,
                            "parameters": param_set,
                            "limit": limit,
                            "results_count": len(search_results[0]),
                            "search_time": search_time,
                            "avg_distance": avg_distance,
                            "search_params": search_params
                        }
                    else:
                        print(f"      ⚠️  No results")
                        group_results[f"test_{i}"] = {
                            "success": False,
                            "parameters": param_set,
                            "error": "No results"
                        }
                        
                except Exception as e:
                    print(f"      ❌ Error: {str(e)[:100]}...")
                    group_results[f"test_{i}"] = {
                        "success": False,
                        "parameters": param_set,
                        "error": str(e)[:200]
                    }
            
            results[test_group['name']] = group_results
        
        return results
    
    def investigate_range_search(self) -> Dict[str, Any]:
        """Investigate range search capabilities and parameters."""
        print(f"\n📏 Investigating Range Search Capabilities")
        print("=" * 50)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Range search configurations to test
            range_configs = [
                # Basic range search
                {"name": "range_0_5_to_1_0", "params": {"radius": 1.0, "range_filter": 0.5}, "desc": "Distance range [0.5, 1.0]"},
                {"name": "range_0_3_to_0_8", "params": {"radius": 0.8, "range_filter": 0.3}, "desc": "Distance range [0.3, 0.8]"},
                {"name": "range_1_0_to_2_0", "params": {"radius": 2.0, "range_filter": 1.0}, "desc": "Distance range [1.0, 2.0]"},
                
                # Radius-only search
                {"name": "radius_0_5", "params": {"radius": 0.5}, "desc": "All within radius 0.5"},
                {"name": "radius_1_0", "params": {"radius": 1.0}, "desc": "All within radius 1.0"},
                {"name": "radius_1_5", "params": {"radius": 1.5}, "desc": "All within radius 1.5"},
                
                # Range filter only (minimum distance)
                {"name": "min_dist_0_3", "params": {"range_filter": 0.3}, "desc": "Minimum distance 0.3"},
                {"name": "min_dist_0_5", "params": {"range_filter": 0.5}, "desc": "Minimum distance 0.5"},
                {"name": "min_dist_0_8", "params": {"range_filter": 0.8}, "desc": "Minimum distance 0.8"},
            ]
            
            for config in range_configs:
                try:
                    print(f"\n🔍 {config['name']}: {config['desc']}")
                    
                    # Prepare search parameters
                    search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
                    search_params["params"].update(config["params"])
                    
                    # Perform range search
                    start_time = time.time()
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=200,  # Higher limit for range search
                        output_fields=["title", "category", "rating"]
                    )
                    search_time = time.time() - start_time
                    
                    if search_results and search_results[0]:
                        distances = [hit.distance for hit in search_results[0]]
                        min_dist = min(distances)
                        max_dist = max(distances)
                        
                        print(f"   ✅ Found {len(search_results[0])} results ({search_time:.4f}s)")
                        print(f"   📊 Distance range: {min_dist:.4f} - {max_dist:.4f}")
                        
                        # Verify range constraints
                        range_valid = True
                        if "radius" in config["params"] and "range_filter" in config["params"]:
                            range_valid = all(config["params"]["range_filter"] <= d <= config["params"]["radius"] for d in distances)
                        elif "radius" in config["params"]:
                            range_valid = all(d <= config["params"]["radius"] for d in distances)
                        elif "range_filter" in config["params"]:
                            range_valid = all(d >= config["params"]["range_filter"] for d in distances)
                        
                        print(f"   🎯 Range constraint satisfied: {range_valid}")
                        
                        results[config['name']] = {
                            "success": True,
                            "description": config["desc"],
                            "parameters": config["params"],
                            "results_count": len(search_results[0]),
                            "search_time": search_time,
                            "min_distance": min_dist,
                            "max_distance": max_dist,
                            "range_valid": range_valid
                        }
                    else:
                        print(f"   ⚠️  No results found")
                        results[config['name']] = {
                            "success": True,
                            "description": config["desc"],
                            "parameters": config["params"],
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:100]}...")
                    results[config['name']] = {
                        "success": False,
                        "description": config["desc"],
                        "parameters": config["params"],
                        "error": str(e)[:200]
                    }
            
        except Exception as e:
            print(f"❌ Error in range search investigation: {e}")
            results["range_search_error"] = str(e)
        
        return results
    
    def investigate_hybrid_search_techniques(self) -> Dict[str, Any]:
        """Investigate hybrid search techniques and reranking strategies."""
        print(f"\n🔀 Investigating Hybrid Search Techniques")
        print("=" * 50)
        
        results = {}
        
        # Create a multi-vector collection for hybrid search testing
        hybrid_collection_name = "hybrid_search_test"
        
        try:
            if utility.has_collection(hybrid_collection_name, using=self.connection_alias):
                utility.drop_collection(hybrid_collection_name, using=self.connection_alias)
            
            # Multi-vector schema
            hybrid_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="rating", dtype=DataType.FLOAT),
                FieldSchema(name="vec1", dtype=DataType.FLOAT_VECTOR, dim=128),
                FieldSchema(name="vec2", dtype=DataType.FLOAT_VECTOR, dim=128),
                FieldSchema(name="vec3", dtype=DataType.FLOAT_VECTOR, dim=128),
            ]
            
            hybrid_schema = CollectionSchema(fields=hybrid_fields, description="Hybrid search test collection")
            hybrid_collection = Collection(name=hybrid_collection_name, schema=hybrid_schema, using=self.connection_alias)
            
            # Populate with test data
            hybrid_data = []
            for i in range(500):
                entity = {
                    "id": i,
                    "title": f"Document {i}",
                    "category": random.choice(["AI", "ML", "DL"]),
                    "rating": round(random.uniform(1.0, 10.0), 1),
                    "vec1": (np.random.random(128) / np.linalg.norm(np.random.random(128))).tolist(),
                    "vec2": (np.random.random(128) / np.linalg.norm(np.random.random(128))).tolist(),
                    "vec3": (np.random.random(128) / np.linalg.norm(np.random.random(128))).tolist(),
                }
                hybrid_data.append(entity)
            
            hybrid_collection.insert(hybrid_data)
            hybrid_collection.flush()
            
            # Create indexes
            index_params = {"index_type": "FLAT", "metric_type": "L2", "params": {}}
            for vec_field in ["vec1", "vec2", "vec3"]:
                hybrid_collection.create_index(field_name=vec_field, index_params=index_params)
            
            hybrid_collection.load()
            print("✅ Hybrid search test collection ready")
            
            # Test different hybrid search configurations
            query_vec = (np.random.random(128) / np.linalg.norm(np.random.random(128))).tolist()
            
            hybrid_tests = [
                {
                    "name": "rrf_two_vectors",
                    "description": "RRF reranking with 2 vector fields",
                    "requests": [
                        AnnSearchRequest(data=[query_vec], anns_field="vec1", param={"metric_type": "L2", "params": {}}, limit=20),
                        AnnSearchRequest(data=[query_vec], anns_field="vec2", param={"metric_type": "L2", "params": {}}, limit=20),
                    ],
                    "reranker": RRFRanker(k=40)
                },
                {
                    "name": "rrf_three_vectors",
                    "description": "RRF reranking with 3 vector fields",
                    "requests": [
                        AnnSearchRequest(data=[query_vec], anns_field="vec1", param={"metric_type": "L2", "params": {}}, limit=15),
                        AnnSearchRequest(data=[query_vec], anns_field="vec2", param={"metric_type": "L2", "params": {}}, limit=15),
                        AnnSearchRequest(data=[query_vec], anns_field="vec3", param={"metric_type": "L2", "params": {}}, limit=15),
                    ],
                    "reranker": RRFRanker(k=45)
                },
                {
                    "name": "weighted_equal",
                    "description": "Weighted reranking with equal weights",
                    "requests": [
                        AnnSearchRequest(data=[query_vec], anns_field="vec1", param={"metric_type": "L2", "params": {}}, limit=20),
                        AnnSearchRequest(data=[query_vec], anns_field="vec2", param={"metric_type": "L2", "params": {}}, limit=20),
                    ],
                    "reranker": WeightedRanker([0.5, 0.5])
                },
                {
                    "name": "weighted_biased",
                    "description": "Weighted reranking with biased weights",
                    "requests": [
                        AnnSearchRequest(data=[query_vec], anns_field="vec1", param={"metric_type": "L2", "params": {}}, limit=20),
                        AnnSearchRequest(data=[query_vec], anns_field="vec2", param={"metric_type": "L2", "params": {}}, limit=20),
                        AnnSearchRequest(data=[query_vec], anns_field="vec3", param={"metric_type": "L2", "params": {}}, limit=20),
                    ],
                    "reranker": WeightedRanker([0.6, 0.3, 0.1])
                },
            ]
            
            for test in hybrid_tests:
                try:
                    print(f"\n🧪 {test['name']}: {test['description']}")
                    
                    start_time = time.time()
                    hybrid_results = hybrid_collection.hybrid_search(
                        reqs=test["requests"],
                        rerank=test["reranker"],
                        limit=10,
                        output_fields=["title", "category", "rating"]
                    )
                    search_time = time.time() - start_time
                    
                    if hybrid_results and hybrid_results[0]:
                        print(f"   ✅ Success: {len(hybrid_results[0])} results ({search_time:.4f}s)")
                        print(f"   📊 Vector fields: {len(test['requests'])}, Reranker: {type(test['reranker']).__name__}")
                        
                        results[test['name']] = {
                            "success": True,
                            "description": test["description"],
                            "vector_fields_count": len(test["requests"]),
                            "reranker_type": type(test["reranker"]).__name__,
                            "results_count": len(hybrid_results[0]),
                            "search_time": search_time
                        }
                    else:
                        print(f"   ⚠️  No results")
                        results[test['name']] = {"success": False, "error": "No results"}
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:100]}...")
                    results[test['name']] = {"success": False, "error": str(e)[:200]}
            
            # Cleanup
            utility.drop_collection(hybrid_collection_name, using=self.connection_alias)
            
        except Exception as e:
            print(f"❌ Error in hybrid search investigation: {e}")
            results["hybrid_search_error"] = str(e)
        
        return results
    
    def investigate_advanced_filtering(self) -> Dict[str, Any]:
        """Investigate advanced filtering capabilities."""
        print(f"\n🎯 Investigating Advanced Filtering Techniques")
        print("=" * 55)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
            
            # Comprehensive filter expressions to test
            filter_expressions = [
                # Basic comparisons
                {"name": "rating_gt", "expr": "rating > 5.0", "desc": "Greater than"},
                {"name": "rating_gte", "expr": "rating >= 7.5", "desc": "Greater than or equal"},
                {"name": "rating_lt", "expr": "rating < 3.0", "desc": "Less than"},
                {"name": "rating_lte", "expr": "rating <= 2.5", "desc": "Less than or equal"},
                {"name": "rating_eq", "expr": "rating == 8.5", "desc": "Exact equality"},
                {"name": "rating_ne", "expr": "rating != 5.0", "desc": "Not equal"},
                
                # String operations
                {"name": "category_exact", "expr": 'category == "AI/ML"', "desc": "String exact match"},
                {"name": "category_not", "expr": 'category != "Computer Vision"', "desc": "String not equal"},
                {"name": "title_like", "expr": 'title like "AI Research%"', "desc": "String pattern matching"},
                
                # Boolean operations
                {"name": "is_featured", "expr": "is_featured == True", "desc": "Boolean true"},
                {"name": "not_featured", "expr": "is_featured == False", "desc": "Boolean false"},
                
                # Range operations
                {"name": "rating_range", "expr": "rating > 6.0 and rating < 9.0", "desc": "Numeric range with AND"},
                {"name": "year_range", "expr": "year >= 2020 and year <= 2023", "desc": "Integer range"},
                {"name": "views_range", "expr": "views > 1000 and views < 50000", "desc": "Large integer range"},
                
                # Complex AND operations
                {"name": "multi_and", "expr": 'category == "AI/ML" and rating > 7.0 and is_featured == True', "desc": "Multiple AND conditions"},
                {"name": "numeric_and", "expr": "year >= 2022 and views > 10000 and rating > 6.0", "desc": "Numeric AND conditions"},
                
                # Complex OR operations
                {"name": "rating_or_views", "expr": "rating > 8.0 or views > 50000", "desc": "High rating OR high views"},
                {"name": "category_or", "expr": 'category == "AI/ML" or category == "Computer Vision"', "desc": "Multiple category options"},
                {"name": "featured_or_rated", "expr": "is_featured == True or rating > 8.5", "desc": "Featured OR highly rated"},
                
                # IN operations
                {"name": "category_in", "expr": 'category in ["AI/ML", "Deep Learning", "NLP"]', "desc": "Category in list"},
                {"name": "year_in", "expr": "year in [2022, 2023, 2024]", "desc": "Year in list"},
                {"name": "rating_in", "expr": "rating in [8.0, 8.5, 9.0, 9.5, 10.0]", "desc": "Rating in list"},
                
                # NOT operations
                {"name": "not_old", "expr": "not (year < 2020)", "desc": "NOT with parentheses"},
                {"name": "not_low_rated", "expr": "not (rating < 5.0)", "desc": "NOT low rated"},
                {"name": "not_category", "expr": 'not (category == "Robotics")', "desc": "NOT category"},
                
                # Complex nested conditions
                {"name": "nested_complex", "expr": "(rating > 7.0 and is_featured == True) or (views > 50000 and year >= 2022)", "desc": "Complex nested with OR"},
                {"name": "advanced_multi", "expr": '(category == "AI/ML" or category == "Deep Learning") and rating > 6.0 and (is_featured == True or views > 25000)', "desc": "Advanced multi-condition"},
                
                # Mathematical expressions
                {"name": "math_expression", "expr": "rating * 2 > 15.0", "desc": "Mathematical expression"},
                {"name": "ratio_expression", "expr": "views / 1000 > rating", "desc": "Ratio comparison"},
                
                # String functions
                {"name": "string_contains", "expr": 'tags like "%research%"', "desc": "String contains"},
                {"name": "string_prefix", "expr": 'title like "Advanced%"', "desc": "String prefix match"},
                {"name": "string_suffix", "expr": 'title like "%Learning"', "desc": "String suffix match"},
            ]
            
            for filter_test in filter_expressions:
                try:
                    print(f"\n🧪 {filter_test['name']}: {filter_test['desc']}")
                    print(f"   Expression: {filter_test['expr']}")
                    
                    start_time = time.time()
                    search_results = self.float_collection.search(
                        data=[query_vector.tolist()],
                        anns_field="embedding",
                        param=search_params,
                        limit=10,
                        expr=filter_test['expr'],
                        output_fields=["title", "category", "rating", "year", "views", "is_featured"]
                    )
                    search_time = time.time() - start_time
                    
                    if search_results and search_results[0]:
                        print(f"   ✅ Success: {len(search_results[0])} results ({search_time:.4f}s)")
                        
                        # Show sample result for verification
                        if search_results[0]:
                            hit = search_results[0][0]
                            print(f"   📋 Sample: Rating={getattr(hit, 'rating', 'N/A')}, Category={getattr(hit, 'category', 'N/A')}")
                        
                        results[filter_test['name']] = {
                            "success": True,
                            "expression": filter_test['expr'],
                            "description": filter_test['desc'],
                            "results_count": len(search_results[0]),
                            "search_time": search_time
                        }
                    else:
                        print(f"   ⚠️  No results (expression may be too restrictive)")
                        results[filter_test['name']] = {
                            "success": True,
                            "expression": filter_test['expr'],
                            "description": filter_test['desc'],
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:150]}...")
                    results[filter_test['name']] = {
                        "success": False,
                        "expression": filter_test['expr'],
                        "description": filter_test['desc'],
                        "error": str(e)[:300]
                    }
            
        except Exception as e:
            print(f"❌ Error in advanced filtering investigation: {e}")
            results["advanced_filtering_error"] = str(e)
        
        return results
    
    def investigate_performance_characteristics(self) -> Dict[str, Any]:
        """Investigate performance characteristics across different scenarios."""
        print(f"\n📈 Investigating Performance Characteristics")
        print("=" * 50)
        
        results = {}
        
        try:
            query_vector = np.random.random(self.dimension).astype(np.float32)
            query_vector = query_vector / np.linalg.norm(query_vector)
            
            # Performance test scenarios
            performance_tests = [
                # Different result set sizes
                {"name": "small_results", "limit": 5, "desc": "Small result set"},
                {"name": "medium_results", "limit": 50, "desc": "Medium result set"},
                {"name": "large_results", "limit": 200, "desc": "Large result set"},
                {"name": "very_large_results", "limit": 500, "desc": "Very large result set"},
                
                # Different nprobe values (precision vs speed)
                {"name": "fast_search", "nprobe": 1, "limit": 10, "desc": "Fast search (low precision)"},
                {"name": "balanced_search", "nprobe": 16, "limit": 10, "desc": "Balanced search"},
                {"name": "precise_search", "nprobe": 64, "limit": 10, "desc": "Precise search (slower)"},
                {"name": "max_precision", "nprobe": 128, "limit": 10, "desc": "Maximum precision"},
                
                # Filtered vs unfiltered
                {"name": "unfiltered", "limit": 10, "expr": None, "desc": "No filtering"},
                {"name": "simple_filter", "limit": 10, "expr": "rating > 5.0", "desc": "Simple filter"},
                {"name": "complex_filter", "limit": 10, "expr": 'category == "AI/ML" and rating > 7.0 and is_featured == True', "desc": "Complex filter"},
            ]
            
            for test in performance_tests:
                try:
                    print(f"\n⏱️  {test['name']}: {test['desc']}")
                    
                    # Prepare search parameters
                    search_params = {"metric_type": "L2", "params": {"nprobe": test.get("nprobe", 16)}}
                    limit = test.get("limit", 10)
                    expr = test.get("expr")
                    
                    # Run multiple iterations for better timing
                    times = []
                    results_counts = []
                    
                    for _ in range(5):  # 5 iterations
                        start_time = time.time()
                        search_results = self.float_collection.search(
                            data=[query_vector.tolist()],
                            anns_field="embedding",
                            param=search_params,
                            limit=limit,
                            expr=expr
                        )
                        search_time = time.time() - start_time
                        
                        times.append(search_time)
                        if search_results and search_results[0]:
                            results_counts.append(len(search_results[0]))
                        else:
                            results_counts.append(0)
                    
                    # Calculate statistics
                    avg_time = sum(times) / len(times)
                    min_time = min(times)
                    max_time = max(times)
                    avg_results = sum(results_counts) / len(results_counts) if results_counts else 0
                    
                    print(f"   ✅ Avg: {avg_time:.4f}s, Min: {min_time:.4f}s, Max: {max_time:.4f}s")
                    print(f"   📊 Results: {avg_results:.1f} avg")
                    
                    results[test['name']] = {
                        "success": True,
                        "description": test["desc"],
                        "parameters": {k: v for k, v in test.items() if k not in ["name", "desc"]},
                        "avg_time": avg_time,
                        "min_time": min_time,
                        "max_time": max_time,
                        "avg_results": avg_results,
                        "iterations": len(times)
                    }
                    
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:100]}...")
                    results[test['name']] = {
                        "success": False,
                        "description": test["desc"],
                        "error": str(e)[:200]
                    }
            
        except Exception as e:
            print(f"❌ Error in performance investigation: {e}")
            results["performance_error"] = str(e)
        
        return results
    
    def run_comprehensive_investigation(self) -> Dict[str, Any]:
        """Run comprehensive investigation of all search techniques."""
        print("🚀 Comprehensive Milvus Search Techniques Investigation")
        print("=" * 70)
        print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_results = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "connection": {"host": self.host, "port": self.port},
            "investigation_type": "comprehensive_search_techniques"
        }
        
        # Connect
        if not self.connect():
            return {"error": "Failed to connect to Milvus"}
        
        # Create test collections
        print("\n" + "="*70)
        all_results["collection_creation"] = self.create_test_collections()
        
        # Populate collections
        print("\n" + "="*70)
        all_results["data_population"] = self.populate_collections(2000)
        
        # Investigate all index types
        print("\n" + "="*70)
        all_results["index_investigation"] = self.investigate_all_index_types()
        
        # Investigate search parameters
        print("\n" + "="*70)
        all_results["parameter_investigation"] = self.investigate_search_parameters()
        
        # Investigate range search
        print("\n" + "="*70)
        all_results["range_search"] = self.investigate_range_search()
        
        # Investigate hybrid search
        print("\n" + "="*70)
        all_results["hybrid_search"] = self.investigate_hybrid_search_techniques()
        
        # Investigate advanced filtering
        print("\n" + "="*70)
        all_results["advanced_filtering"] = self.investigate_advanced_filtering()
        
        # Investigate performance
        print("\n" + "="*70)
        all_results["performance_analysis"] = self.investigate_performance_characteristics()
        
        # Generate comprehensive summary
        self.generate_comprehensive_summary(all_results)
        
        return all_results
    
    def generate_comprehensive_summary(self, results: Dict[str, Any]):
        """Generate comprehensive summary of all investigated techniques."""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE SEARCH TECHNIQUES SUMMARY")
        print("=" * 80)
        
        # Count successful techniques
        total_techniques = 0
        successful_techniques = 0
        
        categories = [
            ("index_investigation", "Index Types & Metrics"),
            ("parameter_investigation", "Search Parameters"),
            ("range_search", "Range Search"),
            ("hybrid_search", "Hybrid Search"),
            ("advanced_filtering", "Advanced Filtering"),
            ("performance_analysis", "Performance Analysis")
        ]
        
        for category_key, category_name in categories:
            if category_key in results and isinstance(results[category_key], dict):
                print(f"\n🔍 {category_name}:")
                
                category_successful = 0
                category_total = 0
                
                for technique_name, technique_result in results[category_key].items():
                    if isinstance(technique_result, dict):
                        if "success" in technique_result:
                            category_total += 1
                            total_techniques += 1
                            
                            if technique_result["success"]:
                                category_successful += 1
                                successful_techniques += 1
                                status = "✅"
                                
                                # Show key metrics
                                metrics = []
                                if "search_time" in technique_result:
                                    metrics.append(f"{technique_result['search_time']:.4f}s")
                                if "results_count" in technique_result:
                                    metrics.append(f"{technique_result['results_count']} results")
                                if "avg_time" in technique_result:
                                    metrics.append(f"avg: {technique_result['avg_time']:.4f}s")
                                
                                extra = f" ({', '.join(metrics)})" if metrics else ""
                            else:
                                status = "❌"
                                extra = ""
                            
                            print(f"   {status} {technique_name}{extra}")
                        elif isinstance(technique_result, dict):
                            # Handle nested results
                            for sub_name, sub_result in technique_result.items():
                                if isinstance(sub_result, dict) and "success" in sub_result:
                                    category_total += 1
                                    total_techniques += 1
                                    
                                    if sub_result["success"]:
                                        category_successful += 1
                                        successful_techniques += 1
                                        status = "✅"
                                    else:
                                        status = "❌"
                                    
                                    print(f"   {status} {technique_name}.{sub_name}")
                
                if category_total > 0:
                    success_rate = (category_successful / category_total) * 100
                    print(f"   📊 Success Rate: {category_successful}/{category_total} ({success_rate:.1f}%)")
        
        # Overall summary
        if total_techniques > 0:
            overall_success_rate = (successful_techniques / total_techniques) * 100
            print(f"\n🎯 OVERALL SUCCESS RATE: {successful_techniques}/{total_techniques} ({overall_success_rate:.1f}%)")
        
        # Key findings
        print(f"\n🔑 KEY FINDINGS:")
        
        # Index types summary
        if "index_investigation" in results and "float_indexes" in results["index_investigation"]:
            float_indexes = results["index_investigation"]["float_indexes"]
            working_indexes = [name for name, result in float_indexes.items() if result.get("success")]
            print(f"   📊 Working Index Types: {len(working_indexes)} tested")
            for idx in working_indexes[:5]:  # Show first 5
                print(f"      - {idx}")
            if len(working_indexes) > 5:
                print(f"      - ... and {len(working_indexes)-5} more")
        
        # Search parameters summary
        if "parameter_investigation" in results:
            param_results = results["parameter_investigation"]
            print(f"   ⚙️  Search Parameter Categories: {len(param_results)} tested")
            for param_type in param_results.keys():
                print(f"      - {param_type.replace('_', ' ').title()}")
        
        # Performance insights
        if "performance_analysis" in results:
            perf_results = results["performance_analysis"]
            working_perf = [name for name, result in perf_results.items() if result.get("success")]
            if working_perf:
                print(f"   📈 Performance Scenarios: {len(working_perf)} tested")
                # Find fastest and slowest
                times = [(name, result.get("avg_time", float('inf'))) for name, result in perf_results.items() if result.get("success") and "avg_time" in result]
                if times:
                    fastest = min(times, key=lambda x: x[1])
                    slowest = max(times, key=lambda x: x[1])
                    print(f"      - Fastest: {fastest[0]} ({fastest[1]:.4f}s)")
                    print(f"      - Slowest: {slowest[0]} ({slowest[1]:.4f}s)")
        
        print(f"\n⏰ Investigation completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
    
    def cleanup(self):
        """Clean up all test collections."""
        collections_to_clean = [
            self.test_collection_name,
            self.binary_collection_name, 
            self.sparse_collection_name
        ]
        
        for collection_name in collections_to_clean:
            try:
                if utility.has_collection(collection_name, using=self.connection_alias):
                    utility.drop_collection(collection_name, using=self.connection_alias)
                    print(f"🗑️ Cleaned up: {collection_name}")
            except Exception as e:
                print(f"⚠️ Cleanup warning for {collection_name}: {e}")
        
        try:
            connections.disconnect(self.connection_alias)
            print("🔌 Disconnected from Milvus")
        except Exception as e:
            print(f"⚠️ Disconnect warning: {e}")

def main():
    """Main execution function."""
    explorer = ComprehensiveSearchExplorer()
    
    try:
        # Run comprehensive investigation
        results = explorer.run_comprehensive_investigation()
        
        # Save results
        output_file = f"milvus_comprehensive_search_investigation_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Comprehensive investigation results saved to: {output_file}")
        
        return results
        
    except KeyboardInterrupt:
        print("\n⚠️ Investigation interrupted by user")
    except Exception as e:
        print(f"\n❌ Investigation failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        explorer.cleanup()

if __name__ == "__main__":
    print(__doc__)
    main()
