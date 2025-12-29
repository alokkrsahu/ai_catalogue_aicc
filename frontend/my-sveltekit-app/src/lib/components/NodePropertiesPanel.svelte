<!-- NodePropertiesPanel.svelte - Enhanced Agent Node Configuration Panel with API Key Based Models -->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { dynamicModelsService, type ModelInfo, type ProviderStatus } from '$lib/services/dynamicModelsService';
  import { docAwareService, type SearchMethod, type SearchMethodParameter } from '$lib/services/docAwareService';
  import type { BulkModelData } from '$lib/stores/llmModelsStore';
  import { 
    getMCPServerCredentials, 
    setMCPServerCredentials, 
    testMCPServerConnection, 
    getMCPServerTools 
  } from '$lib/services/mcpServerService';
  import { 
    generateSystemPrompt, 
    previewGeneratedPrompt,
    type PromptGenerationRequest,
    type PromptGenerationResponse 
  } from '$lib/services/promptGenerationService';
  
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
  
  // 🔧 MCP Server state
  let mcpGoogleDriveCredentials = {
    client_id: '',
    client_secret: '',
    refresh_token: ''
  };
  let mcpSharePointCredentials = {
    tenant_id: '',
    client_id: '',
    client_secret: '',
    site_url: ''
  };
  let mcpCredentialName = '';
  let loadingMCPCredentials = false;
  let savingMCPCredentials = false;
  let testingMCPConnection = false;
  let mcpConnectionTestResult: any = null;
  let mcpAvailableTools: any[] = [];
  let loadingMCPTools = false;
  let mcpCredentialStatus: any = null;
  
  // 🤖 Prompt Generation state
  let generatingPrompt = false;
  let generatedPromptPreview: string | null = null;
  let promptGenerationError: string | null = null;
  let showPromptPreview = false;
  let autoGenerateEnabled = false;
  let descriptionDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  let promptGenerationMetadata: any = null;
  
  // Initialize defaults for new nodes
  function initializeNodeDefaults() {
    // Initialize default LLM configuration if not present
    if (['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
      if (!nodeConfig.llm_provider) {
        // Set defaults based on agent type - will be updated once we check API keys
        if (node.type === 'AssistantAgent') {
          nodeConfig.llm_provider = 'openai';
          nodeConfig.llm_model = 'gpt-4-turbo';
        } else if (node.type === 'DelegateAgent') {
          nodeConfig.llm_provider = 'anthropic';
          nodeConfig.llm_model = 'claude-3-5-haiku-20241022';
        } else if (node.type === 'GroupChatManager') {
          nodeConfig.llm_provider = 'anthropic';
          nodeConfig.llm_model = 'claude-3-5-sonnet-20241022';
        }
        console.log('🤖 LLM CONFIG: Initialized default config for', node.type, nodeConfig.llm_provider, nodeConfig.llm_model);
      }
      
      // Set Group Chat Manager defaults
      if (node.type === 'GroupChatManager') {
        if (!nodeConfig.max_rounds) {
          nodeConfig.max_rounds = 10; // Default for Round Robin, Intelligent will override to 1
        }
        if (!nodeConfig.termination_strategy) {
          nodeConfig.termination_strategy = 'all_delegates_complete';
        }
        if (!nodeConfig.hasOwnProperty('max_subqueries')) {
          nodeConfig.max_subqueries = null; // Default: no limit
        }
      }
    } else if (node.type === 'UserProxyAgent') {
      // UserProxyAgent only gets LLM configuration if DocAware is enabled
      if (nodeConfig.doc_aware && !nodeConfig.llm_provider) {
        nodeConfig.llm_provider = 'openai';
        nodeConfig.llm_model = 'gpt-3.5-turbo';
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
        nodeConfig.query_refinement_enabled = false;
        console.log('📚 RAG CONFIG: Initialized default RAG config for', node.type);
      }
      
      // Initialize query_refinement_enabled if not present (for existing nodes)
      if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type) && !nodeConfig.hasOwnProperty('query_refinement_enabled')) {
        nodeConfig.query_refinement_enabled = false;
      }
      
      // Initialize input_mode for UserProxyAgent (default to 'user' for backward compatibility)
      if (node.type === 'UserProxyAgent' && !nodeConfig.hasOwnProperty('input_mode')) {
        nodeConfig.input_mode = 'user';
        console.log('👤 INPUT MODE: Initialized default input_mode for UserProxyAgent');
      }

      // Initialize content_filters as array if not present
      if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type)) {
        if (!nodeConfig.content_filters || !Array.isArray(nodeConfig.content_filters)) {
          nodeConfig.content_filters = [];
          console.log('📚 CONTENT FILTER: Initialized content_filters as empty array');
        }
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
      console.log('📚 DOCAWARE: Content filters (array):', nodeConfig.content_filters);

      const result = await docAwareService.testSearch(
        projectId,
        selectedSearchMethod.id,
        searchParameters,
        actualQuery,
        nodeConfig.content_filters || []  // Pass array instead of string
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
    
    // CRITICAL FIX: Always update when node changes, regardless of focus state
    // This prevents stale data from previous nodes appearing in the current node's property panel
    if (isDifferentNode) {
      // Force immediate update for different nodes - don't check focus state
      console.log('🔄 NODE SYNC: Different node detected, forcing immediate state update', {
        from: currentNodeId?.slice(-4),
        to: node.id.slice(-4),
        oldName: nodeName,
        newName: currentName
      });
      
      // Clear prompt generation state when node changes
      generatedPromptPreview = null;
      showPromptPreview = false;
      promptGenerationError = null;
      promptGenerationMetadata = null;
      
      // Update current node ID
      currentNodeId = node.id;
      
      // CRITICAL: Force update nodeName and nodeDescription immediately
      // This prevents the previous node's name from appearing in the new node's property panel
      nodeName = currentName;
      nodeDescription = currentDesc;
      nodeConfig = { ...currentConfig }; // Deep clone to prevent reference issues
      
      console.log('✅ NODE SYNC: State forcefully updated for new node', {
        nodeName,
        nodeDescription: nodeDescription.substring(0, 50),
        nodeId: node.id.slice(-4)
      });
    } else if (hasConfigChanged && !document.activeElement?.closest('.node-properties-panel')) {
      // Only update config if data changed and user is not actively editing
      console.log('🔄 NODE SYNC: Same node but data changed, updating state', {
        hasNameChanged: hasNameChanged ? `${nodeName} → ${currentName}` : false,
        hasDescChanged,
        hasConfigChanged,
        nodeId: node.id.slice(-4),
        isUserEditing: !!document.activeElement?.closest('.node-properties-panel')
      });
      
      // Update local state to match the node
      nodeName = currentName;
      nodeDescription = currentDesc;
      nodeConfig = { ...currentConfig }; // Deep clone to prevent reference issues
      
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
  // 🔧 MCP Server Methods
  async function loadMCPCredentials() {
    if (!projectId || !nodeConfig.server_type || loadingMCPCredentials) return;
    
    try {
      loadingMCPCredentials = true;
      const creds = await getMCPServerCredentials(projectId, nodeConfig.server_type);
      
      if (creds) {
        mcpCredentialStatus = creds;
        mcpCredentialName = creds.credential_name || '';
        // Note: We can't decrypt credentials on frontend for security
        // User will need to re-enter them if they want to update
      } else {
        mcpCredentialStatus = null;
        mcpCredentialName = '';
      }
      
      // Load available tools if credentials exist
      if (creds?.is_validated) {
        await loadMCPTools();
      }
    } catch (error: any) {
      console.error('Error loading MCP credentials:', error);
      mcpCredentialStatus = null;
    } finally {
      loadingMCPCredentials = false;
    }
  }
  
  async function loadMCPTools() {
    if (!projectId || !nodeConfig.server_type || loadingMCPTools) return;
    
    try {
      loadingMCPTools = true;
      mcpAvailableTools = await getMCPServerTools(projectId, nodeConfig.server_type);
    } catch (error: any) {
      console.error('Error loading MCP tools:', error);
      mcpAvailableTools = [];
    } finally {
      loadingMCPTools = false;
    }
  }
  
  async function saveMCPCredentials() {
    if (!projectId || !nodeConfig.server_type || savingMCPCredentials) return;
    
    // Validate required fields
    if (nodeConfig.server_type === 'google_drive') {
      if (!mcpGoogleDriveCredentials.client_id || !mcpGoogleDriveCredentials.client_secret || !mcpGoogleDriveCredentials.refresh_token) {
        toasts?.error('Please fill in all required Google Drive credentials');
        return;
      }
    } else if (nodeConfig.server_type === 'sharepoint') {
      if (!mcpSharePointCredentials.tenant_id || !mcpSharePointCredentials.client_id || !mcpSharePointCredentials.client_secret) {
        toasts?.error('Please fill in all required SharePoint credentials');
        return;
      }
      // Store site_url in server_config
      if (!nodeConfig.server_config) nodeConfig.server_config = {};
      nodeConfig.server_config.site_url = mcpSharePointCredentials.site_url;
      updateNodeData();
    }
    
    try {
      savingMCPCredentials = true;
      const credentials = nodeConfig.server_type === 'google_drive' 
        ? mcpGoogleDriveCredentials 
        : mcpSharePointCredentials;
      
      await setMCPServerCredentials(
        projectId,
        nodeConfig.server_type,
        credentials,
        mcpCredentialName,
        nodeConfig.server_config || {}
      );
      
      toasts?.success('MCP server credentials saved successfully');
      await loadMCPCredentials();
      mcpConnectionTestResult = null;
    } catch (error: any) {
      toasts?.error(`Failed to save credentials: ${error.message}`);
    } finally {
      savingMCPCredentials = false;
    }
  }
  
  async function testMCPConnection() {
    if (!projectId || !nodeConfig.server_type || testingMCPConnection) return;
    
    // Save credentials first if not already saved
    if (!mcpCredentialStatus) {
      await saveMCPCredentials();
    }
    
    try {
      testingMCPConnection = true;
      mcpConnectionTestResult = null;
      
      const result = await testMCPServerConnection(projectId, nodeConfig.server_type);
      mcpConnectionTestResult = result;
      
      if (result.success) {
        toasts?.success(`Connection successful! Found ${result.tools_count || 0} tools.`);
        await loadMCPTools();
      } else {
        toasts?.error(`Connection failed: ${result.error || 'Unknown error'}`);
      }
    } catch (error: any) {
      toasts?.error(`Connection test failed: ${error.message}`);
      mcpConnectionTestResult = { success: false, error: error.message };
    } finally {
      testingMCPConnection = false;
    }
  }
  
  function handleServerTypeChange() {
    // Reset credentials when server type changes
    mcpGoogleDriveCredentials = { client_id: '', client_secret: '', refresh_token: '' };
    mcpSharePointCredentials = { tenant_id: '', client_id: '', client_secret: '', site_url: '' };
    mcpCredentialName = '';
    mcpConnectionTestResult = null;
    mcpAvailableTools = [];
    mcpCredentialStatus = null;
    
    // Load credentials for new server type
    if (nodeConfig.server_type) {
      loadMCPCredentials();
    }
    
    updateNodeData();
  }
  
  onMount(async () => {
    // Load MCP credentials if this is an MCPServer node
    if (node.type === 'MCPServer' && projectId && nodeConfig.server_type) {
      await loadMCPCredentials();
    }
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
    
    // Auto-generate Group Chat Manager prompt if delegates are connected
    if (node.type === 'GroupChatManager') {
      // Delay slightly to ensure workflowData is available
      setTimeout(async () => {
        const delegates = findConnectedDelegates();
        if (delegates.length > 0 && (!nodeConfig.system_message || nodeConfig.system_message.trim().length === 0)) {
          console.log('🔧 GROUP CHAT MANAGER: Auto-generating prompt on mount from', delegates.length, 'delegates');
          await autoGenerateGroupChatManagerPrompt();
        }
      }, 500);
    }
  });
  
  // Call update function when node changes
  $: if (node) {
    // Clear prompt generation state when switching to a different node
    if (node.id !== currentNodeId) {
      const previousNodeId = currentNodeId;
      currentNodeId = node.id;
      
      // CRITICAL FIX: Immediately clear and reset all state when switching nodes
      // This prevents name/description/system_message from one node appearing in another node's property panel
      generatedPromptPreview = null;
      showPromptPreview = false;
      promptGenerationError = null;
      promptGenerationMetadata = null;
      
      // Immediately reset nodeName and nodeDescription from the new node's data
      // This ensures the UI reflects the correct node's data, not stale data from the previous node
      const newName = node.data.name || node.data.label || node.type;
      const newDesc = node.data.description || '';
      
      // Force update nodeName and nodeDescription immediately to prevent stale data
      if (nodeName !== newName) {
        nodeName = newName;
        console.log(`🔄 NODE PROPERTIES: Node changed (${previousNodeId?.slice(-4)} → ${node.id.slice(-4)}), reset nodeName: "${nodeName}"`);
      }
      if (nodeDescription !== newDesc) {
        nodeDescription = newDesc;
        console.log(`🔄 NODE PROPERTIES: Node changed, reset nodeDescription`);
      }
      
      // CRITICAL FIX: Immediately reset nodeConfig (including system_message) from the new node's data
      // This prevents system_message and other config values from the previous node appearing in the new node's property panel
      const previousSystemMessage = nodeConfig.system_message;
      nodeConfig = { ...node.data }; // Deep clone to prevent reference issues
      const newSystemMessage = nodeConfig.system_message;
      
      if (previousSystemMessage !== newSystemMessage) {
        console.log(`🔄 NODE PROPERTIES: Node changed, reset system_message from "${previousSystemMessage?.substring(0, 50) || 'empty'}..." to "${newSystemMessage?.substring(0, 50) || 'empty'}..."`);
      }
      
      console.log('🔄 NODE PROPERTIES: Node changed, cleared all state and reset name/description/system_message');
    }
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
      
      // Auto-generate prompt if enabled and agent type supports it
      if (autoGenerateEnabled && ['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
        // Clear existing timer
        if (descriptionDebounceTimer) {
          clearTimeout(descriptionDebounceTimer);
        }
        
        // Debounce auto-generation (2 seconds)
        descriptionDebounceTimer = setTimeout(() => {
          if (nodeDescription.trim().length >= 10) {
            generatePromptFromDescription();
          }
        }, 2000);
      }
    }
  }
  
  // Find connected delegate agents for Group Chat Manager
  function findConnectedDelegates(): Array<{ name: string; description: string }> {
    if (node.type !== 'GroupChatManager' || !workflowData || !workflowData.nodes || !workflowData.edges) {
      return [];
    }
    
    const currentNodeId = node.id;
    const delegates: Array<{ name: string; description: string }> = [];
    
    // Find all edges where this Group Chat Manager is the source and target is a DelegateAgent
    const delegateEdges = workflowData.edges.filter(edge => 
      edge.source === currentNodeId && 
      edge.type === 'delegate'
    );
    
    console.log('🔍 GROUP CHAT MANAGER: Found', delegateEdges.length, 'delegate connections');
    
    for (const edge of delegateEdges) {
      const delegateNode = workflowData.nodes.find(n => n.id === edge.target && n.type === 'DelegateAgent');
      if (delegateNode) {
        const delegateName = delegateNode.data.name || 'Delegate';
        const delegateDescription = delegateNode.data.description || 
                                   delegateNode.data.system_message || 
                                   `${delegateName} is a specialized delegate agent.`;
        
        delegates.push({
          name: delegateName,
          description: delegateDescription
        });
        
        console.log('🔍 GROUP CHAT MANAGER: Found delegate:', delegateName, '-', delegateDescription.substring(0, 50));
      }
    }
    
    return delegates;
  }
  
  // Auto-generate Group Chat Manager prompt from connected delegates
  async function autoGenerateGroupChatManagerPrompt() {
    if (node.type !== 'GroupChatManager') {
      return;
    }
    
    const delegates = findConnectedDelegates();
    
    if (delegates.length === 0) {
      console.log('⚠️ GROUP CHAT MANAGER: No connected delegates found, skipping auto-generation');
      return;
    }
    
    try {
      generatingPrompt = true;
      promptGenerationError = null;
      
      // Build description from delegate capabilities
      const delegateDescriptions = delegates.map(d => 
        `${d.name}: ${d.description}`
      ).join('; ');
      
      // Include Group Chat Manager's own description if available
      const managerDescription = nodeDescription.trim() || node.data.description || '';
      let description = '';
      
      if (managerDescription) {
        description = `Group Chat Manager: ${managerDescription}. This manager coordinates ${delegates.length} specialized delegate agents: ${delegateDescriptions}. The manager should intelligently route tasks to appropriate delegates based on their capabilities and synthesize their responses into comprehensive solutions.`;
      } else {
        description = `Group Chat Manager coordinating ${delegates.length} specialized delegate agents: ${delegateDescriptions}. The manager should intelligently route tasks to appropriate delegates based on their capabilities and synthesize their responses into comprehensive solutions.`;
      }
      
      console.log('🔧 GROUP CHAT MANAGER PROMPT GEN: Auto-generating from', delegates.length, 'delegates');
      console.log('🔧 GROUP CHAT MANAGER PROMPT GEN: Description:', description.substring(0, 100));
      
      const request: PromptGenerationRequest = {
        description: description,
        agent_type: 'GroupChatManager',
        doc_aware: nodeConfig.doc_aware || false,
        project_id: projectId || undefined,
        llm_provider: nodeConfig.llm_provider || 'openai',
        llm_model: nodeConfig.llm_model || 'gpt-4'
      };
      
      const response: PromptGenerationResponse = await generateSystemPrompt(request);
      
      if (response.success && response.generated_prompt) {
        // Auto-apply the generated prompt to system_message
        nodeConfig.system_message = response.generated_prompt;
        updateNodeData();
        
        console.log('✅ GROUP CHAT MANAGER PROMPT GEN: Auto-generated and applied prompt');
        toasts.success(`Auto-generated prompt from ${delegates.length} connected delegate${delegates.length > 1 ? 's' : ''}`);
      } else {
        promptGenerationError = response.error || 'Failed to generate prompt';
        console.error('❌ GROUP CHAT MANAGER PROMPT GEN: Generation failed:', promptGenerationError);
      }
    } catch (error) {
      promptGenerationError = error instanceof Error ? error.message : 'Unknown error';
      console.error('❌ GROUP CHAT MANAGER PROMPT GEN: Exception:', error);
    } finally {
      generatingPrompt = false;
    }
  }
  
  async function generatePromptFromDescription() {
    // Only generate for agents that support system messages
    if (!['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
      return;
    }
    
    if (!nodeDescription || nodeDescription.trim().length < 10) {
      toasts.warning('Please provide a description (at least 10 characters)');
      return;
    }
    
    try {
      generatingPrompt = true;
      promptGenerationError = null;
      generatedPromptPreview = null;
      
      const request: PromptGenerationRequest = {
        description: nodeDescription.trim(),
        agent_type: node.type,
        doc_aware: nodeConfig.doc_aware || false,
        project_id: projectId || undefined,
        llm_provider: nodeConfig.llm_provider || 'openai',
        llm_model: nodeConfig.llm_model || 'gpt-4'
      };
      
      console.log('🔧 PROMPT GEN: Generating prompt for', node.type, 'with description:', nodeDescription.substring(0, 50));
      
      const response: PromptGenerationResponse = await generateSystemPrompt(request);
      
      if (response.success && response.generated_prompt) {
        generatedPromptPreview = response.generated_prompt;
        promptGenerationMetadata = response.metadata;
        showPromptPreview = true;
        toasts.success('Prompt generated successfully!');
        console.log('✅ PROMPT GEN: Generated prompt:', response.generated_prompt.substring(0, 100));
      } else {
        promptGenerationError = response.error || 'Failed to generate prompt';
        toasts.error(promptGenerationError);
        console.error('❌ PROMPT GEN: Generation failed:', promptGenerationError);
      }
    } catch (error) {
      promptGenerationError = error instanceof Error ? error.message : 'Unknown error';
      toasts.error('Failed to generate prompt: ' + promptGenerationError);
      console.error('❌ PROMPT GEN: Exception:', error);
    } finally {
      generatingPrompt = false;
    }
  }
  
  function applyGeneratedPrompt() {
    if (generatedPromptPreview) {
      nodeConfig.system_message = generatedPromptPreview;
      updateNodeData();
      toasts.success('Generated prompt applied to system message');
      showPromptPreview = false;
    }
  }
  
  function dismissPromptPreview() {
    showPromptPreview = false;
    generatedPromptPreview = null;
    promptGenerationError = null;
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
    {#if ['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)}
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-gray-700">
            Description
            {#if node.type === 'DelegateAgent'}
              <i class="fas fa-info-circle ml-1 text-gray-400" title="Describe this delegate's capabilities and expertise. This helps the Group Chat Manager route queries intelligently."></i>
            {/if}
          </label>
          <div class="flex items-center space-x-2">
            <label class="flex items-center space-x-1 text-xs text-gray-600">
              <input
                type="checkbox"
                bind:checked={autoGenerateEnabled}
                class="form-checkbox h-3 w-3 text-oxford-blue rounded"
              />
              <span>Auto-generate</span>
            </label>
            <button
              on:click={generatePromptFromDescription}
              disabled={generatingPrompt || !nodeDescription || nodeDescription.trim().length < 10}
              class="px-3 py-1 text-xs bg-oxford-blue rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center space-x-1"
              style="color: white;"
            >
              {#if generatingPrompt}
                <i class="fas fa-spinner fa-spin" style="color: white;"></i>
                <span style="color: white;">Generating...</span>
              {:else}
                <i class="fas fa-magic" style="color: white;"></i>
                <span style="color: white;">Generate Prompt</span>
              {/if}
            </button>
          </div>
        </div>
        <textarea
          bind:value={nodeDescription}
          on:input={handleDescriptionChange}
          on:blur={handleDescriptionChange}
          rows="2"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all resize-none"
          placeholder={node.type === 'DelegateAgent' 
            ? "Describe this delegate's capabilities and expertise (e.g., 'Financial analyst specializing in quarterly reports and budget analysis')..."
            : "Describe what this agent does (e.g., 'A research assistant that helps users find information in documents')..."}
        ></textarea>
        <p class="text-xs text-gray-500 mt-1">
          {nodeDescription.length}/10,000 characters
          {#if nodeDescription.length < 10 && nodeDescription.length > 0}
            <span class="text-yellow-600"> (minimum 10 characters)</span>
          {/if}
          {#if node.type === 'DelegateAgent'}
            {#if nodeDescription.length >= 100 && nodeDescription.length <= 300}
              <span class="text-green-600 ml-2">
                <i class="fas fa-check-circle"></i> Good length for capability matching
              </span>
            {:else if nodeDescription.length > 0 && nodeDescription.length < 100}
              <span class="text-yellow-600 ml-2">
                <i class="fas fa-exclamation-triangle"></i> Consider adding more detail (100-300 chars recommended)
              </span>
            {/if}
          {/if}
        </p>
        
        <!-- Generated Prompt Preview -->
        {#if showPromptPreview && generatedPromptPreview}
          <div class="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold text-blue-900">Generated Prompt Preview</h4>
              <button
                on:click={dismissPromptPreview}
                class="text-blue-600 hover:text-blue-800 text-xs"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>
            <div class="text-sm text-gray-700 bg-white p-2 rounded border border-blue-100 max-h-48 overflow-y-auto mb-2">
              {generatedPromptPreview}
            </div>
            {#if promptGenerationMetadata}
              <div class="text-xs text-gray-600 mb-2">
                Generated using {promptGenerationMetadata.llm_provider} ({promptGenerationMetadata.llm_model})
                {#if promptGenerationMetadata.fallback_used}
                  <span class="text-yellow-600"> (template fallback)</span>
                {/if}
              </div>
            {/if}
            <div class="flex space-x-2">
              <button
                on:click={applyGeneratedPrompt}
                class="px-3 py-1 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                <i class="fas fa-check mr-1"></i> Apply to System Message
              </button>
              <button
                on:click={generatePromptFromDescription}
                disabled={generatingPrompt}
                class="px-3 py-1 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-300"
              >
                <i class="fas fa-redo mr-1"></i> Regenerate
              </button>
            </div>
          </div>
        {/if}
        
        {#if promptGenerationError}
          <div class="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
            <i class="fas fa-exclamation-circle mr-1"></i>
            {promptGenerationError}
          </div>
        {/if}
      </div>
    {:else}
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
    {/if}
    
    <!-- SYSTEM MESSAGE - For AI Assistant, Delegate, GroupChatManager, and Start Node -->
    {#if node.type === 'AssistantAgent' || node.type === 'DelegateAgent' || node.type === 'GroupChatManager'}
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-gray-700">System Message</label>
          {#if node.type === 'GroupChatManager'}
            <button
              on:click={autoGenerateGroupChatManagerPrompt}
              disabled={generatingPrompt || !workflowData || findConnectedDelegates().length === 0}
              class="px-2 py-1 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center space-x-1"
              title="Auto-generate prompt from connected delegates"
            >
              {#if generatingPrompt}
                <i class="fas fa-spinner fa-spin"></i>
                <span>Generating...</span>
              {:else}
                <i class="fas fa-magic"></i>
                <span>Auto-Generate from Delegates</span>
              {/if}
            </button>
          {/if}
        </div>
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
        {#if node.type === 'GroupChatManager' && findConnectedDelegates().length > 0}
          <p class="text-xs text-gray-500 mt-1">
            <i class="fas fa-info-circle mr-1"></i>
            Connected to {findConnectedDelegates().length} delegate{findConnectedDelegates().length > 1 ? 's' : ''}. 
            Click "Auto-Generate from Delegates" to create a prompt based on their capabilities.
          </p>
        {/if}
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
        <!-- Delegation Mode -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Delegation Mode
            <i class="fas fa-info-circle ml-1 text-gray-400" title="Choose how tasks are delegated to delegate agents"></i>
          </label>
          <select
            bind:value={nodeConfig.delegation_mode}
            on:change={updateNodeData}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            <option value="round_robin">Round Robin (Default)</option>
            <option value="intelligent">Intelligent Delegation</option>
          </select>
          <p class="text-xs text-gray-500 mt-1">
            {#if nodeConfig.delegation_mode === 'intelligent'}
              <i class="fas fa-lightbulb text-yellow-500 mr-1"></i>
              Intelligent mode splits input into subqueries and routes them to delegates based on their capabilities.
            {:else}
              Round robin mode processes all delegates in sequence for each round.
            {/if}
          </p>
        </div>
        
        <!-- Round Robin Configuration (only shown when round_robin mode is selected or default) -->
        {#if !nodeConfig.delegation_mode || nodeConfig.delegation_mode === 'round_robin'}
          <div class="p-3 bg-green-50 border border-green-200 rounded-lg space-y-3">
            <h4 class="text-sm font-semibold text-green-900">Round Robin Settings</h4>
            
            <!-- Max Iterations -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Max Iterations</label>
              <input
                type="number"
                bind:value={nodeConfig.max_iterations}
                on:input={updateNodeData}
                min="1"
                max="20"
                class="w-full px-2 py-1 border border-gray-300 rounded text-xs"
                placeholder="2"
              />
              <p class="text-xs text-gray-500 mt-1">
                Maximum number of iterations each delegate will execute in Round Robin mode. Default: 2
              </p>
            </div>
          </div>
        {/if}
        
        <!-- Intelligent Delegation Configuration (only shown when intelligent mode is selected) -->
        {#if nodeConfig.delegation_mode === 'intelligent'}
          <div class="p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-3">
            <h4 class="text-sm font-semibold text-blue-900">Intelligent Delegation Settings</h4>
            
            <!-- Max Subqueries -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">
                Max Subqueries
                <i class="fas fa-info-circle ml-1 text-gray-400" title="Maximum number of subqueries to generate. Leave empty for no limit."></i>
              </label>
              <input
                type="number"
                min="1"
                max="50"
                bind:value={nodeConfig.max_subqueries}
                on:input={updateNodeData}
                placeholder="No limit"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
              />
              <p class="text-xs text-gray-500 mt-1">
                Limit the number of subqueries generated from the input. Higher priority subqueries are kept when limit is applied. Leave empty for no limit.
              </p>
            </div>
            
            <!-- Confidence Threshold -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">
                Confidence Threshold: {nodeConfig.delegation_confidence_threshold || 0.7}
              </label>
              <input
                type="range"
                bind:value={nodeConfig.delegation_confidence_threshold}
                on:input={updateNodeData}
                min="0"
                max="1"
                step="0.05"
                class="w-full"
              />
              <p class="text-xs text-gray-500 mt-1">
                Minimum confidence score (0.0-1.0) required to assign a subquery to a delegate. Lower values allow more flexible matching.
              </p>
            </div>
            
            <!-- Delegation Timeout -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Delegation Timeout (seconds)</label>
              <input
                type="number"
                bind:value={nodeConfig.delegation_timeout}
                on:input={updateNodeData}
                min="5"
                max="300"
                class="w-full px-2 py-1 border border-gray-300 rounded text-xs"
                placeholder="30"
              />
              <p class="text-xs text-gray-500 mt-1">
                Maximum time to wait for a delegate response before timing out.
              </p>
            </div>
            
            <!-- Max Retries -->
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Max Retries</label>
              <input
                type="number"
                bind:value={nodeConfig.max_delegation_retries}
                on:input={updateNodeData}
                min="0"
                max="10"
                class="w-full px-2 py-1 border border-gray-300 rounded text-xs"
                placeholder="3"
              />
              <p class="text-xs text-gray-500 mt-1">
                Maximum number of retry attempts for failed delegations.
              </p>
            </div>
          </div>
        {/if}
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
        
        <!-- Input Mode Selection -->
        {#if nodeConfig.require_human_input}
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Input Mode</label>
            <div class="space-y-2">
              <label class="flex items-center space-x-2 cursor-pointer">
                <input
                  type="radio"
                  name="input_mode_{node.id}"
                  value="user"
                  checked={nodeConfig.input_mode === 'user' || !nodeConfig.input_mode}
                  on:change={() => {
                    nodeConfig.input_mode = 'user';
                    updateNodeData();
                  }}
                  class="w-4 h-4 text-oxford-blue border-gray-300 focus:ring-oxford-blue"
                />
                <span class="text-sm text-gray-700">User Input</span>
                <span class="text-xs text-gray-500 ml-2">(Collect input from end users in deployment)</span>
              </label>
              <label class="flex items-center space-x-2 cursor-pointer">
                <input
                  type="radio"
                  name="input_mode_{node.id}"
                  value="admin"
                  checked={nodeConfig.input_mode === 'admin'}
                  on:change={() => {
                    nodeConfig.input_mode = 'admin';
                    updateNodeData();
                  }}
                  class="w-4 h-4 text-oxford-blue border-gray-300 focus:ring-oxford-blue"
                />
                <span class="text-sm text-gray-700">Admin Input</span>
                <span class="text-xs text-gray-500 ml-2">(Collect input from admin in admin UI)</span>
              </label>
            </div>
          </div>
        {/if}
        
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
        
        <!-- DOCAWARE CONFIGURATION - Show when DocAware is enabled for UserProxy -->
        <div class="border border-blue-200 rounded-lg p-4 bg-blue-50">
          <div class="flex items-center mb-3">
            <i class="fas fa-book text-blue-600 mr-2"></i>
            <h4 class="font-medium text-blue-900">Document Search Configuration</h4>
          </div>
          
          <!-- Query Refinement Toggle -->
          <div class="mb-4">
            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium text-gray-700">Query Refinement</label>
                <p class="text-xs text-gray-500 mt-1">Use LLM to optimize search queries while preserving all key concepts</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={nodeConfig.query_refinement_enabled || false}
                  on:change={(e) => {
                    nodeConfig.query_refinement_enabled = e.target.checked;
                    updateNodeData();
                  }}
                  class="sr-only peer"
                />
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
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
          
          <!-- Multi-Select Content Filter -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Content Filters (Multi-Select)
              <i class="fas fa-info-circle text-gray-400 ml-1" title="Select multiple folders and/or files to filter DocAware searches"></i>
            </label>

            {#if !hierarchicalPathsLoaded}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading content filter data...</span>
              </div>
            {:else if hierarchicalPaths.length === 0}
              <div class="w-full px-3 py-2 border border-yellow-300 rounded-lg bg-yellow-50">
                <div class="text-yellow-700 text-sm flex items-center">
                  <i class="fas fa-info-circle mr-2"></i>
                  No folders/files available for filtering. Upload and process documents first.
                </div>
              </div>
            {:else}
              <!-- Selected filters display (chips/tags) -->
              {#if nodeConfig.content_filters && nodeConfig.content_filters.length > 0}
                <div class="flex flex-wrap gap-2 mb-2 p-2 bg-gray-50 border border-gray-200 rounded-lg">
                  {#each nodeConfig.content_filters as filterId}
                    {@const item = hierarchicalPaths.find(p => p.id === filterId)}
                    {#if item}
                      <div class="flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-md text-xs">
                        <i class="fas fa-{item.type === 'folder' ? 'folder' : 'file'} text-blue-600"></i>
                        <span>{item.displayName}</span>
                        <button
                          type="button"
                          on:click={() => {
                            if (nodeConfig.content_filters && Array.isArray(nodeConfig.content_filters)) {
                              nodeConfig.content_filters = nodeConfig.content_filters.filter(id => id !== filterId);
                              updateNodeData();
                            }
                          }}
                          class="ml-1 text-blue-600 hover:text-blue-800 focus:outline-none"
                          title="Remove filter"
                        >
                          <i class="fas fa-times"></i>
                        </button>
                      </div>
                    {/if}
                  {/each}
                </div>
              {/if}

              <!-- Dropdown to add more filters -->
              <select
                on:change={(e) => {
                  const selectedValue = e.target.value;
                  // Initialize content_filters if undefined
                  if (!nodeConfig.content_filters) {
                    nodeConfig.content_filters = [];
                  }
                  if (selectedValue && !nodeConfig.content_filters.includes(selectedValue)) {
                    nodeConfig.content_filters = [...nodeConfig.content_filters, selectedValue];
                    updateNodeData();
                  }
                  // Reset dropdown
                  e.target.value = '';
                }}
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-600 focus:ring-2 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
              >
                <option value="">Add folder or file filter...</option>
                <optgroup label="Folders">
                  {#each hierarchicalPaths.filter(p => p.type === 'folder') as folder}
                    <option value={folder.id} disabled={nodeConfig.content_filters && nodeConfig.content_filters.includes(folder.id)}>
                      📁 {folder.displayName}
                    </option>
                  {/each}
                </optgroup>
                <optgroup label="Files">
                  {#each hierarchicalPaths.filter(p => p.type === 'file') as file}
                    <option value={file.id} disabled={nodeConfig.content_filters && nodeConfig.content_filters.includes(file.id)}>
                      📄 {file.displayName}
                    </option>
                  {/each}
                </optgroup>
              </select>
            {/if}

            <!-- Content Filter Description -->
            {#if nodeConfig.content_filters && nodeConfig.content_filters.length > 0}
              <div class="mt-2 p-2 bg-green-100 rounded text-xs text-green-700">
                <div class="flex items-center mb-1">
                  <i class="fas fa-filter mr-1"></i>
                  <strong>Active Filters ({nodeConfig.content_filters.length}):</strong>
                </div>
                <div class="mt-1">
                  DocAware will only search documents in the selected {nodeConfig.content_filters.length === 1 ? 'location' : 'locations'}.
                </div>
                <div class="text-xs text-green-600 mt-1">
                  Multiple filters use OR logic - results from ANY selected location will be returned.
                </div>
              </div>
            {:else}
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
          
          <!-- Query Refinement Toggle -->
          <div class="mb-4">
            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium text-gray-700">Query Refinement</label>
                <p class="text-xs text-gray-500 mt-1">Use LLM to optimize search queries while preserving all key concepts</p>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={nodeConfig.query_refinement_enabled || false}
                  on:change={(e) => {
                    nodeConfig.query_refinement_enabled = e.target.checked;
                    updateNodeData();
                  }}
                  class="sr-only peer"
                />
                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
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
          
          <!-- Multi-Select Content Filter -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Content Filters (Multi-Select)
              <i class="fas fa-info-circle text-gray-400 ml-1" title="Select multiple folders and/or files to filter DocAware searches"></i>
            </label>

            {#if !hierarchicalPathsLoaded}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading content filter data...</span>
              </div>
            {:else if hierarchicalPaths.length === 0}
              <div class="w-full px-3 py-2 border border-yellow-300 rounded-lg bg-yellow-50">
                <div class="text-yellow-700 text-sm flex items-center">
                  <i class="fas fa-info-circle mr-2"></i>
                  No folders/files available for filtering. Upload and process documents first.
                </div>
              </div>
            {:else}
              <!-- Selected filters display (chips/tags) -->
              {#if nodeConfig.content_filters && nodeConfig.content_filters.length > 0}
                <div class="flex flex-wrap gap-2 mb-2 p-2 bg-gray-50 border border-gray-200 rounded-lg">
                  {#each nodeConfig.content_filters as filterId}
                    {@const item = hierarchicalPaths.find(p => p.id === filterId)}
                    {#if item}
                      <div class="flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-md text-xs">
                        <i class="fas fa-{item.type === 'folder' ? 'folder' : 'file'} text-blue-600"></i>
                        <span>{item.displayName}</span>
                        <button
                          type="button"
                          on:click={() => {
                            if (nodeConfig.content_filters && Array.isArray(nodeConfig.content_filters)) {
                              nodeConfig.content_filters = nodeConfig.content_filters.filter(id => id !== filterId);
                              updateNodeData();
                            }
                          }}
                          class="ml-1 text-blue-600 hover:text-blue-800 focus:outline-none"
                          title="Remove filter"
                        >
                          <i class="fas fa-times"></i>
                        </button>
                      </div>
                    {/if}
                  {/each}
                </div>
              {/if}

              <!-- Dropdown to add more filters -->
              <select
                on:change={(e) => {
                  const selectedValue = e.target.value;
                  // Initialize content_filters if undefined
                  if (!nodeConfig.content_filters) {
                    nodeConfig.content_filters = [];
                  }
                  if (selectedValue && !nodeConfig.content_filters.includes(selectedValue)) {
                    nodeConfig.content_filters = [...nodeConfig.content_filters, selectedValue];
                    updateNodeData();
                  }
                  // Reset dropdown
                  e.target.value = '';
                }}
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-600 focus:ring-2 focus:ring-blue-600 focus:ring-opacity-20 bg-white"
              >
                <option value="">Add folder or file filter...</option>
                <optgroup label="Folders">
                  {#each hierarchicalPaths.filter(p => p.type === 'folder') as folder}
                    <option value={folder.id} disabled={nodeConfig.content_filters && nodeConfig.content_filters.includes(folder.id)}>
                      📁 {folder.displayName}
                    </option>
                  {/each}
                </optgroup>
                <optgroup label="Files">
                  {#each hierarchicalPaths.filter(p => p.type === 'file') as file}
                    <option value={file.id} disabled={nodeConfig.content_filters && nodeConfig.content_filters.includes(file.id)}>
                      📄 {file.displayName}
                    </option>
                  {/each}
                </optgroup>
              </select>
            {/if}

            <!-- Content Filter Description -->
            {#if nodeConfig.content_filters && nodeConfig.content_filters.length > 0}
              <div class="mt-2 p-2 bg-green-100 rounded text-xs text-green-700">
                <div class="flex items-center mb-1">
                  <i class="fas fa-filter mr-1"></i>
                  <strong>Active Filters ({nodeConfig.content_filters.length}):</strong>
                </div>
                <div class="mt-1">
                  DocAware will only search documents in the selected {nodeConfig.content_filters.length === 1 ? 'location' : 'locations'}.
                </div>
                <div class="text-xs text-green-600 mt-1">
                  Multiple filters use OR logic - results from ANY selected location will be returned.
                </div>
              </div>
            {:else}
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
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Termination Condition</label>
        <input
          type="text"
          bind:value={nodeConfig.termination_condition}
          on:input={updateNodeData}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
          placeholder="FINISH"
        />
        <p class="text-xs text-gray-600 mt-1">Note: Max iterations are controlled by the Group Chat Manager's Max Rounds setting</p>
      </div>
    {/if}
    
    <!-- MCP SERVER CONFIGURATION -->
    {#if node.type === 'MCPServer'}
      <div class="space-y-4 border-t border-gray-200 pt-4 mt-4">
        <h3 class="text-sm font-semibold text-gray-800">MCP Server Configuration</h3>
        
        <!-- Server Type Selection -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Server Type</label>
          <select
            bind:value={nodeConfig.server_type}
            on:change={handleServerTypeChange}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            <option value="google_drive">Google Drive</option>
            <option value="sharepoint">SharePoint</option>
          </select>
          <p class="text-xs text-gray-500 mt-1">Select the MCP server type to connect to</p>
        </div>
        
        <!-- Credential Status -->
        {#if mcpCredentialStatus}
          <div class="bg-green-50 border border-green-200 rounded-lg p-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center">
                <i class="fas fa-check-circle text-green-600 mr-2"></i>
                <div>
                  <p class="text-sm text-green-800 font-medium">Credentials Configured</p>
                  <p class="text-xs text-green-700">
                    {mcpCredentialStatus.is_validated ? 'Validated' : 'Not validated'}
                    {#if mcpCredentialName}
                      - {mcpCredentialName}
                    {/if}
                  </p>
                </div>
              </div>
            </div>
          </div>
        {/if}
        
        <!-- Credential Name -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Credential Name (Optional)</label>
          <input
            type="text"
            bind:value={mcpCredentialName}
            placeholder="e.g., Production Credentials"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
          />
        </div>
        
        <!-- Google Drive Credentials -->
        {#if nodeConfig.server_type === 'google_drive'}
          <div class="space-y-3 border border-gray-200 rounded-lg p-4 bg-gray-50">
            <h4 class="text-sm font-semibold text-gray-800 mb-3">Google Drive Credentials</h4>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">OAuth Client ID</label>
              <input
                type="text"
                bind:value={mcpGoogleDriveCredentials.client_id}
                placeholder="Enter Google OAuth Client ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">OAuth Client Secret</label>
              <input
                type="password"
                bind:value={mcpGoogleDriveCredentials.client_secret}
                placeholder="Enter Google OAuth Client Secret"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Refresh Token</label>
              <input
                type="password"
                bind:value={mcpGoogleDriveCredentials.refresh_token}
                placeholder="Enter OAuth Refresh Token"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">
                Obtain these from Google Cloud Console after setting up OAuth 2.0 credentials
              </p>
            </div>
          </div>
        {/if}
        
        <!-- SharePoint Credentials -->
        {#if nodeConfig.server_type === 'sharepoint'}
          <div class="space-y-3 border border-gray-200 rounded-lg p-4 bg-gray-50">
            <h4 class="text-sm font-semibold text-gray-800 mb-3">SharePoint Credentials</h4>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Tenant ID</label>
              <input
                type="text"
                bind:value={mcpSharePointCredentials.tenant_id}
                placeholder="Enter Azure AD Tenant ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Client ID (Application ID)</label>
              <input
                type="text"
                bind:value={mcpSharePointCredentials.client_id}
                placeholder="Enter Azure AD Application (Client) ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Client Secret</label>
              <input
                type="password"
                bind:value={mcpSharePointCredentials.client_secret}
                placeholder="Enter Azure AD Client Secret"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">SharePoint Site URL</label>
              <input
                type="text"
                bind:value={mcpSharePointCredentials.site_url}
                placeholder="https://contoso.sharepoint.com/sites/MySite"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">
                Full URL of the SharePoint site you want to access
              </p>
            </div>
          </div>
        {/if}
        
        <!-- Security Notice -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div class="flex items-start">
            <i class="fas fa-shield-alt text-blue-600 mt-0.5 mr-2"></i>
            <div class="text-sm text-blue-800">
              <p class="font-medium mb-1">Secure Storage</p>
              <p class="text-xs">
                All credentials are encrypted using project-specific keys and stored securely. 
                Credentials are isolated per project and cannot be accessed by other users.
              </p>
            </div>
          </div>
        </div>
        
        <!-- Connection Test Result -->
        {#if mcpConnectionTestResult}
          <div class="p-3 rounded-lg {mcpConnectionTestResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}">
            <div class="flex items-center">
              <i class="fas {mcpConnectionTestResult.success ? 'fa-check-circle' : 'fa-times-circle'} text-{mcpConnectionTestResult.success ? 'green' : 'red'}-600 mr-2"></i>
              <div>
                <p class="font-medium text-{mcpConnectionTestResult.success ? 'green' : 'red'}-800 text-sm">
                  {mcpConnectionTestResult.success ? 'Connection Successful' : 'Connection Failed'}
                </p>
                {#if mcpConnectionTestResult.success}
                  <p class="text-xs text-green-700 mt-1">
                    Found {mcpConnectionTestResult.tools_count || 0} available tools
                  </p>
                {:else}
                  <p class="text-xs text-red-700 mt-1">
                    {mcpConnectionTestResult.error || 'Unknown error'}
                  </p>
                {/if}
              </div>
            </div>
          </div>
        {/if}
        
        <!-- Credential Actions -->
        <div class="flex space-x-2">
          <button
            type="button"
            on:click={saveMCPCredentials}
            disabled={savingMCPCredentials}
            class="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            {#if savingMCPCredentials}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Saving...
            {:else}
              <i class="fas fa-save mr-2"></i>
              Save Credentials
            {/if}
          </button>
          
          <button
            type="button"
            on:click={testMCPConnection}
            disabled={testingMCPConnection || savingMCPCredentials}
            class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            {#if testingMCPConnection}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Testing...
            {:else}
              <i class="fas fa-plug mr-2"></i>
              Test Connection
            {/if}
          </button>
        </div>
        
        <!-- Server Configuration (for SharePoint site URL, etc.) -->
        {#if nodeConfig.server_type === 'sharepoint'}
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">SharePoint Site URL</label>
            <input
              type="text"
              bind:value={nodeConfig.server_config.site_url}
              on:input={updateNodeData}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              placeholder="https://contoso.sharepoint.com/sites/MySite"
            />
            <p class="text-xs text-gray-500 mt-1">Full URL of the SharePoint site</p>
          </div>
        {/if}
        
        <!-- Available Tools -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Available Tools</label>
          {#if loadingMCPTools}
            <div class="text-xs text-gray-500 italic">
              <i class="fas fa-spinner fa-spin mr-1"></i>
              Loading tools...
            </div>
          {:else if mcpAvailableTools.length > 0}
            <div class="max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-2 space-y-2">
              {#each mcpAvailableTools as tool}
                <div class="bg-white border border-gray-200 rounded p-2">
                  <div class="flex items-center justify-between">
                    <div class="flex-1">
                      <p class="text-sm font-medium text-gray-800">{tool.name}</p>
                      <p class="text-xs text-gray-600 mt-1">{tool.description}</p>
                    </div>
                    <label class="flex items-center ml-2">
                      <input
                        type="checkbox"
                        checked={nodeConfig.selected_tools?.includes(tool.name) || false}
                        on:change={(e) => {
                          if (!nodeConfig.selected_tools) nodeConfig.selected_tools = [];
                          if (e.target.checked) {
                            if (!nodeConfig.selected_tools.includes(tool.name)) {
                              nodeConfig.selected_tools = [...nodeConfig.selected_tools, tool.name];
                            }
                          } else {
                            nodeConfig.selected_tools = nodeConfig.selected_tools.filter(t => t !== tool.name);
                          }
                          updateNodeData();
                        }}
                        class="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-600"
                      />
                    </label>
                  </div>
                </div>
              {/each}
            </div>
            <p class="text-xs text-gray-500 mt-2">
              Check the tools you want this node to expose (leave all unchecked to expose all tools)
            </p>
          {:else if mcpCredentialStatus?.is_validated}
            <div class="text-xs text-gray-500 italic">
              No tools available. Try testing the connection again.
            </div>
          {:else}
            <div class="text-xs text-gray-500 italic">
              Tools will be loaded after credentials are configured and connection is tested
            </div>
          {/if}
        </div>
        
        <!-- Selected Tools Summary -->
        {#if nodeConfig.selected_tools && nodeConfig.selected_tools.length > 0}
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Selected Tools ({nodeConfig.selected_tools.length})</label>
            <div class="flex flex-wrap gap-2">
              {#each nodeConfig.selected_tools as tool}
                <span class="inline-flex items-center px-2 py-1 rounded-full text-xs bg-purple-100 text-purple-800">
                  {tool}
                  <button
                    type="button"
                    on:click={() => {
                      nodeConfig.selected_tools = nodeConfig.selected_tools.filter(t => t !== tool);
                      updateNodeData();
                    }}
                    class="ml-1 text-purple-600 hover:text-purple-800"
                  >
                    <i class="fas fa-times"></i>
                  </button>
                </span>
              {/each}
            </div>
          </div>
        {/if}
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

