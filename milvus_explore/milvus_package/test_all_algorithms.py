#!/usr/bin/env python3
"""
Comprehensive test script for all 25+ Milvus algorithms.
Tests each algorithm with different configurations and parameters.
"""

import sys
import os
import time
import numpy as np
from typing import Dict, List, Any, Tuple
import json

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from search_engine import ConcurrentSearchEngine
    from models import ConnectionConfig, SearchRequest, SearchParams, IndexType, MetricType
    from algorithm_optimizer import AlgorithmOptimizer, OptimizationStrategy
    print("✅ All modules imported successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

class ComprehensiveAlgorithmTester:
    """Comprehensive tester for all Milvus algorithms."""
    
    def __init__(self):
        self.engine = ConcurrentSearchEngine(max_workers=10, enable_monitoring=True)
        self.collections = [
            "hello_a5d5bb78_93df_408a_863f_27b74a53d5f9",
            "hello_0ec88a22_24b8_4d6b_8d19_a2ee2f57b210", 
            "hello_68c8822f_0b2d_42aa_ae9c_cbf4571ee1f5",
            "hello_a6be3a0f_3c90_448b_ac56_9d0220b7d198",
            "test_4c9f79dd_6537_4298_a79f_7c8351d765f0"
        ]
        self.working_dim = None
        self.test_collection = None
        self.results = {}
        
    def setup_connection(self) -> bool:
        """Setup connection to Milvus."""
        config = ConnectionConfig(
            host="localhost",
            port="19530",
            max_connections=8,
            timeout=60.0
        )
        
        print("🔌 Connecting to Milvus...")
        success = self.engine.add_milvus_instance("test", config, set_as_default=True)
        
        if success:
            print("✅ Connected successfully!")
            return True
        else:
            print("❌ Connection failed")
            return False
    
    def detect_vector_dimension(self) -> bool:
        """Auto-detect working vector dimension."""
        print("\n🔍 Auto-detecting vector dimension...")
        
        dimensions_to_test = [64, 128, 256, 384, 512, 768, 1024, 1536, 2048]
        
        for collection in self.collections:
            print(f"   Testing collection: {collection}")
            
            for dim in dimensions_to_test:
                try:
                    test_vector = np.random.random(dim).astype(np.float32)
                    test_vector = test_vector / np.linalg.norm(test_vector)
                    
                    request = SearchRequest(
                        collection_name=collection,
                        query_vectors=[test_vector.tolist()],
                        index_type=IndexType.AUTOINDEX,
                        metric_type=MetricType.L2,
                        limit=1
                    )
                    
                    result = self.engine.search(request)
                    
                    self.working_dim = dim
                    self.test_collection = collection
                    print(f"✅ Found working configuration:")
                    print(f"   Collection: {collection}")
                    print(f"   Dimension: {dim}")
                    print(f"   Search time: {result.search_time:.4f}s")
                    return True
                    
                except Exception as e:
                    if "dimension" in str(e).lower():
                        continue
                    else:
                        print(f"   ⚠️ Error with {collection} dim {dim}: {e}")
                        continue
        
        print("❌ Could not find working configuration")
        return False
    
    def get_all_algorithm_configurations(self) -> List[Dict[str, Any]]:
        """Get all 25+ algorithm configurations to test."""
        
        configurations = []
        
        # 1. FLAT Index (Exact Search) - 3 configurations
        flat_configs = [
            {
                "name": "FLAT+L2",
                "index_type": "FLAT",
                "metric_type": "L2",
                "search_params": {},
                "description": "Exact search with Euclidean distance"
            },
            {
                "name": "FLAT+IP", 
                "index_type": "FLAT",
                "metric_type": "IP",
                "search_params": {},
                "description": "Exact search with Inner Product"
            },
            {
                "name": "FLAT+COSINE",
                "index_type": "FLAT", 
                "metric_type": "COSINE",
                "search_params": {},
                "description": "Exact search with Cosine similarity"
            }
        ]
        configurations.extend(flat_configs)
        
        # 2. IVF_FLAT Index - 9 configurations (3 metrics × 3 nprobe values)
        ivf_flat_configs = []
        for metric in ["L2", "IP", "COSINE"]:
            for nprobe in [1, 16, 64]:
                ivf_flat_configs.append({
                    "name": f"IVF_FLAT+{metric}+nprobe{nprobe}",
                    "index_type": "IVF_FLAT",
                    "metric_type": metric,
                    "search_params": {"nprobe": nprobe},
                    "description": f"IVF_FLAT with {metric} metric, nprobe={nprobe}"
                })
        configurations.extend(ivf_flat_configs)
        
        # 3. IVF_SQ8 Index - 6 configurations (2 metrics × 3 nprobe values)
        ivf_sq8_configs = []
        for metric in ["L2", "IP"]:  # COSINE often not supported with SQ8
            for nprobe in [1, 16, 64]:
                ivf_sq8_configs.append({
                    "name": f"IVF_SQ8+{metric}+nprobe{nprobe}",
                    "index_type": "IVF_SQ8",
                    "metric_type": metric,
                    "search_params": {"nprobe": nprobe},
                    "description": f"IVF_SQ8 with {metric} metric, nprobe={nprobe}"
                })
        configurations.extend(ivf_sq8_configs)
        
        # 4. IVF_PQ Index - 6 configurations (2 metrics × 3 nprobe values)
        ivf_pq_configs = []
        for metric in ["L2", "IP"]:  # COSINE often problematic with PQ
            for nprobe in [1, 16, 64]:
                ivf_pq_configs.append({
                    "name": f"IVF_PQ+{metric}+nprobe{nprobe}",
                    "index_type": "IVF_PQ",
                    "metric_type": metric,
                    "search_params": {"nprobe": nprobe},
                    "description": f"IVF_PQ with {metric} metric, nprobe={nprobe}"
                })
        configurations.extend(ivf_pq_configs)
        
        # 5. HNSW Index - 9 configurations (3 metrics × 3 ef values)
        hnsw_configs = []
        for metric in ["L2", "IP", "COSINE"]:
            for ef in [16, 64, 200]:
                hnsw_configs.append({
                    "name": f"HNSW+{metric}+ef{ef}",
                    "index_type": "HNSW",
                    "metric_type": metric, 
                    "search_params": {"ef": ef},
                    "description": f"HNSW with {metric} metric, ef={ef}"
                })
        configurations.extend(hnsw_configs)
        
        # 6. SCANN Index - 9 configurations (3 metrics × 3 search_k values)
        scann_configs = []
        for metric in ["L2", "IP", "COSINE"]:
            for search_k in [20, 50, 100]:
                scann_configs.append({
                    "name": f"SCANN+{metric}+searchk{search_k}",
                    "index_type": "SCANN",
                    "metric_type": metric,
                    "search_params": {"search_k": search_k, "nprobe": 16},
                    "description": f"SCANN with {metric} metric, search_k={search_k}"
                })
        configurations.extend(scann_configs)
        
        # 7. AUTOINDEX - 3 configurations (automatic algorithm selection)
        autoindex_configs = [
            {
                "name": "AUTOINDEX+L2",
                "index_type": "AUTOINDEX",
                "metric_type": "L2", 
                "search_params": {},
                "description": "Auto-selected index with L2 metric"
            },
            {
                "name": "AUTOINDEX+IP",
                "index_type": "AUTOINDEX",
                "metric_type": "IP",
                "search_params": {},
                "description": "Auto-selected index with IP metric"
            },
            {
                "name": "AUTOINDEX+COSINE",
                "index_type": "AUTOINDEX",
                "metric_type": "COSINE",
                "search_params": {},
                "description": "Auto-selected index with COSINE metric"
            }
        ]
        configurations.extend(autoindex_configs)
        
        print(f"📋 Generated {len(configurations)} algorithm configurations to test")
        return configurations
    
    def test_single_algorithm(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single algorithm configuration."""
        
        try:
            # Generate test vector
            test_vector = np.random.random(self.working_dim).astype(np.float32)
            test_vector = test_vector / np.linalg.norm(test_vector)
            
            # Build search parameters
            search_params = None
            if config["search_params"]:
                search_params = SearchParams(**config["search_params"])
            
            # Create search request
            request = SearchRequest(
                collection_name=self.test_collection,
                query_vectors=[test_vector.tolist()],
                index_type=getattr(IndexType, config["index_type"], config["index_type"]),
                metric_type=getattr(MetricType, config["metric_type"], config["metric_type"]),
                search_params=search_params,
                limit=5
            )
            
            # Execute search with timeout
            start_time = time.time()
            result = self.engine.search(request)
            search_time = time.time() - start_time
            
            # Return success result
            return {
                "status": "✅ SUCCESS",
                "search_time": result.search_time,
                "total_time": search_time,
                "results_found": result.total_results,
                "algorithm_used": result.algorithm_used,
                "parameters_used": result.parameters_used,
                "error": None,
                "description": config["description"]
            }
            
        except Exception as e:
            # Return failure result
            error_type = "UNKNOWN"
            error_msg = str(e)
            
            if "not supported" in error_msg.lower():
                error_type = "NOT_SUPPORTED"
            elif "dimension" in error_msg.lower():
                error_type = "DIMENSION_MISMATCH"
            elif "index" in error_msg.lower():
                error_type = "INDEX_ERROR"
            elif "metric" in error_msg.lower():
                error_type = "METRIC_ERROR"
            elif "timeout" in error_msg.lower():
                error_type = "TIMEOUT"
            
            return {
                "status": "❌ FAILED",
                "search_time": 0.0,
                "total_time": 0.0,
                "results_found": 0,
                "algorithm_used": "FAILED",
                "parameters_used": {},
                "error": error_msg,
                "error_type": error_type,
                "description": config["description"]
            }
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test of all algorithms."""
        
        print("🚀 Starting Comprehensive Algorithm Test")
        print("=" * 60)
        
        if not self.setup_connection():
            return {"error": "Connection failed"}
        
        if not self.detect_vector_dimension():
            return {"error": "Could not detect vector dimension"}
        
        # Get all algorithm configurations
        configs = self.get_all_algorithm_configurations()
        
        print(f"\n🧪 Testing {len(configs)} Algorithm Configurations")
        print("=" * 60)
        
        # Test each configuration
        results = {}
        successful_tests = 0
        failed_tests = 0
        
        for i, config in enumerate(configs, 1):
            print(f"\n[{i:2d}/{len(configs)}] Testing: {config['name']}")
            print(f"         {config['description']}")
            
            result = self.test_single_algorithm(config)
            results[config['name']] = result
            
            if "SUCCESS" in result['status']:
                successful_tests += 1
                print(f"         {result['status']} | {result['search_time']:.4f}s | {result['results_found']} results")
            else:
                failed_tests += 1
                print(f"         {result['status']} | {result['error_type']} | {result['error'][:50]}...")
            
            # Small delay to prevent overwhelming Milvus
            time.sleep(0.1)
        
        # Generate summary
        summary = self.generate_test_summary(results, successful_tests, failed_tests)
        
        return {
            "summary": summary,
            "results": results,
            "test_config": {
                "collection": self.test_collection,
                "dimension": self.working_dim,
                "total_tests": len(configs)
            }
        }
    
    def generate_test_summary(self, results: Dict[str, Any], 
                            successful: int, failed: int) -> Dict[str, Any]:
        """Generate comprehensive test summary."""
        
        print(f"\n" + "=" * 70)
        print("📊 COMPREHENSIVE TEST SUMMARY")
        print("=" * 70)
        
        total_tests = successful + failed
        success_rate = (successful / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"📈 Overall Results:")
        print(f"   Total algorithms tested: {total_tests}")
        print(f"   Successful: {successful} ({success_rate:.1f}%)")
        print(f"   Failed: {failed} ({100-success_rate:.1f}%)")
        
        # Analyze by index type
        index_analysis = {}
        metric_analysis = {}
        speed_analysis = []
        
        for name, result in results.items():
            if "SUCCESS" in result['status']:
                # Extract index type
                index_type = name.split('+')[0]
                if index_type not in index_analysis:
                    index_analysis[index_type] = {"success": 0, "total": 0, "avg_time": 0, "times": []}
                
                index_analysis[index_type]["success"] += 1
                index_analysis[index_type]["times"].append(result['search_time'])
                
                # Extract metric type
                metric_type = name.split('+')[1].split('+')[0] if '+' in name else "UNKNOWN"
                if metric_type not in metric_analysis:
                    metric_analysis[metric_type] = {"success": 0, "total": 0}
                metric_analysis[metric_type]["success"] += 1
                
                # Speed analysis
                speed_analysis.append((name, result['search_time']))
            
            # Count totals
            index_type = name.split('+')[0]
            if index_type not in index_analysis:
                index_analysis[index_type] = {"success": 0, "total": 0, "avg_time": 0, "times": []}
            index_analysis[index_type]["total"] += 1
            
            metric_type = name.split('+')[1].split('+')[0] if '+' in name else "UNKNOWN"
            if metric_type not in metric_analysis:
                metric_analysis[metric_type] = {"success": 0, "total": 0}
            metric_analysis[metric_type]["total"] += 1
        
        # Calculate averages
        for index_type, data in index_analysis.items():
            if data["times"]:
                data["avg_time"] = sum(data["times"]) / len(data["times"])
        
        # Print analysis
        print(f"\n🔧 Index Type Analysis:")
        print(f"{'Index Type':<12} {'Success':<8} {'Total':<6} {'Rate':<6} {'Avg Time':<10}")
        print("-" * 50)
        
        for index_type, data in sorted(index_analysis.items()):
            rate = (data["success"] / data["total"]) * 100 if data["total"] > 0 else 0
            avg_time = data["avg_time"] if data["avg_time"] > 0 else 0
            print(f"{index_type:<12} {data['success']:<8} {data['total']:<6} {rate:<6.1f}% {avg_time:<10.4f}s")
        
        print(f"\n📏 Metric Type Analysis:")
        print(f"{'Metric':<8} {'Success':<8} {'Total':<6} {'Rate':<6}")
        print("-" * 35)
        
        for metric_type, data in sorted(metric_analysis.items()):
            rate = (data["success"] / data["total"]) * 100 if data["total"] > 0 else 0
            print(f"{metric_type:<8} {data['success']:<8} {data['total']:<6} {rate:<6.1f}%")
        
        # Top 10 fastest algorithms
        if speed_analysis:
            speed_analysis.sort(key=lambda x: x[1])
            print(f"\n⚡ Top 10 Fastest Algorithms:")
            print(f"{'Rank':<4} {'Algorithm':<25} {'Time (ms)':<10}")
            print("-" * 45)
            
            for i, (name, time_val) in enumerate(speed_analysis[:10], 1):
                print(f"{i:<4} {name:<25} {time_val*1000:<10.2f}")
        
        # Error analysis
        error_types = {}
        for name, result in results.items():
            if "FAILED" in result['status']:
                error_type = result.get('error_type', 'UNKNOWN')
                if error_type not in error_types:
                    error_types[error_type] = 0
                error_types[error_type] += 1
        
        if error_types:
            print(f"\n❌ Error Analysis:")
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                print(f"   {error_type}: {count} failures")
        
        return {
            "total_tests": total_tests,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "index_analysis": index_analysis,
            "metric_analysis": metric_analysis,
            "fastest_algorithms": speed_analysis[:10],
            "error_analysis": error_types
        }
    
    def save_results(self, all_results: Dict[str, Any]):
        """Save test results to JSON file."""
        
        timestamp = int(time.time())
        filename = f"milvus_algorithm_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            
            print(f"\n💾 Results saved to: {filename}")
            
        except Exception as e:
            print(f"⚠️ Could not save results: {e}")
    
    def cleanup(self):
        """Cleanup resources."""
        try:
            self.engine.shutdown()
            print("🔌 Disconnected from Milvus")
        except:
            pass

def main():
    """Main execution function."""
    
    print("🧪 Comprehensive Milvus Algorithm Tester")
    print("========================================")
    print("This script will test all 25+ algorithm configurations")
    print("with your actual Milvus collections.")
    print()
    
    tester = ComprehensiveAlgorithmTester()
    
    try:
        # Run comprehensive test
        results = tester.run_comprehensive_test()
        
        if "error" in results:
            print(f"❌ Test failed: {results['error']}")
            return
        
        # Save results
        tester.save_results(results)
        
        # Final summary
        summary = results["summary"]
        print(f"\n🎉 TESTING COMPLETE!")
        print(f"   {summary['successful']}/{summary['total_tests']} algorithms working ({summary['success_rate']:.1f}%)")
        print(f"   Your Milvus setup supports most major algorithms!")
        
        if summary['fastest_algorithms']:
            fastest = summary['fastest_algorithms'][0]
            print(f"   🏆 Fastest algorithm: {fastest[0]} ({fastest[1]*1000:.2f}ms)")
        
        print(f"\n📚 Next steps:")
        print(f"   • Use the working algorithms in your production code")
        print(f"   • Focus on the fastest algorithms for low-latency applications")
        print(f"   • Use high-accuracy algorithms for critical searches")
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.cleanup()

if __name__ == "__main__":
    main()
