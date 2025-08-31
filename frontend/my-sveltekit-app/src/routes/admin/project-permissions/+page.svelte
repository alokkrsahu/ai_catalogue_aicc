<!-- src/routes/admin/project-permissions/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { 
    getUsers, 
    getUserProjectPermissions,
    updateUserProjectPermissions 
  } from '$lib/services/api';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import type { User, IntelliDocProject } from '$lib/types';
  import { toasts } from '$lib/stores/toast';

  let users: User[] = [];
  let projects: IntelliDocProject[] = [];
  let selectedUser: User | null = null;
  let selectedUserId: string = ''; // For select binding
  let selectedUserPermissions: string[] = []; // Using project_id (UUID strings)
  let viewMode: 'grid' | 'list' = 'list';
  let loading = {
    users: true,
    projects: true,
    permissions: false
  };
  let saving = false;
  let error = '';

  onMount(async () => {
    console.log('🚀 Starting to load users and projects...');
    
    try {
      // Load users first
      console.log('📤 Loading users...');
      const usersResponse = await getUsers();
      users = usersResponse;
      console.log('✅ Users loaded:', users.length);
      loading.users = false;
      
      // Then load projects
      console.log('📤 Loading projects...');
      const projectsResponse = await cleanUniversalApi.getAllProjects();
      console.log('📥 Raw projects response:', projectsResponse);
      
      // Handle different response formats
      if (projectsResponse && projectsResponse.projects) {
        projects = projectsResponse.projects;
        console.log('✅ Projects extracted from .projects property:', projects.length);
      } else if (Array.isArray(projectsResponse)) {
        projects = projectsResponse;
        console.log('✅ Projects from array response:', projects.length);
      } else {
        projects = [];
        console.warn('❌ Unexpected projects response format:', projectsResponse);
        error = 'Unexpected response format from projects API';
      }
      
      console.log('📋 Final projects list:', projects);
      
    } catch (err) {
      console.error('❌ Failed to load data:', err);
      if (err.message.includes('Authentication')) {
        error = 'Authentication failed. Please log in again.';
      } else if (err.message.includes('fetch')) {
        error = 'Network error. Please check your connection and try again.';
      } else {
        error = `Failed to load data: ${err.message}`;
      }
    } finally {
      loading.users = false;
      loading.projects = false;
    }
  });

  async function handleUserSelect(userId: string) {
    console.log('🎯 User selected:', userId);
    selectedUserId = userId;
    
    if (!userId) {
      selectedUser = null;
      selectedUserPermissions = [];
      return;
    }

    try {
      loading.permissions = true;
      selectedUser = users.find(u => u.id === parseInt(userId)) || null;
      
      if (selectedUser) {
        // For now, we'll check each project individually to see if user has permission
        // This is not optimal but works for the current API structure
        selectedUserPermissions = [];
        
        for (const project of projects) {
          try {
            const permissions = await getUserProjectPermissions(project.project_id);
            // Check if this user is in the permissions list
            const hasPermission = permissions.some(p => p.user === selectedUser.id);
            if (hasPermission) {
              selectedUserPermissions.push(project.project_id);
            }
          } catch (err) {
            // If project permission check fails, assume no permission
            console.warn(`Failed to check permissions for project ${project.project_id}:`, err);
          }
        }
        
        console.log('User permissions loaded:', selectedUserPermissions);
      }
    } catch (err) {
      console.error('Failed to load user permissions:', err);
      toasts.error('Failed to load user permissions');
    } finally {
      loading.permissions = false;
    }
  }

  function handlePermissionToggle(projectId: string) {
    if (selectedUserPermissions.includes(projectId)) {
      selectedUserPermissions = selectedUserPermissions.filter(id => id !== projectId);
    } else {
      selectedUserPermissions = [...selectedUserPermissions, projectId];
    }
  }

  function selectAllPermissions() {
    selectedUserPermissions = projects.map(p => p.project_id);
  }

  function deselectAllPermissions() {
    selectedUserPermissions = [];
  }

  async function savePermissions() {
    if (!selectedUser) return;

    try {
      saving = true;
      
      // Update permissions for each project based on current selections
      const updatePromises = [];
      
      for (const project of projects) {
        const shouldHavePermission = selectedUserPermissions.includes(project.project_id);
        
        // Get current permissions for this project
        const currentPermissions = await getUserProjectPermissions(project.project_id);
        const currentUserIds = currentPermissions.map(p => p.user);
        
        let newUserIds = [...currentUserIds];
        
        if (shouldHavePermission && !currentUserIds.includes(selectedUser.id)) {
          // Add user to permissions
          newUserIds.push(selectedUser.id);
        } else if (!shouldHavePermission && currentUserIds.includes(selectedUser.id)) {
          // Remove user from permissions
          newUserIds = newUserIds.filter(id => id !== selectedUser.id);
        }
        
        // Only update if there's a change
        if (JSON.stringify(currentUserIds.sort()) !== JSON.stringify(newUserIds.sort())) {
          updatePromises.push(
            updateUserProjectPermissions(project.project_id, newUserIds)
          );
        }
      }
      
      // Execute all updates
      await Promise.all(updatePromises);

      toasts.success(`Updated project permissions for ${selectedUser.email}`);
    } catch (err) {
      console.error('Failed to save permissions:', err);
      toasts.error(`Failed to save permissions: ${err.message}`);
    } finally {
      saving = false;
    }
  }

  $: canSave = selectedUser && !saving;
