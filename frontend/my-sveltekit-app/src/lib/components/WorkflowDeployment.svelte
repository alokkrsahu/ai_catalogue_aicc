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
  let initialGreeting = 'Hi! I am your AI assistant.';
  
  // Function to generate embed code (called on demand to avoid PostCSS issues)
  // Using String.fromCharCode to avoid PostCSS parsing CSS in the string
  function generateEmbedCode(): string {
    if (!endpointUrl || !initialGreeting) {
      console.warn('⚠️ DEPLOYMENT: Cannot generate embed code - missing endpointUrl or initialGreeting');
      return '';
    }
    const escapedEndpoint = endpointUrl.replace(/'/g, "\\'").replace(/\\/g, '\\\\');
    const escapedGreeting = JSON.stringify(initialGreeting);
    
    // Build HTML using array join to avoid PostCSS parsing issues
    const htmlParts: string[] = [];
    htmlParts.push('<!DOCTYPE html>');
    htmlParts.push('<html lang="en">');
    htmlParts.push('<head>');
    htmlParts.push('  <meta charset="UTF-8" />');
    htmlParts.push('  <title>AICC Workflow Chatbot</title>');
    // Split style tag to avoid PostCSS parsing
    htmlParts.push('  <' + 'style>');
    htmlParts.push('    body { font-family: system-ui, -apple-system, sans-serif; background:#f5f5f7; margin:0; padding:0; display:flex; justify-content:center; align-items:center; height:100vh; }');
    htmlParts.push('    .chat-container { width: 420px; max-width: 100%; height: 620px; background:#ffffff; border-radius:16px; box-shadow:0 18px 45px rgba(15,23,42,0.18); display:flex; flex-direction:column; overflow:hidden; }');
    htmlParts.push('    .chat-header { padding:14px 18px; background:#0b3b66; color:#fff; display:flex; align-items:center; justify-content:space-between; }');
    htmlParts.push('    .chat-header-title { font-weight:600; font-size:15px; }');
    htmlParts.push('    .chat-header-sub { font-size:11px; opacity:0.8; }');
    htmlParts.push('    .chat-messages { flex:1; padding:14px 16px; overflow-y:auto; background:#f9fafb; font-size:14px; }');
    htmlParts.push('    .msg { margin-bottom:10px; display:flex; }');
    htmlParts.push('    .msg.user { justify-content:flex-end; }');
    htmlParts.push('    .msg.assistant { justify-content:flex-start; }');
    htmlParts.push('    .bubble { max-width:80%; padding:8px 11px; border-radius:12px; line-height:1.4; }');
    htmlParts.push('    .msg.user .bubble { background:#0b3b66; color:#fff; border-bottom-right-radius:4px; }');
    htmlParts.push('    .msg.assistant .bubble { background:#ffffff; border:1px solid #e5e7eb; color:#111827; border-bottom-left-radius:4px; }');
    htmlParts.push('    .chat-input { padding:10px 12px; border-top:1px solid #e5e7eb; background:#ffffff; display:flex; gap:8px; }');
    htmlParts.push('    .chat-input textarea { flex:1; resize:none; border:1px solid #d1d5db; border-radius:10px; padding:8px 10px; font-size:13px; max-height:80px; }');
    htmlParts.push('    .chat-input button { background:#0b3b66; color:#fff; border:none; border-radius:10px; padding:0 14px; font-size:13px; cursor:pointer; display:flex; align-items:center; gap:6px; }');
    htmlParts.push('    .chat-input button:disabled { opacity:0.6; cursor:not-allowed; }');
    htmlParts.push('    .status { font-size:11px; color:#6b7280; padding:4px 12px 8px; }');
    htmlParts.push('    .human-input-modal { display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:1000; justify-content:center; align-items:center; }');
    htmlParts.push('    .human-input-modal.active { display:flex; }');
    htmlParts.push('    .human-input-box { background:#fff; border-radius:12px; padding:24px; max-width:500px; width:90%; box-shadow:0 20px 60px rgba(0,0,0,0.3); }');
    htmlParts.push('    .human-input-title { font-size:18px; font-weight:600; color:#0b3b66; margin-bottom:12px; }');
    htmlParts.push('    .human-input-message { background:#f9fafb; border:1px solid #e5e7eb; border-radius:8px; padding:12px; margin-bottom:16px; font-size:14px; color:#374151; line-height:1.5; }');
    htmlParts.push('    .human-input-textarea { width:100%; min-height:80px; border:1px solid #d1d5db; border-radius:8px; padding:10px; font-size:14px; resize:vertical; font-family:inherit; }');
    htmlParts.push('    .human-input-buttons { display:flex; gap:8px; justify-content:flex-end; margin-top:16px; }');
    htmlParts.push('    .human-input-buttons button { padding:8px 16px; border-radius:8px; font-size:14px; cursor:pointer; border:none; }');
    htmlParts.push('    .human-input-buttons .submit-btn { background:#0b3b66; color:#fff; }');
    htmlParts.push('    .human-input-buttons .submit-btn:disabled { opacity:0.6; cursor:not-allowed; }');
    htmlParts.push('    .human-input-buttons .cancel-btn { background:#f3f4f6; color:#374151; }');
    htmlParts.push('  </' + 'style>');
    htmlParts.push('</head>');
    htmlParts.push('<body>');
    htmlParts.push('<div class="chat-container">');
    htmlParts.push('  <div class="chat-header">');
    htmlParts.push('    <div>');
    htmlParts.push('      <div class="chat-header-title">AICC Workflow Chatbot</div>');
    htmlParts.push('      <div class="chat-header-sub">Powered by your deployed agent workflow</div>');
    htmlParts.push('    </div>');
    htmlParts.push('  </div>');
    htmlParts.push('  <div id="messages" class="chat-messages"></div>');
    htmlParts.push('  <div id="status" class="status"></div>');
    htmlParts.push('  <div class="chat-input">');
    htmlParts.push('    <textarea id="input" rows="1" placeholder="Ask a question about your documents..."></textarea>');
    htmlParts.push('    <button id="sendBtn">');
    htmlParts.push('      <span>Send</span>');
    htmlParts.push('    </button>');
    htmlParts.push('  </div>');
    htmlParts.push('</div>');
    htmlParts.push('');
    htmlParts.push('<!-- Human Input Modal -->');
    htmlParts.push('<div id="humanInputModal" class="human-input-modal">');
    htmlParts.push('  <div class="human-input-box">');
    htmlParts.push('    <div class="human-input-title" id="humanInputTitle">USER INPUT REQUIRED</div>');
    htmlParts.push('    <div class="human-input-message" id="humanInputMessage"></div>');
    htmlParts.push('    <textarea id="humanInputTextarea" class="human-input-textarea" placeholder="Enter your response..."></textarea>');
    htmlParts.push('    <div class="human-input-buttons">');
    htmlParts.push('      <button class="cancel-btn" id="humanInputCancel">Cancel</button>');
    htmlParts.push('      <button class="submit-btn" id="humanInputSubmit">Submit</button>');
    htmlParts.push('    </div>');
    htmlParts.push('  </div>');
    htmlParts.push('</div>');
    htmlParts.push('');
    // Split script tag to avoid parsing issues
    htmlParts.push('<' + 'script>');
    htmlParts.push('  const ENDPOINT_URL = \'' + escapedEndpoint + '\';');
    htmlParts.push('  const SUBMIT_INPUT_URL = ENDPOINT_URL.replace(/\\/$/, \'\') + \'/submit-input/\';');
    htmlParts.push('  const INITIAL_GREETING = ' + escapedGreeting + ';');
    htmlParts.push('');
    htmlParts.push('  const messages = [];');
    htmlParts.push('  const sessionId = \'sess_\' + Math.random().toString(36).slice(2);');
    htmlParts.push('  let currentExecutionId = null;');
    htmlParts.push('  let awaitingHumanInput = false;');
    htmlParts.push('');
    htmlParts.push('  const messagesEl = document.getElementById(\'messages\');');
    htmlParts.push('  const inputEl = document.getElementById(\'input\');');
    htmlParts.push('  const sendBtn = document.getElementById(\'sendBtn\');');
    htmlParts.push('  const statusEl = document.getElementById(\'status\');');
    htmlParts.push('  const humanInputModal = document.getElementById(\'humanInputModal\');');
    htmlParts.push('  const humanInputTitle = document.getElementById(\'humanInputTitle\');');
    htmlParts.push('  const humanInputMessage = document.getElementById(\'humanInputMessage\');');
    htmlParts.push('  const humanInputTextarea = document.getElementById(\'humanInputTextarea\');');
    htmlParts.push('  const humanInputSubmit = document.getElementById(\'humanInputSubmit\');');
    htmlParts.push('  const humanInputCancel = document.getElementById(\'humanInputCancel\');');
    htmlParts.push('');
    htmlParts.push('  function appendMessage(role, text) {');
    htmlParts.push('    const msg = document.createElement(\'div\');');
    htmlParts.push('    msg.className = \'msg \' + (role === \'user\' ? \'user\' : \'assistant\');');
    htmlParts.push('    const bubble = document.createElement(\'div\');');
    htmlParts.push('    bubble.className = \'bubble\';');
    htmlParts.push('    bubble.textContent = text;');
    htmlParts.push('    msg.appendChild(bubble);');
    htmlParts.push('    messagesEl.appendChild(msg);');
    htmlParts.push('    messagesEl.scrollTop = messagesEl.scrollHeight;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function showHumanInputModal(title, message) {');
    htmlParts.push('    humanInputTitle.textContent = title || \'USER INPUT REQUIRED\';');
    htmlParts.push('    humanInputMessage.textContent = message || \'Please provide your input to continue.\';');
    htmlParts.push('    humanInputTextarea.value = \'\';');
    htmlParts.push('    humanInputModal.classList.add(\'active\');');
    htmlParts.push('    humanInputTextarea.focus();');
    htmlParts.push('    awaitingHumanInput = true;');
    htmlParts.push('    inputEl.disabled = true;');
    htmlParts.push('    sendBtn.disabled = true;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  function hideHumanInputModal() {');
    htmlParts.push('    humanInputModal.classList.remove(\'active\');');
    htmlParts.push('    awaitingHumanInput = false;');
    htmlParts.push('    inputEl.disabled = false;');
    htmlParts.push('    sendBtn.disabled = false;');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  async function submitHumanInput() {');
    htmlParts.push('    const userInput = humanInputTextarea.value.trim();');
    htmlParts.push('    if (!userInput) {');
    htmlParts.push('      alert(\'Please enter your response\');');
    htmlParts.push('      return;');
    htmlParts.push('    }');
    htmlParts.push('');
    htmlParts.push('    humanInputSubmit.disabled = true;');
    htmlParts.push('    statusEl.textContent = \'Submitting your response...\';');
    htmlParts.push('');
    htmlParts.push('    try {');
    htmlParts.push('      const resp = await fetch(SUBMIT_INPUT_URL, {');
    htmlParts.push('        method: \'POST\',');
    htmlParts.push('        headers: { \'Content-Type\': \'application/json\' },');
    htmlParts.push('        body: JSON.stringify({');
    htmlParts.push('          session_id: sessionId,');
    htmlParts.push('          user_input: userInput');
    htmlParts.push('        })');
    htmlParts.push('      });');
    htmlParts.push('');
    htmlParts.push('      if (!resp.ok) {');
    htmlParts.push('        const err = await resp.json().catch(() => ({}));');
    htmlParts.push('        throw new Error(err.error || \'HTTP \' + resp.status);');
    htmlParts.push('      }');
    htmlParts.push('');
    htmlParts.push('      const data = await resp.json();');
    htmlParts.push('      ');
    htmlParts.push('      appendMessage(\'user\', userInput);');
    htmlParts.push('      messages.push({ role: \'user\', content: userInput });');
    htmlParts.push('      ');
    htmlParts.push('      hideHumanInputModal();');
    htmlParts.push('');
    htmlParts.push('      if (data.status === \'awaiting_human_input\') {');
    htmlParts.push('        // Add the last conversation message to the chat UI before showing the modal');
    htmlParts.push('        if (data.last_conversation_message) {');
    htmlParts.push('          appendMessage(\'assistant\', data.last_conversation_message);');
    htmlParts.push('          messages.push({ role: \'assistant\', content: data.last_conversation_message });');
    htmlParts.push('        }');
    htmlParts.push('        showHumanInputModal(data.title, data.last_conversation_message);');
    htmlParts.push('        currentExecutionId = data.execution_id;');
    htmlParts.push('      } else if (data.status === \'success\') {');
    htmlParts.push('        const reply = data.response || \'(No response)\';');
    htmlParts.push('        appendMessage(\'assistant\', reply);');
    htmlParts.push('        messages.push({ role: \'assistant\', content: reply });');
    htmlParts.push('        statusEl.textContent = \'\';');
    htmlParts.push('        currentExecutionId = null;');
    htmlParts.push('      } else if (data.status === \'processing\') {');
    htmlParts.push('        statusEl.textContent = \'Workflow is processing. Please wait...\';');
    htmlParts.push('        setTimeout(() => {');
    htmlParts.push('          statusEl.textContent = \'Processing complete. Check the conversation.\';');
    htmlParts.push('        }, 2000);');
    htmlParts.push('      } else {');
    htmlParts.push('        appendMessage(\'assistant\', \'Error: \' + (data.error || \'Unexpected error\'));');
    htmlParts.push('        statusEl.textContent = \'Error from workflow endpoint\';');
    htmlParts.push('      }');
    htmlParts.push('    } catch (e) {');
    htmlParts.push('      console.error(\'Submit input error:\', e);');
    htmlParts.push('      appendMessage(\'assistant\', \'Sorry, there was a problem submitting your input.\');');
    htmlParts.push('      statusEl.textContent = e.message || \'Network error\';');
    htmlParts.push('    } finally {');
    htmlParts.push('      humanInputSubmit.disabled = false;');
    htmlParts.push('    }');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  async function sendMessage() {');
    htmlParts.push('    const text = inputEl.value.trim();');
    htmlParts.push('    if (!text) return;');
    htmlParts.push('');
    htmlParts.push('    if (awaitingHumanInput) {');
    htmlParts.push('      alert(\'Please respond to the human input request first\');');
    htmlParts.push('      return;');
    htmlParts.push('    }');
    htmlParts.push('');
    htmlParts.push('    appendMessage(\'user\', text);');
    htmlParts.push('    messages.push({ role: \'user\', content: text });');
    htmlParts.push('');
    htmlParts.push('    inputEl.value = \'\';');
    htmlParts.push('    sendBtn.disabled = true;');
    htmlParts.push('    statusEl.textContent = \'Contacting workflow...\';');
    htmlParts.push('');
    htmlParts.push('    try {');
    htmlParts.push('      const resp = await fetch(ENDPOINT_URL, {');
    htmlParts.push('        method: \'POST\',');
    htmlParts.push('        headers: { \'Content-Type\': \'application/json\' },');
    htmlParts.push('        body: JSON.stringify({');
    htmlParts.push('          user_query: text,');
    htmlParts.push('          session_id: sessionId');
    htmlParts.push('        })');
    htmlParts.push('      });');
    htmlParts.push('');
    htmlParts.push('      if (!resp.ok) {');
    htmlParts.push('        const err = await resp.json().catch(() => ({}));');
    htmlParts.push('        throw new Error(err.error || \'HTTP \' + resp.status);');
    htmlParts.push('      }');
    htmlParts.push('');
    htmlParts.push('      const data = await resp.json();');
    htmlParts.push('      ');
    htmlParts.push('      if (data.status === \'awaiting_human_input\') {');
    htmlParts.push('        // Add the last conversation message to the chat UI before showing the modal');
    htmlParts.push('        if (data.last_conversation_message) {');
    htmlParts.push('          appendMessage(\'assistant\', data.last_conversation_message);');
    htmlParts.push('          messages.push({ role: \'assistant\', content: data.last_conversation_message });');
    htmlParts.push('        }');
    htmlParts.push('        showHumanInputModal(data.title, data.last_conversation_message);');
    htmlParts.push('        currentExecutionId = data.execution_id;');
    htmlParts.push('        statusEl.textContent = \'Waiting for your input...\';');
    htmlParts.push('      } else if (data.status === \'success\') {');
    htmlParts.push('        const reply = data.response || \'(No response)\';');
    htmlParts.push('        appendMessage(\'assistant\', reply);');
    htmlParts.push('        messages.push({ role: \'assistant\', content: reply });');
    htmlParts.push('        statusEl.textContent = \'\';');
    htmlParts.push('      } else {');
    htmlParts.push('        appendMessage(\'assistant\', \'Error: \' + (data.error || \'Unexpected error\'));');
    htmlParts.push('        statusEl.textContent = \'Error from workflow endpoint\';');
    htmlParts.push('      }');
    htmlParts.push('    } catch (e) {');
    htmlParts.push('      console.error(\'Chat error:\', e);');
    htmlParts.push('      appendMessage(\'assistant\', \'Sorry, there was a problem talking to the workflow.\');');
    htmlParts.push('      statusEl.textContent = e.message || \'Network error\';');
    htmlParts.push('    } finally {');
    htmlParts.push('      if (!awaitingHumanInput) {');
    htmlParts.push('        sendBtn.disabled = false;');
    htmlParts.push('      }');
    htmlParts.push('    }');
    htmlParts.push('  }');
    htmlParts.push('');
    htmlParts.push('  sendBtn.addEventListener(\'click\', sendMessage);');
    htmlParts.push('  inputEl.addEventListener(\'keydown\', (e) => {');
    htmlParts.push('    if (e.key === \'Enter\' && !e.shiftKey && !awaitingHumanInput) {');
    htmlParts.push('      e.preventDefault();');
    htmlParts.push('      sendMessage();');
    htmlParts.push('    }');
    htmlParts.push('  });');
    htmlParts.push('');
    htmlParts.push('  humanInputSubmit.addEventListener(\'click\', submitHumanInput);');
    htmlParts.push('  humanInputCancel.addEventListener(\'click\', () => {');
    htmlParts.push('    hideHumanInputModal();');
    htmlParts.push('    statusEl.textContent = \'Input cancelled\';');
    htmlParts.push('  });');
    htmlParts.push('  humanInputTextarea.addEventListener(\'keydown\', (e) => {');
    htmlParts.push('    if (e.key === \'Enter\' && e.ctrlKey) {');
    htmlParts.push('      e.preventDefault();');
    htmlParts.push('      submitHumanInput();');
    htmlParts.push('    }');
    htmlParts.push('  });');
    htmlParts.push('');
    htmlParts.push('  appendMessage(\'assistant\', INITIAL_GREETING);');
    htmlParts.push('  messages.push({ role: \'assistant\', content: INITIAL_GREETING });');
    htmlParts.push('</' + 'script>');
    htmlParts.push('</body>');
    htmlParts.push('</html>');
    
    return htmlParts.join('\n');
  }
  
  // Reactive variable that calls the function - explicitly track dependencies
  $: embedCode = endpointUrl && initialGreeting ? generateEmbedCode() : '';
  
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
        
        // Construct endpoint URL
        const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
        endpointUrl = `${baseUrl}${deployment.endpoint_path}`;
        
        // Debug logging
        console.log('🔗 DEPLOYMENT: endpointUrl =', endpointUrl);
        console.log('🔗 DEPLOYMENT: initialGreeting =', initialGreeting);
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
      
      await cleanUniversalApi.updateDeployment(projectId, {
        workflow_id: selectedWorkflowId,
        rate_limit_per_minute: rateLimitPerMinute,
        initial_greeting: initialGreeting
      });
      
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
            <input
              type="text"
              bind:value={initialGreeting}
              class="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-oxford-blue focus:border-oxford-blue"
              placeholder="Hi! I am your AI assistant."
            />
            <p class="text-sm text-gray-500 mt-1">
              This message will be shown as the first assistant message in the embedded chatbot. Changes are project-specific.
            </p>
          </div>

          <!-- Embed Snippet -->
          <div>
            <div class="flex items-center justify-between mb-2">
              <label class="block text-sm font-medium text-gray-700">
                HTML Embed Code (copy and paste into your website)
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
              class="w-full h-72 font-mono text-xs px-3 py-3 border border-gray-300 rounded-md bg-gray-50 text-gray-800"
            >{embedCode}</textarea>
            <p class="text-sm text-gray-500 mt-2">
              <i class="fas fa-info-circle mr-1"></i>
              Copy and paste this HTML code into your website where you want the chatbot to appear. The chatbot will load automatically.
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

