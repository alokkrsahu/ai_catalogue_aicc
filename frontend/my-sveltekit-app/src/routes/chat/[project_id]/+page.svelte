<!--
  Public Chat URL — `/chat/{project_id}`.
  Three render states driven by public-config + login state:
    1. Not available  — deployment off or public URL disabled.
    2. Login required — auth_required=true AND is_logged_in=false.
    3. Chat view      — shared embed iframe (same URL used by every chatbot surface).

  When auth_required=true the chat view also renders a per-browser conversation
  sidebar (localStorage-backed) so end users can keep multiple parallel threads
  the same way admins do in-app. Anonymous deployments keep the single-thread
  behaviour to avoid an unfamiliar UI on landing-page chatbots.

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
  // Sidebar only when password auth is active. Anonymous public deployments
  // keep the single-thread iframe — adding a sidebar there would be a
  // surprising UI on a landing-page chatbot.
  $: showSidebar = showChat && authRequired && isLoggedIn;

  // Conversation list state (mirrors the in-app Chatbot tab pattern, but with
  // a distinct localStorage key so the admin's in-app sessions never leak in).
  type ChatbotSessionMeta = {
    id: string;
    label: string;
    createdAt: string;
    preview?: string;
    updatedAt?: string;
  };
  let chatbotSessions: ChatbotSessionMeta[] = [];
  let activeChatbotSessionId: string | null = null;
  let lastChatbotStorageKey = '';
  let mobileChatbotNavOpen = false;
  let renamingSessionId: string | null = null;
  let renameInputValue = '';

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

  // ─── Conversation list management ────────────────────────────────────
  // Per-browser localStorage. Distinct key from the in-app sidebar so the
  // two surfaces never share state.
  function makeChatbotStorageKey(): string {
    const deploymentKey = config?.deployment_id || 'default';
    return `pchat_sessions_${projectId}_${deploymentKey}`;
  }

  function initializeChatbotSessionsForStorageKey(storageKey: string) {
    if (typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as ChatbotSessionMeta[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          chatbotSessions = parsed;
          const current = activeChatbotSessionId;
          const stillValid =
            current !== null && parsed.some((s) => s.id === current);
          if (!stillValid) {
            activeChatbotSessionId = parsed[0].id;
          }
          return;
        }
      }
    } catch (e) {
      console.warn('PCHAT: Failed to parse stored sessions', e);
    }

    const id = `sess_${Math.random().toString(36).slice(2)}`;
    const createdAt = new Date().toISOString();
    chatbotSessions = [{ id, label: 'Conversation 1', createdAt }];
    activeChatbotSessionId = id;
    persistChatbotSessions();
  }

  function persistChatbotSessions() {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(
        makeChatbotStorageKey(),
        JSON.stringify(chatbotSessions),
      );
    } catch (e) {
      console.warn('PCHAT: Failed to persist sessions', e);
    }
  }

  function handleNewChatbotConversation() {
    const index = chatbotSessions.length + 1;
    const id = `sess_${Math.random().toString(36).slice(2)}`;
    const createdAt = new Date().toISOString();
    chatbotSessions = [
      { id, label: `Conversation ${index}`, createdAt },
      ...chatbotSessions,
    ];
    activeChatbotSessionId = id;
    mobileChatbotNavOpen = false;
    persistChatbotSessions();
  }

  function selectChatbotSession(sessionId: string) {
    activeChatbotSessionId = sessionId;
    mobileChatbotNavOpen = false;
  }

  function startRenameSession(sessionId: string) {
    const s = chatbotSessions.find((x) => x.id === sessionId);
    if (!s) return;
    renamingSessionId = sessionId;
    renameInputValue = s.label;
  }

  function commitRenameSession() {
    if (!renamingSessionId) return;
    const trimmed = renameInputValue.trim();
    if (!trimmed) {
      renamingSessionId = null;
      return;
    }
    const s = chatbotSessions.find((x) => x.id === renamingSessionId);
    if (s) {
      s.label = trimmed;
      chatbotSessions = [...chatbotSessions];
      persistChatbotSessions();
    }
    renamingSessionId = null;
  }

  function cancelRenameSession() {
    renamingSessionId = null;
  }

  function deleteChatbotSession(sessionId: string) {
    chatbotSessions = chatbotSessions.filter((s) => s.id !== sessionId);
    if (activeChatbotSessionId === sessionId) {
      activeChatbotSessionId =
        chatbotSessions.length > 0 ? chatbotSessions[0].id : null;
      if (!activeChatbotSessionId) {
        handleNewChatbotConversation();
        return;
      }
    }
    persistChatbotSessions();
  }

  function formatChatbotSessionDate(iso: string): string {
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return '';
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  }

  // Listen for the iframe's session_message_sent event so we can update the
  // sidebar preview as soon as the user sends a message. Reject cross-origin
  // messages — the embed is same-origin so spoofed messages from elsewhere
  // would otherwise be able to mutate localStorage.
  function handleIframeMessage(event: MessageEvent) {
    if (event.origin !== window.location.origin) return;
    const data: any = event.data;
    if (!data || typeof data !== 'object') return;
    if (data.type !== 'session_message_sent') return;
    const sid = data.sessionId;
    const userText = (data.userText || '').toString();
    if (!sid) return;
    const idx = chatbotSessions.findIndex((s) => s.id === sid);
    if (idx === -1) return;
    chatbotSessions[idx] = {
      ...chatbotSessions[idx],
      preview: userText.slice(0, 80),
      updatedAt: data.timestamp || new Date().toISOString(),
    };
    chatbotSessions = [...chatbotSessions];
    persistChatbotSessions();
  }

  // Initialize sessions whenever the (projectId, deployment) tuple changes
  // and we're in a state that shows the sidebar.
  $: if (showSidebar && typeof window !== 'undefined') {
    const storageKey = makeChatbotStorageKey();
    if (storageKey !== lastChatbotStorageKey) {
      lastChatbotStorageKey = storageKey;
      initializeChatbotSessionsForStorageKey(storageKey);
    }
  }

  // If the user lands here after the cookie expires mid-session (4 h rolling
  // has elapsed), the iframe's own XHR will 401. We pick that up via a simple
  // periodic config refresh so the login screen reappears without a manual
  // page reload.
  onMount(() => {
    const interval = setInterval(refreshConfig, 60 * 1000);
    window.addEventListener('message', handleIframeMessage);
    return () => {
      clearInterval(interval);
      window.removeEventListener('message', handleIframeMessage);
    };
  });
