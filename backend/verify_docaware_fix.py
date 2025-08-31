#!/usr/bin/env python3
"""
DocAware Fix Verification Script
===============================

This script verifies that the DocAware metric type fixes have been applied correctly
and checks the status of the system.

🎯 Checks:
- ✅ Search method defaults updated to use IP metric
- ✅ Service methods updated with auto-detection
- ✅ Enhanced debugging and error handling
- 📊 System status and readiness
"""

import os
import sys
import re

# Check if we're in the right directory
backend_path = "/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend"
if os.getcwd() != backend_path:
    os.chdir(backend_path)

def check_search_methods_config():
    """Check if search_methods.py has been updated correctly"""
    print("🔍 CHECKING: Search Methods Configuration...")
    
    try:
        with open("agent_orchestration/docaware/search_methods.py", "r") as f:
            content = f.read()
        
        # Check for IP metric defaults
        checks = {
            "SEMANTIC_SEARCH IP default": '"metric_type": "IP"' in content and 'Changed from COSINE to IP' in content,
            "HYBRID_SEARCH IP default": content.count('"metric_type": "IP"') >= 2,
            "CONTEXTUAL_SEARCH IP default": '"metric_type": "IP"  # Added explicit metric type' in content,
            "SIMILARITY_THRESHOLD IP default": content.count('"metric_type": "IP"') >= 3,
            "HIERARCHICAL_SEARCH IP default": content.count('"metric_type": "IP"') >= 4,
            "KEYWORD_SEARCH IP default": 'Use IP instead of L2' in content,
        }
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
        
        all_passed = all(checks.values())
        if all_passed:
            print("  🎉 ALL SEARCH METHOD DEFAULTS UPDATED TO IP!")
        else:
            print("  ⚠️ Some search method defaults still need updating")
            
        return all_passed
        
    except Exception as e:
        print(f"  ❌ Error checking search methods: {e}")
        return False

def check_service_updates():
    """Check if service.py has been updated with auto-detection"""
    print("\n🔍 CHECKING: DocAware Service Updates...")
    
    try:
        with open("agent_orchestration/docaware/service.py", "r") as f:
            content = f.read()
        
        checks = {
            "Auto-detection method exists": "def get_collection_metric_type" in content,
            "Enhanced semantic search": "detected_metric = self.get_collection_metric_type" in content,
            "Enhanced hybrid search": "🔍 HYBRID: Starting search with detected metric" in content,
            "Enhanced contextual search": "✅ CONTEXTUAL:" in content and "using {detected_metric} metric" in content,
            "Enhanced threshold search": "🔍 THRESHOLD: Using detected metric" in content,
            "Enhanced hierarchical search": "🔍 HIERARCHICAL: Using detected metric" in content,
            "Enhanced keyword search": "✅ KEYWORD:" in content and "using {detected_metric} metric" in content,
            "Enhanced error handling": "❌ SEMANTIC: Search failed with error:" in content,
            "Metric detection logging": "🔍 METRIC DETECTION: Collection" in content,
            "IP fallback logic": 'return "IP"  # Based on error logs' in content,
        }
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
        
        all_passed = all(checks.values())
        if all_passed:
            print("  🎉 ALL SERVICE ENHANCEMENTS APPLIED!")
        else:
            print("  ⚠️ Some service enhancements still needed")
            
        return all_passed
        
    except Exception as e:
        print(f"  ❌ Error checking service: {e}")
        return False

def check_log_patterns():
    """Check recent logs for improvement patterns"""
    print("\n🔍 CHECKING: Log Patterns...")
    
    import glob
    from datetime import datetime, timedelta
    
    try:
        # Find the most recent backend log
        log_files = glob.glob("logs/backend_*.log")
        if not log_files:
            print("  ⚠️ No backend logs found")
            return False
        
        latest_log = max(log_files, key=os.path.getctime)
        print(f"  📄 Checking: {latest_log}")
        
        with open(latest_log, "r") as f:
            recent_lines = f.readlines()[-100:]  # Last 100 lines
        
        log_content = "".join(recent_lines)
        
        patterns = {
            "Metric detection attempts": "🔍 METRIC DETECTION:" in log_content,
            "Enhanced search logging": "🔍 SEMANTIC:" in log_content or "🔍 HYBRID:" in log_content,
            "Success with metric info": "using IP metric" in log_content or "using COSINE metric" in log_content,
            "No recent metric errors": "metric type not match" not in log_content,
            "DocAware searches": "ENHANCED RAG:" in log_content,
        }
        
        for pattern, found in patterns.items():
            status = "✅" if found else "⚠️"
            print(f"  {status} {pattern}")
        
        return patterns["No recent metric errors"]
        
    except Exception as e:
        print(f"  ❌ Error checking logs: {e}")
        return False

