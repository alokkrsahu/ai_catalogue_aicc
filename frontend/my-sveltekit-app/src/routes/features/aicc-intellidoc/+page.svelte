<!-- AICC-IntelliDoc Template Selection Page -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { createTemplateLogger } from '$lib/logging/logger';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { toasts } from '$lib/stores/toast';
  import type { AICCIntelliDocTemplate, UniversalProject } from '$lib/templates/types';
  
  const logger = createTemplateLogger('aicc-intellidoc', 'SelectionPage');
  
  let template: AICCIntelliDocTemplate | null = null;
  let loading = true;
  let showCreateForm = false;
  let creatingProject = false;
  
  // Project creation form data
  let projectName = '';
  let projectDescription = '';
  
  onMount(() => {
    logger.componentMount('AICCIntelliDocSelectionPage');
    loadTemplateConfiguration();
  });
  
  async function loadTemplateConfiguration() {
    logger.templateAction('load_configuration', 'aicc-intellidoc');
    
    try {
      loading = true;
      const configResult = await cleanUniversalApi.getTemplateConfiguration('aicc-intellidoc');
      template = configResult.discovery || configResult;
      logger.templateAction('configuration_loaded', 'aicc-intellidoc', template);
    } catch (error) {
      logger.error('Failed to load template configuration', error);
      toasts.error('Failed to load AICC-IntelliDoc template configuration');
    } finally {
      loading = false;
    }
  }
  
  async function createProject() {
    if (!projectName.trim() || !projectDescription.trim()) {
      toasts.error('Please fill in all required fields');
      return;
    }
    
    logger.templateAction('create_project_start', 'aicc-intellidoc', {
      name: projectName,
      description: projectDescription
    });
    
    try {
      creatingProject = true;
      
      const projectData = {
        name: projectName.trim(),
        description: projectDescription.trim(),
        template_id: 'aicc-intellidoc'
      };
      
      const newProject = await cleanUniversalApi.createProject(projectData);
      
      logger.templateAction('project_created', 'aicc-intellidoc', newProject);
      toasts.success(`Project "${projectName}" created successfully`);
      
      // Navigate to the UNIVERSAL project interface (template independent)
      logger.templateNavigation('template_selection', 'universal_project', 'universal');
      goto(`/features/intellidoc/project/${newProject.project_id}`);
      
    } catch (error) {
      logger.error('Failed to create project', error);
      toasts.error('Failed to create project. Please try again.');
    } finally {
      creatingProject = false;
    }
  }
  
  function openCreateForm() {
    showCreateForm = true;
    projectName = '';
    projectDescription = '';
    logger.userInteraction('open_create_form', 'create_button');
  }
  
  function closeCreateForm() {
    showCreateForm = false;
    projectName = '';
    projectDescription = '';
    logger.userInteraction('close_create_form', 'close_button');
  }
</script>

<svelte:head>
  <title>AICC-IntelliDoc Template - AI Catalogue</title>
</svelte:head>

