<!-- Analytics Component — Agent Timing Breakdown -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';

  export let projectId: string;

  let loading = true;
  let error: string | null = null;
  let data: any = null;

  // Canvas elements
  let toolCanvas: HTMLCanvasElement;
  let wsCanvas: HTMLCanvasElement;
  let execCanvas: HTMLCanvasElement;

  // Chart instances (destroyed on unmount)
  let charts: any[] = [];

  onMount(() => {
    loadAnalytics();
  });

  onDestroy(() => {
    charts.forEach(c => c.destroy());
    charts = [];
  });

  async function loadAnalytics() {
    try {
      loading = true;
      error = null;
      data = null;
      charts.forEach(c => c.destroy());
      charts = [];

      data = await cleanUniversalApi.getAnalytics(projectId);
    } catch (err: any) {
      error = err.message || 'Failed to load analytics';
    } finally {
      loading = false;
    }
  }

  // Render charts once the DOM has updated with data
  $: if (!loading && !error && data) {
    // Svelte batches DOM updates; use microtask to ensure canvases are mounted
    Promise.resolve().then(renderCharts);
  }

  async function renderCharts() {
    const { Chart, registerables } = await import('chart.js');
    Chart.register(...registerables);

    charts.forEach(c => c.destroy());
    charts = [];

    const OXFORD = '#002147';
    const GREEN  = '#16a34a';
    const AMBER  = '#d97706';
    const RED    = '#dc2626';
    const BLUE   = '#3b82f6';
    const GRAY   = '#9ca3af';

    // ── 1. Tool Call Breakdown ──────────────────────────────────────
    if (toolCanvas && data.tool_breakdown?.length > 0) {
      const tb = data.tool_breakdown.filter((r: any) => r.tool_type !== 'legacy (no timing)');
      const colourMap: Record<string, string> = {
        web_search:    BLUE,
        document_read: OXFORD,
        docaware:      GREEN,
        other:         GRAY,
      };
      charts.push(new Chart(toolCanvas, {
        type: 'bar',
        data: {
          labels: tb.map((r: any) => r.tool_type),
          datasets: [{
            label: 'Avg Response (ms)',
            data: tb.map((r: any) => r.avg_ms),
            backgroundColor: tb.map((r: any) => colourMap[r.tool_type] ?? GRAY),
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { beginAtZero: true, title: { display: true, text: 'ms' } },
          },
        },
      }));
    }

    // ── 3. WebSearch Latency (recent samples) ──────────────────────
    if (wsCanvas && data.websearch?.recent?.length > 0) {
      const recent = [...data.websearch.recent].reverse();
      const durations = recent.map((r: any) => r.duration_ms ?? null);
      const colours = recent.map((r: any) =>
        r.cache_hit === true ? GREEN : r.cache_hit === false ? AMBER : GRAY
      );
      charts.push(new Chart(wsCanvas, {
        type: 'bar',
        data: {
          labels: recent.map((r: any) => r.date),
          datasets: [{
            label: 'Duration (ms)',
            data: durations,
            backgroundColor: colours,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                afterLabel: (ctx: any) => {
                  const r = recent[ctx.dataIndex];
                  const hit = r.cache_hit === true ? 'Cache HIT' : r.cache_hit === false ? 'Cache MISS' : '';
                  return [hit, r.query ? `"${r.query}"` : ''].filter(Boolean).join('\n');
                },
              },
            },
          },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'ms' } },
          },
        },
      }));
    }

    // ── 4. Execution Volume ─────────────────────────────────────────
    if (execCanvas && data.execution_volume?.daily?.length > 0) {
      const daily = data.execution_volume.daily;
      charts.push(new Chart(execCanvas, {
        type: 'bar',
        data: {
          labels: daily.map((r: any) => r.date),
          datasets: [
            {
              label: 'Completed',
              data: daily.map((r: any) => r.completed),
              backgroundColor: GREEN,
              stack: 'exec',
            },
            {
              label: 'Failed',
              data: daily.map((r: any) => r.failed),
              backgroundColor: RED,
              stack: 'exec',
            },
          ],
        },
        options: {
          responsive: true,
          scales: {
            x: { stacked: true },
            y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Executions' } },
          },
        },
      }));
    }
  }

  function fmt(v: number | null | undefined, decimals = 1): string {
    if (v == null) return 'N/A';
    return v.toFixed(decimals);
  }

  // Word cloud helpers
  $: maxWordCount = data?.query_wordcloud?.[0]?.count ?? 1;

  function wordSize(count: number, max: number): string {
    const ratio = max > 1 ? count / max : 1;
    return (0.85 + ratio * 2.35).toFixed(2);
  }

  function wordColor(count: number, max: number): string {
    const ratio = max > 1 ? count / max : 1;
    const PALETTE = [
      '#002147', // oxford blue  — top words
      '#1d4ed8', // blue-700
      '#0e7490', // cyan-700
      '#047857', // emerald-700
      '#6d28d9', // violet-700
      '#92400e', // amber-800
      '#9ca3af', // gray-400  — least frequent
    ];
    const idx = Math.min(Math.floor((1 - ratio) * PALETTE.length), PALETTE.length - 1);
    return PALETTE[idx];
  }
