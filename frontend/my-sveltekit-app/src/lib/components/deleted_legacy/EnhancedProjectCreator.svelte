<!-- src/lib/components/EnhancedProjectCreator.svelte -->
<script>
  import { createEventDispatcher } from 'svelte';
  import enhancedTemplateService from '$lib/services/templateService.js';
  import EnhancedTemplateSelector from './EnhancedTemplateSelector.svelte';
  
  // Events
  const dispatch = createEventDispatcher();
  
  // Form state
  let projectName = '';
  let projectDescription = '';
  let selectedTemplate = null;
  let creating = false;
  let error = null;
  let validationErrors = {};
  
  // Template configuration preview
  let showTemplateConfig = false;
  
  async function createProject() {
    // Reset errors
    error = null;
    validationErrors = {};
    
    // Validate form
    if (!validateForm()) {
      return;
    }
    
    try {
      creating = true;
      
      // Validate template before creation
      const templateValidation = await enhancedTemplateService.validateTemplate(selectedTemplate.id);
      
      if (!templateValidation.valid) {
        throw new Error(`Template validation failed: ${templateValidation.error}`);
      }
      
      // Create project with folder-based template
      const projectData = {
        name: projectName.trim(),
        description: projectDescription.trim(),
        template_id: selectedTemplate.id  // This is the folder name
      };
      
      console.log('Creating project with enhanced template system:', projectData);
      
      // Backend will clone complete template configuration
      const createdProject = await enhancedTemplateService.createProject(projectData);
      
      // Validate that complete configuration was cloned
      console.log('Created project with cloned config:', {
        total_pages: createdProject.total_pages,
        navigation_pages: createdProject.navigation_pages?.length,
        processing_capabilities: Object.keys(createdProject.processing_capabilities || {}).length,
        ui_configuration: Object.keys(createdProject.ui_configuration || {}).length,
        validation_rules: Object.keys(createdProject.validation_rules || {}).length
      });
      
      // Dispatch success event
      dispatch('projectCreated', {
        project: createdProject,
        template: selectedTemplate
      });
      
      // Reset form
      resetForm();
      
    } catch (err) {
      console.error('Failed to create project:', err);
      error = err.message;
    } finally {
      creating = false;
    }
  }
  
  function validateForm() {
    const errors = {};
    
    if (!projectName.trim()) {
      errors.name = 'Project name is required';
    } else if (projectName.trim().length < 3) {
      errors.name = 'Project name must be at least 3 characters';
    }
    
    if (!projectDescription.trim()) {
      errors.description = 'Project description is required';
    } else if (projectDescription.trim().length < 10) {
      errors.description = 'Project description must be at least 10 characters';
    }
    
    if (!selectedTemplate) {
      errors.template = 'Please select a template';
    }
    
    validationErrors = errors;
    return Object.keys(errors).length === 0;
  }
  
  function resetForm() {
    projectName = '';
    projectDescription = '';
    selectedTemplate = null;
    error = null;
    validationErrors = {};
    showTemplateConfig = false;
  }
  
  function onTemplateSelected(event) {
    selectedTemplate = event.detail;
    showTemplateConfig = true;
    
    // Clear template validation error if any
    if (validationErrors.template) {
      delete validationErrors.template;
      validationErrors = { ...validationErrors };
    }
    
    console.log('Template selected in creator:', selectedTemplate);
  }
  
  function clearError() {
    error = null;
  }
  
  // Reactive validation
  $: {
    if (projectName && validationErrors.name) {
      delete validationErrors.name;
      validationErrors = { ...validationErrors };
    }
    if (projectDescription && validationErrors.description) {
      delete validationErrors.description;
      validationErrors = { ...validationErrors };
    }
  }
</script>

