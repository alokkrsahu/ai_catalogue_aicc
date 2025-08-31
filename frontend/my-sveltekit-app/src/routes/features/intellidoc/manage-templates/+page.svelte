<!-- src/routes/features/intellidoc/manage-templates/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toasts } from '$lib/stores/toast';
  import authStore from '$lib/stores/auth';
  import { get } from 'svelte/store';
  import { templateManagement, type Template, type TemplateDuplicationRequest } from '$lib/services/templateManagement';
  
  // State variables
  let templates: Template[] = [];
  let loading = true;
  let showDuplicationForm = false;
  let duplicating = false;
  
  // Form state
  let duplicationForm: TemplateDuplicationRequest = {
    source_template: '',
    new_template_id: '',
    new_name: '',
    new_description: '',
    version: '1.0.0',
    author: ''
  };
  
  // Validation state
  let formErrors: Record<string, string> = {};
  
  // Get current user info
  $: currentUser = get(authStore)?.user;
  
  onMount(() => {
    fetchTemplates();
    if (currentUser) {
      duplicationForm.author = `${currentUser.first_name} ${currentUser.last_name}`.trim() || currentUser.email;
    }
  });
  
  async function fetchTemplates() {
    try {
      loading = true;
      templates = await templateManagement.getAvailableTemplates();
      console.log('✅ Loaded templates:', templates);
    } catch (error) {
      console.error('❌ Failed to fetch templates:', error);
      toasts.error('Failed to load templates');
    } finally {
      loading = false;
    }
  }
  
  function openDuplicationForm(sourceTemplate?: Template) {
    if (sourceTemplate) {
      duplicationForm.source_template = sourceTemplate.id;
    }
    showDuplicationForm = true;
    formErrors = {};
  }
  
  function closeDuplicationForm() {
    showDuplicationForm = false;
    duplicationForm = {
      source_template: '',
      new_template_id: '',
      new_name: '',
      new_description: '',
      version: '1.0.0',
      author: currentUser ? `${currentUser.first_name} ${currentUser.last_name}`.trim() || currentUser.email : ''
    };
    formErrors = {};
  }
  
  function validateForm(): boolean {
    formErrors = {};
    
    if (!duplicationForm.source_template) {
      formErrors.source_template = 'Please select a source template';
    }
    
    // Use template management service for validation
    const idValidation = templateManagement.validateTemplateId(duplicationForm.new_template_id);
    if (!idValidation.valid) {
      formErrors.new_template_id = idValidation.error;
    } else if (templates.some(t => t.id === duplicationForm.new_template_id)) {
      formErrors.new_template_id = 'Template ID already exists';
    }
    
    if (!duplicationForm.new_name.trim()) {
      formErrors.new_name = 'Template name is required';
    }
    
    if (!duplicationForm.new_description.trim()) {
      formErrors.new_description = 'Template description is required';
    }
    
    const versionValidation = templateManagement.validateVersion(duplicationForm.version);
    if (!versionValidation.valid) {
      formErrors.version = versionValidation.error;
    }
    
    if (!duplicationForm.author.trim()) {
      formErrors.author = 'Author is required';
    }
    
    return Object.keys(formErrors).length === 0;
  }
  
  async function duplicateTemplate() {
    if (!validateForm()) {
      toasts.error('Please fix the form errors');
      return;
    }
    
    try {
      duplicating = true;
      
      const result = await templateManagement.duplicateTemplate(duplicationForm);
      
      if (result.success) {
        toasts.success(`Template "${duplicationForm.new_template_id}" created successfully!`);
        closeDuplicationForm();
        await fetchTemplates(); // Refresh template list
      } else {
        throw new Error(result.message || 'Template duplication failed');
      }
      
    } catch (error) {
      console.error('❌ Template duplication failed:', error);
      toasts.error(error.message || 'Failed to duplicate template');
    } finally {
      duplicating = false;
    }
  }
  
  function generateTemplateId(name: string) {
    duplicationForm.new_template_id = templateManagement.generateTemplateId(name);
  }
  
  function getTemplateIcon(template: Template): string {
    return templateManagement.getTemplateIcon(template);
  }
  
  function formatDate(dateString?: string): string {
    return templateManagement.formatDate(dateString);
  }
