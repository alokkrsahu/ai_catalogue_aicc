<!-- src/lib/components/EnhancedTemplateSelector.svelte -->
<script>
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import enhancedTemplateService from '$lib/services/templateService.js';
  
  // Props
  export let selectedTemplate = null;
  export let showConfiguration = false;
  
  // Events
  const dispatch = createEventDispatcher();
  
  // State
  let templates = [];
  let loading = true;
  let error = null;
  let templateConfiguration = null;
  let cacheStats = null;
  
  onMount(async () => {
    await loadTemplates();
  });
  
  async function loadTemplates() {
    try {
      loading = true;
      error = null;
      
      // Load templates from folder-based discovery
      templates = await enhancedTemplateService.loadTemplates();
      
      // Validate template structure
      templates.forEach(template => {
        if (!template.id || !template.template_type) {
          console.error('Invalid template structure:', template);
        }
      });
      
      console.log(`Loaded ${templates.length} templates from folder discovery`);
      
    } catch (err) {
      console.error('Failed to load templates:', err);
      error = err.message;
    } finally {
      loading = false;
    }
  }
  
  async function selectTemplate(template) {
    try {
      // Load complete template configuration
      templateConfiguration = await enhancedTemplateService.getTemplateConfiguration(template.id);
      
      selectedTemplate = {
        ...template,
        configuration: templateConfiguration
      };
      
      // Dispatch selection event
      dispatch('templateSelected', selectedTemplate);
      
      console.log('Template selected:', selectedTemplate);
      
    } catch (err) {
      console.error('Failed to load template configuration:', err);
      error = `Failed to load template configuration: ${err.message}`;
    }
  }
  
  async function refreshTemplates() {
    try {
      // Force template discovery
      const refreshResult = await enhancedTemplateService.refreshTemplates();
      console.log('Templates refreshed:', refreshResult);
      
      // Reload templates
      await loadTemplates();
      
    } catch (err) {
      console.error('Failed to refresh templates:', err);
      error = `Failed to refresh templates: ${err.message}`;
    }
  }
  
  async function loadCacheStats() {
    try {
      cacheStats = await enhancedTemplateService.getCacheStatistics();
      console.log('Cache statistics:', cacheStats);
    } catch (err) {
      console.error('Failed to load cache statistics:', err);
      // Don't show error for cache stats as it's admin-only
    }
  }
  
  function getFeatureList(features) {
    if (!features || typeof features !== 'object') return [];
    return Object.entries(features)
      .filter(([key, value]) => value === true)
      .map(([key, value]) => key.replace(/_/g, ' '));
  }
</script>

