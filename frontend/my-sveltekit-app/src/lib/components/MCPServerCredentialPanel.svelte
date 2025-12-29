<!-- MCPServerCredentialPanel.svelte - MCP Server Credential Management Panel -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import * as mcpService from '$lib/services/mcpServerService';
  import type { MCPServerType, MCPServerCredential, MCPServerStatus } from '$lib/services/mcpServerService';
  
  export let projectId: string;
  export let onClose: () => void;
  
  let serverTypes: MCPServerType[] = [];
  let serverStatus: MCPServerStatus | null = null;
  let loading = false;
  let selectedServerType: string | null = null;
  let credentials: Record<string, any> = {};
  let serverConfig: Record<string, any> = {};
  let credentialName = '';
  let testingConnection = false;
  let connectionTestResult: any = null;
  
  // Server-specific credential fields
  let googleDriveCredentials = {
    client_id: '',
    client_secret: '',
    refresh_token: ''
  };
  
  let sharePointCredentials = {
    tenant_id: '',
    client_id: '',
    client_secret: '',
    site_url: ''
  };
  
  onMount(async () => {
    await loadServerTypes();
    await loadServerStatus();
  });
  
  async function loadServerTypes() {
    try {
      serverTypes = await mcpService.getMCPServerTypes();
    } catch (error: any) {
      toasts.error(`Failed to load server types: ${error.message}`);
    }
  }
  
  async function loadServerStatus() {
    if (!projectId) return;
    try {
      serverStatus = await mcpService.getMCPServerStatus(projectId);
    } catch (error: any) {
      toasts.error(`Failed to load server status: ${error.message}`);
    }
  }
  
  function selectServerType(serverType: string) {
    selectedServerType = serverType;
    connectionTestResult = null;
    
    // Load existing credentials if available
    if (serverStatus) {
      const server = serverStatus.servers.find(s => s.code === serverType);
      if (server?.has_credentials) {
        loadExistingCredentials(serverType);
      }
    }
  }
  
  async function loadExistingCredentials(serverType: string) {
    try {
      const creds = await mcpService.getMCPServerCredentials(projectId, serverType);
      if (creds) {
        // Note: We can't decrypt credentials on the frontend for security
        // This is just for display purposes
        credentialName = creds.credential_name || '';
      }
    } catch (error: any) {
      console.error('Error loading credentials:', error);
    }
  }
  
  function getCredentialsForServerType(): Record<string, any> {
    if (selectedServerType === 'google_drive') {
      return googleDriveCredentials;
    } else if (selectedServerType === 'sharepoint') {
      return {
        ...sharePointCredentials,
        site_url: serverConfig.site_url || sharePointCredentials.site_url
      };
    }
    return {};
  }
  
  async function saveCredentials() {
    if (!selectedServerType) {
      toasts.error('Please select a server type');
      return;
    }
    
    loading = true;
    try {
      const creds = getCredentialsForServerType();
      
      // Validate required fields
      if (selectedServerType === 'google_drive') {
        if (!googleDriveCredentials.client_id || !googleDriveCredentials.client_secret || !googleDriveCredentials.refresh_token) {
          toasts.error('Please fill in all required Google Drive credentials');
          loading = false;
          return;
        }
      } else if (selectedServerType === 'sharepoint') {
        if (!sharePointCredentials.tenant_id || !sharePointCredentials.client_id || !sharePointCredentials.client_secret) {
          toasts.error('Please fill in all required SharePoint credentials');
          loading = false;
          return;
        }
        serverConfig.site_url = sharePointCredentials.site_url;
      }
      
      await mcpService.setMCPServerCredentials(
        projectId,
        selectedServerType,
        creds,
        credentialName,
        serverConfig
      );
      
      toasts.success('Credentials saved successfully');
      await loadServerStatus();
      connectionTestResult = null;
    } catch (error: any) {
      toasts.error(`Failed to save credentials: ${error.message}`);
    } finally {
      loading = false;
    }
  }
  
  async function testConnection() {
    if (!selectedServerType) {
      toasts.error('Please select a server type');
      return;
    }
    
    testingConnection = true;
    connectionTestResult = null;
    
    try {
      // Save credentials first if not already saved
      const existingCreds = await mcpService.getMCPServerCredentials(projectId, selectedServerType);
      if (!existingCreds) {
        await saveCredentials();
      }
      
      const result = await mcpService.testMCPServerConnection(projectId, selectedServerType);
      connectionTestResult = result;
      
      if (result.success) {
        toasts.success(`Connection successful! Found ${result.tools_count || 0} tools.`);
      } else {
        toasts.error(`Connection failed: ${result.error || 'Unknown error'}`);
      }
    } catch (error: any) {
      toasts.error(`Connection test failed: ${error.message}`);
      connectionTestResult = { success: false, error: error.message };
    } finally {
      testingConnection = false;
    }
  }
  
  async function deleteCredentials() {
    if (!selectedServerType) {
      toasts.error('Please select a server type');
      return;
    }
    
    if (!confirm('Are you sure you want to delete these credentials?')) {
      return;
    }
    
    loading = true;
    try {
      await mcpService.deleteMCPServerCredentials(projectId, selectedServerType);
      toasts.success('Credentials deleted successfully');
      
      // Reset form
      if (selectedServerType === 'google_drive') {
        googleDriveCredentials = { client_id: '', client_secret: '', refresh_token: '' };
      } else if (selectedServerType === 'sharepoint') {
        sharePointCredentials = { tenant_id: '', client_id: '', client_secret: '', site_url: '' };
      }
      credentialName = '';
      serverConfig = {};
      connectionTestResult = null;
      
      await loadServerStatus();
    } catch (error: any) {
      toasts.error(`Failed to delete credentials: ${error.message}`);
    } finally {
      loading = false;
    }
  }
  
  function getServerStatus(serverType: string) {
    if (!serverStatus) return null;
    return serverStatus.servers.find(s => s.code === serverType);
  }