</script>

<svelte:head>
  <title>Manage Templates - AI Catalogue</title>
</svelte:head>

<div class="template-management-page">
  <!-- Header Section -->
  <div class="header-section">
    <div class="header-content">
      <div class="page-title">
        <div class="title-icon">
          <i class="fas fa-cogs"></i>
        </div>
        <div class="title-text">
          <h1>Template Management</h1>
          <p>Clone and customize templates for your projects</p>
        </div>
      </div>
      
      <div class="header-stats">
        <div class="stat-item">
          <div class="stat-value">{templates.length}</div>
          <div class="stat-label">Templates</div>
        </div>
      </div>
    </div>
    
    <div class="header-actions">
      <button 
        class="action-button secondary"
        on:click={() => goto('/features/intellidoc')}
      >
        <i class="fas fa-arrow-left"></i>
        Back to Projects
      </button>
      <button 
        class="action-button primary"
        on:click={() => openDuplicationForm()}
      >
        <i class="fas fa-copy"></i>
        Duplicate Template
      </button>
    </div>
  </div>
  
  <!-- Main Content -->
  <div class="main-content">
    {#if loading}
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading templates...</p>
      </div>
    {:else if templates.length === 0}
      <div class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-templates"></i>
        </div>
        <h3>No templates available</h3>
        <p>Contact your administrator to set up templates.</p>
      </div>
    {:else}
      <div class="templates-grid">
        {#each templates as template}
          <div class="template-card">
            <div class="card-header">
              <div class="template-icon">
                <i class="fas {getTemplateIcon(template)}"></i>
              </div>
              <div class="template-info">
                <h3 class="template-name">{template.name}</h3>
                <div class="template-id">ID: {template.id}</div>
              </div>
              <div class="template-actions-menu">
                <button 
                  class="action-button primary small"
                  on:click={() => openDuplicationForm(template)}
                  title="Duplicate this template"
                >
                  <i class="fas fa-copy"></i>
                </button>
              </div>
            </div>
            
            <div class="template-badge">
              <i class="fas fa-tag"></i>
              {template.template_type}
            </div>
            
            <p class="template-description">{template.description}</p>
            
            <div class="template-meta">
              <div class="meta-item">
                <i class="fas fa-code-branch"></i>
                <span>v{template.version}</span>
              </div>
              <div class="meta-item">
                <i class="fas fa-user"></i>
                <span>by {template.author}</span>
              </div>
              {#if template.created_date}
                <div class="meta-item">
                  <i class="fas fa-calendar"></i>
                  <span>Created {formatDate(template.created_date)}</span>
                </div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<!-- Template Duplication Modal -->
{#if showDuplicationForm}
  <div class="modal-overlay" on:click={closeDuplicationForm}>
    <div class="modal-container" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Duplicate Template</h2>
        <button class="close-button" on:click={closeDuplicationForm}>
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="modal-content">
        <div class="form-section">
          <h3>Template Information</h3>
          <p class="section-description">
            Select a source template and provide details for the new template.
          </p>
          
          <div class="form-grid">
            <!-- Source Template Selection -->
            <div class="form-group">
              <label for="source_template">Source Template *</label>
              <select 
                id="source_template"
                bind:value={duplicationForm.source_template}
                class="form-input"
                class:error={formErrors.source_template}
              >
                <option value="">Select a template to duplicate...</option>
                {#each templates as template}
                  <option value={template.id}>{template.name} ({template.id})</option>
                {/each}
              </select>
              {#if formErrors.source_template}
                <div class="field-error">{formErrors.source_template}</div>
              {/if}
            </div>
            
            <!-- New Template Name -->
            <div class="form-group">
              <label for="new_name">Template Name *</label>
              <input 
                id="new_name"
                type="text"
                bind:value={duplicationForm.new_name}
                on:input={() => generateTemplateId(duplicationForm.new_name)}
                placeholder="My Custom Template"
                class="form-input"
                class:error={formErrors.new_name}
              />
              {#if formErrors.new_name}
                <div class="field-error">{formErrors.new_name}</div>
              {/if}
            </div>
            
            <!-- New Template ID -->
            <div class="form-group">
              <label for="new_template_id">Template ID *</label>
              <input 
                id="new_template_id"
                type="text"
                bind:value={duplicationForm.new_template_id}
                placeholder="my-custom-template"
                class="form-input"
                class:error={formErrors.new_template_id}
              />
              <div class="field-help">Lowercase letters, numbers, and hyphens only</div>
              {#if formErrors.new_template_id}
                <div class="field-error">{formErrors.new_template_id}</div>
              {/if}
            </div>
            
            <!-- Version -->
            <div class="form-group">
              <label for="version">Version *</label>
              <input 
                id="version"
                type="text"
                bind:value={duplicationForm.version}
                placeholder="1.0.0"
                class="form-input"
                class:error={formErrors.version}
              />
              <div class="field-help">Semantic version format (e.g., 1.0.0)</div>
              {#if formErrors.version}
                <div class="field-error">{formErrors.version}</div>
              {/if}
            </div>
            
            <!-- Author -->
            <div class="form-group">
              <label for="author">Author *</label>
              <input 
                id="author"
                type="text"
                bind:value={duplicationForm.author}
                placeholder="Your Name"
                class="form-input"
                class:error={formErrors.author}
              />
              {#if formErrors.author}
                <div class="field-error">{formErrors.author}</div>
              {/if}
            </div>
          </div>
          
          <!-- Description -->
          <div class="form-group full-width">
            <label for="new_description">Description *</label>
            <textarea 
              id="new_description"
              bind:value={duplicationForm.new_description}
              placeholder="Describe what this template will be used for..."
              rows="3"
              class="form-input"
              class:error={formErrors.new_description}
            ></textarea>
            {#if formErrors.new_description}
              <div class="field-error">{formErrors.new_description}</div>
            {/if}
          </div>
        </div>
        
        <div class="duplication-info">
          <h4>What will be duplicated?</h4>
          <div class="info-grid">
            <div class="info-item">
              <i class="fas fa-server"></i>
              <span>Backend Components</span>
              <div class="info-details">Views, serializers, URLs, services</div>
            </div>
            <div class="info-item">
              <i class="fas fa-desktop"></i>
              <span>Frontend Components</span>
              <div class="info-details">Routes, components, services</div>
            </div>
            <div class="info-item">
              <i class="fas fa-cog"></i>
              <span>Configuration</span>
              <div class="info-details">Template settings and metadata</div>
            </div>
            <div class="info-item">
              <i class="fas fa-edit"></i>
              <span>Reference Updates</span>
              <div class="info-details">All file references will be updated</div>
            </div>
          </div>
        </div>
        
        <div class="modal-actions">
          <button class="action-button secondary" on:click={closeDuplicationForm}>
            Cancel
          </button>
          <button 
            class="action-button primary"
            on:click={duplicateTemplate}
            disabled={duplicating}
          >
            {#if duplicating}
              <i class="fas fa-spinner fa-spin"></i>
              Duplicating...
            {:else}
              <i class="fas fa-copy"></i>
              Create Template
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .template-management-page {
    min-height: 100vh;
    background: #f8fafc;
    padding: 24px;
  }
  
  .header-section {
    background: white;
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .header-content {
    display: flex;
    align-items: center;
    gap: 32px;
  }
  
  .page-title {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .title-icon {
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.5rem;
  }
  
  .title-text h1 {
    margin: 0 0 8px 0;
    font-size: 2rem;
    font-weight: 700;
    color: #111827;
  }
  
  .title-text p {
    margin: 0;
    color: #6b7280;
    font-size: 1rem;
  }
  
  .header-stats {
    display: flex;
    gap: 24px;
  }
  
  .stat-item {
    text-align: center;
  }
  
  .stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: #002147;
    margin-bottom: 4px;
  }
  
  .stat-label {
    font-size: 0.875rem;
    color: #6b7280;
    text-transform: uppercase;
    font-weight: 500;
  }
  
  .header-actions {
    display: flex;
    gap: 12px;
  }
  
  .action-button {
    padding: 12px 20px;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
  }
  
  .action-button.small {
    padding: 8px 12px;
    font-size: 0.8rem;
  }
  
  .action-button.primary {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
  }
  
  .action-button.primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 33, 71, 0.3);
  }
  
  .action-button.secondary {
    background: #f8fafc;
    color: #002147;
    border: 2px solid #e2e8f0;
  }
  
  .action-button.secondary:hover {
    background: #e2e8f0;
    color: #002147;
  }
  
  .action-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
  
  .loading-state, .empty-state {
    text-align: center;
    padding: 64px 32px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }
  
  .empty-icon {
    font-size: 4rem;
    color: #d1d5db;
    margin-bottom: 24px;
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
  
  .templates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 24px;
  }
  
  .template-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
    transition: all 0.2s ease;
    border: 1px solid #e5e7eb;
  }
  
  .template-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  }
  
  .card-header {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 16px;
  }
  
  .template-icon {
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
  
  .template-info {
    flex: 1;
    min-width: 0;
  }
  
  .template-name {
    margin: 0 0 8px 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: #111827;
    word-break: break-word;
  }
  
  .template-id {
    font-size: 0.75rem;
    color: #9ca3af;
    background: #f1f5f9;
    padding: 4px 8px;
    border-radius: 6px;
    font-family: 'Monaco', 'Menlo', monospace;
    width: fit-content;
  }
  
  .template-actions-menu {
    display: flex;
    gap: 8px;
  }
  
  .template-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #eff6ff;
    color: #1e40af;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.875rem;
    font-weight: 500;
    margin-bottom: 16px;
    border: 1px solid #dbeafe;
  }
  
  .template-description {
    color: #64748b;
    margin: 0 0 16px 0;
    line-height: 1.6;
    font-size: 0.9rem;
  }
  
  .template-meta {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .meta-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.875rem;
    color: #64748b;
  }
  
  .meta-item i {
    width: 16px;
    text-align: center;
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
    max-width: 800px;
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
    padding: 0;
  }
  
  .form-section {
    padding: 32px;
    border-bottom: 1px solid #e5e7eb;
  }
  
  .form-section h3 {
    margin: 0 0 8px 0;
    color: #111827;
    font-size: 1.125rem;
    font-weight: 600;
  }
  
  .section-description {
    color: #6b7280;
    margin: 0 0 24px 0;
    font-size: 0.9rem;
  }
  
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
  }
  
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .form-group.full-width {
    grid-column: 1 / -1;
  }
  
  .form-group label {
    font-weight: 500;
    color: #374151;
    font-size: 0.9rem;
  }
  
  .form-input {
    padding: 12px 16px;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    font-size: 0.9rem;
    transition: all 0.2s ease;
    background: #fafafa;
  }
  
  .form-input:focus {
    outline: none;
    border-color: #002147;
    background: white;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .form-input.error {
    border-color: #ef4444;
    background: #fef2f2;
  }
  
  .field-help {
    font-size: 0.8rem;
    color: #9ca3af;
  }
  
  .field-error {
    font-size: 0.8rem;
    color: #ef4444;
    font-weight: 500;
  }
  
  .duplication-info {
    padding: 32px;
    background: #f8fafc;
    border-bottom: 1px solid #e5e7eb;
  }
  
  .duplication-info h4 {
    margin: 0 0 20px 0;
    color: #111827;
    font-size: 1rem;
    font-weight: 600;
  }
  
  .info-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
  }
  
  .info-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 20px;
    background: white;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
  }
  
  .info-item i {
    font-size: 2rem;
    color: #002147;
    margin-bottom: 12px;
  }
  
  .info-item span {
    font-weight: 500;
    color: #111827;
    margin-bottom: 8px;
  }
  
  .info-details {
    font-size: 0.8rem;
    color: #6b7280;
  }
  
  .modal-actions {
    padding: 24px 32px;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
  
  @media (max-width: 768px) {
    .header-section {
      flex-direction: column;
      align-items: stretch;
      gap: 24px;
    }
    
    .header-content {
      flex-direction: column;
      align-items: stretch;
      gap: 16px;
    }
    
    .page-title {
      flex-direction: column;
      text-align: center;
    }
    
    .templates-grid {
      grid-template-columns: 1fr;
    }
    
    .form-grid {
      grid-template-columns: 1fr;
    }
    
    .info-grid {
      grid-template-columns: 1fr;
    }
    
    .modal-container {
      margin: 20px;
      max-width: calc(100% - 40px);
    }
  }
</style>
