"""
DocAware Metric Type Quick Fix
=============================

This file provides an immediate fix for the DocAware metric type mismatch issue.
Based on error log analysis, all collections are using IP (Inner Product) metric type.

🎯 ISSUE: Collections use IP metric, but searches try COSINE/L2 metrics
🔧 FIX: Override default metric types to use IP
"""

# Based on error log analysis - all collections expect IP metric
DOCAWARE_DEFAULT_METRIC = "IP"

# Collection-specific overrides (if needed)
COLLECTION_METRIC_OVERRIDES = {
    # Add specific overrides here if collections use different metrics
    # "collection_name": "L2",
}

def get_correct_metric_type(collection_name: str = None) -> str:
    """
    Get the correct metric type for DocAware collections
    
    Args:
        collection_name: Optional collection name for specific overrides
        
    Returns:
        Correct metric type string ("IP", "L2", or "COSINE")
    """
    if collection_name and collection_name in COLLECTION_METRIC_OVERRIDES:
        return COLLECTION_METRIC_OVERRIDES[collection_name]
    
    return DOCAWARE_DEFAULT_METRIC

# Quick patch function for existing search methods
def patch_search_params(params: dict, collection_name: str = None) -> dict:
    """
    Patch search parameters to use the correct metric type
    
    Args:
        params: Original search parameters
        collection_name: Collection being searched
        
    Returns:
        Patched parameters with correct metric type
    """
    patched_params = params.copy()
    patched_params["metric_type"] = get_correct_metric_type(collection_name)
    return patched_params

# Updated default configurations for search methods
PATCHED_SEARCH_DEFAULTS = {
    "semantic_search": {
        "index_type": "AUTOINDEX",
        "metric_type": "IP",  # Changed from COSINE to IP
        "search_limit": 5,
        "relevance_threshold": 0.7
    },
    "hybrid_search": {
        "index_type": "AUTOINDEX", 
        "metric_type": "IP",  # Changed from COSINE to IP
        "search_limit": 10,
        "keyword_weight": 0.3,
        "filter_expression": ""
    },
    "contextual_search": {
        "context_window": 3,
        "context_weight": 0.4,
        "search_limit": 8,
        "relevance_threshold": 0.6,
        "metric_type": "IP"  # Added explicit metric type
    },
    "similarity_threshold": {
        "similarity_threshold": 0.8,
        "max_results": 20,
        "index_type": "HNSW",
        "metric_type": "IP"  # Changed from COSINE to IP
    },
    "hierarchical_search": {
        "hierarchy_levels": ["section", "paragraph"],
        "level_weights": '{"section": 0.6, "paragraph": 0.4}',
        "search_limit": 10,
        "preserve_structure": True,
        "metric_type": "IP"  # Added explicit metric type
    },
    "keyword_search": {
        "search_limit": 10,
        "boost_exact_match": True,
        "min_keyword_length": 3,
        "metric_type": "IP"  # Use IP instead of L2
    }
}

def apply_docaware_fix():
    """
    Apply the DocAware metric fix by updating search method defaults
    Call this during application startup or service initialization
    """
    import logging
    logger = logging.getLogger('docaware_fix')
    
    logger.info("🔧 DOCAWARE FIX: Applying metric type corrections")
    logger.info(f"🔧 DOCAWARE FIX: Default metric changed to {DOCAWARE_DEFAULT_METRIC}")
    logger.info("🔧 DOCAWARE FIX: All search methods will now use IP metric by default")
    
    return PATCHED_SEARCH_DEFAULTS

if __name__ == "__main__":
    print("🔧 DocAware Metric Type Quick Fix")
    print("=" * 40)
    print(f"✅ Default metric type: {DOCAWARE_DEFAULT_METRIC}")
    print("✅ This should resolve the 'metric type not match' errors")
    print("")
    print("📝 To apply this fix:")
    print("1. Import this module in your DocAware service")
    print("2. Use get_correct_metric_type() when creating search requests")
    print("3. Or use patch_search_params() to fix existing parameter dictionaries")
    print("")
    print("🎯 Expected result: DocAware searches should now work correctly")
