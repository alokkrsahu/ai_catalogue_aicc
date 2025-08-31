<!-- Test page for Human Input implementation (Phase 3) -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { workflowStatus } from '$lib/stores/workflowStatus';
  import { toasts } from '$lib/stores/toast';
  import HumanInputModal from '$lib/components/HumanInputModal.svelte';
  
  let showTestModal = false;
  let testInputData = {
    execution_id: 'test-exec-12345678',
    agent_name: 'Test UserProxy Agent',
    context: {
      input_sources: [
        {
          name: 'Start Node',
          type: 'StartNode',
          content: 'Please analyze the quarterly sales data and provide insights on regional performance trends.',
          priority: 1
        },
        {
          name: 'Data Analyst Agent',
          type: 'AssistantAgent', 
          content: 'I have processed the Q3 sales data. The analysis shows:\n\n• North region: 23% growth\n• South region: 12% decline\n• West region: 8% growth\n• East region: 15% growth\n\nThe South region decline appears to be seasonal. Should we investigate competitor activities or adjust marketing strategy?',
          priority: 2
        }
      ],
      input_count: 2,
      primary_input: 'Analysis complete - awaiting human decision on next steps'
    },
    conversation_history: 'Start Node → Data Analyst Agent → UserProxy Agent (awaiting input)\n\nThe workflow has processed quarterly sales data and identified regional trends. The analysis shows mixed results with most regions growing but South region declining. Human input is needed to decide on the appropriate response strategy.'
  };
  
  // Test functions
  function openTestModal() {
    showTestModal = true;
    console.log('📝 TEST: Opening human input modal with test data');
  }
  
  function handleTestInputSubmitted(event) {
    console.log('✅ TEST: Human input submitted:', event.detail);
    toasts.success(`Test input submitted: ${event.detail.humanInput.slice(0, 50)}...`);
    showTestModal = false;
  }
  
  function handleTestModalClosed() {
    console.log('❌ TEST: Modal closed');
    showTestModal = false;
  }
  
  // Test workflow status polling
  function startTestPolling() {
    console.log('🔄 TEST: Starting workflow status polling');
    workflowStatus.startPolling(5000);
    toasts.info('Started polling for pending human inputs (5s interval)');
  }
  
  function stopTestPolling() {
    console.log('🛑 TEST: Stopping workflow status polling');
    workflowStatus.stopPolling();
    toasts.info('Stopped polling for pending human inputs');
  }
  
  async function refreshInputs() {
    try {
      console.log('🔄 TEST: Manually refreshing inputs');
      await workflowStatus.refreshInputs();
      toasts.success('Inputs refreshed successfully');
    } catch (error) {
      console.error('❌ TEST: Refresh failed:', error);
      toasts.error(`Refresh failed: ${error.message}`);
    }
  }
  
  // Monitor workflow status
  $: console.log('📊 TEST: Workflow status update:', {
    pendingCount: $workflowStatus.pendingInputs.length,
    isPolling: $workflowStatus.isPolling,
    error: $workflowStatus.error,
    lastUpdate: $workflowStatus.lastUpdate
  });
</script>

<svelte:head>
  <title>Human Input Test - Phase 3</title>
</svelte:head>

