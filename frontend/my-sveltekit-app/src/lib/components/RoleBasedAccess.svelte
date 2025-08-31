<!-- Role-Based Access Control Component -->
<!-- src/lib/components/RoleBasedAccess.svelte -->
<script lang="ts">
  import { isAdmin, user, isAuthenticated } from '$lib/stores/auth';
  
  export let requiredRole: 'ADMIN' | 'STAFF' | 'USER' = 'USER';
  export let requireAuth: boolean = true;
  export let fallback: boolean = false; // Show fallback content instead of hiding
  export let fallbackMessage: string = 'Access restricted';
  
  // Role hierarchy: ADMIN > STAFF > USER
  const roleHierarchy = {
    'ADMIN': 3,
    'STAFF': 2,
    'USER': 1
  };
  
  $: currentUserRole = $user?.role || 'USER';
  $: hasAccess = checkAccess(currentUserRole, requiredRole, $isAuthenticated, requireAuth);
  
  function checkAccess(userRole: string, required: string, authenticated: boolean, needsAuth: boolean): boolean {
    // Check authentication first
    if (needsAuth && !authenticated) {
      return false;
    }
    
    // Check role hierarchy
    const userRoleLevel = roleHierarchy[userRole as keyof typeof roleHierarchy] || 0;
    const requiredRoleLevel = roleHierarchy[required] || 0;
    
    return userRoleLevel >= requiredRoleLevel;
  }
</script>

{#if hasAccess}
  <slot />
{:else if fallback}
  <div class="access-restricted">
    <i class="fas fa-lock text-gray-400"></i>
    <span class="text-gray-500 text-sm">{fallbackMessage}</span>
  </div>
{/if}

<style>
  .access-restricted {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    background-color: #f9fafb;
    border: 1px dashed #d1d5db;
    border-radius: 0.375rem;
    justify-content: center;
  }
</style>