/**
 * Enhanced LLM Configuration Component
 * ====================================
 * 
 * Optimized component for agent LLM configuration using pre-loaded models
 * to eliminate API calls and reduce LAG during agent configuration.
 */

<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { 
    llmModelsService, 
    type LLMModel, 
    type BulkModelData,
    useModelsForProvider, 
    useRecommendedModels 
  } from '$lib/stores/llmModelsStore';
  
  export let agentId: string;
  export let agentName: string;
  export let agentType: string;
  export let currentConfig: any = {};
  export let bulkModelData: BulkModelData | null = null;
  export let modelsLoaded: boolean = false;
  
  const dispatch = createEventDispatcher();
  
  // Configuration state
  let selectedProvider = currentConfig.llm_provider || 'openai';
  let selectedModel = currentConfig.llm_model || 'gpt-4';
  let temperature = currentConfig.temperature || 0.7;
  let maxTokens = currentConfig.max_tokens || 2048;
  let topP = currentConfig.top_p || 1.0;
  let frequencyPenalty = currentConfig.frequency_penalty || 0.0;
  let presencePenalty = currentConfig.presence_penalty || 0.0;
  
  // UI state
  let showAdvanced = false;
  let configError: string | null = null;
  let estimatedCost = 0;
  
  console.log(`🤖 LLM CONFIG: Initializing for ${agentType} agent "${agentName}"`);
  
  // Reactive derived values from pre-loaded data
  $: availableProviders = bulkModelData ? 
    Object.keys(bulkModelData.provider_statuses).filter(provider => 
      bulkModelData.provider_statuses[provider]?.api_key_valid
    ) : [];
  
  $: providerModels = bulkModelData?.provider_models[selectedProvider] || [];
  
  $: recommendedModels = bulkModelData?.models_by_agent_type[agentType] || [];
  
  $: providerStatus = bulkModelData?.provider_statuses[selectedProvider];
  
  $: selectedModelInfo = providerModels.find(model => model.id === selectedModel);
  
  // Auto-select default model when provider changes
  $: if (selectedProvider && providerModels.length > 0) {
    // If current model is not available in selected provider, choose a default
    if (!providerModels.find(model => model.id === selectedModel)) {
      const recommendedForProvider = recommendedModels.find(model => 
        model.provider === selectedProvider
      );
      selectedModel = recommendedForProvider?.id || providerModels[0]?.id || 'gpt-4';
    }
  }
  
  // Calculate estimated cost
  $: if (selectedModelInfo && maxTokens) {
    const costPer1K = selectedModelInfo.cost_per_1k_tokens || 0.01;
    estimatedCost = (maxTokens / 1000) * costPer1K;
  }
  
  function handleProviderChange() {
    console.log(`🔄 LLM CONFIG: Provider changed to ${selectedProvider}`);
    
    // Auto-select recommended model for this provider and agent type
    const recommendedForProvider = recommendedModels.find(model => 
      model.provider === selectedProvider
    );
    
    if (recommendedForProvider) {
      selectedModel = recommendedForProvider.id;
    } else if (providerModels.length > 0) {
      selectedModel = providerModels[0].id;
    }
    
    emitConfigChange();
  }
  
  function handleModelChange() {
    console.log(`🔄 LLM CONFIG: Model changed to ${selectedModel}`);
    emitConfigChange();
  }
  
  function handleParameterChange() {
    emitConfigChange();
  }
  
  function emitConfigChange() {
    const config = {
      llm_provider: selectedProvider,
      llm_model: selectedModel,
      temperature,
      max_tokens: maxTokens,
      top_p: topP,
      frequency_penalty: frequencyPenalty,
      presence_penalty: presencePenalty
    };
    
    console.log(`💾 LLM CONFIG: Emitting config change for ${agentName}:`, config);
    
    dispatch('configChange', {
      agentId,
      config
    });
  }
  
  function resetToDefaults() {
    console.log(`🔄 LLM CONFIG: Resetting to defaults for ${agentType}`);
    
    // Get recommended model for this agent type
    const recommended = recommendedModels[0];
    if (recommended) {
      selectedProvider = recommended.provider;
      selectedModel = recommended.id;
    }
    
    // Reset other parameters based on agent type
    const defaults = {
      'AssistantAgent': { temperature: 0.7, maxTokens: 2048 },
      'UserProxyAgent': { temperature: 0.3, maxTokens: 1024 },
      'GroupChatManager': { temperature: 0.5, maxTokens: 1024 },
      'DelegateAgent': { temperature: 0.4, maxTokens: 1024 }
    };
    
    const agentDefaults = defaults[agentType] || defaults['AssistantAgent'];
    temperature = agentDefaults.temperature;
    maxTokens = agentDefaults.maxTokens;
    topP = 1.0;
    frequencyPenalty = 0.0;
    presencePenalty = 0.0;
    
    emitConfigChange();
  }
  
  function getModelDisplayName(model: LLMModel): string {
    return model.display_name || model.name || model.id;
  }
  
  function getProviderDisplayName(providerId: string): string {
    const names = {
      'openai': 'OpenAI',
      'anthropic': 'Anthropic',
      'google': 'Google'
    };
    return names[providerId] || providerId;
  }
