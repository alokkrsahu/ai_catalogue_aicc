#!/usr/bin/env python3
"""
Check both Docker Milvus and PyMilvus versions in your system.
"""

import subprocess
import sys
import os

def check_pymilvus_version():
    """Check PyMilvus version and server connection."""
    print("🐍 PyMilvus Version Check")
    print("=" * 30)
    
    try:
        import pymilvus
        print(f"✅ PyMilvus installed: v{pymilvus.__version__}")
        
        # Try to connect and get server version
        from pymilvus import connections, utility
        
        print("🔌 Connecting to Milvus server...")
        connections.connect(host="localhost", port="19530", alias="version_check")
        
        server_version = utility.get_server_version(using="version_check")
        print(f"✅ Milvus Server Version: {server_version}")
        
        # Get basic info
        collections = utility.list_collections(using="version_check")
        print(f"📚 Collections found: {len(collections)}")
        if collections:
            print(f"   Collection names: {', '.join(collections[:3])}{'...' if len(collections) > 3 else ''}")
        
        connections.disconnect("version_check")
        
        return True, pymilvus.__version__, server_version
        
    except ImportError:
        print("❌ PyMilvus not installed")
        return False, None, None
    except Exception as e:
        print(f"⚠️ Connection failed: {e}")
        try:
            import pymilvus
            return False, pymilvus.__version__, None
        except:
            return False, None, None

def check_docker_version():
    """Check Docker Milvus version."""
    print("\n📦 Docker Milvus Version Check")
    print("=" * 35)
    
    try:
        # Check if Docker is running
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Docker is not installed or not running")
            return None
        
        print(f"✅ Docker installed: {result.stdout.strip()}")
        
        # Check running Milvus containers
        result = subprocess.run(['docker', 'ps', '--filter', 'name=milvus'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Has containers beyond header
                print(f"🔄 Running Milvus containers:")
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            container_name = parts[-1]
                            image = parts[1]
                            status = parts[4:7]  # Status info
                            print(f"   📊 {container_name}")
                            print(f"      Image: {image}")
                            print(f"      Status: {' '.join(status)}")
            else:
                print("⚠️ No Milvus containers currently running")
        
        # Check Milvus Docker images
        result = subprocess.run(['docker', 'images', '--filter', 'reference=milvusdb/milvus'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                print(f"\n🖼️ Milvus Docker images:")
                docker_versions = []
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            repo = parts[0]
                            tag = parts[1]
                            size = parts[-1]
                            created = parts[-2]
                            print(f"   📦 {repo}:{tag}")
                            print(f"      Size: {size}, Created: {created}")
                            docker_versions.append(tag)
                
                return docker_versions
            else:
                print("❌ No Milvus Docker images found")
                return []
        
        return []
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker command failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Error checking Docker: {e}")
        return None

def check_docker_compose_config():
    """Check the Docker Compose configuration file."""
    print("\n⚙️ Docker Compose Configuration")
    print("=" * 38)
    
    compose_file = "/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/docker-compose-milvus.yml"
    
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
            
        # Extract Milvus version from compose file
        import re
        milvus_match = re.search(r'milvusdb/milvus:v([0-9.]+)', content)
        etcd_match = re.search(r'etcd:v([0-9.]+)', content)
        minio_match = re.search(r'minio:RELEASE\.([0-9T-]+Z)', content)
        
        if milvus_match:
            compose_milvus_version = milvus_match.group(1)
            print(f"📄 Docker Compose Milvus version: v{compose_milvus_version}")
        else:
            print("⚠️ Could not find Milvus version in docker-compose.yml")
            
        if etcd_match:
            print(f"📄 Docker Compose etcd version: v{etcd_match.group(1)}")
            
        if minio_match:
            print(f"📄 Docker Compose MinIO version: {minio_match.group(1)}")
            
        return compose_milvus_version if milvus_match else None
        
    except FileNotFoundError:
        print(f"❌ Docker Compose file not found: {compose_file}")
        return None
    except Exception as e:
        print(f"❌ Error reading Docker Compose file: {e}")
        return None

def compare_versions(pymilvus_version, server_version, docker_versions, compose_version):
    """Compare all versions and provide recommendations."""
    print("\n📊 Version Comparison & Analysis")
    print("=" * 42)
    
    # Latest known versions (as of January 2025)
    latest_versions = {
        "milvus": "2.5.12",
        "pymilvus": "2.5.10"
    }
    
    print("🔍 Current Status:")
    
    if pymilvus_version:
        print(f"   PyMilvus: v{pymilvus_version}")
        if pymilvus_version < latest_versions["pymilvus"]:
            print("      ❌ OUTDATED")
        else:
            print("      ✅ UP TO DATE")
    
    if server_version:
        print(f"   Milvus Server: v{server_version}")
        if server_version < latest_versions["milvus"]:
            print("      ❌ OUTDATED")
        else:
            print("      ✅ UP TO DATE")
    
    if compose_version:
        print(f"   Docker Compose Config: v{compose_version}")
        if compose_version < latest_versions["milvus"]:
            print("      ❌ CRITICALLY OUTDATED")
        else:
            print("      ✅ UP TO DATE")
    
    if docker_versions:
        print(f"   Docker Images: {', '.join(docker_versions)}")
    
    print(f"\n🎯 Latest Available Versions:")
    print(f"   Milvus: v{latest_versions['milvus']}")
    print(f"   PyMilvus: v{latest_versions['pymilvus']}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    
    if compose_version and compose_version < latest_versions["milvus"]:
        print("   🚨 URGENT: Update your Docker Compose configuration")
        print("   📝 Your Milvus container is significantly outdated")
    
    if pymilvus_version and pymilvus_version < latest_versions["pymilvus"]:
        print("   📦 Update PyMilvus: pip install --upgrade pymilvus")
    
    if server_version and server_version < latest_versions["milvus"]:
        print("   🔄 Update your Milvus server to the latest version")
    
    # Compatibility check
    if pymilvus_version and server_version:
        pymilvus_major_minor = '.'.join(pymilvus_version.split('.')[:2])
        server_major_minor = '.'.join(server_version.split('.')[:2])
        
        if pymilvus_major_minor == server_major_minor:
            print("   ✅ PyMilvus and Server versions are compatible")
        else:
            print("   ⚠️ PyMilvus and Server versions may have compatibility issues")
            print(f"      Recommended: Use PyMilvus v{server_major_minor}.x with Server v{server_version}")

def main():
    """Main function to check all versions."""
    print("🔍 Complete Milvus Version Analysis")
    print("=" * 45)
    print("Checking PyMilvus, Docker containers, and configuration files...")
    print()
    
    # Check PyMilvus
    pymilvus_connected, pymilvus_version, server_version = check_pymilvus_version()
    
    # Check Docker
    docker_versions = check_docker_version()
    
    # Check Docker Compose config
    compose_version = check_docker_compose_config()
    
    # Compare and provide recommendations
    compare_versions(pymilvus_version, server_version, docker_versions, compose_version)
    
    print(f"\n🎉 Version check complete!")

if __name__ == "__main__":
    main()
