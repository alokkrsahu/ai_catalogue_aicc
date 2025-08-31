// 🤖 PHASE 3: Multi-Provider LLM Configuration Service - Enhanced AutoGen Integration
import { 
  type LLMProvider, 
  type LLMModel, 
  type AgentLLMConfig,
  type EnhancedLLMProvider,
  type EnhancedLLMModel,
  type MultiProviderLLMConfig,
  type LLMProviderStatus,
  DEFAULT_LLM_PROVIDERS,
  DEFAULT_LLM_MODELS,
  DEFAULT_AGENT_LLM_CONFIGS,
  PROVIDER_OPTIMIZATION_PROFILES,
  AGENT_TYPE_LLM_RECOMMENDATIONS,
  getProviderIcon,
  getProviderColor,
  formatCost,
  getCapabilityIcon,
  getRecommendedProvidersForAgent,
  getOptimizationProfile
} from '$lib/types/llm-config';

class MultiProviderLLMConfigurationService {
  private baseUrl = '/api/llm';
  private cache: {
    providers: EnhancedLLMProvider[];
    models: EnhancedLLMModel[];
    lastFetch: number;
  } = {
    providers: [],
    models: [],
    lastFetch: 0
  };
  private cacheTimeout = 5 * 60 * 1000; // 5 minutes

  constructor() {
    console.log('🤖 MULTI-LLM SERVICE: Initialized multi-provider LLM configuration service');
  }

