<!-- src/routes/admin/group-permissions/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { 
    getGroups, 
    getDashboardIcons, 
    getGroupIconPermissions,
    updateGroupIconPermissions 
  } from '$lib/services/api';
  import type { Group, DashboardIcon, GroupIconPermission } from '$lib/types';
  import { toasts } from '$lib/stores/toast';

  let groups: Group[] = [];
  let icons: DashboardIcon[] = [];
  let selectedGroup: Group | null = null;
  let selectedGroupPermissions: number[] = [];
  let viewMode: 'grid' | 'list' = 'list'; // Default to list view for better name visibility
  let loading = {
    groups: true,
    icons: true,
    permissions: false
  };
  let saving = false;
  let error = '';

  onMount(async () => {
    try {
      // Load groups and icons in parallel
      const [groupsResponse, iconsResponse] = await Promise.all([
        getGroups(),
        getDashboardIcons()
      ]);
      
      groups = groupsResponse;
      icons = iconsResponse;
    } catch (err) {
      console.error('Failed to load data:', err);
      error = 'Failed to load groups or icons. Please refresh the page.';
    } finally {
      loading.groups = false;
      loading.icons = false;
    }
  });

  async function handleGroupSelect(groupId: string) {
    if (!groupId) {
      selectedGroup = null;
      selectedGroupPermissions = [];
      return;
    }
    
    const group = groups.find(g => g.id.toString() === groupId);
    if (!group) return;
    
    selectedGroup = group;
    loading.permissions = true;
    
    try {
      const permissions = await getGroupIconPermissions(groupId);
      selectedGroupPermissions = permissions.map((p: GroupIconPermission) => p.icon);
    } catch (err) {
      console.error('Failed to load permissions:', err);
      toasts.error(`Failed to load permissions for ${group.name}`);
    } finally {
      loading.permissions = false;
    }
  }

  function handleIconToggle(iconId: number) {
    const index = selectedGroupPermissions.indexOf(iconId);
    
    if (index === -1) {
      // Add permission
      selectedGroupPermissions = [...selectedGroupPermissions, iconId];
    } else {
      // Remove permission
      selectedGroupPermissions = selectedGroupPermissions.filter(id => id !== iconId);
    }
  }

  function handleKeyPress(event: KeyboardEvent, iconId: number) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleIconToggle(iconId);
    }
  }

  function selectAll() {
    selectedGroupPermissions = icons.map(icon => icon.id);
  }

  function deselectAll() {
    selectedGroupPermissions = [];
  }

  async function savePermissions() {
    if (!selectedGroup) return;
    
    saving = true;
    
    try {
      await updateGroupIconPermissions(
        selectedGroup.id.toString(), 
        selectedGroupPermissions
      );
      
      toasts.success(`Permissions updated for group: ${selectedGroup.name}`);
    } catch (err) {
      console.error('Failed to update permissions:', err);
      toasts.error(`Failed to update permissions for group: ${selectedGroup.name}`);
    } finally {
      saving = false;
    }
  }
  
  function getColorClasses(color: string): string {
    const colorMap: {[key: string]: string} = {
      'blue': 'bg-oxford-100 text-oxford-800 border-oxford-200',
      'green': 'bg-green-100 text-green-800 border-green-200',
      'red': 'bg-red-100 text-red-800 border-red-200',
      'yellow': 'bg-yellow-100 text-yellow-800 border-yellow-200',
      'purple': 'bg-purple-100 text-purple-800 border-purple-200',
      'indigo': 'bg-indigo-100 text-indigo-800 border-indigo-200',
      'pink': 'bg-pink-100 text-pink-800 border-pink-200',
      'gray': 'bg-gray-100 text-gray-800 border-gray-200',
      'orange': 'bg-orange-100 text-orange-800 border-orange-200',
      'teal': 'bg-teal-100 text-teal-800 border-teal-200',
    };
    
    return colorMap[color] || colorMap['blue'];
  }
</script>

