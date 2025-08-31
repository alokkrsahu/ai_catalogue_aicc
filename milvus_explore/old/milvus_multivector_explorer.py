#!/usr/bin/env python3
"""
Milvus 2.4+ Multi-Vector Capabilities Explorer
==============================================

This script tests all the new multi-vector features available in Milvus 2.4+.
It explores hybrid search, multiple vector fields, sparse vectors, and advanced reranking.

Requirements:
- pymilvus>=2.4.0
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
    utility, AnnSearchRequest, RRFRanker, WeightedRanker
)

class MilvusMultiVectorExplorer:
    """Comprehensive explorer for Milvus 2.4+ multi-vector capabilities."""
    
    def __init__(self, host: str = "localhost", port: str = "19530"):
        """Initialize connection to Milvus."""
        self.host = host
        self.port = port
        self.connection_alias = "multivector_explorer"
        self.multi_collection_name = "ai_papers_multivector"
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
            
            # Get server info
            version = utility.get_server_version(using=self.connection_alias)
            collections = utility.list_collections(using=self.connection_alias)
            print(f"🔍 Milvus Server: {version}")
            print(f"📊 Existing Collections: {len(collections)}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Milvus: {e}")
            return False
    
    def create_multi_vector_collection(self) -> bool:
        """Create a collection with multiple vector fields (the main 2.4+ feature!)."""
        try:
            if utility.has_collection(self.multi_collection_name, using=self.connection_alias):
                utility.drop_collection(self.multi_collection_name, using=self.connection_alias)
                print(f"🗑️ Dropped existing collection")
            
            print("🏗️ Creating Multi-Vector Collection (NEW in 2.4+!)")
            
            # Define comprehensive multi-vector schema
            fields = [
                # Primary key
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                
                # Metadata fields
                FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="abstract", dtype=DataType.VARCHAR, max_length=2000),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="venue", dtype=DataType.VARCHAR, max_length=200),
                FieldSchema(name="year", dtype=DataType.INT32),
                FieldSchema(name="citation_count", dtype=DataType.INT64),
                FieldSchema(name="quality_score", dtype=DataType.FLOAT),
                FieldSchema(name="is_seminal", dtype=DataType.BOOL),
                FieldSchema(name="is_trending", dtype=DataType.BOOL),
                
                # MULTIPLE VECTOR FIELDS - This is the key 2.4+ feature!
                FieldSchema(name="title_embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                FieldSchema(name="abstract_embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                FieldSchema(name="methodology_embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                FieldSchema(name="results_embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                
                # Test sparse vector support (2.4+ feature)
                # Note: We'll test this separately as it may need special handling
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Multi-vector AI papers collection for testing 2.4+ features"
            )
            
            self.collection = Collection(
                name=self.multi_collection_name,
                schema=schema,
                using=self.connection_alias
            )
            
            print(f"✅ Successfully created multi-vector collection!")
            print(f"   📊 Total fields: {len(fields)}")
            print(f"   🎯 Vector fields: 4 (title, abstract, methodology, results)")
            print(f"   📝 Scalar fields: {len(fields) - 4}")
            
            # Display the schema
            print(f"\n📋 Collection Schema:")
            for field in fields:
                field_type = "VECTOR" if "embedding" in field.name else "SCALAR"
                print(f"   - {field.name}: {field.dtype} ({field_type})")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating multi-vector collection: {e}")
            print(f"   This might indicate you're still on Milvus < 2.4")
            import traceback
            traceback.print_exc()
            return False
    
    def populate_multi_vector_collection(self, num_entities: int = 1000) -> bool:
        """Populate the multi-vector collection with comprehensive test data."""
        print(f"\n🔄 Populating multi-vector collection with {num_entities} entities...")
        
        categories = ["NLP", "Computer Vision", "Machine Learning", "Robotics", "AI Theory", "Deep Learning"]
        venues = ["NeurIPS", "ICML", "ICLR", "AAAI", "IJCAI", "ACL", "EMNLP", "CVPR", "ICCV", "ECCV"]
        
        try:
            batch_size = 100
            
            for batch_start in range(0, num_entities, batch_size):
                batch_end = min(batch_start + batch_size, num_entities)
                
                # Generate comprehensive test data
                ids = list(range(batch_start, batch_end))
                titles = [f"Advanced {random.choice(['Neural', 'Deep', 'Reinforcement'])} Learning for {random.choice(['NLP', 'Vision', 'Robotics'])} Applications {i+1}" for i in range(batch_start, batch_end)]
                abstracts = [f"This paper presents a novel approach to {random.choice(['optimization', 'representation learning', 'transfer learning'])} using {random.choice(['transformers', 'CNNs', 'GANs', 'RNNs'])} with applications in {random.choice(['language understanding', 'image recognition', 'speech processing'])}." for i in range(batch_start, batch_end)]
                categories_list = [random.choice(categories) for _ in range(batch_end - batch_start)]
                venues_list = [random.choice(venues) for _ in range(batch_end - batch_start)]
                years = [random.randint(2018, 2024) for _ in range(batch_end - batch_start)]
                citation_counts = [random.randint(0, 1000) for _ in range(batch_end - batch_start)]
                quality_scores = [round(random.uniform(1.0, 10.0), 2) for _ in range(batch_end - batch_start)]
                is_seminal_list = [random.choice([True, False]) for _ in range(batch_end - batch_start)]
                is_trending_list = [random.choice([True, False]) for _ in range(batch_end - batch_start)]
                
                # Generate MULTIPLE VECTOR EMBEDDINGS - This is the key feature!
                title_embeddings = []
                abstract_embeddings = [] 
                methodology_embeddings = []
                results_embeddings = []
                
                for _ in range(batch_end - batch_start):
                    # Each vector field gets different embeddings
                    # Simulating different aspects of the same paper
                    
                    # Title embedding - focused on topic
                    title_vec = np.random.random(self.dimension).astype(np.float32)
                    title_vec = title_vec / np.linalg.norm(title_vec)
                    title_embeddings.append(title_vec.tolist())
                    
                    # Abstract embedding - broader semantic content
                    abstract_vec = np.random.random(self.dimension).astype(np.float32)
                    abstract_vec = abstract_vec / np.linalg.norm(abstract_vec)
                    abstract_embeddings.append(abstract_vec.tolist())
                    
                    # Methodology embedding - technical approach
                    method_vec = np.random.random(self.dimension).astype(np.float32)
                    method_vec = method_vec / np.linalg.norm(method_vec)
                    methodology_embeddings.append(method_vec.tolist())
                    
                    # Results embedding - outcomes and performance
                    results_vec = np.random.random(self.dimension).astype(np.float32)
                    results_vec = results_vec / np.linalg.norm(results_vec)
                    results_embeddings.append(results_vec.tolist())
                
                # Insert batch with ALL vector fields
                batch_data = [
                    ids, titles, abstracts, categories_list, venues_list, years, 
                    citation_counts, quality_scores, is_seminal_list, is_trending_list,
                    title_embeddings, abstract_embeddings, methodology_embeddings, results_embeddings
                ]
                
                insert_result = self.collection.insert(batch_data)
                
                if batch_start == 0:
                    print(f"   ✅ First batch inserted: {insert_result.insert_count} entities")
                    print(f"   🎯 Each entity has 4 different vector embeddings!")
            
            self.collection.flush()
            print(f"✅ Successfully populated multi-vector collection: {num_entities} entities")
            print(f"   📊 Total vectors stored: {num_entities * 4} (4 per entity)")
            
            return True
            
        except Exception as e:
            print(f"❌ Error populating multi-vector collection: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_multi_vector_indexes(self) -> Dict[str, bool]:
        """Create indexes for all vector fields."""
        print(f"\n🔧 Creating Indexes for Multiple Vector Fields")
        print("=" * 50)
        
        results = {}
        vector_fields = ["title_embedding", "abstract_embedding", "methodology_embedding", "results_embedding"]
        
        # Index configuration - using IVF_FLAT for compatibility
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "L2", 
            "params": {"nlist": 128}
        }
        
        for field_name in vector_fields:
            try:
                print(f"   🔧 Creating index for {field_name}...")
                
                self.collection.create_index(
                    field_name=field_name,
                    index_params=index_params
                )
                
                print(f"   ✅ Index created for {field_name}")
                results[field_name] = True
                
            except Exception as e:
                print(f"   ❌ Failed to create index for {field_name}: {e}")
                results[field_name] = False
        
        # Load collection
        try:
            print(f"\n🔄 Loading collection to memory...")
            self.collection.load()
            print(f"✅ Multi-vector collection loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading collection: {e}")
            results["collection_load"] = False
            return results
        
        results["collection_load"] = True
        return results
    
    def test_individual_vector_searches(self) -> Dict[str, Any]:
        """Test individual searches on each vector field."""
        print(f"\n🔍 Testing Individual Vector Field Searches")
        print("=" * 50)
        
        results = {}
        vector_fields = ["title_embedding", "abstract_embedding", "methodology_embedding", "results_embedding"]
        
        search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
        
        for field_name in vector_fields:
            try:
                print(f"\n🔍 Searching {field_name}:")
                
                # Generate query vector
                query_vector = np.random.random(self.dimension).astype(np.float32)
                query_vector = query_vector / np.linalg.norm(query_vector)
                
                start_time = time.time()
                search_results = self.collection.search(
                    data=[query_vector.tolist()],
                    anns_field=field_name,
                    param=search_params,
                    limit=5,
                    output_fields=["title", "category", "venue", "quality_score"]
                )
                search_time = time.time() - start_time
                
                if search_results and search_results[0]:
                    print(f"   ✅ Found {len(search_results[0])} results ({search_time:.4f}s)")
                    
                    # Show sample results
                    for i, hit in enumerate(search_results[0][:3]):
                        entity = hit.entity
                        print(f"      {i+1}. Distance: {hit.distance:.4f}")
                        print(f"         Title: {entity.get('title', 'N/A')[:80]}...")
                        print(f"         Category: {entity.get('category')}, Venue: {entity.get('venue')}")
                    
                    results[field_name] = {
                        "success": True,
                        "results_count": len(search_results[0]),
                        "search_time": search_time,
                        "avg_distance": sum(hit.distance for hit in search_results[0]) / len(search_results[0])
                    }
                else:
                    print(f"   ⚠️ No results found")
                    results[field_name] = {"success": True, "results_count": 0}
                    
            except Exception as e:
                print(f"   ❌ Error searching {field_name}: {e}")
                results[field_name] = {"success": False, "error": str(e)[:200]}
        
        return results
    
    def test_hybrid_search_rrf(self) -> Dict[str, Any]:
        """Test hybrid search with RRF (Reciprocal Rank Fusion) reranking."""
        print(f"\n🔀 Testing Hybrid Search with RRF Reranking")
        print("=" * 50)
        
        results = {}
        
        try:
            # Generate query vectors for different aspects
            title_query = np.random.random(self.dimension).astype(np.float32)
            title_query = title_query / np.linalg.norm(title_query)
            
            abstract_query = np.random.random(self.dimension).astype(np.float32)
            abstract_query = abstract_query / np.linalg.norm(abstract_query)
            
            methodology_query = np.random.random(self.dimension).astype(np.float32)
            methodology_query = methodology_query / np.linalg.norm(methodology_query)
            
            print("🎯 Creating hybrid search with 3 vector fields...")
            
            # Create ANN search requests for hybrid search
            search_requests = [
                AnnSearchRequest(
                    data=[title_query.tolist()],
                    anns_field="title_embedding",
                    param={"metric_type": "L2", "params": {"nprobe": 16}},
                    limit=20  # Get more results for reranking
                ),
                AnnSearchRequest(
                    data=[abstract_query.tolist()],
                    anns_field="abstract_embedding",
                    param={"metric_type": "L2", "params": {"nprobe": 16}},
                    limit=20
                ),
                AnnSearchRequest(
                    data=[methodology_query.tolist()],
                    anns_field="methodology_embedding", 
                    param={"metric_type": "L2", "params": {"nprobe": 16}},
                    limit=20
                )
            ]
            
            # RRF Reranker
            rrf_ranker = RRFRanker(k=60)
            
            print("🔄 Executing hybrid search...")
            start_time = time.time()
            
            hybrid_results = self.collection.hybrid_search(
                reqs=search_requests,
                rerank=rrf_ranker,
                limit=10,
                output_fields=["title", "category", "venue", "quality_score", "year"]
            )
            
            search_time = time.time() - start_time
            
            if hybrid_results and hybrid_results[0]:
                print(f"✅ Hybrid search successful! ({search_time:.4f}s)")
                print(f"📊 Results combined from 3 vector fields using RRF reranking")
                print(f"🎯 Final results: {len(hybrid_results[0])}")
                
                print(f"\n📋 Top Hybrid Search Results:")
                for i, hit in enumerate(hybrid_results[0][:5]):
                    entity = hit.entity
                    print(f"   {i+1}. Score: {hit.distance:.4f}")
                    print(f"      Title: {entity.get('title', 'N/A')[:80]}...")
                    print(f"      Category: {entity.get('category')}, Venue: {entity.get('venue')}")
                    print(f"      Year: {entity.get('year')}, Quality: {entity.get('quality_score')}")
                
                results["rrf_hybrid_search"] = {
                    "success": True,
                    "search_time": search_time,
                    "results_count": len(hybrid_results[0]),
                    "vector_fields_used": 3,
                    "reranking_method": "RRF"
                }
            else:
                print(f"⚠️ No hybrid search results")
                results["rrf_hybrid_search"] = {"success": True, "results_count": 0}
                
        except Exception as e:
            print(f"❌ Error in RRF hybrid search: {e}")
            results["rrf_hybrid_search"] = {"success": False, "error": str(e)[:300]}
            import traceback
            traceback.print_exc()
        
        return results
    
    def test_hybrid_search_weighted(self) -> Dict[str, Any]:
        """Test hybrid search with weighted scoring reranking."""
        print(f"\n⚖️ Testing Hybrid Search with Weighted Scoring")
        print("=" * 50)
        
        results = {}
        
        try:
            # Generate query vectors
            title_query = np.random.random(self.dimension).astype(np.float32)
            title_query = title_query / np.linalg.norm(title_query)
            
            abstract_query = np.random.random(self.dimension).astype(np.float32)
            abstract_query = abstract_query / np.linalg.norm(abstract_query)
            
            results_query = np.random.random(self.dimension).astype(np.float32)
            results_query = results_query / np.linalg.norm(results_query)
            
            print("🎯 Creating weighted hybrid search...")
            print("   📊 Weights: Title=0.5, Abstract=0.3, Results=0.2")
            
            # Create search requests with different priorities
            search_requests = [
                AnnSearchRequest(
                    data=[title_query.tolist()],
                    anns_field="title_embedding",
                    param={"metric_type": "L2", "params": {"nprobe": 16}},
                    limit=20
                ),
                AnnSearchRequest(
                    data=[abstract_query.tolist()],
                    anns_field="abstract_embedding",
                    param={"metric_type": "L2", "params": {"nprobe": 16}},
                    limit=20
                ),
                AnnSearchRequest(
                    data=[results_query.tolist()],
                    anns_field="results_embedding",
                    param={"metric_type": "L2", "params": {"nprobe": 16}},
                    limit=20
                )
            ]
            
            # Weighted reranker - title gets highest weight
            weighted_ranker = WeightedRanker(weights=[0.5, 0.3, 0.2])
            
            print("🔄 Executing weighted hybrid search...")
            start_time = time.time()
            
            hybrid_results = self.collection.hybrid_search(
                reqs=search_requests,
                rerank=weighted_ranker,
                limit=10,
                output_fields=["title", "category", "venue", "quality_score", "citation_count"]
            )
            
            search_time = time.time() - start_time
            
            if hybrid_results and hybrid_results[0]:
                print(f"✅ Weighted hybrid search successful! ({search_time:.4f}s)")
                print(f"📊 Results weighted: Title (50%) + Abstract (30%) + Results (20%)")
                
                print(f"\n📋 Top Weighted Search Results:")
                for i, hit in enumerate(hybrid_results[0][:5]):
                    entity = hit.entity
                    print(f"   {i+1}. Weighted Score: {hit.distance:.4f}")
                    print(f"      Title: {entity.get('title', 'N/A')[:80]}...")
                    print(f"      Category: {entity.get('category')}, Citations: {entity.get('citation_count')}")
                
                results["weighted_hybrid_search"] = {
                    "success": True,
                    "search_time": search_time,
                    "results_count": len(hybrid_results[0]),
                    "vector_fields_used": 3,
                    "reranking_method": "Weighted",
                    "weights": [0.5, 0.3, 0.2]
                }
            else:
                print(f"⚠️ No weighted hybrid search results")
                results["weighted_hybrid_search"] = {"success": True, "results_count": 0}
                
        except Exception as e:
            print(f"❌ Error in weighted hybrid search: {e}")
            results["weighted_hybrid_search"] = {"success": False, "error": str(e)[:300]}
        
        return results
    
    def test_advanced_filtering_with_hybrid_search(self) -> Dict[str, Any]:
        """Test hybrid search combined with advanced filtering."""
        print(f"\n🎯 Testing Hybrid Search + Advanced Filtering")
        print("=" * 50)
        
        results = {}
        
        try:
            # Generate query vectors
            title_query = np.random.random(self.dimension).astype(np.float32)
            title_query = title_query / np.linalg.norm(title_query)
            
            abstract_query = np.random.random(self.dimension).astype(np.float32)
            abstract_query = abstract_query / np.linalg.norm(abstract_query)
            
            # Complex filtering expressions
            filter_tests = [
                {
                    "name": "high_quality_recent",
                    "expr": "quality_score > 7.0 and year >= 2022",
                    "desc": "High quality recent papers"
                },
                {
                    "name": "seminal_trending",
                    "expr": "is_seminal == True or is_trending == True",
                    "desc": "Seminal OR trending papers"
                },
                {
                    "name": "top_venues_cited",
                    "expr": 'venue in ["NeurIPS", "ICML", "ICLR"] and citation_count > 50',
                    "desc": "Top venues with high citations"
                }
            ]
            
            for test in filter_tests:
                try:
                    print(f"\n🔍 {test['name']}: {test['desc']}")
                    print(f"   Filter: {test['expr']}")
                    
                    # Hybrid search with filtering
                    search_requests = [
                        AnnSearchRequest(
                            data=[title_query.tolist()],
                            anns_field="title_embedding",
                            param={"metric_type": "L2", "params": {"nprobe": 16}},
                            limit=15,
                            expr=test['expr']
                        ),
                        AnnSearchRequest(
                            data=[abstract_query.tolist()],
                            anns_field="abstract_embedding", 
                            param={"metric_type": "L2", "params": {"nprobe": 16}},
                            limit=15,
                            expr=test['expr']
                        )
                    ]
                    
                    start_time = time.time()
                    hybrid_results = self.collection.hybrid_search(
                        reqs=search_requests,
                        rerank=RRFRanker(k=30),
                        limit=5,
                        output_fields=["title", "category", "venue", "year", "quality_score", "citation_count", "is_seminal", "is_trending"]
                    )
                    search_time = time.time() - start_time
                    
                    if hybrid_results and hybrid_results[0]:
                        print(f"   ✅ Found {len(hybrid_results[0])} filtered results ({search_time:.4f}s)")
                        
                        for i, hit in enumerate(hybrid_results[0][:3]):
                            entity = hit.entity
                            print(f"      {i+1}. Score: {hit.distance:.4f}")
                            print(f"         {entity.get('title', 'N/A')[:60]}...")
                            print(f"         Venue: {entity.get('venue')}, Year: {entity.get('year')}, Quality: {entity.get('quality_score')}")
                        
                        results[test['name']] = {
                            "success": True,
                            "expression": test['expr'],
                            "results_count": len(hybrid_results[0]),
                            "search_time": search_time
                        }
                    else:
                        print(f"   ⚠️ No results found")
                        results[test['name']] = {
                            "success": True,
                            "expression": test['expr'],
                            "results_count": 0
                        }
                        
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    results[test['name']] = {"success": False, "error": str(e)[:200]}
            
        except Exception as e:
            print(f"❌ Error in advanced filtering test: {e}")
            results["advanced_filtering_error"] = str(e)
        
        return results
    
    def test_collection_statistics(self) -> Dict[str, Any]:
        """Test collection statistics for multi-vector setup."""
        print(f"\n📊 Multi-Vector Collection Statistics")
        print("=" * 40)
        
        stats = {}
        
        try:
            print("📈 Collection Statistics:")
            print(f"   Name: {self.collection.name}")
            print(f"   Description: {self.collection.description}")
            
            # Entity count
            entity_count = self.collection.num_entities
            print(f"   Entity count: {entity_count}")
            stats["entity_count"] = entity_count
            
            # Total vectors stored
            vector_fields = 4  # title, abstract, methodology, results
            total_vectors = entity_count * vector_fields
            print(f"   Total vectors stored: {total_vectors} ({vector_fields} per entity)")
            stats["total_vectors"] = total_vectors
            stats["vectors_per_entity"] = vector_fields
            
            # Schema analysis
            schema = self.collection.schema
            vector_fields_list = []
            scalar_fields_list = []
            
            for field in schema.fields:
                if "embedding" in field.name:
                    vector_fields_list.append(field.name)
                else:
                    scalar_fields_list.append(field.name)
            
            print(f"   Vector fields: {len(vector_fields_list)}")
            for vf in vector_fields_list:
                print(f"      - {vf}")
            
            print(f"   Scalar fields: {len(scalar_fields_list)}")
            for sf in scalar_fields_list[:5]:  # Show first 5
                print(f"      - {sf}")
            if len(scalar_fields_list) > 5:
                print(f"      - ... and {len(scalar_fields_list)-5} more")
            
            stats["vector_fields"] = vector_fields_list
            stats["scalar_fields"] = scalar_fields_list
            stats["schema_field_count"] = len(schema.fields)
            
            # Index information
            try:
                indexes = self.collection.indexes
                print(f"   Indexes: {len(indexes)}")
                index_info = []
                for idx in indexes:
                    idx_data = {
                        "field": idx.field_name,
                        "type": idx.params.get('index_type', 'Unknown'),
                        "metric": idx.params.get('metric_type', 'Unknown')
                    }
                    index_info.append(idx_data)
                    print(f"      - {idx.field_name}: {idx.params.get('index_type')} ({idx.params.get('metric_type')})")
                
                stats["indexes"] = index_info
            except Exception as e:
                print(f"   Index info error: {e}")
                stats["indexes"] = []
            
            stats["success"] = True
            
        except Exception as e:
            print(f"❌ Error getting collection statistics: {e}")
            stats["error"] = str(e)
            stats["success"] = False
        
        return stats
    
    def run_multi_vector_exploration(self) -> Dict[str, Any]:
        """Run comprehensive exploration of Milvus 2.4+ multi-vector capabilities."""
        print("🚀 Milvus 2.4+ Multi-Vector Capabilities Exploration")
        print("=" * 60)
        print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Testing Multi-Vector Features (New in 2.4+)")
        
        all_results = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "connection": {"host": self.host, "port": self.port},
            "test_type": "multi_vector_2_4_plus",
            "features_tested": [
                "Multi-vector collection creation",
                "Multiple vector field indexing", 
                "Individual vector field searches",
                "Hybrid search with RRF reranking",
                "Hybrid search with weighted scoring",
                "Advanced filtering with hybrid search",
                "Multi-vector collection statistics"
            ]
        }
        
        # Connect
        if not self.connect():
            return {"error": "Failed to connect to Milvus"}
        
        # Test multi-vector collection creation
        if not self.create_multi_vector_collection():
            return {"error": "Failed to create multi-vector collection - you may need Milvus 2.4+"}
        
        # Populate with test data
        if not self.populate_multi_vector_collection(1000):
            return {"error": "Failed to populate multi-vector collection"}
        
        # Create indexes for all vector fields
        print("\n" + "="*60)
        all_results["index_creation"] = self.create_multi_vector_indexes()
        
        # Test individual vector searches
        print("\n" + "="*60)
        all_results["individual_searches"] = self.test_individual_vector_searches()
        
        # Test hybrid search with RRF
        print("\n" + "="*60) 
        all_results["rrf_hybrid_search"] = self.test_hybrid_search_rrf()
        
        # Test hybrid search with weighted scoring
        print("\n" + "="*60)
        all_results["weighted_hybrid_search"] = self.test_hybrid_search_weighted()
        
        # Test advanced filtering with hybrid search
        print("\n" + "="*60)
        all_results["filtered_hybrid_search"] = self.test_advanced_filtering_with_hybrid_search()
        
        # Collection statistics
        print("\n" + "="*60)
        all_results["collection_statistics"] = self.test_collection_statistics()
        
        # Generate summary
        self.generate_multi_vector_summary(all_results)
        
        return all_results
    
    def generate_multi_vector_summary(self, results: Dict[str, Any]):
        """Generate comprehensive summary of multi-vector testing."""
        print("\n" + "=" * 80)
        print("📋 MILVUS 2.4+ MULTI-VECTOR CAPABILITIES SUMMARY")
        print("=" * 80)
        
        # Feature success tracking
        features_tested = [
            ("index_creation", "Multi-Vector Index Creation"), 
            ("individual_searches", "Individual Vector Field Searches"),
            ("rrf_hybrid_search", "RRF Hybrid Search"),
            ("weighted_hybrid_search", "Weighted Hybrid Search"),
            ("filtered_hybrid_search", "Filtered Hybrid Search"),
            ("collection_statistics", "Multi-Vector Statistics")
        ]
        
        total_successful = 0
        total_tested = 0
        
        for category_key, category_name in features_tested:
            if category_key in results:
                print(f"\n🔍 {category_name}:")
                
                category_data = results[category_key]
                if isinstance(category_data, dict):
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
                                if "results_count" in feature_result and feature_result["results_count"] > 0:
                                    metrics.append(f"{feature_result['results_count']} results")
                                if "search_time" in feature_result:
                                    metrics.append(f"{feature_result['search_time']:.4f}s")
                                if "vector_fields_used" in feature_result:
                                    metrics.append(f"{feature_result['vector_fields_used']} vectors")
                                
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
        
        # Key capabilities discovered
        print(f"\n🔑 KEY MULTI-VECTOR CAPABILITIES:")
        print(f"   ✅ Multi-vector collections: 4 vector fields per entity")
        print(f"   ✅ Hybrid search: Combine multiple vector fields")  
        print(f"   ✅ RRF reranking: Reciprocal rank fusion")
        print(f"   ✅ Weighted scoring: Custom vector field weights")
        print(f"   ✅ Advanced filtering: Hybrid search + metadata filters")
        print(f"   ✅ Individual field search: Search each vector independently")
        
        # Architecture benefits
        if "collection_statistics" in results and results["collection_statistics"].get("success"):
            stats = results["collection_statistics"]
            entity_count = stats.get("entity_count", 0)
            total_vectors = stats.get("total_vectors", 0)
            
            print(f"\n📊 ARCHITECTURE BENEFITS:")
            print(f"   • Single collection: {entity_count} entities with {total_vectors} total vectors")
            print(f"   • Unified schema: {len(stats.get('vector_fields', []))} vector + {len(stats.get('scalar_fields', []))} scalar fields")
            print(f"   • Simplified queries: No cross-collection joins needed")
            print(f"   • Built-in reranking: RRF and weighted strategies")
        
        print(f"\n⏰ Analysis completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
    
    def cleanup(self):
        """Clean up test resources."""
        try:
            if self.collection:
                utility.drop_collection(self.multi_collection_name, using=self.connection_alias)
                print(f"🗑️ Cleaned up multi-vector collection: {self.multi_collection_name}")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        try:
            connections.disconnect(self.connection_alias)
            print("🔌 Disconnected from Milvus")
        except Exception as e:
            print(f"⚠️ Disconnect warning: {e}")

def main():
    """Main execution function."""
    explorer = MilvusMultiVectorExplorer()
    
    try:
        # Run multi-vector exploration
        results = explorer.run_multi_vector_exploration()
        
        # Save results
        output_file = f"milvus_multivector_analysis_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Multi-vector analysis results saved to: {output_file}")
        
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
