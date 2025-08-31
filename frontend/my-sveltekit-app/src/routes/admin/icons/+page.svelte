<!-- src/routes/admin/icons/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getDashboardIcons, createDashboardIcon, updateDashboardIcon, deleteDashboardIcon } from '$lib/services/api';
  import type { DashboardIcon } from '$lib/types';
  import { toasts } from '$lib/stores/toast';
  
  let icons: DashboardIcon[] = [];
  let loading = true;
  let error = '';
  let editingIcon: DashboardIcon | null = null;
  let showDeleteModal = false;
  let iconToDelete: DashboardIcon | null = null;
  let actionLoading = false;
  let showCreateModal = false;
  
  let formData = {
    name: '',
    description: '',
    icon_class: '',
    color: 'blue',
    route: '',
    order: 0,
    is_active: true
  };
  
  let formErrors: Record<string, string> = {};
  
  const colorOptions = [
    { value: 'blue', label: 'Blue' },
    { value: 'green', label: 'Green' },
    { value: 'red', label: 'Red' },
    { value: 'yellow', label: 'Yellow' },
    { value: 'purple', label: 'Purple' },
    { value: 'indigo', label: 'Indigo' },
    { value: 'pink', label: 'Pink' },
    { value: 'gray', label: 'Gray' },
    { value: 'orange', label: 'Orange' },
    { value: 'teal', label: 'Teal' },
  ];
  
  onMount(async () => {
    await loadIcons();
  });
  
  async function loadIcons() {
    loading = true;
    try {
      icons = await getDashboardIcons();
    } catch (err) {
      error = 'Failed to load icons';
      console.error(err);
    } finally {
      loading = false;
    }
  }
  
  function startCreate() {
    formData = {
      name: '',
      description: '',
      icon_class: 'fa-star',
      color: 'blue',
      route: '/features/',
      order: icons.length + 1,
      is_active: true
    };
    formErrors = {};
    showCreateModal = true;
  }
  
  function startEdit(icon: DashboardIcon) {
    editingIcon = icon;
    formData = {
      name: icon.name,
      description: icon.description,
      icon_class: icon.icon_class,
      color: icon.color,
      route: icon.route,
      order: icon.order,
      is_active: icon.is_active
    };
    formErrors = {};
  }
  
  function cancelEdit() {
    editingIcon = null;
    formErrors = {};
  }
  
  function cancelCreate() {
    showCreateModal = false;
    formErrors = {};
  }
  
  async function handleCreate() {
    actionLoading = true;
    formErrors = {};
    
    try {
      await createDashboardIcon(formData);
      await loadIcons();
      showCreateModal = false;
      toasts.success('Icon created successfully');
    } catch (err: any) {
      if (err.response?.data) {
        formErrors = err.response.data;
      } else {
        formErrors.general = 'Failed to create icon';
      }
      console.error(err);
    } finally {
      actionLoading = false;
    }
  }
  
  async function handleUpdate() {
    if (!editingIcon) return;
    
    actionLoading = true;
    formErrors = {};
    
    try {
      await updateDashboardIcon(editingIcon.id.toString(), formData);
      await loadIcons();
      editingIcon = null;
      toasts.success('Icon updated successfully');
    } catch (err: any) {
      if (err.response?.data) {
        formErrors = err.response.data;
      } else {
        formErrors.general = 'Failed to update icon';
      }
      console.error(err);
    } finally {
      actionLoading = false;
    }
  }
  
  function confirmDelete(icon: DashboardIcon) {
    iconToDelete = icon;
    showDeleteModal = true;
  }
  
  function cancelDelete() {
    iconToDelete = null;
    showDeleteModal = false;
  }
  
  async function handleDelete() {
    if (!iconToDelete) return;
    
    actionLoading = true;
    
    try {
      await deleteDashboardIcon(iconToDelete.id.toString());
      await loadIcons();
      showDeleteModal = false;
      iconToDelete = null;
      toasts.success('Icon deleted successfully');
    } catch (err) {
      error = 'Failed to delete icon';
      console.error(err);
      toasts.error('Failed to delete icon');
    } finally {
      actionLoading = false;
    }
  }
  
  function getColorClasses(color: string): string {
    const colorMap: {[key: string]: string} = {
      'blue': 'bg-blue-100 text-blue-800',
      'green': 'bg-green-100 text-green-800',
      'red': 'bg-red-100 text-red-800',
      'yellow': 'bg-yellow-100 text-yellow-800',
      'purple': 'bg-purple-100 text-purple-800',
      'indigo': 'bg-indigo-100 text-indigo-800',
      'pink': 'bg-pink-100 text-pink-800',
      'gray': 'bg-gray-100 text-gray-800',
      'orange': 'bg-orange-100 text-orange-800',
      'teal': 'bg-teal-100 text-teal-800',
    };
    
    return colorMap[color] || colorMap['blue'];
  }
</script>

<h2 class="text-2xl font-bold text-gray-900 mb-6">Dashboard Icons Management</h2>

