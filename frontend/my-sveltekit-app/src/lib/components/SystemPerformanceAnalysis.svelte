<!-- System Performance Analysis Component -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  
  export let projectId: string;
  
  let loading = true;
  let error: string | null = null;
  let experimentData: any = null;
  
  // Experiment metrics state
  let intelligentDelegation: any = null;
  let delegationOverhead: any = null;
  let sequentialVsParallel: any = null;
  let docawareImpact: any = null;
  let perAgentVsWorkflowRAG: any = null;
  let concurrentLoad: any = null;
  let agentStatistics: any[] = [];
  let configurations: any = {};
  
  // Helper function to format configuration
  function formatConfiguration(expType: string, hasData: boolean = false): string {
    // If no data exists, don't show a default configuration
    if (!hasData) {
      return 'N/A';
    }
    
    const config = configurations[expType];
    if (!config || Object.keys(config).length === 0) {
      return 'N/A';
    }
    
    // Format based on experiment type using actual stored configuration
    switch(expType) {
      case 'intelligent_delegation':
        const delegateCount = config.delegate_count;
        const threshold = config.confidence_threshold;
        if (delegateCount !== undefined && threshold !== undefined) {
          return `${delegateCount} delegates, θ=${threshold}`;
        }
        return 'N/A';
      case 'delegation_overhead':
        if (config.delegate_count !== undefined) {
          return `${config.delegate_count} delegates`;
        }
        return 'N/A';
      case 'sequential_vs_parallel':
        const agentCount = config.agent_count;
        const ragStatus = config.has_rag !== undefined ? (config.has_rag ? 'RAG' : 'No RAG') : '';
        if (agentCount !== undefined) {
          return ragStatus ? `${agentCount} agents, ${ragStatus}` : `${agentCount} agents`;
        }
        return 'N/A';
      case 'docaware_impact':
        return '2 agents, RAG on vs off';
      case 'per_agent_vs_workflow_rag':
        return 'Legal+Technical agents';
      case 'concurrent_load':
        return 'Full system';
      default:
        return JSON.stringify(config);
    }
  }
  
  onMount(() => {
    loadExperimentMetrics();
  });
  
  async function loadExperimentMetrics() {
    try {
      loading = true;
      error = null;
      
      // Fetch experiment metrics from backend
      experimentData = await cleanUniversalApi.getExperimentMetrics(projectId);
      
      // Parse and organize metrics by experiment type
      if (experimentData) {
        intelligentDelegation = experimentData.intelligent_delegation || null;
        delegationOverhead = experimentData.delegation_overhead || null;
        sequentialVsParallel = experimentData.sequential_vs_parallel || null;
        docawareImpact = experimentData.docaware_impact || null;
        perAgentVsWorkflowRAG = experimentData.per_agent_vs_workflow_rag || null;
        concurrentLoad = experimentData.concurrent_load || null;
        agentStatistics = experimentData.agent_statistics || [];
        
        // Store configurations for display
        configurations = experimentData.configurations || {};
      }
    } catch (err: any) {
      console.error('❌ Failed to load experiment metrics:', err);
      error = err.message || 'Failed to load experiment metrics';
    } finally {
      loading = false;
    }
  }
  
  function formatNumber(value: number | null | undefined, decimals: number = 2): string {
    if (value === null || value === undefined) return 'N/A';
    return value.toFixed(decimals);
  }
  
  function formatPercentage(value: number | null | undefined): string {
    if (value === null || value === undefined) return 'N/A';
    return `${value.toFixed(1)}%`;
  }
</script>

