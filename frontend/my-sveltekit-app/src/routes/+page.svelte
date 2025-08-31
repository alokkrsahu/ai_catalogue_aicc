<!-- src/routes/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { isAuthenticated, user } from '$lib/stores/auth';
  import { getMyDashboardIcons } from '$lib/services/api';
  import type { DashboardIcon } from '$lib/types';


  let icons: DashboardIcon[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    console.log("Authentication status:", $isAuthenticated);
    // Note: Consider investigating why $user might be undefined here, as seen in logs.
    // It might be a timing issue with auth state propagation.
    console.log("User data on mount:", $user);

    if (!$isAuthenticated) {
      console.log("Not authenticated, redirecting to login");
      goto('/login');
      return;
    }

    try {
      const response = await getMyDashboardIcons();
      console.log('API Response:', response);

      if (Array.isArray(response)) {
        icons = response;
      } else {
        // Handle cases where the API might not return a valid array
        console.error('API did not return a valid array:', response);
        icons = [];
        error = 'Received invalid data format for dashboard icons.';
      }
      console.log('Icons loaded:', icons.length);
    } catch (err) {
      console.error('Failed to load dashboard icons:', err);
      // Provide a more specific error message if possible, e.g., from err.message
      error = `Failed to load dashboard icons. Please refresh the page. (${err instanceof Error ? err.message : 'Unknown error'})`;
    } finally {
      loading = false;
    }
  });

  // This function determines the icon color class and container styling
  function getIconColorClass(color: string): string {
    // Map the new ColorTheme choices to CSS icon color classes
    const iconColorMap: {[key: string]: string} = {
      // Oxford University Colors
      'oxford-blue': 'icon-oxford-blue',
      'oxford-blue-light': 'icon-oxford-blue-light',
      'oxford-blue-dark': 'icon-oxford-blue-dark',
      
      // Academic Colors
      'academic-gold': 'icon-academic-gold',
      'antique-gold': 'icon-antique-gold',
      
      // Classic Academic Colors
      'burgundy': 'icon-burgundy',
      'forest-green': 'icon-forest-green', 
      'royal-purple': 'icon-royal-purple',
      'crimson': 'icon-crimson',
      
      // Professional Neutrals
      'charcoal': 'icon-charcoal',
      'slate': 'icon-slate',
      'pearl': 'icon-pearl',
      'cream': 'icon-cream',
      
      // Status Colors
      'success': 'icon-success',
      'warning': 'icon-warning',
      'error': 'icon-error',
      'info': 'icon-info',
      
      // Vibrant Options
      'emerald': 'icon-emerald',
      'sapphire': 'icon-sapphire',
      'ruby': 'icon-ruby',
      'amber': 'icon-amber',
      
      // Modern Variants
      'teal': 'icon-teal',
      'indigo': 'icon-indigo',
      'coral': 'icon-coral',
      'mint': 'icon-mint',
      
      // Legacy color fallbacks (for backward compatibility)
      'blue': 'icon-oxford-blue',
      'green': 'icon-forest-green',
      'red': 'icon-crimson',
      'yellow': 'icon-amber',
      'purple': 'icon-royal-purple',
      'orange': 'icon-coral',
      'pink': 'icon-ruby',
      'gray': 'icon-slate',
      'grey': 'icon-slate'
    };
    
    return iconColorMap[color] || 'icon-oxford-blue'; // Default to Oxford blue
  }
  
  function getContainerClasses(color: string): string {
    // Container styling that works with all color themes
    return 'dashboard-icon-oxford hover:shadow-oxford-lg transition-all duration-300';
  }

  // No getSvgPath function needed as we are using Font Awesome classes directly
</script>



<div class="dashboard-oxford">
  <main>
    <div class="container-oxford section-oxford">
      {#if $user}
        <div class="mb-8">
          <h1 class="heading-oxford-1">
            <i class="fas fa-university mr-3" style="color: #002147;" aria-hidden="true"></i>
            Welcome, {$user.first_name || $user.email || 'User'}!
          </h1>
          <p class="text-oxford-secondary">
            Here are the AI powered Apps available to you:
          </p>
        </div>

        {#if loading}
          <div class="text-center py-12">
            <div class="spinner-oxford mx-auto"></div>
            <p class="mt-4 text-oxford-secondary">Loading your dashboard...</p>
          </div>
        {:else if error}
          <div class="alert-oxford-error">
            <i class="fas fa-exclamation-triangle mr-2" aria-hidden="true"></i>
            <strong>Error:</strong> {error}
          </div>
        {:else if icons.length === 0}
          <div class="alert-oxford-warning">
            <i class="fas fa-info-circle mr-2" aria-hidden="true"></i>
            <strong>No Access:</strong> You don't have access to any dashboard features yet. Please contact an administrator.
          </div>
        {:else}
          <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {#each icons as icon (icon.id)}
              <a
                href={icon.route}
                class="{getContainerClasses(icon.color)} focus-oxford"
                aria-label="Open {icon.name}: {icon.description}"
              >
                <div class="icon mb-3">
                  <i class="fas {icon.icon_class} {getIconColorClass(icon.color)} text-3xl" aria-hidden="true"></i>
                </div>
                <div class="title">{icon.name}</div>
                <div class="description">{icon.description}</div>
              </a>
            {/each}
          </div>
        {/if}
      {:else if !loading}
        <div class="alert-oxford-warning">
          <i class="fas fa-exclamation-triangle mr-2" aria-hidden="true"></i>
          <strong>Authentication Required:</strong> User information is not available. Please try logging in again or contact support.
        </div>
      {/if}
    </div>
  </main>
</div>
