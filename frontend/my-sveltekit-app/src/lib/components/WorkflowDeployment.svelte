<!-- WorkflowDeployment.svelte - Workflow Deployment Component -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { get } from 'svelte/store';
  import authStore from '$lib/stores/auth';
  
  export let project: any;
  export let projectId: string;
  
  // Component state
  let deployment: any = null;
  let workflows: any[] = [];
  let selectedWorkflowId: string = '';
  let isActive = false;
  let rateLimitPerMinute = 10;
  let allowedOrigins: any[] = [];
  let loading = false;
  let saving = false;
  
  // Origin management
  let newOrigin = '';
  let newOriginRateLimit = 10;
  let showAddOrigin = false;
  
  // Endpoint URL
  let endpointUrl = '';
  const GREETING_MAX_LENGTH = 2500;
  let initialGreeting = 'Hi! I am your AI assistant.';
  
  // Chatbot branding customization
  let chatbotTitle = 'AI Assistant';
  let chatbotSubtitle = 'Powered by AICC IntelliDoc';
  let primaryColor = '#ffffff';
  let secondaryColor = '#ffffff';
  let logoUrl = '';
  let fontColor = '#000000';
  let fileUploadsEnabled = false;

  // Public Chat URL — hosted /chat/{project_id} page. Credentials here are
  // strictly scoped: they authorize only this deployment's public chat and
  // cannot grant access to any other part of the system.
  let publicUrlEnabled = false;
  let publicUrlAuthEnabled = false;
  let publicUrlUsername = '';
  let publicUrlPassword = '';      // plaintext entered by admin; only sent on save when non-empty
  let publicUrlPasswordSet = false;  // mirrors server-side "hash exists" flag
  let publicUrlEnabledSaving = false;  // separate state so other buttons stay interactive
  $: publicChatUrl = (typeof window !== 'undefined' ? window.location.origin : '') + `/chat/${projectId}`;

  function copyPublicUrl() {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(publicChatUrl);
      toasts.success('Public chat URL copied');
    }
  }

  // Public Chat URL toggle auto-saves immediately — it's a kill-switch, so
  // requiring a separate Save click is surprising and dangerous. The rest of
  // the Public Chat URL form (auth toggle, username, password) still waits
  // for Save Configuration because those changes deserve deliberate review.
  async function handlePublicUrlToggle(event: Event) {
    const target = event.target as HTMLInputElement;
    const newValue = target.checked;
    if (!selectedWorkflowId) {
      // Can't save without a workflow — revert the UI and tell the admin.
      target.checked = !newValue;
      publicUrlEnabled = !newValue;
      toasts.error('Please select and save a workflow first');
      return;
    }
    publicUrlEnabled = newValue;
    publicUrlEnabledSaving = true;
    try {
      await cleanUniversalApi.updateDeployment(projectId, {
        workflow_id: selectedWorkflowId,
        public_url_enabled: newValue,
      });
      toasts.success(
        newValue
          ? 'Public Chat URL enabled'
          : 'Public Chat URL disabled — all sessions terminated'
      );
      await loadDeployment();
    } catch (error: any) {
      // Revert the toggle and surface the error — don't leave the UI in a
      // misleading state where the switch looks flipped but the backend isn't.
      publicUrlEnabled = !newValue;
      target.checked = !newValue;
      toasts.error(error?.message || 'Failed to update Public Chat URL');
    } finally {
      publicUrlEnabledSaving = false;
    }
  }


  // Generate iframe-based embed code — points to server-rendered HTML
  // This ensures full feature parity (file uploads, copy button, citations, streaming)
  function generateEmbedCode(): string {
    if (!endpointUrl || !initialGreeting) {
      console.warn('⚠️ DEPLOYMENT: Cannot generate embed code - missing endpointUrl or initialGreeting');
      return '';
    }
    const title = chatbotTitle || 'AI Assistant';
    const embedUrl = endpointUrl.replace(/\/$/, '') + '/embed/';
    return `<iframe src="${embedUrl}" title="${title}" style="width:100%;height:600px;border:none;border-radius:12px;" allow="clipboard-write"></iframe>`;
  }

  // Full HTML embed — fetched from the same server endpoint (single source of truth)
  let fullHtmlCode = '';
  let fullHtmlLoading = false;

  async function fetchFullHtmlCode() {
    if (!endpointUrl) return;
    fullHtmlLoading = true;
    try {
      const embedUrl = endpointUrl.replace(/\/$/, '') + '/embed/';
      const resp = await fetch(embedUrl);
      if (resp.ok) {
        let html = await resp.text();
        // The server injects _SERVER_ENDPOINT using request.build_absolute_uri()
        // which may return a Docker-internal hostname (e.g. http://backend:8000/...).
        // Replace it with the correct browser-accessible endpointUrl.
        const serverEndpointMatch = html.match(/const _SERVER_ENDPOINT = "([^"]+)"/);
        if (serverEndpointMatch && serverEndpointMatch[1] !== endpointUrl) {
          html = html.replace(serverEndpointMatch[1], endpointUrl);
        }
        fullHtmlCode = html;
      } else {
        fullHtmlCode = '<!-- Failed to load embed HTML -->';
      }
    } catch (e) {
      fullHtmlCode = '<!-- Error fetching embed HTML -->';
    } finally {
      fullHtmlLoading = false;
    }
  }

  function copyFullHtmlCode() {
    if (typeof navigator !== 'undefined' && navigator.clipboard && fullHtmlCode) {
      navigator.clipboard.writeText(fullHtmlCode);
    }
  }


  // Reactive variable that calls the function - track all branding dependencies
  $: embedCode = endpointUrl && initialGreeting ? generateEmbedCode() : '';
  // Trigger regeneration when branding settings change
  $: if (chatbotTitle || chatbotSubtitle || primaryColor || secondaryColor || logoUrl) {
    if (endpointUrl && initialGreeting) {
      embedCode = generateEmbedCode();
    }
  }
  
  onMount(() => {
    loadDeployment();
    loadWorkflows();
  });
  
  async function loadDeployment() {
    try {
      loading = true;
      console.log(`📋 DEPLOYMENT: Loading deployment for project ${projectId}`);
      
      const data = await cleanUniversalApi.getDeployment(projectId);
      
      deployment = data.deployment;
      workflows = data.available_workflows || [];
      allowedOrigins = data.allowed_origins || [];
      
      if (deployment) {
        selectedWorkflowId = deployment.workflow_id || '';
        isActive = deployment.is_active || false;
        rateLimitPerMinute = deployment.rate_limit_per_minute || 10;
        initialGreeting = deployment.initial_greeting || initialGreeting;
        
        // Load branding customization
        chatbotTitle = deployment.chatbot_title || 'AI Assistant';
        chatbotSubtitle = deployment.chatbot_subtitle || 'Powered by AICC IntelliDoc';
        primaryColor = deployment.primary_color || '#ffffff';
        secondaryColor = deployment.secondary_color || '#ffffff';
        logoUrl = deployment.logo_url || '';
        fontColor = deployment.font_color || '#000000';
        fileUploadsEnabled = deployment.file_uploads_enabled || false;

        // Public Chat URL fields (password never returned by API — reset local buffer
        // and use the `public_url_password_set` boolean to show "is set" state).
        publicUrlEnabled = deployment.public_url_enabled || false;
        publicUrlAuthEnabled = deployment.public_url_auth_enabled || false;
        publicUrlUsername = deployment.public_url_username || '';
        publicUrlPasswordSet = !!deployment.public_url_password_set;
        publicUrlPassword = '';

        // Construct endpoint URL:
        // For embed code (external use): use VITE_BACKEND_URL (direct backend, works cross-origin)
        // Fallback: window.location.origin (works in production where frontend=backend behind nginx)
        const backendOrigin = import.meta.env.VITE_BACKEND_URL || (typeof window !== 'undefined' ? window.location.origin : '');
        endpointUrl = `${backendOrigin}${deployment.endpoint_path}`;
        
        // Debug logging
        console.log('🔗 DEPLOYMENT: endpointUrl =', endpointUrl);
        console.log('🔗 DEPLOYMENT: initialGreeting =', initialGreeting);
        console.log('🎨 DEPLOYMENT: Branding loaded - title:', chatbotTitle, 'colors:', primaryColor, secondaryColor);
      }
      
      console.log(`✅ DEPLOYMENT: Loaded deployment data`);
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to load deployment:', error);
      toasts.error('Failed to load deployment configuration');
    } finally {
      loading = false;
    }
  }
  
  async function loadWorkflows() {
    try {
      const auth = get(authStore);
      const token = auth?.token || '';
      
      const response = await fetch(`/api/projects/${projectId}/workflows/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to load workflows: ${response.status}`);
      }
      
      const data = await response.json();
      workflows = Array.isArray(data) ? data : (data.workflows || data.results || []);
      
      // If no workflow selected and we have workflows, select first one
      if (workflows.length > 0 && !selectedWorkflowId) {
        selectedWorkflowId = workflows[0].workflow_id;
      }
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to load workflows:', error);
    }
  }
  
  async function saveDeployment() {
    if (!selectedWorkflowId) {
      toasts.error('Please select a workflow to deploy');
      return;
    }
    
    try {
      saving = true;
      console.log(`💾 DEPLOYMENT: Saving deployment configuration`);
      
      // Build the payload; only include the password when the admin typed a
      // new one, so re-saving other fields never wipes the existing password.
      // NOTE: `public_url_enabled` intentionally omitted — that toggle is a
      // kill-switch and auto-saves via handlePublicUrlToggle() the moment
      // the admin flips it. Including it here would re-bump the session
      // generation version on every Save Configuration click.
      const payload: Record<string, any> = {
        workflow_id: selectedWorkflowId,
        rate_limit_per_minute: rateLimitPerMinute,
        initial_greeting: initialGreeting,
        // Branding customization
        chatbot_title: chatbotTitle,
        chatbot_subtitle: chatbotSubtitle,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
        logo_url: logoUrl || null,
        font_color: fontColor,
        file_uploads_enabled: fileUploadsEnabled,
        // Public Chat URL auth fields (enable toggle handled separately)
        public_url_auth_enabled: publicUrlAuthEnabled,
        public_url_username: publicUrlUsername || ''
      };
      if (publicUrlPassword) {
        payload.public_url_password = publicUrlPassword;
      }
      await cleanUniversalApi.updateDeployment(projectId, payload);
      
      toasts.success('Deployment configuration saved successfully');
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to save deployment:', error);
      toasts.error(error.message || 'Failed to save deployment configuration');
    } finally {
      saving = false;
    }
  }
  
  async function toggleDeployment() {
    try {
      saving = true;
      console.log(`🔄 DEPLOYMENT: Toggling deployment to ${!isActive ? 'active' : 'inactive'}`);
      
      const result = await cleanUniversalApi.toggleDeployment(projectId);
      isActive = result.is_active;
      
      toasts.success(result.message || `Deployment ${isActive ? 'activated' : 'deactivated'} successfully`);
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to toggle deployment:', error);
      toasts.error(error.message || 'Failed to toggle deployment');
    } finally {
      saving = false;
    }
  }
  
  async function addOrigin() {
    if (!newOrigin.trim()) {
      toasts.error('Please enter an origin URL');
      return;
    }
    
    // Basic validation
    if (!newOrigin.startsWith('http://') && !newOrigin.startsWith('https://')) {
      toasts.error('Origin must start with http:// or https://');
      return;
    }
    
    try {
      saving = true;
      console.log(`➕ DEPLOYMENT: Adding origin ${newOrigin}`);
      
      await cleanUniversalApi.addAllowedOrigin(projectId, {
        origin: newOrigin.trim(),
        rate_limit_per_minute: newOriginRateLimit
      });
      
      toasts.success('Origin added successfully');
      newOrigin = '';
      newOriginRateLimit = rateLimitPerMinute;
      showAddOrigin = false;
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to add origin:', error);
      toasts.error(error.message || 'Failed to add origin');
    } finally {
      saving = false;
    }
  }
  
  async function removeOrigin(originId: number) {
    if (!confirm('Are you sure you want to remove this origin?')) {
      return;
    }
    
    try {
      saving = true;
      console.log(`🗑️ DEPLOYMENT: Removing origin ${originId}`);
      
      await cleanUniversalApi.removeAllowedOrigin(projectId, originId);
      
      toasts.success('Origin removed successfully');
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to remove origin:', error);
      toasts.error(error.message || 'Failed to remove origin');
    } finally {
      saving = false;
    }
  }
  
  async function updateOrigin(origin: any) {
    try {
      saving = true;
      console.log(`🔄 DEPLOYMENT: Updating origin ${origin.id}`);
      
      await cleanUniversalApi.updateOriginRateLimit(projectId, origin.id, {
        rate_limit_per_minute: origin.rate_limit_per_minute,
        is_active: origin.is_active
      });
      
      toasts.success('Origin updated successfully');
      await loadDeployment();
    } catch (error) {
      console.error('❌ DEPLOYMENT: Failed to update origin:', error);
      toasts.error(error.message || 'Failed to update origin');
    } finally {
      saving = false;
    }
  }
  
  function copyEndpointUrl() {
    if (typeof window !== 'undefined' && endpointUrl) {
      navigator.clipboard.writeText(endpointUrl);
      toasts.success('Endpoint URL copied to clipboard');
    }
  }
  
  function copyEmbedCode() {
    if (typeof navigator !== 'undefined' && navigator.clipboard && embedCode) {
      navigator.clipboard.writeText(embedCode);
      toasts.success('HTML embed code copied to clipboard');
    }
  }
