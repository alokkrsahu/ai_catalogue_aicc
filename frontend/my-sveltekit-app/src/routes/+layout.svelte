<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import "../app.css";
  import ToastContainer from '$lib/components/ToastContainer.svelte';
  import Navigation from '$lib/components/Navigation.svelte';
  import UniversalThemeProvider from '$lib/components/UniversalThemeProvider.svelte';
  import { page } from '$app/stores';

  // Hide admin chrome (top nav) on public-facing routes so end-users
  // visiting /chat/<project_id> see only the chatbot.
  $: isPublicChatRoute = $page.url.pathname.startsWith('/chat/');
</script>

<UniversalThemeProvider>
  {#if !isPublicChatRoute}
    <Navigation />
  {/if}
  <ToastContainer />
  <slot />
</UniversalThemeProvider>
