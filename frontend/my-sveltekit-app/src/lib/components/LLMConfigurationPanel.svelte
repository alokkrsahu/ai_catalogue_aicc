<!-- LLMConfigurationPanel.svelte - Agent LLM Configuration Interface -->
<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import { llmConfigService } from '$lib/services/llmConfigService';
  import type { LLMProvider, LLMModel, AgentLLMConfig } from '$lib/types/llm-config';
  import { toasts } from '$lib/stores/toast';
  
  export let agentId: string;
  export let agentName: string;
  export let agentType: string;
  export let currentConfig: AgentLLMConfig | null = null;
  
  const dispatch = createEventDispatcher();
  
  // State
  let providers: LLMProvider[] = [];
  let models: LLMModel[] = [];
  let filteredModels: LLMModel[] = [];
  let loading = true;
  let saving = false;
  
  // Configuration state
  let config: AgentLLMConfig;
  let selectedProvider: LLMProvider | null = null;
  let selectedModel: LLMModel | null = null;
  let estimatedCostPer1K = 0;
  
  // Validation
  let validationErrors: string[] = [];
  
  // UI state
  let showAdvancedSettings = false;
  
  console.log(`🔧 LLM CONFIG PANEL: Initializing for agent ${agentId} (${agentType})`);
  
  onMount(() => {
    loadConfigurationData();
  });
  
  async function loadConfigurationData() {
    try {
      loading = true;
      
      // Load providers and models
      [providers, models] = await Promise.all([
        llmConfigService.getProviders(),
        llmConfigService.getModels()
      ]);
      
      // Initialize configuration
      if (currentConfig) {
        config = { ...currentConfig };
      } else {
        // Use defaults for agent type
        const defaults = llmConfigService.getDefaultConfigForAgentType(agentType);
        config = llmConfigService.getCompleteAgentConfig(agentId, agentName, agentType, defaults);
      }
      
      // Update UI state
      await updateProviderAndModel();
      
      console.log('✅ LLM CONFIG PANEL: Configuration loaded', {
        providers: providers.length,
        models: models.length,
        currentProvider: config.providerId,
        currentModel: config.modelId
      });
      
    } catch (error) {
      console.error('❌ LLM CONFIG PANEL: Failed to load configuration:', error);
      toasts.error('Failed to load LLM configuration');
    } finally {
      loading = false;
    }
  }
  
  async function updateProviderAndModel() {
    // Find selected provider and model
    selectedProvider = providers.find(p => p.id === config.providerId) || null;
    selectedModel = models.find(m => m.id === config.modelId) || null;
    
    // Filter models for selected provider
    filteredModels = models.filter(m => m.providerId === config.providerId);
    
    // Calculate estimated cost
    if (selectedModel) {
      estimatedCostPer1K = selectedModel.costPerToken * 1000;
    }
    
    // Validate configuration
    const validation = llmConfigService.validateConfig(config);
    validationErrors = validation.errors;
  }
  
  async function handleProviderChange() {
    console.log('🔄 LLM CONFIG PANEL: Provider changed to', config.providerId);
    
    // Filter models for new provider
    filteredModels = models.filter(m => m.providerId === config.providerId);
    
    // Reset model if it doesn't belong to new provider
    if (!filteredModels.find(m => m.id === config.modelId)) {
      if (filteredModels.length > 0) {
        config.modelId = filteredModels[0].id;
      }
    }
    
    await updateProviderAndModel();
  }
  
  async function handleModelChange() {
    console.log('🔄 LLM CONFIG PANEL: Model changed to', config.modelId);
    await updateProviderAndModel();
  }
  
  async function saveConfiguration() {
    if (saving) return;
    
    try {
      saving = true;
      
      // Validate configuration
      const validation = llmConfigService.validateConfig(config);
      if (!validation.valid) {
        toasts.error(`Configuration invalid: ${validation.errors.join(', ')}`);
        return;
      }
      
      console.log('💾 LLM CONFIG PANEL: Saving configuration', config);
      
      // Save via service (will extend to API later)
      const savedConfig = await llmConfigService.updateAgentLLMConfig('', agentId, config);
      
      // Notify parent component
      dispatch('configurationUpdate', savedConfig);
      
      toasts.success('LLM configuration saved successfully');
      console.log('✅ LLM CONFIG PANEL: Configuration saved');
      
    } catch (error) {
      console.error('❌ LLM CONFIG PANEL: Save failed:', error);
      toasts.error(`Save failed: ${error.message}`);
    } finally {
      saving = false;
    }
  }
  
  function resetToDefaults() {
    const defaults = llmConfigService.getDefaultConfigForAgentType(agentType);
    config = llmConfigService.getCompleteAgentConfig(agentId, agentName, agentType, defaults);
    updateProviderAndModel();
    
    toasts.info('Configuration reset to defaults');
    console.log('🔄 LLM CONFIG PANEL: Reset to defaults');
  }
  
  function getProviderIcon(provider: LLMProvider): string {
    return provider.icon;
  }
  
  function getProviderColor(providerId: string): string {
    const colors: Record<string, string> = {
      'openai': 'text-green-600',
      'anthropic': 'text-orange-600',
      'google': 'text-blue-600',
      'local': 'text-gray-600',
      'custom': 'text-purple-600'
    };
    return colors[providerId] || 'text-gray-600';
  }
  
  function formatCost(cost: number): string {
    if (cost < 0.001) {
      return '<$0.001';
    }
    return `$${cost.toFixed(4)}`;
  }
