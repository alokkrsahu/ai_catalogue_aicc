/**
 * LLM Models Store - Optimized for Agent Orchestration
 * ====================================================
 * 
 * Pre-loads and caches all LLM models from all providers to eliminate
 * repetitive API calls and reduce LAG in Agent Orchestration interface.
 */

import { writable, derived, get } from 'svelte/store';
import api from '$lib/services/api';

// Types
export interface LLMModel {
  id: string;
  name: string;
  display_name: string;
  provider: string;
  context_length?: number;
  cost_per_1k_tokens?: number;
  capabilities?: string[];
  recommended_for?: string[];
  is_available: boolean;
  last_checked?: string;
  provider_status?: {
    provider: string;
    name: string;
    has_api_key: boolean;
    api_key_valid: boolean;
    models_available: boolean;
    message: string;
  };
}

export interface LLMProvider {
  id: string;
  name: string;
  status: {
    available: boolean;
    has_api_key: boolean;
    api_key_valid: boolean;
    message: string;
    models_count: number;
  };
  models: LLMModel[];
}

export interface BulkModelData {
  provider_models: Record<string, LLMModel[]>;
  all_models: LLMModel[];
  models_by_agent_type: Record<string, LLMModel[]>;
  provider_statuses: Record<string, any>;
  provider_summary: Record<string, any>;
  statistics: {
    total_models: number;
    available_providers: number;
    total_providers: number;
    models_per_provider: Record<string, number>;
  };
  metadata: {
    loaded_at: string;
    cache_ttl: number;
    api_version: string;
    supports_agent_orchestration: boolean;
    optimized_for_frontend: boolean;
  };
  source?: 'cache' | 'api' | 'fresh_load';
  cache_hit?: boolean;
}

// Store state
interface LLMModelsState {
  isLoading: boolean;
  isLoaded: boolean;
  error: string | null;
  bulkData: BulkModelData | null;
  lastLoadTime: number;
  loadingProgress: {
    stage: string;
    percentage: number;
  };
}

// Initial state
const initialState: LLMModelsState = {
  isLoading: false,
  isLoaded: false,
  error: null,
  bulkData: null,
  lastLoadTime: 0,
  loadingProgress: {
    stage: 'idle',
    percentage: 0
  }
};

// Main store
const llmModelsStore = writable<LLMModelsState>(initialState);

// Derived stores for easy access
export const allModels = derived(llmModelsStore, ($store) => 
  $store.bulkData?.all_models || []
);

export const providerModels = derived(llmModelsStore, ($store) => 
  $store.bulkData?.provider_models || {}
);

export const modelsByAgentType = derived(llmModelsStore, ($store) => 
  $store.bulkData?.models_by_agent_type || {}
);

export const providerStatuses = derived(llmModelsStore, ($store) => 
  $store.bulkData?.provider_statuses || {}
);

export const availableProviders = derived(llmModelsStore, ($store) => {
  const statuses = $store.bulkData?.provider_statuses || {};
  return Object.keys(statuses).filter(provider => 
    statuses[provider]?.api_key_valid
  );
});

export const modelStatistics = derived(llmModelsStore, ($store) => 
  $store.bulkData?.statistics || {
    total_models: 0,
    available_providers: 0,
    total_providers: 0,
    models_per_provider: {}
  }
);

export const isLoading = derived(llmModelsStore, ($store) => $store.isLoading);
export const isLoaded = derived(llmModelsStore, ($store) => $store.isLoaded);
export const loadError = derived(llmModelsStore, ($store) => $store.error);
export const loadingProgress = derived(llmModelsStore, ($store) => $store.loadingProgress);

// Service class
class LLMModelsService {
  private readonly CACHE_KEY = 'llm_models_bulk_data';
  private readonly CACHE_TTL = 60 * 60 * 1000; // 1 hour in milliseconds
  
  constructor() {
    console.log('🤖 LLM MODELS STORE: Service initialized');
  }