<div class="dashboard-oxford container-oxford section-oxford">
  <h2 class="heading-oxford-2">Group Icon Permissions</h2>

  {#if loading.groups || loading.icons}
    <div class="text-center py-8">
      <div class="spinner-oxford"></div>
      <p class="mt-2 text-oxford-secondary">Loading data...</p>
    </div>
  {:else if error}
    <div class="alert-oxford-error mb-4">
      {error}
    </div>
  {:else}
    <div class="flex flex-col space-y-6">
      <div class="card-oxford">
        <h3 class="card-oxford-title">Select Group</h3>
        
        {#if groups.length === 0}
          <div class="alert-oxford-warning mb-4">
            <p>No user groups found. Create groups in the Django admin panel first at <code>/admin/auth/group/</code>.</p>
          </div>
        {:else}
          <div class="max-w-md">
            <label for="group-select" class="form-label">Group</label>
            <select 
              id="group-select" 
              on:change={(e) => handleGroupSelect(e.currentTarget.value)}
              class="form-input focus-oxford"
            >
              <option value="">-- Select a group --</option>
              {#each groups as group}
                <option value={group.id}>{group.name}</option>
              {/each}
            </select>
            <p class="mt-2 text-sm text-oxford-secondary">
              Users will automatically have access to icons assigned to their groups.
            </p>
          </div>
        {/if}
      </div>
      
      {#if selectedGroup}
        <div class="card-oxford">
          <div class="card-oxford-header">
            <div class="flex justify-between items-center">
              <div>
                <h3 class="card-oxford-title">
                  Icons for Group: {selectedGroup.name}
                </h3>
                <p class="card-oxford-subtitle">
                  Configure which dashboard features this group can access
                </p>
              </div>
              <div class="flex space-x-3">
                <div class="flex space-x-2 bg-oxford-50 rounded-md p-1">
                  <button
                    on:click={() => viewMode = 'list'}
                    class="p-2 rounded-md transition-colors duration-200 {viewMode === 'list' ? 'bg-oxford-blue text-white' : 'text-oxford-600 hover:bg-oxford-100'}"
                    title="List View"
                    aria-label="Switch to list view"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd" />
                    </svg>
                  </button>
                  <button
                    on:click={() => viewMode = 'grid'}
                    class="p-2 rounded-md transition-colors duration-200 {viewMode === 'grid' ? 'bg-oxford-blue text-white' : 'text-oxford-600 hover:bg-oxford-100'}"
                    title="Grid View"
                    aria-label="Switch to grid view"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                      <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                    </svg>
                  </button>
                </div>
                <button 
                  on:click={savePermissions}
                  disabled={saving || loading.permissions}
                  class="btn-oxford-primary disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Permissions'}
                </button>
              </div>
            </div>
          </div>
          
          {#if loading.permissions}
            <div class="text-center py-8">
              <div class="spinner-oxford"></div>
              <p class="mt-2 text-oxford-secondary">Loading permissions...</p>
            </div>
          {:else}
            <div class="mb-4 flex justify-between items-center">
              <p class="text-oxford-secondary">
                Select which dashboard icons this group should have access to:
              </p>
              <div class="flex space-x-2">
                <button 
                  on:click={selectAll}
                  class="text-sm text-oxford-blue hover:text-oxford-800 transition-colors duration-200"
                >
                  Select All
                </button>
                <span class="text-oxford-300">|</span>
                <button 
                  on:click={deselectAll}
                  class="text-sm text-oxford-blue hover:text-oxford-800 transition-colors duration-200"
                >
                  Deselect All
                </button>
              </div>
            </div>
            
            {#if viewMode === 'list'}
              <!-- Accessible List View -->
              <div class="table-oxford">
                <table class="w-full">
                  <thead>
                    <tr>
                      <th scope="col" class="px-3 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">
                        Access
                      </th>
                      <th scope="col" class="px-3 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">
                        Icon
                      </th>
                      <th scope="col" class="px-3 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">
                        Name
                      </th>
                      <th scope="col" class="px-3 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">
                        Description
                      </th>
                      <th scope="col" class="px-3 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">
                        Route
                      </th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-oxford-100">
                    {#each icons as icon (icon.id)}
                      <tr 
                        class="hover:bg-oxford-50 cursor-pointer transition-colors duration-200" 
                        role="button"
                        tabindex="0"
                        aria-label="Toggle access for {icon.name}"
                        on:click={() => handleIconToggle(icon.id)}
                        on:keydown={(e) => handleKeyPress(e, icon.id)}
                      >
                        <td class="px-3 py-4 whitespace-nowrap">
                          <input 
                            type="checkbox" 
                            checked={selectedGroupPermissions.includes(icon.id)} 
                            on:change={() => handleIconToggle(icon.id)}
                            class="h-4 w-4 text-oxford-blue focus:ring-oxford-500 border-oxford-300 rounded"
                            aria-label="Grant access to {icon.name}"
                          />
                        </td>
                        <td class="px-3 py-4 whitespace-nowrap">
                          <div class="w-8 h-8 flex items-center justify-center rounded-md {getColorClasses(icon.color)}">
                            <i class="fas {icon.icon_class}" aria-hidden="true"></i>
                          </div>
                        </td>
                        <td class="px-3 py-4 whitespace-nowrap">
                          <div class="text-sm font-medium text-oxford-800">{icon.name}</div>
                        </td>
                        <td class="px-3 py-4">
                          <div class="text-sm text-oxford-600">{icon.description}</div>
                        </td>
                        <td class="px-3 py-4 whitespace-nowrap text-sm text-oxford-500">
                          <code class="bg-oxford-50 px-2 py-1 rounded text-xs">{icon.route}</code>
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <!-- Accessible Grid View -->
              <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {#each icons as icon (icon.id)}
                  <button 
                    type="button"
                    class="dashboard-icon-oxford text-left transition-all duration-300 {selectedGroupPermissions.includes(icon.id) ? 'border-oxford-500 ring-2 ring-oxford-200 bg-oxford-50' : 'border-oxford-200 hover:border-oxford-300'}"
                    on:click={() => handleIconToggle(icon.id)}
                    aria-pressed={selectedGroupPermissions.includes(icon.id)}
                    aria-label="Toggle access for {icon.name}: {icon.description}"
                  >
                    <div class="flex items-center mb-2">
                      <div class="w-8 h-8 flex items-center justify-center rounded-md mr-3 {getColorClasses(icon.color)}">
                        <i class="fas {icon.icon_class}" aria-hidden="true"></i>
                      </div>
                      <div class="title">{icon.name}</div>
                    </div>
                    <p class="description">{icon.description}</p>
                    <div class="mt-2 flex justify-between items-center">
                      <code class="text-xs text-oxford-400 bg-oxford-50 px-2 py-1 rounded">{icon.route}</code>
                      <input 
                        type="checkbox" 
                        checked={selectedGroupPermissions.includes(icon.id)} 
                        on:change={() => handleIconToggle(icon.id)}
                        class="h-4 w-4 text-oxford-blue focus:ring-oxford-500 border-oxford-300 rounded"
                        tabindex="-1"
                        aria-hidden="true"
                      />
                    </div>
                  </button>
                {/each}
              </div>
            {/if}
            
            {#if icons.length === 0}
              <div class="text-center py-8">
                <p class="text-oxford-500">No dashboard icons available.</p>
                <p class="text-sm text-oxford-400 mt-1">Create some dashboard icons in the admin panel first.</p>
              </div>
            {/if}
          {/if}
        </div>
      {/if}
    </div>
    
    <div class="mt-6 alert-oxford-info">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-blue-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3 flex-1 md:flex md:justify-between">
          <p class="text-sm text-blue-700">
            Groups are managed in the Django admin panel at <code>/admin/auth/group/</code>. Create groups there first, then assign icon permissions here.
          </p>
          <p class="mt-3 text-sm md:mt-0 md:ml-6">
            <a href="http://localhost:8000/admin/auth/group/" target="_blank" class="whitespace-nowrap font-medium text-blue-700 hover:text-blue-600 focus-oxford">
              Open Django Admin <span aria-hidden="true">&rarr;</span>
            </a>
          </p>
        </div>
      </div>
    </div>
  {/if}
</div>
