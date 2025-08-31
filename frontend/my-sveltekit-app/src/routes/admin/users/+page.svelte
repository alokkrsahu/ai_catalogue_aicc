<!-- src/routes/admin/users/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getUsers, updateUser, deleteUser } from '$lib/services/api';
  import type { User } from '$lib/types';
  import { UserRole } from '$lib/types';

  let users: User[] = [];
  let loading = true;
  let error = '';
  let editingUser: User | null = null;
  let formData = {
    first_name: '',
    last_name: '',
    role: '',
    is_active: true
  };
  let showDeleteModal = false;
  let userToDelete: User | null = null;
  let formErrors: Record<string, string> = {};
  let actionLoading = false;

  onMount(async () => {
    await loadUsers();
  });

  async function loadUsers() {
    loading = true;
    try {
      users = await getUsers();
    } catch (err) {
      error = 'Failed to load users';
      console.error(err);
    } finally {
      loading = false;
    }
  }

  function startEdit(user: User) {
    editingUser = user;
    formData = {
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      is_active: user.is_active
    };
    formErrors = {};
  }

  function cancelEdit() {
    editingUser = null;
    formErrors = {};
  }

  async function handleUpdate() {
    if (!editingUser) return;
    
    actionLoading = true;
    formErrors = {};
    
    try {
      await updateUser(editingUser.id, formData);
      await loadUsers();
      editingUser = null;
    } catch (err: any) {
      if (err.response?.data) {
        formErrors = err.response.data;
      } else {
        formErrors.general = 'Failed to update user';
      }
      console.error(err);
    } finally {
      actionLoading = false;
    }
  }

  function confirmDelete(user: User) {
    userToDelete = user;
    showDeleteModal = true;
  }

  function cancelDelete() {
    userToDelete = null;
    showDeleteModal = false;
  }

  async function handleDelete() {
    if (!userToDelete) return;
    
    actionLoading = true;
    
    try {
      await deleteUser(userToDelete.id);
      await loadUsers();
      showDeleteModal = false;
      userToDelete = null;
    } catch (err) {
      error = 'Failed to delete user';
      console.error(err);
    } finally {
      actionLoading = false;
    }
  }
</script>

<h2 class="text-2xl font-bold text-gray-900 mb-6">User Management</h2>

{#if loading && users.length === 0}
  <div class="text-center py-8">
    <p>Loading users...</p>
  </div>
{:else if error}
  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
    {error}
  </div>
{:else}
  <div class="flex justify-between items-center mb-6">
    <div>
      <h3 class="text-lg font-medium text-gray-900">All Users ({users.length})</h3>
    </div>
    <button 
      on:click={loadUsers}
      class="btn btn-secondary text-sm"
    >
      Refresh
    </button>
  </div>
  
  <div class="overflow-x-auto">
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
          <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
            Actions
          </th>
        </tr>
      </thead>
      <tbody class="bg-white divide-y divide-gray-200">
        {#each users as user (user.id)}
          <tr>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
              {user.email}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
              {user.first_name} {user.last_name}
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
              <button 
                on:click={() => startEdit(user)}
                class="text-blue-600 hover:text-blue-900 mr-3"
              >
                Edit
              </button>
              <button 
                on:click={() => confirmDelete(user)}
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

<!-- Edit User Modal -->
{#if editingUser}
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
                Edit User
              </h3>
              <div class="mt-4">
                {#if formErrors.general}
                  <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                    {formErrors.general}
                  </div>
                {/if}
                
                <form on:submit|preventDefault={handleUpdate} class="space-y-4">
                  <div>
                    <label for="email" class="form-label">Email</label>
                    <input 
                      type="text" 
                      id="email" 
                      value={editingUser.email} 
                      disabled 
                      class="form-input bg-gray-100"
                    />
                  </div>
                  
                  <div class="grid grid-cols-1 gap-y-4 gap-x-4 sm:grid-cols-2">
                    <div>
                      <label for="first_name" class="form-label">First Name</label>
                      <input 
                        type="text" 
                        id="first_name" 
                        bind:value={formData.first_name} 
                        class="form-input"
                      />
                      {#if formErrors.first_name}
                        <p class="form-error">{formErrors.first_name}</p>
                      {/if}
                    </div>
                    
                    <div>
                      <label for="last_name" class="form-label">Last Name</label>
                      <input 
                        type="text" 
                        id="last_name" 
                        bind:value={formData.last_name} 
                        class="form-input"
                      />
                      {#if formErrors.last_name}
                        <p class="form-error">{formErrors.last_name}</p>
                      {/if}
                    </div>
                  </div>
                  
                  <div>
                    <label for="role" class="form-label">Role</label>
                    <select 
                      id="role" 
                      bind:value={formData.role} 
                      class="form-input"
                    >
                      <option value={UserRole.ADMIN}>Admin</option>
                      <option value={UserRole.STAFF}>Staff</option>
                      <option value={UserRole.USER}>Regular User</option>
                    </select>
                    {#if formErrors.role}
                      <p class="form-error">{formErrors.role}</p>
                    {/if}
                  </div>
                  
                  <div class="flex items-center">
                    <input 
                      type="checkbox" 
                      id="is_active" 
                      bind:checked={formData.is_active} 
                      class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label for="is_active" class="ml-2 block text-sm text-gray-900">
                      Active Account
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
            class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm"
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
                Delete User
              </h3>
              <div class="mt-2">
                <p class="text-sm text-gray-500">
                  Are you sure you want to delete the user <strong>{userToDelete?.email}</strong>? This action cannot be undone.
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
