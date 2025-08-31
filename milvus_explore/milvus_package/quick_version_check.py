#!/usr/bin/env python3
"""
Quick version check for both PyMilvus and Milvus server.
"""

def quick_version_check():
    print("🔍 Quick Milvus Version Check")
    print("=" * 35)
    
    # Check PyMilvus
    try:
        import pymilvus
        print(f"✅ PyMilvus: v{pymilvus.__version__}")
        
        # Try server connection
        from pymilvus import connections, utility
        connections.connect(host="localhost", port="19530", alias="quick_check")
        server_version = utility.get_server_version(using="quick_check")
        print(f"✅ Milvus Server: v{server_version}")
        connections.disconnect("quick_check")
        
        # Check Docker Compose config
        compose_file = "/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/docker-compose-milvus.yml"
        try:
            with open(compose_file, 'r') as f:
                content = f.read()
            
            import re
            match = re.search(r'milvusdb/milvus:v([0-9.]+)', content)
            if match:
                compose_version = match.group(1)
                print(f"📄 Docker Compose Config: v{compose_version}")
                
                # Version comparison
                print(f"\n📊 Version Analysis:")
                if compose_version < "2.5.0":
                    print("   🚨 CRITICAL: Docker config is severely outdated!")
                    print("   📝 Recommended: Update to v2.5.12+")
                    
                if pymilvus.__version__ < "2.5.0":
                    print("   ⚠️ PyMilvus is outdated")
                    print("   📦 Run: pip install --upgrade pymilvus")
                    
                if server_version < "2.5.0":
                    print("   🔄 Server needs updating")
                else:
                    print("   ✅ Versions look good!")
                    
        except Exception as e:
            print(f"⚠️ Could not read Docker Compose file: {e}")
            
    except ImportError:
        print("❌ PyMilvus not installed")
    except Exception as e:
        print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    quick_version_check()