</script>

<div class="admin-page">
  <div class="page-header">
    <h1>Project Permissions</h1>
    <p class="page-description">
      Assign project access permissions to individual users. Users will only be able to see and access projects they have permission for.
    </p>
  </div>

  {#if error}
    <div class="alert alert-error">
      <i class="fas fa-exclamation-triangle"></i>
      {error}
    </div>
  {/if}

  <div class="content-grid">
    <!-- User Selection Panel -->
    <div class="selection-panel">
      <div class="panel-header">
        <h2>Select User</h2>
        <i class="fas fa-user"></i>
      </div>
      
      {#if loading.users}
        <div class="loading-spinner">
          <i class="fas fa-spinner fa-spin"></i>
          Loading users...
        </div>
      {:else if users.length === 0}
        <div class="empty-state">
          <i class="fas fa-users"></i>
          <p>No users found</p>
        </div>
      {:else}
        <div class="user-selector">
          <select 
            bind:value={selectedUserId}
            on:change={(e) => handleUserSelect(e.target.value)}
            class="form-select"
          >
            <option value="">Select a user...</option>
            {#each users as user}
              <option value={user.id}>
                {user.email} ({user.first_name} {user.last_name})
              </option>
            {/each}
          </select>
        </div>
      {/if}
    </div>

    <!-- Project Permissions Panel -->
    <div class="permissions-panel">
      <div class="panel-header">
        <h2>Project Permissions</h2>
        <div class="panel-controls">
          {#if selectedUser}
            <div class="view-toggle">
              <button 
                class="toggle-btn {viewMode === 'grid' ? 'active' : ''}"
                on:click={() => viewMode = 'grid'}
                title="Grid view"
              >
                <i class="fas fa-th"></i>
              </button>
              <button 
                class="toggle-btn {viewMode === 'list' ? 'active' : ''}"
                on:click={() => viewMode = 'list'}
                title="List view"
              >
                <i class="fas fa-list"></i>
              </button>
            </div>
          {/if}
        </div>
      </div>

      {#if !selectedUser}
        <div class="empty-state">
          <i class="fas fa-hand-pointer"></i>
          <p>Select a user to manage their project permissions</p>
          <div class="mt-4 text-sm text-gray-500">
            <p>Debug Info:</p>
            <p>Users loaded: {users.length}</p>
            <p>Projects loaded: {projects.length}</p>
            <p>Loading state: {JSON.stringify(loading)}</p>
            {#if error}
              <p class="text-red-500">Error: {error}</p>
            {/if}
          </div>
        </div>
      {:else if loading.permissions}
        <div class="loading-spinner">
          <i class="fas fa-spinner fa-spin"></i>
          Loading permissions...
        </div>
      {:else if loading.projects}
        <div class="loading-spinner">
          <i class="fas fa-spinner fa-spin"></i>
          Loading projects...
        </div>
      {:else if projects.length === 0}
        <div class="empty-state">
          <i class="fas fa-folder-open"></i>
          <p>No projects available</p>
          <p class="text-sm text-gray-500 mt-2">
            Debug: Users loaded: {users.length}, Projects loaded: {projects.length}, Loading state: {JSON.stringify(loading)}
          </p>
        </div>
      {:else}
        <div class="permissions-content">
          <!-- Bulk Actions -->
          <div class="bulk-actions">
            <button 
              class="bulk-btn"
              on:click={selectAllPermissions}
              disabled={saving}
            >
              <i class="fas fa-check-square"></i>
              Select All
            </button>
            <button 
              class="bulk-btn"
              on:click={deselectAllPermissions}
              disabled={saving}
            >
              <i class="fas fa-square"></i>
              Deselect All
            </button>
            <span class="selected-count">
              {selectedUserPermissions.length} of {projects.length} selected
            </span>
          </div>

          <!-- Projects Grid/List -->
          <div class="projects-container {viewMode}">
            {#each projects as project}
              <label class="project-item {selectedUserPermissions.includes(project.project_id) ? 'selected' : ''}">
                <input
                  type="checkbox"
                  checked={selectedUserPermissions.includes(project.project_id)}
                  on:change={() => handlePermissionToggle(project.project_id)}
                  disabled={saving}
                />
                <div class="project-info">
                  <div class="project-icon">
                    <i class="fas {project.icon_class}"></i>
                  </div>
                  <div class="project-details">
                    <div class="project-name">{project.name}</div>
                    <div class="project-meta">
                      <span class="project-type">{project.template_type}</span>
                      {#if viewMode === 'list'}
                        <span class="project-description">{project.description}</span>
                      {/if}
                    </div>
                  </div>
                </div>
                {#if selectedUserPermissions.includes(project.project_id)}
                  <div class="permission-indicator">
                    <i class="fas fa-check-circle"></i>
                  </div>
                {/if}
              </label>
            {/each}
          </div>

          <!-- Save Button -->
          <div class="save-section">
            <button 
              class="save-btn"
              on:click={savePermissions}
              disabled={!canSave}
            >
              {#if saving}
                <i class="fas fa-spinner fa-spin"></i>
                Saving...
              {:else}
                <i class="fas fa-save"></i>
                Save Permissions
              {/if}
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .admin-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px;
  }

  .page-header {
    margin-bottom: 32px;
  }

  .page-header h1 {
    font-size: 2rem;
    font-weight: 700;
    color: #002147;
    margin-bottom: 8px;
  }

  .page-description {
    color: #6b7280;
    font-size: 1rem;
    margin: 0;
  }

  .content-grid {
    display: grid;
    grid-template-columns: 350px 1fr;
    gap: 32px;
    align-items: start;
  }

  .selection-panel,
  .permissions-panel {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.1);
    overflow: hidden;
  }

  .panel-header {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
    padding: 20px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .panel-header h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0;
  }

  .panel-controls {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .view-toggle {
    display: flex;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .toggle-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.7);
    padding: 8px 12px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .toggle-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }

  .toggle-btn.active {
    background: rgba(255, 255, 255, 0.2);
    color: white;
  }

  .user-selector {
    padding: 24px;
  }

  .form-select {
    width: 100%;
    padding: 12px 16px;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    font-size: 14px;
    background: white;
    transition: border-color 0.2s ease;
  }

  .form-select:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }

  .permissions-content {
    padding: 24px;
  }

  .bulk-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e5e7eb;
  }

  .bulk-btn {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    color: #475569;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .bulk-btn:hover:not(:disabled) {
    background: #e2e8f0;
  }

  .bulk-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .selected-count {
    margin-left: auto;
    font-size: 14px;
    color: #6b7280;
    font-weight: 500;
  }

  .projects-container {
    max-height: 60vh;
    overflow-y: auto;
  }

  .projects-container.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  .projects-container.list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .project-item {
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .project-item:hover {
    border-color: #002147;
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.1);
  }

  .project-item.selected {
    border-color: #10b981;
    background: #f0fdf4;
  }

  .project-item input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: #10b981;
  }

  .project-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
  }

  .project-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 16px;
  }

  .project-details {
    flex: 1;
  }

  .project-name {
    font-weight: 600;
    color: #111827;
    margin-bottom: 4px;
  }

  .project-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  .project-type {
    background: #e0f2fe;
    color: #0277bd;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 500;
  }

  .project-description {
    color: #6b7280;
    font-size: 13px;
  }

  .permission-indicator {
    color: #10b981;
    font-size: 18px;
  }

  .save-section {
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid #e5e7eb;
    display: flex;
    justify-content: flex-end;
  }

  .save-btn {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .save-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
  }

  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  .loading-spinner,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: #6b7280;
  }

  .loading-spinner i,
  .empty-state i {
    font-size: 2rem;
    margin-bottom: 12px;
    color: #9ca3af;
  }

  .alert {
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .alert-error {
    background: #fef2f2;
    color: #dc2626;
    border: 1px solid #fecaca;
  }

  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
      gap: 24px;
    }
  }

  @media (max-width: 768px) {
    .admin-page {
      padding: 16px;
    }
    
    .projects-container.grid {
      grid-template-columns: 1fr;
    }
  }
</style>