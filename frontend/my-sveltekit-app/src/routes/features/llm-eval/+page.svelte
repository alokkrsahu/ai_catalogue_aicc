<!-- src/routes/features/llm-eval/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { user } from '$lib/stores/auth';
  import { toasts } from '$lib/stores/toast';
  import { 
    getAvailableLLMProviders, 
    createLLMComparison, 
    getLLMComparisons,
    getProviderModels,
    deleteLLMComparison
  } from '$lib/services/llm-api';
  import type { LLMProvider, LLMComparison, LLMResponse, ProviderConfig, LLMModel } from '$lib/types';
  
  interface ProviderWithModels extends LLMProvider {
    models: LLMModel[];
    selectedModels: string[]; // Changed from selectedModel to selectedModels array
    modelsLoading: boolean;
    modelsError: string;
    isEnabled: boolean;
  }
  
  let providers: ProviderWithModels[] = [];
  let prompt = '';
  let title = '';
  let temperature = 0.7;
  let loading = false;
  let providersLoading = true;
  let currentComparison: LLMComparison | null = null;
  let recentComparisons: LLMComparison[] = [];
  let currentPage = 0;
  let modelsPerPage = 2; // Show 2 models side by side
  
  // Pagination calculations
  $: totalPages = currentComparison?.responses ? Math.ceil(currentComparison.responses.length / modelsPerPage) : 0;
  $: paginatedResponses = currentComparison?.responses ? 
    currentComparison.responses.slice(currentPage * modelsPerPage, (currentPage + 1) * modelsPerPage) : [];
  
  function nextPage() {
    if (currentPage < totalPages - 1) {
      currentPage++;
    }
  }
  
  function prevPage() {
    if (currentPage > 0) {
      currentPage--;
    }
  }
  
  function goToPage(page: number) {
    if (page >= 0 && page < totalPages) {
      currentPage = page;
    }
  }
  
  // Reset pagination when new comparison loads
  $: if (currentComparison) {
    currentPage = 0;
  }
  
  let showHistory = false;
  let selectedComparisons: number[] = []; // Track selected comparison IDs for deletion
  let isSelectAllChecked = false;
  let showDeleteConfirmation = false;
  let deletingComparisons = false;
  
  // LLM as a Judge functionality
  let judgeEnabled = false;
  let selectedJudgeProvider: ProviderWithModels | null = null;
  let selectedJudgeModel = '';
  let judgeAnalysis: string | null = null;
  let judgeLoading = false;
  let judgeError = '';
  let modelsLoadedForJudge = false; // Track if we've loaded models for judge selection
  
  // Load models for all providers when judge analysis is enabled
  async function loadModelsForJudgeSelection() {
    if (modelsLoadedForJudge) return; // Already loaded
    
    console.log('🚀 Loading models for all providers for judge selection...');
    
    // Load models for all providers that don't have models loaded yet
    const providersToLoad = providers.filter((p, i) => p.models.length === 0 && !p.modelsLoading);
    
    if (providersToLoad.length === 0) {
      modelsLoadedForJudge = true;
      return;
    }
    
    console.log(`🚀 Found ${providersToLoad.length} providers that need models loaded`);
    
    for (let i = 0; i < providers.length; i++) {
      if (providers[i].models.length === 0 && !providers[i].modelsLoading) {
        console.log(`🚀 Loading models for ${providers[i].name}...`);
        await loadModelsForProvider(i);
      }
    }
    
    modelsLoadedForJudge = true;
    console.log('✅ Finished loading models for judge selection');
    
    // Force reactivity update
    providers = [...providers];
  }
  
  // Reactive calculation for select all state
  $: {
    if (recentComparisons.length > 0) {
      isSelectAllChecked = selectedComparisons.length === recentComparisons.length;
    } else {
      isSelectAllChecked = false;
    }
  }
  
  // Reactive statement to load models when judge is enabled
  $: if (judgeEnabled && !modelsLoadedForJudge) {
    loadModelsForJudgeSelection();
  }
  
  function toggleSelectAll() {
    if (isSelectAllChecked) {
      selectedComparisons = [];
    } else {
      selectedComparisons = recentComparisons.map(c => c.id);
    }
  }
  
  function toggleComparisonSelection(comparisonId: number) {
    if (selectedComparisons.includes(comparisonId)) {
      selectedComparisons = selectedComparisons.filter(id => id !== comparisonId);
    } else {
      selectedComparisons = [...selectedComparisons, comparisonId];
    }
  }
  
  async function deleteSelectedComparisons() {
    if (selectedComparisons.length === 0) return;
    
    deletingComparisons = true;
    let successCount = 0;
    let errorCount = 0;
    
    try {
      // Delete each comparison individually
      for (const comparisonId of selectedComparisons) {
        try {
          await deleteLLMComparison(comparisonId.toString());
          successCount++;
        } catch (error) {
          console.error(`Failed to delete comparison ${comparisonId}:`, error);
          errorCount++;
        }
      }
      
      // Show results
      if (successCount > 0) {
        toasts.success(`Deleted ${successCount} comparison${successCount > 1 ? 's' : ''} successfully`);
      }
      if (errorCount > 0) {
        toasts.error(`Failed to delete ${errorCount} comparison${errorCount > 1 ? 's' : ''}`);
      }
      
      // Reset selections and reload
      selectedComparisons = [];
      showDeleteConfirmation = false;
      await loadRecentComparisons();
      
    } catch (error) {
      console.error('Error during bulk deletion:', error);
      toasts.error('An error occurred while deleting comparisons');
    } finally {
      deletingComparisons = false;
    }
  }
  
  // LLM as a Judge functions
  function selectJudgeProvider(provider: ProviderWithModels) {
    console.log('🎯 Selecting judge provider:', provider);
    selectedJudgeProvider = provider;
    // Auto-select first model if available
    if (provider.models.length > 0) {
      selectedJudgeModel = provider.models[0].id || provider.models[0].name || '';
      console.log('🎯 Auto-selected judge model:', selectedJudgeModel);
    } else {
      selectedJudgeModel = '';
      console.log('🎯 No models available for judge provider');
    }
  }
  
  // New improved judge model selection functions
  function getAllAvailableModels() {
    const availableModels = [];
    
    // Get models from ALL providers that have loaded models, regardless of enabled status
    providers.forEach(provider => {
      if (provider.models && provider.models.length > 0) {
        provider.models.forEach(model => {
          availableModels.push({
            providerId: provider.id,
            providerName: provider.name,
            providerType: provider.provider_type,
            modelId: model.id || model.name,
            modelName: getModelDisplayName(model),
            fullDisplayName: `${provider.name} - ${getModelDisplayName(model)}`
          });
        });
      }
    });
    
    console.log('🔎 Available models for judge:', availableModels.length, availableModels.map(m => m.fullDisplayName));
    
    // Sort by provider name first, then by model name
    return availableModels.sort((a, b) => {
      if (a.providerName !== b.providerName) {
        return a.providerName.localeCompare(b.providerName);
      }
      return a.modelName.localeCompare(b.modelName);
    });
  }
  
  // Group models by provider for better dropdown organization
  function getGroupedModels() {
    const models = getAllAvailableModels();
    const grouped = {};
    
    models.forEach(model => {
      if (!grouped[model.providerName]) {
        grouped[model.providerName] = [];
      }
      grouped[model.providerName].push(model);
    });
    
    return grouped;
  }
  
  function handleJudgeModelChange() {
    console.log('🎯 Judge model selection changed to:', selectedJudgeModel);
    
    if (selectedJudgeModel) {
      const [providerId, modelId] = selectedJudgeModel.split(':');
      const provider = providers.find(p => p.id.toString() === providerId);
      
      if (provider) {
        selectedJudgeProvider = provider;
        console.log('🎯 Updated judge provider to:', provider.name);
        console.log('🎯 Updated judge model to:', modelId);
      } else {
        console.error('🎯 Could not find provider with ID:', providerId);
        selectedJudgeProvider = null;
      }
    } else {
      selectedJudgeProvider = null;
      console.log('🎯 Cleared judge selection');
    }
  }
  
  function getSelectedJudgeInfo() {
    if (!selectedJudgeModel || !selectedJudgeProvider) {
      return null;
    }
    
    const [providerId, modelId] = selectedJudgeModel.split(':');
    const model = selectedJudgeProvider.models.find(m => (m.id || m.name) === modelId);
    
    return {
      providerId: selectedJudgeProvider.id,
      providerName: selectedJudgeProvider.name,
      providerType: selectedJudgeProvider.provider_type,
      modelId: modelId,
      modelName: model ? getModelDisplayName(model) : modelId
    };
  }
  
  async function runJudgeAnalysis() {
    console.log('🕰️ Starting judge analysis...');
    console.log('- Current comparison:', currentComparison ? `${currentComparison.id} with ${currentComparison.responses?.length || 0} responses` : 'null');
    console.log('- Selected judge provider:', selectedJudgeProvider ? `${selectedJudgeProvider.name} (ID: ${selectedJudgeProvider.id})` : 'null');
    console.log('- Selected judge model:', selectedJudgeModel || 'empty');
    console.log('- Available providers with models:', providers.filter(p => p.models.length > 0).map(p => `${p.name} (${p.models.length} models)`));
    
    if (!currentComparison || !selectedJudgeProvider || !selectedJudgeModel) {
      toasts.error('Please select a judge model and ensure you have comparison results');
      return;
    }
    
    judgeLoading = true;
    judgeError = '';
    judgeAnalysis = null;
    
    try {
      // Create a comprehensive prompt for the judge
      const judgePrompt = createJudgePrompt(currentComparison);
      
      console.log('🏛️ Creating judge analysis request...');
      console.log('📝 Judge prompt length:', judgePrompt.length);
      console.log('🤖 Judge provider:', selectedJudgeProvider.name);
      console.log('🧠 Judge model:', selectedJudgeModel);
      console.log('🔢 Judge provider ID:', selectedJudgeProvider.id);
      
      // Validate model selection
      if (!selectedJudgeModel || selectedJudgeModel === '') {
        console.error('❌ No judge model selected');
        judgeError = 'Please select a judge model';
        toasts.error('Configuration error: ' + judgeError);
        return;
      }
      
      const [providerId, modelId] = selectedJudgeModel.split(':');
      
      // Validate provider ID is a number
      const providerIdNum = parseInt(providerId);
      if (isNaN(providerIdNum)) {
        console.error('❌ Invalid provider ID:', providerId);
        judgeError = 'Invalid provider ID - must be a number';
        toasts.error('Configuration error: ' + judgeError);
        return;
      }
      
      // Validate model name is not empty
      if (!modelId || modelId.trim() === '') {
        console.error('❌ Invalid model name:', modelId);
        judgeError = 'Invalid model name - cannot be empty';
        toasts.error('Configuration error: ' + judgeError);
        return;
      }
      
      const requestPayload = {
        prompt: judgePrompt,
        title: `Judge Analysis: ${currentComparison.title || 'Untitled'}`,
        provider_configs: [{
          provider_id: providerIdNum,
          model_name: modelId.trim()
        }],
        temperature: 0.3 // Lower temperature for more consistent judging
      };
      
      console.log('📦 Request payload validation:');
      console.log('- Prompt length:', requestPayload.prompt.length);
      console.log('- Title:', requestPayload.title);
      console.log('- Provider configs:', requestPayload.provider_configs);
      console.log('- Temperature:', requestPayload.temperature);
      
      // Validate payload before sending
      if (!requestPayload.prompt || requestPayload.prompt.length === 0) {
        judgeError = 'Judge prompt is empty';
        toasts.error('Error: ' + judgeError);
        return;
      }
      
      if (requestPayload.prompt.length > 9500) {
        judgeError = `Judge prompt is too long (${requestPayload.prompt.length} chars, max 9500)`;
        toasts.error('Error: ' + judgeError);
        return;
      }
      
      const judgeRequest = await createLLMComparison(requestPayload);
      
      console.log('⚖️ Judge request response:', judgeRequest);
      
      if (judgeRequest.success && judgeRequest.comparison && judgeRequest.comparison.responses && judgeRequest.comparison.responses.length > 0) {
        const judgeResponse = judgeRequest.comparison.responses[0];
        console.log('📋 Judge response:', judgeResponse);
        
        if (judgeResponse.error_message) {
          judgeError = judgeResponse.error_message;
          toasts.error('Judge analysis failed: ' + judgeResponse.error_message);
        } else if (judgeResponse.response_text) {
          judgeAnalysis = judgeResponse.response_text;
          toasts.success('Judge analysis completed successfully!');
          console.log('✅ Judge analysis successful!');
        } else {
          judgeError = 'No response text received from judge';
          toasts.error('Judge analysis completed but no text was received');
        }
      } else {
        judgeError = judgeRequest.error || 'Failed to get judge analysis';
        toasts.error('Failed to get judge analysis: ' + judgeError);
        console.log('❌ Judge request failed:', judgeRequest);
      }
      
    } catch (error) {
      console.error('❌ Judge analysis error:', error);
      console.error('🔍 Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        statusText: error.response?.statusText,
        config: error.config ? {
          url: error.config.url,
          method: error.config.method,
          data: typeof error.config.data === 'string' ? 
            error.config.data.substring(0, 500) + '...' : 
            JSON.stringify(error.config.data).substring(0, 500) + '...'
        } : null
      });
      
      // Extract more detailed error information
      let errorMessage = 'An error occurred during judge analysis';
      
      if (error.response?.data) {
        if (typeof error.response.data === 'string') {
          errorMessage = error.response.data;
        } else if (error.response.data.error) {
          errorMessage = error.response.data.error;
        } else if (error.response.data.details) {
          errorMessage = JSON.stringify(error.response.data.details);
        } else {
          errorMessage = JSON.stringify(error.response.data);
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      judgeError = errorMessage;
      toasts.error('Judge analysis failed: ' + errorMessage);
    } finally {
      judgeLoading = false;
    }
  }
  
  function createJudgePrompt(comparison: LLMComparison): string {
    console.log('📝 Creating judge prompt for comparison:', comparison.id);
    console.log('📋 Number of responses to judge:', comparison.responses.length);
    
    let prompt = `You are an expert AI model evaluator. Please analyze the following responses to determine which is the best and provide detailed reasoning.\n\n`;
    
    prompt += `**Original Prompt:**\n${comparison.prompt}\n\n`;
    
    prompt += `**Model Responses to Evaluate:**\n\n`;
    
    comparison.responses.forEach((response, index) => {
      console.log(`🤖 Processing response ${index + 1}: ${response.provider_name} - ${response.model_name}`);
      prompt += `**Response ${index + 1} - ${response.provider_name} (${response.model_name}):**\n`;
      if (response.error_message) {
        prompt += `[ERROR: ${response.error_message}]\n`;
        console.log(`⚠️ Response ${index + 1} has error: ${response.error_message}`);
      } else {
        // Truncate very long responses to prevent prompt from becoming too large
        let responseText = response.response_text;
        if (responseText.length > 1500) {
          responseText = responseText.substring(0, 1500) + '\n\n[Response truncated for analysis...]';
          console.log(`✂️ Response ${index + 1} truncated from ${response.response_text.length} to ${responseText.length} characters`);
        }
        prompt += `${responseText}\n`;
        console.log(`✅ Response ${index + 1} text length: ${responseText.length}`);
      }
      prompt += `\n---\n\n`;
    });
    
    prompt += `**Evaluation Criteria:**\nPlease evaluate each response based on:\n`;
    prompt += `1. **Accuracy & Correctness**: How factually accurate and correct is the information?\n`;
    prompt += `2. **Relevance & Focus**: How well does it address the original prompt?\n`;
    prompt += `3. **Clarity & Structure**: How clear, well-organized, and easy to understand is the response?\n`;
    prompt += `4. **Completeness**: How thoroughly does it answer the question?\n`;
    prompt += `5. **Usefulness**: How helpful would this be to the person asking?\n\n`;
    
    prompt += `**Please provide your analysis in the following format:**\n\n`;
    prompt += `## 🏆 Best Response\n**Winner: [Provider Name - Model Name]**\n\n`;
    prompt += `## 📊 Detailed Analysis\n`;
    prompt += `**Winner Strengths:**\n- [Key strengths of the winning response]\n\n`;
    prompt += `**Comparison with Other Responses:**\n- [Brief comparison with other responses]\n\n`;
    prompt += `**Overall Reasoning:**\n[Detailed explanation of why this response is the best]\n\n`;
    prompt += `## 📈 Scores (1-10 scale)\n`;
    comparison.responses.forEach((response, index) => {
      prompt += `**${response.provider_name} (${response.model_name}):** [Score]/10 - [Brief reason]\n`;
    });
    
    console.log('✅ Judge prompt created, total length:', prompt.length);
    
    // If prompt is too long, truncate further
    if (prompt.length > 9000) {
      console.warn('⚠️ Judge prompt is too long:', prompt.length, 'characters, truncating...');
      
      // Create a shorter version
      let shortPrompt = `You are an expert AI model evaluator. Please analyze the following responses and determine which is the best.\n\n`;
      shortPrompt += `**Original Prompt:**\n${comparison.prompt}\n\n`;
      shortPrompt += `**Model Responses:**\n\n`;
      
      comparison.responses.forEach((response, index) => {
        shortPrompt += `**Response ${index + 1} - ${response.provider_name} (${response.model_name}):**\n`;
        if (response.error_message) {
          shortPrompt += `[ERROR: ${response.error_message}]\n`;
        } else {
          // Further truncate for short prompt
          let responseText = response.response_text;
          if (responseText.length > 800) {
            responseText = responseText.substring(0, 800) + '\n[Truncated...]';
          }
          shortPrompt += `${responseText}\n`;
        }
        shortPrompt += `\n---\n\n`;
      });
      
      shortPrompt += `**Please provide:**\n1. Which response is best and why\n2. Brief comparison of key differences\n3. Scores (1-10) for each response`;
      
      console.log('✅ Short judge prompt created, length:', shortPrompt.length);
      return shortPrompt;
    }
    
    return prompt;
  }
  
  onMount(async () => {
    await loadProviders();
    await loadRecentComparisons();
  });
  
  async function loadProviders() {
    try {
      const providersData = await getAvailableLLMProviders();
      providers = providersData.map((provider: LLMProvider) => ({
        ...provider,
        models: [],
        selectedModels: [], // Initialize as empty array
        modelsLoading: false,
        modelsError: '',
        isEnabled: false
      }));
    } catch (error) {
      console.error('Failed to load providers:', error);
      toasts.error('Failed to load available AI providers');
    } finally {
      providersLoading = false;
    }
  }
  
  async function loadModelsForProvider(providerIndex: number) {
    const provider = providers[providerIndex];
    console.log(`Starting to load models for ${provider.name}...`);
    
    provider.modelsLoading = true;
    provider.modelsError = '';
    
    try {
      const response = await getProviderModels(provider.id.toString());
      console.log(`Models response for ${provider.name}:`, response);
      
      if (response.models && response.models.length > 0) {
        provider.models = response.models;
        console.log(`Loaded ${response.models.length} models for ${provider.name}`);
        
        // Auto-select the first model if none are selected
        if (provider.selectedModels.length === 0 && response.models.length > 0) {
          provider.selectedModels = [response.models[0].id || response.models[0].name || ''];
          console.log(`Auto-selected model: ${provider.selectedModels[0]}`);
        }
      } else {
        provider.modelsError = response.error || 'No models available';
        console.log(`No models available for ${provider.name}: ${provider.modelsError}`);
      }
    } catch (error) {
      console.error(`Failed to load models for ${provider.name}:`, error);
      provider.modelsError = 'Failed to load models';
    } finally {
      provider.modelsLoading = false;
    }
    
    // Trigger reactivity
    providers = [...providers];
  }
  
  async function toggleProvider(providerIndex: number, event?: Event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    
    console.log(`Toggling provider ${providerIndex}: ${providers[providerIndex].name}`);
    
    const provider = providers[providerIndex];
    provider.isEnabled = !provider.isEnabled;
    
    console.log(`Provider ${provider.name} is now: ${provider.isEnabled ? 'enabled' : 'disabled'}`);
    
    // Load models if enabling for the first time
    if (provider.isEnabled && provider.models.length === 0 && !provider.modelsLoading) {
      console.log(`Loading models for ${provider.name}...`);
      await loadModelsForProvider(providerIndex);
    }
    
    // Trigger reactivity by reassigning the array
    providers = [...providers];
  }
  
  function updateSelectedModel(providerIndex: number, modelId: string, isChecked: boolean) {
    const provider = providers[providerIndex];
    
    if (isChecked) {
      // Add model if not already selected
      if (!provider.selectedModels.includes(modelId)) {
        provider.selectedModels = [...provider.selectedModels, modelId];
      }
    } else {
      // Remove model from selection
      provider.selectedModels = provider.selectedModels.filter(id => id !== modelId);
    }
    
    console.log(`Updated ${provider.name} selected models:`, provider.selectedModels);
    providers = [...providers];
  }
  
  async function loadRecentComparisons() {
    try {
      recentComparisons = await getLLMComparisons();
    } catch (error) {
      console.error('Failed to load comparison history:', error);
    }
  }
  
  async function runComparison() {
    if (!prompt.trim()) {
      toasts.error('Please enter a prompt');
      return;
    }
    
    const enabledProviders = providers.filter(p => p.isEnabled);
    if (enabledProviders.length === 0) {
      toasts.error('Please select at least one AI provider');
      return;
    }
    
    const invalidProviders = enabledProviders.filter(p => p.selectedModels.length === 0);
    if (invalidProviders.length > 0) {
      toasts.error('Please select at least one model for each enabled provider');
      return;
    }
    
    loading = true;
    currentComparison = null;
    
    try {
      const providerConfigs: ProviderConfig[] = [];
      
      // Create a config for each selected model from each provider
      enabledProviders.forEach(provider => {
        provider.selectedModels.forEach(modelName => {
          providerConfigs.push({
            provider_id: provider.id,
            model_name: modelName
          });
        });
      });
      
      console.log('Provider configs for comparison:', providerConfigs);
      
      const result = await createLLMComparison({
        prompt: prompt.trim(),
        title: title.trim(),
        provider_configs: providerConfigs,
        temperature: 0.7 // Fixed temperature for balanced responses
      });
      
      if (result.success) {
        currentComparison = result.comparison;
        console.log('✅ Comparison result:', result.comparison);
        console.log('📊 Responses received:', result.comparison.responses);
        
        toasts.success(`Comparison completed! Got responses from ${result.summary.successful_responses} providers`);
        
        if (result.summary.errors.length > 0) {
          result.summary.errors.forEach(error => {
            toasts.error(`Error: ${error}`);
          });
        }
        
        await loadRecentComparisons();
      } else {
        toasts.error(result.error || 'Failed to run comparison');
      }
      
    } catch (error) {
      console.error('Comparison failed:', error);
      toasts.error('Failed to run comparison. Please try again.');
    } finally {
      loading = false;
    }
  }
  
  function clearForm() {
    prompt = '';
    title = '';
    currentComparison = null;
    // Reset provider selections
    providers = providers.map(p => ({
      ...p,
      isEnabled: false,
      selectedModels: p.models.length > 0 ? [p.models[0].id || p.models[0].name || ''] : []
    }));
  }
  
  function loadComparison(comparison: LLMComparison) {
    currentComparison = comparison;
    prompt = comparison.prompt;
    title = comparison.title;
    showHistory = false;
  }

  function handleComparisonKeyPress(event: KeyboardEvent, comparison: LLMComparison) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      loadComparison(comparison);
    }
  }
  
  function getProviderIcon(providerType: string): string {
    const icons: Record<string, string> = {
      'openai': 'fa-robot',
      'gemini': 'fa-google',
      'claude': 'fa-brain',
      'huggingface': 'fa-face-smile'
    };
    return icons[providerType] || 'fa-microchip';
  }
  
  function getProviderColor(providerType: string): string {
    const colors: Record<string, string> = {
      'openai': 'bg-green-100 text-green-800 border-green-200',
      'gemini': 'bg-blue-100 text-blue-800 border-blue-200',
      'claude': 'bg-purple-100 text-purple-800 border-purple-200',
      'huggingface': 'bg-orange-100 text-orange-800 border-orange-200'
    };
    return colors[providerType] || 'bg-gray-100 text-gray-800 border-gray-200';
  }
  
  function formatResponseTime(ms: number): string {
    if (ms < 1000) {
      return `${ms}ms`;
    }
    return `${(ms / 1000).toFixed(1)}s`;
  }
  
  function formatCost(cost: any): string {
    // Handle null, undefined, or non-numeric values
    if (!cost || typeof cost !== 'number' || isNaN(cost)) {
      return 'N/A';
    }
    return `${cost.toFixed(4)}`;
  }
  
  function getModelDisplayName(model: LLMModel): string {
    return model.displayName || model.name || model.id;
  }
