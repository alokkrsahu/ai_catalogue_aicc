<!-- AICC-IntelliDoc Template-Specific Project Interface Component -->
<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import { universalProjectApi } from '$lib/services/universalProjectApi';
  import { createUniversalLogger } from '$lib/logging/logger';
  import MultiPageNavigation from '$lib/components/MultiPageNavigation.svelte';
  import LoadingIndicator from '$lib/components/LoadingIndicator.svelte';
  import AdminDeleteButton from '$lib/components/AdminDeleteButton.svelte';
  
  export let projectId: string;
  export let project: any = null;
  
  const logger = createUniversalLogger('AICCIntelliDocProjectInterface');
  const dispatch = createEventDispatcher();
  
  // AICC-IntelliDoc specific state
  let currentPage = 1;
  let processingStatus: any = null;
  let uploadedDocuments: any[] = [];
  let searchResults: any[] = [];
  let searchQuery = '';
  let isSearching = false;
  let dragActive = false;
  let uploading = false;
  
  // Template-specific capabilities from cloned project data
  let templateCapabilities: any = {};
  let navigationPages: any[] = [];
  let suggestedQuestions: string[] = [];
  
  logger.info(`Initializing AICC-IntelliDoc interface for project ${projectId}`);
  
  onMount(() => {
    if (project) {
      initializeAICCInterface();
    }
  });
  
  $: if (project) {
    initializeAICCInterface();
  }
  
  function initializeAICCInterface() {
    // Verify this is an AICC-IntelliDoc project
    if (project.template_type !== 'aicc-intellidoc') {
      logger.error(`Project is not AICC-IntelliDoc type: ${project.template_type}`);
      dispatch('error', { message: 'Project is not compatible with AICC-IntelliDoc interface' });
      return;
    }
    
    // Extract AICC-specific configuration from cloned project data
    templateCapabilities = project.processing_capabilities || {};
    navigationPages = project.navigation_pages || [];
    suggestedQuestions = project.suggested_questions || [];
    
    // Initialize navigation if project supports it
    if (project.has_navigation && project.total_pages > 1) {
      currentPage = 1;
    }
    
    logger.info('AICC-IntelliDoc interface initialized', {
      has_navigation: project.has_navigation,
      total_pages: project.total_pages,
      capabilities: Object.keys(templateCapabilities),
      suggested_questions: suggestedQuestions.length
    });
    
    // Load initial data
    loadDocuments();
    loadProcessingStatus();
  }
  
  async function loadDocuments() {
    try {
      logger.projectAction('load_documents', projectId);
      const documents = await universalProjectApi.getDocuments(projectId);
      uploadedDocuments = documents;
      
      logger.info(`Loaded ${documents.length} documents for AICC-IntelliDoc project`);
      dispatch('documentsLoaded', { documents });
    } catch (error) {
      logger.error('Failed to load documents', error);
      dispatch('error', { message: 'Failed to load documents' });
    }
  }
  
  async function loadProcessingStatus() {
    try {
      logger.projectAction('load_processing_status', projectId);
      const status = await universalProjectApi.getStatus(projectId);
      processingStatus = status;
      
      logger.info('AICC processing status loaded', status);
      dispatch('statusLoaded', { status });
    } catch (error) {
      logger.error('Failed to load processing status', error);
      // Non-critical error, continue without status
    }
  }
  
  // Navigation functions
  function goToNextPage() {
    if (currentPage < project.total_pages) {
      currentPage++;
      logger.info(`AICC Navigation: moved to page ${currentPage}`);
      dispatch('pageChanged', { page: currentPage });
    }
  }
  
  function goToPreviousPage() {
    if (currentPage > 1) {
      currentPage--;
      logger.info(`AICC Navigation: moved to page ${currentPage}`);
      dispatch('pageChanged', { page: currentPage });
    }
  }
  
  function goToPage(page: number) {
    if (page >= 1 && page <= project.total_pages) {
      currentPage = page;
      logger.info(`AICC Navigation: jumped to page ${currentPage}`);
      dispatch('pageChanged', { page: currentPage });
    }
  }
  
  // File handling
  function handleDragOver(event: DragEvent) {
    event.preventDefault();
    dragActive = true;
  }
  
  function handleDragLeave(event: DragEvent) {
    event.preventDefault();
    dragActive = false;
  }
  
  function handleDrop(event: DragEvent) {
    event.preventDefault();
    dragActive = false;
    
    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      uploadFiles(Array.from(event.dataTransfer.files));
    }
  }
  
  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      uploadFiles(Array.from(input.files));
    }
  }
  
  async function uploadFiles(files: File[]) {
    uploading = true;
    logger.fileOperation('upload_start', { 
      file_count: files.length, 
      file_names: files.map(f => f.name),
      template_type: 'aicc-intellidoc'
    });
    
    try {
      const result = await universalProjectApi.uploadDocuments(projectId, files);
      
      logger.fileOperation('upload_success', result);
      dispatch('filesUploaded', { result });
      
      // Reload documents
      await loadDocuments();
      
    } catch (error) {
      logger.fileOperation('upload_failed', { error: error.message });
      dispatch('error', { message: `Upload failed: ${error.message}` });
    } finally {
      uploading = false;
    }
  }
  
  // AICC-IntelliDoc specific processing
  async function processDocuments() {
    if (!uploadedDocuments.length) {
      dispatch('warning', { message: 'No documents to process' });
      return;
    }
    
    try {
      logger.projectAction('process_documents_start', projectId, { template_type: 'aicc-intellidoc' });
      dispatch('info', { message: 'Starting AICC-IntelliDoc enhanced processing...' });
      
      // Use universal processing API (automatically selects AICC-IntelliDoc optimal mode)
      const result = await universalProjectApi.processDocuments(projectId);
      
      logger.projectAction('process_documents_completed', projectId, result);
      
      if (result.status === 'completed') {
        dispatch('success', { message: 'AICC-IntelliDoc processing completed successfully! 🎯' });
        if (result.universal_features?.enhanced_hierarchical_support) {
          dispatch('success', { message: '✨ Enhanced hierarchical analysis enabled!' });
        }
      } else {
        dispatch('error', { message: `Processing failed: ${result.message || 'Unknown error'}` });
      }
      
      // Reload status
      await loadProcessingStatus();
      
    } catch (error) {
      logger.projectAction('process_documents_failed', projectId, error);
      dispatch('error', { message: `AICC-IntelliDoc processing failed: ${error.message}` });
    }
  }
  
  // AICC-IntelliDoc specific search
  async function searchDocuments(query: string = searchQuery) {
    if (!query.trim()) {
      dispatch('warning', { message: 'Please enter a search query' });
      return;
    }
    
    isSearching = true;
    
    try {
      logger.projectAction('search_documents', projectId, { 
        query, 
        template_type: 'aicc-intellidoc' 
      });
      
      // Use universal search API (automatically uses AICC-IntelliDoc optimal search mode)
      const results = await universalProjectApi.searchDocuments(projectId, query);
      
      searchResults = results.results || [];
      
      logger.projectAction('search_completed', projectId, {
        query,
        result_count: results.total_results,
        search_mode: results.search_mode
      });
      
      dispatch('success', { 
        message: `Found ${results.total_results} results using ${results.search_mode} search` 
      });
      dispatch('searchCompleted', { results, query });
      
    } catch (error) {
      logger.projectAction('search_failed', projectId, error);
      dispatch('error', { message: `Search failed: ${error.message}` });
    } finally {
      isSearching = false;
    }
  }
  
  function useSuggestedQuestion(question: string) {
    searchQuery = question;
    searchDocuments(question);
  }
  
  function deleteDocument(documentId: string, filename: string) {
    if (confirm(`Delete "${filename}"?`)) {
      logger.fileOperation('delete_document', { 
        document_id: documentId, 
        filename,
        template_type: 'aicc-intellidoc'
      });
      dispatch('deleteDocument', { documentId, filename });
    }
  }
  
  function formatFileSize(bytes: number) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
  
  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
