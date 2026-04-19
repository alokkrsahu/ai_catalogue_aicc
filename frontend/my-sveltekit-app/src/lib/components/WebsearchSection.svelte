<!--
  WebsearchSection.svelte
  =======================

  Shared websearch configuration UI extracted from NodePropertiesPanel.

  Renders the enable toggle plus mode/domains/URLs/top_k/max_results/cache-TTL
  controls, the per-URL summaries panel, and the clear-cache button.

  Used twice in NodePropertiesPanel — once for UserProxyAgent (no doc-tool
  gating) and once for AssistantAgent/DelegateAgent (gated on
  nodeConfig.doc_tool_calling). The `gatedByDocToolCalling` prop toggles
  between these behaviours so the two call sites stay in lock-step.
-->
<script lang="ts">
  import api from '$lib/services/api';
  import { onDestroy } from 'svelte';
  import type { AgentNodeData } from '$lib/types';

  /** Two-way bound node config. */
  export let nodeConfig: AgentNodeData;
  /** Project UUID used for scoped cache / index / summary endpoints. */
  export let projectId: string = '';
  /**
   * When true (AssistantAgent/DelegateAgent), the toggle is disabled unless
   * nodeConfig.doc_tool_calling === true and the config block only renders
   * when both flags are on. When false (UserProxyAgent), there is no gating.
   */
  export let gatedByDocToolCalling: boolean = false;
  /**
   * Parent callback. Called after every config mutation so the parent can
   * persist the change to the workflow graph.
   */
  export let onChange: () => void = () => {};

  // Must stay in lock-step with backend WEBSEARCH_CONFIG.MAX_URLS_PER_AGENT.
  const MAX_URLS_PER_AGENT = 50;

  // ---- URL indexing state ------------------------------------------------
  let syncingWebIndex = false;
  let webIndexStatus: string | null = null;
  let webIndexDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  let urlListWarning: string | null = null;

  // ---- Per-URL summaries state ------------------------------------------
  type UrlSummary = {
    url: string;
    short_summary: string;
    long_summary: string;
    llm_provider: string;
    llm_model: string;
    updated_at: string | null;
  };
  let urlSummariesByUrl: Record<string, UrlSummary> = {};
  let urlSummariesLoaded = false;
  let generatingUrlSummaries = false;
  let urlSummaryStatus: string | null = null;
  let regeneratingUrl: string | null = null;
  let expandedSummaryUrl: string | null = null;
  let summaryPollTimer: ReturnType<typeof setTimeout> | null = null;
  // Mirror of backend's summary-generation Redis flag — true while a
  // detached thread is still producing summaries for this project.
  let generationInProgress = false;
  // If the backend returned a non-retryable error (missing API key,
  // provider config), stop auto-triggering from the textarea debounce
  // so we don't spam the user on every keystroke. The manual button
  // still works — it clears this flag on success.
  let autoSummarySuppressed = false;

  // ---- Clear-cache state ------------------------------------------------
  let clearingWebCache = false;
  let webCacheCleared = false;

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  function parseUrlTextarea(value: string): { urls: string[]; warning: string | null } {
    const raw = (value || '').split('\n').map(u => u.trim()).filter(u => u.length > 0);
    const seen = new Set<string>();
    const deduped: string[] = [];
    let duplicates = 0;
    for (const u of raw) {
      if (seen.has(u)) { duplicates += 1; continue; }
      seen.add(u);
      deduped.push(u);
    }
    const overCap = Math.max(0, deduped.length - MAX_URLS_PER_AGENT);
    const capped = overCap ? deduped.slice(0, MAX_URLS_PER_AGENT) : deduped;
    const parts: string[] = [];
    if (duplicates) parts.push(`${duplicates} duplicate${duplicates === 1 ? '' : 's'} removed`);
    if (overCap) parts.push(`${overCap} extra URL${overCap === 1 ? '' : 's'} ignored (max ${MAX_URLS_PER_AGENT})`);
    return { urls: capped, warning: parts.length ? parts.join('; ') : null };
  }

  function debouncedSyncWebIndex(urls: string[]) {
    if (webIndexDebounceTimer) clearTimeout(webIndexDebounceTimer);
    webIndexDebounceTimer = setTimeout(() => {
      // Run the two pieces in parallel — they target different systems
      // (Milvus for the RAG index, LLM for the per-URL summaries) and
      // don't depend on each other.
      doSyncWebIndex(urls);
      maybeAutoGenerateSummaries();
    }, 2000);
  }

  async function doSyncWebIndex(urls: string[]) {
    if (!projectId || syncingWebIndex) return;
    const validUrls = urls.filter(u => u.startsWith('http://') || u.startsWith('https://'));
    if (validUrls.length === 0) return;
    syncingWebIndex = true;
    webIndexStatus = null;
    try {
      const cacheTtl = nodeConfig.web_search_cache_ttl ?? 2592000;
      const res = await api.post(`/agent-orchestration/projects/${projectId}/sync-websearch-index/`, {
        urls: validUrls,
        cache_ttl: cacheTtl,
      });
      const d = res.data;
      if (d.indexed > 0 || d.removed > 0) {
        webIndexStatus = `Indexed ${d.indexed} new, removed ${d.removed} stale` + (d.failed > 0 ? `, ${d.failed} failed` : '');
      } else {
        webIndexStatus = `All ${d.already_indexed} URLs up to date`;
      }
      setTimeout(() => { webIndexStatus = null; }, 5000);
    } catch (err) {
      console.warn('Sync web index failed:', err);
      webIndexStatus = null;
    } finally {
      syncingWebIndex = false;
    }
  }

  async function doClearWebCache() {
    if (!projectId || clearingWebCache) return;
    clearingWebCache = true;
    webCacheCleared = false;
    try {
      await api.post(`/agent-orchestration/projects/${projectId}/clear-websearch-cache/`, {});
      webCacheCleared = true;
      setTimeout(() => { webCacheCleared = false; }, 3000);
    } catch (err) {
      console.warn('Clear web cache failed:', err);
    } finally {
      clearingWebCache = false;
    }
  }

  async function loadUrlSummaries(): Promise<boolean> {
    // Returns the latest generation_in_progress flag so the poller can
    // decide whether to schedule another tick.
    if (!projectId) return false;
    try {
      const res = await api.get(`/agent-orchestration/projects/${projectId}/url-summaries/`);
      const map: Record<string, UrlSummary> = {};
      for (const s of (res.data?.summaries ?? [])) map[s.url] = s;
      urlSummariesByUrl = map;
      urlSummariesLoaded = true;
      generationInProgress = Boolean(res.data?.generation_in_progress);
      return generationInProgress;
    } catch (err) {
      console.warn('Load URL summaries failed:', err);
      urlSummariesLoaded = true;
      return false;
    }
  }

  /**
   * Poll `/url-summaries/` every 3s while the backend's generation flag
   * is alive. Progress text is derived from how many of the configured
   * URLs now have a summary — the per-URL checkmarks in the list above
   * re-render automatically as `urlSummariesByUrl` updates.
   * Safety stop: 15 minutes (matches the backend Redis flag TTL).
   */
  async function pollSummaryProgress() {
    if (summaryPollTimer) clearTimeout(summaryPollTimer);
    const deadline = Date.now() + 15 * 60 * 1000;

    const tick = async () => {
      const stillRunning = await loadUrlSummaries();
      const configured = (nodeConfig.web_search_urls || []).filter(
        (u: string) => u.startsWith('http://') || u.startsWith('https://'),
      );
      const done = configured.filter((u: string) => urlSummariesByUrl[u]).length;
      if (stillRunning && Date.now() < deadline) {
        urlSummaryStatus = `Generating in background… ${done}/${configured.length} done`;
        summaryPollTimer = setTimeout(tick, 3000);
      } else {
        generatingUrlSummaries = false;
        regeneratingUrl = null;
        summaryPollTimer = null;
        if (!stillRunning) {
          urlSummaryStatus = done >= configured.length && configured.length > 0
            ? `All ${done} summaries ready`
            : `${done}/${configured.length} summaries ready`;
        } else {
          urlSummaryStatus = 'Still generating in background — close this panel and return later';
        }
        setTimeout(() => { urlSummaryStatus = null; }, 6000);
      }
    };

    // Fire first tick immediately so UI reflects whatever completed
    // before this function was called.
    tick();
  }

  /**
   * Auto-trigger summary generation for URLs that don't have summaries yet.
   * Called after the debounced URL-textarea change and on initial URL-mode
   * entry so the user doesn't have to remember to click "Generate missing".
   *
   * Safe to call on every input:
   *  - No-op if URL mode isn't active, no URLs are configured, or a
   *    generation is already running.
   *  - Checks the client-side summaries map first and only POSTs when at
   *    least one URL is genuinely missing a summary.
   *  - Re-uses generateMissingUrlSummaries so 409 handling, polling, and
   *    status text all stay consistent with the manual button path.
   */
  async function maybeAutoGenerateSummaries() {
    if (!projectId) return;
    if (!nodeConfig.web_search_enabled) return;
    if (nodeConfig.web_search_mode !== 'urls') return;
    if (generatingUrlSummaries) return;
    if (autoSummarySuppressed) return;  // non-retryable error — wait for manual button
    const urls = (nodeConfig.web_search_urls || []).filter(
      (u: string) => u.startsWith('http://') || u.startsWith('https://'),
    );
    if (urls.length === 0) return;
    // Need a fresh snapshot — a summary may have landed since last poll.
    if (!urlSummariesLoaded) await loadUrlSummaries();
    const missing = urls.filter((u: string) => !urlSummariesByUrl[u]);
    if (missing.length === 0) return;
    await generateMissingUrlSummaries();
  }

  async function generateMissingUrlSummaries() {
    if (!projectId || generatingUrlSummaries) return;
    const urls = (nodeConfig.web_search_urls || []).filter(
      (u: string) => u.startsWith('http://') || u.startsWith('https://'),
    );
    if (urls.length === 0) {
      urlSummaryStatus = 'No valid URLs configured.';
      setTimeout(() => { urlSummaryStatus = null; }, 3000);
      return;
    }
    generatingUrlSummaries = true;
    urlSummaryStatus = 'Starting…';
    try {
      const res = await api.post(
        `/agent-orchestration/projects/${projectId}/summarize-urls/`,
        {
          urls,
          llm_provider: nodeConfig.llm_provider || 'openai',
          llm_model: nodeConfig.llm_model || '',
          cache_ttl: nodeConfig.web_search_cache_ttl ?? 2592000,
          force: false,
        },
      );
      const d = res.data || {};
      // 200 with status='noop' means nothing to do (all URLs had summaries
      // and force=false). 202 with status='started' means the background
      // thread was kicked off — start polling.
      if (d.status === 'noop') {
        urlSummaryStatus = 'All URLs already have summaries';
        generatingUrlSummaries = false;
        autoSummarySuppressed = false;  // clear any previous suppression
        await loadUrlSummaries();
        setTimeout(() => { urlSummaryStatus = null; }, 4000);
        return;
      }
      // Successful 202 → clear suppression so auto-gen can try again later.
      autoSummarySuppressed = false;
      urlSummaryStatus = `Queued ${d.urls_queued ?? urls.length} URL(s) — generating in background…`;
      await pollSummaryProgress();
    } catch (err: any) {
      const statusCode = err?.response?.status;
      const msg = err?.response?.data?.error || err?.message || 'Request failed';
      if (statusCode === 409) {
        // Already running — join the existing run via polling.
        urlSummaryStatus = 'Already generating — joining in-progress run…';
        await pollSummaryProgress();
      } else {
        // 400 usually means "no API key configured" — non-retryable from
        // the client's side. Suppress auto-gen to stop nagging on every
        // keystroke; the manual button still works for a deliberate retry.
        if (statusCode === 400) autoSummarySuppressed = true;
        urlSummaryStatus = `Error: ${msg}`;
        generatingUrlSummaries = false;
        setTimeout(() => { urlSummaryStatus = null; }, 6000);
      }
    }
  }

  async function regenerateUrlSummary(url: string) {
    if (!projectId || regeneratingUrl) return;
    regeneratingUrl = url;
    try {
      const res = await api.post(
        `/agent-orchestration/projects/${projectId}/summarize-urls/`,
        {
          urls: [url],
          llm_provider: nodeConfig.llm_provider || 'openai',
          llm_model: nodeConfig.llm_model || '',
          cache_ttl: nodeConfig.web_search_cache_ttl ?? 2592000,
          force: true,
        },
      );
      const d = res.data || {};
      if (d.status === 'started' || d.status === 'noop') {
        // Single URL regeneration is usually fast, but still detached on
        // the backend — poll briefly for the fresh summary.
        generatingUrlSummaries = true;
        await pollSummaryProgress();
      } else {
        await loadUrlSummaries();
      }
    } catch (err: any) {
      const statusCode = err?.response?.status;
      if (statusCode === 409) {
        generatingUrlSummaries = true;
        await pollSummaryProgress();
      } else {
        console.warn('Regenerate URL summary failed:', err);
      }
    } finally {
      // regeneratingUrl is cleared by the poller once generation finishes;
      // if the POST failed outright, clear it now.
      if (!generatingUrlSummaries) regeneratingUrl = null;
    }
  }

  function handleEnableToggle(checked: boolean) {
    nodeConfig.web_search_enabled = checked;
    if (checked) {
      if (!nodeConfig.web_search_mode) nodeConfig.web_search_mode = 'general';
      if (!nodeConfig.web_search_cache_ttl) nodeConfig.web_search_cache_ttl = 2592000;
      if (!nodeConfig.web_search_max_results) nodeConfig.web_search_max_results = 5;
      if (!nodeConfig.web_search_urls) nodeConfig.web_search_urls = [];
      if (!nodeConfig.web_search_domains) nodeConfig.web_search_domains = [];
    } else {
      // Disable WebSearch but preserve mode so re-enable restores it.
      nodeConfig.web_search_urls = [];
      nodeConfig.web_search_domains = [];
    }
    nodeConfig = { ...nodeConfig };
    onChange();
  }

  // Lazy-load summaries the first time the user switches into URL mode.
  // If a background generation is already running server-side (another
  // tab started it, or the page reloaded during a run), pick up the
  // polling automatically so the user sees progress.
  $: if (
    projectId &&
    nodeConfig?.web_search_enabled &&
    nodeConfig?.web_search_mode === 'urls' &&
    !urlSummariesLoaded
  ) {
    loadUrlSummaries().then((running) => {
      if (running && !generatingUrlSummaries) {
        generatingUrlSummaries = true;
        urlSummaryStatus = 'Generation already in progress — tracking…';
        pollSummaryProgress();
      } else {
        // Fresh entry: if there are URLs configured without summaries
        // (e.g. a saved agent opened for the first time), auto-kick the
        // same background path so the user doesn't have to click.
        maybeAutoGenerateSummaries();
      }
    });
  }

  // Stop the polling timer when this component is torn down so it
  // doesn't keep firing after the panel closes.
  onDestroy(() => {
    if (summaryPollTimer) {
      clearTimeout(summaryPollTimer);
      summaryPollTimer = null;
    }
    if (webIndexDebounceTimer) {
      clearTimeout(webIndexDebounceTimer);
      webIndexDebounceTimer = null;
    }
  });

  $: toggleDisabled = gatedByDocToolCalling && !nodeConfig.doc_tool_calling;
  $: showConfig = nodeConfig.web_search_enabled && (!gatedByDocToolCalling || nodeConfig.doc_tool_calling);
