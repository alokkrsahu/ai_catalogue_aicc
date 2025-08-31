// LLM Configuration Service - Template Independent Agent LLM Management
import { 
  type LLMProvider, 
  type LLMModel, 
  type AgentLLMConfig,
  DEFAULT_LLM_PROVIDERS,
  DEFAULT_LLM_MODELS,
  DEFAULT_AGENT_LLM_CONFIGS
} from '$lib/types/llm-config';

class LLMConfigurationService {
  private baseUrl = '/api';

  constructor() {
    console.log('🤖 LLM CONFIG: Service initialized');
  }

  /**
   * Get all available LLM providers
   */
  async getProviders(): Promise<LLMProvider[]> {
    try {
      console.log('📋 LLM CONFIG: Fetching LLM providers');
      
      // For now, return default providers - extend to API when backend is ready
      const providers = DEFAULT_LLM_PROVIDERS;
      
      console.log(`✅ LLM CONFIG: Loaded ${providers.length} providers`);
      return providers;
      
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to load providers:', error);
      // Fallback to default providers
      return DEFAULT_LLM_PROVIDERS;
    }
  }

  /**
   * Get all available LLM models
   */
  async getModels(providerId?: string): Promise<LLMModel[]> {
    try {
      console.log('📋 LLM CONFIG: Fetching LLM models', { providerId });
      
      let models = DEFAULT_LLM_MODELS;
      
      // Filter by provider if specified
      if (providerId) {
        models = models.filter(model => model.providerId === providerId);
      }
      
      console.log(`✅ LLM CONFIG: Loaded ${models.length} models`);
      return models;
      
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to load models:', error);
      return DEFAULT_LLM_MODELS;
    }
  }

  /**
   * Get LLM configuration for a specific agent
   */
  async getAgentLLMConfig(projectId: string, agentId: string): Promise<AgentLLMConfig | null> {
    try {
      console.log('🎯 LLM CONFIG: Fetching agent LLM config', { projectId, agentId });
      
      // TODO: Implement API call when backend is ready
      // const response = await fetch(`${this.baseUrl}/projects/${projectId}/agents/${agentId}/llm-config`);
      // if (!response.ok) throw new Error('Failed to fetch agent LLM config');
      // return await response.json();
      
      // For now, return null (will use defaults)
      return null;
      
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to load agent config:', error);
      return null;
    }
  }

  /**
   * Update LLM configuration for a specific agent
   */
  async updateAgentLLMConfig(projectId: string, agentId: string, config: AgentLLMConfig): Promise<AgentLLMConfig> {
    try {
      console.log('💾 LLM CONFIG: Updating agent LLM config', { projectId, agentId });
      
      // TODO: Implement API call when backend is ready
      // const response = await fetch(`${this.baseUrl}/projects/${projectId}/agents/${agentId}/llm-config`, {
      //   method: 'PUT',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(config)
      // });
      // if (!response.ok) throw new Error('Failed to update agent LLM config');
      // const updatedConfig = await response.json();
      
      console.log('✅ LLM CONFIG: Agent LLM config updated successfully');
      return config; // Return the config for now
      
    } catch (error) {
      console.error('❌ LLM CONFIG: Failed to update agent config:', error);
      throw error;
    }
  }

  /**
   * Get default LLM configuration for an agent type
   */
  getDefaultConfigForAgentType(agentType: string): Partial<AgentLLMConfig> {
    const defaultConfig = DEFAULT_AGENT_LLM_CONFIGS[agentType];
    
    if (defaultConfig) {
      console.log(`🎯 LLM CONFIG: Using default config for ${agentType}`);
      return defaultConfig;
    }
    
    console.log(`⚠️ LLM CONFIG: No default config for ${agentType}, using AssistantAgent defaults`);
    return DEFAULT_AGENT_LLM_CONFIGS['AssistantAgent'];
  }