<div class="enhanced-template-selector">
  <div class="selector-header">
    <h3>Select Project Template</h3>
    <div class="header-actions">
      <button class="refresh-btn" on:click={refreshTemplates} disabled={loading}>
        <i class="fas fa-sync-alt"></i>
        Refresh
      </button>
      <button class="stats-btn" on:click={loadCacheStats}>
        <i class="fas fa-chart-bar"></i>
        Stats
      </button>
    </div>
  </div>
  
  {#if error}
    <div class="error-message">
      <i class="fas fa-exclamation-triangle"></i>
      <span>{error}</span>
      <button on:click={() => error = null}>×</button>
    </div>
  {/if}
  
  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Discovering templates from folders...</p>
    </div>
  {:else if templates.length === 0}
    <div class="empty-state">
      <i class="fas fa-folder-open"></i>
      <h4>No templates available</h4>
      <p>No template folders were found</p>
      <button on:click={refreshTemplates}>Refresh Templates</button>
    </div>
  {:else}
    <div class="templates-grid">
      {#each templates as template}
        <div 
          class="template-card {selectedTemplate?.id === template.id ? 'selected' : ''}"
          on:click={() => selectTemplate(template)}
        >
          <!-- Template Icon -->
          <div class="template-icon">
            <i class="fas {template.icon_class || 'fa-file-alt'}"></i>
          </div>
          
          <!-- Template Info -->
          <div class="template-info">
            <h4>{template.name}</h4>
            <p class="description">{template.description}</p>
            
            <!-- Version and Author -->
            {#if template.version || template.author}
              <div class="metadata">
                {#if template.version}
                  <span class="version">v{template.version}</span>
                {/if}
                {#if template.author}
                  <span class="author">by {template.author}</span>
                {/if}
              </div>
            {/if}
            
            <!-- Analysis Focus -->
            {#if template.analysis_focus}
              <div class="analysis-focus">
                <strong>Focus:</strong> {template.analysis_focus}
              </div>
            {/if}
          </div>
          
          <!-- Features -->
          {#if template.features}
            <div class="features">
              {#each getFeatureList(template.features) as feature}
                <span class="feature-tag">{feature}</span>
              {/each}
            </div>
          {/if}
          
          <!-- Source Indicator -->
          <div class="source-indicator">
            <i class="fas fa-folder"></i>
            <span>Folder-based</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
  
  <!-- Configuration Preview -->
  {#if showConfiguration && selectedTemplate && templateConfiguration}
    <div class="configuration-preview">
      <h4>Template Configuration Preview</h4>
      
      <div class="config-grid">
        <div class="config-item">
          <label>Navigation:</label>
          <span>
            {templateConfiguration.has_navigation ? 
              `${templateConfiguration.total_pages} pages` : 
              'Single page'}
          </span>
        </div>
        
        <div class="config-item">
          <label>Processing:</label>
          <span>
            {Object.keys(templateConfiguration.processing_capabilities || {}).length} capabilities
          </span>
        </div>
        
        <div class="config-item">
          <label>UI Layout:</label>
          <span>
            {templateConfiguration.ui_configuration?.layout || 'default'}
          </span>
        </div>
        
        <div class="config-item">
          <label>Features:</label>
          <span>
            {templateConfiguration.navigation_pages?.length || 0} pages configured
          </span>
        </div>
      </div>
      
      <!-- Navigation Pages Preview -->
      {#if templateConfiguration.navigation_pages?.length > 0}
        <div class="navigation-preview">
          <h5>Navigation Pages:</h5>
          <div class="pages-list">
            {#each templateConfiguration.navigation_pages as page}
              <div class="page-item">
                <i class="fas {page.icon || 'fa-file'}"></i>
                <span>{page.name}</span>
                <small>({page.features?.length || 0} features)</small>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
  
  <!-- Cache Statistics (if loaded) -->
  {#if cacheStats}
    <div class="cache-stats">
      <h5>Cache Performance</h5>
      <div class="stats-grid">
        <div class="stat-item">
          <label>Hit Rate:</label>
          <span>{cacheStats.hit_rate_percent}%</span>
        </div>
        <div class="stat-item">
          <label>Response Time:</label>
          <span>{cacheStats.average_response_time_ms}ms</span>
        </div>
        <div class="stat-item">
          <label>Cache Size:</label>
          <span>{cacheStats.memory_cache_size} items</span>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .enhanced-template-selector {
    max-width: 100%;
    margin: 0 auto;
  }
  
  .selector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }
  
  .selector-header h3 {
    margin: 0;
    color: #002147;
    font-weight: 600;
  }
  
  .header-actions {
    display: flex;
    gap: 0.5rem;
  }
  
  .refresh-btn, .stats-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border: 1px solid #002147;
    background: white;
    color: #002147;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    transition: all 0.2s;
  }
  
  .refresh-btn:hover, .stats-btn:hover {
    background: #002147;
    color: white;
  }
  
  .refresh-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .error-message {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 4px;
    color: #dc2626;
    margin-bottom: 1rem;
  }
  
  .error-message button {
    margin-left: auto;
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: #dc2626;
  }
  
  .loading-state, .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    text-align: center;
    color: #6b7280;
  }
  
  .spinner {
    width: 2rem;
    height: 2rem;
    border: 3px solid #e5e7eb;
    border-top: 3px solid #002147;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .empty-state i {
    font-size: 3rem;
    margin-bottom: 1rem;
    color: #d1d5db;
  }
  
  .templates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
  }
  
  .template-card {
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
    background: white;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
  }
  
  .template-card:hover {
    border-color: #002147;
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.1);
  }
  
  .template-card.selected {
    border-color: #002147;
    background: #f8fafc;
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.15);
  }
  
  .template-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    background: #002147;
    color: white;
    border-radius: 8px;
    margin-bottom: 1rem;
    font-size: 1.25rem;
  }
  
  .template-info h4 {
    margin: 0 0 0.5rem 0;
    color: #002147;
    font-weight: 600;
  }
  
  .description {
    color: #6b7280;
    font-size: 0.875rem;
    line-height: 1.4;
    margin-bottom: 0.75rem;
  }
  
  .metadata {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    font-size: 0.75rem;
  }
  
  .version, .author {
    padding: 0.25rem 0.5rem;
    background: #f3f4f6;
    border-radius: 4px;
    color: #6b7280;
  }
  
  .analysis-focus {
    font-size: 0.75rem;
    color: #6b7280;
    margin-bottom: 1rem;
  }
  
  .features {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  
  .feature-tag {
    padding: 0.25rem 0.5rem;
    background: #dbeafe;
    color: #1e40af;
    border-radius: 4px;
    font-size: 0.75rem;
    text-transform: capitalize;
  }
  
  .source-indicator {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: #10b981;
  }
  
  .configuration-preview {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  
  .configuration-preview h4 {
    margin: 0 0 1rem 0;
    color: #002147;
  }
  
  .config-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }
  
  .config-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem;
    background: white;
    border-radius: 4px;
  }
  
  .config-item label {
    font-weight: 500;
    color: #374151;
  }
  
  .navigation-preview h5 {
    margin: 1rem 0 0.5rem 0;
    color: #002147;
  }
  
  .pages-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  
  .page-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    font-size: 0.875rem;
  }
  
  .cache-stats {
    background: #fefce8;
    border: 1px solid #fbbf24;
    border-radius: 8px;
    padding: 1rem;
  }
  
  .cache-stats h5 {
    margin: 0 0 0.75rem 0;
    color: #92400e;
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.75rem;
  }
  
  .stat-item {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
  }
  
  .stat-item label {
    color: #92400e;
    font-weight: 500;
  }
</style>