</script>

<svelte:head>
  <title>LLM Eval - AI Model Comparison</title>
</svelte:head>

<div class="dashboard-oxford">
  <div class="container-oxford section-oxford">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="heading-oxford-1">
            <i class="fas fa-robot mr-3" style="color: #002147;"></i>
            LLM Eval
          </h1>
          <p class="text-oxford-secondary">
            Compare responses from different AI language models side by side
          </p>
        </div>
        <div class="flex space-x-3">
          <button
            on:click={() => showHistory = !showHistory}
            class="btn-oxford-secondary"
            aria-expanded={showHistory}
          >
            <i class="fas fa-history mr-2"></i>
            {showHistory ? 'Hide' : 'Show'} History
          </button>
          <button
            on:click={clearForm}
            class="btn-oxford-outline"
          >
            <i class="fas fa-eraser mr-2"></i>
            Clear
          </button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-4 gap-8">
      <!-- Input Panel -->
      <div class="lg:col-span-1">
        <div class="card-oxford">
          <h2 class="card-oxford-title">
            <i class="fas fa-edit mr-2" style="color: #002147;"></i>
            Prompt Setup
          </h2>
          
          <!-- Title Input -->
          <div class="mb-4">
            <label for="title" class="form-label">
              Title (Optional)
            </label>
            <input
              type="text"
              id="title"
              bind:value={title}
              placeholder="Give this comparison a name..."
              class="form-input focus-oxford"
            />
          </div>
          
          <!-- LLM as a Judge Section -->
          <div class="mb-6">
            <div class="card-oxford bg-gradient-to-r from-purple-50 to-indigo-50 border-purple-200">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center">
                  <i class="fas fa-gavel mr-2 text-purple-600"></i>
                  <h3 class="text-lg font-semibold text-oxford-800">LLM as a Judge</h3>
                </div>
                <label class="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    bind:checked={judgeEnabled}
                    class="mr-2 h-4 w-4 text-purple-600 focus:ring-purple-500 border-oxford-300 rounded"
                  />
                  <span class="text-sm text-oxford-700">Enable Judge Analysis</span>
                </label>
              </div>
              
              <p class="text-sm text-oxford-600 mb-4">
                Select an AI model to act as a judge and automatically evaluate which response is the best based on accuracy, relevance, clarity, and usefulness.
                {#if judgeEnabled && !modelsLoadedForJudge}
                  <span class="block mt-2 text-purple-600 font-medium">
                    <i class="fas fa-cog fa-spin mr-1"></i>
                    Loading models from all providers...
                  </span>
                {/if}
              </p>
              
              {#if judgeEnabled}
                <div class="space-y-4">
                  <!-- Single Dropdown for All Judge Models -->
                  <div>
                    <label for="judgeModelSelect" class="form-label">
                      <i class="fas fa-gavel mr-2"></i>
                      Select Judge Model
                    </label>
                    <select
                      id="judgeModelSelect"
                      bind:value={selectedJudgeModel}
                      on:change={handleJudgeModelChange}
                      class="w-full px-4 py-3 border border-oxford-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 bg-white transition-all duration-200 hover:border-purple-300"
                    >
                      <option value="" disabled>
                        Choose a model to act as judge...
                      </option>
                      {#each Object.entries(getGroupedModels()) as [providerName, models]}
                        <optgroup label={providerName}>
                          {#each models as modelOption}
                            <option value={`${modelOption.providerId}:${modelOption.modelId}`}>
                              {modelOption.modelName}
                            </option>
                          {/each}
                        </optgroup>
                      {/each}
                    </select>
                    
                    {#if getAllAvailableModels().length === 0}
                      <div class="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <div class="flex items-center">
                          <i class="fas fa-exclamation-triangle text-yellow-500 mr-2"></i>
                          <span class="text-sm text-yellow-700">
                            {#if modelsLoadedForJudge}
                              No models available. Please check if providers have valid API keys configured.
                            {:else}
                              Loading models from all providers...
                            {/if}
                          </span>
                        </div>
                        {#if !modelsLoadedForJudge}
                          <div class="flex items-center mt-2">
                            <div class="spinner-oxford mr-2" style="width: 16px; height: 16px;"></div>
                            <span class="text-xs text-yellow-600">This may take a few seconds...</span>
                          </div>
                        {/if}
                      </div>
                    {/if}
                    
                    {#if selectedJudgeModel && getSelectedJudgeInfo()}
                      {@const judgeInfo = getSelectedJudgeInfo()}
                      <div class="mt-3 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                        <div class="flex items-center justify-between">
                          <div class="flex items-center">
                            <i class="fas {getProviderIcon(judgeInfo.providerType)} mr-2 text-purple-600"></i>
                            <div>
                              <div class="text-sm font-medium text-purple-800">
                                Selected: {judgeInfo.providerName}
                              </div>
                              <div class="text-xs text-purple-600">
                                Model: {judgeInfo.modelName}
                              </div>
                            </div>
                          </div>
                          <button
                            on:click={() => selectedJudgeModel = ''}
                            class="text-purple-400 hover:text-purple-600 transition-colors duration-200"
                            title="Clear selection"
                          >
                            <i class="fas fa-times"></i>
                          </button>
                        </div>
                      </div>
                    {/if}
                  </div>
                  
                  <!-- Judge Analysis Display - Removed from sidebar -->
                  <!-- Analysis will only show in the center results area -->
                  
                  {#if judgeError}
                    <div class="alert-oxford-error">
                      <i class="fas fa-exclamation-triangle mr-2"></i>
                      <strong>Judge Analysis Error:</strong> {judgeError}
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          </div>
          
          <!-- Prompt Input -->
          <div class="mb-6">
            <label for="prompt" class="form-label">
              Prompt <span class="text-red-500">*</span>
            </label>
            <textarea
              id="prompt"
              bind:value={prompt}
              placeholder="Enter your prompt here...\n\nYou can write detailed, multi-paragraph prompts for comprehensive AI model comparisons. The text box will expand as you type."
              rows="6"
              class="form-input focus-oxford resize-y min-h-[120px] max-h-[300px]"
            ></textarea>
            <div class="mt-1 text-xs text-oxford-500">
              {prompt.length} characters • Temperature: 0.7 (optimized for balanced responses)
            </div>
          </div>
          
          <!-- Provider & Model Selection -->
          <div class="mb-6">
            <fieldset>
              <legend class="form-label">AI Providers & Models</legend>
              {#if providersLoading}
                <div class="text-center py-4">
                  <div class="spinner-oxford"></div>
                  <p class="text-oxford-secondary mt-2">Loading providers...</p>
                </div>
              {:else if providers.length === 0}
                <div class="text-center py-4">
                  <i class="fas fa-exclamation-triangle text-yellow-500"></i>
                  <p class="text-oxford-secondary mt-2">No AI providers available</p>
                  <p class="text-xs text-oxford-400">Contact admin to set up access</p>
                </div>
              {:else}
                <div class="space-y-3">
                  {#each providers as provider, index (provider.id)}
                    <div class="border rounded-lg overflow-hidden transition-all duration-200 {provider.isEnabled ? 'border-oxford-400 bg-oxford-50' : 'border-oxford-200 bg-white hover:border-oxford-300'}">
                      <!-- Compact Provider Header -->
                      <div class="p-3">
                        <div class="flex items-center justify-between">
                          <div class="flex items-center cursor-pointer flex-1">
                            <button
                              type="button"
                              class="flex items-center w-full text-left focus-oxford rounded p-1 -m-1"
                              on:click={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                toggleProvider(index);
                              }}
                              on:keydown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault();
                                  toggleProvider(index);
                                }
                              }}
                              aria-label="Toggle {provider.name} provider"
                            >
                              <input
                                type="checkbox"
                                checked={provider.isEnabled}
                                on:change={(e) => {
                                  e.stopPropagation();
                                  toggleProvider(index);
                                }}
                                class="mr-3 h-4 w-4 text-oxford-blue focus:ring-oxford-500 border-oxford-300 rounded"
                                aria-describedby="provider-{index}-description"
                              />
                              <div class="flex items-center">
                                <i class="fas {getProviderIcon(provider.provider_type)} mr-2 text-lg" style="color: #002147;" aria-hidden="true"></i>
                                <div>
                                  <div class="font-semibold text-oxford-800 text-sm">{provider.name}</div>
                                  <div class="text-xs text-oxford-600" id="provider-{index}-description">{provider.provider_type.toUpperCase()}</div>
                                </div>
                              </div>
                            </button>
                          </div>
                          
                          <!-- Compact Status Indicator -->
                          <div class="ml-3">
                            {#if provider.isEnabled}
                              <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                <i class="fas fa-check mr-1"></i>
                                {provider.selectedModels.length} selected
                              </span>
                            {:else}
                              <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                Disabled
                              </span>
                            {/if}
                          </div>
                        </div>
                        
                        <!-- Compact Model Selection (only when enabled) -->
                        {#if provider.isEnabled}
                          <div class="mt-3 pt-3 border-t border-oxford-200">
                            {#if provider.modelsLoading}
                              <div class="flex items-center justify-center py-2">
                                <div class="spinner-oxford mr-2" style="width: 14px; height: 14px;"></div>
                                <span class="text-sm text-oxford-600">Loading models...</span>
                              </div>
                            {:else if provider.modelsError}
                              <div class="py-2">
                                <div class="flex items-center justify-between bg-red-50 border border-red-200 rounded-lg p-2">
                                  <div class="flex items-center">
                                    <i class="fas fa-exclamation-triangle text-red-500 mr-2"></i>
                                    <span class="text-sm text-red-700">{provider.modelsError}</span>
                                  </div>
                      <button
                        on:click={() => loadModelsForProvider(index)}
                        class="text-sm text-red-600 hover:text-red-800 underline"
                        aria-label="Retry loading models for {provider.name}"
                      >
                        Retry
                      </button>
                                </div>
                              </div>
                            {:else if provider.models.length > 0}
                              <div class="space-y-2">
                                <!-- Compact Model Selection Header -->
                                <div class="flex items-center justify-between">
                                  <span class="text-sm font-medium text-oxford-700">
                                    Models ({provider.selectedModels.length}/{provider.models.length})
                                  </span>
                                  <div class="flex space-x-2">
                                    <button
                                      on:click={() => {
                                        provider.selectedModels = provider.models.map(m => m.id || m.name);
                                        providers = [...providers];
                                      }}
                                      class="text-xs text-oxford-blue hover:underline"
                                      aria-label="Select all models for {provider.name}"
                                    >
                                      All
                                    </button>
                                    <button
                                      on:click={() => {
                                        provider.selectedModels = [];
                                        providers = [...providers];
                                      }}
                                      class="text-xs text-red-600 hover:underline"
                                      aria-label="Deselect all models for {provider.name}"
                                    >
                                      None
                                    </button>
                                  </div>
                                </div>
                                
                                <!-- Compact Model Grid -->
                                <div class="grid grid-cols-1 gap-1 max-h-32 overflow-y-auto scrollbar-oxford">
                                  {#each provider.models as model}
                                    {@const modelId = model.id || model.name}
                                    {@const isSelected = provider.selectedModels.includes(modelId)}
                                    <label class="flex items-center p-2 rounded border transition-all duration-200 cursor-pointer {isSelected ? 'bg-oxford-100 border-oxford-300' : 'bg-white border-oxford-200 hover:border-oxford-300'}">
                                      <input
                                        type="checkbox"
                                        checked={isSelected}
                                        on:change={(e) => updateSelectedModel(index, modelId, e.target.checked)}
                                        class="mr-2 h-3 w-3 text-oxford-blue focus:ring-oxford-500 border-oxford-300 rounded"
                                      />
                                      <div class="flex-1 min-w-0">
                                        <div class="text-sm font-medium text-oxford-800 truncate">
                                          {getModelDisplayName(model)}
                                        </div>
                                      </div>
                                      {#if isSelected}
                                        <i class="fas fa-check text-oxford-blue text-xs"></i>
                                      {/if}
                                    </label>
                                  {/each}
                                </div>
                                
                                <!-- Selected Models Summary (compact) -->
                                {#if provider.selectedModels.length > 0}
                                  <div class="bg-oxford-50 border border-oxford-200 rounded p-2">
                                    <div class="text-xs text-oxford-600 mb-1">
                                      Selected: {provider.selectedModels.slice(0, 2).map(selectedModel => {
                                        const modelObj = provider.models.find(m => (m.id || m.name) === selectedModel);
                                        return modelObj ? getModelDisplayName(modelObj) : selectedModel;
                                      }).join(', ')}{provider.selectedModels.length > 2 ? ` +${provider.selectedModels.length - 2} more` : ''}
                                    </div>
                                  </div>
                                {/if}
                              </div>
                            {:else}
                              <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-2">
                                <div class="flex items-center">
                                  <i class="fas fa-exclamation-triangle text-yellow-500 mr-2"></i>
                                  <span class="text-sm text-yellow-700">No models available</span>
                                </div>
                              </div>
                            {/if}
                          </div>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </fieldset>
          </div>
          
          <!-- Run Button -->
          <button
            on:click={runComparison}
            disabled={loading || !prompt.trim() || providers.filter(p => p.isEnabled && p.selectedModels.length > 0).length === 0}
            class="btn-oxford-primary w-full py-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if loading}
              <div class="spinner-oxford mr-2"></div>
              Running Comparison...
            {:else}
              <i class="fas fa-play mr-2"></i>
              Run Comparison ({providers.filter(p => p.isEnabled).reduce((total, p) => total + p.selectedModels.length, 0)} models)
            {/if}
          </button>
        </div>
      </div>
      
      <!-- Results Panel -->
      <div class="lg:col-span-3">
        {#if showHistory}
          <!-- History Panel with Delete Functionality -->
          <div class="card-oxford">
            <div class="flex items-center justify-between mb-4">
              <h2 class="card-oxford-title">
                <i class="fas fa-history mr-2" style="color: #002147;"></i>
                Recent Comparisons
              </h2>
              
              <!-- History Controls -->
              <div class="flex items-center space-x-2">
                {#if recentComparisons.length > 0}
                  <!-- Selection Counter -->
                  {#if selectedComparisons.length > 0}
                    <span class="text-sm text-oxford-600 bg-oxford-100 px-3 py-1 rounded-full">
                      {selectedComparisons.length} selected
                    </span>
                  {/if}
                  
                  <!-- Select All Checkbox -->
                  <label class="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isSelectAllChecked}
                      on:change={toggleSelectAll}
                      class="mr-2 h-4 w-4 text-oxford-blue focus:ring-oxford-500 border-oxford-300 rounded"
                    />
                    <span class="text-sm text-oxford-700">Select All</span>
                  </label>
                  
                  <!-- Delete Button -->
                  {#if selectedComparisons.length > 0}
                    <button
                      on:click={() => showDeleteConfirmation = true}
                      disabled={deletingComparisons}
                      class="btn-oxford-outline text-red-600 border-red-300 hover:bg-red-50 px-3 py-1 text-sm disabled:opacity-50"
                    >
                      <i class="fas fa-trash mr-1"></i>
                      Delete ({selectedComparisons.length})
                    </button>
                  {/if}
                {/if}
              </div>
            </div>
            
            {#if recentComparisons.length === 0}
              <div class="text-center py-8">
                <i class="fas fa-folder-open text-oxford-400 text-3xl"></i>
                <p class="text-oxford-secondary mt-2">No comparisons yet</p>
                <p class="text-sm text-oxford-400">Run your first AI model comparison!</p>
              </div>
            {:else}
              <div class="space-y-3">
                {#each recentComparisons as comparison (comparison.id)}
                  {@const isSelected = selectedComparisons.includes(comparison.id)}
                  <div class="flex items-start space-x-3 p-4 border rounded-lg transition-all duration-200 {isSelected ? 'border-oxford-400 bg-oxford-50' : 'border-oxford-200 hover:border-oxford-300 hover:bg-oxford-25'}">
                    <!-- Selection Checkbox -->
                    <div class="flex-shrink-0 pt-1">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        on:change={() => toggleComparisonSelection(comparison.id)}
                        class="h-4 w-4 text-oxford-blue focus:ring-oxford-500 border-oxford-300 rounded"
                      />
                    </div>
                    
                    <!-- Comparison Content -->
                    <button 
                      type="button"
                      class="flex-1 text-left focus-oxford rounded"
                      on:click={() => loadComparison(comparison)}
                      on:keydown={(e) => handleComparisonKeyPress(e, comparison)}
                      aria-label="Load comparison: {comparison.title || 'Untitled Comparison'}"
                    >
                      <div class="flex justify-between items-start">
                        <div class="flex-1">
                          <h3 class="font-medium text-oxford-800">
                            {comparison.title || 'Untitled Comparison'}
                          </h3>
                          <p class="text-sm text-oxford-600 mt-1 line-clamp-2">
                            {comparison.prompt}
                          </p>
                          <div class="flex items-center mt-2 text-xs text-oxford-400">
                            <i class="fas fa-clock mr-1" aria-hidden="true"></i>
                            <time datetime={comparison.created_at}>
                              {new Date(comparison.created_at).toLocaleDateString()}
                            </time>
                            <span class="mx-2">•</span>
                            <i class="fas fa-reply mr-1" aria-hidden="true"></i>
                            {comparison.responses.length} responses
                            {#if comparison.responses.length > 0}
                              <span class="mx-2">•</span>
                              <i class="fas fa-eye mr-1" aria-hidden="true"></i>
                              <span class="text-oxford-500">Click to view</span>
                            {/if}
                          </div>
                        </div>
                        <i class="fas fa-chevron-right text-oxford-400 ml-3" aria-hidden="true"></i>
                      </div>
                    </button>
                  </div>
                {/each}
              </div>
              
              <!-- Bulk Actions Footer -->
              {#if selectedComparisons.length > 0}
                <div class="mt-4 p-3 bg-oxford-50 border border-oxford-200 rounded-lg">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center text-sm text-oxford-700">
                      <i class="fas fa-info-circle mr-2"></i>
                      {selectedComparisons.length} comparison{selectedComparisons.length > 1 ? 's' : ''} selected
                    </div>
                    <div class="flex space-x-2">
                      <button
                        on:click={() => selectedComparisons = []}
                        class="text-sm text-oxford-600 hover:text-oxford-800 underline"
                      >
                        Clear Selection
                      </button>
                      <button
                        on:click={() => showDeleteConfirmation = true}
                        disabled={deletingComparisons}
                        class="btn-oxford-outline text-red-600 border-red-300 hover:bg-red-50 px-3 py-1 text-sm disabled:opacity-50"
                      >
                        {#if deletingComparisons}
                          <div class="spinner-oxford mr-1" style="width: 12px; height: 12px;"></div>
                          Deleting...
                        {:else}
                          <i class="fas fa-trash mr-1"></i>
                          Delete Selected
                        {/if}
                      </button>
                    </div>
                  </div>
                </div>
              {/if}
            {/if}
          </div>
        {:else if currentComparison}
          <!-- Results Display with Split-Pane Layout -->
          <div class="space-y-6">
            <!-- Comparison Header -->
            <div class="card-oxford">
              <div class="flex items-center justify-between mb-4">
                <h2 class="card-oxford-title">
                  {currentComparison.title || 'AI Model Comparison'}
                </h2>
                <!-- Pagination Controls -->
                {#if totalPages > 1}
                  <div class="flex items-center space-x-2">
                    <button
                      on:click={prevPage}
                      disabled={currentPage === 0}
                      class="btn-oxford-outline px-3 py-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <i class="fas fa-chevron-left mr-1"></i>
                      Previous
                    </button>
                    
                    <!-- Page Numbers -->
                    <div class="flex space-x-1">
                      {#each Array(totalPages) as _, index}
                        <button
                          on:click={() => goToPage(index)}
                          class="w-8 h-8 rounded text-sm transition-colors duration-200 {currentPage === index ? 'bg-oxford-blue text-white' : 'bg-oxford-100 text-oxford-700 hover:bg-oxford-200'}"
                          aria-label="Go to page {index + 1}"
                          aria-current={currentPage === index ? 'page' : undefined}
                        >
                          {index + 1}
                        </button>
                      {/each}
                    </div>
                    
                    <button
                      on:click={nextPage}
                      disabled={currentPage === totalPages - 1}
                      class="btn-oxford-outline px-3 py-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Next
                      <i class="fas fa-chevron-right ml-1"></i>
                    </button>
                    
                    <span class="text-sm text-oxford-600 ml-3">
                      Showing {(currentPage * modelsPerPage) + 1}-{Math.min((currentPage + 1) * modelsPerPage, currentComparison.responses.length)} of {currentComparison.responses.length} models
                    </span>
                  </div>
                {/if}
              </div>
              
              <div class="bg-oxford-50 p-4 rounded-lg">
                <p class="text-sm font-medium text-oxford-700 mb-2">Prompt:</p>
                <p class="text-oxford-900">{currentComparison.prompt}</p>
              </div>
            </div>
            
            <!-- Split-Pane Response Layout -->
            {#if currentComparison.responses && currentComparison.responses.length > 0}
              <div class="card-oxford p-0 overflow-hidden">
                <!-- Response Navigation Header -->
                <div class="bg-oxford-blue text-white p-4">
                  <div class="flex items-center justify-between">
                    <h3 class="text-lg font-semibold">
                      <i class="fas fa-columns mr-2"></i>
                      Model Comparison View
                    </h3>
                    <div class="flex items-center space-x-4">
                      <!-- Models per page selector -->
                      <div class="flex items-center space-x-2">
                        <label class="text-sm text-oxford-100">Models per view:</label>
                        <select
                          bind:value={modelsPerPage}
                          on:change={() => currentPage = 0}
                          class="px-2 py-1 rounded text-oxford-800 text-sm"
                        >
                          <option value={1}>1</option>
                          <option value={2}>2</option>
                          <option value={3}>3</option>
                          <option value={4}>4</option>
                        </select>
                      </div>
                      
                      <!-- Quick navigation -->
                      {#if totalPages > 1}
                        <div class="flex items-center space-x-1">
                          <button
                            on:click={() => goToPage(0)}
                            disabled={currentPage === 0}
                            class="p-1 rounded text-oxford-100 hover:bg-oxford-800 disabled:opacity-50"
                            title="First page"
                          >
                            <i class="fas fa-angle-double-left"></i>
                          </button>
                          <button
                            on:click={prevPage}
                            disabled={currentPage === 0}
                            class="p-1 rounded text-oxford-100 hover:bg-oxford-800 disabled:opacity-50"
                            title="Previous page"
                          >
                            <i class="fas fa-angle-left"></i>
                          </button>
                          <span class="text-oxford-100 text-sm px-2">
                            {currentPage + 1} / {totalPages}
                          </span>
                          <button
                            on:click={nextPage}
                            disabled={currentPage === totalPages - 1}
                            class="p-1 rounded text-oxford-100 hover:bg-oxford-800 disabled:opacity-50"
                            title="Next page"
                          >
                            <i class="fas fa-angle-right"></i>
                          </button>
                          <button
                            on:click={() => goToPage(totalPages - 1)}
                            disabled={currentPage === totalPages - 1}
                            class="p-1 rounded text-oxford-100 hover:bg-oxford-800 disabled:opacity-50"
                            title="Last page"
                          >
                            <i class="fas fa-angle-double-right"></i>
                          </button>
                        </div>
                      {/if}
                    </div>
                  </div>
                </div>
                
                <!-- Split Pane Container -->
                <div class="split-pane-container h-[600px] flex">
                  {#each paginatedResponses as response, index (response.id)}
                    <div class="split-pane flex-1 {index < paginatedResponses.length - 1 ? 'border-r border-oxford-200' : ''}">
                      <!-- Response Header -->
                      <div class="response-header bg-oxford-50 border-b border-oxford-200 p-4">
                        <div class="flex items-center justify-between">
                          <div class="flex items-center">
                            <div class="w-10 h-10 rounded-full flex items-center justify-center mr-3 {getProviderColor(response.provider_name.toLowerCase())}">
                              <i class="fas {getProviderIcon(response.provider_name.toLowerCase())} text-lg"></i>
                            </div>
                            <div>
                              <h4 class="font-semibold text-oxford-800">{response.provider_name}</h4>
                              <p class="text-sm text-oxford-600">{response.model_name}</p>
                            </div>
                          </div>
                          
                          <!-- Performance Metrics -->
                          <div class="flex items-center space-x-4 text-xs text-oxford-500">
                            <div class="flex items-center">
                              <i class="fas fa-bolt mr-1"></i>
                              <span>{formatResponseTime(response.response_time_ms)}</span>
                            </div>
                            {#if response.token_count}
                              <div class="flex items-center">
                                <i class="fas fa-hashtag mr-1"></i>
                                <span>{response.token_count} tokens</span>
                              </div>
                            {/if}
                            {#if response.cost_estimate}
                              <div class="flex items-center">
                                <i class="fas fa-dollar-sign mr-1"></i>
                                <span>${formatCost(response.cost_estimate)}</span>
                              </div>
                            {/if}
                          </div>
                        </div>
                      </div>
                      
                      <!-- Response Content -->
                      <div class="response-content p-4 h-full overflow-y-auto">
                        {#if response.error_message}
                          <div class="alert-oxford-error">
                            <i class="fas fa-exclamation-triangle mr-2"></i>
                            <div>
                              <strong>Error:</strong>
                              <p class="mt-1">{response.error_message}</p>
                            </div>
                          </div>
                        {:else if response.response_text}
                          <div class="prose prose-sm max-w-none">
                            <div class="response-text text-oxford-800 leading-relaxed whitespace-pre-wrap">
                              {response.response_text}
                            </div>
                          </div>
                        {:else}
                          <div class="flex items-center justify-center h-32 text-oxford-500">
                            <div class="text-center">
                              <i class="fas fa-question-circle text-2xl mb-2"></i>
                              <p class="text-sm">No response generated</p>
                            </div>
                          </div>
                        {/if}
                      </div>
                    </div>
                  {/each}
                  
                  <!-- Empty panes if less than modelsPerPage -->
                  {#each Array(modelsPerPage - paginatedResponses.length) as _, index}
                    <div class="split-pane flex-1 {paginatedResponses.length + index < modelsPerPage - 1 ? 'border-r border-oxford-200' : ''}">
                      <div class="h-full flex items-center justify-center bg-oxford-25">
                        <div class="text-center text-oxford-400">
                          <i class="fas fa-plus-circle text-3xl mb-2"></i>
                          <p class="text-sm">Empty slot</p>
                          <p class="text-xs">Add more providers to fill</p>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
                
                <!-- Bottom Navigation -->
                {#if totalPages > 1}
                  <div class="border-t border-oxford-200 p-4 bg-oxford-50">
                    <div class="flex items-center justify-center space-x-2">
                      <button
                        on:click={prevPage}
                        disabled={currentPage === 0}
                        class="btn-oxford-outline px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <i class="fas fa-chevron-left mr-2"></i>
                        Previous Models
                      </button>
                      
                      <!-- Page Dots -->
                      <div class="flex space-x-2 mx-6">
                        {#each Array(totalPages) as _, index}
                          <button
                            on:click={() => goToPage(index)}
                            class="w-3 h-3 rounded-full transition-colors duration-200 {currentPage === index ? 'bg-oxford-blue' : 'bg-oxford-300 hover:bg-oxford-400'}"
                            title="Page {index + 1}"
                          ></button>
                        {/each}
                      </div>
                      
                      <button
                        on:click={nextPage}
                        disabled={currentPage === totalPages - 1}
                        class="btn-oxford-outline px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Next Models
                        <i class="fas fa-chevron-right ml-2"></i>
                      </button>
                    </div>
                  </div>
                {/if}
                
                <!-- Judge Analysis Section -->
                {#if judgeEnabled && currentComparison && currentComparison.responses.length > 1}
                  <div class="border-t border-purple-200 bg-gradient-to-r from-purple-50 to-indigo-50 p-4">
                    <div class="flex items-center justify-between mb-3">
                      <div class="flex items-center">
                        <i class="fas fa-gavel text-purple-600 mr-2"></i>
                        <h4 class="font-semibold text-oxford-800">AI Judge Analysis</h4>
                        {#if selectedJudgeModel && getSelectedJudgeInfo()}
                          {@const judgeInfo = getSelectedJudgeInfo()}
                          <span class="ml-2 text-xs text-purple-600 bg-purple-100 px-2 py-1 rounded-full">
                            {judgeInfo.providerName} - {judgeInfo.modelName}
                          </span>
                        {/if}
                      </div>
                      
                      <button
                        on:click={runJudgeAnalysis}
                        disabled={judgeLoading || !selectedJudgeModel || selectedJudgeModel === ''}
                        class="btn-oxford-primary bg-purple-600 hover:bg-purple-700 border-purple-600 px-4 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {#if judgeLoading}
                          <div class="spinner-oxford mr-2" style="width: 14px; height: 14px;"></div>
                          Analyzing...
                        {:else}
                          <i class="fas fa-balance-scale mr-2"></i>
                          Run Judge Analysis
                        {/if}
                      </button>
                    </div>
                    
                    {#if judgeAnalysis}
                      <div class="bg-white border border-purple-200 rounded-lg p-4">
                        <div class="prose prose-sm max-w-none">
                          <div class="text-oxford-800 leading-relaxed whitespace-pre-wrap text-sm">
                            {judgeAnalysis}
                          </div>
                        </div>
                      </div>
                    {:else if judgeError}
                      <div class="alert-oxford-error">
                        <i class="fas fa-exclamation-triangle mr-2"></i>
                        <strong>Analysis Error:</strong> {judgeError}
                      </div>
                    {:else if !selectedJudgeModel || selectedJudgeModel === ''}
                      <div class="text-center py-4">
                        <i class="fas fa-info-circle text-purple-400 text-xl mb-2"></i>
                        <p class="text-sm text-oxford-600">Please select a judge model above to enable AI analysis of the responses.</p>
                      </div>
                    {:else}
                      <div class="text-center py-4">
                        <i class="fas fa-gavel text-purple-400 text-xl mb-2"></i>
                        <p class="text-sm text-oxford-600">Click "Run Judge Analysis" to get AI evaluation of which response is best and why.</p>
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
            {:else}
              <div class="card-oxford p-8 text-center">
                <i class="fas fa-exclamation-circle text-oxford-400 text-3xl mb-3"></i>
                <h3 class="text-lg font-medium text-oxford-800 mb-2">No Responses Found</h3>
                <p class="text-oxford-600">The comparison was created but no responses were generated.</p>
                <p class="text-sm text-oxford-500 mt-2">This might be a data structure issue or the backend might be returning responses in a different format.</p>
              </div>
            {/if}
          </div>
        {:else}
          <!-- Welcome State -->
          <div class="card-oxford p-12 text-center">
            <div class="mx-auto w-24 h-24 rounded-full bg-oxford-100 flex items-center justify-center mb-6">
              <i class="fas fa-robot text-3xl" style="color: #002147;"></i>
            </div>
            <h2 class="heading-oxford-2">
              Welcome to LLM Eval
            </h2>
            <p class="text-oxford-600 mb-6 max-w-md mx-auto">
              Compare how different AI language models respond to the same prompt. 
              Select providers and specific models on the left, then see responses side by side.
            </p>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-lg mx-auto">
              <div class="text-center">
                <div class="w-12 h-12 mx-auto rounded-lg bg-green-100 flex items-center justify-center mb-2">
                  <i class="fas fa-robot text-green-600"></i>
                </div>
                <p class="text-xs text-oxford-600">OpenAI Models</p>
              </div>
              <div class="text-center">
                <div class="w-12 h-12 mx-auto rounded-lg bg-blue-100 flex items-center justify-center mb-2">
                  <i class="fab fa-google text-blue-600"></i>
                </div>
                <p class="text-xs text-oxford-600">Gemini Models</p>
              </div>
              <div class="text-center">
                <div class="w-12 h-12 mx-auto rounded-lg bg-purple-100 flex items-center justify-center mb-2">
                  <i class="fas fa-brain text-purple-600"></i>
                </div>
                <p class="text-xs text-oxford-600">Claude Models</p>
              </div>
              <div class="text-center">
                <div class="w-12 h-12 mx-auto rounded-lg bg-orange-100 flex items-center justify-center mb-2">
                  <i class="fas fa-face-smile text-orange-600"></i>
                </div>
                <p class="text-xs text-oxford-600">Other Models</p>
              </div>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirmation}
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 fade-in-oxford">
    <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
      <div class="flex items-center mb-4">
        <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center mr-3">
          <i class="fas fa-exclamation-triangle text-red-600"></i>
        </div>
        <h3 class="text-lg font-semibold text-oxford-800">Confirm Deletion</h3>
      </div>
      
      <p class="text-oxford-600 mb-6">
        Are you sure you want to delete {selectedComparisons.length} comparison{selectedComparisons.length > 1 ? 's' : ''}? 
        This action cannot be undone.
      </p>
      
      <div class="flex justify-end space-x-3">
        <button
          on:click={() => showDeleteConfirmation = false}
          disabled={deletingComparisons}
          class="btn-oxford-secondary px-4 py-2 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          on:click={deleteSelectedComparisons}
          disabled={deletingComparisons}
          class="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {#if deletingComparisons}
            <div class="spinner-oxford mr-2" style="width: 16px; height: 16px; border-color: white; border-top-color: transparent;"></div>
            Deleting...
          {:else}
            <i class="fas fa-trash mr-2"></i>
            Delete {selectedComparisons.length > 1 ? 'All' : ''}
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  /* Split Pane Styles */
  .split-pane-container {
    min-height: 600px;
    background: white;
  }
  
  .split-pane {
    display: flex;
    flex-direction: column;
    min-width: 0; /* Allow flex items to shrink */
  }
  
  .response-header {
    flex-shrink: 0;
  }
  
  .response-content {
    flex: 1;
    overflow-y: auto;
    max-height: calc(600px - 80px); /* Account for header height */
  }
  
  .response-text {
    font-size: 14px;
    line-height: 1.6;
  }
  
  /* Custom scrollbar for response content */
  .response-content::-webkit-scrollbar {
    width: 6px;
  }
  
  .response-content::-webkit-scrollbar-track {
    background: #f1f5f9;
    border-radius: 3px;
  }
  
  .response-content::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 3px;
  }
  
  .response-content::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
  }
  
  /* Responsive adjustments */
  @media (max-width: 768px) {
    .split-pane-container {
      flex-direction: column;
      height: auto;
    }
    
    .split-pane {
      border-right: none !important;
      border-bottom: 1px solid #e2e8f0;
      min-height: 300px;
    }
    
    .response-content {
      max-height: 250px;
    }
  }
  
  /* Oxford color variations */
  .bg-oxford-25 {
    background-color: #f8fafc;
  }
  
  .bg-oxford-25:hover {
    background-color: #f1f5f9;
  }
  
  /* Enhanced Judge Model Selection Dropdown */
  #judgeModelSelect {
    background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
    background-position: right 0.75rem center;
    background-repeat: no-repeat;
    background-size: 1.25rem 1.25rem;
    padding-right: 2.75rem;
  }
  
  #judgeModelSelect optgroup {
    font-weight: 600;
    font-size: 0.875rem;
    color: #002147;
    background-color: #f8fafc;
    padding: 0.25rem 0;
  }
  
  #judgeModelSelect option {
    font-weight: 400;
    color: #374151;
    padding: 0.5rem 1rem;
  }
  
  #judgeModelSelect option:hover {
    background-color: #ede9fe;
  }
  
  /* Improved Prompt Textarea */
  #prompt {
    line-height: 1.6;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  
  #prompt::placeholder {
    color: #9ca3af;
    font-style: italic;
  }
  
  /* Compact Scrollbars */
  .scrollbar-oxford::-webkit-scrollbar {
    width: 4px;
    height: 4px;
  }
  
  .scrollbar-oxford::-webkit-scrollbar-track {
    background: #f1f5f9;
    border-radius: 2px;
  }
  
  .scrollbar-oxford::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 2px;
  }
  
  .scrollbar-oxford::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
  }
</style>