<div class="min-h-screen bg-gray-50 py-8">
  <div class="max-w-4xl mx-auto px-6">
    <!-- Header -->
    <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
      <div class="flex items-center space-x-4">
        <div class="w-12 h-12 bg-gradient-to-r from-oxford-blue to-blue-700 text-white rounded-xl flex items-center justify-center shadow-lg">
          <i class="fas fa-user-check text-xl"></i>
        </div>
        <div>
          <h1 class="text-2xl font-bold text-gray-900">Human Input Implementation Test</h1>
          <p class="text-gray-600">Phase 3: UserProxyAgent Human-in-the-Loop Testing</p>
        </div>
      </div>
    </div>

    <!-- Status Panel -->
    <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Workflow Status Monitor</h2>
      
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div class="bg-blue-50 p-4 rounded-lg border border-blue-200">
          <div class="text-2xl font-bold text-blue-600">
            {$workflowStatus.pendingInputs.length}
          </div>
          <div class="text-sm text-blue-600">Pending Inputs</div>
        </div>
        
        <div class="bg-{$workflowStatus.isPolling ? 'green' : 'gray'}-50 p-4 rounded-lg border border-{$workflowStatus.isPolling ? 'green' : 'gray'}-200">
          <div class="text-sm font-medium text-{$workflowStatus.isPolling ? 'green' : 'gray'}-700">
            {$workflowStatus.isPolling ? '🔄 Polling Active' : '⏸️ Polling Inactive'}
          </div>
          <div class="text-xs text-{$workflowStatus.isPolling ? 'green' : 'gray'}-600">
            {$workflowStatus.lastUpdate ? `Last: ${new Date($workflowStatus.lastUpdate).toLocaleTimeString()}` : 'No updates'}
          </div>
        </div>
        
        <div class="bg-{$workflowStatus.error ? 'red' : 'gray'}-50 p-4 rounded-lg border border-{$workflowStatus.error ? 'red' : 'gray'}-200">
          <div class="text-sm font-medium text-{$workflowStatus.error ? 'red' : 'gray'}-700">
            {$workflowStatus.error ? '❌ Error' : '✅ No Errors'}
          </div>
          <div class="text-xs text-{$workflowStatus.error ? 'red' : 'gray'}-600">
            {$workflowStatus.error || 'System operational'}
          </div>
        </div>
      </div>
      
      <div class="flex space-x-3">
        <button
          class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          on:click={startTestPolling}
          disabled={$workflowStatus.isPolling}
        >
          <i class="fas fa-play mr-2"></i>
          Start Polling
        </button>
        
        <button
          class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          on:click={stopTestPolling}
          disabled={!$workflowStatus.isPolling}
        >
          <i class="fas fa-stop mr-2"></i>
          Stop Polling
        </button>
        
        <button
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          on:click={refreshInputs}
          disabled={$workflowStatus.isLoading}
        >
          <i class="fas fa-sync-alt mr-2"></i>
          Manual Refresh
        </button>
      </div>
    </div>

    <!-- Test Controls -->
    <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Test Controls</h2>
      
      <div class="space-y-4">
        <div>
          <button
            class="px-6 py-3 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors font-medium shadow-lg hover:shadow-xl"
            on:click={openTestModal}
          >
            <i class="fas fa-user-check mr-2"></i>
            Open Test Human Input Modal
          </button>
          <p class="text-sm text-gray-600 mt-2">
            Opens a simulated human input modal with sample data to test the UI components
          </p>
        </div>
      </div>
    </div>

    <!-- Implementation Status -->
    <div class="bg-white rounded-xl shadow-lg p-6">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Phase 3 Implementation Status</h2>
      
      <div class="space-y-3">
        <div class="flex items-center space-x-3 text-sm">
          <i class="fas fa-check-circle text-green-500"></i>
          <span class="text-gray-700"><strong>Backend:</strong> Human input API endpoints implemented</span>
        </div>
        <div class="flex items-center space-x-3 text-sm">
          <i class="fas fa-check-circle text-green-500"></i>
          <span class="text-gray-700"><strong>Database:</strong> HumanInputInteraction model ready</span>
        </div>
        <div class="flex items-center space-x-3 text-sm">
          <i class="fas fa-check-circle text-green-500"></i>
          <span class="text-gray-700"><strong>Service:</strong> humanInputService.ts API client</span>
        </div>
        <div class="flex items-center space-x-3 text-sm">
          <i class="fas fa-check-circle text-green-500"></i>
          <span class="text-gray-700"><strong>Store:</strong> workflowStatus.ts reactive store</span>
        </div>
        <div class="flex items-center space-x-3 text-sm">
          <i class="fas fa-check-circle text-green-500"></i>
          <span class="text-gray-700"><strong>Modal:</strong> HumanInputModal.svelte component</span>
        </div>
        <div class="flex items-center space-x-3 text-sm">
          <i class="fas fa-check-circle text-green-500"></i>
          <span class="text-gray-700"><strong>Integration:</strong> AgentOrchestrationInterface polling & modal</span>
        </div>
      </div>
      
      <div class="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
        <div class="flex items-start">
          <i class="fas fa-info-circle text-green-600 mt-1 mr-3"></i>
          <div class="text-sm text-green-700">
            <p class="font-medium mb-2">🎉 Phase 3 Implementation Complete!</p>
            <p>The UserProxyAgent human-in-the-loop system is fully implemented with:</p>
            <ul class="list-disc list-inside mt-2 space-y-1 ml-4">
              <li>Real-time polling for pending human input requests</li>
              <li>Beautiful modal interface for human responses</li>
              <li>Automatic workflow resumption after input submission</li>
              <li>Visual status indicators and notifications</li>
              <li>Error handling and loading states</li>
              <li>Integration with existing workflow designer</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Test Human Input Modal -->
{#if showTestModal}
  <HumanInputModal
    executionId={testInputData.execution_id}
    agentName={testInputData.agent_name}
    inputContext={testInputData.context}
    conversationHistory={testInputData.conversation_history}
    isVisible={showTestModal}
    on:inputSubmitted={handleTestInputSubmitted}
    on:close={handleTestModalClosed}
  />
{/if}

<style>
  :global(.oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
</style>
