<!-- AI Workflow Builder Chatbot — generates workflows from natural language -->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';

  export let projectId: string;
  export let currentNodes: any[] = [];
  export let currentEdges: any[] = [];

  const dispatch = createEventDispatcher();

  let messages: Array<{role: string; content: string; toolCalls?: any[]; attachments?: string[]; plan?: string; diff?: any; graphJson?: any; planExpanded?: boolean}> = [];
  let inputText = '';
  let loading = false;
  let conversationHistory: any[] = [];
  let messagesContainer: HTMLElement;
  let lastGraphJson: any = null;

  // File attachments staged for the next outgoing message
  let attachedFiles: File[] = [];
  let fileInputEl: HTMLInputElement;
  const MAX_FILES = 5;
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB — matches DocumentProcessor
  // Minimized is `export let` with `bind:` support so the parent can shrink
  // the outer fixed-position container and the pill can float freely.
  export let minimized: boolean = false;

  // Let the parent know whether undo is available — shows/hides the undo button
  export let canUndoAI: boolean = false;

  // Persistence
  $: storageKey = `wf_ai_chat_${projectId}`;

  onMount(() => {
    loadSession();
  });

  function saveSession() {
    try {
      const data = { messages, conversationHistory, lastGraphJson };
      localStorage.setItem(storageKey, JSON.stringify(data));
    } catch (_) {}
  }

  function loadSession() {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const data = JSON.parse(raw);
        messages = data.messages || [];
        conversationHistory = data.conversationHistory || [];
        lastGraphJson = data.lastGraphJson || null;
        scrollToBottom();
      }
    } catch (_) {}
  }

  // Auto-save whenever messages change
  $: if (messages.length > 0) saveSession();

  async function sendMessage() {
    const text = inputText.trim();
    if ((!text && attachedFiles.length === 0) || loading) return;

    // Snapshot the files so we can clear the staging area immediately while
    // the request is in-flight.
    const filesForThisTurn = attachedFiles;
    attachedFiles = [];

    // Add user message — include attachment names so chips render in history
    const userMsg: any = { role: 'user', content: text };
    if (filesForThisTurn.length > 0) {
      userMsg.attachments = filesForThisTurn.map(f => f.name);
    }
    messages = [...messages, userMsg];
    inputText = '';
    loading = true;
    scrollToBottom();

    try {
      // Pass current canvas state so the LLM can modify existing workflows
      const currentGraph = (currentNodes.length > 0) ? JSON.parse(JSON.stringify({ nodes: currentNodes, edges: currentEdges })) : null;
      const result = await cleanUniversalApi.generateWorkflow(projectId, text, conversationHistory, currentGraph, filesForThisTurn);

      // Add assistant response
      const assistantMsg: any = { role: 'assistant', content: result.explanation || 'Workflow generated.' };
      if (result.tool_calls && result.tool_calls.length > 0) {
        assistantMsg.toolCalls = result.tool_calls;
      }
      messages = [...messages, assistantMsg];

      // Update conversation history for follow-up messages
      conversationHistory = [
        ...conversationHistory,
        { role: 'user', content: text },
        { role: 'assistant', content: result.explanation || '' },
      ];

      // Store the generated graph
      if (result.graph_json && result.graph_json.nodes && result.graph_json.nodes.length > 0) {
        lastGraphJson = result.graph_json;

        // Pillar 4: when modifying an existing workflow, the backend returns
        // a `diff`. Show a preview card and DEFER applyWorkflow until the
        // user clicks Apply. For fresh builds (diff === null), keep the
        // current auto-apply behavior — there's nothing to compare against.
        if (result.diff) {
          messages = [...messages, {
            role: 'preview',
            content: result.explanation || '',
            plan: result.plan || '',
            diff: result.diff,
            graphJson: result.graph_json,
          } as any];
        } else {
          dispatch('applyWorkflow', { graphJson: result.graph_json });
        }
      } else if (!result.graph_json || !result.graph_json?.nodes?.length) {
        messages = [...messages, {
          role: 'system',
          content: result.errors?.length
            ? `Could not generate workflow: ${result.errors.join(', ')}`
            : 'No workflow was generated. Try rephrasing your request.',
        }];
      }

      if (result.errors && result.errors.length > 0 && result.graph_json?.nodes?.length) {
        messages = [...messages, {
          role: 'system',
          content: `Validation: ${result.errors.join(', ')}`,
        }];
      }
    } catch (err: any) {
      messages = [...messages, {
        role: 'system',
        content: `Error: ${err.message || 'Failed to generate workflow'}`,
      }];
      // Preserve user message in conversation history even on error
      conversationHistory = [
        ...conversationHistory,
        { role: 'user', content: text },
      ];
    } finally {
      loading = false;
      scrollToBottom();
    }
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }, 50);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function reapplyWorkflow() {
    if (lastGraphJson) {
      dispatch('applyWorkflow', { graphJson: lastGraphJson });
    }
  }

  function clearChat() {
    messages = [];
    conversationHistory = [];
    lastGraphJson = null;
    attachedFiles = [];
    try { localStorage.removeItem(storageKey); } catch (_) {}
  }

  function formatBytes(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  }

  function onPickFiles(e: Event) {
    const input = e.target as HTMLInputElement;
    const picked = input.files ? Array.from(input.files) : [];
    addFiles(picked);
    // Reset so picking the SAME file again still fires `change`
    input.value = '';
  }

  function addFiles(picked: File[]) {
    if (picked.length === 0) return;
    const errors: string[] = [];
    const accepted: File[] = [];
    for (const f of picked) {
      if (f.size > MAX_FILE_SIZE) {
        errors.push(`${f.name}: exceeds 50 MB limit`);
        continue;
      }
      // Skip duplicates (by name + size)
      if (attachedFiles.some(a => a.name === f.name && a.size === f.size)) continue;
      accepted.push(f);
    }
    let next = [...attachedFiles, ...accepted];
    if (next.length > MAX_FILES) {
      errors.push(`Only ${MAX_FILES} files per message — extra files were dropped.`);
      next = next.slice(0, MAX_FILES);
    }
    attachedFiles = next;
    if (errors.length > 0) {
      messages = [...messages, { role: 'system', content: errors.join(' ') }];
      scrollToBottom();
    }
  }

  function removeAttached(idx: number) {
    attachedFiles = attachedFiles.filter((_, i) => i !== idx);
  }

  // Pillar 4 — preview-card actions
  function applyPreview(msgIdx: number) {
    const m = messages[msgIdx];
    if (!m || !m.graphJson) return;
    dispatch('applyWorkflow', { graphJson: m.graphJson });
    // Convert the preview into a confirmed system message so the chat history
    // shows what was applied without keeping the Apply/Discard buttons live.
    const summary = summarizeDiff(m.diff);
    messages = messages.map((mm, i) => i === msgIdx
      ? { role: 'system', content: `Applied: ${summary}` }
      : mm
    );
    scrollToBottom();
  }

  function discardPreview(msgIdx: number) {
    const m = messages[msgIdx];
    if (!m) return;
    messages = messages.map((mm, i) => i === msgIdx
      ? { role: 'system', content: 'Discarded — canvas unchanged.' }
      : mm
    );
    scrollToBottom();
  }

  function togglePlan(msgIdx: number) {
    messages = messages.map((mm, i) => i === msgIdx
      ? { ...mm, planExpanded: !mm.planExpanded }
      : mm
    );
  }

  function summarizeDiff(diff: any): string {
    if (!diff) return 'no changes';
    const parts: string[] = [];
    if (diff.added_nodes?.length) parts.push(`+${diff.added_nodes.length} agent(s)`);
    if (diff.removed_nodes?.length) parts.push(`-${diff.removed_nodes.length} agent(s)`);
    if (diff.updated_nodes?.length) parts.push(`~${diff.updated_nodes.length} agent(s)`);
    if (diff.added_edges?.length) parts.push(`+${diff.added_edges.length} edge(s)`);
    if (diff.removed_edges?.length) parts.push(`-${diff.removed_edges.length} edge(s)`);
    return parts.length ? parts.join(', ') : 'no structural changes';
  }