</script>

<div class="llm-config-component bg-white border border-gray-200 rounded-lg p-4">
  <!-- Header -->
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center space-x-2">
      <i class="fas fa-robot text-blue-600"></i>
      <h3 class="text-lg font-semibold text-gray-900">LLM Configuration</h3>
      <span class="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">{agentType}</span>
    </div>
    
    <div class="flex items-center space-x-2">
      {#if modelsLoaded}
        <div class="flex items-center text-green-600 text-xs">
          <i class="fas fa-check-circle mr-1"></i>
          <span>Models Ready</span>
        </div>
      {:else}
        <div class="flex items-center text-gray-500 text-xs">
          <i class="fas fa-clock mr-1"></i>
          <span>Loading...</span>
        </div>
      {/if}
      
      <button 
        class="text-gray-400 hover:text-gray-600 text-sm"
        on:click={resetToDefaults}
        title="Reset to defaults"
      >
        <i class="fas fa-undo"></i>
      </button>
    </div>
  </div>
  
  {#if !modelsLoaded || !bulkModelData}
    <!-- Loading State -->
    <div class="text-center py-6">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
      <p class="text-gray-600 text-sm">Loading LLM models...</p>
      <p class="text-gray-500 text-xs mt-1">Pre-loading models for faster configuration</p>
    </div>
  {:else if availableProviders.length === 0}
    <!-- No Providers Available -->
    <div class="text-center py-6">
      <div class="w-12 h-12 bg-red-100 text-red-600 rounded-lg flex items-center justify-center mx-auto mb-3">
        <i class="fas fa-exclamation-triangle text-xl"></i>
      </div>
      <p class="text-red-600 font-medium">No LLM providers available</p>
      <p class="text-gray-600 text-sm mt-1">Please configure API keys in settings</p>
    </div>
  {:else}
    <!-- Configuration Form -->
    <div class="space-y-4">
      <!-- Provider Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          LLM Provider
          <span class="text-red-500">*</span>
        </label>
        <div class="grid grid-cols-{Math.min(availableProviders.length, 3)} gap-2">
          {#each availableProviders as providerId}
            <button
              class="p-3 border-2 rounded-lg text-left transition-all {
                selectedProvider === providerId 
                  ? 'border-blue-500 bg-blue-50 text-blue-700' 
                  : 'border-gray-200 hover:border-blue-300'
              }"
              on:click={() => { selectedProvider = providerId; handleProviderChange(); }}
            >
              <div class="font-medium text-sm">{getProviderDisplayName(providerId)}</div>
              <div class="text-xs text-gray-500 mt-1">
                {bulkModelData.provider_models[providerId]?.length || 0} models
              </div>
            </button>
          {/each}
        </div>
      </div>
      
      <!-- Model Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Model
          <span class="text-red-500">*</span>
          {#if recommendedModels.length > 0}
            <span class="text-green-600 text-xs ml-2">
              <i class="fas fa-star"></i> {recommendedModels.length} recommended
            </span>
          {/if}
        </label>
        
        <select 
          bind:value={selectedModel}
          on:change={handleModelChange}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
        >
          {#if recommendedModels.filter(m => m.provider === selectedProvider).length > 0}
            <optgroup label="Recommended for {agentType}">
              {#each recommendedModels.filter(m => m.provider === selectedProvider) as model}
                <option value={model.id}>
                  ⭐ {getModelDisplayName(model)}
                  {#if model.cost_per_1k_tokens}
                    (${model.cost_per_1k_tokens}/1K tokens)
                  {/if}
                </option>
              {/each}
            </optgroup>
          {/if}
          
          <optgroup label="All {getProviderDisplayName(selectedProvider)} Models">
            {#each providerModels as model}
              {#if !recommendedModels.find(r => r.id === model.id)}
                <option value={model.id}>
                  {getModelDisplayName(model)}
                  {#if model.cost_per_1k_tokens}
                    (${model.cost_per_1k_tokens}/1K tokens)
                  {/if}
                </option>
              {/if}
            {/each}
          </optgroup>
        </select>
        
        {#if selectedModelInfo}
          <div class="mt-2 p-3 bg-gray-50 rounded-lg text-xs space-y-1">
            <div class="flex justify-between">
              <span class="text-gray-600">Context Length:</span>
              <span class="font-medium">{selectedModelInfo.context_length?.toLocaleString() || 'Unknown'} tokens</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Cost per 1K tokens:</span>
              <span class="font-medium">${selectedModelInfo.cost_per_1k_tokens || 'Unknown'}</span>
            </div>
            {#if selectedModelInfo.capabilities && selectedModelInfo.capabilities.length > 0}
              <div class="flex items-start">
                <span class="text-gray-600 mr-2">Capabilities:</span>
                <div class="flex flex-wrap gap-1">
                  {#each selectedModelInfo.capabilities.slice(0, 3) as capability}
                    <span class="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">{capability}</span>
                  {/each}
                  {#if selectedModelInfo.capabilities.length > 3}
                    <span class="text-gray-500">+{selectedModelInfo.capabilities.length - 3} more</span>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
      
      <!-- Basic Parameters -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Temperature
            <span class="text-gray-500 text-xs">(0.0 - 2.0)</span>
          </label>
          <input 
            type="number" 
            bind:value={temperature}
            on:input={handleParameterChange}
            min="0" 
            max="2" 
            step="0.1"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
          />
          <div class="text-xs text-gray-500 mt-1">
            {temperature < 0.3 ? 'Very focused' : temperature < 0.7 ? 'Balanced' : 'Creative'}
          </div>
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Max Tokens
            <span class="text-gray-500 text-xs">(1 - 32000)</span>
          </label>
          <input 
            type="number" 
            bind:value={maxTokens}
            on:input={handleParameterChange}
            min="1" 
            max="32000"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
          />
          <div class="text-xs text-gray-500 mt-1">
            Estimated cost: ${estimatedCost.toFixed(4)}
          </div>
        </div>
      </div>
      
      <!-- Advanced Parameters Toggle -->
      <div>
        <button 
          class="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
          on:click={() => showAdvanced = !showAdvanced}
        >
          <i class="fas fa-chevron-{showAdvanced ? 'up' : 'down'}"></i>
          <span>Advanced Parameters</span>
        </button>
        
        {#if showAdvanced}
          <div class="mt-4 space-y-4 p-4 bg-gray-50 rounded-lg">
            <div class="grid grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Top P
                  <span class="text-gray-500 text-xs">(0.0 - 1.0)</span>
                </label>
                <input 
                  type="number" 
                  bind:value={topP}
                  on:input={handleParameterChange}
                  min="0" 
                  max="1" 
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
                />
              </div>
              
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Frequency Penalty
                  <span class="text-gray-500 text-xs">(-2.0 - 2.0)</span>
                </label>
                <input 
                  type="number" 
                  bind:value={frequencyPenalty}
                  on:input={handleParameterChange}
                  min="-2" 
                  max="2" 
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
                />
              </div>
              
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Presence Penalty
                  <span class="text-gray-500 text-xs">(-2.0 - 2.0)</span>
                </label>
                <input 
                  type="number" 
                  bind:value={presencePenalty}
                  on:input={handleParameterChange}
                  min="-2" 
                  max="2" 
                  step="0.1"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
                />
              </div>
            </div>
          </div>
        {/if}
      </div>
      
      <!-- Configuration Summary -->
      <div class="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div class="flex items-center justify-between text-sm">
          <div class="flex items-center space-x-2">
            <i class="fas fa-info-circle text-blue-600"></i>
            <span class="font-medium text-blue-900">Configuration Summary</span>
          </div>
          <div class="text-blue-700">
            {getProviderDisplayName(selectedProvider)} • {getModelDisplayName(selectedModelInfo || { id: selectedModel, display_name: selectedModel })}
          </div>
        </div>
        <div class="mt-2 text-xs text-blue-700">
          Temperature: {temperature} • Max Tokens: {maxTokens} • Estimated Cost: ${estimatedCost.toFixed(4)}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .llm-config-component {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  
  /* Custom grid classes for dynamic provider count */
  :global(.grid-cols-1) { grid-template-columns: repeat(1, minmax(0, 1fr)); }
  :global(.grid-cols-2) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  :global(.grid-cols-3) { grid-template-columns: repeat(3, minmax(0, 1fr)); }
</style>
