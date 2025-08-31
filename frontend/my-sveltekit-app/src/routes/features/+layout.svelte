<!-- src/routes/features/+layout.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { isAuthenticated } from '$lib/stores/auth';

  import { page } from '$app/stores';
</script>

<svelte:head>
  {#if $page.url.pathname === '/features/profile'}
    <title>User Profile</title>
  {:else}
    <title>Feature</title>
  {/if}
</svelte:head>



<div class="min-h-screen bg-gray-100 w-full">
  <header class="bg-white shadow w-full">
    <div class="w-full py-6 px-6">
      <slot name="header">
        {#if $page.url.pathname === '/features/profile'}
          <h1 class="text-3xl font-bold text-gray-900">
            User Profile
          </h1>
        {:else}
          <h1 class="text-3xl font-bold text-gray-900">
            Feature
          </h1>
        {/if}
      </slot>
    </div>
  </header>
  <main class="w-full min-h-screen">
    <slot />
  </main>
</div>