  /**
   * Get a complete LLM configuration with defaults filled in
   */
  getCompleteAgentConfig(
    agentId: string,
    agentName: string,
    agentType: string,
    partialConfig?: Partial<AgentLLMConfig>
  ): AgentLLMConfig {
    const defaults = this.getDefaultConfigForAgentType(agentType);
    
    return {
      agentId,
      agentName,
      providerId: partialConfig?.providerId || defaults.providerId || 'openai',
      modelId: partialConfig?.modelId || defaults.modelId || 'gpt-4',
      temperature: partialConfig?.temperature ?? defaults.temperature ?? 0.7,
      maxTokens: partialConfig?.maxTokens || defaults.maxTokens || 2048,
      topP: partialConfig?.topP ?? defaults.topP ?? 1.0,
      frequencyPenalty: partialConfig?.frequencyPenalty ?? defaults.frequencyPenalty ?? 0.0,
      presencePenalty: partialConfig?.presencePenalty ?? defaults.presencePenalty ?? 0.0,
      customConfig: partialConfig?.customConfig || defaults.customConfig || {},
      systemMessage: partialConfig?.systemMessage || defaults.systemMessage
    };
  }

  /**
   * Validate LLM configuration
   */
  validateConfig(config: AgentLLMConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!config.agentId) {
      errors.push('Agent ID is required');
    }

    if (!config.agentName) {
      errors.push('Agent name is required');
    }

    if (!config.providerId) {
      errors.push('LLM provider is required');
    }

    if (!config.modelId) {
      errors.push('LLM model is required');
    }

    if (config.temperature < 0 || config.temperature > 2) {
      errors.push('Temperature must be between 0 and 2');
    }

    if (config.maxTokens < 1 || config.maxTokens > 32000) {
      errors.push('Max tokens must be between 1 and 32000');
    }

    if (config.topP < 0 || config.topP > 1) {
      errors.push('Top P must be between 0 and 1');
    }

    if (config.frequencyPenalty < -2 || config.frequencyPenalty > 2) {
      errors.push('Frequency penalty must be between -2 and 2');
    }

    if (config.presencePenalty < -2 || config.presencePenalty > 2) {
      errors.push('Presence penalty must be between -2 and 2');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Get LLM provider by ID
   */
  async getProvider(providerId: string): Promise<LLMProvider | null> {
    const providers = await this.getProviders();
    return providers.find(p => p.id === providerId) || null;
  }

  /**
   * Get LLM model by ID
   */
  async getModel(modelId: string): Promise<LLMModel | null> {
    const models = await this.getModels();
    return models.find(m => m.id === modelId) || null;
  }

  /**
   * Get models for a specific provider
   */
  async getModelsForProvider(providerId: string): Promise<LLMModel[]> {
    return this.getModels(providerId);
  }

  /**
   * Calculate estimated cost for a configuration
   */
  async calculateEstimatedCost(config: AgentLLMConfig, estimatedTokens: number): Promise<number> {
    const model = await this.getModel(config.modelId);
    if (!model) return 0;
    
    return model.costPerToken * estimatedTokens;
  }

  /**
   * Get configuration summary for display
   */
  async getConfigSummary(config: AgentLLMConfig): Promise<{
    provider: LLMProvider | null;
    model: LLMModel | null;
    estimatedCostPer1K: number;
  }> {
    const [provider, model] = await Promise.all([
      this.getProvider(config.providerId),
      this.getModel(config.modelId)
    ]);

    const estimatedCostPer1K = model ? model.costPerToken * 1000 : 0;

    return {
      provider,
      model,
      estimatedCostPer1K
    };
  }
}

// Export singleton instance
export const llmConfigService = new LLMConfigurationService();

// Export utility functions
export {
  DEFAULT_LLM_PROVIDERS,
  DEFAULT_LLM_MODELS,
  DEFAULT_AGENT_LLM_CONFIGS
} from '$lib/types/llm-config';
