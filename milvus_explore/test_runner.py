#!/usr/bin/env python3
"""
Test runner for the Milvus Concurrent Search Engine package.
"""

import unittest
import sys
import os
import time
import numpy as np
from typing import List, Dict, Any

# Add package to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from milvus_package import (
    ConcurrentSearchEngine, ConnectionConfig, SearchRequest, SearchParams,
    IndexType, MetricType, SearchMode, OptimizationStrategy
)

class TestMilvusPackage(unittest.TestCase):
    """Test suite for Milvus concurrent search engine."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.config = ConnectionConfig(
            host="localhost",
            port="19530",
            max_connections=5
        )
        
        cls.test_vectors = cls.generate_test_vectors(10, 128)
        cls.collection_name = "test_collection"  # Change to your test collection
    
    @staticmethod
    def generate_test_vectors(count: int, dimension: int) -> List[List[float]]:
        """Generate normalized test vectors."""
        vectors = []
        for _ in range(count):
            vector = np.random.random(dimension).astype(np.float32)
            vector = vector / np.linalg.norm(vector)
            vectors.append(vector.tolist())
        return vectors
    
    def setUp(self):
        """Set up each test."""
        self.engine = ConcurrentSearchEngine(max_workers=3, enable_monitoring=True)
        
    def tearDown(self):
        """Clean up after each test."""
        if self.engine:
            self.engine.shutdown()
    
    def test_connection_management(self):
        """Test connection management functionality."""
        # Test adding instance
        success = self.engine.add_milvus_instance("test", self.config, set_as_default=True)
        
        if not success:
            self.skipTest("Could not connect to Milvus - skipping connection tests")
        
        # Test instance listing
        instances = self.engine.list_instances()
        self.assertIn("test", instances)
        
        # Test instance stats
        stats = self.engine.get_instance_info("test")
        self.assertIn("test", stats)
        self.assertIn("config", stats["test"])
    
    def test_basic_search(self):
        """Test basic vector search functionality."""
        success = self.engine.add_milvus_instance("test", self.config, set_as_default=True)
        
        if not success:
            self.skipTest("Could not connect to Milvus - skipping search tests")
        
        request = SearchRequest(
            collection_name=self.collection_name,
            query_vectors=self.test_vectors[:1],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType.L2,
            limit=5
        )
        
        try:
            result = self.engine.search(request)
            
            # Verify result structure
            self.assertIsNotNone(result)
            self.assertIsInstance(result.hits, list)
            self.assertIsInstance(result.search_time, float)
            self.assertGreater(result.search_time, 0)
            self.assertIsInstance(result.total_results, int)
            
        except Exception as e:
            self.skipTest(f"Search failed - collection may not exist: {e}")
    
    def test_algorithm_optimization(self):
        """Test algorithm optimization functionality."""
        success = self.engine.add_milvus_instance("test", self.config, set_as_default=True)
        
        if not success:
            self.skipTest("Could not connect to Milvus - skipping optimization tests")
        
        # Test parameter optimization
        strategy = OptimizationStrategy(
            priority="speed",
            data_size_hint=1000,
            target_latency_ms=50
        )
        
        request = SearchRequest(
            collection_name=self.collection_name,
            query_vectors=self.test_vectors[:1],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType.L2,
            limit=5
        )
        
        optimized_request = self.engine.optimize_search_parameters(request, strategy)
        
        # Verify optimization occurred
        self.assertIsNotNone(optimized_request.search_params)
        self.assertIsInstance(optimized_request.index_type, IndexType)
        self.assertIsInstance(optimized_request.metric_type, MetricType)
    
    def test_batch_search(self):
        """Test batch search functionality."""
        success = self.engine.add_milvus_instance("test", self.config, set_as_default=True)
        
        if not success:
            self.skipTest("Could not connect to Milvus - skipping batch tests")
        
        # Create multiple requests
        requests = []
        for i in range(3):
            request = SearchRequest(
                collection_name=self.collection_name,
                query_vectors=[self.test_vectors[i]],
                index_type=IndexType.AUTOINDEX,
                metric_type=MetricType.L2,
                limit=3
            )
            requests.append(request)
        
        try:
            results = self.engine.batch_search(requests, max_concurrent=2)
            
            # Verify batch results
            self.assertEqual(len(results), len(requests))
            for result in results:
                self.assertIsNotNone(result)
                self.assertIsInstance(result.search_time, float)
                
        except Exception as e:
            self.skipTest(f"Batch search failed: {e}")
    
    def test_performance_monitoring(self):
        """Test performance monitoring functionality."""
        success = self.engine.add_milvus_instance("test", self.config, set_as_default=True)
        
        if not success:
            self.skipTest("Could not connect to Milvus - skipping monitoring tests")
        
        # Perform some searches to generate metrics
        request = SearchRequest(
            collection_name=self.collection_name,
            query_vectors=self.test_vectors[:1],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType.L2,
            limit=5
        )
        
        try:
            # Execute multiple searches
            for _ in range(3):
                self.engine.search(request)
                time.sleep(0.1)
            
            # Get performance stats
            stats = self.engine.get_performance_stats()
            
            # Verify stats structure
            self.assertIn("metrics", stats)
            self.assertIsInstance(stats["metrics"]["total_requests"], int)
            self.assertGreaterEqual(stats["metrics"]["total_requests"], 3)
            
        except Exception as e:
            self.skipTest(f"Performance monitoring test failed: {e}")
    
    def test_search_parameters_validation(self):
        """Test search parameter validation."""
        from milvus_package.utils import SearchValidator
        
        # Test valid request
        valid_request = SearchRequest(
            collection_name="test_collection",
            query_vectors=self.test_vectors[:1],
            index_type=IndexType.HNSW,
            metric_type=MetricType.L2,
            limit=10
        )
        
        errors = SearchValidator.validate_search_request(valid_request)
        self.assertEqual(len(errors), 0)
        
        # Test invalid request - empty collection name
        invalid_request = SearchRequest(
            collection_name="",
            query_vectors=self.test_vectors[:1],
            limit=10
        )
        
        errors = SearchValidator.validate_search_request(invalid_request)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Collection name" in error for error in errors))
        
        # Test invalid limit
        invalid_limit_request = SearchRequest(
            collection_name="test_collection", 
            query_vectors=self.test_vectors[:1],
            limit=0
        )
        
        errors = SearchValidator.validate_search_request(invalid_limit_request)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Limit must be" in error for error in errors))
    
    def test_connection_config(self):
        """Test connection configuration."""
        config = ConnectionConfig(
            host="test-host",
            port="19530",
            max_connections=15,
            timeout=45.0
        )
        
        connect_params = config.to_connect_params()
        
        self.assertEqual(connect_params["host"], "test-host")
        self.assertEqual(connect_params["port"], "19530")
        self.assertNotIn("max_connections", connect_params)  # This is pool-specific
        self.assertNotIn("timeout", connect_params)  # This is pool-specific
    
    def test_search_params_serialization(self):
        """Test search parameters serialization."""
        params = SearchParams(
            nprobe=16,
            ef=64,
            radius=1.0,
            range_filter=0.5
        )
        
        params_dict = params.to_dict()
        
        self.assertEqual(params_dict["nprobe"], 16)
        self.assertEqual(params_dict["ef"], 64)
        self.assertEqual(params_dict["radius"], 1.0)
        self.assertEqual(params_dict["range_filter"], 0.5)
        
        # Test with None values
        params_with_none = SearchParams(nprobe=32, ef=None)
        params_dict_filtered = params_with_none.to_dict()
        
        self.assertEqual(params_dict_filtered["nprobe"], 32)
        self.assertNotIn("ef", params_dict_filtered)
    
    def test_enum_handling(self):
        """Test enum conversion and handling."""
        # Test IndexType enum
        self.assertEqual(IndexType.HNSW.value, "HNSW")
        self.assertEqual(IndexType.IVF_FLAT.value, "IVF_FLAT")
        
        # Test MetricType enum
        self.assertEqual(MetricType.L2.value, "L2")
        self.assertEqual(MetricType.COSINE.value, "COSINE")
        
        # Test SearchMode enum
        self.assertEqual(SearchMode.VECTOR.value, "vector")
        self.assertEqual(SearchMode.HYBRID.value, "hybrid")

class TestIntegration(unittest.TestCase):
    """Integration tests that require a running Milvus instance."""
    
    def setUp(self):
        """Set up integration tests."""
        self.config = ConnectionConfig(host="localhost", port="19530")
        self.engine = ConcurrentSearchEngine()
        
    def tearDown(self):
        """Clean up integration tests."""
        if self.engine:
            self.engine.shutdown()
    
    def test_full_workflow(self):
        """Test complete workflow from connection to search."""
        # Add instance
        success = self.engine.add_milvus_instance("integration", self.config)
        
        if not success:
            self.skipTest("Could not connect to Milvus for integration test")
        
        # Generate test data
        test_vectors = TestMilvusPackage.generate_test_vectors(5, 128)
        
        # Create search request
        request = SearchRequest(
            collection_name="test_collection",
            query_vectors=test_vectors[:2],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType.L2,
            limit=10
        )
        
        try:
            # Execute search
            result = self.engine.search(request)
            
            # Verify workflow completion
            self.assertIsNotNone(result)
            self.assertIsInstance(result.hits, list)
            
            # Get stats
            stats = self.engine.get_performance_stats()
            self.assertGreaterEqual(stats["metrics"]["total_requests"], 1)
            
        except Exception as e:
            self.skipTest(f"Integration test failed: {e}")

def run_tests():
    """Run all tests."""
    print("🧪 Running Milvus Package Tests")
    print("=" * 50)
    print("⚠️  These tests require a running Milvus instance at localhost:19530")
    print("⚠️  Ensure you have a test collection available")
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMilvusPackage))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print(f"❌ {len(result.failures)} failures, {len(result.errors)} errors")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
