<!-- src/routes/admin/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getUsers } from '$lib/services/api';
  import type { User } from '$lib/types';
  
  let users: User[] = [];
  let usersCount = { total: 0, active: 0, admin: 0, staff: 0, regular: 0 };
  let loading = true;
  let error = '';
  
  onMount(async () => {
    try {
      users = await getUsers();
      
      // Calculate counts
      usersCount.total = users.length;
      usersCount.active = users.filter(user => user.is_active).length;
      usersCount.admin = users.filter(user => user.role === 'ADMIN').length;
      usersCount.staff = users.filter(user => user.role === 'STAFF').length;
      usersCount.regular = users.filter(user => user.role === 'USER').length;
    } catch (err) {
      error = 'Failed to load user data';
      console.error(err);
    } finally {
      loading = false;
    }
  });
</script>

<h2 class="text-2xl font-bold text-gray-900 mb-6">Admin Dashboard</h2>

{#if loading}
  <div class="text-center py-8">
    <p>Loading data...</p>
  </div>
{:else if error}
  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
    {error}
  </div>
{:else}
  <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
    <!-- Total Users Card -->
    <div class="bg-gray-50 overflow-hidden shadow rounded-lg">
      <div class="px-4 py-5 sm:p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0 bg-blue-500 rounded-md p-3">
            <svg class="h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          </div>
          <div class="ml-5 w-0 flex-1">
            <dl>
              <dt class="text-sm font-medium text-gray-500 truncate">
                Total Users
              </dt>
              <dd>
                <div class="text-lg font-medium text-gray-900">
                  {usersCount.total}
                </div>
              </dd>
            </dl>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Users Card -->
    <div class="bg-gray-50 overflow-hidden shadow rounded-lg">
      <div class="px-4 py-5 sm:p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0 bg-green-500 rounded-md p-3">
            <svg class="h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div class="ml-5 w-0 flex-1">
            <dl>
              <dt class="text-sm font-medium text-gray-500 truncate">
                Active Users
              </dt>
              <dd>
                <div class="text-lg font-medium text-gray-900">
                  {usersCount.active}
                </div>
              </dd>
            </dl>
          </div>
        </div>
      </div>
    </div>

    <!-- Admin Users Card -->
    <div class="bg-gray-50 overflow-hidden shadow rounded-lg">
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
                  {usersCount.admin}
                </div>
              </dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Role Distribution -->
  <div class="mt-8">
    <h3 class="text-lg font-medium text-gray-900 mb-4">Role Distribution</h3>
    <div class="bg-white shadow overflow-hidden rounded-lg">
      <div class="px-4 py-5 sm:p-6">
        <div class="grid grid-cols-3 gap-5">
          <div class="text-center">
            <div class="text-lg font-medium text-purple-600">{usersCount.admin}</div>
            <div class="text-sm text-gray-500">Admins</div>
            <div class="mt-2 h-1 bg-gray-200 rounded-full overflow-hidden">
              <div class="bg-purple-500 h-1" style="width: {(usersCount.admin / usersCount.total * 100) || 0}%"></div>
            </div>
          </div>
          <div class="text-center">
            <div class="text-lg font-medium text-blue-600">{usersCount.staff}</div>
            <div class="text-sm text-gray-500">Staff</div>
            <div class="mt-2 h-1 bg-gray-200 rounded-full overflow-hidden">
              <div class="bg-blue-500 h-1" style="width: {(usersCount.staff / usersCount.total * 100) || 0}%"></div>
            </div>
          </div>
          <div class="text-center">
            <div class="text-lg font-medium text-gray-600">{usersCount.regular}</div>
            <div class="text-sm text-gray-500">Regular Users</div>
            <div class="mt-2 h-1 bg-gray-200 rounded-full overflow-hidden">
              <div class="bg-gray-500 h-1" style="width: {(usersCount.regular / usersCount.total * 100) || 0}%"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Recent Users Table -->
  <h3 class="text-lg font-medium text-gray-900 mt-8 mb-4">Recent Users</h3>
  
  <div class="flex flex-col">
    <div class="-my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
      <div class="py-2 align-middle inline-block min-w-full sm:px-6 lg:px-8">
        <div class="shadow overflow-hidden border-b border-gray-200 sm:rounded-lg">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  User
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
                <th scope="col" class="relative px-6 py-3">
                  <span class="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              {#each users.slice(0, 5) as user}
                <tr>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                      <div class="flex-shrink-0 h-10 w-10 bg-gray-200 rounded-full flex items-center justify-center">
                        <span class="text-gray-500 font-medium">
                          {user.first_name && user.last_name
                            ? `${user.first_name[0]}${user.last_name[0]}`
                            : user.email[0].toUpperCase()}
                        </span>
                      </div>
                      <div class="ml-4">
                        <div class="text-sm font-medium text-gray-900">
                          {user.first_name} {user.last_name}
                        </div>
                        <div class="text-sm text-gray-500">
                          {user.email}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                      {user.role === 'ADMIN' ? 'bg-purple-100 text-purple-800' : 
                       user.role === 'STAFF' ? 'bg-blue-100 text-blue-800' : 
                       'bg-gray-100 text-gray-800'}">
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
                  <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <a href="/admin/users" class="text-blue-600 hover:text-blue-900">Edit</a>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- Quick Actions -->
  <div class="mt-8">
    <h3 class="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
    <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <a href="/admin/users" class="bg-white shadow overflow-hidden rounded-lg p-6 hover:bg-gray-50">
        <div class="flex items-center">
          <div class="flex-shrink-0 bg-blue-100 rounded-md p-3">
            <svg class="h-6 w-6 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
          </div>
          <div class="ml-4">
            <h4 class="text-base font-medium text-gray-900">Manage Users</h4>
            <p class="text-sm text-gray-500">Add, update, or delete users</p>
          </div>
        </div>
      </a>
      
      <a href="/admin/roles" class="bg-white shadow overflow-hidden rounded-lg p-6 hover:bg-gray-50">
        <div class="flex items-center">
          <div class="flex-shrink-0 bg-green-100 rounded-md p-3">
            <svg class="h-6 w-6 text-green-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <div class="ml-4">
            <h4 class="text-base font-medium text-gray-900">Manage Roles</h4>
            <p class="text-sm text-gray-500">Assign roles to users</p>
          </div>
        </div>
      </a>
    </div>
  </div>
{/if}