</script>

<div class="project-analytics">
  <div class="mb-6">
    <h2 class="text-2xl font-bold text-gray-900 flex items-center">
      <i class="fas fa-chart-line mr-3 text-oxford-blue"></i>
      Analytics
    </h2>
    <p class="text-gray-600 mt-2">Agent planning time, tool call latency, and execution trends</p>
  </div>

  {#if loading}
    <div class="flex items-center justify-center min-h-96">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
        <p class="text-oxford-blue">Loading analytics...</p>
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
        on:click={loadAnalytics}
      >
        <i class="fas fa-refresh mr-2"></i>Retry
      </button>
    </div>
  {:else if data}
    <div class="space-y-6">

      <!-- Planning Time -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-lg font-bold text-gray-900 mb-1 flex items-center">
          <i class="fas fa-brain mr-2 text-oxford-blue"></i>
          Agent Planning Time
        </h3>
        <p class="text-sm text-gray-500 mb-4">Time the LLM spends deciding which tools to call (tool_plan phase)</p>
        <div class="grid grid-cols-3 gap-4">
          <div class="bg-gray-50 rounded-lg p-3 text-center">
            <p class="text-xs text-gray-500 uppercase tracking-wide">Avg</p>
            <p class="text-xl font-bold text-oxford-blue">{fmt(data.planning_time?.avg_ms)} ms</p>
          </div>
          <div class="bg-gray-50 rounded-lg p-3 text-center">
            <p class="text-xs text-gray-500 uppercase tracking-wide">Max</p>
            <p class="text-xl font-bold text-gray-700">{fmt(data.planning_time?.max_ms, 0)} ms</p>
          </div>
          <div class="bg-gray-50 rounded-lg p-3 text-center">
            <p class="text-xs text-gray-500 uppercase tracking-wide">Samples</p>
            <p class="text-xl font-bold text-gray-700">{data.planning_time?.total_count ?? 0}</p>
          </div>
        </div>
      </div>

      <!-- Tool Call Breakdown -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-lg font-bold text-gray-900 mb-1 flex items-center">
          <i class="fas fa-tools mr-2 text-oxford-blue"></i>
          Tool Call Latency by Type
        </h3>
        <p class="text-sm text-gray-500 mb-4">Average time per tool call — WebSearch, Document reads, DocAware search</p>
        {#if data.tool_breakdown?.filter((r: any) => r.tool_type !== 'legacy (no timing)').length > 0}
          <canvas bind:this={toolCanvas} height="140"></canvas>
          <div class="mt-4 overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead>
                <tr class="bg-gray-50">
                  <th class="px-3 py-2 text-left text-xs font-medium text-gray-600 uppercase">Tool Type</th>
                  <th class="px-3 py-2 text-left text-xs font-medium text-gray-600 uppercase">Avg (ms)</th>
                  <th class="px-3 py-2 text-left text-xs font-medium text-gray-600 uppercase">Max (ms)</th>
                  <th class="px-3 py-2 text-left text-xs font-medium text-gray-600 uppercase">Calls</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                {#each data.tool_breakdown as row}
                  <tr>
                    <td class="px-3 py-2 font-medium text-gray-800">{row.tool_type}</td>
                    <td class="px-3 py-2 text-oxford-blue font-semibold">{fmt(row.avg_ms)}</td>
                    <td class="px-3 py-2 text-gray-600">{row.max_ms}</td>
                    <td class="px-3 py-2 text-gray-600">{row.count}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="text-sm text-gray-400 text-center py-6">No tool timing data yet. Tool call timing is captured from the next workflow run onwards.</p>
        {/if}
      </div>

      <!-- WebSearch Latency -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-lg font-bold text-gray-900 mb-1 flex items-center">
          <i class="fas fa-search mr-2 text-oxford-blue"></i>
          WebSearch Latency
        </h3>
        <p class="text-sm text-gray-500 mb-4">
          Duration per search request — green = cache hit, amber = cache miss
        </p>
        {#if data.websearch?.sample_count > 0}
          <div class="grid grid-cols-3 gap-4 mb-4">
            <div class="bg-gray-50 rounded-lg p-3 text-center">
              <p class="text-xs text-gray-500 uppercase tracking-wide">Avg</p>
              <p class="text-xl font-bold text-oxford-blue">{fmt(data.websearch.avg_ms)} ms</p>
            </div>
            <div class="bg-gray-50 rounded-lg p-3 text-center">
              <p class="text-xs text-gray-500 uppercase tracking-wide">Cache Hit Rate</p>
              <p class="text-xl font-bold text-green-600">
                {data.websearch.cache_hit_rate != null ? data.websearch.cache_hit_rate + '%' : 'N/A'}
              </p>
            </div>
            <div class="bg-gray-50 rounded-lg p-3 text-center">
              <p class="text-xs text-gray-500 uppercase tracking-wide">Samples</p>
              <p class="text-xl font-bold text-gray-700">{data.websearch.sample_count}</p>
            </div>
          </div>
          <canvas bind:this={wsCanvas} height="120"></canvas>
        {:else}
          <p class="text-sm text-gray-400 text-center py-6">No WebSearch data yet — enable web search in a workflow and run it.</p>
        {/if}
      </div>

      <!-- Execution Volume -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-lg font-bold text-gray-900 mb-1 flex items-center">
          <i class="fas fa-play-circle mr-2 text-oxford-blue"></i>
          Execution Volume
        </h3>
        <p class="text-sm text-gray-500 mb-4">Daily workflow runs — completed vs failed</p>
        {#if data.execution_volume?.daily?.length > 0}
          <div class="mb-4">
            <span class="text-sm text-gray-600 font-medium">Total executions: </span>
            <span class="text-sm font-bold text-oxford-blue">{data.execution_volume.total_executions}</span>
          </div>
          <canvas bind:this={execCanvas} height="120"></canvas>
        {:else}
          <p class="text-sm text-gray-400 text-center py-6">No executions yet for this project.</p>
        {/if}
      </div>

      <!-- Word Cloud -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h3 class="text-lg font-bold text-gray-900 mb-1 flex items-center">
          <i class="fas fa-comment-dots mr-2 text-oxford-blue"></i>
          User Query Word Cloud
        </h3>
        {#if data.query_wordcloud?.length > 0}
          <p class="text-sm text-gray-500 mb-4">
            Most frequent words across all user queries &mdash; {data.query_wordcloud.length} unique words
          </p>
          <div class="flex flex-wrap gap-2 items-center justify-center p-6 bg-gray-50 rounded-lg min-h-32">
            {#each data.query_wordcloud as item}
              <span
                class="cursor-default select-none transition-opacity hover:opacity-60 leading-tight"
                style="font-size: {wordSize(item.count, maxWordCount)}rem; color: {wordColor(item.count, maxWordCount)}; font-weight: {item.count > maxWordCount * 0.5 ? '700' : item.count > maxWordCount * 0.25 ? '600' : '400'};"
                title="{item.word}: {item.count} occurrence{item.count !== 1 ? 's' : ''}"
              >
                {item.word}
              </span>
            {/each}
          </div>
        {:else}
          <p class="text-sm text-gray-500 mb-4">Most frequent words from workflow start prompts and human input</p>
          <p class="text-sm text-gray-400 text-center py-6">No query data yet — run workflows to populate this word cloud.</p>
        {/if}
      </div>

      <!-- Refresh -->
      <div class="flex justify-end mt-6">
        <button
          class="px-6 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center"
          on:click={loadAnalytics}
        >
          <i class="fas fa-sync-alt mr-2"></i>
          Refresh
        </button>
      </div>

    </div>
  {/if}
</div>

<style>
  .project-analytics {
    min-height: 100%;
  }
</style>
