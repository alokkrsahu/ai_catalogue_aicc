<!-- Medical Template Selection Page -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { createTemplateLogger } from '$lib/logging/logger';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { toasts } from '$lib/stores/toast';
  import type { MedicalTemplate, UniversalProject } from '$lib/templates/types';
  
  const logger = createTemplateLogger('medical', 'SelectionPage');
  
  let template: any | null = null;
  let loading = true;
  let showCreateForm = false;
  let creatingProject = false;
  
  // Project creation form data
  let projectName = '';
  let projectDescription = '';
  
  onMount(() => {
    logger.componentMount('MedicalSelectionPage');
    loadTemplateConfiguration();
  });
  
  async function loadTemplateConfiguration() {
    logger.templateAction('load_configuration', 'medical');
    
    try {
      loading = true;
      const configResult = await cleanUniversalApi.getTemplateConfiguration('medical');
      template = configResult.discovery || configResult;
      logger.templateAction('configuration_loaded', 'medical', template);
    } catch (error) {
      logger.error('Failed to load template configuration', error);
      toasts.error('Failed to load Medical template configuration');
    } finally {
      loading = false;
    }
  }
  
  async function createProject() {
    if (!projectName.trim() || !projectDescription.trim()) {
      toasts.error('Please fill in all required fields');
      return;
    }
    
    logger.templateAction('create_project_start', 'medical', {
      name: projectName,
      description: projectDescription
    });
    
    try {
      creatingProject = true;
      
      const projectData = {
        name: projectName.trim(),
        description: projectDescription.trim(),
        template_id: 'medical'
      };
      
      const newProject = await cleanUniversalApi.createProject(projectData);
      
      logger.templateAction('project_created', 'medical', newProject);
      toasts.success(`Medical project "${projectName}" created successfully`);
      
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
  <title>Medical Template - AI Catalogue</title>
</svelte:head>

<div class="template-selection-page">
  <!-- Header Section -->
  <div class="header-section medical-theme">
    <div class="template-hero">
      <div class="hero-icon">
        <i class="fas fa-user-md"></i>
      </div>
      <div class="hero-content">
        <h1>Medical Document Template</h1>
        <p class="hero-description">
          Healthcare document analysis with HIPAA compliance and clinical features
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
        Create Medical Project
      </button>
    </div>
  </div>
  
  <!-- Template Information -->
  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading medical template configuration...</p>
    </div>
  {:else if template}
    <div class="template-details">
      <!-- HIPAA Compliance -->
      {#if template.hipaa_compliance}
        <div class="compliance-badge">
          <div class="compliance-icon">
            <i class="fas fa-shield-alt"></i>
          </div>
          <div class="compliance-content">
            <h3>HIPAA Compliant</h3>
            <p>This template meets HIPAA requirements for healthcare data protection</p>
          </div>
        </div>
      {/if}
      
      <!-- Medical Document Types -->
      {#if template.medical_document_types && template.medical_document_types.length > 0}
        <div class="document-types-section">
          <h2>Supported Medical Document Types</h2>
          <div class="document-types-grid">
            {#each template.medical_document_types as docType}
              <div class="document-type-card medical">
                <div class="doc-type-header">
                  <i class="fas fa-file-medical"></i>
                  <h3>{docType.type}</h3>
                  <div class="privacy-badge {docType.privacy_level}">
                    {docType.privacy_level}
                  </div>
                </div>
                <p>{docType.description}</p>
              </div>
            {/each}
          </div>
        </div>
      {/if}
      
      <!-- Clinical Features -->
      {#if template.clinical_features && template.clinical_features.length > 0}
        <div class="clinical-section">
          <h2>Clinical Features</h2>
          <div class="clinical-grid">
            {#each template.clinical_features as feature}
              <div class="clinical-card">
                <div class="clinical-header">
                  <i class="fas fa-stethoscope"></i>
                  <h3>{feature.feature}</h3>
                </div>
                <p>{feature.description}</p>
                {#if feature.medical_standards && feature.medical_standards.length > 0}
                  <div class="standards-list">
                    <span class="standards-label">Medical Standards:</span>
                    <div class="standards-tags">
                      {#each feature.medical_standards as standard}
                        <span class="standard-tag">{standard}</span>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}
      
      <!-- Key Features -->
      <div class="features-section">
        <h2>Key Features</h2>
        <div class="features-grid">
          <div class="feature-card medical">
            <div class="feature-icon">
              <i class="fas fa-heartbeat"></i>
            </div>
            <div class="feature-content">
              <h3>Clinical Data Processing</h3>
              <p>Specialized analysis for medical records, lab results, and clinical notes</p>
            </div>
          </div>
          
          <div class="feature-card medical">
            <div class="feature-icon">
              <i class="fas fa-shield-alt"></i>
            </div>
            <div class="feature-content">
              <h3>HIPAA Compliance</h3>
              <p>Full compliance with healthcare data protection regulations</p>
            </div>
          </div>
          
          <div class="feature-card medical">
            <div class="feature-icon">
              <i class="fas fa-search-plus"></i>
            </div>
            <div class="feature-content">
              <h3>Medical Term Extraction</h3>
              <p>Automatic identification of medical terminology and codes</p>
            </div>
          </div>
          
          <div class="feature-card medical">
            <div class="feature-icon">
              <i class="fas fa-chart-line"></i>
            </div>
            <div class="feature-content">
              <h3>Clinical Analytics</h3>
              <p>Advanced analytics for patient data and treatment outcomes</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  {:else}
    <div class="error-state">
      <div class="error-icon">
        <i class="fas fa-exclamation-triangle"></i>
      </div>
      <h3>Template Not Available</h3>
      <p>The Medical template configuration could not be loaded.</p>
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
      <div class="modal-header medical-theme">
        <h2>Create Medical Project</h2>
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
              placeholder="e.g., Patient Records Analysis"
              class="form-input"
              required
            />
          </div>
          
          <div class="form-group">
            <label for="projectDescription">Description *</label>
            <textarea 
              id="projectDescription"
              bind:value={projectDescription}
              placeholder="Describe the medical documents you'll be analyzing and your clinical objectives"
              class="form-textarea"
              rows="4"
              required
            ></textarea>
          </div>
          
          <div class="template-info medical">
            <div class="info-icon">
              <i class="fas fa-user-md"></i>
            </div>
            <div class="info-content">
              <p><strong>This project will use the Medical template</strong></p>
              <p>HIPAA-compliant healthcare document analysis with clinical features and medical terminology extraction.</p>
            </div>
          </div>
          
          <div class="hipaa-notice">
            <div class="notice-icon">
              <i class="fas fa-shield-alt"></i>
            </div>
            <div class="notice-content">
              <p><strong>HIPAA Compliance Notice</strong></p>
              <p>This template is designed to maintain HIPAA compliance. Ensure all data handling procedures follow your organization's healthcare data policies.</p>
            </div>
          </div>
          
          <div class="form-actions">
            <button type="button" class="action-button secondary" on:click={closeCreateForm}>
              Cancel
            </button>
            <button 
              type="submit" 
              class="action-button primary medical"
              disabled={creatingProject || !projectName.trim() || !projectDescription.trim()}
            >
              {#if creatingProject}
                <i class="fas fa-spinner fa-spin"></i>
                Creating Project...
              {:else}
                <i class="fas fa-user-md"></i>
                Create Medical Project
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
  
  .header-section.medical-theme {
    background: linear-gradient(135deg, #047857 0%, #065f46 100%);
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
    border-top: 3px solid #047857;
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
    background: #047857;
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
    background: #065f46;
  }
  
  .template-details {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }
  
  .compliance-badge {
    background: linear-gradient(135deg, #ecfdf5, #d1fae5);
    border: 2px solid #10b981;
    border-radius: 16px;
    padding: 24px;
    display: flex;
    align-items: center;
    gap: 20px;
    box-shadow: 0 4px 16px rgba(16, 185, 129, 0.1);
  }
  
  .compliance-icon {
    width: 60px;
    height: 60px;
    background: #10b981;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.5rem;
  }
  
  .compliance-content h3 {
    margin: 0 0 8px 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: #047857;
  }
  
  .compliance-content p {
    margin: 0;
    color: #065f46;
    font-size: 1rem;
  }
  
  .document-types-section, .clinical-section, .features-section {
    background: white;
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }
  
  .document-types-section h2, .clinical-section h2, .features-section h2 {
    margin: 0 0 24px 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
  }
  
  .document-types-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
  }
  
  .document-type-card.medical {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 20px;
  }
  
  .doc-type-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    position: relative;
  }
  
  .doc-type-header i {
    color: #047857;
    font-size: 1.125rem;
  }
  
  .doc-type-header h3 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #047857;
    flex: 1;
  }
  
  .privacy-badge {
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
  }
  
  .privacy-badge.public {
    background: #dbeafe;
    color: #1e40af;
  }
  
  .privacy-badge.restricted {
    background: #fed7aa;
    color: #c2410c;
  }
  
  .privacy-badge.confidential {
    background: #fecaca;
    color: #dc2626;
  }
  
  .document-type-card p {
    margin: 0;
    color: #6b7280;
    line-height: 1.5;
    font-size: 0.875rem;
  }
  
  .clinical-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 20px;
  }
  
  .clinical-card {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 20px;
  }
  
  .clinical-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }
  
  .clinical-header i {
    color: #047857;
    font-size: 1.125rem;
  }
  
  .clinical-header h3 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #047857;
  }
  
  .clinical-card p {
    margin: 0 0 12px 0;
    color: #6b7280;
    line-height: 1.5;
    font-size: 0.875rem;
  }
  
  .standards-label {
    font-weight: 600;
    color: #047857;
    font-size: 0.8rem;
    display: block;
    margin-bottom: 8px;
  }
  
  .standards-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  
  .standard-tag {
    background: #047857;
    color: white;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 500;
  }
  
  .features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
  }
  
  .feature-card.medical {
    background: #ecfdf5;
    border-radius: 12px;
    padding: 24px;
    display: flex;
    align-items: flex-start;
    gap: 16px;
    border: 1px solid #a7f3d0;
  }
  
  .feature-icon {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #047857, #065f46);
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
    color: #047857;
  }
  
  .feature-content p {
    margin: 0;
    color: #6b7280;
    line-height: 1.5;
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
  
  .modal-header.medical-theme {
    padding: 24px 32px;
    background: linear-gradient(135deg, #047857 0%, #065f46 100%);
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
    border-color: #047857;
    box-shadow: 0 0 0 3px rgba(4, 120, 87, 0.1);
  }
  
  .form-textarea {
    resize: vertical;
    min-height: 100px;
  }
  
  .template-info.medical {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    display: flex;
    gap: 16px;
  }
  
  .info-icon {
    color: #047857;
    font-size: 1.25rem;
    flex-shrink: 0;
  }
  
  .info-content p {
    margin: 0 0 8px 0;
    color: #047857;
    font-size: 0.875rem;
    line-height: 1.5;
  }
  
  .info-content p:last-child {
    margin-bottom: 0;
  }
  
  .hipaa-notice {
    background: #fef3c7;
    border: 1px solid #f59e0b;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    display: flex;
    gap: 16px;
  }
  
  .notice-icon {
    color: #d97706;
    font-size: 1.25rem;
    flex-shrink: 0;
  }
  
  .notice-content p {
    margin: 0 0 8px 0;
    color: #92400e;
    font-size: 0.875rem;
    line-height: 1.5;
  }
  
  .notice-content p:last-child {
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
  
  .action-button.primary.medical {
    background: linear-gradient(135deg, #047857, #065f46);
    color: white;
  }
  
  .action-button.primary.medical:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(4, 120, 87, 0.3);
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
    
    .compliance-badge {
      flex-direction: column;
      text-align: center;
    }
    
    .document-types-grid, .clinical-grid, .features-grid {
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