</script>

<svelte:head>
  <title>{config?.chatbot_title || 'Chat'}</title>
</svelte:head>

<div class="public-chat-shell flex flex-col bg-neutral-50">
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
              class="w-full rounded-lg border border-gray-300 px-3 py-3 min-h-[44px] text-base sm:text-sm focus:ring-[#002147] focus:border-[#002147]"
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
              class="w-full rounded-lg border border-gray-300 px-3 py-3 min-h-[44px] text-base sm:text-sm focus:ring-[#002147] focus:border-[#002147]"
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
            class="w-full rounded-lg bg-[#002147] text-white text-sm font-medium py-3 min-h-[44px] hover:bg-blue-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
        {#if showSidebar}
          <!-- Mobile-only hamburger to open the conversation drawer. -->
          <button
            type="button"
            class="md:hidden inline-flex items-center justify-center w-11 h-11 rounded-lg text-[#002147] hover:bg-gray-100"
            aria-label="Open conversations"
            on:click={() => (mobileChatbotNavOpen = true)}
          >
            <i class="fas fa-bars text-base"></i>
          </button>
        {/if}
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
          class="text-xs text-gray-500 hover:text-[#002147] px-3 py-2 min-h-[44px] rounded-md hover:bg-gray-100 transition-colors inline-flex items-center"
        >
          <i class="fas fa-sign-out-alt mr-1.5"></i>Sign out
        </button>
      {/if}
    </header>
    <main class="flex-1 min-h-0 flex">
      {#if showSidebar}
        {#if mobileChatbotNavOpen}
          <button
            type="button"
            aria-label="Close conversations"
            class="md:hidden fixed inset-0 z-30 bg-black/40"
            on:click={() => (mobileChatbotNavOpen = false)}
          ></button>
        {/if}
        <aside
          class="pchat-conv-rail {mobileChatbotNavOpen ? 'mobile-open' : ''} bg-white border-r border-slate-200 flex flex-col md:w-64 md:shrink-0 md:translate-x-0"
          aria-label="Conversations"
        >
          <div class="p-3 border-b border-slate-200 shrink-0">
            <button
              type="button"
              class="w-full inline-flex items-center justify-center px-3 py-3 min-h-[44px] text-sm font-medium bg-[#002147] text-white rounded-lg hover:bg-blue-900 transition-colors shadow-sm"
              on:click={handleNewChatbotConversation}
              title="Start a new conversation"
            >
              <i class="fas fa-plus mr-2"></i>
              New conversation
            </button>
          </div>
          <nav class="flex-1 min-h-0 overflow-y-auto p-2 space-y-0.5">
            {#each chatbotSessions as session (session.id)}
              {#if renamingSessionId === session.id}
                <div class="px-2 py-1.5">
                  <!-- svelte-ignore a11y-autofocus -->
                  <input
                    type="text"
                    class="w-full text-sm rounded-md border border-slate-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-[#002147] focus:border-transparent"
                    bind:value={renameInputValue}
                    on:keydown={(e) => {
                      if (e.key === 'Enter') commitRenameSession();
                      if (e.key === 'Escape') cancelRenameSession();
                    }}
                    on:blur={commitRenameSession}
                    autofocus
                  />
                </div>
              {:else}
                <div class="relative group">
                  <button
                    type="button"
                    class="w-full text-left rounded-lg px-3 py-3 pr-8 text-sm transition-colors min-h-[44px]
                      {activeChatbotSessionId === session.id
                        ? 'bg-slate-100 text-[#002147] font-medium'
                        : 'text-gray-700 hover:bg-slate-50'}"
                    on:click={() => selectChatbotSession(session.id)}
                  >
                    <span class="block truncate">{session.label}</span>
                    {#if session.preview}
                      <span class="block text-xs text-gray-400 mt-0.5 truncate">{session.preview}</span>
                    {:else if session.createdAt}
                      <span class="block text-xs text-gray-400 mt-0.5">{formatChatbotSessionDate(session.createdAt)}</span>
                    {/if}
                  </button>
                  <div class="absolute right-1 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5">
                    <button
                      type="button"
                      class="p-1 rounded text-gray-400 hover:text-[#002147] hover:bg-slate-200 transition-colors"
                      on:click|stopPropagation={() => startRenameSession(session.id)}
                      title="Rename"
                    ><i class="fas fa-pen text-[10px]"></i></button>
                    <button
                      type="button"
                      class="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                      on:click|stopPropagation={() => deleteChatbotSession(session.id)}
                      title="Delete"
                    ><i class="fas fa-trash text-[10px]"></i></button>
                  </div>
                </div>
              {/if}
            {/each}
          </nav>
        </aside>
      {/if}
      <div class="flex-1 min-w-0 min-h-0">
        {#if showSidebar}
          {#key activeChatbotSessionId}
            <iframe
              title="Chat"
              src={`/api/workflow-deploy/${projectId}/embed/?hide_header=1${activeChatbotSessionId ? `&session_id=${activeChatbotSessionId}` : ''}`}
              class="public-chat-iframe w-full h-full block border-0"
            ></iframe>
          {/key}
        {:else}
          <iframe
            title="Chat"
            src="/api/workflow-deploy/{projectId}/embed/?hide_header=1"
            class="public-chat-iframe w-full h-full block border-0"
          ></iframe>
        {/if}
      </div>
    </main>
  {/if}
</div>

<style>
  /* Use dynamic viewport units so the layout shrinks correctly when the
     mobile browser chrome shows/hides and when the soft keyboard opens.
     Falls back to vh on older browsers; min-height: -webkit-fill-available
     covers iOS Safari versions before dvh support landed. */
  .public-chat-shell {
    min-height: 100vh;
    min-height: 100dvh;
    min-height: -webkit-fill-available;
    /* Keep the header's top padding clear of the iOS notch when the page
       is in viewport-fit=cover mode (set via the iframe's viewport meta;
       this layer sits above the iframe and benefits too). */
    padding-top: env(safe-area-inset-top);
  }
  .public-chat-iframe {
    height: calc(100vh - 49px);
    height: calc(100dvh - 49px);
  }

  /* Conversation rail: drawer on mobile, sticky aside on desktop. */
  .pchat-conv-rail {
    position: fixed;
    inset: 0 auto 0 0;
    width: 80%;
    max-width: 320px;
    z-index: 40;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
    box-shadow: 4px 0 16px rgba(0, 0, 0, 0.08);
  }
  .pchat-conv-rail.mobile-open {
    transform: translateX(0);
  }
  @media (min-width: 768px) {
    .pchat-conv-rail {
      position: relative;
      inset: auto;
      width: 16rem;
      max-width: none;
      transform: none;
      box-shadow: none;
      z-index: 0;
    }
  }
</style>
