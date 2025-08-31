<!-- NodePropertiesPanel.svelte - Enhanced Agent Node Configuration Panel with API Key Based Models -->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { dynamicModelsService, type ModelInfo, type ProviderStatus } from '$lib/services/dynamicModelsService';
  import { docAwareService, type SearchMethod, type SearchMethodParameter } from '$lib/services/docAwareService';
  import type { BulkModelData } from '$lib/stores/llmModelsStore';
  
  export let node: any;
  export let capabilities: any;
  export let projectId: string = ''; // Add projectId prop for DocAware functionality
  export let workflowData: any = null; // Add workflow data to get StartNode input
  export let bulkModelData: BulkModelData | null = null; // Pre-loaded model data
  export let modelsLoaded: boolean = false; // Whether models are loaded
  export let hierarchicalPaths: any[] = []; // Hierarchical paths for Content Filter
  export let hierarchicalPathsLoaded: boolean = false; // Whether hierarchical paths are loaded
  
  const dispatch = createEventDispatcher();
  
  // Track the current node ID to detect changes
  let currentNodeId = node.id;
  
  // Editable node data - Initialize from current node
  let nodeName = node.data.name || node.data.label || node.type;
  let nodeDescription = node.data.description || '';
  let nodeConfig = { ...node.data };
  
  // API Key based models state
  let availableModels: ModelInfo[] = [];
  let loadingModels = false;
  let modelsError: string | null = null;
  let lastProviderChange = '';
  let providerStatus: ProviderStatus | null = null;
  let hasValidApiKeys = false;
  
  // 📚 DocAware state
  let availableSearchMethods: SearchMethod[] = [];
  let loadingSearchMethods = false;
  let searchMethodsError: string | null = null;
  let selectedSearchMethod: SearchMethod | null = null;
  let searchParameters: Record<string, any> = {};
  let testingSearch = false;
  let testSearchResults: any = null;
  
  // Initialize defaults for new nodes
  function initializeNodeDefaults() {
    // Initialize default LLM configuration if not present
    if (['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
      if (!nodeConfig.llm_provider) {
        // Set defaults based on agent type - will be updated once we check API keys
        if (node.type === 'AssistantAgent') {
          nodeConfig.llm_provider = 'openai';
          nodeConfig.llm_model = 'gpt-4-turbo';
          nodeConfig.temperature = 0.7;
          nodeConfig.max_tokens = 2048;
        } else if (node.type === 'DelegateAgent') {
          nodeConfig.llm_provider = 'anthropic';
          nodeConfig.llm_model = 'claude-3-5-haiku-20241022';
          nodeConfig.temperature = 0.4;
          nodeConfig.max_tokens = 1024;
        } else if (node.type === 'GroupChatManager') {
          nodeConfig.llm_provider = 'anthropic';
          nodeConfig.llm_model = 'claude-3-5-sonnet-20241022';
          nodeConfig.temperature = 0.5;
          nodeConfig.max_tokens = 1024;
        }
        console.log('🤖 LLM CONFIG: Initialized default config for', node.type, nodeConfig.llm_provider, nodeConfig.llm_model);
      }
    } else if (node.type === 'UserProxyAgent') {
      // UserProxyAgent only gets LLM configuration if DocAware is enabled
      if (nodeConfig.doc_aware && !nodeConfig.llm_provider) {
        nodeConfig.llm_provider = 'openai';
        nodeConfig.llm_model = 'gpt-3.5-turbo';
        nodeConfig.temperature = 0.3;
        nodeConfig.max_tokens = 1024;
        console.log('🤖 LLM CONFIG: Initialized DocAware LLM config for UserProxyAgent');
      }
      
      // Initialize system message if not present for agents that need it
      if (['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
        if (!nodeConfig.system_message) {
          if (node.type === 'AssistantAgent') {
            nodeConfig.system_message = 'You are a helpful AI assistant.';
          } else if (node.type === 'DelegateAgent') {
            nodeConfig.system_message = 'You are a specialized delegate agent.';
          } else if (node.type === 'GroupChatManager') {
            nodeConfig.system_message = 'You are a Group Chat Manager responsible for coordinating multiple specialized agents and synthesizing their contributions into comprehensive solutions.';
          }
          console.log('💬 SYSTEM MESSAGE: Initialized default system message for', node.type);
        }
      }
      
      // Initialize default RAG configuration if not present
      if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type) && !nodeConfig.hasOwnProperty('doc_aware')) {
        nodeConfig.doc_aware = false;
        nodeConfig.vector_collections = [];
        nodeConfig.rag_search_limit = 5;
        nodeConfig.rag_relevance_threshold = 0.7;
        console.log('📚 RAG CONFIG: Initialized default RAG config for', node.type);
      }
    }
  }
  
  // 📚 DocAware Methods
  async function loadSearchMethods() {
    if (loadingSearchMethods) return;
    
    try {
      loadingSearchMethods = true;
      searchMethodsError = null;
      
      console.log('📚 DOCAWARE: Loading search methods');
      console.log('📚 DOCAWARE: Making API call to:', '/agent-orchestration/docaware/search_methods/');
      
      const response = await docAwareService.getSearchMethods();
      
      if (!response || !response.methods) {
        throw new Error('Invalid response structure: missing methods array');
      }
      
      availableSearchMethods = response.methods;
      console.log('✅ DOCAWARE: Successfully loaded', availableSearchMethods.length, 'search methods');
      console.log('📚 DOCAWARE: Method IDs:', availableSearchMethods.map(m => m.id));
      
      // Handle existing configuration after methods load
      if (nodeConfig.search_method && !selectedSearchMethod) {
        await handleSearchMethodChange();
      }
      
    } catch (error) {
      console.error('❌ DOCAWARE: Failed to load search methods:', error);
      console.error('❌ DOCAWARE: Error details:', {
        name: error.name,
        message: error.message,
        stack: error.stack,
        response: error.response,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      });
      
      // Provide actionable error messages
      if (error.response?.status === 404) {
        searchMethodsError = 'DocAware API endpoints not found. Check backend URL configuration.';
      } else if (error.response?.status === 403) {
        searchMethodsError = 'Access denied. Check authentication and permissions.';
      } else if (error.response?.status >= 500) {
        searchMethodsError = 'Server error. Check backend service and database connectivity.';
      } else {
        searchMethodsError = `Failed to load search methods: ${error.response?.status || ''} ${error.message}`;
      }
      
      availableSearchMethods = [];
    } finally {
      loadingSearchMethods = false;
    }
  }
  
  async function handleSearchMethodChange() {
    const methodId = nodeConfig.search_method;
    
    if (!methodId) {
      selectedSearchMethod = null;
      searchParameters = {};
      updateNodeData();
      return;
    }
    
    // Ensure search methods are loaded before proceeding
    if (availableSearchMethods.length === 0 && !loadingSearchMethods) {
      console.log('📚 DOCAWARE: Search methods not loaded, loading now...');
      await loadSearchMethods();
    }
    
    selectedSearchMethod = availableSearchMethods.find(m => m.id === methodId) || null;
    
    if (selectedSearchMethod) {
      // Reset parameters to defaults for new method
      searchParameters = docAwareService.getDefaultParameters(selectedSearchMethod);
      nodeConfig.search_parameters = { ...searchParameters };
      
      console.log('📚 DOCAWARE: Selected method:', selectedSearchMethod.name);
      console.log('📚 DOCAWARE: Default parameters:', searchParameters);
      
      updateNodeData();
    } else if (availableSearchMethods.length > 0) {
      console.error('📚 DOCAWARE: Method not found:', methodId, 'Available:', availableSearchMethods.map(m => m.id));
    }
  }
  
  function handleSearchParameterChange(paramKey: string, value: any) {
    searchParameters[paramKey] = value;
    nodeConfig.search_parameters = { ...searchParameters };
    
    console.log(`📚 DOCAWARE: Updated parameter ${paramKey}:`, value);
    updateNodeData();
  }
  
  async function testSearch() {
    if (!selectedSearchMethod || !projectId || testingSearch) return;
    
    try {
      testingSearch = true;
      testSearchResults = null;
      
      console.log('📚 DOCAWARE: Testing search with method:', selectedSearchMethod.id);
      
      let actualQuery = '';
      let inputSource = 'no input available';
      
      // Only use aggregated input from directly connected nodes
      if (workflowData && workflowData.nodes && workflowData.edges) {
        // Find all nodes that connect TO this current node (input sources)
        const currentNodeId = node.id;
        const inputEdges = workflowData.edges.filter(edge => edge.target === currentNodeId);
        
        console.log('📚 DOCAWARE: Found', inputEdges.length, 'input connections to current node');
        
        if (inputEdges.length > 0) {
          const inputContents = [];
          
          for (const edge of inputEdges) {
            const sourceNode = workflowData.nodes.find(n => n.id === edge.source);
            if (sourceNode) {
              console.log('📚 DOCAWARE: Processing connected node:', sourceNode.type, sourceNode.data.name);
              
              if (sourceNode.type === 'StartNode' && sourceNode.data.prompt) {
                inputContents.push(sourceNode.data.prompt);
                console.log('📚 DOCAWARE: Added StartNode prompt:', sourceNode.data.prompt);
              } else if (sourceNode.data.system_message) {
                inputContents.push(sourceNode.data.system_message);
                console.log('📚 DOCAWARE: Added system message from:', sourceNode.data.name || sourceNode.type);
              }
            }
          }
          
          if (inputContents.length > 0) {
            actualQuery = inputContents.join('; ');
            inputSource = `aggregated input from ${inputEdges.length} connected nodes`;
            console.log('📚 DOCAWARE: Using aggregated input:', actualQuery);
          }
        }
      }
      
      // If no valid query found from connected nodes, show error
      if (!actualQuery || actualQuery.trim().length === 0) {
        console.error('📚 DOCAWARE: No valid input found from connected nodes');
        testSearchResults = {
          success: false,
          error: 'No input available from connected agents. Please connect this DocAware agent to other agents that provide input (StartNode, AssistantAgent, etc.) or ensure connected agents have configured prompts/system messages.',
          query: '',
          method: selectedSearchMethod.id
        };
        toasts?.error('No input available from connected agents');
        return;
      }
      
      console.log('📚 DOCAWARE: Final test query:', actualQuery);
      console.log('📚 DOCAWARE: Input source:', inputSource);
      
      const result = await docAwareService.testSearch(
        projectId,
        selectedSearchMethod.id,
        searchParameters,
        actualQuery,
        nodeConfig.content_filter
      );
      
      testSearchResults = result;
      
      if (result.success) {
        toasts?.success(`Search test successful! Found ${result.results_count} results using ${inputSource}.`);
      } else {
        toasts?.error(`Search test failed: ${result.error}`);
      }
      
    } catch (error) {
      console.error('❌ DOCAWARE: Search test failed:', error);
      toasts?.error('Search test failed');
    } finally {
      testingSearch = false;
    }
  }
  
  // Check if we have any valid API keys from bulk data
  function checkApiKeyAvailability() {
    if (!bulkModelData || !modelsLoaded) {
      hasValidApiKeys = false;
      modelsError = 'Models not loaded yet. Please wait...';
      return;
    }
    
    // Check bulk data for valid providers
    const validProviders = Object.values(bulkModelData.provider_statuses)
      .filter(status => status.api_key_valid);
    
    hasValidApiKeys = validProviders.length > 0;
    
    console.log('🔑 BULK API KEY CHECK: Has valid API keys:', hasValidApiKeys, 'Valid providers:', validProviders.length);
    
    if (!hasValidApiKeys) {
      modelsError = 'No LLM provider API keys are configured. Please configure API keys in settings.';
      availableModels = [];
      return;
    }
    
    // If current provider doesn't have valid API key, switch to first valid provider
    if (nodeConfig.llm_provider) {
      const currentProviderStatus = bulkModelData.provider_statuses[nodeConfig.llm_provider];
      if (!currentProviderStatus?.api_key_valid) {
        const firstValidProvider = validProviders[0];
        if (firstValidProvider) {
          const providerId = Object.keys(bulkModelData.provider_statuses)
            .find(id => bulkModelData.provider_statuses[id] === firstValidProvider);
          
          if (providerId) {
            console.log(`⚠️ BULK API KEY: Current provider ${nodeConfig.llm_provider} not valid, switching to ${providerId}`);
            nodeConfig.llm_provider = providerId;
            nodeConfig.llm_model = ''; // Will be set when models load
            updateNodeData();
          }
        }
      }
    }
  }
  
  // Load models for the current provider from bulk data
  function loadModelsForProvider(providerId: string, forceRefresh = false) {
    if (!providerId) {
      availableModels = [];
      modelsError = 'No provider selected';
      return;
    }
    
    if (!bulkModelData || !modelsLoaded) {
      availableModels = [];
      modelsError = 'Models not loaded yet. Please wait...';
      loadingModels = false;
      return;
    }
    
    console.log(`🚀 BULK MODELS: Loading models for provider ${providerId} from bulk data`);
    
    // Get provider status from bulk data
    providerStatus = bulkModelData.provider_statuses[providerId];
    
    if (!providerStatus?.api_key_valid) {
      availableModels = [];
      modelsError = providerStatus?.message || 'No valid API key for this provider';
      console.log(`❌ BULK MODELS: Provider ${providerId} has no valid API key`);
      return;
    }
    
    // Get models from bulk data - INSTANT!
    const models = bulkModelData.provider_models[providerId] || [];
    availableModels = models;
    modelsError = null;
    
    console.log(`✅ BULK MODELS: Loaded ${models.length} models for ${providerId} instantly!`, models.map(m => m.id));
    
    // If no models available
    if (models.length === 0) {
      modelsError = `No models available for ${providerId.toUpperCase()}. Please check your API key configuration.`;
      return;
    }
    
    // If current model is not in the list, reset to first available model
    if (models.length > 0) {
      const currentModel = nodeConfig.llm_model;
      const modelExists = models.some(model => model.id === currentModel);
      
      if (!modelExists) {
        console.log(`⚠️ BULK MODELS: Current model ${currentModel} not found, switching to ${models[0].id}`);
        nodeConfig.llm_model = models[0].id;
        updateNodeData();
      }
    }
  }
  
  // Handle provider change
  function handleProviderChange() {
    const newProvider = nodeConfig.llm_provider;
    
    if (newProvider !== lastProviderChange) {
      console.log(`🔄 PROVIDER CHANGE: From ${lastProviderChange} to ${newProvider}`);
      lastProviderChange = newProvider;
      
      // Reset model - will be set when models load
      nodeConfig.llm_model = '';
      
      // Load models for the new provider from bulk data
      loadModelsForProvider(newProvider, false);
      
      updateNodeData();
    }
  }
  
  // Use controlled updates instead of reactive statements
  let isUpdatingFromNode = false; // Flag to prevent update loops
  
  function updateLocalStateFromNode() {
    if (!node || !node.id || isUpdatingFromNode) return;
    
    // Extract current values from the node
    const currentName = node.data.name || node.data.label || node.type;
    const currentDesc = node.data.description || '';
    const currentConfig = { ...node.data };
    
    // Check if this is a different node OR if the data has changed
    const isDifferentNode = node.id !== currentNodeId;
    const hasNameChanged = nodeName !== currentName;
    const hasDescChanged = nodeDescription !== currentDesc;
    const hasConfigChanged = JSON.stringify(nodeConfig) !== JSON.stringify(currentConfig);
    
    // Only update if this is a different node or we're not currently editing
    if (isDifferentNode || (hasConfigChanged && !document.activeElement?.closest('.node-properties-panel'))) {
      console.log('🔄 NODE SYNC: Detected changes', {
        isDifferentNode,
        hasNameChanged: hasNameChanged ? `${nodeName} → ${currentName}` : false,
        hasDescChanged,
        hasConfigChanged,
        nodeId: node.id.slice(-4),
        isUserEditing: !!document.activeElement?.closest('.node-properties-panel')
      });
      
      // Update current node ID
      currentNodeId = node.id;
      
      // Update local state to match the node
      nodeName = currentName;
      nodeDescription = currentDesc;
      nodeConfig = currentConfig;
      
      // Initialize defaults if needed
      if (isDifferentNode) {
        initializeNodeDefaults();
        
        // Check API keys and load models for the current provider
        if (nodeConfig.llm_provider) {
          lastProviderChange = nodeConfig.llm_provider;
          checkApiKeyAvailability();
          if (hasValidApiKeys && bulkModelData && modelsLoaded) {
            loadModelsForProvider(nodeConfig.llm_provider, false);
          }
        }
      }
      
      console.log('✅ NODE SYNC: Local state updated', {
        nodeName,
        nodeDescription,
        docAware: nodeConfig.doc_aware,
        nodeId: node.id.slice(-4)
      });
    }
  }
  
  // Initialize on mount and when node changes
  onMount(async () => {
    initializeNodeDefaults();
    console.log('🔧 NODE PROPERTIES: Opening panel for node:', node.id, node.type);
    
    // Check API key availability from bulk data
    checkApiKeyAvailability();
    
    // Load models for the current provider from bulk data
    if (nodeConfig.llm_provider && hasValidApiKeys && bulkModelData && modelsLoaded) {
      lastProviderChange = nodeConfig.llm_provider;
      loadModelsForProvider(nodeConfig.llm_provider, false);
    }
    
    // 📚 DOCAWARE: Load search methods if DocAware is supported
    if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type)) {
      await loadSearchMethods();
    }
  });
  
  // Call update function when node changes
  $: if (node) {
    updateLocalStateFromNode();
  }
  
  // Handle delayed search method loading for DocAware
  $: if (nodeConfig.doc_aware && !selectedSearchMethod && nodeConfig.search_method && availableSearchMethods.length > 0) {
    console.log('📚 DOCAWARE: Reactive - Setting up search method after delayed loading');
    handleSearchMethodChange();
  }
  
  // Deep clone to prevent shared references
  function updateNodeData() {
    const trimmedName = nodeName.trim();
    const trimmedDesc = nodeDescription.trim();
    
    console.log('🔥 UPDATE NODE DATA: Starting update for node', node.id.slice(-4));
    console.log('🔥 NODE CONFIG CHECK:', JSON.stringify(nodeConfig));
    console.log('📚 DOC AWARE STATUS:', nodeConfig.doc_aware);
    
    // Set flag to prevent updateLocalStateFromNode from running
    isUpdatingFromNode = true;
    
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
      id: node.id, // Keep original ID
      type: node.type, // Keep original type
      position: { ...node.position }, // Clone position
      data: updatedData
    };
    
    console.log('🔥 UPDATE NODE DATA DEBUG:', {
      nodeId: node.id.slice(-4),
      originalData: JSON.stringify(node.data),
      updatedData: JSON.stringify(updatedNode.data),
      nameChange: (node.data.name || 'undefined') + ' → ' + trimmedName,
      docAwareValue: updatedNode.data.doc_aware,
      dataMemoryCheck: {
        originalRef: node.data,
        newRef: updatedNode.data,
        isSameReference: node.data === updatedNode.data
      }
    });
    
    // Enhanced dispatch with position preservation
    dispatch('nodeUpdate', {
      ...updatedNode,
      canvasUpdate: {
        preservePosition: true,
        updateType: 'properties',
        timestamp: Date.now()
      }
    });
    
    // Reset flag after a short delay
    setTimeout(() => {
      isUpdatingFromNode = false;
    }, 100);
    
    console.log('✅ NODE PROPERTIES: Update dispatched for node', node.id.slice(-4), 'new name:', trimmedName, 'doc_aware:', updatedNode.data.doc_aware);
  }
  
  function handleNameChange(event) {
    const newName = event?.target?.value || nodeName;
    const currentName = node.data.name || node.data.label || node.type;
    
    console.log('📝 HANDLE NAME CHANGE: Called with newName=', newName, 'currentName=', currentName);
    console.log('📝 BINDING CHECK: nodeName variable=', nodeName, 'input value=', newName);
    
    if (newName.trim() !== currentName) {
      console.log('📝 NAME CHANGE DEBUG:', {
        from: currentName,
        to: newName.trim(),
        nodeId: node.id.slice(-4),
        currentNodeData: node.data
      });
      
      // Update nodeName variable to match input
      nodeName = newName;
      updateNodeData();
    } else {
      console.log('⚠️ NAME CHANGE: No change detected, not updating');
    }
  }
  
  function handleDescriptionChange() {
    if (nodeDescription.trim() !== (node.data.description || '')) {
      console.log('📝 DESC CHANGE: Updated description for node', node.id.slice(-4));
      updateNodeData();
    }
  }
  
  function saveNodeChanges() {
    try {
      const updatedNode = {
        ...node,
        data: {
          ...node.data,
          name: nodeName,
          description: nodeDescription,
          label: nodeName, // Ensure label is synchronized
          ...nodeConfig
        }
      };
      
      // Enhanced save with canvas context
      dispatch('nodeUpdate', {
        ...updatedNode,
        canvasUpdate: {
          preservePosition: true,
          updateType: 'save',
          timestamp: Date.now(),
          triggerCanvasRedraw: true
        }
      });
      toasts.success('Node updated successfully');
      
      console.log('✅ NODE PROPERTIES: Node updated:', node.id);
      
    } catch (error) {
      console.error('❌ NODE PROPERTIES: Update failed:', error);
      toasts.error('Failed to update node');
    }
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
  
  // Refresh models function - now uses bulk data
  function refreshModels() {
    if (nodeConfig.llm_provider && bulkModelData && modelsLoaded) {
      console.log('🔄 REFRESH: Refreshing models from bulk data');
      loadModelsForProvider(nodeConfig.llm_provider, false);
    } else {
      console.log('⚠️ REFRESH: Cannot refresh - bulk data not available');
      modelsError = 'Bulk model data not available. Please wait for models to load.';
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
  
  <!-- Properties Form - Enhanced with API Key Based Models -->
  <div class="flex-1 overflow-y-auto p-4 space-y-4">
    
    <!-- API Key Status Warning -->
    {#if !hasValidApiKeys}
      <div class="p-3 bg-red-50 border border-red-200 rounded-lg">
        <div class="flex items-center">
          <i class="fas fa-exclamation-triangle text-red-500 mr-2"></i>
          <div class="text-red-700">
            <div class="font-medium">No LLM API Keys Configured</div>
            <div class="text-sm mt-1">Please configure API keys for OpenAI, Anthropic, or Google AI to use LLM models.</div>
          </div>
        </div>
      </div>
    {/if}
    
    <!-- AGENT NAME -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">Agent Name</label>
      <input
        type="text"
        bind:value={nodeName}
        on:input={(e) => handleNameChange(e)}
        on:blur={(e) => handleNameChange(e)}
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
    
    <!-- SYSTEM MESSAGE - For AI Assistant, Delegate, GroupChatManager, and Start Node -->
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
    
    <!-- LLM PROVIDER - For AI agents (excluding UserProxyAgent which has special handling) -->
    {#if ['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">LLM Provider</label>
        {#if hasValidApiKeys}
          <select
            bind:value={nodeConfig.llm_provider}
            on:change={handleProviderChange}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google AI</option>
          </select>
        {:else}
          <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
            <option>No API keys configured</option>
          </select>
        {/if}
        
        <!-- Provider Status Display -->
        {#if providerStatus}
          <div class="mt-2 text-xs">
            {#if providerStatus.api_key_valid}
              <div class="text-green-600 flex items-center">
                <i class="fas fa-check-circle mr-1"></i>
                {providerStatus.name} API key configured and valid
              </div>
            {:else}
              <div class="text-red-600 flex items-center">
                <i class="fas fa-exclamation-circle mr-1"></i>
                {providerStatus.message}
              </div>
            {/if}
          </div>
        {/if}
      </div>
      
      <!-- LLM MODEL - Enhanced with API Key Based Loading -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-medium text-gray-700">LLM Model</label>
          {#if nodeConfig.llm_provider && hasValidApiKeys}
            <button
              class="text-xs text-oxford-blue hover:text-blue-700 transition-colors flex items-center"
              on:click={refreshModels}
              disabled={loadingModels}
              title="Refresh models list"
            >
              <i class="fas {loadingModels ? 'fa-spinner fa-spin' : 'fa-sync-alt'} mr-1"></i>
              Refresh
            </button>
          {/if}
        </div>
        
        {#if !hasValidApiKeys}
          <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
            <option>Configure API keys to see models</option>
          </select>
        {:else if loadingModels}
          <div class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 flex items-center justify-center">
            <i class="fas fa-spinner fa-spin mr-2 text-oxford-blue"></i>
            <span class="text-sm text-gray-600">Loading models...</span>
          </div>
        {:else if modelsError}
          <div class="w-full px-3 py-2 border border-red-300 rounded-lg bg-red-50 text-red-700 text-sm">
            <i class="fas fa-exclamation-triangle mr-2"></i>
            {modelsError}
          </div>
        {:else if availableModels.length === 0}
          <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
            <option>{dynamicModelsService.getNoApiKeyMessage(nodeConfig.llm_provider)}</option>
          </select>
        {:else}
          <select
            bind:value={nodeConfig.llm_model}
            on:change={updateNodeData}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            {#each availableModels as model}
              <option value={model.id} title={model.capabilities ? model.capabilities.join(', ') : ''}>
                {model.display_name || model.name}
                {#if model.cost_per_1k_tokens}
                  (${model.cost_per_1k_tokens}/1k tokens)
                {/if}
              </option>
            {/each}
          </select>
        {/if}
        
        <!-- Model Info Display -->
        {#if availableModels.length > 0 && nodeConfig.llm_model}
          {@const selectedModel = availableModels.find(m => m.id === nodeConfig.llm_model)}
          {#if selectedModel}
            <div class="mt-2 p-2 bg-blue-50 rounded-lg border border-blue-200">
              <div class="text-xs text-blue-700">
                <div class="flex items-center justify-between">
                  <span class="font-medium">{selectedModel.display_name}</span>
                  {#if selectedModel.cost_per_1k_tokens}
                    <span class="bg-blue-100 px-2 py-1 rounded">${selectedModel.cost_per_1k_tokens}/1k tokens</span>
                  {/if}
                </div>
                {#if selectedModel.context_length}
                  <div class="mt-1">Context: {selectedModel.context_length.toLocaleString()} tokens</div>
                {/if}
                {#if selectedModel.capabilities && selectedModel.capabilities.length > 0}
                  <div class="mt-1">Capabilities: {selectedModel.capabilities.join(', ')}</div>
                {/if}
                {#if selectedModel.recommended_for && selectedModel.recommended_for.includes(node.type)}
                  <div class="mt-1 text-green-700">
                    <i class="fas fa-check-circle mr-1"></i>
                    Recommended for {node.type}
                  </div>
                {/if}
              </div>
            </div>
          {/if}
        {/if}
      </div>
      
      <!-- TEMPERATURE AND MAX TOKENS/MAX ROUNDS - Different layout for GroupChatManager -->
      {#if node.type === 'GroupChatManager'}
        <!-- GROUP CHAT MANAGER: Temperature and Max Rounds side by side -->
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
        </div>
        
        <!-- Max Tokens full width -->
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
        
        <!-- Termination Strategy full width -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Termination Strategy</label>
          <select
            bind:value={nodeConfig.termination_strategy}
            on:change={updateNodeData}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            <option value="all_delegates_complete">All Delegates Complete</option>
            <option value="any_delegate_complete">Any Delegate Complete</option>
            <option value="max_iterations_reached">Max Iterations Reached</option>
            <option value="custom_condition">Custom Condition</option>
          </select>
        </div>
      {:else}
        <!-- OTHER AGENTS: Temperature and Max Tokens side by side -->
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
      {/if}
    {/if}
    
    <!-- USERPROXY AGENT SPECIFIC CONFIGURATION -->
    {#if node.type === 'UserProxyAgent'}
      <!-- DocAware Toggle -->
      <div>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">DocAware</label>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={nodeConfig.doc_aware}
              on:change={async (e) => {
                nodeConfig.doc_aware = e.target.checked;
                
                if (e.target.checked) {
                  // When enabling DocAware, ensure we have search methods loaded
                  if (availableSearchMethods.length === 0 && !loadingSearchMethods) {
                    console.log('📚 DOCAWARE: Toggle enabled - loading search methods');
                    await loadSearchMethods();
                  }
                  
                  // Set default values
                  if (!nodeConfig.vector_collections || nodeConfig.vector_collections.length === 0) {
                    nodeConfig.vector_collections = ['project_documents'];
                  }
                  
                  // Set default search method after ensuring methods are loaded
                  if (!nodeConfig.search_method && availableSearchMethods.length > 0) {
                    nodeConfig.search_method = 'semantic_search';
                    await handleSearchMethodChange();
                  } else if (!nodeConfig.search_method) {
                    // If still no methods available, set fallback
                    console.warn('📚 DOCAWARE: No search methods available, will retry when methods load');
                  }
                  
                  // Set default LLM configuration when DocAware is enabled
                  if (!nodeConfig.llm_provider) {
                    nodeConfig.llm_provider = 'openai';
                    nodeConfig.llm_model = 'gpt-3.5-turbo';
                    nodeConfig.temperature = 0.3;
                    nodeConfig.max_tokens = 1024;
                  }
                } else {
                  // When disabling DocAware, clear search configuration
                  nodeConfig.search_method = '';
                  selectedSearchMethod = null;
                  searchParameters = {};
                  testSearchResults = null;
                  
                  // Clear LLM configuration when DocAware is disabled
                  nodeConfig.llm_provider = '';
                  nodeConfig.llm_model = '';
                  nodeConfig.system_message = '';
                }
                
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Enable document-aware RAG capabilities for this agent</p>
      </div>
      
      <!-- User Proxy Specific Settings -->
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
      
      <!-- LLM PROVIDER - Only visible when DocAware is enabled -->
      {#if nodeConfig.doc_aware}
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">LLM Provider</label>
          {#if hasValidApiKeys}
            <select
              bind:value={nodeConfig.llm_provider}
              on:change={handleProviderChange}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="google">Google AI</option>
            </select>
          {:else}
            <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
              <option>No API keys configured</option>
            </select>
          {/if}
          
          <!-- Provider Status Display -->
          {#if providerStatus}
            <div class="mt-2 text-xs">
              {#if providerStatus.api_key_valid}
                <div class="text-green-600 flex items-center">
                  <i class="fas fa-check-circle mr-1"></i>
                  {providerStatus.name} API key configured and valid
                </div>
              {:else}
                <div class="text-red-600 flex items-center">
                  <i class="fas fa-exclamation-circle mr-1"></i>
                  {providerStatus.message}
                </div>
              {/if}
            </div>
          {/if}
        </div>
        
        <!-- LLM MODEL - Only visible when DocAware is enabled -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium text-gray-700">LLM Model</label>
            {#if nodeConfig.llm_provider && hasValidApiKeys}
              <button
                class="text-xs text-oxford-blue hover:text-blue-700 transition-colors flex items-center"
                on:click={refreshModels}
                disabled={loadingModels}
                title="Refresh models list"
              >
                <i class="fas {loadingModels ? 'fa-spinner fa-spin' : 'fa-sync-alt'} mr-1"></i>
                Refresh
              </button>
            {/if}
          </div>
          
          {#if !hasValidApiKeys}
            <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
              <option>Configure API keys to see models</option>
            </select>
          {:else if loadingModels}
            <div class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 flex items-center justify-center">
              <i class="fas fa-spinner fa-spin mr-2 text-oxford-blue"></i>
              <span class="text-sm text-gray-600">Loading models...</span>
            </div>
          {:else if modelsError}
            <div class="w-full px-3 py-2 border border-red-300 rounded-lg bg-red-50 text-red-700 text-sm">
              <i class="fas fa-exclamation-triangle mr-2"></i>
              {modelsError}
            </div>
          {:else if availableModels.length === 0}
            <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
              <option>{dynamicModelsService.getNoApiKeyMessage(nodeConfig.llm_provider)}</option>
            </select>
          {:else}
            <select
              bind:value={nodeConfig.llm_model}
              on:change={updateNodeData}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
            >
              {#each availableModels as model}
                <option value={model.id} title={model.capabilities ? model.capabilities.join(', ') : ''}>
                  {model.display_name || model.name}
                  {#if model.cost_per_1k_tokens}
                    (${model.cost_per_1k_tokens}/1k tokens)
                  {/if}
                </option>
              {/each}
            </select>
          {/if}
          
          <!-- Model Info Display -->
          {#if availableModels.length > 0 && nodeConfig.llm_model}
            {@const selectedModel = availableModels.find(m => m.id === nodeConfig.llm_model)}
            {#if selectedModel}
              <div class="mt-2 p-2 bg-blue-50 rounded-lg border border-blue-200">
                <div class="text-xs text-blue-700">
                  <div class="flex items-center justify-between">
                    <span class="font-medium">{selectedModel.display_name}</span>
                    {#if selectedModel.cost_per_1k_tokens}
                      <span class="bg-blue-100 px-2 py-1 rounded">${selectedModel.cost_per_1k_tokens}/1k tokens</span>
                    {/if}
                  </div>
                  {#if selectedModel.context_length}
                    <div class="mt-1">Context: {selectedModel.context_length.toLocaleString()} tokens</div>
                  {/if}
                  {#if selectedModel.capabilities && selectedModel.capabilities.length > 0}
                    <div class="mt-1">Capabilities: {selectedModel.capabilities.join(', ')}</div>
                  {/if}
                  {#if selectedModel.recommended_for && selectedModel.recommended_for.includes(node.type)}
                    <div class="mt-1 text-green-700">
                      <i class="fas fa-check-circle mr-1"></i>
                      Recommended for {node.type}
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
          {/if}
        </div>
        
        <!-- SYSTEM MESSAGE - Only visible when DocAware is enabled -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">System Message</label>
          <textarea
            bind:value={nodeConfig.system_message}
            on:input={updateNodeData}
            rows="3"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all resize-none"
            placeholder="You are a helpful assistant that uses retrieved documents to answer user questions..."
          ></textarea>
        </div>
        
        <!-- TEMPERATURE AND MAX TOKENS - Only visible when DocAware is enabled -->
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
        
        <!-- DOCAWARE CONFIGURATION - Show when DocAware is enabled for UserProxy -->
        <div class="border border-blue-200 rounded-lg p-4 bg-blue-50">
          <div class="flex items-center mb-3">
            <i class="fas fa-book text-blue-600 mr-2"></i>
            <h4 class="font-medium text-blue-900">Document Search Configuration</h4>
          </div>
          
          <!-- Search Method Selection -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Search Method</label>
            {#if loadingSearchMethods}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading search methods...</span>
              </div>
            {:else if searchMethodsError}
              <div class="w-full px-3 py-2 border border-red-300 rounded-lg bg-red-50">
                <div class="text-red-700 text-sm flex items-center">
                  <i class="fas fa-exclamation-triangle mr-2"></i>
                  {searchMethodsError}
                </div>
                <button 
                  class="mt-2 text-xs text-red-600 hover:text-red-800 underline flex items-center"
                  on:click={() => loadSearchMethods()}
                >
                  <i class="fas fa-sync mr-1"></i>
                  Retry Loading Search Methods
                </button>
              </div>
            {:else if availableSearchMethods.length === 0}
              <div class="w-full px-3 py-2 border border-yellow-300 rounded-lg bg-yellow-50">
                <div class="text-yellow-700 text-sm flex items-center">
                  <i class="fas fa-exclamation-circle mr-2"></i>
                  No search methods available. Check DocAware service configuration.
                </div>
                <button 
                  class="mt-2 text-xs text-yellow-600 hover:text-yellow-800 underline flex items-center"
                  on:click={() => loadSearchMethods()}
                >
                  <i class="fas fa-sync mr-1"></i>
                  Retry Loading Search Methods
                </button>
              </div>
            {:else}
              <!-- Normal dropdown when methods are available -->
              <select
                bind:value={nodeConfig.search_method}
                on:change={() => handleSearchMethodChange()}
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-600 focus:ring-2 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
              >
                <option value="">Select search method...</option>
                {#each availableSearchMethods as method}
                  <option value={method.id}>{method.name}</option>
                {/each}
              </select>
            {/if}
            
            <!-- Search Method Description -->
            {#if selectedSearchMethod}
              <div class="mt-2 p-2 bg-blue-100 rounded text-xs text-blue-700">
                <strong>{selectedSearchMethod.name}:</strong> {selectedSearchMethod.description}
              </div>
            {/if}
          </div>
          
          <!-- Content Filter Selection -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Content Filter</label>
            {#if !hierarchicalPathsLoaded}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading content filter data...</span>
              </div>
            {:else if hierarchicalPaths.length === 0}
              <div class="w-full px-3 py-2 border border-yellow-300 rounded-lg bg-yellow-50">
                <div class="text-yellow-700 text-sm flex items-center">
                  <i class="fas fa-info-circle mr-2"></i>
                  No folders available for filtering. Upload and process documents first.
                </div>
              </div>
            {:else}
              <select
                bind:value={nodeConfig.content_filter}
                on:change={updateNodeData}
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-600 focus:ring-2 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
              >
                <option value="">All project files (no filter)</option>
                {#each hierarchicalPaths as folder}
                  <option value={folder.id}>📁 {folder.displayName}</option>
                {/each}
              </select>
            {/if}
            
            <!-- Content Filter Description -->
            {#if nodeConfig.content_filter && hierarchicalPaths.length > 0}
              {@const selectedFilter = hierarchicalPaths.find(p => p.id === nodeConfig.content_filter)}
              {#if selectedFilter}
                <div class="mt-2 p-2 bg-green-100 rounded text-xs text-green-700">
                  <div class="flex items-center">
                    <i class="fas fa-folder mr-1"></i>
                    <strong>Filter Active:</strong>
                  </div>
                  <div class="mt-1">
                    DocAware will only search documents in folder: <strong>{selectedFilter.name || selectedFilter.displayName}</strong>
                  </div>
                  <div class="text-xs text-green-600 mt-1">
                    Path: {selectedFilter.path || selectedFilter.displayName}
                  </div>
                </div>
              {/if}
            {:else if nodeConfig.content_filter === '' || !nodeConfig.content_filter}
              <div class="mt-2 p-2 bg-gray-100 rounded text-xs text-gray-600">
                <i class="fas fa-globe mr-1"></i>
                <strong>No Filter:</strong> DocAware will search all project documents
              </div>
            {/if}
          </div>
          
          <!-- Dynamic Search Method Parameters -->
          {#if selectedSearchMethod}
            <div class="space-y-3">
              <h5 class="text-sm font-medium text-gray-700">Search Parameters</h5>
              
              {#each docAwareService.generateParameterInputs(selectedSearchMethod) as {key, parameter, defaultValue}}
                <div>
                  <label class="block text-xs font-medium text-gray-600 mb-1">
                    {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    {#if parameter.description}
                      <i class="fas fa-question-circle text-gray-400 ml-1" title="{parameter.description}"></i>
                    {/if}
                  </label>
                  
                  {#if parameter.type === 'select'}
                    <select
                      value={searchParameters[key] || defaultValue}
                      on:change={(e) => handleSearchParameterChange(key, e.target.value)}
                      class="w-full px-2 py-1 border border-gray-200 rounded text-xs focus:border-blue-600 focus:ring-1 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
                    >
                      {#each parameter.options || [] as option}
                        <option value={option}>{option}</option>
                      {/each}
                    </select>
                  {:else if parameter.type === 'multiselect'}
                    <div class="text-xs text-gray-500">Multi-select (Advanced): {JSON.stringify(searchParameters[key] || defaultValue)}</div>
                  {:else if parameter.type === 'number'}
                    <input
                      type="number"
                      value={searchParameters[key] || defaultValue}
                      min={parameter.min}
                      max={parameter.max}
                      step={parameter.step || 1}
                      on:input={(e) => handleSearchParameterChange(key, parseFloat(e.target.value) || defaultValue)}
                      class="w-full px-2 py-1 border border-gray-200 rounded text-xs focus:border-blue-600 focus:ring-1 focus:ring-blue-600 focus:ring-opacity-20"
                    />
                  {:else if parameter.type === 'boolean'}
                    <label class="flex items-center">
                      <input
                        type="checkbox"
                        checked={searchParameters[key] !== undefined ? searchParameters[key] : defaultValue}
                        on:change={(e) => handleSearchParameterChange(key, e.target.checked)}
                        class="mr-2 text-blue-600 border-gray-300 rounded focus:ring-blue-600"
                      />
                      <span class="text-xs text-gray-600">Enable this option</span>
                    </label>
                  {:else if parameter.type === 'text'}
                    <input
                      type="text"
                      value={searchParameters[key] || defaultValue || ''}
                      on:input={(e) => handleSearchParameterChange(key, e.target.value)}
                      placeholder={parameter.description}
                      class="w-full px-2 py-1 border border-gray-200 rounded text-xs focus:border-blue-600 focus:ring-1 focus:ring-blue-600 focus:ring-opacity-20"
                    />
                  {/if}
                  
                  {#if parameter.description}
                    <p class="text-xs text-gray-500 mt-1">{parameter.description}</p>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
      
    {/if}
    
    <!-- DOCAWARE TOGGLE - For other applicable agents (excluding UserProxyAgent) -->
    {#if ['AssistantAgent', 'DelegateAgent'].includes(node.type)}
      <div>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">DocAware</label>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={nodeConfig.doc_aware}
              on:change={async (e) => {
                nodeConfig.doc_aware = e.target.checked;
                
                if (e.target.checked) {
                  // When enabling DocAware, ensure we have search methods loaded
                  if (availableSearchMethods.length === 0 && !loadingSearchMethods) {
                    console.log('📚 DOCAWARE: Toggle enabled - loading search methods');
                    await loadSearchMethods();
                  }
                  
                  // Set default values
                  if (!nodeConfig.vector_collections || nodeConfig.vector_collections.length === 0) {
                    nodeConfig.vector_collections = ['project_documents'];
                  }
                  
                  // Set default search method after ensuring methods are loaded
                  if (!nodeConfig.search_method && availableSearchMethods.length > 0) {
                    nodeConfig.search_method = 'semantic_search';
                    await handleSearchMethodChange();
                  } else if (!nodeConfig.search_method) {
                    // If still no methods available, set fallback
                    console.warn('📚 DOCAWARE: No search methods available, will retry when methods load');
                  }
                } else {
                  // When disabling DocAware, clear search configuration
                  nodeConfig.search_method = '';
                  selectedSearchMethod = null;
                  searchParameters = {};
                  testSearchResults = null;
                }
                
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Enable document-aware RAG capabilities for this agent</p>
      </div>
      
      <!-- DOCAWARE CONFIGURATION - Show when DocAware is enabled -->
      {#if nodeConfig.doc_aware}
        <div class="border border-blue-200 rounded-lg p-4 bg-blue-50">
          <div class="flex items-center mb-3">
            <i class="fas fa-book text-blue-600 mr-2"></i>
            <h4 class="font-medium text-blue-900">Document Search Configuration</h4>
          </div>
          
          <!-- Search Method Selection -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Search Method</label>
            {#if loadingSearchMethods}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading search methods...</span>
              </div>
            {:else if searchMethodsError}
              <div class="w-full px-3 py-2 border border-red-300 rounded-lg bg-red-50">
                <div class="text-red-700 text-sm flex items-center">
                  <i class="fas fa-exclamation-triangle mr-2"></i>
                  {searchMethodsError}
                </div>
                <button 
                  class="mt-2 text-xs text-red-600 hover:text-red-800 underline flex items-center"
                  on:click={() => loadSearchMethods()}
                >
                  <i class="fas fa-sync mr-1"></i>
                  Retry Loading Search Methods
                </button>
              </div>
            {:else if availableSearchMethods.length === 0}
              <div class="w-full px-3 py-2 border border-yellow-300 rounded-lg bg-yellow-50">
                <div class="text-yellow-700 text-sm flex items-center">
                  <i class="fas fa-exclamation-circle mr-2"></i>
                  No search methods available. Check DocAware service configuration.
                </div>
                <button 
                  class="mt-2 text-xs text-yellow-600 hover:text-yellow-800 underline flex items-center"
                  on:click={() => loadSearchMethods()}
                >
                  <i class="fas fa-sync mr-1"></i>
                  Retry Loading Search Methods
                </button>
              </div>
            {:else}
              <!-- Normal dropdown when methods are available -->
              <select
                bind:value={nodeConfig.search_method}
                on:change={() => handleSearchMethodChange()}
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-600 focus:ring-2 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
              >
                <option value="">Select search method...</option>
                {#each availableSearchMethods as method}
                  <option value={method.id}>{method.name}</option>
                {/each}
              </select>
            {/if}
            
            <!-- Search Method Description -->
            {#if selectedSearchMethod}
              <div class="mt-2 p-2 bg-blue-100 rounded text-xs text-blue-700">
                <strong>{selectedSearchMethod.name}:</strong> {selectedSearchMethod.description}
              </div>
            {/if}
          </div>
          
          <!-- Content Filter Selection -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Content Filter</label>
            {#if !hierarchicalPathsLoaded}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading content filter data...</span>
              </div>
            {:else if hierarchicalPaths.length === 0}
              <div class="w-full px-3 py-2 border border-yellow-300 rounded-lg bg-yellow-50">
                <div class="text-yellow-700 text-sm flex items-center">
                  <i class="fas fa-info-circle mr-2"></i>
                  No folders available for filtering. Upload and process documents first.
                </div>
              </div>
            {:else}
              <select
                bind:value={nodeConfig.content_filter}
                on:change={updateNodeData}
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-600 focus:ring-2 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
              >
                <option value="">All project files (no filter)</option>
                {#each hierarchicalPaths as folder}
                  <option value={folder.id}>📁 {folder.displayName}</option>
                {/each}
              </select>
            {/if}
            
            <!-- Content Filter Description -->
            {#if nodeConfig.content_filter && hierarchicalPaths.length > 0}
              {@const selectedFilter = hierarchicalPaths.find(p => p.id === nodeConfig.content_filter)}
              {#if selectedFilter}
                <div class="mt-2 p-2 bg-green-100 rounded text-xs text-green-700">
                  <div class="flex items-center">
                    <i class="fas fa-folder mr-1"></i>
                    <strong>Filter Active:</strong>
                  </div>
                  <div class="mt-1">
                    DocAware will only search documents in folder: <strong>{selectedFilter.name || selectedFilter.displayName}</strong>
                  </div>
                  <div class="text-xs text-green-600 mt-1">
                    Path: {selectedFilter.path || selectedFilter.displayName}
                  </div>
                </div>
              {/if}
            {:else if nodeConfig.content_filter === '' || !nodeConfig.content_filter}
              <div class="mt-2 p-2 bg-gray-100 rounded text-xs text-gray-600">
                <i class="fas fa-globe mr-1"></i>
                <strong>No Filter:</strong> DocAware will search all project documents
              </div>
            {/if}
          </div>
          
          <!-- Dynamic Search Method Parameters -->
          {#if selectedSearchMethod}
            <div class="space-y-3">
              <h5 class="text-sm font-medium text-gray-700">Search Parameters</h5>
              
              {#each docAwareService.generateParameterInputs(selectedSearchMethod) as {key, parameter, defaultValue}}
                <div>
                  <label class="block text-xs font-medium text-gray-600 mb-1">
                    {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    {#if parameter.description}
                      <i class="fas fa-question-circle text-gray-400 ml-1" title="{parameter.description}"></i>
                    {/if}
                  </label>
                  
                  {#if parameter.type === 'select'}
                    <select
                      value={searchParameters[key] || defaultValue}
                      on:change={(e) => handleSearchParameterChange(key, e.target.value)}
                      class="w-full px-2 py-1 border border-gray-200 rounded text-xs focus:border-blue-600 focus:ring-1 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
                    >
                      {#each parameter.options || [] as option}
                        <option value={option}>{option}</option>
                      {/each}
                    </select>
                  {:else if parameter.type === 'multiselect'}
                    <div class="text-xs text-gray-500">Multi-select (Advanced): {JSON.stringify(searchParameters[key] || defaultValue)}</div>
                  {:else if parameter.type === 'number'}
                    <input
                      type="number"
                      value={searchParameters[key] || defaultValue}
                      min={parameter.min}
                      max={parameter.max}
                      step={parameter.step || 1}
                      on:input={(e) => handleSearchParameterChange(key, parseFloat(e.target.value) || defaultValue)}
                      class="w-full px-2 py-1 border border-gray-200 rounded text-xs focus:border-blue-600 focus:ring-1 focus:ring-blue-600 focus:ring-opacity-20"
                    />
                  {:else if parameter.type === 'boolean'}
                    <label class="flex items-center">
                      <input
                        type="checkbox"
                        checked={searchParameters[key] !== undefined ? searchParameters[key] : defaultValue}
                        on:change={(e) => handleSearchParameterChange(key, e.target.checked)}
                        class="mr-2 text-blue-600 border-gray-300 rounded focus:ring-blue-600"
                      />
                      <span class="text-xs text-gray-600">Enable this option</span>
                    </label>
                  {:else if parameter.type === 'text'}
                    <input
                      type="text"
                      value={searchParameters[key] || defaultValue || ''}
                      on:input={(e) => handleSearchParameterChange(key, e.target.value)}
                      placeholder={parameter.description}
                      class="w-full px-2 py-1 border border-gray-200 rounded text-xs focus:border-blue-600 focus:ring-1 focus:ring-blue-600 focus:ring-opacity-20"
                    />
                  {/if}
                  
                  {#if parameter.description}
                    <p class="text-xs text-gray-500 mt-1">{parameter.description}</p>
                  {/if}
                </div>
              {/each}
            </div>
            
            <!-- Test Search Button -->
            {#if projectId}
              <div class="mt-4 pt-3 border-t border-blue-200">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-medium text-gray-700">Test Search</span>
                  <button
                    class="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    on:click={testSearch}
                    disabled={testingSearch}
                  >
                    {#if testingSearch}
                      <i class="fas fa-spinner fa-spin mr-1"></i>
                      Testing...
                    {:else}
                      <i class="fas fa-search mr-1"></i>
                      Test Search
                    {/if}
                  </button>
                </div>
                
                <!-- Test Results - Enhanced Display -->
                {#if testSearchResults}
                  <div class="mt-2 rounded text-xs {testSearchResults.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}">
                    {#if testSearchResults.success}
                      <!-- Success Header -->
                      <div class="p-2 border-b border-green-200 bg-green-100">
                        <div class="flex items-center text-green-800">
                          <i class="fas fa-check-circle mr-2"></i>
                          <strong>Test Successful!</strong>
                        </div>
                        <div class="text-green-700 mt-1">
                          Found <strong>{testSearchResults.results_count}</strong> results using <strong>{testSearchResults.method}</strong>
                        </div>
                        <div class="text-green-600 text-xs mt-1">
                          Query: "{testSearchResults.query}"
                        </div>
                      </div>
                      
                      <!-- Search Results List -->
                      {#if testSearchResults.sample_results && testSearchResults.sample_results.length > 0}
                        <div class="p-2">
                          <div class="text-green-800 font-medium mb-2">
                            Sample Results ({testSearchResults.sample_results.length} shown):
                          </div>
                          
                          <div class="space-y-2 max-h-64 overflow-y-auto">
                            {#each testSearchResults.sample_results as result, index}
                              <div class="bg-green-100 border border-green-200 rounded p-2">
                                <!-- Result Header -->
                                <div class="flex items-center justify-between mb-1">
                                  <span class="font-medium text-green-800">
                                    Result #{index + 1}
                                    {#if result.source}
                                      - {result.source}
                                    {/if}
                                  </span>
                                  <div class="flex items-center space-x-2 text-xs text-green-600">
                                    {#if result.score !== undefined}
                                      <span class="bg-green-200 px-2 py-1 rounded">
                                        Score: {(result.score * 100).toFixed(1)}%
                                      </span>
                                    {/if}
                                    {#if result.page}
                                      <span class="bg-green-200 px-2 py-1 rounded">
                                        Page {result.page}
                                      </span>
                                    {/if}
                                  </div>
                                </div>
                                
                                <!-- Content Preview -->
                                <div class="bg-white border border-green-300 rounded p-2 text-gray-800">
                                  <div class="text-xs text-gray-600 mb-1">Content Preview:</div>
                                  <div class="text-sm leading-relaxed">
                                    {result.content_preview || 'No content preview available'}
                                  </div>
                                </div>
                                
                                <!-- Metadata -->
                                {#if result.search_method}
                                  <div class="mt-1 text-xs text-green-600">
                                    Method: {result.search_method}
                                  </div>
                                {/if}
                              </div>
                            {/each}
                          </div>
                          
                          <!-- Show More Results Hint -->
                          {#if testSearchResults.results_count > testSearchResults.sample_results.length}
                            <div class="mt-2 p-2 bg-green-100 border border-green-200 rounded text-center text-green-700">
                              <i class="fas fa-info-circle mr-1"></i>
                              Showing {testSearchResults.sample_results.length} of {testSearchResults.results_count} total results
                              <div class="text-xs mt-1">
                                The full search will return all {testSearchResults.results_count} results during workflow execution
                              </div>
                            </div>
                          {/if}
                          
                          <!-- Search Parameters Used -->
                          {#if testSearchResults.parameters_used}
                            <div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded">
                              <div class="text-blue-800 font-medium text-xs mb-1">Search Parameters Used:</div>
                              <div class="text-xs text-blue-700">
                                {#each Object.entries(testSearchResults.parameters_used) as [key, value]}
                                  <div class="flex justify-between">
                                    <span class="font-medium">{key.replace(/_/g, ' ')}:</span>
                                    <span>{JSON.stringify(value)}</span>
                                  </div>
                                {/each}
                              </div>
                            </div>
                          {/if}
                        </div>
                      {:else}
                        <div class="p-2 text-green-700">
                          <div class="flex items-center">
                            <i class="fas fa-exclamation-circle mr-2"></i>
                            Search completed successfully but no sample results were returned.
                          </div>
                          <div class="text-xs mt-1">
                            This might indicate that the relevance threshold is too high or no documents match the search query.
                          </div>
                        </div>
                      {/if}
                      
                    {:else}
                      <!-- Error Display -->
                      <div class="p-2">
                        <div class="flex items-center text-red-800">
                          <i class="fas fa-exclamation-triangle mr-2"></i>
                          <strong>Test Failed</strong>
                        </div>
                        <div class="text-red-700 mt-1">
                          {testSearchResults.error || 'Unknown error occurred'}
                        </div>
                        {#if testSearchResults.query}
                          <div class="text-red-600 text-xs mt-1">
                            Query: "{testSearchResults.query}"
                          </div>
                        {/if}
                        {#if testSearchResults.method}
                          <div class="text-red-600 text-xs mt-1">
                            Method: {testSearchResults.method}
                          </div>
                        {/if}
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
            {:else}
              <div class="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-700">
                <i class="fas fa-info-circle mr-1"></i>
                Project ID required for search testing
              </div>
            {/if}
          {/if}
        </div>
      {/if}
    {/if}
    
    <!-- DELEGATE-SPECIFIC FIELDS -->
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
        on:click={saveNodeChanges}
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
  
  :global(.focus\\:border-oxford-blue:focus) {
    border-color: #002147;
  }
  
  :global(.focus\\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  :global(.text-oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
</style>