</script>

<div class="workflow-deployment-container">
  <div class="deployment-header">
    <h2 class="text-2xl font-bold text-gray-900 mb-2">
      <i class="fas fa-rocket mr-2 text-oxford-blue"></i>
      Workflow Deployment
    </h2>
    <p class="text-gray-600 mb-6">Deploy your workflows as public-facing chatbots</p>
  </div>
  
  {#if loading}
    <div class="flex items-center justify-center min-h-96">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
        <p class="text-oxford-blue">Loading deployment configuration...</p>
      </div>
    </div>
  {:else}
    <!-- Deployment Status Section -->
    <div class="deployment-section mb-8">
      <h3 class="text-xl font-semibold text-gray-900 mb-4">
        <i class="fas fa-cog mr-2 text-oxford-blue"></i>
        Deployment Configuration
      </h3>
      
      <div class="bg-white rounded-lg shadow-md p-6">
        <!-- Workflow Selection -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Select Workflow to Deploy
          </label>
          <select
            bind:value={selectedWorkflowId}
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
            disabled={saving}
          >
            <option value="">-- Select a workflow --</option>
            {#each workflows as workflow}
              <option value={workflow.workflow_id}>
                {workflow.name} {workflow.description ? `- ${workflow.description}` : ''}
              </option>
            {/each}
          </select>
          {#if workflows.length === 0}
            <p class="text-sm text-gray-500 mt-2">
              <i class="fas fa-info-circle mr-1"></i>
              No workflows available. Create a workflow in the Agent Orchestration tab first.
            </p>
          {/if}
        </div>
        
        <!-- Rate Limit Setting -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Default Rate Limit (requests per minute)
          </label>
          <input
            type="number"
            bind:value={rateLimitPerMinute}
            min="1"
            max="1000"
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
            disabled={saving}
          />
          <p class="text-sm text-gray-500 mt-1">
            This is the default rate limit for origins without specific limits
          </p>
        </div>

        <!-- Public Chat URL -->
        <div class="mb-6 border-t border-gray-200 pt-6">
          <label class="flex items-start justify-between gap-4 cursor-pointer">
            <div class="min-w-0">
              <div class="font-medium text-gray-900">
                <i class="fas fa-globe mr-2 text-oxford-blue"></i>Public Chat URL
              </div>
              <p class="text-xs text-gray-500 mt-1">
                When enabled, external users can chat with this workflow at a
                dedicated page. Credentials (if set) grant access only to this
                public chat page — never to the admin area.
              </p>
            </div>
            <span class="relative inline-flex flex-shrink-0 w-11 h-6">
              <input
                type="checkbox"
                checked={publicUrlEnabled}
                on:change={handlePublicUrlToggle}
                disabled={saving || publicUrlEnabledSaving}
                class="sr-only peer"
              />
              <span class="absolute inset-0 rounded-full bg-gray-300 peer-checked:bg-oxford-blue transition-colors"></span>
              <span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform peer-checked:translate-x-5"></span>
            </span>
          </label>
          {#if publicUrlEnabledSaving}
            <p class="text-xs text-gray-500 mt-2">
              <i class="fas fa-spinner fa-spin mr-1"></i>Applying…
            </p>
          {/if}

          {#if publicUrlEnabled}
            <div class="mt-4">
              <label class="block text-xs text-gray-600 mb-1">Public Chat URL</label>
              <div class="flex">
                <input
                  readonly
                  value={publicChatUrl}
                  class="flex-1 rounded-l-lg border border-gray-300 px-3 py-2 text-sm bg-gray-50 font-mono text-gray-700"
                />
                <button
                  type="button"
                  on:click={copyPublicUrl}
                  class="px-3 bg-oxford-blue text-white rounded-r-lg hover:bg-oxford-blue-dark transition-colors"
                  title="Copy URL"
                >
                  <i class="fas fa-copy"></i>
                </button>
              </div>
            </div>

            <label class="flex items-start justify-between gap-4 mt-4 cursor-pointer">
              <div class="min-w-0">
                <div class="font-medium text-gray-900">Require authentication</div>
                <p class="text-xs text-gray-500 mt-1">
                  End-users must enter a username and password before chatting.
                </p>
              </div>
              <span class="relative inline-flex flex-shrink-0 w-11 h-6">
                <input
                  type="checkbox"
                  bind:checked={publicUrlAuthEnabled}
                  disabled={saving}
                  class="sr-only peer"
                />
                <span class="absolute inset-0 rounded-full bg-gray-300 peer-checked:bg-oxford-blue transition-colors"></span>
                <span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform peer-checked:translate-x-5"></span>
              </span>
            </label>

            {#if publicUrlAuthEnabled}
              <div class="mt-4 space-y-3">
                <div>
                  <label class="block text-xs text-gray-600 mb-1">Username</label>
                  <input
                    type="text"
                    bind:value={publicUrlUsername}
                    autocomplete="off"
                    placeholder="Choose a username"
                    class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-oxford-blue focus:border-oxford-blue"
                    disabled={saving}
                  />
                </div>
                <div>
                  <label class="block text-xs text-gray-600 mb-1">
                    Password
                    {#if publicUrlPasswordSet && !publicUrlPassword}
                      <span class="ml-1 text-green-600">
                        <i class="fas fa-check-circle"></i> set
                      </span>
                    {/if}
                  </label>
                  <input
                    type="password"
                    bind:value={publicUrlPassword}
                    autocomplete="new-password"
                    placeholder={publicUrlPasswordSet ? 'Leave blank to keep existing password' : 'Choose a password'}
                    class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-oxford-blue focus:border-oxford-blue"
                    disabled={saving}
                  />
                </div>
                <p class="text-xs text-gray-500">
                  Password is hashed on save. Saving a new password immediately logs
                  out any currently-signed-in end-users.
                </p>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Save Button -->
        <button
          on:click={saveDeployment}
          disabled={saving || !selectedWorkflowId}
          class="px-6 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {#if saving}
            <i class="fas fa-spinner fa-spin mr-2"></i>
            Saving...
          {:else}
            <i class="fas fa-save mr-2"></i>
            Save Configuration
          {/if}
        </button>
      </div>
    </div>
    
    <!-- Deployment Status Toggle -->
    {#if deployment && deployment.workflow_id}
      <div class="deployment-section mb-8">
        <h3 class="text-xl font-semibold text-gray-900 mb-4">
          <i class="fas fa-power-off mr-2 text-oxford-blue"></i>
          Deployment Status
        </h3>
        
        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <p class="text-sm font-medium text-gray-700 mb-1">Deployment Status</p>
              <p class="text-lg font-semibold {isActive ? 'text-green-600' : 'text-gray-500'}">
                {isActive ? 'Active' : 'Inactive'}
              </p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                bind:checked={isActive}
                on:change={toggleDeployment}
                disabled={saving}
                class="sr-only peer"
              />
              <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-oxford-blue/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-oxford-blue"></div>
            </label>
          </div>
          
          <!-- Endpoint URL -->
          <div class="mt-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Endpoint URL
            </label>
            <div class="flex items-center gap-2">
              <input
                type="text"
                value={endpointUrl}
                readonly
                class="flex-1 px-4 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-700"
              />
              <button
                on:click={copyEndpointUrl}
                class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
                title="Copy to clipboard"
              >
                <i class="fas fa-copy"></i>
              </button>
            </div>
            <p class="text-sm text-gray-500 mt-1">
              Use this endpoint to access your deployed workflow
            </p>
          </div>
        </div>
      </div>
    {/if}
    
    <!-- Allowed Origins Section -->
    <div class="deployment-section mb-8">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-xl font-semibold text-gray-900">
          <i class="fas fa-globe mr-2 text-oxford-blue"></i>
          Allowed Origins
        </h3>
        <button
          on:click={() => showAddOrigin = !showAddOrigin}
          class="px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
        >
          <i class="fas fa-plus mr-2"></i>
          Add Origin
        </button>
      </div>
      
      <!-- Add Origin Form -->
      {#if showAddOrigin}
        <div class="bg-white rounded-lg shadow-md p-6 mb-4">
          <h4 class="text-lg font-medium text-gray-900 mb-4">Add New Origin</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Origin URL
              </label>
              <input
                type="text"
                bind:value={newOrigin}
                placeholder="https://example.com"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Rate Limit (per minute)
              </label>
              <input
                type="number"
                bind:value={newOriginRateLimit}
                min="1"
                max="1000"
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
              />
            </div>
          </div>
          <div class="flex gap-2">
            <button
              on:click={addOrigin}
              disabled={saving}
              class="px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors disabled:opacity-50"
            >
              <i class="fas fa-check mr-2"></i>
              Add
            </button>
            <button
              on:click={() => { showAddOrigin = false; newOrigin = ''; }}
              class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      {/if}
      
      <!-- Origins List -->
      <div class="bg-white rounded-lg shadow-md overflow-hidden">
        {#if allowedOrigins.length === 0}
          <div class="p-8 text-center text-gray-500">
            <i class="fas fa-inbox text-4xl mb-4"></i>
            <p>No allowed origins configured</p>
            <p class="text-sm mt-2">Add origins to allow specific domains to access your deployed workflow</p>
          </div>
        {:else}
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Origin</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rate Limit</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              {#each allowedOrigins as origin}
                <tr>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm font-medium text-gray-900">{origin.origin}</div>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <input
                      type="number"
                      bind:value={origin.rate_limit_per_minute}
                      min="1"
                      max="1000"
                      on:blur={() => updateOrigin(origin)}
                      class="w-24 px-2 py-1 border border-gray-300 rounded text-sm"
                    />
                    <span class="text-xs text-gray-500 ml-1">/min</span>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        bind:checked={origin.is_active}
                        on:change={() => updateOrigin(origin)}
                        class="sr-only peer"
                      />
                      <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-oxford-blue/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-oxford-blue"></div>
                      <span class="ml-2 text-sm text-gray-700">{origin.is_active ? 'Active' : 'Inactive'}</span>
                    </label>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      on:click={() => removeOrigin(origin.id)}
                      class="text-red-600 hover:text-red-900"
                    >
                      <i class="fas fa-trash"></i>
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </div>
    
    <!-- Embed Code Section -->
    {#if deployment && deployment.workflow_id && endpointUrl}
      <div class="deployment-section mb-8">
        <h3 class="text-xl font-semibold text-gray-900 mb-4">
          <i class="fas fa-code mr-2 text-oxford-blue"></i>
          Embed Code
        </h3>
        
        <div class="bg-white rounded-lg shadow-md p-6 space-y-6">
          <!-- Greeting Editor -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Initial Greeting Message
            </label>
            <textarea
              bind:value={initialGreeting}
              maxlength={GREETING_MAX_LENGTH}
              rows="4"
              class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
              placeholder="Hi! I am your AI assistant."
            ></textarea>
            <div class="flex justify-between mt-1">
              <p class="text-sm text-gray-500">
                This message will be shown as the first assistant message in the embedded chatbot. Changes are project-specific.
              </p>
              <p class="text-sm {initialGreeting.length >= GREETING_MAX_LENGTH ? 'text-red-500' : 'text-gray-500'} whitespace-nowrap ml-4">
                {initialGreeting.length}/{GREETING_MAX_LENGTH}
              </p>
            </div>
          </div>

          <!-- Embed Snippet -->
          <!-- Chatbot Branding Customization -->
          <div class="mt-8 pt-6 border-t border-gray-200">
            <h4 class="text-lg font-semibold text-gray-900 mb-4">
              <i class="fas fa-palette mr-2 text-oxford-blue"></i>
              Chatbot Branding
            </h4>
            <p class="text-sm text-gray-600 mb-6">
              Customize the appearance of your embedded chatbot to match your brand.
            </p>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <!-- Chatbot Title -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Chatbot Title
                </label>
                <input
                  type="text"
                  bind:value={chatbotTitle}
                  class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
                  placeholder="AI Assistant"
                />
              </div>
              
              <!-- Chatbot Subtitle -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Chatbot Subtitle
                </label>
                <input
                  type="text"
                  bind:value={chatbotSubtitle}
                  class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
                  placeholder="Powered by AICC IntelliDoc"
                />
              </div>
              
              <!-- Primary Color -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Primary Color
                </label>
                <div class="flex items-center gap-3">
                  <input
                    type="color"
                    bind:value={primaryColor}
                    class="w-12 h-10 border border-gray-300 rounded-md cursor-pointer p-1"
                  />
                  <input
                    type="text"
                    bind:value={primaryColor}
                    class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue font-mono text-sm"
                    placeholder="#0b3b66"
                    maxlength="7"
                  />
                </div>
                <p class="text-xs text-gray-500 mt-1">Header background and user message bubbles</p>
              </div>
              
              <!-- Secondary Color -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Secondary Color (Gradient)
                </label>
                <div class="flex items-center gap-3">
                  <input
                    type="color"
                    bind:value={secondaryColor}
                    class="w-12 h-10 border border-gray-300 rounded-md cursor-pointer p-1"
                  />
                  <input
                    type="text"
                    bind:value={secondaryColor}
                    class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue font-mono text-sm"
                    placeholder="#1e5a8a"
                    maxlength="7"
                  />
                </div>
                <p class="text-xs text-gray-500 mt-1">Used for gradient effects</p>
              </div>
            </div>

            <!-- Font Color -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Font Color
              </label>
              <div class="flex items-center gap-3">
                <input
                  type="color"
                  bind:value={fontColor}
                  class="w-10 h-10 rounded cursor-pointer border border-gray-300"
                />
                <input
                  type="text"
                  bind:value={fontColor}
                  class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue font-mono text-sm"
                  placeholder="#1e293b"
                  maxlength="7"
                />
              </div>
              <p class="text-xs text-gray-500 mt-1">Text color for chatbot messages</p>
            </div>

            <!-- Logo URL -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Logo URL (Optional)
              </label>
              <input
                type="url"
                bind:value={logoUrl}
                class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
                placeholder="https://example.com/logo.png"
              />
              <p class="text-xs text-gray-500 mt-1">
                URL to your logo image. Leave empty to display the first letter of the title. Recommended size: 44x44px or larger.
              </p>
            </div>
            
            <!-- File Uploads Toggle -->
            <div class="mb-6">
              <label class="flex items-center gap-3 cursor-pointer">
                <div class="relative">
                  <input
                    type="checkbox"
                    bind:checked={fileUploadsEnabled}
                    class="sr-only peer"
                  />
                  <div class="w-10 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-oxford-blue"></div>
                </div>
                <div>
                  <span class="text-sm font-medium text-gray-700">Allow File Uploads</span>
                  <p class="text-xs text-gray-500">
                    {fileUploadsEnabled ? 'Users can attach PDF, TXT, DOC, DOCX, MD, RTF files in the chatbot' : 'File upload is disabled for chatbot users'}
                  </p>
                </div>
              </label>
            </div>

            <!-- Live Preview -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Header Preview
              </label>
              <div 
                class="rounded-xl overflow-hidden shadow-lg"
                style="max-width: 420px;"
              >
                <div 
                  class="flex items-center gap-3 p-4 text-white"
                  style="background: linear-gradient(135deg, {primaryColor} 0%, {secondaryColor} 100%);"
                >
                  <div 
                    class="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                    style="background: rgba(255, 255, 255, 0.2);"
                  >
                    {#if logoUrl}
                      <img src={logoUrl} alt="Logo" class="w-full h-full object-cover rounded-xl" />
                    {:else}
                      <span class="text-lg font-bold text-white uppercase">
                        {chatbotTitle ? chatbotTitle[0] : 'A'}
                      </span>
                    {/if}
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="font-bold text-base truncate">{chatbotTitle || 'AI Assistant'}</div>
                    <div class="text-xs opacity-85 truncate">{chatbotSubtitle || 'Powered by AICC IntelliDoc'}</div>
                  </div>
                  <div class="w-2.5 h-2.5 bg-green-400 rounded-full shadow-[0_0_0_3px_rgba(34,197,94,0.3)]"></div>
                </div>
              </div>
            </div>
            
            <!-- Save Branding Button -->
            <button
              on:click={saveDeployment}
              disabled={saving || !selectedWorkflowId}
              class="px-6 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {#if saving}
                <i class="fas fa-spinner fa-spin mr-2"></i>
                Saving...
              {:else}
                <i class="fas fa-save mr-2"></i>
                Save Branding
              {/if}
            </button>
          </div>

          <!-- Iframe Embed -->
          <div class="mt-8 pt-6 border-t border-gray-200">
            <div class="flex items-center justify-between mb-2">
              <label class="block text-sm font-medium text-gray-700">
                Iframe Embed Code <span class="text-xs font-normal text-green-600 ml-1">(recommended)</span>
              </label>
              <button
                on:click={copyEmbedCode}
                class="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-xs font-medium"
              >
                <i class="fas fa-copy mr-1"></i>
                Copy
              </button>
            </div>
            <textarea
              readonly
              class="w-full h-16 font-mono text-xs px-3 py-3 border border-gray-300 rounded-md bg-gray-50 text-gray-800"
            >{embedCode}</textarea>
            <p class="text-sm text-gray-500 mt-2">
              <i class="fas fa-info-circle mr-1"></i>
              Paste this into your website. All features (file uploads, copy, citations) are included automatically.
            </p>
          </div>

          <!-- Full HTML Embed -->
          <div class="mt-6 pt-4 border-t border-gray-100">
            <div class="flex items-center justify-between mb-2">
              <label class="block text-sm font-medium text-gray-700">
                Full HTML Embed Code
              </label>
              <div class="flex gap-2">
                {#if !fullHtmlCode}
                  <button
                    on:click={fetchFullHtmlCode}
                    disabled={fullHtmlLoading}
                    class="px-3 py-1.5 bg-oxford-blue text-white rounded-md hover:bg-blue-800 text-xs font-medium disabled:opacity-50"
                  >
                    {#if fullHtmlLoading}
                      <i class="fas fa-spinner fa-spin mr-1"></i> Loading...
                    {:else}
                      <i class="fas fa-code mr-1"></i> Load Full HTML
                    {/if}
                  </button>
                {:else}
                  <button
                    on:click={copyFullHtmlCode}
                    class="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-xs font-medium"
                  >
                    <i class="fas fa-copy mr-1"></i>
                    Copy
                  </button>
                {/if}
              </div>
            </div>
            {#if fullHtmlCode}
              <textarea
                readonly
                class="w-full h-72 font-mono text-xs px-3 py-3 border border-gray-300 rounded-md bg-gray-50 text-gray-800"
              >{fullHtmlCode}</textarea>
            {:else}
              <p class="text-sm text-gray-400 py-4 text-center border border-dashed border-gray-200 rounded-md">
                Click "Load Full HTML" to generate the standalone HTML code from the server.
              </p>
            {/if}
            <p class="text-sm text-gray-500 mt-2">
              <i class="fas fa-info-circle mr-1"></i>
              Self-contained HTML — same code as the iframe version. Use this if you need to host the chatbot HTML directly.
            </p>
          </div>
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  .workflow-deployment-container {
    @apply p-6 max-w-6xl mx-auto;
  }
  
  .deployment-section {
    @apply mb-8;
  }
</style>

