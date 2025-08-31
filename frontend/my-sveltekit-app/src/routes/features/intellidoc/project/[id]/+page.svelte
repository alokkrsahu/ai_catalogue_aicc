<!-- Clean Universal Project Interface - Template Independent -->
<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { toasts } from '$lib/stores/toast';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import ApiManagement from '$lib/components/project/ApiManagement.svelte';
  import AdminDeleteButton from '$lib/components/AdminDeleteButton.svelte';
  import { isAdmin } from '$lib/stores/auth';
  
  // Get project ID from URL
  $: projectId = $page.params.id;
  
  // State variables
  let project: any = null;
  let loading = true;
  let uploadedDocuments: any[] = [];
  let dragActive = false;
  let uploading = false;
  let fileInput: HTMLInputElement; // File input reference
  let folderInput: HTMLInputElement; // Folder input reference
  let zipInput: HTMLInputElement; // Zip input reference
  
  // Processing state
  let processing = false;
  let processingStatus: any = null;
  
  // Navigation state (capability-based, not template-based)
  let currentPage = 1;
  let hasNavigation = false;
  let navigationPages: any[] = [];
  let sidebarCollapsed = false;
  
  // Capability-based UI state
  let projectCapabilities: any = {};
  
  // API Management modal state
  let showApiManagement = false;
  
  console.log(`🎯 UNIVERSAL: Initializing universal project interface for project ${projectId}`);
  
  // Toggle sidebar function
  function toggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
  }
  
  onMount(() => {
    loadProject();
  });
  
  async function loadProject() {
    try {
      loading = true;
      console.log(`📄 UNIVERSAL: Loading project ${projectId}`);
      
      // Load project using universal API (works for ALL projects regardless of template)
      project = await cleanUniversalApi.getProject(projectId);
      
      // Extract capabilities from cloned project data (not template files)
      projectCapabilities = project.processing_capabilities || {};
      hasNavigation = project.has_navigation || false;
      navigationPages = project.navigation_pages || [];
      
      // Set up navigation based on cloned project data
      if (hasNavigation && project.total_pages > 1) {
        currentPage = 1;
      }
      
      console.log('✅ UNIVERSAL: Project loaded successfully', {
        name: project.name,
        template_type: project.template_type,
        has_navigation: hasNavigation,
        total_pages: project.total_pages,
        capabilities: Object.keys(projectCapabilities)
      });
      
      // Load documents and status
      await Promise.all([
        loadDocuments(),
        loadProcessingStatus()
      ]);
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Failed to load project:', error);
      toasts.error('Failed to load project');
      goto('/features/intellidoc');
    } finally {
      loading = false;
    }
  }
  
  async function loadDocuments() {
    try {
      console.log(`📄 UNIVERSAL: Loading documents for project ${projectId}`);
      const documents = await cleanUniversalApi.getDocuments(projectId);
      uploadedDocuments = documents;
      
      console.log(`✅ UNIVERSAL: Loaded ${documents.length} documents`);
    } catch (error) {
      console.error('❌ UNIVERSAL: Failed to load documents:', error);
      toasts.error('Failed to load documents');
    }
  }
  
  async function loadProcessingStatus() {
    try {
      console.log(`📊 UNIVERSAL: Loading processing status for project ${projectId}`);
      processingStatus = await cleanUniversalApi.getProcessingStatus(projectId);
      
      console.log('✅ UNIVERSAL: Processing status loaded');
    } catch (error) {
      console.error('❌ UNIVERSAL: Failed to load processing status:', error);
    }
  }
  
  // File upload handlers
  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      uploadFiles(Array.from(input.files));
    }
  }

  function handleFolderSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      console.log(`📁 UNIVERSAL: Selected folder with ${input.files.length} files`);
      uploadFiles(Array.from(input.files), 'bulk');
    }
  }

  function handleZipSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      const file = input.files[0];
      if (file.name.toLowerCase().endsWith('.zip')) {
        console.log(`📦 UNIVERSAL: Selected zip file: ${file.name}`);
        uploadFiles([file], 'zip');
      } else {
        toasts.error('Please select a zip file (.zip)');
      }
    }
  }
  
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
    
    if (event.dataTransfer?.files) {
      const files = Array.from(event.dataTransfer.files);
      
      // Check if it's a single zip file
      if (files.length === 1 && files[0].name.toLowerCase().endsWith('.zip')) {
        uploadFiles(files, 'zip');
      } else {
        uploadFiles(files, 'bulk');
      }
    }
  }
  
  async function uploadFiles(files: File[], uploadType: 'single' | 'bulk' | 'zip' = 'bulk') {
    if (uploading) return;
    
    try {
      uploading = true;
      console.log(`📤 UNIVERSAL: Uploading ${files.length} files to project ${projectId} (type: ${uploadType})`);
      
      let result;
      if (uploadType === 'single') {
        // Single file upload (original behavior)
        for (const file of files) {
          await cleanUniversalApi.uploadDocument(projectId, file);
        }
        result = { total_successful: files.length, total_failed: 0 };
      } else if (uploadType === 'zip' && files.length === 1) {
        // Zip file upload
        result = await cleanUniversalApi.uploadZipFile(projectId, files[0]);
        
        // Show detailed results for zip uploads
        if (result.failed_extractions && result.failed_extractions.length > 0) {
          const failedFilesList = result.failed_extractions.map(f => `${f.filename}: ${f.error}`).slice(0, 3).join('; ');
          const moreFailures = result.failed_extractions.length > 3 ? ` and ${result.failed_extractions.length - 3} more...` : '';
          toasts.warning(`Zip extraction had some failures: ${failedFilesList}${moreFailures}`);
        }
        
        if (result.extracted_files_info && result.extracted_files_info.length > 0) {
          const extractedInfo = result.extracted_files_info.map(f => f.filename).slice(0, 5).join(', ');
          const moreFiles = result.extracted_files_info.length > 5 ? ` and ${result.extracted_files_info.length - 5} more...` : '';
          console.log(`📦 UNIVERSAL: Extracted files with paths: ${extractedInfo}${moreFiles}`);
        }
      } else {
        // Bulk file upload
        result = await cleanUniversalApi.uploadBulkFiles(projectId, files);
        
        // Show detailed results for bulk uploads
        if (result.failed_uploads && result.failed_uploads.length > 0) {
          const failedFilesList = result.failed_uploads.map(f => `${f.filename}: ${f.error}`).slice(0, 3).join('; ');
          const moreFailures = result.failed_uploads.length > 3 ? ` and ${result.failed_uploads.length - 3} more...` : '';
          toasts.warning(`Bulk upload had some failures: ${failedFilesList}${moreFailures}`);
        }
      }
      
      console.log('✅ UNIVERSAL: Upload completed successfully');
      
      const successCount = result.total_successful || result.total_extracted || files.length;
      const failCount = result.total_failed || 0;
      
      if (successCount > 0) {
        toasts.success(`Successfully uploaded ${successCount} file(s)${failCount > 0 ? ` (${failCount} failed)` : ''}`);
      } else {
        toasts.error('No files were uploaded successfully');
      }
      
      // Reload documents
      await loadDocuments();
      
    } catch (error) {
      console.error('❌ UNIVERSAL: File upload failed:', error);
      toasts.error(`Upload failed: ${error.message}`);
    } finally {
      uploading = false;
    }
  }
  
  async function deleteDocument(documentId: string, documentName: string) {
    if (!confirm(`Are you sure you want to delete "${documentName}"?`)) {
      return;
    }
    
    try {
      console.log(`🗑️ UNIVERSAL: Deleting document ${documentId} from project ${projectId}`);
      await cleanUniversalApi.deleteDocument(projectId, documentId);
      
      console.log('✅ UNIVERSAL: Document deleted successfully');
      toasts.success(`Deleted "${documentName}" successfully`);
      
      // Reload documents
      await loadDocuments();
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Document deletion failed:', error);
      toasts.error(`Failed to delete document: ${error.message}`);
    }
  }
  
  async function processDocuments() {
    if (processing) return;
    
    try {
      processing = true;
      console.log(`🚀 UNIVERSAL: Starting document processing for project ${projectId}`);
      
      const result = await cleanUniversalApi.processDocuments(projectId);
      
      console.log('✅ UNIVERSAL: Document processing started');
      toasts.success('Document processing started successfully');
      
      // Reload status
      await loadProcessingStatus();
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Document processing failed:', error);
      toasts.error(`Processing failed: ${error.message}`);
    } finally {
      processing = false;
    }
  }
  
  // Search functionality
  let searchQuery = '';
  let searchResults: any[] = [];
  let searching = false;
  
  async function searchDocuments() {
    if (!searchQuery.trim() || searching) return;
    
    try {
      searching = true;
      console.log(`🔍 UNIVERSAL: Searching documents in project ${projectId}: "${searchQuery}"`);
      
      const results = await cleanUniversalApi.searchDocuments(projectId, searchQuery.trim());
      searchResults = results.results || [];
      
      console.log(`✅ UNIVERSAL: Search completed, ${searchResults.length} results found`);
      
      if (searchResults.length === 0) {
        toasts.info('No results found for your search');
      }
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Search failed:', error);
      toasts.error(`Search failed: ${error.message}`);
      searchResults = [];
    } finally {
      searching = false;
    }
  }
  
  // Navigation functions (capability-based)
  function goToNextPage() {
    if (hasNavigation && currentPage < project.total_pages) {
      currentPage++;
    }
  }
  
  function goToPreviousPage() {
    if (hasNavigation && currentPage > 1) {
      currentPage--;
    }
  }
  
  function goToPage(page: number) {
    if (hasNavigation && page >= 1 && page <= project.total_pages) {
      currentPage = page;
    }
  }
