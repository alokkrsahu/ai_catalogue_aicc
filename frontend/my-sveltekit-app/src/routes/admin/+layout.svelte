<!-- src/routes/admin/+layout.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { isAuthenticated, isAdmin } from '$lib/stores/auth';

  
  onMount(() => {
    if (!$isAuthenticated) {
      goto('/login');
    } else if (!$isAdmin) {
      goto('/');
    }
  });
</script>



<div class="min-h-screen bg-gray-100">
  <header class="bg-white shadow">
    <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
      <h1 class="text-3xl font-bold text-gray-900">
        Admin Panel
      </h1>
    </div>
  </header>
  
  <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
    <div class="flex flex-wrap sm:flex-nowrap">
      <aside class="w-full sm:w-64 mr-0 sm:mr-8 mb-6 sm:mb-0">
        <nav class="bg-white shadow rounded-lg overflow-hidden">
          <div class="px-4 py-5 sm:p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Admin Navigation</h2>
            <ul class="space-y-2">
              <li>
                <a 
                  href="/admin" 
                  class="block px-3 py-2 rounded-md hover:bg-gray-100 text-gray-800"
                >
                  Dashboard
                </a>
              </li>
              <li>
                <a 
                  href="/admin/users" 
                  class="block px-3 py-2 rounded-md hover:bg-gray-100 text-gray-800"
                >
                  User Management
                </a>
              </li>
              <li>
                <a 
                  href="/admin/icons" 
                  class="block px-3 py-2 rounded-md hover:bg-gray-100 text-gray-800"
                >
                  Dashboard Icons
                </a>
              </li>
              <li>
                <a 
                  href="/admin/icon-permissions" 
                  class="block px-3 py-2 rounded-md hover:bg-gray-100 text-gray-800"
                >
                  Icon Permissions
                </a>
              </li>
              <li>
                <a 
                  href="/admin/group-permissions" 
                  class="block px-3 py-2 rounded-md hover:bg-gray-100 text-gray-800"
                >
                  Group Permissions
                </a>
              </li>
              <li>
                <a 
                  href="/admin/project-permissions" 
                  class="block px-3 py-2 rounded-md hover:bg-gray-100 text-gray-800"
                >
                  Project Permissions
                </a>
              </li>
              <li>
                <a 
                  href="/admin/roles" 
                  class="block px-3 py-2 rounded-md hover:bg-gray-100 text-gray-800"
                >
                  Role Management
                </a>
              </li>
            </ul>
          </div>
        </nav>
      </aside>
      
      <main class="flex-1 bg-white shadow rounded-lg overflow-hidden">
        <div class="px-4 py-5 sm:p-6">
          <slot />
        </div>
      </main>
    </div>
  </div>
</div>