<div class="template-selection-page">
  <!-- Header Section -->
  <div class="header-section">
    <div class="template-hero">
      <div class="hero-icon">
        <i class="fas fa-brain"></i>
      </div>
      <div class="hero-content">
        <h1>AICC-IntelliDoc Template</h1>
        <p class="hero-description">
          Advanced AI-powered document analysis with hierarchical processing and multi-page navigation
        </p>
        {#if template}
          <div class="template-version">
            Version {template.version} • {template.template_type}
          </div>
        {/if}
      </div>
    </div>
    
    <div class="hero-actions">
      <button class="create-project-button" on:click={openCreateForm}>
        <i class="fas fa-plus"></i>
        Create New Project
      </button>
    </div>
  </div>
  
  <!-- Template Information -->
  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading template configuration...</p>
    </div>
  {:else if template}
    <div class="template-details">
      <!-- Features Overview -->
      <div class="features-section">
        <h2>Template Features</h2>
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-sitemap"></i>
            </div>
            <div class="feature-content">
              <h3>Multi-Page Navigation</h3>
              <p>{template.total_pages} specialized pages for comprehensive document analysis</p>
            </div>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-robot"></i>
            </div>
            <div class="feature-content">
              <h3>AI Analysis</h3>
              <p>Advanced AI-powered document processing with hierarchical analysis</p>
            </div>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-search"></i>
            </div>
            <div class="feature-content">
              <h3>Vector Search</h3>
              <p>Semantic search capabilities for intelligent document retrieval</p>
            </div>
          </div>
          
          <div class="feature-card">
            <div class="feature-icon">
              <i class="fas fa-layer-group"></i>
            </div>
            <div class="feature-content">
              <h3>Hierarchical Processing</h3>
              <p>Structured document analysis with categorization and organization</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Navigation Pages Preview -->
      {#if template.navigation_pages && template.navigation_pages.length > 0}
        <div class="navigation-preview">
          <h2>Page Structure</h2>
          <div class="pages-grid">
            {#each template.navigation_pages as page}
              <div class="page-card">
                <div class="page-number">{page.id}</div>
                <div class="page-content">
                  <h4>{page.title}</h4>
                  <p>{page.description}</p>
                  {#if page.features && page.features.length > 0}
                    <div class="page-features">
                      {#each page.features as feature}
                        <span class="feature-tag">{feature}</span>
                      {/each}
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
      
      <!-- Processing Capabilities -->
      {#if template.processing_capabilities}
        <div class="capabilities-section">
          <h2>Processing Capabilities</h2>
          <div class="capabilities-grid">
            <div class="capability-item">
              <i class="fas fa-check-circle"></i>
              <span>Maximum file size: {(template.processing_capabilities.max_file_size / 1024 / 1024).toFixed(1)} MB</span>
            </div>
            {#if template.processing_capabilities.supported_file_types}
              <div class="capability-item">
                <i class="fas fa-file-alt"></i>
                <span>Supported formats: {template.processing_capabilities.supported_file_types.join(', ')}</span>
              </div>
            {/if}
            {#if template.processing_capabilities.supports_ai_analysis}
              <div class="capability-item">
                <i class="fas fa-brain"></i>
                <span>AI-powered analysis enabled</span>
              </div>
            {/if}
            {#if template.processing_capabilities.supports_vector_search}
              <div class="capability-item">
                <i class="fas fa-search"></i>
                <span>Vector search capabilities</span>
              </div>
            {/if}
          </div>
        </div>
      {/if}
      
      <!-- Analysis Focus -->
      {#if template.analysis_focus}
        <div class="focus-section">
          <h2>Analysis Focus</h2>
          <div class="focus-content">
            <p>{template.analysis_focus}</p>
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <div class="error-state">
      <div class="error-icon">
        <i class="fas fa-exclamation-triangle"></i>
      </div>
      <h3>Template Not Available</h3>
      <p>The AICC-IntelliDoc template configuration could not be loaded.</p>
      <button class="retry-button" on:click={loadTemplateConfiguration}>
        <i class="fas fa-redo"></i>
        Retry
      </button>
    </div>
  {/if}
</div>

<!-- Create Project Modal -->
{#if showCreateForm}
  <div class="modal-overlay" on:click={closeCreateForm}>
    <div class="modal-container" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Create AICC-IntelliDoc Project</h2>
        <button class="close-button" on:click={closeCreateForm}>
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <div class="modal-content">
        <form on:submit|preventDefault={createProject}>
          <div class="form-group">
            <label for="projectName">Project Name *</label>
            <input 
              id="projectName"
              type="text" 
              bind:value={projectName}
              placeholder="Enter project name"
              class="form-input"
              required
            />
          </div>
          
          <div class="form-group">
            <label for="projectDescription">Description *</label>
            <textarea 
              id="projectDescription"
              bind:value={projectDescription}
              placeholder="Describe your project and its objectives"
              class="form-textarea"
              rows="4"
              required
            ></textarea>
          </div>
          
          <div class="template-info">
            <div class="info-icon">
              <i class="fas fa-info-circle"></i>
            </div>
            <div class="info-content">
              <p><strong>This project will use the AICC-IntelliDoc template</strong></p>
              <p>You'll get {template?.total_pages || 4} specialized pages with AI analysis, vector search, and hierarchical processing capabilities.</p>
            </div>
          </div>
          
          <div class="form-actions">
            <button type="button" class="action-button secondary" on:click={closeCreateForm}>
              Cancel
            </button>
            <button 
              type="submit" 
              class="action-button primary"
              disabled={creatingProject || !projectName.trim() || !projectDescription.trim()}
            >
              {#if creatingProject}
                <i class="fas fa-spinner fa-spin"></i>
                Creating Project...
              {:else}
                <i class="fas fa-rocket"></i>
                Create Project
              {/if}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}

<style>
  .template-selection-page {
    min-height: 100vh;
    background: #f8fafc;
    padding: 24px;
  }
  
  .header-section {
    background: linear-gradient(135deg, #002147 0%, #1e3a5f 100%);
    border-radius: 16px;
    padding: 48px;
    margin-bottom: 32px;
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .template-hero {
    display: flex;
    align-items: center;
    gap: 24px;
  }
  
  .hero-icon {
    width: 80px;
    height: 80px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: white;
  }
  
  .hero-content h1 {
    margin: 0 0 12px 0;
    font-size: 2.5rem;
    font-weight: 700;
    color: white;
  }
  
  .hero-description {
    margin: 0 0 12px 0;
    font-size: 1.125rem;
    color: rgba(255, 255, 255, 0.9);
    line-height: 1.6;
  }
  
  .template-version {
    background: rgba(255, 255, 255, 0.1);
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.875rem;
    color: rgba(255, 255, 255, 0.8);
    width: fit-content;
  }
  
  .create-project-button {
    background: rgba(255, 255, 255, 0.1);
    color: white;
    border: 2px solid rgba(255, 255, 255, 0.2);
    padding: 16px 32px;
    border-radius: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 1.125rem;
  }
  
  .create-project-button:hover {
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.4);
    transform: translateY(-2px);
  }
  
  .loading-state, .error-state {
    text-align: center;
    padding: 64px 32px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }
  
  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #e5e7eb;
    border-top: 3px solid #002147;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 16px;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .error-icon {
    font-size: 3rem;
    color: #ef4444;
    margin-bottom: 16px;
  }
  
  .retry-button {
    background: #002147;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  
  .retry-button:hover {
    background: #1e3a5f;
  }
  
  .template-details {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }
  
  .features-section, .navigation-preview, .capabilities-section, .focus-section {
    background: white;
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }
  
  .features-section h2, .navigation-preview h2, .capabilities-section h2, .focus-section h2 {
    margin: 0 0 24px 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
  }
  
  .features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
  }
  
  .feature-card {
    background: #f8fafc;
    border-radius: 12px;
    padding: 24px;
    display: flex;
    align-items: flex-start;
    gap: 16px;
    border: 1px solid #e5e7eb;
  }
  
  .feature-icon {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.125rem;
    flex-shrink: 0;
  }
  
  .feature-content h3 {
    margin: 0 0 8px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #111827;
  }
  
  .feature-content p {
    margin: 0;
    color: #6b7280;
    line-height: 1.5;
  }
  
  .pages-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }
  
  .page-card {
    background: #f8fafc;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #e5e7eb;
    display: flex;
    align-items: flex-start;
    gap: 16px;
  }
  
  .page-number {
    width: 32px;
    height: 32px;
    background: #002147;
    color: white;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    flex-shrink: 0;
  }
  
  .page-content h4 {
    margin: 0 0 8px 0;
    font-size: 1rem;
    font-weight: 600;
    color: #111827;
  }
  
  .page-content p {
    margin: 0 0 12px 0;
    color: #6b7280;
    font-size: 0.875rem;
    line-height: 1.5;
  }
  
  .page-features {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  
  .feature-tag {
    background: #eff6ff;
    color: #1e40af;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .capabilities-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
  }
  
  .capability-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: #f8fafc;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
  }
  
  .capability-item i {
    color: #10b981;
    font-size: 1.125rem;
  }
  
  .capability-item span {
    color: #374151;
    font-size: 0.875rem;
  }
  
  .focus-content {
    background: #f8fafc;
    border-radius: 12px;
    padding: 24px;
    border: 1px solid #e5e7eb;
  }
  
  .focus-content p {
    margin: 0;
    color: #374151;
    line-height: 1.6;
    font-size: 1rem;
  }
  
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }
  
  .modal-container {
    background: white;
    border-radius: 16px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
    max-width: 600px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
  }
  
  .modal-header {
    padding: 24px 32px;
    background: linear-gradient(135deg, #002147 0%, #1e3a5f 100%);
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-radius: 16px 16px 0 0;
  }
  
  .modal-header h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: white;
  }
  
  .close-button {
    background: none;
    border: none;
    font-size: 1.25rem;
    color: rgba(255, 255, 255, 0.8);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.2s ease;
  }
  
  .close-button:hover {
    color: white;
    background: rgba(255, 255, 255, 0.1);
  }
  
  .modal-content {
    padding: 32px;
  }
  
  .form-group {
    margin-bottom: 24px;
  }
  
  .form-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
    color: #374151;
  }
  
  .form-input, .form-textarea {
    width: 100%;
    padding: 12px 16px;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    font-size: 0.875rem;
    transition: all 0.2s ease;
    font-family: inherit;
  }
  
  .form-input:focus, .form-textarea:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .form-textarea {
    resize: vertical;
    min-height: 100px;
  }
  
  .template-info {
    background: #eff6ff;
    border: 1px solid #dbeafe;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    display: flex;
    gap: 16px;
  }
  
  .info-icon {
    color: #1e40af;
    font-size: 1.25rem;
    flex-shrink: 0;
  }
  
  .info-content p {
    margin: 0 0 8px 0;
    color: #1e40af;
    font-size: 0.875rem;
    line-height: 1.5;
  }
  
  .info-content p:last-child {
    margin-bottom: 0;
  }
  
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
  
  .action-button {
    padding: 12px 24px;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.875rem;
  }
  
  .action-button.primary {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
  }
  
  .action-button.primary:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.3);
  }
  
  .action-button.secondary {
    background: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
  }
  
  .action-button.secondary:hover {
    background: #f1f5f9;
    color: #475569;
  }
  
  .action-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
  
  @media (max-width: 768px) {
    .header-section {
      flex-direction: column;
      align-items: stretch;
      gap: 24px;
      text-align: center;
    }
    
    .template-hero {
      flex-direction: column;
      text-align: center;
    }
    
    .features-grid {
      grid-template-columns: 1fr;
    }
    
    .pages-grid {
      grid-template-columns: 1fr;
    }
    
    .capabilities-grid {
      grid-template-columns: 1fr;
    }
    
    .modal-container {
      margin: 20px;
      max-width: calc(100% - 40px);
    }
    
    .modal-content {
      padding: 24px;
    }
    
    .form-actions {
      flex-direction: column;
    }
  }
</style>