</script>

<svelte:head>
  <title>{project?.name || 'Project'} - AI Catalogue</title>
</svelte:head>

{#if loading}
  <div class="flex items-center justify-center min-h-96">
    <div class="text-center">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
      <p class="text-oxford-blue">Loading project...</p>
    </div>
  </div>
{:else if project}
  <div class="min-h-screen bg-gray-50 flex w-full">
    <!-- Left Sidebar Navigation (if supported by project capabilities) -->
    {#if hasNavigation && navigationPages.length > 0}
      <div class="{sidebarCollapsed ? 'w-16' : 'w-64'} bg-white border-r border-gray-200 transition-all duration-300 flex flex-col shadow-lg">
        <!-- Sidebar Header -->
        <div class="p-4 border-b border-gray-200">
          <div class="flex items-center {sidebarCollapsed ? 'justify-center' : 'justify-between'}">
            {#if !sidebarCollapsed}
              <h3 class="text-lg font-bold text-gray-900">Navigation</h3>
            {/if}
            <button
              class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              on:click={toggleSidebar}
              title={sidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            >
              <i class="fas {sidebarCollapsed ? 'fa-chevron-right' : 'fa-chevron-left'} text-gray-600"></i>
            </button>
          </div>
        </div>
        
        <!-- Navigation Items -->
        <nav class="flex-1 p-4">
          <div class="space-y-2">
            {#each navigationPages as navPage, index}
              <button
                class="w-full flex items-center {sidebarCollapsed ? 'justify-center p-3' : 'p-4'} rounded-xl font-medium transition-all duration-200 {currentPage === index + 1 
                  ? 'bg-oxford-blue shadow-lg' 
                  : 'text-gray-600 hover:text-oxford-blue hover:bg-blue-50 hover:shadow-md'}"
                on:click={() => goToPage(index + 1)}
                title={sidebarCollapsed ? navPage.name : ''}
              >
                <div class="flex-shrink-0">
                  <i class="fas {navPage.icon} text-lg {currentPage === index + 1 ? '!text-white' : 'text-gray-600'}"></i>
                </div>
                {#if !sidebarCollapsed}
                  <div class="ml-4 text-left flex-1">
                    <div class="font-semibold text-sm {currentPage === index + 1 ? '!text-white' : 'text-gray-600'}">{navPage.name}</div>
                    {#if navPage.features && navPage.features.length > 0}
                      <div class="text-xs opacity-75 mt-1 {currentPage === index + 1 ? '!text-white' : 'text-gray-500'}">
                        {navPage.features.slice(0, 2).join(' • ')}
                      </div>
                    {/if}
                  </div>
                  {#if currentPage === index + 1}
                    <div class="flex-shrink-0">
                      <i class="fas fa-check text-sm bg-white bg-opacity-20 rounded-full p-1 !text-white"></i>
                    </div>
                  {/if}
                {/if}
              </button>
            {/each}
          </div>
        </nav>
      </div>
    {/if}
    
    <!-- Main Content Area -->
    <div class="flex-1 flex flex-col">
      <!-- Project Header -->
      <div class="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div class="w-full px-6">
          <div class="flex items-center justify-between py-6">
            <div class="flex items-center space-x-4">
              <div class="w-12 h-12 bg-oxford-blue text-white rounded-xl flex items-center justify-center shadow-lg">
                <i class="fas {project.icon_class} text-lg"></i>
              </div>
              <div>
                <h1 class="text-3xl font-bold text-gray-900">{project.name}</h1>
                <p class="text-lg text-gray-600">{project.description}</p>
                <div class="flex items-center space-x-6 mt-2 text-sm text-gray-500">
                  <span class="flex items-center">
                    <i class="fas fa-layer-group mr-2"></i>
                    Template: {project.template_name}
                  </span>
                  <span class="flex items-center">
                    <i class="fas fa-calendar mr-2"></i>
                    Created: {new Date(project.created_at).toLocaleDateString()}
                  </span>
                  {#if uploadedDocuments.length > 0}
                    <span class="flex items-center">
                      <i class="fas fa-files mr-2"></i>
                      {uploadedDocuments.length} documents
                    </span>
                  {/if}
                </div>
              </div>
            </div>
            
            <!-- Header Actions -->
            <div class="flex items-center space-x-4">
              <!-- API Management Button -->
              <button
                class="inline-flex items-center px-4 py-2 bg-white border-2 border-oxford-blue text-oxford-blue rounded-lg hover:bg-oxford-blue hover:text-white transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                on:click={() => showApiManagement = true}
                title="Manage project-specific API keys"
              >
                <i class="fas fa-key mr-2"></i>
                API Management
              </button>
              <div class="text-right">
                <div class="inline-flex items-center px-3 py-2 rounded-full text-sm font-medium bg-green-100 text-green-800 border border-green-200">
                  <i class="fas fa-check-circle mr-2"></i>
                  Template Independent
                </div>
                <div class="text-xs text-gray-500 mt-1 text-right">Universal Interface v1.0</div>
              </div>
              
              {#if processingStatus}
                <div class="bg-white border border-gray-200 rounded-lg p-3 min-w-[200px]">
                  <div class="flex items-center justify-between text-sm mb-2">
                    <span class="font-medium text-gray-700">Processing Status</span>
                    <span class="text-oxford-blue font-semibold">{processingStatus.vector_status?.processing_status || 'Ready'}</span>
                  </div>
                  {#if processingStatus.vector_status?.total_documents > 0}
                    <div class="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        class="bg-oxford-blue h-2 rounded-full transition-all duration-300"
                        style="width: {Math.min(100, (processingStatus.vector_status.ready_documents / processingStatus.vector_status.total_documents) * 100)}%"
                      ></div>
                    </div>
                    <div class="text-xs text-gray-500 mt-1">
                      {processingStatus.vector_status.ready_documents}/{processingStatus.vector_status.total_documents} processed
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          </div>
        </div>
      </div>
    
    <!-- Page Content (Capability-Based) - Full Width Layout -->
    <div class="flex-1 w-full px-6 py-8">
      {#if !hasNavigation || currentPage === 1}
        <!-- Page 1: Document Management (Enhanced Full Width Layout) -->
        <div class="grid grid-cols-1 xl:grid-cols-12 gap-8">
          <!-- Left Section: Upload & Documents (8 columns) -->
          <div class="xl:col-span-8 space-y-6">
            <!-- Upload Section -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div class="px-6 py-4 bg-oxford-blue text-white">
                <h2 class="text-xl font-bold flex items-center !text-white">
                  <i class="fas fa-upload mr-3 !text-white"></i>
                  Document Upload
                </h2>
                <p class="mt-1 !text-white">Upload your documents to get started</p>
              </div>
              
              <!-- Upload Area -->
              <div class="p-6">
                <div
                  class="border-2 border-dashed rounded-xl p-12 text-center transition-all duration-300 {dragActive 
                    ? 'border-oxford-blue bg-blue-50 scale-105' 
                    : 'border-gray-300 hover:border-oxford-blue hover:bg-gray-50'}"
                  on:dragover={handleDragOver}
                  on:dragleave={handleDragLeave}
                  on:drop={handleDrop}
                >
                  {#if uploading}
                    <div class="animate-spin rounded-full h-12 w-12 border-b-4 border-oxford-blue mx-auto mb-4"></div>
                    <p class="text-oxford-blue font-semibold text-lg">Uploading documents...</p>
                    <p class="text-gray-500 text-sm mt-1">Please wait while we process your files</p>
                  {:else}
                    <i class="fas fa-cloud-upload-alt text-6xl text-gray-400 mb-6"></i>
                    <h3 class="text-xl font-semibold text-gray-700 mb-2">Drop files here or choose upload method</h3>
                    <p class="text-gray-500 mb-6">Supports PDF, Word, Text, Markdown files, folders, and zip archives up to 50MB each</p>
                    
                    <!-- Hidden file inputs -->
                    <input
                      type="file"
                      multiple
                      class="hidden"
                      bind:this={fileInput}
                      on:change={handleFileSelect}
                      accept=".pdf,.doc,.docx,.txt,.md,.rtf"
                    >
                    <input
                      type="file"
                      multiple
                      webkitdirectory
                      class="hidden"
                      bind:this={folderInput}
                      on:change={handleFolderSelect}
                    >
                    <input
                      type="file"
                      class="hidden"
                      bind:this={zipInput}
                      on:change={handleZipSelect}
                      accept=".zip"
                    >
                    
                    <!-- Upload buttons -->
                    <div class="flex flex-wrap gap-3 justify-center">
                      <button
                        class="inline-flex items-center px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                        on:click={() => fileInput?.click()}
                      >
                        <i class="fas fa-file mr-2"></i>
                        Select Files
                      </button>
                      
                      <button
                        class="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                        on:click={() => folderInput?.click()}
                      >
                        <i class="fas fa-folder mr-2"></i>
                        Select Folder
                      </button>
                      
                      <button
                      class="inline-flex items-center px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-800 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                      on:click={() => zipInput?.click()}
                      >
                        <i class="fas fa-file-archive mr-2"></i>
                        Upload Zip
                      </button>
                    </div>
                    
                    <div class="mt-4 text-xs text-gray-500 text-center">
                      <p><strong>Files:</strong> Select individual files to upload</p>
                      <p><strong>Folder:</strong> Upload all files from a folder and its subfolders</p>
                      <p><strong>Zip:</strong> Upload a zip file and automatically extract all contents</p>
                    </div>
                  {/if}
                </div>
              </div>
            </div>
            
            <!-- Documents List -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div class="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <div class="flex items-center justify-between">
                  <h2 class="text-xl font-bold text-gray-900 flex items-center">
                    <i class="fas fa-file-alt mr-3 text-oxford-blue"></i>
                    Documents
                    <span class="ml-2 bg-oxford-blue text-white text-sm px-2 py-1 rounded-full">{uploadedDocuments.length}</span>
                  </h2>
                  {#if uploadedDocuments.length > 0}
                    <div class="text-sm text-gray-500">
                      Total: {uploadedDocuments.reduce((total, doc) => total + (doc.file_size || 0), 0) > 1024 * 1024 ? 
                        Math.round(uploadedDocuments.reduce((total, doc) => total + (doc.file_size || 0), 0) / (1024 * 1024)) + ' MB' : 
                        Math.round(uploadedDocuments.reduce((total, doc) => total + (doc.file_size || 0), 0) / 1024) + ' KB'}
                    </div>
                  {/if}
                </div>
              </div>
              
              <div class="p-6">
                {#if uploadedDocuments.length === 0}
                  <div class="text-center py-12">
                    <i class="fas fa-folder-open text-5xl text-gray-300 mb-4"></i>
                    <h3 class="text-lg font-medium text-gray-700 mb-2">No documents uploaded yet</h3>
                    <p class="text-gray-500">Upload documents to get started with AI analysis</p>
                  </div>
                {:else}
                  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {#each uploadedDocuments as doc}
                      <div class="flex items-start p-4 border border-gray-200 rounded-lg hover:border-oxford-blue hover:shadow-md transition-all duration-200 group">
                        <div class="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-oxford-blue to-blue-600 text-white rounded-lg flex items-center justify-center mr-4">
                          <i class="fas fa-file text-sm"></i>
                        </div>
                        <div class="flex-1 min-w-0">
                          <p class="font-medium text-gray-900 truncate">{doc.original_filename || doc.filename}</p>
                          <div class="flex items-center text-sm text-gray-500 mt-1 space-x-4">
                            <span class="flex items-center">
                              <i class="fas fa-weight-hanging mr-1"></i>
                              {doc.file_size_formatted || 'Unknown size'}
                            </span>
                            <span class="flex items-center">
                              <i class="fas fa-circle mr-1 {doc.upload_status === 'ready' ? 'text-green-500' : 'text-yellow-500'}"></i>
                              {doc.upload_status || 'ready'}
                            </span>
                          </div>
                        </div>
                        <div class="opacity-0 group-hover:opacity-100 transition-all duration-200 ml-2">
                          <AdminDeleteButton
                            size="small"
                            itemName={doc.original_filename || doc.filename}
                            on:delete={() => deleteDocument(doc.document_id || doc.id, doc.original_filename || doc.filename)}
                          />
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>
          </div>
          
          <!-- Right Section: Processing & Stats (4 columns) -->
          <div class="xl:col-span-4 space-y-6">
            <!-- Quick Stats -->
            <div class="bg-oxford-blue text-white rounded-xl p-6">
              <h3 class="text-lg font-semibold mb-4 !text-white">Project Overview</h3>
              <div class="grid grid-cols-2 gap-4">
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{uploadedDocuments.length}</div>
                  <div class="text-sm !text-white opacity-80">Documents</div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{processingStatus?.vector_status?.ready_documents || 0}</div>
                  <div class="text-sm !text-white opacity-80">Processed</div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{project.total_pages}</div>
                  <div class="text-sm !text-white opacity-80">Pages</div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{hasNavigation ? 'Multi' : 'Single'}</div>
                  <div class="text-sm !text-white opacity-80">Page Mode</div>
                </div>
              </div>
            </div>
            
            <!-- Processing Section -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div class="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 class="text-lg font-bold text-gray-900 flex items-center">
                  <i class="fas fa-cogs mr-3 text-oxford-blue"></i>
                  Document Processing
                </h2>
              </div>
              
              <div class="p-6">
                {#if processingStatus}
                  <div class="mb-6">
                    <div class="flex items-center justify-between text-sm mb-3">
                      <span class="font-medium text-gray-700">Status</span>
                      <span class="font-semibold text-oxford-blue capitalize">
                        {processingStatus.vector_status?.processing_status || 'Ready'}
                      </span>
                    </div>
                    
                    {#if processingStatus.vector_status?.total_documents > 0}
                      <div class="w-full bg-gray-200 rounded-full h-3 mb-2">
                        <div 
                          class="bg-oxford-blue h-3 rounded-full transition-all duration-500"
                          style="width: {Math.min(100, (processingStatus.vector_status.ready_documents / processingStatus.vector_status.total_documents) * 100)}%"
                        ></div>
                      </div>
                      <div class="flex justify-between text-xs text-gray-500">
                        <span>{processingStatus.vector_status.ready_documents} processed</span>
                        <span>{processingStatus.vector_status.total_documents} total</span>
                      </div>
                    {/if}
                  </div>
                {/if}
                
                <button
                  class="w-full flex items-center justify-center px-6 py-3 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg"
                  on:click={processDocuments}
                  disabled={processing || uploadedDocuments.length === 0}
                >
                  {#if processing}
                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3"></div>
                    Processing...
                  {:else}
                    <i class="fas fa-play mr-3"></i>
                    {uploadedDocuments.length === 0 ? 'Upload documents first' : 'Start Processing'}
                  {/if}
                </button>
                
                {#if uploadedDocuments.length > 0}
                  <div class="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div class="flex items-start">
                      <i class="fas fa-info-circle text-blue-500 mt-0.5 mr-2"></i>
                      <div class="text-xs text-blue-700">
                        <p class="font-medium">Processing will:</p>
                        <ul class="mt-1 space-y-1">
                          <li>• Analyze document content with AI</li>
                          <li>• Create searchable embeddings</li>
                          <li>• Enable advanced features</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                {/if}
              </div>
            </div>
            
            <!-- Template Info -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div class="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 class="text-lg font-bold text-gray-900 flex items-center">
                  <i class="fas fa-info-circle mr-3 text-oxford-blue"></i>
                  Template Info
                </h2>
              </div>
              
              <div class="p-6 space-y-4">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-600">Template Type</span>
                  <span class="font-medium text-gray-900">{project.template_type}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-600">Architecture</span>
                  <span class="font-medium text-green-600">Independent</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-600">Interface Version</span>
                  <span class="font-medium text-gray-900">Universal v1.0</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      {/if}
    
    {#if hasNavigation && currentPage === 2}
      <!-- Page 2: Agent Orchestration (Capability-Based Rendering) -->
      {#if project.processing_capabilities?.supports_agent_orchestration}
        <div class="agent-orchestration-page h-full flex-1 w-full">
          {#await import('$lib/components/AgentOrchestrationInterface.svelte')}
            <div class="flex items-center justify-center min-h-96">
              <div class="text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
                <p class="text-oxford-blue">Loading Agent Orchestration...</p>
              </div>
            </div>
          {:then AgentOrchestrationModule}
            <svelte:component this={AgentOrchestrationModule.default} {project} {projectId} />
          {:catch error}
            <div class="flex items-center justify-center min-h-96">
              <div class="text-center">
                <div class="w-16 h-16 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                  <i class="fas fa-exclamation-triangle text-2xl"></i>
                </div>
                <h2 class="text-xl font-bold text-gray-900 mb-2">Loading Error</h2>
                <p class="text-gray-600">Failed to load agent orchestration interface.</p>
                <button 
                  class="mt-4 px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
                  on:click={() => window.location.reload()}
                >
                  <i class="fas fa-refresh mr-2"></i>
                  Retry
                </button>
              </div>
            </div>
          {/await}
        </div>
      {:else}
        <div class="flex items-center justify-center min-h-96">
          <div class="text-center">
            <div class="w-16 h-16 bg-oxford-blue text-white rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
              <i class="fas fa-robot text-2xl"></i>
            </div>
            <h2 class="text-xl font-bold text-gray-900 mb-2">Agent Orchestration</h2>
            <p class="text-gray-600 mb-4">This project template does not support agent orchestration.</p>
            <div class="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div class="flex items-start">
                <i class="fas fa-info-circle text-blue-500 mt-0.5 mr-2"></i>
                <div class="text-sm text-blue-700">
                  <p class="font-medium">To use agent orchestration:</p>
                  <p class="mt-1">Create a new project using the AICC-IntelliDoc v2 template</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      {/if}
    {/if}
    
    {#if hasNavigation && currentPage === 3}
      <!-- Page 3: Coming Soon -->
      <div class="flex items-center justify-center min-h-96">
        <div class="text-center">
          <div class="w-16 h-16 bg-oxford-blue text-white rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <i class="fas fa-cube text-2xl"></i>
          </div>
          <h2 class="text-xl font-bold text-gray-900 mb-2">Page 3</h2>
          <p class="text-gray-600 mb-4">Coming Soon</p>
          <div class="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm">
            <i class="fas fa-clock mr-2"></i>
            This feature is under development
          </div>
        </div>
      </div>
    {/if}
    
    {#if hasNavigation && currentPage === 4}
      <!-- Page 4: Coming Soon -->
      <div class="flex items-center justify-center min-h-96">
        <div class="text-center">
          <div class="w-16 h-16 bg-oxford-blue text-white rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <i class="fas fa-lightbulb text-2xl"></i>
          </div>
          <h2 class="text-xl font-bold text-gray-900 mb-2">Page 4</h2>
          <p class="text-gray-600 mb-4">Coming Soon</p>
          <div class="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm">
            <i class="fas fa-clock mr-2"></i>
            This feature is under development
          </div>
        </div>
      </div>
    {/if}
    
    {#if hasNavigation && currentPage === 5}
      <!-- Page 5: Coming Soon -->
      <div class="flex items-center justify-center min-h-96">
        <div class="text-center">
          <div class="w-16 h-16 bg-oxford-blue text-white rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <i class="fas fa-star text-2xl"></i>
          </div>
          <h2 class="text-xl font-bold text-gray-900 mb-2">Page 5</h2>
          <p class="text-gray-600 mb-4">Coming Soon</p>
          <div class="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm">
            <i class="fas fa-clock mr-2"></i>
            This feature is under development
          </div>
        </div>
      </div>
    {/if}
      </div>
    </div>
  </div>
{:else}
  <div class="flex items-center justify-center min-h-96">
    <div class="text-center">
      <i class="fas fa-exclamation-triangle text-4xl text-red-400 mb-4"></i>
      <h2 class="text-xl font-bold text-gray-900 mb-2">Project not found</h2>
      <p class="text-gray-600">The project you're looking for doesn't exist or you don't have access to it.</p>
      <button
        class="mt-4 px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
        on:click={() => goto('/features/intellidoc')}
      >
        <i class="fas fa-arrow-left mr-2"></i>
        Back to Projects
      </button>
    </div>
  </div>
{/if}

<style>
  :global(.oxford-blue) {
    color: #002147;
  }
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  :global(.bg-oxford-blue-dark) {
    background-color: #001122;
  }
  :global(.line-clamp-3) {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>

<!-- API Management Modal -->
<ApiManagement 
  {projectId}
  projectName={project?.name || ''}
  bind:showModal={showApiManagement}
  on:close={() => showApiManagement = false}
/>