<div class="enhanced-project-creator">
  <div class="creator-header">
    <h2>Create New Project</h2>
    <p>Create a project using the enhanced folder-based template system</p>
  </div>
  
  {#if error}
    <div class="error-alert">
      <i class="fas fa-exclamation-triangle"></i>
      <span>{error}</span>
      <button on:click={clearError}>×</button>
    </div>
  {/if}
  
  <form on:submit|preventDefault={createProject} class="project-form">
    <!-- Project Details Section -->
    <div class="form-section">
      <h3>Project Details</h3>
      
      <div class="form-group">
        <label for="projectName">
          Project Name
          <span class="required">*</span>
        </label>
        <input 
          id="projectName"
          type="text" 
          bind:value={projectName}
          placeholder="Enter a descriptive project name"
          class:error={validationErrors.name}
          disabled={creating}
        />
        {#if validationErrors.name}
          <div class="field-error">
            <i class="fas fa-exclamation-circle"></i>
            {validationErrors.name}
          </div>
        {/if}
      </div>
      
      <div class="form-group">
        <label for="projectDescription">
          Project Description
          <span class="required">*</span>
        </label>
        <textarea 
          id="projectDescription"
          bind:value={projectDescription}
          placeholder="Describe what you'll be analyzing in this project"
          rows="4"
          class:error={validationErrors.description}
          disabled={creating}
        ></textarea>
        {#if validationErrors.description}
          <div class="field-error">
            <i class="fas fa-exclamation-circle"></i>
            {validationErrors.description}
          </div>
        {/if}
      </div>
    </div>
    
    <!-- Template Selection Section -->
    <div class="form-section">
      <h3>
        Select Template
        <span class="required">*</span>
      </h3>
      {#if validationErrors.template}
        <div class="field-error">
          <i class="fas fa-exclamation-circle"></i>
          {validationErrors.template}
        </div>
      {/if}
      
      <EnhancedTemplateSelector 
        bind:selectedTemplate
        showConfiguration={showTemplateConfig}
        on:templateSelected={onTemplateSelected}
      />
    </div>
    
    <!-- Project Configuration Preview -->
    {#if selectedTemplate && selectedTemplate.configuration}
      <div class="form-section">
        <h3>Project Configuration Preview</h3>
        
        <div class="config-preview">
          <div class="preview-grid">
            <div class="preview-item">
              <div class="preview-icon">
                <i class="fas fa-sitemap"></i>
              </div>
              <div class="preview-content">
                <h4>Navigation</h4>
                <p>
                  {selectedTemplate.configuration.has_navigation ? 
                    `Multi-page (${selectedTemplate.configuration.total_pages} pages)` : 
                    'Single page layout'}
                </p>
              </div>
            </div>
            
            <div class="preview-item">
              <div class="preview-icon">
                <i class="fas fa-cogs"></i>
              </div>
              <div class="preview-content">
                <h4>Processing</h4>
                <p>
                  {Object.keys(selectedTemplate.configuration.processing_capabilities || {}).length} capabilities configured
                </p>
              </div>
            </div>
            
            <div class="preview-item">
              <div class="preview-icon">
                <i class="fas fa-palette"></i>
              </div>
              <div class="preview-content">
                <h4>UI Layout</h4>
                <p>
                  {selectedTemplate.configuration.ui_configuration?.layout || 'Default layout'}
                </p>
              </div>
            </div>
            
            <div class="preview-item">
              <div class="preview-icon">
                <i class="fas fa-brain"></i>
              </div>
              <div class="preview-content">
                <h4>AI Features</h4>
                <p>
                  {selectedTemplate.configuration.processing_capabilities?.supports_ai_analysis ? 
                    'AI analysis enabled' : 
                    'Basic processing'}
                </p>
              </div>
            </div>
          </div>
          
          <!-- Feature Details -->
          {#if selectedTemplate.configuration.navigation_pages?.length > 0}
            <div class="feature-details">
              <h4>Navigation Pages:</h4>
              <div class="pages-preview">
                {#each selectedTemplate.configuration.navigation_pages as page, index}
                  <div class="page-preview">
                    <span class="page-number">{index + 1}</span>
                    <i class="fas {page.icon || 'fa-file'}"></i>
                    <span class="page-name">{page.name}</span>
                    <small>({page.features?.length || 0} features)</small>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
    
    <!-- Form Actions -->
    <div class="form-actions">
      <button 
        type="button" 
        class="cancel-btn"
        on:click={resetForm}
        disabled={creating}
      >
        <i class="fas fa-times"></i>
        Cancel
      </button>
      
      <button 
        type="submit" 
        class="create-btn"
        disabled={creating || !selectedTemplate}
      >
        {#if creating}
          <i class="fas fa-spinner fa-spin"></i>
          Creating Project...
        {:else}
          <i class="fas fa-plus"></i>
          Create Project
        {/if}
      </button>
    </div>
  </form>
</div>

<style>
  .enhanced-project-creator {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
  }
  
  .creator-header {
    text-align: center;
    margin-bottom: 2rem;
  }
  
  .creator-header h2 {
    margin: 0 0 0.5rem 0;
    color: #002147;
    font-weight: 600;
  }
  
  .creator-header p {
    color: #6b7280;
    margin: 0;
  }
  
  .error-alert {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    color: #dc2626;
    margin-bottom: 1.5rem;
  }
  
  .error-alert button {
    margin-left: auto;
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: #dc2626;
  }
  
  .project-form {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }
  
  .form-section {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
  }
  
  .form-section h3 {
    margin: 0 0 1rem 0;
    color: #002147;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .required {
    color: #dc2626;
  }
  
  .form-group {
    margin-bottom: 1.5rem;
  }
  
  .form-group:last-child {
    margin-bottom: 0;
  }
  
  label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #374151;
  }
  
  input, textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
    transition: border-color 0.2s;
  }
  
  input:focus, textarea:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  input.error, textarea.error {
    border-color: #dc2626;
  }
  
  input:disabled, textarea:disabled {
    background: #f9fafb;
    color: #6b7280;
  }
  
  .field-error {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    color: #dc2626;
    font-size: 0.875rem;
  }
  
  .config-preview {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1.5rem;
  }
  
  .preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  
  .preview-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem;
    background: white;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
  }
  
  .preview-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: #002147;
    color: white;
    border-radius: 6px;
    font-size: 1rem;
  }
  
  .preview-content h4 {
    margin: 0 0 0.25rem 0;
    color: #002147;
    font-size: 0.875rem;
    font-weight: 600;
  }
  
  .preview-content p {
    margin: 0;
    color: #6b7280;
    font-size: 0.75rem;
  }
  
  .feature-details h4 {
    margin: 0 0 0.75rem 0;
    color: #002147;
    font-size: 0.875rem;
    font-weight: 600;
  }
  
  .pages-preview {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  
  .page-preview {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.75rem;
  }
  
  .page-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    background: #002147;
    color: white;
    border-radius: 50%;
    font-size: 0.625rem;
    font-weight: 600;
  }
  
  .page-name {
    font-weight: 500;
    color: #374151;
  }
  
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #e5e7eb;
  }
  
  .cancel-btn, .create-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .cancel-btn {
    background: white;
    border: 1px solid #d1d5db;
    color: #6b7280;
  }
  
  .cancel-btn:hover {
    background: #f9fafb;
    border-color: #9ca3af;
  }
  
  .create-btn {
    background: #002147;
    border: 1px solid #002147;
    color: white;
  }
  
  .create-btn:hover:not(:disabled) {
    background: #001a36;
  }
  
  .create-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .cancel-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
