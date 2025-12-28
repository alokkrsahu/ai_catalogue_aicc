<!-- DeploymentActivityTracker.svelte - Activity Tracker for Deployed Chatbots -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  
  export let projectId: string;
  export let deployment: any;
  
  // Component state
  let sessions: any[] = [];
  let loading = false;
  let selectedSession: any = null;
  let searchQuery = '';
  let totalSessions = 0;
  let currentPage = 0;
  let pageSize = 20;
  
  onMount(() => {
    loadActivity();
  });
  
  async function loadActivity() {
    if (!deployment || !deployment.workflow_id) {
      return;
    }
    
    try {
      loading = true;
      console.log(`📊 ACTIVITY: Loading deployment activity for project ${projectId}`);
      
      const params: any = {
        limit: pageSize,
        offset: currentPage * pageSize
      };
      
      if (searchQuery.trim()) {
        params.session_id = searchQuery.trim();
      }
      
      const data = await cleanUniversalApi.getDeploymentActivity(projectId, params);
      
      sessions = data.sessions || [];
      totalSessions = data.total_sessions || 0;
      
      console.log(`✅ ACTIVITY: Loaded ${sessions.length} sessions (total: ${totalSessions})`);
    } catch (error) {
      console.error('❌ ACTIVITY: Failed to load activity:', error);
      toasts.error('Failed to load deployment activity');
    } finally {
      loading = false;
    }
  }
  
  function selectSession(session: any) {
    selectedSession = selectedSession?.session_id === session.session_id ? null : session;
  }
  
  function formatDate(dateString: string): string {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  }
  
  function formatDuration(ms: number | null): string {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
  
  $: hasMore = (currentPage + 1) * pageSize < totalSessions;
  $: hasPrevious = currentPage > 0;
  
  function nextPage() {
    if (hasMore) {
      currentPage++;
      loadActivity();
    }
  }
  
  function previousPage() {
    if (hasPrevious) {
      currentPage--;
      loadActivity();
    }
  }
  
  function handleSearch() {
    currentPage = 0;
    loadActivity();
  }
</script>

<div class="activity-tracker-container">
  <div class="activity-header mb-6">
    <h3 class="text-xl font-semibold text-gray-900 mb-2">
      <i class="fas fa-chart-line mr-2 text-oxford-blue"></i>
      Activity Tracker
    </h3>
    <p class="text-gray-600">View all conversations from deployed chatbots</p>
  </div>
  
  {#if !deployment || !deployment.workflow_id}
    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <p class="text-yellow-800">
        <i class="fas fa-info-circle mr-2"></i>
        Please configure and activate a deployment to view activity.
      </p>
    </div>
  {:else if loading}
    <div class="flex items-center justify-center min-h-96">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
        <p class="text-oxford-blue">Loading activity...</p>
      </div>
    </div>
  {:else}
    <!-- Search and Filters -->
    <div class="bg-white rounded-lg shadow-md p-4 mb-6">
      <div class="flex items-center gap-4">
        <div class="flex-1">
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="Search by session ID..."
            class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
            on:keydown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <button
          on:click={handleSearch}
          class="px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
        >
          <i class="fas fa-search mr-2"></i>
          Search
        </button>
        <button
          on:click={() => { searchQuery = ''; currentPage = 0; loadActivity(); }}
          class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
        >
          <i class="fas fa-refresh mr-2"></i>
          Refresh
        </button>
      </div>
    </div>
    
    <!-- Sessions List -->
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
      {#if sessions.length === 0}
        <div class="p-8 text-center text-gray-500">
          <i class="fas fa-inbox text-4xl mb-4"></i>
          <p>No deployment activity found</p>
          <p class="text-sm mt-2">Activity will appear here once users start using your deployed chatbot</p>
        </div>
      {:else}
        <div class="divide-y divide-gray-200">
          {#each sessions as session}
            <div class="p-4 hover:bg-gray-50 transition-colors">
              <div class="flex items-center justify-between cursor-pointer" on:click={() => selectSession(session)}>
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-mono text-gray-600 bg-gray-100 px-2 py-1 rounded">
                        {session.session_id.substring(0, 12)}...
                      </span>
                      {#if session.is_active}
                        <span class="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">Active</span>
                      {:else}
                        <span class="text-xs bg-gray-100 text-gray-800 px-2 py-1 rounded">Inactive</span>
                      {/if}
                    </div>
                  </div>
                  <div class="flex items-center gap-4 text-sm text-gray-600">
                    <span>
                      <i class="fas fa-comments mr-1"></i>
                      {session.message_count} messages
                    </span>
                    <span>
                      <i class="fas fa-clock mr-1"></i>
                      Started: {formatDate(session.created_at)}
                    </span>
                    <span>
                      <i class="fas fa-history mr-1"></i>
                      Last: {formatDate(session.last_activity)}
                    </span>
                  </div>
                </div>
                <div class="ml-4">
                  <i class="fas fa-chevron-{selectedSession?.session_id === session.session_id ? 'up' : 'down'} text-gray-400"></i>
                </div>
              </div>
              
              <!-- Expanded Conversation History -->
              {#if selectedSession?.session_id === session.session_id}
                <div class="mt-4 pt-4 border-t border-gray-200">
                  <h4 class="text-sm font-semibold text-gray-900 mb-3">Conversation History</h4>
                  <div class="space-y-3 max-h-96 overflow-y-auto">
                    {#each session.conversation_history as msg}
                      <div class="flex {msg.role === 'user' ? 'justify-end' : 'justify-start'}">
                        <div class="max-w-3xl {msg.role === 'user' ? 'bg-oxford-blue text-white' : 'bg-gray-100 text-gray-900'} rounded-lg px-4 py-2">
                          <div class="text-xs font-semibold mb-1 opacity-75 {msg.role === 'user' ? 'text-white' : 'text-gray-700'}">
                            {msg.role === 'user' ? 'User' : 'Assistant'}
                          </div>
                          <div class="text-sm whitespace-pre-wrap {msg.role === 'user' ? 'text-white' : 'text-gray-900'}">
                            {msg.content}
                          </div>
                          {#if msg.timestamp}
                            <div class="text-xs opacity-60 mt-1 {msg.role === 'user' ? 'text-white' : 'text-gray-600'}">
                              {formatDate(msg.timestamp)}
                            </div>
                          {/if}
                        </div>
                      </div>
                    {/each}
                  </div>
                  
                  <!-- Executions Summary -->
                  {#if session.executions && session.executions.length > 0}
                    <div class="mt-4 pt-4 border-t border-gray-200">
                      <h4 class="text-sm font-semibold text-gray-900 mb-3">Executions ({session.executions.length})</h4>
                      <div class="space-y-2">
                        {#each session.executions.slice(0, 5) as exec}
                          <div class="bg-gray-50 rounded p-2 text-xs">
                            <div class="flex items-center justify-between mb-1">
                              <span class="font-mono text-gray-600">{exec.execution_id.substring(0, 16)}...</span>
                              <span class="text-gray-500">{formatDuration(exec.execution_time_ms)}</span>
                            </div>
                            <div class="text-gray-700">
                              <strong>Q:</strong> {exec.user_query.substring(0, 100)}{exec.user_query.length > 100 ? '...' : ''}
                            </div>
                          </div>
                        {/each}
                        {#if session.executions.length > 5}
                          <p class="text-xs text-gray-500 text-center mt-2">
                            ... and {session.executions.length - 5} more executions
                          </p>
                        {/if}
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
        
        <!-- Pagination -->
        {#if totalSessions > pageSize}
          <div class="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
            <div class="text-sm text-gray-700">
              Showing {currentPage * pageSize + 1} to {Math.min((currentPage + 1) * pageSize, totalSessions)} of {totalSessions} sessions
            </div>
            <div class="flex items-center gap-2">
              <button
                on:click={previousPage}
                disabled={!hasPrevious}
                class="px-3 py-1 bg-white border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                <i class="fas fa-chevron-left mr-1"></i>
                Previous
              </button>
              <button
                on:click={nextPage}
                disabled={!hasMore}
                class="px-3 py-1 bg-white border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Next
                <i class="fas fa-chevron-right ml-1"></i>
              </button>
            </div>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .activity-tracker-container {
    @apply p-6;
  }
  
  /* Ensure user messages have white text on blue background - with high specificity */
  .activity-tracker-container .bg-oxford-blue,
  .activity-tracker-container .bg-oxford-blue *,
  .activity-tracker-container .bg-oxford-blue.text-white,
  .activity-tracker-container .bg-oxford-blue.text-white * {
    color: #ffffff !important;
  }
  
  /* User message text elements - force white color for all nested elements */
  .activity-tracker-container div.bg-oxford-blue div,
  .activity-tracker-container div.bg-oxford-blue span,
  .activity-tracker-container div.bg-oxford-blue p {
    color: #ffffff !important;
  }
</style>