  /**
   * Pre-load all models for Agent Orchestration interface
   * This is the main function to call when loading the Agent Orchestration page
   */
  async preLoadAllModels(forceRefresh = false, projectId?: string): Promise<BulkModelData> {
    const state = get(llmModelsStore);
    
    // Prevent multiple simultaneous loads
    if (state.isLoading) {
      console.log('🔄 LLM MODELS: Load already in progress, waiting...');
      return this.waitForLoad();
    }
    
    // Check if we have valid cached data
    if (!forceRefresh && this.hasValidCache()) {
      const cachedData = this.getCachedData();
      if (cachedData) {
        console.log('✅ LLM MODELS: Using cached data');
        this.updateStore({ 
          isLoaded: true, 
          bulkData: cachedData,
          lastLoadTime: Date.now()
        });
        return cachedData;
      }
    }
    
    try {
      console.log('🚀 LLM MODELS: Starting bulk model pre-loading');
      
      // Update loading state
      this.updateStore({ 
        isLoading: true, 
        error: null,
        loadingProgress: { stage: 'Connecting to API...', percentage: 10 }
      });
      
      // Call bulk load API with project context
      const params: any = {
        force_refresh: forceRefresh,
        max_age_minutes: 60
      };
      
      // Get project_id from URL or user's first project if not provided
      if (projectId) {
        params.project_id = projectId;
      } else {
        // Try to get project from URL params or user context
        try {
          // Import cleanUniversalApi to get user's projects
          const cleanUniversalApiModule = await import('$lib/services/cleanUniversalApi');
          const cleanUniversalApi = new cleanUniversalApiModule.CleanUniversalApiService();
          const projects = await cleanUniversalApi.getAllProjects();
          if (projects && projects.length > 0) {
            params.project_id = projects[0].project_id;
            console.log('🔑 LLM MODELS: Using first project for API keys:', projects[0].name);
          } else {
            console.warn('⚠️ LLM MODELS: No projects found, API keys may not be available');
          }
        } catch (error) {
          console.warn('⚠️ LLM MODELS: Could not get project context:', error);
        }
      }
      
      const response = await api.get('/llm/bulk-load/', {
        params
      });
      
      this.updateStore({
        loadingProgress: { stage: 'Processing model data...', percentage: 70 }
      });
      
      const bulkData: BulkModelData = response.data;
      
      // Cache the data
      this.cacheData(bulkData);
      
      this.updateStore({
        loadingProgress: { stage: 'Finalizing...', percentage: 90 }
      });
      
      // Update store with loaded data
      this.updateStore({
        isLoading: false,
        isLoaded: true,
        error: null,
        bulkData,
        lastLoadTime: Date.now(),
        loadingProgress: { stage: 'Complete', percentage: 100 }
      });
      
      console.log(
        `✅ LLM MODELS: Pre-loaded ${bulkData.statistics.total_models} models ` +
        `from ${bulkData.statistics.available_providers} providers ` +
        `(source: ${bulkData.source})`
      );
      
      return bulkData;
      
    } catch (error) {
      console.error('❌ LLM MODELS: Pre-loading failed:', error);
      
      this.updateStore({
        isLoading: false,
        error: error.message || 'Failed to load models',
        loadingProgress: { stage: 'Error', percentage: 0 }
      });
      
      throw error;
    }
  }

  /**
   * Get models for a specific provider
   */
  getModelsForProvider(providerId: string): LLMModel[] {
    const state = get(llmModelsStore);
    return state.bulkData?.provider_models[providerId] || [];
  }

  /**
   * Get recommended models for an agent type
   */
  getRecommendedModelsForAgent(agentType: string): LLMModel[] {
    const state = get(llmModelsStore);
    return state.bulkData?.models_by_agent_type[agentType] || [];
  }

  /**
   * Get a specific model by ID
   */
  getModelById(modelId: string): LLMModel | null {
    const state = get(llmModelsStore);
    const allModels = state.bulkData?.all_models || [];
    return allModels.find(model => model.id === modelId) || null;
  }

  /**
   * Refresh models for a specific provider
   */
  async refreshProvider(providerId: string): Promise<BulkModelData> {
    try {
      console.log(`🔄 LLM MODELS: Refreshing ${providerId} models`);
      
      this.updateStore({
        loadingProgress: { stage: `Refreshing ${providerId}...`, percentage: 50 }
      });
      
      const response = await api.post(`/llm/refresh/${providerId}/`);
      const updatedBulkData: BulkModelData = response.data.bulk_data;
      
      // Update cache and store
      this.cacheData(updatedBulkData);
      this.updateStore({
        bulkData: updatedBulkData,
        lastLoadTime: Date.now(),
        loadingProgress: { stage: 'Complete', percentage: 100 }
      });
      
      console.log(`✅ LLM MODELS: Refreshed ${response.data.models_count} models for ${providerId}`);
      return updatedBulkData;
      
    } catch (error) {
      console.error(`❌ LLM MODELS: Failed to refresh ${providerId}:`, error);
      throw error;
    }
  }

  /**
   * Clear all caches and force fresh reload
   */
  async clearCacheAndReload(): Promise<BulkModelData> {
    try {
      console.log('🧹 LLM MODELS: Clearing cache and reloading');
      
      // Clear backend cache
      await api.delete('/llm/clear-cache/');
      
      // Clear frontend cache
      this.clearCache();
      
      // Force fresh reload
      return await this.preLoadAllModels(true);
      
    } catch (error) {
      console.error('❌ LLM MODELS: Failed to clear cache and reload:', error);
      throw error;
    }
  }

  /**
   * Check if models are available for a provider
   */
  isProviderAvailable(providerId: string): boolean {
    const state = get(llmModelsStore);
    const status = state.bulkData?.provider_statuses[providerId];
    return status?.api_key_valid || false;
  }

