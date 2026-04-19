<!--
  System Performance Analysis — admin-facing analytics page.

  Two sub-tabs:

  1. "Project Analytics" (general / project-wide)
     - Sequential vs Parallel execution timings
     - DocAware impact (RAG on vs off)
     - Agent performance statistics (project-wide)
     - Cache tier breakdown (websearch calls by cache layer)
     - Summary-job health (recent summarize-urls thread runs)
     - Splitter + classifier decision aggregates

  2. "Workflow Performance" (per-workflow drill-down)
     - Dropdown of recent WorkflowExecution rows
     - When selected, re-fetches experiment-metrics scoped to that
       execution_id so the cards show metrics for ONE run only.

  Backend surface used:
     GET /projects/<id>/experiment-metrics/?execution_id=<optional>
     GET /projects/<id>/analytics/
     GET /projects/<id>/recent-executions/?limit=50
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';

  export let projectId: string;

  type Tab = 'project' | 'workflow';
  let activeTab: Tab = 'project';

  // Shared loading flags.
  let loading = true;
  let error: string | null = null;

  // Project-wide data (unfiltered experiment-metrics + /analytics/).
  let projectExperiment: any = null;
  let projectAnalytics: any = null;

  // Per-workflow data — only populated when the user picks an execution.
  let recentExecutions: Array<any> = [];
  let recentLoading = false;
  let selectedExecutionId: string | null = null;
  let workflowExperiment: any = null;
  let workflowLoading = false;

  onMount(() => {
    loadProjectScope();
  });

  async function loadProjectScope() {
    loading = true;
    error = null;
    try {
      // Fire both in parallel.
      const [expData, analyticsData] = await Promise.all([
        cleanUniversalApi.getExperimentMetrics(projectId),
        cleanUniversalApi.getAnalytics(projectId).catch((e) => {
          console.warn('analytics load failed:', e);
          return null;
        }),
      ]);
      projectExperiment = expData || null;
      projectAnalytics = analyticsData || null;
    } catch (err: any) {
      console.error('❌ Failed to load experiment metrics:', err);
      error = err?.message || 'Failed to load experiment metrics';
    } finally {
      loading = false;
    }
  }

  async function loadRecentExecutions() {
    recentLoading = true;
    try {
      const res = await cleanUniversalApi.getRecentExecutions(projectId, 50);
      recentExecutions = res?.executions || [];
    } catch (err) {
      console.warn('recent executions load failed:', err);
      recentExecutions = [];
    } finally {
      recentLoading = false;
    }
  }

  async function loadWorkflowMetrics(executionId: string) {
    workflowLoading = true;
    workflowExperiment = null;
    try {
      workflowExperiment = await cleanUniversalApi.getExperimentMetrics(projectId, { executionId });
    } catch (err) {
      console.warn('per-execution metrics load failed:', err);
      workflowExperiment = null;
    } finally {
      workflowLoading = false;
    }
  }

  // When the user switches to Workflow Performance for the first time,
  // lazy-load the recent-executions list.
  $: if (activeTab === 'workflow' && !recentExecutions.length && !recentLoading) {
    loadRecentExecutions();
  }

  // Load metrics whenever a new execution is chosen.
  $: if (activeTab === 'workflow' && selectedExecutionId) {
    loadWorkflowMetrics(selectedExecutionId);
  }

  // ---- formatting helpers ---------------------------------------------

  function fmt(value: number | null | undefined, decimals = 2): string {
    if (value === null || value === undefined) return 'N/A';
    return Number(value).toFixed(decimals);
  }

  function pct(value: number | null | undefined): string {
    if (value === null || value === undefined) return 'N/A';
    return `${Number(value).toFixed(1)}%`;
  }

  function titleTier(tier: string): string {
    switch (tier) {
      case 'flag_alive': return 'Flag alive (skip all work)';
      case 'content_hash': return 'Content-hash match (skip embed)';
      case 'embed_cache': return 'Embedding cache hit';
      case 'url_cache': return 'URL content cache hit';
      case 'search_cache': return 'Search-result cache hit';
      case 'cold': return 'Cold run (full pipeline)';
      case 'mixed': return 'Mixed tiers';
      default: return tier || 'unknown';
    }
  }
</script>