</script>

<div class="llm-config-panel bg-white border rounded-lg p-4 shadow-sm">
  <!-- Header -->
  <div class="flex items-center justify-between mb-4">
    <div>
      <h4 class="font-semibold text-gray-900 flex items-center">
        <i class="fas fa-brain mr-2 text-oxford-blue"></i>
        LLM Configuration
      </h4>
      <p class="text-sm text-gray-600">Configure AI model for this agent</p>
    </div>
    
    {#if validationErrors.length > 0}
      <div class="text-red-600 text-sm">
        <i class="fas fa-exclamation-triangle mr-1"></i>
        {validationErrors.length} error(s)
      </div>
    {/if}
  </div>
  
  {#if loading}
    <!-- Loading State -->
    <div class="flex items-center justify-center py-8">
      <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-oxford-blue mr-3"></div>
      <span class="text-gray-600">Loading LLM configuration...</span>
    </div>
  {:else}
    <!-- Configuration Form -->
    <div class="space-y-4">
      <!-- Provider Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          <i class="fas fa-server mr-1"></i>
          LLM Provider
        </label>
        <select
          bind:value={config.providerId}
          on:change={handleProviderChange}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue transition-colors"
        >
          {#each providers as provider}
            <option value={provider.id}>{provider.name}</option>
          {/each}
        </select>
        
        {#if selectedProvider}
          <div class="mt-2 p-2 bg-gray-50 rounded text-xs">
            <div class="flex items-center text-gray-600">
              <i class="fas {getProviderIcon(selectedProvider)} mr-2 {getProviderColor(selectedProvider.id)}"></i>
              <span>{selectedProvider.description}</span>
            </div>
            <div class="mt-1 flex flex-wrap gap-1">
              {#each selectedProvider.supportedFeatures as feature}
                <span class="inline-block bg-gray-200 text-gray-700 px-2 py-0.5 rounded text-xs">{feature}</span>
              {/each}
            </div>
          </div>
        {/if}
      </div>
      
      <!-- Model Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          <i class="fas fa-robot mr-1"></i>
          LLM Model
        </label>
        <select
          bind:value={config.modelId}
          on:change={handleModelChange}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue transition-colors"
        >
          {#each filteredModels as model}
            <option value={model.id}>{model.name}</option>
          {/each}
        </select>
        
        {#if selectedModel}
          <div class="mt-2 p-2 bg-gray-50 rounded text-xs">
            <div class="text-gray-600 mb-1">{selectedModel.description}</div>
            <div class="grid grid-cols-2 gap-2 text-gray-500">
              <div class="flex items-center">
                <i class="fas fa-memory mr-1"></i>
                {selectedModel.contextWindow.toLocaleString()} tokens
              </div>
              <div class="flex items-center">
                <i class="fas fa-dollar-sign mr-1"></i>
                {formatCost(estimatedCostPer1K)}/1K tokens
              </div>
            </div>
            <div class="mt-1 flex flex-wrap gap-1">
              {#each selectedModel.capabilities as capability}
                <span class="inline-block bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs">{capability}</span>
              {/each}
            </div>
          </div>
        {/if}
      </div>
      
      <!-- Basic Settings -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Temperature
            <span class="text-xs text-gray-500">(0-2)</span>
          </label>
          <input
            type="number"
            min="0"
            max="2"
            step="0.1"
            bind:value={config.temperature}
            class="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Max Tokens
          </label>
          <input
            type="number"
            min="1"
            max="32000"
            bind:value={config.maxTokens}
            class="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          />
        </div>
      </div>
      
      <!-- Advanced Settings Toggle -->
      <button
        class="text-sm text-oxford-blue hover:text-blue-700 flex items-center transition-colors"
        on:click={() => showAdvancedSettings = !showAdvancedSettings}
      >
        <i class="fas fa-{showAdvancedSettings ? 'chevron-up' : 'chevron-down'} mr-2"></i>
        Advanced Settings
      </button>
      
      {#if showAdvancedSettings}
        <div class="space-y-3 p-3 bg-gray-50 rounded-lg">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                Top P
                <span class="text-xs text-gray-500">(0-1)</span>
              </label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.1"
                bind:value={config.topP}
                class="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">
                Frequency Penalty
                <span class="text-xs text-gray-500">(-2 to 2)</span>
              </label>
              <input
                type="number"
                min="-2"
                max="2"
                step="0.1"
                bind:value={config.frequencyPenalty}
                class="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
              />
            </div>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Presence Penalty
              <span class="text-xs text-gray-500">(-2 to 2)</span>
            </label>
            <input
              type="number"
              min="-2"
              max="2"
              step="0.1"
              bind:value={config.presencePenalty}
              class="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              System Message (Optional)
            </label>
            <textarea
              bind:value={config.systemMessage}
              placeholder="Custom system message for this agent..."
              rows="3"
              class="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
            ></textarea>
          </div>
        </div>
      {/if}
      
      <!-- Validation Errors -->
      {#if validationErrors.length > 0}
        <div class="p-3 bg-red-50 border border-red-200 rounded-lg">
          <div class="text-red-800 text-sm font-medium mb-1">
            <i class="fas fa-exclamation-triangle mr-1"></i>
            Configuration Errors:
          </div>
          <ul class="text-red-700 text-sm space-y-1">
            {#each validationErrors as error}
              <li>• {error}</li>
            {/each}
          </ul>
        </div>
      {/if}
      
      <!-- Action Buttons -->
      <div class="flex items-center justify-between pt-3 border-t border-gray-200">
        <button
          class="text-sm text-gray-600 hover:text-gray-800 transition-colors"
          on:click={resetToDefaults}
        >
          <i class="fas fa-undo mr-1"></i>
          Reset to Defaults
        </button>
        
        <div class="flex space-x-2">
          <button
            class="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
            on:click={() => dispatch('close')}
          >
            Cancel
          </button>
          
          <button
            class="px-3 py-1.5 text-sm bg-oxford-blue text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            on:click={saveConfiguration}
            disabled={saving || validationErrors.length > 0}
          >
            {#if saving}
              <i class="fas fa-spinner fa-spin mr-1"></i>
              Saving...
            {:else}
              <i class="fas fa-save mr-1"></i>
              Save Configuration
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .llm-config-panel {
    font-size: 14px;
  }
  
  :global(.oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  
  :global(.focus\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  :global(.focus\:border-oxford-blue:focus) {
    border-color: #002147;
  }
</style>