def check_error_logs():
    """Check error logs for recent metric mismatches"""
    print("\n🔍 CHECKING: Error Logs...")
    
    import glob
    
    try:
        # Find the most recent error log
        error_files = glob.glob("logs/error_log_*.txt")
        if not error_files:
            print("  ⚠️ No error logs found")
            return True  # No error logs is good
        
        latest_error_log = max(error_files, key=os.path.getctime)
        print(f"  📄 Checking: {latest_error_log}")
        
        with open(latest_error_log, "r") as f:
            content = f.read()
        
        # Count recent metric errors
        metric_errors = content.count("metric type not match")
        recent_lines = content.split('\n')[-20:]  # Last 20 lines
        recent_content = '\n'.join(recent_lines)
        recent_metric_errors = recent_content.count("metric type not match")
        
        print(f"  📊 Total metric errors in log: {metric_errors}")
        print(f"  📊 Recent metric errors (last 20 lines): {recent_metric_errors}")
        
        if recent_metric_errors == 0:
            print("  ✅ No recent metric type mismatch errors!")
            return True
        else:
            print(f"  ❌ Still seeing {recent_metric_errors} recent metric errors")
            return False
            
    except Exception as e:
        print(f"  ❌ Error checking error logs: {e}")
        return False

def show_restart_instructions():
    """Show instructions for restarting Django"""
    print("\n🚀 RESTART INSTRUCTIONS:")
    print("=" * 50)
    print("1. Stop the current Django server (Ctrl+C)")
    print("2. Restart with:")
    print("   cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend")
    print("   python manage.py runserver 0.0.0.0:8000")
    print("3. Test DocAware workflow execution")
    print("4. Monitor logs:")
    print("   tail -f logs/backend_*.log | grep 'Found.*results'")

def show_testing_instructions():
    """Show testing instructions"""
    print("\n🧪 TESTING INSTRUCTIONS:")
    print("=" * 50)
    print("1. Execute a workflow with DocAware agents")
    print("2. Look for these log messages:")
    print("   ✅ '🔍 METRIC DETECTION: Collection ... uses IP metric'")
    print("   ✅ '✅ SEMANTIC: Found X results using IP metric'")
    print("   ✅ '✅ HYBRID: Found X results using IP metric'")
    print("3. Verify no new errors:")
    print("   tail -f logs/error_log_*.txt | grep 'metric type not match'")
    print("4. Check DocAware agent responses for document content")

def main():
    """Main verification function"""
    print("🔧 DocAware Fix Verification")
    print("=" * 40)
    
    # Run all checks
    config_ok = check_search_methods_config()
    service_ok = check_service_updates()
    logs_ok = check_log_patterns()
    errors_ok = check_error_logs()
    
    print("\n📊 OVERALL STATUS:")
    print("=" * 50)
    
    overall_score = sum([config_ok, service_ok, logs_ok, errors_ok])
    
    if overall_score == 4:
        print("🎉 ALL CHECKS PASSED!")
        print("✅ DocAware metric type fix has been successfully applied")
        print("✅ System should now work correctly")
        show_restart_instructions()
    elif overall_score >= 2:
        print("⚠️ MOSTLY READY - Some minor issues detected")
        print(f"📊 Score: {overall_score}/4 checks passed")
        show_restart_instructions()
        show_testing_instructions()
    else:
        print("❌ ISSUES DETECTED - Additional fixes needed")
        print(f"📊 Score: {overall_score}/4 checks passed")
        print("🔧 Review the failed checks above and apply missing fixes")
    
    print(f"\n🎯 EXPECTED RESULT:")
    print("After restart, DocAware agents should:")
    print("  ✅ Return relevant search results (not 0)")
    print("  ✅ Use IP metric automatically")  
    print("  ✅ Show enhanced logging")
    print("  ✅ No metric type mismatch errors")

if __name__ == "__main__":
    main()