<div class="system-performance-analysis">
  <!-- Header -->
  <div class="mb-6">
    <h2 class="text-2xl font-bold text-gray-900 flex items-center">
      <i class="fas fa-chart-bar mr-3 text-oxford-blue"></i>
      System Performance Analysis
    </h2>
    <p class="text-gray-600 mt-2">Admin performance dashboard. Switch between project-wide aggregates and per-workflow drill-downs.</p>
  </div>

  <!-- Tab bar -->
  <div class="border-b border-gray-200 mb-6">
    <nav class="-mb-px flex space-x-6">
      <button
        class="py-3 px-1 border-b-2 text-sm font-medium transition-colors {activeTab === 'project'
          ? 'border-oxford-blue text-oxford-blue'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
        on:click={() => (activeTab = 'project')}
      >
        <i class="fas fa-layer-group mr-2"></i>
        Project Analytics
      </button>
      <button
        class="py-3 px-1 border-b-2 text-sm font-medium transition-colors {activeTab === 'workflow'
          ? 'border-oxford-blue text-oxford-blue'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
        on:click={() => (activeTab = 'workflow')}
      >
        <i class="fas fa-project-diagram mr-2"></i>
        Workflow Performance
      </button>
    </nav>
  </div>

  {#if loading}
    <div class="flex items-center justify-center min-h-96">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
        <p class="text-oxford-blue">Loading project analytics…</p>
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
        on:click={loadProjectScope}
      >
        <i class="fas fa-refresh mr-2"></i>Retry
      </button>
    </div>
  {:else if activeTab === 'project'}
    <!-- ==================================================================
         PROJECT ANALYTICS TAB
    =================================================================== -->
    {@const exp = projectExperiment || {}}
    {@const ana = projectAnalytics || {}}
    <div class="space-y-6">
      <!-- Sequential vs Parallel -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-tasks mr-2 text-oxford-blue"></i>Sequential vs Parallel Execution</h3>
        {#if exp.sequential_vs_parallel}
          <table class="min-w-full divide-y divide-gray-200">
            <tbody class="bg-white divide-y divide-gray-200">
              <tr><td class="px-4 py-2 text-sm">Sequential avg</td><td class="px-4 py-2 text-sm font-semibold">{fmt(exp.sequential_vs_parallel.sequential_time_s, 3)} s</td></tr>
              <tr><td class="px-4 py-2 text-sm">Parallel avg</td><td class="px-4 py-2 text-sm font-semibold">{fmt(exp.sequential_vs_parallel.parallel_time_s, 3)} s</td></tr>
              <tr><td class="px-4 py-2 text-sm">Speedup</td><td class="px-4 py-2 text-sm font-semibold text-green-600">{fmt(exp.sequential_vs_parallel.speedup_factor, 2)}×</td></tr>
            </tbody>
          </table>
        {:else}
          <p class="text-sm text-gray-500">No workflow execution metrics yet.</p>
        {/if}
      </div>

      <!-- DocAware Impact -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-book-reader mr-2 text-oxford-blue"></i>DocAware Impact</h3>
        {#if exp.docaware_impact}
          <table class="min-w-full divide-y divide-gray-200">
            <tbody class="bg-white divide-y divide-gray-200">
              <tr><td class="px-4 py-2 text-sm">BERTScore Δ (RAG − no RAG)</td><td class="px-4 py-2 text-sm font-semibold">{fmt(exp.docaware_impact.bertscore_delta, 3)}</td></tr>
              <tr><td class="px-4 py-2 text-sm">Avg retrieval overhead</td><td class="px-4 py-2 text-sm font-semibold">{fmt(exp.docaware_impact.retrieval_overhead_ms, 1)} ms</td></tr>
            </tbody>
          </table>
          {#if exp.docaware_impact.message}
            <p class="mt-3 text-xs text-amber-700"><i class="fas fa-info-circle mr-1"></i>{exp.docaware_impact.message}</p>
          {/if}
        {:else}
          <p class="text-sm text-gray-500">No DocAware metrics yet.</p>
        {/if}
      </div>

      <!-- Cache Tier Breakdown -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-database mr-2 text-oxford-blue"></i>Cache Tier Breakdown</h3>
        <p class="text-sm text-gray-500 mb-4">How often each websearch cache layer saved work. Derived from <code>websearch</code> + <code>websearch_index_batch</code> metrics.</p>
        {#if ana.cache_tier_breakdown}
          {@const callTiers = ana.cache_tier_breakdown.call_tier_counts || {}}
          {@const urlTotals = ana.cache_tier_breakdown.url_tier_totals || {}}
          <div class="grid md:grid-cols-2 gap-6">
            <div>
              <div class="text-sm font-medium text-gray-700 mb-2">Websearch calls (last 50) by tier</div>
              {#if Object.keys(callTiers).length}
                <ul class="text-sm divide-y divide-gray-100">
                  {#each Object.entries(callTiers) as [tier, count]}
                    <li class="py-1.5 flex justify-between">
                      <span>{titleTier(tier)}</span>
                      <span class="font-semibold">{count}</span>
                    </li>
                  {/each}
                </ul>
              {:else}
                <p class="text-xs text-gray-400">No websearch calls recorded yet.</p>
              {/if}
            </div>
            <div>
              <div class="text-sm font-medium text-gray-700 mb-2">Sync-index URL hits (cumulative)</div>
              <table class="min-w-full text-sm">
                <tbody>
                  <tr><td class="py-1.5">Sync runs</td><td class="text-right font-semibold">{urlTotals.sync_runs ?? 0}</td></tr>
                  <tr><td class="py-1.5">URLs processed</td><td class="text-right font-semibold">{urlTotals.n_urls ?? 0}</td></tr>
                  <tr><td class="py-1.5">Flag alive</td><td class="text-right font-semibold text-green-700">{urlTotals.flag_alive_hits ?? 0}</td></tr>
                  <tr><td class="py-1.5">Content-hash hits</td><td class="text-right font-semibold text-green-700">{urlTotals.content_hash_hits ?? 0}</td></tr>
                  <tr><td class="py-1.5">Embed cache hits</td><td class="text-right font-semibold text-blue-700">{urlTotals.embed_cache_hits ?? 0}</td></tr>
                  <tr><td class="py-1.5">Cold</td><td class="text-right font-semibold text-amber-700">{urlTotals.cold_count ?? 0}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          {#if ana.websearch?.cache_hit_rate != null}
            <p class="mt-4 text-sm text-gray-600">Overall cache-hit rate: <span class="font-semibold text-oxford-blue">{pct(ana.websearch.cache_hit_rate)}</span> ({ana.websearch.sample_count} samples)</p>
          {/if}
        {:else}
          <p class="text-sm text-gray-500">No cache data available yet.</p>
        {/if}
      </div>

      <!-- Summary Job Health -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-magic mr-2 text-oxford-blue"></i>URL-Summary Job Health</h3>
        <p class="text-sm text-gray-500 mb-4">Last 20 background <code>summarize-urls</code> jobs. Helps spot stuck or failing generations.</p>
        {#if ana.summary_jobs && ana.summary_jobs.total_jobs > 0}
          <div class="mb-3 text-sm"><span class="text-green-700 font-semibold">{ana.summary_jobs.ok_count} ok</span> · <span class="text-red-700 font-semibold">{ana.summary_jobs.error_count} errors</span> across {ana.summary_jobs.total_jobs} jobs</div>
          <div class="overflow-x-auto">
            <table class="min-w-full text-sm divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">When</th>
                  <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">Status</th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-gray-600">Queued</th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-gray-600">Done</th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-gray-600">Failed</th>
                  <th class="px-3 py-2 text-right text-xs font-medium text-gray-600">Duration</th>
                  <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">Model</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                {#each ana.summary_jobs.recent as j}
                  <tr>
                    <td class="px-3 py-2 text-xs text-gray-600">{new Date(j.date).toLocaleString()}</td>
                    <td class="px-3 py-2"><span class="text-xs px-2 py-0.5 rounded-full {j.status === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}">{j.status}</span></td>
                    <td class="px-3 py-2 text-right">{j.urls_queued ?? '—'}</td>
                    <td class="px-3 py-2 text-right text-green-700">{j.summarized ?? '—'}</td>
                    <td class="px-3 py-2 text-right text-red-700">{j.failed ?? '—'}</td>
                    <td class="px-3 py-2 text-right">{j.duration_ms != null ? `${(j.duration_ms / 1000).toFixed(1)} s` : '—'}</td>
                    <td class="px-3 py-2 text-xs text-gray-500">{j.llm_model ?? ''}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="text-sm text-gray-500">No summarize-urls jobs have run for this project yet.</p>
        {/if}
      </div>

      <!-- Splitter + Classifier stats -->
      {#if exp.splitter_stats || exp.classifier_stats}
        <div class="bg-white rounded-lg shadow-md p-6">
          <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-code-branch mr-2 text-oxford-blue"></i>Branching Decisions</h3>
          <div class="grid md:grid-cols-2 gap-6">
            {#if exp.splitter_stats}
              <div>
                <div class="text-sm font-medium text-gray-700 mb-2">Splitter</div>
                <p class="text-xs text-gray-500 mb-2">{exp.splitter_stats.total_decisions} decisions · avg {fmt(exp.splitter_stats.avg_duration_ms, 0)} ms · avg {fmt(exp.splitter_stats.avg_allocated, 1)} allocated / {fmt(exp.splitter_stats.avg_pruned, 1)} pruned</p>
                {#if exp.splitter_stats.top_targets?.length}
                  <ul class="text-sm divide-y divide-gray-100">
                    {#each exp.splitter_stats.top_targets as t}
                      <li class="py-1 flex justify-between"><span>{t.agent_name}</span><span class="font-semibold">{t.allocations}</span></li>
                    {/each}
                  </ul>
                {/if}
              </div>
            {/if}
            {#if exp.classifier_stats}
              <div>
                <div class="text-sm font-medium text-gray-700 mb-2">Classifier</div>
                <p class="text-xs text-gray-500 mb-2">{exp.classifier_stats.total_decisions} decisions · avg {fmt(exp.classifier_stats.avg_duration_ms, 0)} ms</p>
                {#if exp.classifier_stats.category_distribution?.length}
                  <ul class="text-sm divide-y divide-gray-100">
                    {#each exp.classifier_stats.category_distribution as c}
                      <li class="py-1 flex justify-between"><span>{c.category_name}</span><span class="font-semibold">{c.count}</span></li>
                    {/each}
                  </ul>
                {/if}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Agent Statistics (project-wide) -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-robot mr-2 text-oxford-blue"></i>Agent Performance (project-wide)</h3>
        {#if exp.agent_statistics?.length}
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-600">Agent</th>
                  <th class="px-4 py-2 text-left text-xs font-medium text-gray-600">Type</th>
                  <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Execs</th>
                  <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Msgs</th>
                  <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Avg ms</th>
                  <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Min / Max</th>
                  <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Tokens</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                {#each exp.agent_statistics as a}
                  <tr>
                    <td class="px-4 py-2 text-sm font-medium">{a.agent_name}</td>
                    <td class="px-4 py-2 text-sm text-gray-600">{a.agent_type}</td>
                    <td class="px-4 py-2 text-sm text-right">{a.total_executions}</td>
                    <td class="px-4 py-2 text-sm text-right">{a.total_messages}</td>
                    <td class="px-4 py-2 text-sm text-right">{fmt(a.avg_response_time_ms, 1)}</td>
                    <td class="px-4 py-2 text-xs text-right text-gray-500">{fmt(a.min_response_time_ms, 0)} / {fmt(a.max_response_time_ms, 0)}</td>
                    <td class="px-4 py-2 text-sm text-right">{a.total_tokens > 0 ? a.total_tokens.toLocaleString() : 'N/A'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="text-sm text-gray-500">No agent statistics yet — run some workflows to populate.</p>
        {/if}
      </div>

      <div class="flex justify-end">
        <button class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors" on:click={loadProjectScope}>
          <i class="fas fa-sync-alt mr-2"></i>Refresh
        </button>
      </div>
    </div>
  {:else}
    <!-- ==================================================================
         WORKFLOW PERFORMANCE TAB
    =================================================================== -->
    <div class="space-y-6">
      <div class="bg-white rounded-lg shadow-md p-6">
        <label class="block text-sm font-medium text-gray-700 mb-2" for="exec-picker">Workflow Execution</label>
        <div class="flex items-center gap-3">
          <select
            id="exec-picker"
            class="flex-1 px-3 py-2 border border-gray-300 rounded-lg bg-white"
            bind:value={selectedExecutionId}
            disabled={recentLoading || !recentExecutions.length}
          >
            <option value={null} disabled>{recentLoading ? 'Loading executions…' : 'Select a run to drill into'}</option>
            {#each recentExecutions as ex}
              <option value={ex.execution_id}>
                {ex.workflow_name} · {new Date(ex.started_at).toLocaleString()} · {ex.status}{ex.duration_s != null ? ` · ${fmt(ex.duration_s, 1)} s` : ''}
              </option>
            {/each}
          </select>
          <button class="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50" on:click={loadRecentExecutions}>
            <i class="fas fa-sync-alt mr-1"></i>Refresh list
          </button>
        </div>
        {#if !recentLoading && !recentExecutions.length}
          <p class="mt-2 text-xs text-gray-500">No executions recorded for this project yet.</p>
        {/if}
      </div>

      {#if selectedExecutionId}
        {#if workflowLoading}
          <div class="flex items-center justify-center py-10">
            <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-oxford-blue"></div>
          </div>
        {:else if workflowExperiment}
          {@const wx = workflowExperiment}
          <!-- Per-run cards: same layout as project tab but filtered -->
          <div class="bg-white rounded-lg shadow-md p-6">
            <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-tasks mr-2 text-oxford-blue"></i>Timing (this run)</h3>
            {#if wx.sequential_vs_parallel}
              <table class="min-w-full divide-y divide-gray-200">
                <tbody class="bg-white divide-y divide-gray-200">
                  <tr><td class="px-4 py-2 text-sm">Sequential (s)</td><td class="px-4 py-2 text-sm font-semibold">{fmt(wx.sequential_vs_parallel.sequential_time_s, 3)}</td></tr>
                  <tr><td class="px-4 py-2 text-sm">Parallel (s)</td><td class="px-4 py-2 text-sm font-semibold">{fmt(wx.sequential_vs_parallel.parallel_time_s, 3)}</td></tr>
                  <tr><td class="px-4 py-2 text-sm">Speedup</td><td class="px-4 py-2 text-sm font-semibold text-green-600">{fmt(wx.sequential_vs_parallel.speedup_factor, 2)}×</td></tr>
                </tbody>
              </table>
            {:else}
              <p class="text-sm text-gray-500">No workflow-execution metric row for this run yet.</p>
            {/if}
          </div>

          {#if wx.splitter_stats || wx.classifier_stats}
            <div class="bg-white rounded-lg shadow-md p-6">
              <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-code-branch mr-2 text-oxford-blue"></i>Branching decisions (this run)</h3>
              <div class="grid md:grid-cols-2 gap-6">
                {#if wx.splitter_stats}
                  <div>
                    <div class="text-sm font-medium text-gray-700 mb-2">Splitter</div>
                    <p class="text-xs text-gray-500 mb-2">{wx.splitter_stats.total_decisions} decisions · avg {fmt(wx.splitter_stats.avg_duration_ms, 0)} ms</p>
                    {#each wx.splitter_stats.top_targets || [] as t}
                      <div class="text-sm flex justify-between py-1"><span>{t.agent_name}</span><span class="font-semibold">{t.allocations}</span></div>
                    {/each}
                  </div>
                {/if}
                {#if wx.classifier_stats}
                  <div>
                    <div class="text-sm font-medium text-gray-700 mb-2">Classifier</div>
                    <p class="text-xs text-gray-500 mb-2">{wx.classifier_stats.total_decisions} decisions · avg {fmt(wx.classifier_stats.avg_duration_ms, 0)} ms</p>
                    {#each wx.classifier_stats.category_distribution || [] as c}
                      <div class="text-sm flex justify-between py-1"><span>{c.category_name}</span><span class="font-semibold">{c.count}</span></div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <div class="bg-white rounded-lg shadow-md p-6">
            <h3 class="text-xl font-bold text-gray-900 mb-4"><i class="fas fa-robot mr-2 text-oxford-blue"></i>Agent Performance (this run)</h3>
            {#if wx.agent_statistics?.length}
              <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                  <thead class="bg-gray-50">
                    <tr>
                      <th class="px-4 py-2 text-left text-xs font-medium text-gray-600">Agent</th>
                      <th class="px-4 py-2 text-left text-xs font-medium text-gray-600">Type</th>
                      <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Msgs</th>
                      <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Avg ms</th>
                      <th class="px-4 py-2 text-right text-xs font-medium text-gray-600">Tokens</th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-gray-200">
                    {#each wx.agent_statistics as a}
                      <tr>
                        <td class="px-4 py-2 text-sm font-medium">{a.agent_name}</td>
                        <td class="px-4 py-2 text-sm text-gray-600">{a.agent_type}</td>
                        <td class="px-4 py-2 text-sm text-right">{a.total_messages}</td>
                        <td class="px-4 py-2 text-sm text-right">{fmt(a.avg_response_time_ms, 1)}</td>
                        <td class="px-4 py-2 text-sm text-right">{a.total_tokens > 0 ? a.total_tokens.toLocaleString() : 'N/A'}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <p class="text-sm text-gray-500">No per-agent data for this run.</p>
            {/if}
          </div>
        {/if}
      {:else}
        <div class="bg-white rounded-lg shadow-sm border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
          Pick a workflow execution above to view per-run performance.
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .system-performance-analysis {
    min-height: 100%;
  }
</style>
