<!--
  Public Chat URL — `/chat/{project_id}`.
  Three render states driven by public-config + login state:
    1. Not available  — deployment off or public URL disabled.
    2. Login required — auth_required=true AND is_logged_in=false.
    3. Chat view      — shared embed iframe (same URL used by every chatbot surface).

  The iframe is always-same-origin with the SvelteKit host, so the path-scoped
  `pchat_<deployment.id>` cookie set by /public-auth/ flows automatically with
  every request it makes. No token plumbing inside the iframe.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import type { PageData } from './$types';

  export let data: PageData;

  let config: any = data.config;
  let available: boolean = data.available;
  let projectId: string = data.projectId;

  // Auth form state
  let username = '';
  let password = '';
  let submitting = false;
  let loginError = '';

  $: authRequired = !!config?.auth_required;
  $: isLoggedIn = !!config?.is_logged_in;
  $: showChat = available && (!authRequired || isLoggedIn);
  $: showLogin = available && authRequired && !isLoggedIn;

  // A short fingerprint of the config values that affect session validity.
  // Whenever the admin flips public_url_enabled or public_url_auth_enabled
  // (or the session is no longer logged in), this value changes and the
  // page hard-reloads so the iframe remounts cleanly.
  function sessionFingerprint(c: any): string {
    if (!c) return 'unavailable';
    return `${c.public_url_enabled ? 1 : 0}:${c.auth_required ? 1 : 0}:${c.is_logged_in ? 1 : 0}`;
  }

  async function refreshConfig() {
    try {
      const resp = await fetch(`/api/workflow-deploy/${projectId}/public-config/`, {
        credentials: 'include',
      });
      if (resp.status === 404) {
        // Admin turned the public URL off — switch to the not-available
        // card. Reload forces the iframe (if any) to unmount immediately.
        if (available) window.location.reload();
        available = false;
        config = null;
        return;
      }
      if (resp.ok) {
        const newConfig = await resp.json();
        const oldPrint = sessionFingerprint(config);
        const newPrint = sessionFingerprint(newConfig);
        config = newConfig;
        available = true;
        if (oldPrint !== 'unavailable' && oldPrint !== newPrint) {
          // Session-affecting transition — reload to guarantee a clean iframe.
          window.location.reload();
        }
      }
    } catch {
      /* leave state unchanged */
    }
  }

  async function submitLogin() {
    if (submitting) return;
    submitting = true;
    loginError = '';
    try {
      const resp = await fetch(`/api/workflow-deploy/${projectId}/public-auth/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (resp.ok) {
        password = '';
        await refreshConfig();
      } else if (resp.status === 429) {
        const body = await resp.json().catch(() => ({}));
        loginError = body.error || 'Too many attempts. Please wait and try again.';
      } else {
        loginError = 'Invalid credentials';
      }
    } catch {
      loginError = 'Could not reach the server. Please try again.';
    } finally {
      submitting = false;
    }
  }

  async function logout() {
    try {
      await fetch(`/api/workflow-deploy/${projectId}/public-logout/`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      /* swallow */
    }
    await refreshConfig();
  }

  // If the user lands here after the cookie expires mid-session (4 h rolling
  // has elapsed), the iframe's own XHR will 401. We pick that up via a simple
  // periodic config refresh so the login screen reappears without a manual
  // page reload.
  onMount(() => {
    const interval = setInterval(refreshConfig, 60 * 1000);
    return () => clearInterval(interval);
  });
</script>

<svelte:head>
  <title>{config?.chatbot_title || 'Chat'}</title>
</svelte:head>

<div class="min-h-screen flex flex-col bg-neutral-50">
  {#if !available}
    <!-- State 1: Not available -->
    <div class="flex-1 flex items-center justify-center p-6">
      <div class="max-w-md text-center bg-white border border-gray-200 rounded-2xl shadow-sm p-8">
        <div class="w-14 h-14 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center text-gray-400">
          <i class="fas fa-plug-circle-xmark text-2xl"></i>
        </div>
        <h1 class="text-xl font-semibold text-gray-900 mb-2">This chat is not available</h1>
        <p class="text-sm text-gray-600">
          The owner hasn't enabled public access, or this link is no longer active.
        </p>
      </div>
    </div>
  {:else if showLogin}
    <!-- State 2: Login required -->
    <div class="flex-1 flex items-center justify-center p-6">
      <div class="w-full max-w-sm bg-white border border-gray-200 rounded-2xl shadow-sm p-8">
        <div class="text-center mb-6">
          {#if config?.logo_url}
            <img src={config.logo_url} alt="" class="mx-auto h-12 w-12 object-contain mb-3" />
          {:else}
            <div
              class="mx-auto w-12 h-12 rounded-xl flex items-center justify-center text-white mb-3"
              style="background: linear-gradient(135deg, {config?.primary_color || '#002147'} 0%, {config?.secondary_color || '#234a7a'} 100%)"
            >
              <i class="fas fa-lock"></i>
            </div>
          {/if}
          <h1 class="text-lg font-semibold text-gray-900">
            {config?.chatbot_title || 'Sign in'}
          </h1>
          <p class="text-xs text-gray-500 mt-1">
            Enter your credentials to start chatting.
          </p>
        </div>
        <form class="space-y-3" on:submit|preventDefault={submitLogin}>
          <div>
            <label class="block text-xs text-gray-600 mb-1" for="pchat-user">Username</label>
            <input
              id="pchat-user"
              type="text"
              bind:value={username}
              autocomplete="username"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-[#002147] focus:border-[#002147]"
              required
            />
          </div>
          <div>
            <label class="block text-xs text-gray-600 mb-1" for="pchat-pass">Password</label>
            <input
              id="pchat-pass"
              type="password"
              bind:value={password}
              autocomplete="current-password"
              class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-[#002147] focus:border-[#002147]"
              required
            />
          </div>
          {#if loginError}
            <div class="rounded-md bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">
              {loginError}
            </div>
          {/if}
          <button
            type="submit"
            disabled={submitting}
            class="w-full rounded-lg bg-[#002147] text-white text-sm font-medium py-2 hover:bg-blue-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  {:else if showChat}
    <!-- State 3: Chat view — iframed /embed/ is the shared chatbot code. -->
    <header class="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white shrink-0">
      <div class="flex items-center gap-3 min-w-0">
        {#if config?.logo_url}
          <img src={config.logo_url} alt="" class="h-8 w-8 object-contain rounded" />
        {:else}
          <div
            class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-semibold shrink-0"
            style="background: linear-gradient(135deg, {config?.primary_color || '#002147'} 0%, {config?.secondary_color || '#234a7a'} 100%)"
          >
            {(config?.chatbot_title || 'A').slice(0, 1).toUpperCase()}
          </div>
        {/if}
        <div class="min-w-0">
          <div class="font-semibold text-gray-900 text-sm truncate">
            {config?.chatbot_title || 'AI Assistant'}
          </div>
          {#if config?.chatbot_subtitle}
            <div class="text-xs text-gray-500 truncate">{config.chatbot_subtitle}</div>
          {/if}
        </div>
      </div>
      {#if authRequired}
        <button
          type="button"
          on:click={logout}
          class="text-xs text-gray-500 hover:text-[#002147] px-3 py-1.5 rounded-md hover:bg-gray-100 transition-colors inline-flex items-center"
        >
          <i class="fas fa-sign-out-alt mr-1.5"></i>Sign out
        </button>
      {/if}
    </header>
    <main class="flex-1 min-h-0">
      <iframe
        title="Chat"
        src="/api/workflow-deploy/{projectId}/embed/?hide_header=1"
        class="w-full h-full block border-0"
        style="height: calc(100vh - 49px);"
      ></iframe>
    </main>
  {/if}
</div>