</script>

<!-- WEBSEARCH TOGGLE -->
<div class:opacity-50={toggleDisabled}>
  <div class="flex items-center justify-between">
    <label class="text-sm font-medium text-gray-700">WebSearch</label>
    <label class="relative inline-flex items-center {toggleDisabled ? 'cursor-not-allowed' : 'cursor-pointer'}">
      <input
        type="checkbox"
        checked={nodeConfig.web_search_enabled}
        disabled={toggleDisabled}
        on:change={(e) => handleEnableToggle((e.currentTarget as HTMLInputElement).checked)}
        class="sr-only peer"
      />
      <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600 peer-disabled:opacity-60"></div>
    </label>
  </div>
  <p class="text-xs text-gray-500 mt-1">Enable web search capabilities to retrieve real-time information from the internet</p>
  {#if gatedByDocToolCalling && !nodeConfig.doc_tool_calling}
    <p class="text-xs text-gray-400 mt-1">Enable Document Tool Calling to use this.</p>
  {/if}
</div>

<!-- WEBSEARCH CONFIGURATION -->
{#if showConfig}
  <div class="border border-green-200 rounded-lg p-4 bg-green-50">
    <div class="flex items-center mb-3">
      <i class="fas fa-globe text-green-600 mr-2"></i>
      <h4 class="font-medium text-green-900">Web Search Configuration</h4>
    </div>

    <!-- Search Mode Selection -->
    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">Search Mode</label>
      <select
        bind:value={nodeConfig.web_search_mode}
        on:change={onChange}
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20 bg-white"
      >
        <option value="general">General Web Search</option>
        <option value="domains">Search Specific Domains</option>
        <option value="urls">Fetch Specific URLs</option>
      </select>
      <p class="text-xs text-gray-500 mt-1">
        {#if nodeConfig.web_search_mode === 'general'}
          Search the entire web using DuckDuckGo
        {:else if nodeConfig.web_search_mode === 'domains'}
          Restrict search to specific domains/websites
        {:else if nodeConfig.web_search_mode === 'urls'}
          Fetch content from specific URLs directly
        {:else}
          Select a search mode to configure web search
        {/if}
      </p>
    </div>

    <!-- Domain List (for 'domains' mode) -->
    {#if nodeConfig.web_search_mode === 'domains'}
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Search Domains
          <span class="text-xs text-gray-500 ml-1">(one per line)</span>
        </label>
        <textarea
          value={(nodeConfig.web_search_domains || []).join('\n')}
          on:input={(e) => {
            const domains = (e.currentTarget as HTMLTextAreaElement).value.split('\n').map(d => d.trim()).filter(d => d);
            nodeConfig.web_search_domains = domains;
            onChange();
          }}
          rows="3"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
          placeholder="wikipedia.org&#10;docs.python.org&#10;developer.mozilla.org"
        ></textarea>
        <p class="text-xs text-gray-500 mt-1">Enter domain names (without https://) to restrict search results</p>
      </div>
    {/if}

    <!-- URL List (for 'urls' mode) -->
    {#if nodeConfig.web_search_mode === 'urls'}
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          URLs to Fetch
          <span class="text-xs text-gray-500 ml-1">(one per line)</span>
        </label>
        <textarea
          value={(nodeConfig.web_search_urls || []).join('\n')}
          on:input={(e) => {
            const { urls, warning } = parseUrlTextarea((e.currentTarget as HTMLTextAreaElement).value);
            nodeConfig.web_search_urls = urls;
            urlListWarning = warning;
            onChange();
            debouncedSyncWebIndex(urls);
          }}
          rows="4"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
          placeholder="https://example.com/page1&#10;https://docs.example.com/api&#10;https://wiki.example.org/article"
        ></textarea>
        <div class="flex items-center gap-2 mt-1 flex-wrap">
          <p class="text-xs text-gray-500">Enter full URLs (with https://) to fetch content from specific pages</p>
          {#if syncingWebIndex}
            <span class="text-xs text-blue-600"><i class="fas fa-spinner fa-spin mr-1"></i>Indexing...</span>
          {/if}
          {#if webIndexStatus}
            <span class="text-xs text-green-600"><i class="fas fa-check mr-1"></i>{webIndexStatus}</span>
          {/if}
          {#if urlListWarning}
            <span class="text-xs text-amber-600"><i class="fas fa-exclamation-triangle mr-1"></i>{urlListWarning}</span>
          {/if}
        </div>

        <!-- Relevant Excerpts (RAG top-K) -->
        <div class="mt-3">
          <label class="block text-sm font-medium text-gray-700 mb-2">Relevant Excerpts</label>
          <input
            type="number"
            value={nodeConfig.web_search_top_k ?? 5}
            on:change={(e) => {
              const target = e.currentTarget as HTMLInputElement;
              nodeConfig.web_search_top_k = Math.max(1, Math.min(20, parseInt(target.value) || 5));
              target.value = String(nodeConfig.web_search_top_k);
              onChange();
            }}
            min="1"
            max="20"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
          />
          <p class="text-xs text-gray-500 mt-1">Number of most relevant text excerpts to send to the LLM (1-20). Lower = faster and cheaper.</p>
        </div>

        <!-- Per-URL LLM summaries -->
        <div class="mt-4 border-t pt-3">
          <div class="flex items-center justify-between mb-2">
            <label class="block text-sm font-medium text-gray-700">
              Per-URL Summaries
              <span class="text-xs text-gray-500 ml-1">(LLM-generated; enables selective URL tools)</span>
              <span class="block text-[11px] text-gray-500 font-normal mt-0.5">
                Auto-generates in the background whenever you add URLs — safe to close this panel. The button is only needed for a manual retry (e.g. after fixing an API-key issue).
              </span>
            </label>
            <button
              type="button"
              class="px-2 py-1 text-xs rounded-md border border-green-600 text-green-700 hover:bg-green-50 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={generatingUrlSummaries || !(nodeConfig.web_search_urls || []).length}
              on:click={() => { autoSummarySuppressed = false; generateMissingUrlSummaries(); }}
            >
              {#if generatingUrlSummaries}
                <i class="fas fa-spinner fa-spin mr-1"></i>Generating…
              {:else}
                <i class="fas fa-magic mr-1"></i>Generate missing
              {/if}
            </button>
          </div>
          {#if urlSummaryStatus}
            <p class="text-xs text-gray-600 mb-2">{urlSummaryStatus}</p>
          {/if}
          {#if (nodeConfig.web_search_urls || []).length === 0}
            <p class="text-xs text-gray-500">Add URLs above to generate summaries.</p>
          {:else}
            <ul class="space-y-1 text-xs">
              {#each (nodeConfig.web_search_urls || []) as u}
                {@const s = urlSummariesByUrl[u]}
                <li class="border border-gray-200 rounded-md px-2 py-1.5 bg-white">
                  <div class="flex items-start gap-2">
                    <button
                      type="button"
                      class="flex-1 text-left truncate font-mono text-[11px] text-gray-700 hover:text-green-700"
                      title={u}
                      on:click={() => expandedSummaryUrl = expandedSummaryUrl === u ? null : u}
                    >
                      {#if s}<i class="fas fa-check-circle text-green-600 mr-1"></i>{:else}<i class="far fa-circle text-gray-400 mr-1"></i>{/if}
                      {u}
                    </button>
                    {#if s}
                      <button
                        type="button"
                        class="text-[11px] text-blue-600 hover:text-blue-800 disabled:opacity-50"
                        disabled={regeneratingUrl === u}
                        on:click={() => regenerateUrlSummary(u)}
                        title="Regenerate summary"
                      >
                        {#if regeneratingUrl === u}
                          <i class="fas fa-spinner fa-spin"></i>
                        {:else}
                          <i class="fas fa-sync-alt"></i>
                        {/if}
                      </button>
                    {/if}
                  </div>
                  {#if expandedSummaryUrl === u && s}
                    <div class="mt-1.5 pl-4 text-[11px] text-gray-600 whitespace-pre-wrap">
                      <div class="text-gray-400 mb-1">
                        Updated {s.updated_at ? new Date(s.updated_at).toLocaleString() : '—'}
                        {#if s.llm_provider}· {s.llm_provider}{#if s.llm_model} / {s.llm_model}{/if}{/if}
                      </div>
                      {s.short_summary || '(empty summary)'}
                    </div>
                  {:else if expandedSummaryUrl === u && !s}
                    <div class="mt-1.5 pl-4 text-[11px] text-gray-400">No summary generated yet.</div>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Max Results (for 'general' and 'domains' modes) -->
    {#if nodeConfig.web_search_mode === 'general' || nodeConfig.web_search_mode === 'domains'}
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">Max Results</label>
        <input
          type="number"
          bind:value={nodeConfig.web_search_max_results}
          on:input={onChange}
          min="1"
          max="20"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
        />
        <p class="text-xs text-gray-500 mt-1">Maximum number of search results to retrieve (1-20)</p>
      </div>
    {/if}

    <!-- Cache TTL (input in days, stored as seconds) -->
    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">Cache Duration (days)</label>
      <input
        type="number"
        value={Math.round((nodeConfig.web_search_cache_ttl ?? 2592000) / 86400)}
        on:change={(e) => {
          const target = e.currentTarget as HTMLInputElement;
          const days = Math.max(0, Math.min(365, parseInt(target.value) || 0));
          nodeConfig.web_search_cache_ttl = days * 86400;
          target.value = String(days);
          onChange();
        }}
        min="0"
        max="365"
        step="1"
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
      />
      <p class="text-xs text-gray-500 mt-1">How long to cache fetched page content. 0 = no caching, 30 = 30 days (recommended)</p>
    </div>

    <!-- Current Configuration Summary -->
    <div class="mt-3 p-2 bg-green-100 border border-green-200 rounded text-xs text-green-700">
      <i class="fas fa-info-circle mr-1"></i>
      <strong>Mode:</strong> {nodeConfig.web_search_mode || 'Not set'} |
      {#if nodeConfig.web_search_mode === 'urls'}
        <strong>URLs:</strong> {(nodeConfig.web_search_urls || []).length} configured
      {:else if nodeConfig.web_search_mode === 'domains'}
        <strong>Domains:</strong> {(nodeConfig.web_search_domains || []).length} configured
      {:else}
        <strong>Max Results:</strong> {nodeConfig.web_search_max_results || 5}
      {/if}
      | <strong>Cache:</strong> {Math.round((nodeConfig.web_search_cache_ttl || 2592000) / 86400)} day(s)
    </div>

    <!-- Clear Web Cache -->
    <div class="mt-2 flex items-center gap-2">
      <button
        type="button"
        on:click={doClearWebCache}
        disabled={clearingWebCache}
        class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded border border-red-300 text-red-600 bg-white hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        <i class="fas {clearingWebCache ? 'fa-spinner fa-spin' : 'fa-trash-alt'}"></i>
        {clearingWebCache ? 'Clearing…' : 'Clear Web Cache'}
      </button>
      {#if webCacheCleared}
        <span class="text-xs text-green-600"><i class="fas fa-check mr-1"></i>Cache cleared — pages will be re-fetched on next run</span>
      {/if}
    </div>
  </div>
{/if}
