<!-- SimpleNodePropertiesPanel.svelte - Simplified Node Properties Panel for Svelte 5 -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  
  // Svelte 5 Props
  interface Props {
    node: any;
    capabilities?: any;
    projectId?: string;
    workflowData?: any;
    bulkModelData?: any;
    modelsLoaded?: boolean;
    hierarchicalPaths?: any[];
    hierarchicalPathsLoaded?: boolean;
  }
  
  let {
    node,
    capabilities = {},
    projectId = '',
    workflowData = null,
    bulkModelData = null,
    modelsLoaded = false,
    hierarchicalPaths = [],
    hierarchicalPathsLoaded = false
  }: Props = $props();
  
  const dispatch = createEventDispatcher();
  
  // Track the current node ID to detect changes
  let currentNodeId = $state(node.id);
  
  // Editable node data - Initialize from current node
  let nodeName = $state(node.data.name || node.data.label || node.type);
  let nodeDescription = $state(node.data.description || '');
  let nodeConfig = $state({ ...node.data });
  
  // Initialize defaults for new nodes
  function initializeNodeDefaults() {
    // Initialize default values based on node type
    if (node.type === 'StartNode' && !nodeConfig.prompt) {
      nodeConfig.prompt = '';
    }
    
    if (['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
      if (!nodeConfig.system_message) {
        if (node.type === 'AssistantAgent') {
          nodeConfig.system_message = 'You are a helpful AI assistant.';
        } else if (node.type === 'DelegateAgent') {
          nodeConfig.system_message = 'You are a specialized delegate agent.';
        } else if (node.type === 'GroupChatManager') {
          nodeConfig.system_message = 'You are a Group Chat Manager responsible for coordinating multiple specialized agents.';
        }
      }
      
      if (!nodeConfig.llm_provider) {
        nodeConfig.llm_provider = 'openai';
        nodeConfig.llm_model = 'gpt-4';
        nodeConfig.temperature = 0.7;
        nodeConfig.max_tokens = 2048;
      }
    }
    
    if (node.type === 'UserProxyAgent') {
      if (!nodeConfig.hasOwnProperty('require_human_input')) {
        nodeConfig.require_human_input = true;
      }
      if (!nodeConfig.hasOwnProperty('code_execution_enabled')) {
        nodeConfig.code_execution_enabled = false;
      }
    }
    
    if (node.type === 'DelegateAgent') {
      if (!nodeConfig.number_of_iterations) {
        nodeConfig.number_of_iterations = 5;
      }
      if (!nodeConfig.termination_condition) {
        nodeConfig.termination_condition = 'FINISH';
      }
    }
    
    if (node.type === 'GroupChatManager') {
      if (!nodeConfig.max_rounds) {
        nodeConfig.max_rounds = 10;
      }
      if (!nodeConfig.termination_strategy) {
        nodeConfig.termination_strategy = 'all_delegates_complete';
      }
    }
  }
  
  // Initialize on component load
  $effect(() => {
    initializeNodeDefaults();
    console.log('🔧 SIMPLE NODE PROPERTIES: Panel opened for', node.type, node.id.slice(-4));
  });
  
  // Deep clone to prevent shared references
  function updateNodeData() {
    const trimmedName = nodeName.trim();
    const trimmedDesc = nodeDescription.trim();
    
    console.log('🔄 SIMPLE UPDATE: Updating node data for', node.id.slice(-4));
    
    // Create completely new objects to prevent shared references
    const baseData = JSON.parse(JSON.stringify(node.data));
    const configData = JSON.parse(JSON.stringify(nodeConfig));
    
    // Create data object with explicit order to ensure our values take precedence
    const updatedData = {
      ...baseData,
      ...configData,
      // These MUST come last to override any conflicts
      name: trimmedName,
      label: trimmedName,
      description: trimmedDesc
    };
    
    const updatedNode = {
      id: node.id,
      type: node.type,
      position: { ...node.position },
      data: updatedData
    };
    
    console.log('✅ SIMPLE UPDATE: Dispatching node update');
    
    dispatch('nodeUpdate', {
      ...updatedNode,
      canvasUpdate: {
        preservePosition: true,
        updateType: 'properties',
        timestamp: Date.now()
      }
    });
  }
  
  function handleNameChange(event: any) {
    const newName = event?.target?.value || nodeName;
    nodeName = newName;
    updateNodeData();
  }
  
  function handleDescriptionChange() {
    updateNodeData();
  }
  
  function closePanel() {
    dispatch('close');
  }
  
  function getNodeIcon(nodeType: string) {
    switch (nodeType) {
      case 'StartNode': return 'fa-play';
      case 'UserProxyAgent': return 'fa-user';
      case 'AssistantAgent': return 'fa-robot';
      case 'GroupChatManager': return 'fa-users';
      case 'DelegateAgent': return 'fa-handshake';
      case 'EndNode': return 'fa-stop';
      default: return 'fa-cog';
    }
  }
  
  function getNodeTypeColor(nodeType: string) {
    switch (nodeType) {
      case 'StartNode': return 'bg-green-600';
      case 'UserProxyAgent': return 'bg-blue-600';
      case 'AssistantAgent': return 'bg-oxford-blue';
      case 'GroupChatManager': return 'bg-purple-600';
      case 'DelegateAgent': return 'bg-orange-600';
      case 'EndNode': return 'bg-red-600';
      default: return 'bg-gray-600';
    }
  }
</script>

<div class="node-properties-panel h-full flex flex-col bg-white">
  <!-- Panel Header -->
  <div class="p-4 border-b border-gray-200">
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 {getNodeTypeColor(node.type)} text-white rounded-lg flex items-center justify-center">
          <i class="fas {getNodeIcon(node.type)} text-lg"></i>
        </div>
        <div>
          <h3 class="font-semibold text-gray-900">Agent Properties</h3>
          <p class="text-sm text-gray-600">{node.type}</p>
        </div>
      </div>
      <button
        class="p-1 rounded hover:bg-gray-100 transition-colors"
        on:click={closePanel}
        title="Close Panel"
      >
        <i class="fas fa-times text-gray-500"></i>
      </button>
    </div>
  </div>
  
  <!-- Properties Form -->
  <div class="flex-1 overflow-y-auto p-4 space-y-4">
    
    <!-- AGENT NAME -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">Agent Name</label>
      <input
        type="text"
        bind:value={nodeName}
        on:input={handleNameChange}
        on:blur={handleNameChange}
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all"
        placeholder="Enter agent name..."
      />
    </div>
    
    <!-- DESCRIPTION -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">Description</label>
      <textarea
        bind:value={nodeDescription}
        on:input={handleDescriptionChange}
        on:blur={handleDescriptionChange}
        rows="2"
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all resize-none"
        placeholder="Describe what this agent does..."
      ></textarea>
    </div>
    
    <!-- SYSTEM MESSAGE / INITIAL PROMPT -->
    {#if node.type === 'AssistantAgent' || node.type === 'DelegateAgent' || node.type === 'GroupChatManager'}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">System Message</label>
        <textarea
          bind:value={nodeConfig.system_message}
          on:input={updateNodeData}
          rows="3"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all resize-none"
          placeholder={node.type === 'AssistantAgent' 
            ? "You are a helpful AI assistant specialized in..." 
            : node.type === 'GroupChatManager'
            ? "You are a Group Chat Manager responsible for coordinating multiple specialized agents..."
            : "You are a specialized delegate agent that works with the Group Chat Manager..."}
        ></textarea>
      </div>
    {:else if node.type === 'StartNode'}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Initial Prompt</label>
        <textarea
          bind:value={nodeConfig.prompt}
          on:input={updateNodeData}
          rows="3"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all resize-none"
          placeholder="Enter the initial prompt to start the workflow..."
        ></textarea>
      </div>
    {/if}
    
    <!-- LLM CONFIGURATION -->
    {#if ['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">LLM Provider</label>
        <select
          bind:value={nodeConfig.llm_provider}
          on:change={updateNodeData}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
        >
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
          <option value="google">Google AI</option>
        </select>
      </div>
      
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">LLM Model</label>
        <select
          bind:value={nodeConfig.llm_model}
          on:change={updateNodeData}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
        >
          {#if nodeConfig.llm_provider === 'openai'}
            <option value="gpt-4">GPT-4</option>
            <option value="gpt-4-turbo">GPT-4 Turbo</option>
            <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
          {:else if nodeConfig.llm_provider === 'anthropic'}
            <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
            <option value="claude-3-5-haiku-20241022">Claude 3.5 Haiku</option>
            <option value="claude-3-opus-20240229">Claude 3 Opus</option>
          {:else if nodeConfig.llm_provider === 'google'}
            <option value="gemini-pro">Gemini Pro</option>
            <option value="gemini-pro-vision">Gemini Pro Vision</option>
          {/if}
        </select>
      </div>
      
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Temperature</label>
          <input
            type="number"
            bind:value={nodeConfig.temperature}
            on:input={updateNodeData}
            min="0"
            max="2"
            step="0.1"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Max Tokens</label>
          <input
            type="number"
            bind:value={nodeConfig.max_tokens}
            on:input={updateNodeData}
            min="100"
            max="8000"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
          />
        </div>
      </div>
      
      {#if node.type === 'GroupChatManager'}
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Max Rounds</label>
          <input
            type="number"
            bind:value={nodeConfig.max_rounds}
            on:input={updateNodeData}
            min="1"
            max="100"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
            placeholder="10"
          />
        </div>
      {/if}
    {/if}
    
    <!-- USER PROXY AGENT SETTINGS -->
    {#if node.type === 'UserProxyAgent'}
      <div class="space-y-3">
        <div>
          <label class="flex items-center space-x-2">
            <input
              type="checkbox"
              bind:checked={nodeConfig.require_human_input}
              on:change={updateNodeData}
              class="w-4 h-4 text-oxford-blue border-gray-300 rounded focus:ring-oxford-blue"
            />
            <span class="text-sm font-medium text-gray-700">Require Human Input</span>
          </label>
        </div>
        
        <div>
          <label class="flex items-center space-x-2">
            <input
              type="checkbox"
              bind:checked={nodeConfig.code_execution_enabled}
              on:change={updateNodeData}
              class="w-4 h-4 text-oxford-blue border-gray-300 rounded focus:ring-oxford-blue"
            />
            <span class="text-sm font-medium text-gray-700">Enable Code Execution</span>
          </label>
        </div>
      </div>
    {/if}
    
    <!-- DELEGATE AGENT SETTINGS -->
    {#if node.type === 'DelegateAgent'}
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Max Iterations</label>
          <input
            type="number"
            bind:value={nodeConfig.number_of_iterations}
            on:input={updateNodeData}
            min="1"
            max="50"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
            placeholder="5"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Termination Condition</label>
          <input
            type="text"
            bind:value={nodeConfig.termination_condition}
            on:input={updateNodeData}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
            placeholder="FINISH"
          />
        </div>
      </div>
    {/if}
    
  </div>
  
  <!-- Panel Footer -->
  <div class="p-4 border-t border-gray-200 bg-gray-50">
    <div class="flex justify-end space-x-2">
      <button
        class="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium"
        on:click={closePanel}
      >
        Cancel
      </button>
      <button
        class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        on:click={updateNodeData}
      >
        <i class="fas fa-save mr-1"></i>
        Save Changes
      </button>
    </div>
  </div>
</div>

<style>
  .node-properties-panel {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  
  :global(.text-oxford-blue) {
    color: #002147;
  }
  
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  
  :global(.focus\:border-oxford-blue:focus) {
    border-color: #002147;
  }
  
  :global(.focus\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
</style>