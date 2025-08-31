<!-- src/routes/admin/roles/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getUsers } from '$lib/services/api';
  import type { User } from '$lib/types';
  import { UserRole } from '$lib/types';

  let users: User[] = [];
  let loading = true;
  let error = '';
  
  // Role counts
  let roleCounts = {
    [UserRole.ADMIN]: 0,
    [UserRole.STAFF]: 0,
    [UserRole.USER]: 0
  };
  
  // Filter by role
  let selectedRole: UserRole | 'ALL' = 'ALL';
  
  $: filteredUsers = selectedRole === 'ALL' 
    ? users 
    : users.filter(user => user.role === selectedRole);

  onMount(async () => {
    await loadUsers();
  });

  async function loadUsers() {
    loading = true;
    try {
      users = await getUsers();
      
      // Calculate role counts
      roleCounts = {
        [UserRole.ADMIN]: users.filter(u => u.role === UserRole.ADMIN).length,
        [UserRole.STAFF]: users.filter(u => u.role === UserRole.STAFF).length,
        [UserRole.USER]: users.filter(u => u.role === UserRole.USER).length
      };
    } catch (err) {
      error = 'Failed to load users';
      console.error(err);
    } finally {
      loading = false;
    }
  }
  
  function getRoleBadgeClass(role: UserRole): string {
    switch (role) {
      case UserRole.ADMIN:
        return 'bg-purple-100 text-purple-800';
      case UserRole.STAFF:
        return 'bg-blue-100 text-blue-800';
      case UserRole.USER:
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }
</script>

<h2 class="text-2xl font-bold text-gray-900 mb-6">Role Management</h2>

{#if loading && users.length === 0}
  <div class="text-center py-8">
    <p>Loading users...</p>
  </div>
{:else if error}
  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
    {error}
  </div>
{:else}
  <div class="mb-6">
    <h3 class="text-lg font-medium text-gray-900 mb-4">Role Overview</h3>
    
    <div class="grid grid-cols-1 gap-5 sm:grid-cols-3">
      <div class="bg-white overflow-hidden shadow rounded-lg">
        <div class="px-4 py-5 sm:p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0 bg-purple-500 rounded-md p-3">
              <svg class="h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <div class="ml-5 w-0 flex-1">
              <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                  Admin Users
                </dt>
                <dd>
                  <div class="text-lg font-medium text-gray-900">
                    {roleCounts[UserRole.ADMIN]}
                  </div>
                </dd>
              </dl>
            </div>
          </div>
        </div>
        <div class="bg-gray-50 px-4 py-3">
          <button 
            class="text-sm text-purple-700 font-medium hover:text-purple-900"
            on:click={() => selectedRole = UserRole.ADMIN}
          >
            View all admins →
          </button>
        </div>
      </div>
      
      <div class="bg-white overflow-hidden shadow rounded-lg">
        <div class="px-4 py-5 sm:p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0 bg-blue-500 rounded-md p-3">
              <svg class="h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div class="ml-5 w-0 flex-1">
              <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                  Staff Users
                </dt>
                <dd>
                  <div class="text-lg font-medium text-gray-900">
                    {roleCounts[UserRole.STAFF]}
                  </div>
                </dd>
              </dl>
            </div>
          </div>
        </div>
        <div class="bg-gray-50 px-4 py-3">
          <button 
            class="text-sm text-blue-700 font-medium hover:text-blue-900"
            on:click={() => selectedRole = UserRole.STAFF}
          >
            View all staff →
          </button>
        </div>
      </div>
      
      <div class="bg-white overflow-hidden shadow rounded-lg">
        <div class="px-4 py-5 sm:p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0 bg-gray-500 rounded-md p-3">
              <svg class="h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div class="ml-5 w-0 flex-1">
              <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                  Regular Users
                </dt>
                <dd>
                  <div class="text-lg font-medium text-gray-900">
                    {roleCounts[UserRole.USER]}
                  </div>
                </dd>
              </dl>
            </div>
          </div>
        </div>
        <div class="bg-gray-50 px-4 py-3">
          <button 
            class="text-sm text-gray-700 font-medium hover:text-gray-900"
            on:click={() => selectedRole = UserRole.USER}
          >
            View all users →
          </button>
        </div>
      </div>
    </div>
  </div>
  
  <div class="mb-6">
    <div class="flex justify-between items-center">
      <div class="flex items-center">
        <h3 class="text-lg font-medium text-gray-900">
          {selectedRole === 'ALL' ? 'All Users' : `${selectedRole} Users`}
        </h3>
        <div class="ml-4">
          <select 
            bind:value={selectedRole}
            class="mt-1 block pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
          >
            <option value="ALL">All Roles</option>
            <option value={UserRole.ADMIN}>Admin</option>
            <option value={UserRole.STAFF}>Staff</option>
            <option value={UserRole.USER}>Regular User</option>
          </select>
        </div>
      </div>
      
      <button 
        on:click={loadUsers}
        class="btn btn-secondary text-sm"
      >
        Refresh
      </button>
    </div>
    
    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Email
            </th>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Name
            </th>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Role
            </th>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Joined
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          {#each filteredUsers as user (user.id)}
            <tr>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {user.email}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {user.first_name} {user.last_name}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getRoleBadgeClass(user.role)}`}>
                  {user.role}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                  {user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                  {user.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {new Date(user.date_joined).toLocaleDateString()}
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="5" class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 text-center">
                No users found with the selected role.
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
  
  <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
    <h4 class="text-md font-medium text-gray-900 mb-2">About User Roles</h4>
    <ul class="list-disc pl-5 space-y-2 text-sm text-gray-600">
      <li><strong>Admin:</strong> Full access to all system features including user management and role assignments.</li>
      <li><strong>Staff:</strong> Access to content management and support features, but cannot manage users or roles.</li>
      <li><strong>Regular User:</strong> Basic access to application features without any administrative privileges.</li>
    </ul>
    <p class="mt-3 text-sm text-gray-600">
      To modify a user's role, go to the <a href="/admin/users" class="text-blue-600 hover:text-blue-800">User Management</a> page.
    </p>
  </div>
{/if}