  /**
   * 🌐 Get all available LLM providers with real-time status
   */
  async getProviders(): Promise<EnhancedLLMProvider[]> {
    try {
      console.log('📋 MULTI-LLM SERVICE: Fetching LLM providers with status');
      
      // Check cache first
      const now = Date.now();
      if (this.cache.providers.length > 0 && (now - this.cache.lastFetch) < this.cacheTimeout) {
        console.log('✅ MULTI-LLM SERVICE: Using cached providers');
        return this.cache.providers;
      }
      
      const response = await fetch(`${this.baseUrl}/providers/`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      const providers = data.providers || [];
      
      // Enhance providers with UI helpers
      const enhancedProviders: EnhancedLLMProvider[] = providers.map((provider: any) => ({
        ...provider,
        icon: provider.icon || getProviderIcon(provider.id),
        rate_limits: provider.rate_limits || {},
        status: provider.status || {
          available: false,
          provider_name: provider.name,
          requires_api_key: provider.api_key_required,
          api_key_configured: false,
          supported_features: provider.supported_features || [],
          rate_limits: provider.rate_limits || {}
        }
      }));
      
      // Update cache
      this.cache.providers = enhancedProviders;
      this.cache.lastFetch = now;
      
      console.log(`✅ MULTI-LLM SERVICE: Loaded ${enhancedProviders.length} providers`);
      console.log(`📊 MULTI-LLM SERVICE: Available providers: ${enhancedProviders.filter(p => p.status.available).length}`);
      
      return enhancedProviders;
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Failed to load providers:', error);
      // Fallback to default providers with unknown status
      return DEFAULT_LLM_PROVIDERS.map(provider => ({
        ...provider,
        rate_limits: {},
        status: {
          available: false,
          provider_name: provider.name,
          requires_api_key: provider.apiKeyRequired,
          api_key_configured: false,
          supported_features: provider.supportedFeatures,
          rate_limits: {},
          error: 'Failed to check provider status'
        }
      }));
    }
  }

  /**
   * 🤖 Get all available LLM models with enhanced metadata
   */
  async getModels(providerId?: string, agentType?: string): Promise<EnhancedLLMModel[]> {
    try {
      console.log('📋 MULTI-LLM SERVICE: Fetching LLM models', { providerId, agentType });
      
      const params = new URLSearchParams();
      if (providerId) params.append('provider_id', providerId);
      if (agentType) params.append('agent_type', agentType);
      
      const response = await fetch(`${this.baseUrl}/models/?${params}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      let models = data.models || [];
      
      // Enhance models with UI helpers and recommendations
      const enhancedModels: EnhancedLLMModel[] = models.map((model: any) => ({
        ...model,
        recommended_for: model.recommended_for || [],
        cost_per_1k_tokens: model.cost_per_token * 1000,
        optimization_score: this.calculateOptimizationScore(model, agentType),
        capabilities: model.capabilities || [],
        contextWindow: model.context_window || model.contextWindow || 8192,
        maxTokens: model.max_tokens || model.maxTokens || 2048,
        supportsStreaming: model.supports_streaming ?? model.supportsStreaming ?? true,
        supportsFunctionCalling: model.supports_function_calling ?? model.supportsFunctionCalling ?? false,
        costPerToken: model.cost_per_token || model.costPerToken || 0.00001
      }));
      
      // Sort by optimization score if agent type provided
      if (agentType) {
        enhancedModels.sort((a, b) => b.optimization_score - a.optimization_score);
      }
      
      console.log(`✅ MULTI-LLM SERVICE: Loaded ${enhancedModels.length} models`);
      return enhancedModels;
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Failed to load models:', error);
      // Fallback to default models
      let fallbackModels = DEFAULT_LLM_MODELS;
      
      if (providerId) {
        fallbackModels = fallbackModels.filter(m => m.providerId === providerId);
      }
      
      return fallbackModels.map(model => ({
        ...model,
        recommended_for: this.getModelRecommendations(model.id),
        cost_per_1k_tokens: model.costPerToken * 1000,
        optimization_score: this.calculateOptimizationScore(model, agentType)
      }));
    }
  }

  /**
   * 🎯 Get recommended models for specific agent type
   */
  async getRecommendedModelsForAgent(agentType: string): Promise<EnhancedLLMModel[]> {
    try {
      console.log(`🎯 MULTI-LLM SERVICE: Getting recommended models for ${agentType}`);
      
      const models = await this.getModels(undefined, agentType);
      const recommendations = AGENT_TYPE_LLM_RECOMMENDATIONS[agentType];
      const recommendedProviders = recommendations?.recommended_providers || ['openai'];
      
      // Filter and sort by recommendations
      const recommendedModels = models
        .filter(model => 
          recommendedProviders.includes(model.providerId) ||
          model.recommended_for.includes(agentType)
        )
        .sort((a, b) => {
          // Sort by optimization score, then by cost effectiveness
          if (b.optimization_score !== a.optimization_score) {
            return b.optimization_score - a.optimization_score;
          }
          return a.cost_per_1k_tokens - b.cost_per_1k_tokens;
        })
        .slice(0, 10); // Top 10 recommendations
      
      console.log(`✅ MULTI-LLM SERVICE: Found ${recommendedModels.length} recommended models for ${agentType}`);
      return recommendedModels;
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Failed to get recommendations:', error);
      return [];
    }
  }

  /**
   * 🔧 Get LLM configuration for a specific agent
   */
  async getAgentLLMConfig(projectId: string, agentId: string): Promise<MultiProviderLLMConfig | null> {
    try {
      console.log('🎯 MULTI-LLM SERVICE: Fetching agent LLM config', { projectId, agentId });
      
      const response = await fetch(`${this.baseUrl}/projects/${projectId}/agents/${agentId}/config/`);
      if (!response.ok) {
        if (response.status === 404) {
          console.log('⚠️ MULTI-LLM SERVICE: Agent config not found, will use defaults');
          return null;
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('✅ MULTI-LLM SERVICE: Agent LLM config loaded');
      
      return data as MultiProviderLLMConfig;
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Failed to load agent config:', error);
      return null;
    }
  }

  /**
   * 💾 Update LLM configuration for a specific agent
   */
  async updateAgentLLMConfig(projectId: string, agentId: string, config: Partial<AgentLLMConfig>): Promise<MultiProviderLLMConfig> {
    try {
      console.log('💾 MULTI-LLM SERVICE: Updating agent LLM config', { projectId, agentId });
      
      const response = await fetch(`${this.baseUrl}/projects/${projectId}/agents/${agentId}/config/update/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
      }
      
      const updatedConfig = await response.json();
      console.log('✅ MULTI-LLM SERVICE: Agent LLM config updated successfully');
      
      return updatedConfig;
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Failed to update agent config:', error);
      throw error;
    }
  }

  /**
   * 🎯 Get default LLM configuration for an agent type
   */
  async getDefaultConfigForAgentType(agentType: string): Promise<AgentLLMConfig> {
    try {
      console.log(`🎯 MULTI-LLM SERVICE: Getting default config for ${agentType}`);
      
      const response = await fetch(`${this.baseUrl}/defaults/${agentType}/`);
      if (!response.ok) {
        console.log('⚠️ MULTI-LLM SERVICE: Using local defaults');
        return this.getLocalDefaultConfig(agentType);
      }
      
      const data = await response.json();
      console.log(`✅ MULTI-LLM SERVICE: Default config loaded for ${agentType}`);
      
      return data.default_config;
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Failed to load default config:', error);
      return this.getLocalDefaultConfig(agentType);
    }
  }

  /**
   * 🔍 Validate LLM configuration
   */
  async validateConfig(config: Partial<AgentLLMConfig>): Promise<{ valid: boolean; errors: string[]; warnings: string[] }> {
    try {
      console.log('🔍 MULTI-LLM SERVICE: Validating LLM configuration');
      
      const response = await fetch(`${this.baseUrl}/validate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config)
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      const validation = data.validation_result;
      
      console.log(`✅ MULTI-LLM SERVICE: Configuration validation completed (valid: ${validation.valid})`);
      return validation;
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Validation failed:', error);
      // Fallback to local validation
      return this.validateConfigLocally(config);
    }
  }

  /**
   * 💰 Calculate cost estimate for configuration
   */
  async calculateCostEstimate(config: Partial<AgentLLMConfig>, estimatedTokens: number = 1000, workflowComplexity: string = 'medium'): Promise<{
    cost: number;
    currency: string;
    breakdown: any;
  }> {
    try {
      console.log('💰 MULTI-LLM SERVICE: Calculating cost estimate');
      
      const response = await fetch(`${this.baseUrl}/cost-estimate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...config,
          estimated_tokens: estimatedTokens,
          workflow_complexity: workflowComplexity
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log(`✅ MULTI-LLM SERVICE: Cost estimate calculated: $${data.cost_estimate.cost}`);
      
      return {
        cost: data.cost_estimate.cost,
        currency: data.cost_estimate.currency,
        breakdown: data.cost_breakdown
      };
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Cost calculation failed:', error);
      // Fallback to local calculation
      return this.calculateCostLocally(config, estimatedTokens);
    }
  }

  /**
   * 📊 Get configuration summary with provider and model info
   */
  async getConfigSummary(config: Partial<AgentLLMConfig>): Promise<{
    provider: any;
    model: any;
    parameters: any;
    cost_estimate: any;
    recommendations: any;
  }> {
    try {
      const [providers, models] = await Promise.all([
        this.getProviders(),
        this.getModels()
      ]);
      
      const provider = providers.find(p => p.id === config.providerId);
      const model = models.find(m => m.id === config.modelId);
      
      const costEstimate = await this.calculateCostEstimate(config).catch(() => ({ cost: 0, currency: 'USD', breakdown: {} }));
      
      return {
        provider: provider ? {
          id: provider.id,
          name: provider.name,
          description: provider.description,
          status: provider.status,
          icon: provider.icon
        } : null,
        model: model ? {
          id: model.id,
          name: model.name,
          description: model.description,
          context_window: model.contextWindow,
          cost_per_1k: model.cost_per_1k_tokens,
          capabilities: model.capabilities,
          supports_streaming: model.supportsStreaming,
          supports_function_calling: model.supportsFunctionCalling
        } : null,
        parameters: {
          temperature: config.temperature || 0.7,
          max_tokens: config.maxTokens || 2048,
          top_p: config.topP || 1.0
        },
        cost_estimate: costEstimate,
        recommendations: {
          optimization_suggestions: await this.getOptimizationSuggestions(config),
          alternative_models: await this.getAlternativeModels(config)
        }
      };
      
    } catch (error) {
      console.error('❌ MULTI-LLM SERVICE: Failed to get config summary:', error);
      return {
        provider: null,
        model: null,
        parameters: {},
        cost_estimate: { cost: 0, currency: 'USD', breakdown: {} },
        recommendations: {}
      };
    }
  }

  /**
   * 🚀 Get optimization profile recommendations
   */
  getOptimizationProfiles(): Record<string, any> {
    return PROVIDER_OPTIMIZATION_PROFILES;
  }

  /**
   * 🎯 Apply optimization profile to configuration
   */
  async applyOptimizationProfile(config: Partial<AgentLLMConfig>, profileName: string, agentType: string): Promise<AgentLLMConfig> {
    const profile = getOptimizationProfile(profileName);
    const models = await this.getModels();
    
    // Find best model from preferred models that exists
    let selectedModel = null;
    for (const preferredModelId of profile.preferred_models) {
      const model = models.find(m => m.id === preferredModelId);
      if (model) {
        selectedModel = model;
        break;
      }
    }
    
    // If no preferred model found, use current or default
    if (!selectedModel) {
      selectedModel = models.find(m => m.id === config.modelId) || models[0];
    }
    
    const optimizedConfig: AgentLLMConfig = {
      agentId: config.agentId || '',
      agentName: config.agentName || '',
      providerId: selectedModel?.providerId || config.providerId || 'openai',
      modelId: selectedModel?.id || config.modelId || 'gpt-4',
      temperature: this.getOptimalTemperature(profileName, agentType),
      maxTokens: this.getOptimalMaxTokens(profileName, agentType),
      topP: config.topP || 1.0,
      frequencyPenalty: config.frequencyPenalty || 0.0,
      presencePenalty: config.presencePenalty || 0.0,
      customConfig: config.customConfig || {}
    };
    
    console.log(`🚀 MULTI-LLM SERVICE: Applied ${profileName} profile to ${agentType}`);
    return optimizedConfig;
  }

  // Private helper methods
  private calculateOptimizationScore(model: any, agentType?: string): number {
    let score = 0;
    
    // Base score from capabilities
    score += model.capabilities?.length * 10 || 0;
    
    // Cost effectiveness (lower cost = higher score)
    const costPer1K = model.cost_per_token * 1000;
    score += Math.max(0, 50 - costPer1K * 10000);
    
    // Context window bonus
    const contextWindow = model.context_window || model.contextWindow || 8192;
    score += Math.min(30, contextWindow / 1000);
    
    // Agent type specific bonuses
    if (agentType && model.recommended_for?.includes(agentType)) {
      score += 50;
    }
    
    return Math.round(score);
  }

  private getModelRecommendations(modelId: string): string[] {
    // Map models to agent types they work well with
    const recommendations: Record<string, string[]> = {
      'gpt-4': ['AssistantAgent', 'GroupChatManager'],
      'gpt-4-turbo': ['AssistantAgent', 'GroupChatManager', 'UserProxyAgent'],
      'gpt-3.5-turbo': ['UserProxyAgent', 'FunctionTool'],
      'claude-3-opus': ['AssistantAgent', 'GroupChatManager'],
      'claude-3-sonnet': ['AssistantAgent', 'UserProxyAgent', 'GroupChatManager'],
      'claude-3-haiku': ['UserProxyAgent', 'FunctionTool'],
      'gemini-pro': ['AssistantAgent', 'GroupChatManager'],
      'gemini-pro-vision': ['AssistantAgent', 'UserProxyAgent']
    };
    
    return recommendations[modelId] || [];
  }

  private getLocalDefaultConfig(agentType: string): AgentLLMConfig {
    const defaults = DEFAULT_AGENT_LLM_CONFIGS[agentType] || DEFAULT_AGENT_LLM_CONFIGS['AssistantAgent'];
    
    return {
      agentId: '',
      agentName: '',
      providerId: defaults.providerId || 'openai',
      modelId: defaults.modelId || 'gpt-4',
      temperature: defaults.temperature || 0.7,
      maxTokens: defaults.maxTokens || 2048,
      topP: defaults.topP || 1.0,
      frequencyPenalty: defaults.frequencyPenalty || 0.0,
      presencePenalty: defaults.presencePenalty || 0.0,
      customConfig: defaults.customConfig || {}
    };
  }

  private validateConfigLocally(config: Partial<AgentLLMConfig>): { valid: boolean; errors: string[]; warnings: string[] } {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!config.providerId) errors.push('Provider is required');
    if (!config.modelId) errors.push('Model is required');
    
    const temperature = config.temperature;
    if (temperature !== undefined && (temperature < 0 || temperature > 2)) {
      errors.push('Temperature must be between 0 and 2');
    }
    
    const maxTokens = config.maxTokens;
    if (maxTokens !== undefined && (maxTokens < 1 || maxTokens > 32000)) {
      errors.push('Max tokens must be between 1 and 32000');
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings
    };
  }

  private async calculateCostLocally(config: Partial<AgentLLMConfig>, estimatedTokens: number): Promise<{ cost: number; currency: string; breakdown: any }> {
    const models = await this.getModels();
    const model = models.find(m => m.id === config.modelId);
    
    const cost = model ? model.costPerToken * estimatedTokens : 0;
    
    return {
      cost,
      currency: 'USD',
      breakdown: {
        base_tokens: estimatedTokens,
        cost_per_token: model?.costPerToken || 0,
        model: model?.name || 'Unknown'
      }
    };
  }

  private async getOptimizationSuggestions(config: Partial<AgentLLMConfig>): Promise<string[]> {
    const suggestions: string[] = [];
    
    // Temperature suggestions
    if (config.temperature && config.temperature > 1.0) {
      suggestions.push('Consider lowering temperature for more consistent responses');
    }
    
    // Token efficiency suggestions
    if (config.maxTokens && config.maxTokens > 4000) {
      suggestions.push('High max tokens may increase costs - consider if needed');
    }
    
    return suggestions;
  }

  private async getAlternativeModels(config: Partial<AgentLLMConfig>): Promise<any[]> {
    if (!config.modelId) return [];
    
    const models = await this.getModels();
    const currentModel = models.find(m => m.id === config.modelId);
    
    if (!currentModel) return [];
    
    // Find similar models with different cost/performance profiles
    return models
      .filter(m => 
        m.id !== config.modelId && 
        m.providerId !== currentModel.providerId &&
        m.capabilities.some(cap => currentModel.capabilities.includes(cap))
      )
      .slice(0, 3);
  }

  private getOptimalTemperature(profileName: string, agentType: string): number {
    const profiles = {
      'cost_effective': 0.3,
      'performance': 0.7,
      'balanced': 0.5,
      'large_context': 0.4
    };
    
    return profiles[profileName as keyof typeof profiles] || 0.7;
  }

  private getOptimalMaxTokens(profileName: string, agentType: string): number {
    const profiles = {
      'cost_effective': 1024,
      'performance': 3000,
      'balanced': 2048,
      'large_context': 4000
    };
    
    return profiles[profileName as keyof typeof profiles] || 2048;
  }
}

// Export singleton instance
export const multiProviderLLMService = new MultiProviderLLMConfigurationService();

// Export utility functions and types
export {
  DEFAULT_LLM_PROVIDERS,
  DEFAULT_LLM_MODELS,
  DEFAULT_AGENT_LLM_CONFIGS,
  PROVIDER_OPTIMIZATION_PROFILES,
  AGENT_TYPE_LLM_RECOMMENDATIONS,
  getProviderIcon,
  getProviderColor,
  formatCost,
  getCapabilityIcon,
  getRecommendedProvidersForAgent,
  getOptimizationProfile
} from '$lib/types/llm-config';

export type {
  LLMProvider,
  LLMModel,
  AgentLLMConfig,
  EnhancedLLMProvider,
  EnhancedLLMModel,
  MultiProviderLLMConfig,
  LLMProviderStatus
} from '$lib/types/llm-config';