</script>

{#if minimized}
  <!-- Minimized: a small floating pill that restores the chat on click -->
  <button
    class="wf-chatbot-pill"
    title="Open AI Workflow Builder"
    on:click={() => { minimized = false; scrollToBottom(); }}
  >
    <i class="fas fa-wand-magic-sparkles text-violet-500"></i>
    <span>AI Builder</span>
  </button>
{:else}
<div class="wf-chatbot">
  <div class="wf-chatbot-header">
    <div class="flex items-center gap-2">
      <i class="fas fa-wand-magic-sparkles text-violet-500"></i>
      <span class="font-semibold text-sm text-gray-800">AI Workflow Builder</span>
    </div>
    <div class="flex items-center gap-1">
      {#if canUndoAI}
        <button class="icon-btn" title="Undo last AI change" on:click={() => dispatch('undo')}>
          <i class="fas fa-rotate-left text-xs"></i>
        </button>
      {/if}
      {#if lastGraphJson}
        <button class="icon-btn" title="Re-apply workflow" on:click={reapplyWorkflow}>
          <i class="fas fa-redo text-xs"></i>
        </button>
      {/if}
      <button class="icon-btn" title="Clear chat" on:click={clearChat}>
        <i class="fas fa-trash text-xs"></i>
      </button>
      <button class="icon-btn" title="Minimize" on:click={() => minimized = true}>
        <i class="fas fa-minus text-xs"></i>
      </button>
      <button class="icon-btn" title="Close" on:click={() => dispatch('close')}>
        <i class="fas fa-times text-xs"></i>
      </button>
    </div>
  </div>

  <div class="wf-chatbot-messages" bind:this={messagesContainer}>
    {#if messages.length === 0}
      <div class="empty-state">
        <i class="fas fa-wand-magic-sparkles text-2xl text-gray-300 mb-2"></i>
        <p class="text-sm text-gray-400">Describe the workflow you need and I'll build it for you.</p>
        <div class="mt-3 space-y-1">
          <button class="suggestion" on:click={() => { inputText = 'Create a simple document analysis workflow'; sendMessage(); }}>
            Document analysis workflow
          </button>
          <button class="suggestion" on:click={() => { inputText = 'Build a workflow with 2 parallel research agents and a synthesizer'; sendMessage(); }}>
            Parallel research + synthesis
          </button>
          <button class="suggestion" on:click={() => { inputText = 'Create a workflow with human review before final output'; sendMessage(); }}>
            Workflow with human review
          </button>
        </div>
      </div>
    {:else}
      {#each messages as msg, msgIdx}
        <div class="msg {msg.role}">
          {#if msg.role === 'user'}
            <div class="msg-bubble user-bubble">
              {#if msg.attachments && msg.attachments.length > 0}
                <div class="user-attachments">
                  {#each msg.attachments as fname}
                    <div class="user-attachment-chip">
                      <i class="fas fa-paperclip text-[10px]"></i>
                      <span>{fname}</span>
                    </div>
                  {/each}
                </div>
              {/if}
              {#if msg.content}
                <div class="whitespace-pre-wrap break-words">{msg.content}</div>
              {/if}
            </div>
          {:else if msg.role === 'assistant'}
            <div class="msg-bubble assistant-bubble">
              <div class="whitespace-pre-wrap">{msg.content}</div>
              {#if msg.toolCalls && msg.toolCalls.length > 0}
                <div class="tool-calls">
                  <div class="text-xs font-medium text-gray-500 mb-1">
                    <i class="fas fa-wrench mr-1"></i>{msg.toolCalls.length} tool call{msg.toolCalls.length > 1 ? 's' : ''}
                  </div>
                  {#each msg.toolCalls as tc}
                    <div class="tool-call-item">
                      <span class="tool-name">{tc.tool}</span>
                      <span class="tool-args">{JSON.stringify(tc.args).slice(0, 80)}{JSON.stringify(tc.args).length > 80 ? '...' : ''}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {:else if msg.role === 'system'}
            <div class="msg-bubble system-bubble">{msg.content}</div>
          {:else if msg.role === 'preview'}
            <div class="preview-card">
              <div class="preview-header">
                <i class="fas fa-eye text-amber-600"></i>
                <span class="font-semibold text-gray-800 text-xs">Preview changes</span>
                <span class="text-xs text-gray-500">— {summarizeDiff(msg.diff)}</span>
              </div>
              {#if msg.plan}
                <button class="plan-toggle" on:click={() => togglePlan(msgIdx)}>
                  <i class="fas fa-chevron-{msg.planExpanded ? 'down' : 'right'} text-[10px]"></i>
                  Plan
                </button>
                {#if msg.planExpanded}
                  <div class="plan-body whitespace-pre-wrap">{msg.plan}</div>
                {/if}
              {/if}
              {#if msg.content}
                <div class="preview-explanation whitespace-pre-wrap">{msg.content}</div>
              {/if}
              <div class="diff-list">
                {#each (msg.diff?.added_nodes || []) as n}
                  <div class="diff-line diff-add">+ agent {n}</div>
                {/each}
                {#each (msg.diff?.removed_nodes || []) as n}
                  <div class="diff-line diff-rm">– agent {n}</div>
                {/each}
                {#each (msg.diff?.updated_nodes || []) as u}
                  <div class="diff-line diff-up">~ agent {u.name} ({u.fields.join(', ')})</div>
                {/each}
                {#each (msg.diff?.added_edges || []) as e}
                  <div class="diff-line diff-add">+ edge {e.source} → {e.target}{e.category ? ` [${e.category}]` : ''}</div>
                {/each}
                {#each (msg.diff?.removed_edges || []) as e}
                  <div class="diff-line diff-rm">– edge {e.source} → {e.target}{e.category ? ` [${e.category}]` : ''}</div>
                {/each}
              </div>
              <div class="preview-actions">
                <button class="preview-discard" on:click={() => discardPreview(msgIdx)}>Discard</button>
                <button class="preview-apply" on:click={() => applyPreview(msgIdx)}>Apply</button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
      {#if loading}
        <div class="msg assistant">
          <div class="msg-bubble assistant-bubble">
            <div class="flex items-center gap-2 text-gray-400">
              <i class="fas fa-spinner fa-spin"></i>
              <span class="text-sm">Building workflow...</span>
            </div>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <div class="wf-chatbot-input-wrap">
    {#if attachedFiles.length > 0}
      <div class="staged-attachments">
        {#each attachedFiles as f, i (f.name + f.size)}
          <div class="staged-chip" title={`${f.name} (${formatBytes(f.size)})`}>
            <i class="fas fa-paperclip text-[10px]"></i>
            <span class="staged-name">{f.name}</span>
            <span class="staged-size">{formatBytes(f.size)}</span>
            <button class="staged-remove" title="Remove" on:click={() => removeAttached(i)}>
              <i class="fas fa-times text-[10px]"></i>
            </button>
          </div>
        {/each}
      </div>
    {/if}
    <div class="wf-chatbot-input">
      <input
        type="file"
        bind:this={fileInputEl}
        on:change={onPickFiles}
        multiple
        accept=".pdf,.txt,.md,.markdown,.docx,.doc,.csv,.json,.html,.htm,.xlsx,.xls"
        style="display: none;"
      />
      <button
        class="attach-btn"
        title={attachedFiles.length >= MAX_FILES ? `Max ${MAX_FILES} files` : 'Attach a document'}
        disabled={loading || attachedFiles.length >= MAX_FILES}
        on:click={() => fileInputEl?.click()}
      >
        <i class="fas fa-paperclip"></i>
      </button>
      <textarea
        bind:value={inputText}
        on:keydown={handleKeydown}
        placeholder={attachedFiles.length > 0 ? 'Add an instruction for these file(s)…' : 'Describe the workflow you need...'}
        rows="2"
        disabled={loading}
      ></textarea>
      <button on:click={sendMessage} disabled={loading || (!inputText.trim() && attachedFiles.length === 0)} class="send-btn">
        <i class="fas fa-paper-plane"></i>
      </button>
    </div>
  </div>
</div>
{/if}

<style>
  .wf-chatbot {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #fff;
    border-left: 1px solid #e2e8f0;
  }

  .wf-chatbot-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
  }

  .icon-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    color: #94a3b8;
    cursor: pointer;
    border-radius: 4px;
  }
  .icon-btn:hover { background: #f1f5f9; color: #475569; }

  .wf-chatbot-messages {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    text-align: center;
    padding: 20px;
  }

  .suggestion {
    display: block;
    width: 100%;
    padding: 6px 10px;
    font-size: 12px;
    color: #475569;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
  }
  .suggestion:hover { background: #e2e8f0; }

  .msg { display: flex; }
  .msg.user { justify-content: flex-end; }
  .msg.assistant, .msg.system { justify-content: flex-start; }

  .msg-bubble {
    max-width: 90%;
    padding: 8px 12px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.5;
    overflow-wrap: break-word;
    word-break: break-word;
  }

  .user-bubble {
    background: #002147 !important;
    color: #ffffff !important;
    border-bottom-right-radius: 4px;
  }
  /* Force white on every descendant inside the navy user bubble — the
     wrapper div for whitespace/word-break preservation otherwise reverts to
     a darker default from project-wide Tailwind preflight rules. */
  .user-bubble,
  .user-bubble * {
    color: #ffffff !important;
  }

  .assistant-bubble {
    background: #f1f5f9;
    color: #1e293b;
    border-bottom-left-radius: 4px;
  }

  .system-bubble {
    background: #fef3c7;
    color: #92400e;
    font-size: 12px;
    border-radius: 8px;
  }

  .tool-calls {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #e2e8f0;
  }

  .tool-call-item {
    display: flex;
    gap: 6px;
    align-items: baseline;
    font-size: 11px;
    padding: 2px 0;
  }

  .tool-name {
    font-weight: 600;
    color: #002147;
    white-space: nowrap;
  }

  .tool-args {
    color: #64748b;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .wf-chatbot-input {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 10px 12px;
    border-top: 1px solid #e2e8f0;
    background: #f8fafc;
  }

  .wf-chatbot-input textarea {
    flex: 1;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
    resize: none;
    outline: none;
    font-family: inherit;
  }
  .wf-chatbot-input textarea:focus { border-color: #002147; }

  .send-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #002147;
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    flex-shrink: 0;
  }
  .send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .send-btn:hover:not(:disabled) { background: #003366; }

  /* File attachment UI ---------------------------------------------------- */
  .wf-chatbot-input-wrap {
    border-top: 1px solid #e2e8f0;
    background: #f8fafc;
  }
  .wf-chatbot-input-wrap .wf-chatbot-input {
    border-top: none;  /* parent draws the border now */
  }

  .attach-btn {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    color: #64748b;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    cursor: pointer;
  }
  .attach-btn:hover:not(:disabled) {
    background: #e2e8f0;
    color: #002147;
  }
  .attach-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* Staged attachments shown above the textarea before send */
  .staged-attachments {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 12px 0 12px;
  }
  .staged-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    max-width: 100%;
    padding: 4px 8px;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 11px;
    color: #1e293b;
  }
  .staged-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 140px;
  }
  .staged-size { color: #64748b; }
  .staged-remove {
    border: none;
    background: transparent;
    color: #64748b;
    cursor: pointer;
    padding: 0 2px;
    line-height: 1;
  }
  .staged-remove:hover { color: #dc2626; }

  /* Pillar 4 — preview card (modify mode) */
  .msg.preview { justify-content: stretch; }
  .preview-card {
    width: 100%;
    border: 1px solid #f59e0b;
    background: #fffbeb;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 12px;
    color: #1e293b;
  }
  .preview-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }
  .plan-toggle {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: none;
    background: transparent;
    color: #475569;
    font-size: 11px;
    cursor: pointer;
    padding: 2px 0;
  }
  .plan-toggle:hover { color: #002147; }
  .plan-body {
    margin: 4px 0 8px 0;
    padding: 6px 8px;
    background: #ffffff;
    border-left: 2px solid #f59e0b;
    border-radius: 4px;
    font-size: 11px;
    color: #475569;
    max-height: 200px;
    overflow-y: auto;
  }
  .preview-explanation {
    margin-bottom: 8px;
    color: #475569;
  }
  .diff-list {
    margin: 6px 0;
    padding: 6px 8px;
    background: #ffffff;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    max-height: 200px;
    overflow-y: auto;
  }
  .diff-line { padding: 1px 0; }
  .diff-add { color: #16a34a; }
  .diff-rm  { color: #dc2626; }
  .diff-up  { color: #b45309; }
  .preview-actions {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    margin-top: 8px;
  }
  .preview-discard,
  .preview-apply {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border: none;
  }
  .preview-discard {
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #cbd5e1;
  }
  .preview-discard:hover { background: #e2e8f0; }
  .preview-apply {
    background: #002147;
    color: #ffffff;
  }
  .preview-apply:hover { background: #003366; }

  /* Attachment chips inside a sent user-message bubble */
  .user-attachments {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 6px;
  }
  .user-attachment-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: rgba(255, 255, 255, 0.18);
    border-radius: 4px;
    font-size: 11px;
    max-width: 100%;
  }
  .user-attachment-chip span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 180px;
  }

  /* Minimized pill — small floating anchor that restores the chat */
  .wf-chatbot-pill {
    position: fixed;
    right: 20px;
    bottom: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: 999px;
    border: 1px solid #e2e8f0;
    background: #ffffff;
    color: #1e293b;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 6px 16px rgba(15, 23, 42, 0.12);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }
  .wf-chatbot-pill:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 20px rgba(15, 23, 42, 0.18);
  }
</style>