{#if loading && icons.length === 0}
  <div class="text-center py-8">
    <p>Loading icons...</p>
  </div>
{:else if error}
  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
    {error}
  </div>
{:else}
  <div class="flex justify-between items-center mb-6">
    <div>
      <h3 class="text-lg font-medium text-gray-900">All Icons ({icons.length})</h3>
    </div>
    <div class="flex space-x-3">
      <button 
        on:click={loadIcons}
        class="py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
      >
        Refresh
      </button>
      <button 
        on:click={startCreate}
        class="py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
      >
        Add New Icon
      </button>
    </div>
  </div>
  
  <div class="overflow-x-auto">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50">
        <tr>
          <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Icon
          </th>
          <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Name
          </th>
          <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Route
          </th>
          <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Order
          </th>
          <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            Status
          </th>
          <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
            Actions
          </th>
        </tr>
      </thead>
      <tbody class="bg-white divide-y divide-gray-200">
        {#each icons as icon (icon.id)}
          <tr>
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="w-10 h-10 flex items-center justify-center rounded-md {getColorClasses(icon.color)}">
                <i class="fas {icon.icon_class}"></i>
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="text-sm font-medium text-gray-900">{icon.name}</div>
              <div class="text-sm text-gray-500">{icon.description}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {icon.route}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {icon.order}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                {icon.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                {icon.is_active ? 'Active' : 'Inactive'}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
              <button 
                on:click={() => startEdit(icon)}
                class="text-indigo-600 hover:text-indigo-900 mr-3"
              >
                Edit
              </button>
              <button 
                on:click={() => confirmDelete(icon)}
                class="text-red-600 hover:text-red-900"
              >
                Delete
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<!-- Create Icon Modal -->
{#if showCreateModal}
  <div class="fixed z-10 inset-0 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 transition-opacity" aria-hidden="true">
        <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
      </div>

      <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
        <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
          <div class="sm:flex sm:items-start">
            <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
              <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                Create New Icon
              </h3>
              <div class="mt-4">
                {#if formErrors.general}
                  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                    {formErrors.general}
                  </div>
                {/if}
                
                <form on:submit|preventDefault={handleCreate} class="space-y-4">
                  <div>
                    <label for="name" class="block text-sm font-medium text-gray-700">Name</label>
                    <input 
                      type="text" 
                      id="name" 
                      bind:value={formData.name} 
                      class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                    />
                    {#if formErrors.name}
                      <p class="mt-1 text-sm text-red-600">{formErrors.name}</p>
                    {/if}
                  </div>
                  
                  <div>
                    <label for="description" class="block text-sm font-medium text-gray-700">Description</label>
                    <textarea 
                      id="description" 
                      bind:value={formData.description} 
                      class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      rows="2"
                    ></textarea>
                    {#if formErrors.description}
                      <p class="mt-1 text-sm text-red-600">{formErrors.description}</p>
                    {/if}
                  </div>
                  
                  <div class="grid grid-cols-1 gap-y-4 gap-x-4 sm:grid-cols-2">
                    <div>
                      <label for="icon_class" class="block text-sm font-medium text-gray-700">Icon Class</label>
                      <input 
                        type="text" 
                        id="icon_class" 
                        bind:value={formData.icon_class} 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                        placeholder="fa-star"
                      />
                      <p class="mt-1 text-xs text-gray-500">
                        FontAwesome classes, e.g., "fa-user"
                      </p>
                      {#if formErrors.icon_class}
                        <p class="mt-1 text-sm text-red-600">{formErrors.icon_class}</p>
                      {/if}
                    </div>
                    
                    <div>
                      <label for="color" class="block text-sm font-medium text-gray-700">Color</label>
                      <select 
                        id="color" 
                        bind:value={formData.color} 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      >
                        {#each colorOptions as option}
                          <option value={option.value}>{option.label}</option>
                        {/each}
                      </select>
                      {#if formErrors.color}
                        <p class="mt-1 text-sm text-red-600">{formErrors.color}</p>
                      {/if}
                    </div>
                  </div>
                  
<div class="grid grid-cols-1 gap-y-4 gap-x-4 sm:grid-cols-2">
                    <div>
                      <label for="route" class="block text-sm font-medium text-gray-700">Route</label>
                      <input 
                        type="text" 
                        id="route" 
                        bind:value={formData.route} 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                        placeholder="/features/example"
                      />
                      {#if formErrors.route}
                        <p class="mt-1 text-sm text-red-600">{formErrors.route}</p>
                      {/if}
                    </div>
                    
                    <div>
                      <label for="order" class="block text-sm font-medium text-gray-700">Display Order</label>
                      <input 
                        type="number" 
                        id="order" 
                        bind:value={formData.order}
                        min="0" 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      />
                      {#if formErrors.order}
                        <p class="mt-1 text-sm text-red-600">{formErrors.order}</p>
                      {/if}
                    </div>
                  </div>
                  
                  <div class="flex items-center">
                    <input 
                      type="checkbox" 
                      id="is_active" 
                      bind:checked={formData.is_active} 
                      class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                    />
                    <label for="is_active" class="ml-2 block text-sm text-gray-900">
                      Active
                    </label>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
        <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
          <button 
            type="button" 
            on:click={handleCreate}
            disabled={actionLoading}
            class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm"
          >
            {actionLoading ? 'Creating...' : 'Create'}
          </button>
          <button 
            type="button" 
            on:click={cancelCreate}
            disabled={actionLoading}
            class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:w-auto sm:text-sm"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- Edit Icon Modal -->
{#if editingIcon}
  <div class="fixed z-10 inset-0 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 transition-opacity" aria-hidden="true">
        <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
      </div>

      <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
        <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
          <div class="sm:flex sm:items-start">
            <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
              <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                Edit Icon
              </h3>
              <div class="mt-4">
                {#if formErrors.general}
                  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                    {formErrors.general}
                  </div>
                {/if}
                
                <form on:submit|preventDefault={handleUpdate} class="space-y-4">
                  <div>
                    <label for="edit-name" class="block text-sm font-medium text-gray-700">Name</label>
                    <input 
                      type="text" 
                      id="edit-name" 
                      bind:value={formData.name} 
                      class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                    />
                    {#if formErrors.name}
                      <p class="mt-1 text-sm text-red-600">{formErrors.name}</p>
                    {/if}
                  </div>
                  
                  <div>
                    <label for="edit-description" class="block text-sm font-medium text-gray-700">Description</label>
                    <textarea 
                      id="edit-description" 
                      bind:value={formData.description} 
                      class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      rows="2"
                    ></textarea>
                    {#if formErrors.description}
                      <p class="mt-1 text-sm text-red-600">{formErrors.description}</p>
                    {/if}
                  </div>
                  
                  <div class="grid grid-cols-1 gap-y-4 gap-x-4 sm:grid-cols-2">
                    <div>
                      <label for="edit-icon-class" class="block text-sm font-medium text-gray-700">Icon Class</label>
                      <input 
                        type="text" 
                        id="edit-icon-class" 
                        bind:value={formData.icon_class} 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      />
                      <p class="mt-1 text-xs text-gray-500">
                        FontAwesome classes, e.g., "fa-user"
                      </p>
                      {#if formErrors.icon_class}
                        <p class="mt-1 text-sm text-red-600">{formErrors.icon_class}</p>
                      {/if}
                    </div>
                    
                    <div>
                      <label for="edit-color" class="block text-sm font-medium text-gray-700">Color</label>
                      <select 
                        id="edit-color" 
                        bind:value={formData.color} 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      >
                        {#each colorOptions as option}
                          <option value={option.value}>{option.label}</option>
                        {/each}
                      </select>
                      {#if formErrors.color}
                        <p class="mt-1 text-sm text-red-600">{formErrors.color}</p>
                      {/if}
                    </div>
                  </div>
                  
                  <div class="grid grid-cols-1 gap-y-4 gap-x-4 sm:grid-cols-2">
                    <div>
                      <label for="edit-route" class="block text-sm font-medium text-gray-700">Route</label>
                      <input 
                        type="text" 
                        id="edit-route" 
                        bind:value={formData.route} 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      />
                      {#if formErrors.route}
                        <p class="mt-1 text-sm text-red-600">{formErrors.route}</p>
                      {/if}
                    </div>
                    
                    <div>
                      <label for="edit-order" class="block text-sm font-medium text-gray-700">Display Order</label>
                      <input 
                        type="number" 
                        id="edit-order" 
                        bind:value={formData.order}
                        min="0" 
                        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      />
                      {#if formErrors.order}
                        <p class="mt-1 text-sm text-red-600">{formErrors.order}</p>
                      {/if}
                    </div>
                  </div>
                  
                  <div class="flex items-center">
                    <input 
                      type="checkbox" 
                      id="edit-is-active" 
                      bind:checked={formData.is_active} 
                      class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                    />
                    <label for="edit-is-active" class="ml-2 block text-sm text-gray-900">
                      Active
                    </label>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
        <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
          <button 
            type="button" 
            on:click={handleUpdate}
            disabled={actionLoading}
            class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm"
          >
            {actionLoading ? 'Saving...' : 'Save Changes'}
          </button>
          <button 
            type="button" 
            on:click={cancelEdit}
            disabled={actionLoading}
            class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:w-auto sm:text-sm"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteModal}
  <div class="fixed z-10 inset-0 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
      <div class="fixed inset-0 transition-opacity" aria-hidden="true">
        <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
      </div>

      <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
        <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
          <div class="sm:flex sm:items-start">
            <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
              <svg class="h-6 w-6 text-red-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
              <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                Delete Icon
              </h3>
              <div class="mt-2">
                <p class="text-sm text-gray-500">
                  Are you sure you want to delete the icon <strong>{iconToDelete?.name}</strong>? This action cannot be undone.
                </p>
              </div>
            </div>
          </div>
        </div>
        <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
          <button 
            type="button" 
            on:click={handleDelete}
            disabled={actionLoading}
            class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm"
          >
            {actionLoading ? 'Deleting...' : 'Delete'}
          </button>
          <button 
            type="button" 
            on:click={cancelDelete}
            disabled={actionLoading}
            class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:w-auto sm:text-sm"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