<div class="system-performance-analysis">
  <div class="mb-6">
    <h2 class="text-2xl font-bold text-gray-900 flex items-center">
      <i class="fas fa-chart-bar mr-3 text-oxford-blue"></i>
      System Performance Analysis
    </h2>
    <p class="text-gray-600 mt-2">Comprehensive performance evaluation metrics for AICC-IntelliDoc system</p>
  </div>
  
  {#if loading}
    <div class="flex items-center justify-center min-h-96">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
        <p class="text-oxford-blue">Loading experiment metrics...</p>
      </div>
    </div>
  {:else if error}
    <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
      <div class="flex items-center">
        <i class="fas fa-exclamation-triangle text-red-600 mr-2"></i>
        <p class="text-red-800">{error}</p>
      </div>
      <button
        class="mt-3 px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors"
        on:click={loadExperimentMetrics}
      >
        <i class="fas fa-refresh mr-2"></i>
        Retry
      </button>
    </div>
  {:else}
    <div class="space-y-6">
      <!-- Experiment 1: Intelligent Delegation Accuracy -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <i class="fas fa-route mr-2 text-oxford-blue"></i>
          Experiment 1: Intelligent Delegation Accuracy
        </h3>
        <div class="mb-4">
          <p class="text-sm text-gray-600 mb-2"><strong>Configuration:</strong> {formatConfiguration('intelligent_delegation', intelligentDelegation !== null && intelligentDelegation.routing_accuracy !== undefined)}</p>
          {#if intelligentDelegation?.message}
            <div class="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p class="text-sm text-yellow-800">
                <i class="fas fa-info-circle mr-2"></i>
                {intelligentDelegation.message}
              </p>
            </div>
          {/if}
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Metric</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Routing Accuracy (%)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if intelligentDelegation?.routing_accuracy !== undefined && intelligentDelegation.routing_accuracy !== null}
                    {formatPercentage(intelligentDelegation.routing_accuracy)}
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Broadcast Rate (%)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if intelligentDelegation?.broadcast_rate !== undefined && intelligentDelegation.broadcast_rate !== null}
                    {formatPercentage(intelligentDelegation.broadcast_rate)}
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Experiment 2: Delegation Processing Overhead -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <i class="fas fa-clock mr-2 text-oxford-blue"></i>
          Experiment 2: Delegation Processing Overhead
        </h3>
        <div class="mb-4">
          <p class="text-sm text-gray-600 mb-2"><strong>Configuration:</strong> {formatConfiguration('delegation_overhead', delegationOverhead !== null && delegationOverhead.query_analysis_time_ms !== undefined)}</p>
          {#if delegationOverhead?.message}
            <div class="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p class="text-sm text-yellow-800">
                <i class="fas fa-info-circle mr-2"></i>
                {delegationOverhead.message}
              </p>
            </div>
          {/if}
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Metric</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Query Analysis Time (ms)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if delegationOverhead?.query_analysis_time_ms !== undefined && delegationOverhead.query_analysis_time_ms !== null}
                    {formatNumber(delegationOverhead.query_analysis_time_ms, 1)} ms
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Matching Time (ms)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if delegationOverhead?.matching_time_ms !== undefined && delegationOverhead.matching_time_ms !== null}
                    {formatNumber(delegationOverhead.matching_time_ms, 1)} ms
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Experiment 3: Sequential vs Parallel Execution -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <i class="fas fa-tasks mr-2 text-oxford-blue"></i>
          Experiment 3: Sequential vs Parallel Execution
        </h3>
        <div class="mb-4">
          <p class="text-sm text-gray-600 mb-2"><strong>Configuration:</strong> {formatConfiguration('sequential_vs_parallel', sequentialVsParallel !== null && sequentialVsParallel.sequential_time_s !== undefined)}</p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Metric</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Total Time - Sequential (s)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if sequentialVsParallel?.sequential_time_s !== undefined}
                    {formatNumber(sequentialVsParallel.sequential_time_s, 3)} s
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Total Time - Parallel (s)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if sequentialVsParallel?.parallel_time_s !== undefined}
                    {formatNumber(sequentialVsParallel.parallel_time_s, 3)} s
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Speedup Factor</td>
                <td class="px-4 py-3 text-sm font-semibold text-green-600">
                  {#if sequentialVsParallel?.speedup_factor !== undefined}
                    {formatNumber(sequentialVsParallel.speedup_factor, 2)}x
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Experiment 4: DocAware Impact -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <i class="fas fa-book-reader mr-2 text-oxford-blue"></i>
          Experiment 4: DocAware Impact
        </h3>
        <div class="mb-4">
          <p class="text-sm text-gray-600 mb-2"><strong>Configuration:</strong> {formatConfiguration('docaware_impact')}</p>
          {#if docawareImpact?.message}
            <div class="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p class="text-sm text-yellow-800">
                <i class="fas fa-info-circle mr-2"></i>
                {docawareImpact.message}
              </p>
            </div>
          {/if}
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Metric</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">BERTScore Δ</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if docawareImpact?.bertscore_delta !== undefined}
                    {formatNumber(docawareImpact.bertscore_delta, 3)}
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Retrieval Overhead (ms)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if docawareImpact?.retrieval_overhead_ms !== undefined}
                    {formatNumber(docawareImpact.retrieval_overhead_ms, 1)} ms
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Experiment 5: Per-Agent vs Workflow-Level RAG -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <i class="fas fa-layer-group mr-2 text-oxford-blue"></i>
          Experiment 5: Per-Agent vs Workflow-Level RAG
        </h3>
        <div class="mb-4">
          <p class="text-sm text-gray-600 mb-2"><strong>Configuration:</strong> {formatConfiguration('per_agent_vs_workflow_rag')}</p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Metric</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Response Relevance (%)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if perAgentVsWorkflowRAG?.response_relevance !== undefined}
                    {formatPercentage(perAgentVsWorkflowRAG.response_relevance)}
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Cross-contamination Rate (%)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if perAgentVsWorkflowRAG?.cross_contamination_rate !== undefined}
                    {formatPercentage(perAgentVsWorkflowRAG.cross_contamination_rate)}
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Experiment 6: Concurrent Load (10 users) -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <i class="fas fa-users mr-2 text-oxford-blue"></i>
          Experiment 6: Concurrent Load (10 users)
        </h3>
        <div class="mb-4">
          <p class="text-sm text-gray-600 mb-2"><strong>Configuration:</strong> {formatConfiguration('concurrent_load')}</p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Metric</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Value</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">P95 Latency (s)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if concurrentLoad?.p95_latency_s !== undefined}
                    {formatNumber(concurrentLoad.p95_latency_s, 3)} s
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
              <tr>
                <td class="px-4 py-3 text-sm text-gray-900">Throughput (req/min)</td>
                <td class="px-4 py-3 text-sm font-semibold text-oxford-blue">
                  {#if concurrentLoad?.throughput_req_min !== undefined}
                    {formatNumber(concurrentLoad.throughput_req_min, 1)} req/min
                  {:else}
                    <span class="text-gray-400">No data</span>
                  {/if}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- Experiment 7: Agent Statistics -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <i class="fas fa-robot mr-2 text-oxford-blue"></i>
          Agent Performance Statistics
        </h3>
        <div class="mb-4">
          <p class="text-sm text-gray-600 mb-2">Performance metrics for each agent orchestrated in workflows</p>
        </div>
        {#if agentStatistics && agentStatistics.length > 0}
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Agent Name</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Type</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Executions</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Messages</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Avg Response (ms)</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Min/Max (ms)</th>
                  <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">Total Tokens</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                {#each agentStatistics as agent}
                  <tr>
                    <td class="px-4 py-3 text-sm font-medium text-gray-900">{agent.agent_name}</td>
                    <td class="px-4 py-3 text-sm text-gray-600">{agent.agent_type}</td>
                    <td class="px-4 py-3 text-sm text-gray-900">{agent.total_executions}</td>
                    <td class="px-4 py-3 text-sm text-gray-900">{agent.total_messages}</td>
                    <td class="px-4 py-3 text-sm text-gray-900">{formatNumber(agent.avg_response_time_ms, 1)}</td>
                    <td class="px-4 py-3 text-sm text-gray-600">{formatNumber(agent.min_response_time_ms, 0)} / {formatNumber(agent.max_response_time_ms, 0)}</td>
                    <td class="px-4 py-3 text-sm text-gray-900">{agent.total_tokens > 0 ? agent.total_tokens.toLocaleString() : 'N/A'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <div class="text-center py-8 text-gray-500">
            <i class="fas fa-info-circle mb-2"></i>
            <p>No agent statistics available. Run some workflow executions to see agent performance metrics.</p>
          </div>
        {/if}
      </div>
      
      <!-- Refresh Button -->
      <div class="flex justify-end mt-6">
        <button
          class="px-6 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center"
          on:click={loadExperimentMetrics}
        >
          <i class="fas fa-sync-alt mr-2"></i>
          Refresh Metrics
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .system-performance-analysis {
    min-height: 100%;
  }
</style>

