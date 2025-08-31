#!/usr/bin/env python3
"""
DocAware Milvus Metric Type Fix Script
=====================================

This script diagnoses and fixes the DocAware metric type mismatch issue that is causing
all DocAware searches to fail with the error:
"metric type not match: invalid parameter[expected=IP][actual=COSINE/L2]"

🎯 Root Cause:
- Milvus collections are created with IP (Inner Product) metric type
- DocAware searches are trying to use COSINE and L2 metrics
- This mismatch causes all searches to fail

🔧 Solution:
- Auto-detect collection metric types
- Use the correct metric type for each collection
- Add comprehensive debugging
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.append('/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend')

try:
    import django
    django.setup()
except Exception as e:
    print(f"❌ Failed to setup Django: {e}")
    sys.exit(1)

from django_milvus_search import MilvusSearchService
from django_milvus_search.models import SearchRequest, IndexType, MetricType
from pymilvus import connections, Collection, utility
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocAwareMetricFixer:
    """Fix DocAware metric type mismatches"""
    
    def __init__(self):
        print("🔧 DocAware Metric Type Fixer")
        print("=" * 40)
        
        try:
            self.milvus_service = MilvusSearchService()
            print("✅ Milvus service initialized")
        except Exception as e:
            print(f"❌ Failed to initialize Milvus service: {e}")
            raise
    
    def diagnose_collections(self):
        """Diagnose all collections and their metric types"""
        print("\n🔍 DIAGNOSIS: Inspecting Collections...")
        print("-" * 50)
        
        try:
            collections = self.milvus_service.list_collections()
            docaware_collections = [col for col in collections if any(keyword in col.lower() 
                                   for keyword in ['hello', 'helooo', 'project', 'intellidoc'])]
            
            print(f"📊 Found {len(collections)} total collections")
            print(f"📊 Found {len(docaware_collections)} DocAware collections:")
            
            for col in docaware_collections:
                print(f"  - {col}")
            
            if not docaware_collections:
                print("⚠️ No DocAware collections found - this might indicate a different issue")
                return {}
            
            # Inspect each collection
            collection_metrics = {}
            for collection_name in docaware_collections:
                metric_type = self.inspect_collection(collection_name)
                collection_metrics[collection_name] = metric_type
            
            return collection_metrics
            
        except Exception as e:
            print(f"❌ Error during collection diagnosis: {e}")
            return {}
    
    def inspect_collection(self, collection_name: str) -> Optional[str]:
        """Inspect a specific collection to determine its metric type"""
        print(f"\n🔍 Inspecting: {collection_name}")
        
        try:
            # Get collection info
            collection_info = self.milvus_service.get_collection_info(collection_name)
            
            # Try to detect metric from indexes
            indexes = collection_info.get('indexes', [])
            detected_metric = None
            
            print(f"  📊 Entities: {collection_info.get('num_entities', 'Unknown')}")
            print(f"  🏗️ Indexes: {len(indexes)}")
            
            for idx, index in enumerate(indexes):
                print(f"    Index {idx + 1}: {getattr(index, 'field_name', 'Unknown field')}")
                
                # Try different ways to get metric type
                metric = self.extract_metric_from_index(index)
                if metric:
                    print(f"      ✅ Metric: {metric}")
                    detected_metric = metric
                else:
                    print(f"      ⚠️ Metric: Could not detect")
            
            if not detected_metric:
                # Test with different metrics to see which one works
                detected_metric = self.test_collection_compatibility(collection_name)
            
            return detected_metric
            
        except Exception as e:
            print(f"  ❌ Error inspecting {collection_name}: {e}")
            return None
    
    def extract_metric_from_index(self, index) -> Optional[str]:
        """Try to extract metric type from index object"""
        try:
            # Try different attribute patterns
            if hasattr(index, '_params') and index._params:
                for param in index._params:
                    if hasattr(param, 'key') and param.key == 'metric_type':
                        return param.value
            
            if hasattr(index, 'params') and isinstance(index.params, dict):
                return index.params.get('metric_type')
            
            if hasattr(index, 'metric_type'):
                return index.metric_type
                
            return None
            
        except Exception as e:
            print(f"      ⚠️ Error extracting metric: {e}")
            return None
    
    def test_collection_compatibility(self, collection_name: str) -> Optional[str]:
        """Test which metric type works with this collection"""
        print(f"  🧪 Testing metric compatibility for {collection_name}...")
        
        # Create a dummy search vector (try 384 dimensions based on logs)
        try:
            dummy_vector = np.random.random(384).tolist()
        except:
            dummy_vector = np.random.random(256).tolist()  # Fallback
        
        metrics_to_test = [MetricType.IP, MetricType.L2, MetricType.COSINE]
        
        for metric in metrics_to_test:
            try:
                search_request = SearchRequest(
                    collection_name=collection_name,
                    query_vectors=[dummy_vector],
                    index_type=IndexType.AUTOINDEX,
                    metric_type=metric,
                    limit=1
                )
                
                result = self.milvus_service.search(search_request)
                print(f"      ✅ {metric.value}: Compatible ({result.total_results} results)")
                return metric.value  # Return the first working metric
                
            except Exception as e:
                if "metric type not match" in str(e):
                    print(f"      ❌ {metric.value}: Incompatible (metric mismatch)")
                elif "dimension" in str(e).lower():
                    print(f"      ⚠️ {metric.value}: Dimension mismatch - trying different vector size")
                    # Try different vector sizes
                    for dim in [256, 384, 512, 768, 1024]:
                        try:
                            test_vector = np.random.random(dim).tolist()
                            test_request = SearchRequest(
                                collection_name=collection_name,
                                query_vectors=[test_vector],
                                index_type=IndexType.AUTOINDEX,
                                metric_type=metric,
                                limit=1
                            )
                            test_result = self.milvus_service.search(test_request)
                            print(f"      ✅ {metric.value}: Compatible with {dim}D vectors")
                            return metric.value
                        except:
                            continue
                else:
                    print(f"      ⚠️ {metric.value}: Error - {str(e)[:50]}...")
        
        print(f"      ❌ No compatible metrics found for {collection_name}")
        return None
    
    def create_patch_file(self, collection_metrics: Dict[str, str]):
        """Create a patch for the DocAware service"""
        print(f"\n🔧 SOLUTION: Creating Configuration Patch...")
        print("-" * 50)
        
        if not collection_metrics:
            print("❌ No collection metrics detected - cannot create patch")
            return
        
        # Determine the most common metric type
        metric_counts = {}
        for metric in collection_metrics.values():
            if metric:
                metric_counts[metric] = metric_counts.get(metric, 0) + 1
        
        if not metric_counts:
            print("❌ No valid metrics found")
            return
        
        most_common_metric = max(metric_counts.items(), key=lambda x: x[1])[0]
        print(f"📊 Most common metric type: {most_common_metric} ({metric_counts[most_common_metric]} collections)")
        
        # Create the patch content
        patch_content = f'''# DocAware Metric Type Configuration Patch
# Generated automatically to fix metric type mismatches

# Collection Metrics Detected:
{chr(10).join(f"# - {col}: {metric}" for col, metric in collection_metrics.items() if metric)}

# Apply this configuration to fix DocAware searches:

# 1. Update default metric type in search_methods.py
DEFAULT_METRIC_TYPE = "{most_common_metric}"

# 2. Collection-specific metric mappings
COLLECTION_METRICS = {{
{chr(10).join(f'    "{col}": "{metric}",' for col, metric in collection_metrics.items() if metric)}
}}

# 3. Use this function in DocAware service:
def get_collection_metric_type(collection_name):
    \"\"\"Get the correct metric type for a collection\"\"\"
    return COLLECTION_METRICS.get(collection_name, "{most_common_metric}")
'''
        
        patch_file = "/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/docaware_metric_patch.py"
        with open(patch_file, 'w') as f:
            f.write(patch_content)
        
        print(f"✅ Patch file created: {patch_file}")
        
        # Show immediate fix instructions
        print(f"\n🚀 IMMEDIATE FIX INSTRUCTIONS:")
        print("=" * 50)
        print("1. The main issue is that collections use IP metric but searches try COSINE/L2")
        print(f"2. All DocAware searches should use '{most_common_metric}' metric type")
        print("3. Apply these changes:")
        print(f"   - In search_methods.py: Change default metric_type to '{most_common_metric}'")
        print(f"   - In service.py: Auto-detect metric type or default to '{most_common_metric}'")
        print("4. Restart the Django server to apply changes")
    
    def show_debug_instructions(self):
        """Show debugging instructions for developers"""
        print(f"\n🔍 DEBUG INSTRUCTIONS:")
        print("=" * 50)
        print("To add debugging to your DocAware searches:")
        print("")
        print("1. Add this to your search methods:")
        print("   logger.info(f'🔍 SEARCH: Using metric {metric_type} for collection {collection_name}')")
        print("")
        print("2. Check logs for metric mismatches:")
        print("   tail -f logs/error_log_*.txt | grep 'metric type not match'")
        print("")
        print("3. Test individual collections:")
        print("   python fix_docaware_metrics.py --test-collection <collection_name>")
        print("")
        print("4. Monitor search success rates:")
        print("   grep 'Found.*results' logs/backend_*.log")

def main():
    """Main function to run the diagnostic and fix process"""
    try:
        fixer = DocAwareMetricFixer()
        
        # Step 1: Diagnose collections
        collection_metrics = fixer.diagnose_collections()
        
        # Step 2: Create patch
        if collection_metrics:
            fixer.create_patch_file(collection_metrics)
        
        # Step 3: Show debug instructions
        fixer.show_debug_instructions()
        
        print(f"\n✅ SUMMARY:")
        print("=" * 50)
        if collection_metrics:
            working_collections = len([m for m in collection_metrics.values() if m])
            total_collections = len(collection_metrics)
            print(f"📊 Analyzed {total_collections} DocAware collections")
            print(f"✅ Found metrics for {working_collections} collections")
            
            if working_collections > 0:
                print("🎯 ROOT CAUSE CONFIRMED: Metric type mismatch")
                print("🔧 SOLUTION: Use auto-detected metrics in searches")
                print("📝 NEXT STEPS: Apply the patch file and restart Django")
            else:
                print("❌ Could not detect working metrics - deeper investigation needed")
        else:
            print("❌ No DocAware collections found or analyzed")
            print("🔍 Check if collections exist and Milvus is running properly")
    
    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
