<!-- src/lib/components/DarkModeToggle.svelte -->
<script lang="ts">
  import { darkMode } from '$lib/stores/darkMode';
  import { onMount } from 'svelte';

  onMount(() => {
    // Initialize dark mode on component mount
    darkMode.init();
  });

  function toggleDarkMode() {
    darkMode.toggle();
  }
</script>

<button
  class="dark-mode-toggle text-gray-300 hover:text-white"
  on:click={toggleDarkMode}
  aria-label={$darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
  title={$darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
>
  {#if $darkMode}
    <!-- Sun icon for light mode -->
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      class="w-5 h-5"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
      />
    </svg>
  {:else}
    <!-- Moon icon for dark mode -->
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      class="w-5 h-5"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
      />
    </svg>
  {/if}
</button>