</script>

<!-- AICC-IntelliDoc Project Interface -->
<div class="aicc-interface">
  
  <!-- AICC-IntelliDoc Header -->
  <div class="aicc-header">
    <div class="aicc-template-info">
      <div class="aicc-template-badge">
        <i class="fas fa-robot"></i>
        <span>AICC-IntelliDoc v2.0</span>
      </div>
      
      <!-- Processing Status Badge -->
      {#if processingStatus}
        <div class="aicc-status-badge status-{processingStatus.status?.toLowerCase() || 'pending'}">
          <i class="fas fa-{processingStatus.status === 'completed' ? 'check-circle' : processingStatus.status === 'failed' ? 'exclamation-circle' : 'clock'}"></i>
          <span>{processingStatus.status || 'PENDING'}</span>
          {#if processingStatus.processed_documents > 0}
            <span class="status-count">({processingStatus.processed_documents}/{processingStatus.total_documents || uploadedDocuments.length})</span>
          {/if}
        </div>
      {/if}
    </div>
    
    <!-- AICC-IntelliDoc Multi-Page Navigation -->
    {#if project?.has_navigation && project?.total_pages > 1}
      <MultiPageNavigation 
        {currentPage} 
        totalPages={project.total_pages}
        pages={navigationPages}
        {goToNextPage}
        {goToPreviousPage}
        {goToPage}
      />
    {/if}
  </div>

  <!-- Main Content Based on Current Page -->
  {#if !project?.has_navigation || currentPage === 1}
    <!-- Page 1: Document Management -->
    <div class="aicc-content-section">
      <h2 class="aicc-section-title">
        <i class="fas fa-upload"></i>
        Document Upload & Management
      </h2>
      
      <!-- File Upload Area -->
      <div class="aicc-upload-zone">
        <div 
          class="aicc-upload-area {dragActive ? 'drag-active' : ''}"
          on:dragover={handleDragOver}
          on:dragleave={handleDragLeave}
          on:drop={handleDrop}
          on:click={() => document.getElementById('aiccFileInput')?.click()}
        >
          <div class="aicc-upload-content">
            <i class="fas fa-cloud-upload-alt aicc-upload-icon"></i>
            <h3>Drop files here or click to browse</h3>
            <p>Optimized for AICC-IntelliDoc intelligent analysis</p>
            <p class="aicc-upload-note">Supported: PDF, DOC, DOCX, TXT, MD, RTF | Max: 50MB</p>
          </div>
          
          <input 
            type="file" 
            id="aiccFileInput" 
            multiple 
            accept=".pdf,.doc,.docx,.txt,.md,.rtf"
            on:change={handleFileSelect}
            style="display: none;"
          />
        </div>

        {#if uploading}
          <div class="aicc-upload-progress">
            <LoadingIndicator size="small" />
            <span>Uploading files for AICC analysis...</span>
          </div>
        {/if}
      </div>

      <!-- Processing Button -->
      {#if uploadedDocuments.length > 0}
        <div class="aicc-actions">
          <button 
            class="aicc-process-button"
            on:click={processDocuments}
            disabled={uploading}
          >
            <i class="fas fa-magic"></i>
            <span>Start AICC-IntelliDoc Analysis</span>
          </button>
        </div>
      {/if}

      <!-- Documents List -->
      {#if uploadedDocuments.length > 0}
        <div class="aicc-documents">
          <h3 class="aicc-subsection-title">
            <i class="fas fa-file-alt"></i>
            Uploaded Documents ({uploadedDocuments.length})
          </h3>
          
          <div class="aicc-documents-grid">
            {#each uploadedDocuments as document}
              <div class="aicc-document-card">
                <div class="aicc-document-header">
                  <div class="aicc-document-icon">
                    <i class="fas fa-file-pdf"></i>
                  </div>
                  <div class="aicc-document-info">
                    <h4 class="aicc-document-title">{document.original_filename || document.filename}</h4>
                    <div class="aicc-document-meta">
                      <span><i class="fas fa-weight"></i> {formatFileSize(document.file_size)}</span>
                      <span><i class="fas fa-calendar"></i> {formatDate(document.uploaded_at)}</span>
                    </div>
                  </div>
                  <AdminDeleteButton
                    size="small"
                    itemName={document.original_filename || document.filename}
                    on:delete={() => deleteDocument(document.id || document.document_id, document.original_filename || document.filename)}
                  />
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}

  {#if project?.has_navigation && currentPage === 2}
    <!-- Page 2: AICC-IntelliDoc Analysis & Search -->
    <div class="aicc-content-section">
      <h2 class="aicc-section-title">
        <i class="fas fa-search"></i>
        Intelligent Document Search
      </h2>
      
      <!-- Search Interface -->
      <div class="aicc-search-section">
        <div class="aicc-search-bar">
          <input 
            type="text" 
            bind:value={searchQuery}
            placeholder="Enter your search query for intelligent analysis..."
            class="aicc-search-input"
            on:keydown={(e) => e.key === 'Enter' && searchDocuments()}
          />
          <button 
            class="aicc-search-button" 
            on:click={() => searchDocuments()}
            disabled={isSearching}
          >
            {#if isSearching}
              <LoadingIndicator size="small" />
            {:else}
              <i class="fas fa-search"></i>
            {/if}
            <span>{isSearching ? 'Searching...' : 'Search'}</span>
          </button>
        </div>
        
        <!-- AICC-IntelliDoc Suggested Questions -->
        {#if suggestedQuestions.length > 0}
          <div class="aicc-suggested-questions">
            <h4>Suggested Analytical Questions:</h4>
            <div class="aicc-questions-grid">
              {#each suggestedQuestions as question}
                <button 
                  class="aicc-question-button"
                  on:click={() => useSuggestedQuestion(question)}
                >
                  {question}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>
      
      <!-- Search Results -->
      {#if searchResults.length > 0}
        <div class="aicc-results-section">
          <h3 class="aicc-subsection-title">
            <i class="fas fa-list"></i>
            Search Results ({searchResults.length})
          </h3>
          
          <div class="aicc-results-list">
            {#each searchResults as result, index}
              <div class="aicc-result-card">
                <div class="aicc-result-header">
                  <span class="aicc-result-rank">#{index + 1}</span>
                  <h4 class="aicc-result-title">{result.document_name || 'Document'}</h4>
                  <span class="aicc-result-score">Score: {result.score?.toFixed(3) || 'N/A'}</span>
                </div>
                <div class="aicc-result-content">
                  <p>{result.content || result.text || 'No content available'}</p>
                </div>
                {#if result.metadata}
                  <div class="aicc-result-meta">
                    <small>Page: {result.metadata.page || 'N/A'} | Section: {result.metadata.section || 'N/A'}</small>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {:else if searchQuery && !isSearching}
        <div class="aicc-no-results">
          <i class="fas fa-search"></i>
          <p>No results found for "{searchQuery}". Try a different query or ensure documents are processed.</p>
        </div>
      {/if}
    </div>
  {/if}

  {#if project?.has_navigation && currentPage === 3}
    <!-- Page 3: AICC-IntelliDoc Analytics Dashboard -->
    <div class="aicc-content-section">
      <h2 class="aicc-section-title">
        <i class="fas fa-chart-bar"></i>
        Analytics Dashboard
      </h2>
      
      <div class="aicc-analytics-grid">
        <div class="aicc-analytics-card">
          <h4>Document Analysis</h4>
          <p class="aicc-metric">{uploadedDocuments.length}</p>
          <span class="aicc-metric-label">Documents Processed</span>
        </div>
        
        <div class="aicc-analytics-card">
          <h4>Processing Status</h4>
          <p class="aicc-metric">{processingStatus?.status || 'Not Started'}</p>
          <span class="aicc-metric-label">Current Status</span>
        </div>
        
        <div class="aicc-analytics-card">
          <h4>Template Features</h4>
          <p class="aicc-metric">{Object.keys(templateCapabilities).length}</p>
          <span class="aicc-metric-label">Capabilities Enabled</span>
        </div>
        
        <div class="aicc-analytics-card">
          <h4>Search Queries</h4>
          <p class="aicc-metric">{searchResults.length}</p>
          <span class="aicc-metric-label">Latest Results</span>
        </div>
      </div>
      
      <!-- Template Capabilities Display -->
      {#if Object.keys(templateCapabilities).length > 0}
        <div class="aicc-capabilities-section">
          <h3 class="aicc-subsection-title">
            <i class="fas fa-cogs"></i>
            AICC-IntelliDoc Capabilities
          </h3>
          
          <div class="aicc-capabilities-grid">
            {#each Object.entries(templateCapabilities) as [key, value]}
              <div class="aicc-capability-card">
                <h5>{key.replace(/_/g, ' ').toUpperCase()}</h5>
                <p>{typeof value === 'boolean' ? (value ? 'Enabled' : 'Disabled') : JSON.stringify(value)}</p>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}

  {#if project?.has_navigation && currentPage === 4}
    <!-- Page 4: AICC-IntelliDoc Advanced Features -->
    <div class="aicc-content-section">
      <h2 class="aicc-section-title">
        <i class="fas fa-cogs"></i>
        Advanced AICC-IntelliDoc Features
      </h2>
      
      <div class="aicc-advanced-features">
        <div class="aicc-feature-info">
          <h3>Template Configuration</h3>
          <p>This project was created from the AICC-IntelliDoc template with the following configuration:</p>
          
          <div class="aicc-config-display">
            <div class="aicc-config-item">
              <strong>Template Type:</strong> {project.template_type}
            </div>
            <div class="aicc-config-item">
              <strong>Template Name:</strong> {project.template_name}
            </div>
            <div class="aicc-config-item">
              <strong>Navigation:</strong> {project.has_navigation ? 'Enabled' : 'Disabled'}
            </div>
            <div class="aicc-config-item">
              <strong>Total Pages:</strong> {project.total_pages}
            </div>
            <div class="aicc-config-item">
              <strong>Analysis Focus:</strong> {project.analysis_focus || 'General document analysis'}
            </div>
          </div>
        </div>
        
        <!-- Advanced Actions -->
        <div class="aicc-advanced-actions">
          <h3>Advanced Operations</h3>
          <div class="aicc-actions-grid">
            <button class="aicc-action-button" on:click={() => dispatch('exportData')}>
              <i class="fas fa-download"></i>
              <span>Export Analysis Data</span>
            </button>
            
            <button class="aicc-action-button" on:click={() => dispatch('generateReport')}>
              <i class="fas fa-file-chart"></i>
              <span>Generate Report</span>
            </button>
            
            <button class="aicc-action-button" on:click={() => dispatch('advancedSettings')}>
              <i class="fas fa-cogs"></i>
              <span>Advanced Settings</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  /* AICC-IntelliDoc Component Specific Styling */
  .aicc-interface {
    width: 100%;
    background: white;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0, 33, 71, 0.08);
    border: 1px solid #e2e8f0;
  }

  .aicc-header {
    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
    padding: 1.5rem 2rem;
    border-bottom: 1px solid #e2e8f0;
  }

  .aicc-template-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .aicc-template-badge {
    background: linear-gradient(135deg, #002147, #334e68);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .aicc-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .status-completed {
    background: #dcfce7;
    color: #166534;
  }

  .status-failed {
    background: #fee2e2;
    color: #dc2626;
  }

  .status-pending {
    background: #fef3c7;
    color: #d97706;
  }

  .aicc-content-section {
    padding: 2rem;
  }

  .aicc-section-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #002147;
    margin: 0 0 2rem 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .aicc-subsection-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #002147;
    margin: 0 0 1.5rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* Upload Section */
  .aicc-upload-zone {
    margin-bottom: 2rem;
  }

  .aicc-upload-area {
    border: 2px dashed #cbd5e1;
    border-radius: 12px;
    padding: 3rem 2rem;
    text-align: center;
    transition: all 0.3s ease;
    cursor: pointer;
    background: #f8fafc;
  }

  .aicc-upload-area:hover,
  .aicc-upload-area.drag-active {
    border-color: #002147;
    background: #f0f9ff;
    transform: translateY(-2px);
  }

  .aicc-upload-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
  }

  .aicc-upload-icon {
    font-size: 3rem;
    color: #002147;
    margin-bottom: 0.5rem;
  }

  .aicc-upload-content h3 {
    margin: 0;
    color: #002147;
    font-size: 1.25rem;
    font-weight: 600;
  }

  .aicc-upload-content p {
    margin: 0;
    color: #64748b;
    font-size: 0.875rem;
  }

  .aicc-upload-note {
    color: #059669 !important;
    font-weight: 500;
  }

  .aicc-upload-progress {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    justify-content: center;
    margin-top: 1rem;
    color: #64748b;
    font-size: 0.875rem;
  }

  /* Actions */
  .aicc-actions {
    margin-bottom: 2rem;
    display: flex;
    justify-content: center;
  }

  .aicc-process-button {
    background: linear-gradient(135deg, #002147, #334e68);
    color: white;
    border: none;
    padding: 1rem 2rem;
    border-radius: 12px;
    font-size: 1.125rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    box-shadow: 0 4px 20px rgba(0, 33, 71, 0.3);
  }

  .aicc-process-button:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0, 33, 71, 0.4);
  }

  .aicc-process-button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  /* Documents */
  .aicc-documents {
    margin-top: 2rem;
  }

  .aicc-documents-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: 1.5rem;
  }

  .aicc-document-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1.5rem;
    transition: all 0.2s ease;
  }

  .aicc-document-card:hover {
    box-shadow: 0 4px 15px rgba(0, 33, 71, 0.1);
    transform: translateY(-1px);
  }

  .aicc-document-header {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .aicc-document-icon {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #002147, #334e68);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.25rem;
    flex-shrink: 0;
  }

  .aicc-document-info {
    flex: 1;
    min-width: 0;
  }

  .aicc-document-title {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: #002147;
    word-break: break-word;
  }

  .aicc-document-meta {
    display: flex;
    gap: 1rem;
    font-size: 0.75rem;
    color: #64748b;
  }

  .aicc-delete-button {
    background: #fee2e2;
    color: #dc2626;
    border: none;
    padding: 0.5rem;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .aicc-delete-button:hover {
    background: #fecaca;
    transform: scale(1.05);
  }

  /* Search Section */
  .aicc-search-section {
    margin-bottom: 2rem;
  }

  .aicc-search-bar {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .aicc-search-input {
    flex: 1;
    padding: 1rem;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 1rem;
    transition: all 0.2s ease;
  }

  .aicc-search-input:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }

  .aicc-search-button {
    background: linear-gradient(135deg, #059669, #10b981);
    color: white;
    border: none;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 120px;
    justify-content: center;
  }

  .aicc-search-button:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(5, 150, 105, 0.3);
  }

  .aicc-search-button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .aicc-suggested-questions {
    background: #f8fafc;
    border-radius: 8px;
    padding: 1.5rem;
  }

  .aicc-suggested-questions h4 {
    margin: 0 0 1rem 0;
    color: #002147;
    font-weight: 600;
  }

  .aicc-questions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 0.75rem;
  }

  .aicc-question-button {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 0.75rem;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: 0.875rem;
  }

  .aicc-question-button:hover {
    border-color: #002147;
    background: #f0f9ff;
  }

  /* Search Results */
  .aicc-results-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .aicc-result-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1.5rem;
    transition: all 0.2s ease;
  }

  .aicc-result-card:hover {
    box-shadow: 0 2px 8px rgba(0, 33, 71, 0.1);
  }

  .aicc-result-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }

  .aicc-result-rank {
    background: #002147;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .aicc-result-title {
    flex: 1;
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: #002147;
  }

  .aicc-result-score {
    background: #e2e8f0;
    color: #64748b;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
  }

  .aicc-result-content p {
    margin: 0 0 0.5rem 0;
    color: #374151;
    line-height: 1.5;
  }

  .aicc-result-meta {
    color: #64748b;
    font-size: 0.75rem;
    border-top: 1px solid #e2e8f0;
    padding-top: 0.5rem;
  }

  .aicc-no-results {
    text-align: center;
    padding: 3rem;
    color: #64748b;
  }

  .aicc-no-results i {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.5;
  }

  /* Analytics */
  .aicc-analytics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
  }

  .aicc-analytics-card {
    background: #f8fafc;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    border: 1px solid #e2e8f0;
    transition: all 0.2s ease;
  }

  .aicc-analytics-card:hover {
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.1);
  }

  .aicc-analytics-card h4 {
    margin: 0 0 1rem 0;
    color: #002147;
    font-weight: 600;
  }

  .aicc-metric {
    font-size: 2rem;
    font-weight: 700;
    color: #002147;
    margin: 0 0 0.5rem 0;
  }

  .aicc-metric-label {
    color: #64748b;
    font-size: 0.875rem;
  }

  /* Capabilities */
  .aicc-capabilities-section {
    margin-top: 2rem;
  }

  .aicc-capabilities-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1rem;
  }

  .aicc-capability-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
  }

  .aicc-capability-card h5 {
    margin: 0 0 0.5rem 0;
    color: #002147;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .aicc-capability-card p {
    margin: 0;
    color: #64748b;
    font-size: 0.75rem;
  }

  /* Advanced Features */
  .aicc-advanced-features {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
  }

  .aicc-feature-info {
    background: #f8fafc;
    border-radius: 12px;
    padding: 1.5rem;
  }

  .aicc-feature-info h3 {
    margin: 0 0 1rem 0;
    color: #002147;
    font-weight: 600;
  }

  .aicc-config-display {
    background: white;
    border-radius: 8px;
    padding: 1rem;
    border: 1px solid #e2e8f0;
  }

  .aicc-config-item {
    padding: 0.5rem 0;
    border-bottom: 1px solid #f1f5f9;
    font-size: 0.875rem;
  }

  .aicc-config-item:last-child {
    border-bottom: none;
  }

  .aicc-advanced-actions h3 {
    margin: 0 0 1rem 0;
    color: #002147;
    font-weight: 600;
  }

  .aicc-actions-grid {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .aicc-action-button {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
    transition: all 0.2s ease;
    color: #002147;
    font-weight: 500;
  }

  .aicc-action-button:hover {
    border-color: #002147;
    background: #f0f9ff;
    transform: translateY(-1px);
  }

  /* Responsive Design */
  @media (max-width: 768px) {
    .aicc-header,
    .aicc-content-section {
      padding: 1rem;
    }
    
    .aicc-documents-grid {
      grid-template-columns: 1fr;
    }
    
    .aicc-search-bar {
      flex-direction: column;
    }
    
    .aicc-analytics-grid {
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }
    
    .aicc-advanced-features {
      grid-template-columns: 1fr;
    }
  }
</style>