  /**
   * Get provider status
   */
  getProviderStatus(providerId: string): any {
    const state = get(llmModelsStore);
    return state.bulkData?.provider_statuses[providerId] || null;
  }

  /**
   * Wait for current loading to complete
   */
  private async waitForLoad(): Promise<BulkModelData> {
    return new Promise((resolve, reject) => {
      const unsubscribe = llmModelsStore.subscribe(state => {
        if (!state.isLoading) {
          unsubscribe();
          if (state.error) {
            reject(new Error(state.error));
          } else if (state.bulkData) {
            resolve(state.bulkData);
          } else {
            reject(new Error('No data loaded'));
          }
        }
      });
    });
  }

  /**
   * Update store state
   */
  private updateStore(updates: Partial<LLMModelsState>) {
    llmModelsStore.update(state => ({ ...state, ...updates }));
  }

  /**
   * Cache data in localStorage
   */
  private cacheData(data: BulkModelData) {
    try {
      const cacheItem = {
        data,
        timestamp: Date.now()
      };
      localStorage.setItem(this.CACHE_KEY, JSON.stringify(cacheItem));
      console.log('💾 LLM MODELS: Data cached successfully');
    } catch (error) {
      console.warn('⚠️ LLM MODELS: Failed to cache data:', error);
    }
  }

  /**
   * Get cached data from localStorage
   */
  private getCachedData(): BulkModelData | null {
    try {
      const cached = localStorage.getItem(this.CACHE_KEY);
      if (!cached) return null;
      
      const cacheItem = JSON.parse(cached);
      return cacheItem.data;
    } catch (error) {
      console.warn('⚠️ LLM MODELS: Failed to get cached data:', error);
      return null;
    }
  }

  /**
   * Check if cached data is still valid
   */
  private hasValidCache(): boolean {
    try {
      const cached = localStorage.getItem(this.CACHE_KEY);
      if (!cached) return false;
      
      const cacheItem = JSON.parse(cached);
      const age = Date.now() - cacheItem.timestamp;
      return age < this.CACHE_TTL;
    } catch (error) {
      return false;
    }
  }

  /**
   * Clear cached data
   */
  private clearCache() {
    try {
      localStorage.removeItem(this.CACHE_KEY);
      console.log('🧹 LLM MODELS: Cache cleared');
    } catch (error) {
      console.warn('⚠️ LLM MODELS: Failed to clear cache:', error);
    }
  }

  /**
   * Get default model for agent type and provider
   */
  getDefaultModelForAgent(agentType: string, providerId?: string): LLMModel | null {
    const state = get(llmModelsStore);
    if (!state.bulkData) return null;
    
    // If provider specified, get models for that provider
    if (providerId) {
      const providerModels = state.bulkData.provider_models[providerId] || [];
      const recommended = providerModels.filter(model => 
        model.recommended_for?.includes(agentType)
      );
      return recommended[0] || providerModels[0] || null;
    }
    
    // Get recommended models for agent type across all providers
    const recommended = state.bulkData.models_by_agent_type[agentType] || [];
    return recommended[0] || null;
  }

  /**
   * Check if models are loaded and ready
   */
  isReady(): boolean {
    const state = get(llmModelsStore);
    return state.isLoaded && !!state.bulkData && !state.isLoading;
  }

  /**
   * Get loading summary for UI
   */
  getLoadingSummary(): {
    isLoading: boolean;
    isLoaded: boolean;
    error: string | null;
    totalModels: number;
    availableProviders: number;
    lastLoadTime: number;
    cacheAge: number;
  } {
    const state = get(llmModelsStore);
    const cacheAge = this.hasValidCache() ? Date.now() - state.lastLoadTime : 0;
    
    return {
      isLoading: state.isLoading,
      isLoaded: state.isLoaded,
      error: state.error,
      totalModels: state.bulkData?.statistics.total_models || 0,
      availableProviders: state.bulkData?.statistics.available_providers || 0,
      lastLoadTime: state.lastLoadTime,
      cacheAge
    };
  }
}

// Export singleton service
export const llmModelsService = new LLMModelsService();

// Export store and derived stores
export { llmModelsStore };

// Utility function to ensure models are loaded
export async function ensureModelsLoaded(forceRefresh = false, projectId?: string): Promise<BulkModelData> {
  const state = get(llmModelsStore);
  
  if (state.isLoaded && state.bulkData && !forceRefresh) {
    return state.bulkData;
  }
  
  return await llmModelsService.preLoadAllModels(forceRefresh, projectId);
}

// Reactive function for components
export function useModelsForProvider(providerId: string) {
  return derived(providerModels, ($providerModels) => 
    $providerModels[providerId] || []
  );
}

export function useRecommendedModels(agentType: string) {
  return derived(modelsByAgentType, ($modelsByAgentType) => 
    $modelsByAgentType[agentType] || []
  );
}
