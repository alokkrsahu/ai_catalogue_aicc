<!-- AI Workflow Builder Chatbot — generates workflows from natural language -->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';

  export let projectId: string;
  export let currentNodes: any[] = [];
  export let currentEdges: any[] = [];

  const dispatch = createEventDispatcher();

  let messages: Array<{role: string; content: string; toolCalls?: any[]}> = [];
  let inputText = '';
  let loading = false;
  let conversationHistory: any[] = [];
  let messagesContainer: HTMLElement;
  let lastGraphJson: any = null;

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
    if (!text || loading) return;

    // Add user message
    messages = [...messages, { role: 'user', content: text }];
    inputText = '';
    loading = true;
    scrollToBottom();

    try {
      // Pass current canvas state so the LLM can modify existing workflows
      const currentGraph = (currentNodes.length > 0) ? JSON.parse(JSON.stringify({ nodes: currentNodes, edges: currentEdges })) : null;
      const result = await cleanUniversalApi.generateWorkflow(projectId, text, conversationHistory, currentGraph);

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
        // Auto-apply to canvas
        dispatch('applyWorkflow', { graphJson: result.graph_json });
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
    try { localStorage.removeItem(storageKey); } catch (_) {}
  }
</script>

<div class="wf-chatbot">
  <div class="wf-chatbot-header">
    <div class="flex items-center gap-2">
      <i class="fas fa-wand-magic-sparkles text-violet-500"></i>
      <span class="font-semibold text-sm text-gray-800">AI Workflow Builder</span>
    </div>
    <div class="flex items-center gap-1">
      {#if lastGraphJson}
        <button class="icon-btn" title="Re-apply workflow" on:click={reapplyWorkflow}>
          <i class="fas fa-redo text-xs"></i>
        </button>
      {/if}
      <button class="icon-btn" title="Clear chat" on:click={clearChat}>
        <i class="fas fa-trash text-xs"></i>
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
      {#each messages as msg}
        <div class="msg {msg.role}">
          {#if msg.role === 'user'}
            <div class="msg-bubble user-bubble">{msg.content}</div>
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

  <div class="wf-chatbot-input">
    <textarea
      bind:value={inputText}
      on:keydown={handleKeydown}
      placeholder="Describe the workflow you need..."
      rows="2"
      disabled={loading}
    ></textarea>
    <button on:click={sendMessage} disabled={loading || !inputText.trim()} class="send-btn">
      <i class="fas fa-paper-plane"></i>
    </button>
  </div>
</div>

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
  }

  .user-bubble {
    background: #002147 !important;
    color: #ffffff !important;
    border-bottom-right-radius: 4px;
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
</style>