</script>

<div class="mcp-credential-panel w-full max-w-4xl mx-auto bg-white rounded-lg shadow-lg">
  <!-- Header -->
  <div class="p-6 border-b border-gray-200">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-gray-900">MCP Server Credentials</h2>
        <p class="text-sm text-gray-600 mt-1">Configure credentials for MCP servers (Google Drive, SharePoint, etc.)</p>
      </div>
      <button
        on:click={onClose}
        class="p-2 text-gray-400 hover:text-gray-600 transition-colors"
      >
        <i class="fas fa-times text-xl"></i>
      </button>
    </div>
  </div>
  
  <!-- Content -->
  <div class="p-6 space-y-6">
    <!-- Server Type Selection -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">Select MCP Server</label>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        {#each serverTypes as serverType}
          {@const status = getServerStatus(serverType.code)}
          <button
            type="button"
            on:click={() => selectServerType(serverType.code)}
            class="p-4 border-2 rounded-lg transition-all text-left {selectedServerType === serverType.code ? 'border-purple-600 bg-purple-50' : 'border-gray-200 hover:border-gray-300'}"
          >
            <div class="flex items-center justify-between">
              <div>
                <div class="flex items-center space-x-2">
                  <i class="fas {serverType.icon} text-{serverType.color}-600"></i>
                  <h3 class="font-semibold text-gray-900">{serverType.display_name}</h3>
                </div>
                <p class="text-xs text-gray-600 mt-1">{serverType.description}</p>
              </div>
              {#if status?.has_credentials}
                <span class="px-2 py-1 text-xs rounded {status.is_validated ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}">
                  {status.is_validated ? '✓ Configured' : '⚠ Needs Validation'}
                </span>
              {/if}
            </div>
          </button>
        {/each}
      </div>
    </div>
    
    <!-- Credential Form -->
    {#if selectedServerType}
      <div class="border-t border-gray-200 pt-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">
          {serverTypes.find(s => s.code === selectedServerType)?.display_name} Credentials
        </h3>
        
        <!-- Credential Name -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">Credential Name (Optional)</label>
          <input
            type="text"
            bind:value={credentialName}
            placeholder="e.g., Production Credentials"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
          />
        </div>
        
        <!-- Google Drive Credentials -->
        {#if selectedServerType === 'google_drive'}
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">OAuth Client ID</label>
              <input
                type="text"
                bind:value={googleDriveCredentials.client_id}
                placeholder="Enter Google OAuth Client ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">OAuth Client Secret</label>
              <input
                type="password"
                bind:value={googleDriveCredentials.client_secret}
                placeholder="Enter Google OAuth Client Secret"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Refresh Token</label>
              <input
                type="password"
                bind:value={googleDriveCredentials.refresh_token}
                placeholder="Enter OAuth Refresh Token"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">
                Obtain these from Google Cloud Console after setting up OAuth 2.0 credentials
              </p>
            </div>
          </div>
        {/if}
        
        <!-- SharePoint Credentials -->
        {#if selectedServerType === 'sharepoint'}
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Tenant ID</label>
              <input
                type="text"
                bind:value={sharePointCredentials.tenant_id}
                placeholder="Enter Azure AD Tenant ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Client ID (Application ID)</label>
              <input
                type="text"
                bind:value={sharePointCredentials.client_id}
                placeholder="Enter Azure AD Application (Client) ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Client Secret</label>
              <input
                type="password"
                bind:value={sharePointCredentials.client_secret}
                placeholder="Enter Azure AD Client Secret"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">SharePoint Site URL</label>
              <input
                type="text"
                bind:value={sharePointCredentials.site_url}
                placeholder="https://contoso.sharepoint.com/sites/MySite"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-purple-600 focus:ring-2 focus:ring-purple-600 focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">
                Full URL of the SharePoint site you want to access
              </p>
            </div>
          </div>
        {/if}
        
        <!-- Security Notice -->
        <div class="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div class="flex items-start">
            <i class="fas fa-shield-alt text-blue-600 mt-0.5 mr-2"></i>
            <div class="text-sm text-blue-800">
              <p class="font-medium mb-1">Secure Storage</p>
              <p class="text-xs">
                All credentials are encrypted using project-specific keys and stored securely. 
                Credentials are isolated per project and cannot be accessed by other users.
              </p>
            </div>
          </div>
        </div>
        
        <!-- Connection Test Result -->
        {#if connectionTestResult}
          <div class="mt-4 p-4 rounded-lg {connectionTestResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}">
            <div class="flex items-center">
              <i class="fas {connectionTestResult.success ? 'fa-check-circle' : 'fa-times-circle'} text-{connectionTestResult.success ? 'green' : 'red'}-600 mr-2"></i>
              <div>
                <p class="font-medium text-{connectionTestResult.success ? 'green' : 'red'}-800">
                  {connectionTestResult.success ? 'Connection Successful' : 'Connection Failed'}
                </p>
                {#if connectionTestResult.success}
                  <p class="text-xs text-green-700 mt-1">
                    Found {connectionTestResult.tools_count || 0} available tools
                  </p>
                {:else}
                  <p class="text-xs text-red-700 mt-1">
                    {connectionTestResult.error || 'Unknown error'}
                  </p>
                {/if}
              </div>
            </div>
          </div>
        {/if}
        
        <!-- Actions -->
        <div class="mt-6 flex space-x-3">
          <button
            on:click={saveCredentials}
            disabled={loading}
            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if loading}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Saving...
            {:else}
              <i class="fas fa-save mr-2"></i>
              Save Credentials
            {/if}
          </button>
          
          <button
            on:click={testConnection}
            disabled={loading || testingConnection}
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if testingConnection}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Testing...
            {:else}
              <i class="fas fa-plug mr-2"></i>
              Test Connection
            {/if}
          </button>
          
          {#if getServerStatus(selectedServerType)?.has_credentials}
            <button
              on:click={deleteCredentials}
              disabled={loading}
              class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <i class="fas fa-trash mr-2"></i>
              Delete
            </button>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .mcp-credential-panel {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
</style>

