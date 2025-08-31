#!/usr/bin/env python3
"""
Test script for admin-only project deletion functionality
Tests both the IntelliDocProjectViewSet and UniversalProjectViewSet
"""

import os
import sys
import django
import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

def setup_django():
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    django.setup()

def test_admin_deletion():
    """Test admin-only project deletion functionality"""
    setup_django()
    
    # Import after Django setup
    from users.models import IntelliDocProject, UserRole
    from django.contrib.auth.models import Group
    
    User = get_user_model()
    client = APIClient()
    
    print("🧪 Testing Admin-Only Project Deletion")
    print("=" * 50)
    
    # Create test users
    try:
        # Create admin user
        admin_user = User.objects.create_user(
            email='admin@test.com',
            password='admin123',
            role=UserRole.ADMIN,
            is_staff=True,
            is_active=True
        )
        print("✅ Created admin user")
        
        # Create regular user
        regular_user = User.objects.create_user(
            email='user@test.com', 
            password='user123',
            role=UserRole.USER,
            is_active=True
        )
        print("✅ Created regular user")
        
        # Create staff user
        staff_user = User.objects.create_user(
            email='staff@test.com',
            password='staff123', 
            role=UserRole.STAFF,
            is_staff=True,
            is_active=True
        )
        print("✅ Created staff user")
        
        # Create test project
        test_project = IntelliDocProject.objects.create(
            name='Test Project for Deletion',
            description='A test project to verify admin-only deletion',
            template_name='Test Template',
            template_type='test',
            created_by=admin_user
        )
        print(f"✅ Created test project: {test_project.name} (ID: {test_project.project_id})")
        
        # Test cases
        test_cases = [
            {
                'user': regular_user,
                'password': 'user123',
                'expected_status': status.HTTP_403_FORBIDDEN,
                'description': 'Regular user should be denied'
            },
            {
                'user': staff_user,
                'password': 'staff123', 
                'expected_status': status.HTTP_403_FORBIDDEN,
                'description': 'Staff user should be denied'
            },
            {
                'user': admin_user,
                'password': 'wrong_password',
                'expected_status': status.HTTP_401_UNAUTHORIZED,
                'description': 'Admin with wrong password should be denied'
            },
            {
                'user': admin_user,
                'password': None,
                'expected_status': status.HTTP_400_BAD_REQUEST,
                'description': 'Admin without password should be denied'
            },
            {
                'user': admin_user,
                'password': 'admin123',
                'expected_status': status.HTTP_200_OK,
                'description': 'Admin with correct password should succeed'
            }
        ]
        
        # Test Universal Project API
        print("\n🔬 Testing Universal Project API (/api/projects/)")
        for i, test_case in enumerate(test_cases, 1):
            print(f"\nTest {i}: {test_case['description']}")
            
            # Authenticate as test user
            client.force_authenticate(user=test_case['user'])
            
            # Prepare deletion data
            deletion_data = {}
            if test_case['password'] is not None:
                deletion_data['password'] = test_case['password']
            
            # Attempt deletion
            response = client.delete(
                f'/api/projects/{test_project.project_id}/',
                data=deletion_data,
                format='json'
            )
            
            print(f"   Expected status: {test_case['expected_status']}")
            print(f"   Actual status: {response.status_code}")
            
            if response.status_code == test_case['expected_status']:
                print("   ✅ PASS")
            else:
                print("   ❌ FAIL")
                print(f"   Response: {response.data}")
            
            # If this was the successful deletion, recreate the project for next tests
            if (response.status_code == status.HTTP_200_OK and 
                test_case['expected_status'] == status.HTTP_200_OK):
                test_project = IntelliDocProject.objects.create(
                    name='Test Project for Deletion (Recreated)',
                    description='A test project to verify admin-only deletion', 
                    template_name='Test Template',
                    template_type='test',
                    created_by=admin_user
                )
                print(f"   🔄 Recreated project for remaining tests")
        
        print("\n📊 Test Summary")
        print("All tests completed. Check output above for results.")
        
        # Cleanup
        try:
            if IntelliDocProject.objects.filter(name__contains='Test Project for Deletion').exists():
                IntelliDocProject.objects.filter(name__contains='Test Project for Deletion').delete()
                print("🧹 Cleaned up test projects")
        except:
            pass
            
        try:
            User.objects.filter(email__in=['admin@test.com', 'user@test.com', 'staff@test.com']).delete()
            print("🧹 Cleaned up test users")
        except:
            pass
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

def test_permission_classes():
    """Test the permission classes directly"""
    setup_django()
    
    print("\n🔐 Testing Permission Classes")
    print("=" * 50)
    
    from api.permissions import IsAdminUser, IsAdminUserForDeletion
    from django.http import HttpRequest
    from rest_framework.request import Request
    
    User = get_user_model()
    
    # Create test users
    admin_user = User.objects.create_user(
        email='perm_admin@test.com',
        password='admin123',
        role='ADMIN'
    )
    
    regular_user = User.objects.create_user(
        email='perm_user@test.com',
        password='user123', 
        role='USER'
    )
    
    # Create mock request
    http_request = HttpRequest()
    http_request.method = 'DELETE'
    
    # Test with admin user
    http_request.user = admin_user
    request = Request(http_request)
    
    # Create mock view
    class MockView:
        action = 'destroy'
    
    view = MockView()
    
    # Test permissions
    admin_permission = IsAdminUser()
    deletion_permission = IsAdminUserForDeletion()
    
    print("Testing admin user permissions:")
    print(f"  IsAdminUser: {admin_permission.has_permission(request, view)}")
    print(f"  IsAdminUserForDeletion: {deletion_permission.has_permission(request, view)}")
    
    # Test with regular user
    http_request.user = regular_user
    request = Request(http_request)
    
    print("Testing regular user permissions:")
    print(f"  IsAdminUser: {admin_permission.has_permission(request, view)}")
    print(f"  IsAdminUserForDeletion: {deletion_permission.has_permission(request, view)}")
    
    # Cleanup
    User.objects.filter(email__in=['perm_admin@test.com', 'perm_user@test.com']).delete()

if __name__ == '__main__':
    print("🚀 Starting Admin-Only Project Deletion Tests")
    test_admin_deletion()
    test_permission_classes()
    print("\n✅ All tests completed!")