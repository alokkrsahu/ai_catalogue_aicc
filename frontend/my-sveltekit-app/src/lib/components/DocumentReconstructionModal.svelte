<!-- DocumentReconstructionModal.svelte -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { reconstructDocument, getDocumentChunksNavigation } from '$lib/services/api';
  import { toasts } from '$lib/stores/toast';
  
  export let projectId: string;
  export let document: any = null;
  export let show: boolean = false;
  
  const dispatch = createEventDispatcher();
  
  // State
  let loading = false;
  let reconstructedContent = '';
  let chunksNavigation: any[] = [];
  let currentChunk = 0;
  let showChunkNavigation = false;
  let reconstructionMode = 'full'; // 'full' | 'chunk_by_chunk'
  
  // Watch for document changes
  $: if (document && show) {
    loadDocumentContent();
  }
  
  async function loadDocumentContent() {
    if (!document || !projectId) return;
    
    try {
      loading = true;
      
      if (reconstructionMode === 'full') {
        // Get full reconstructed document
        const response = await reconstructDocument(projectId, document.document_id);
        reconstructedContent = response.full_content || response.content || '';
      } else {
        // Get chunk navigation
        const navResponse = await getDocumentChunksNavigation(projectId, document.document_id);
        chunksNavigation = navResponse.chunks || [];
        showChunkNavigation = true;
        
        if (chunksNavigation.length > 0) {
          reconstructedContent = chunksNavigation[0].content || '';
          currentChunk = 0;
        }
      }
      
    } catch (error) {
      console.error('Failed to load document content:', error);
      toasts.error('Failed to load document content');
      reconstructedContent = 'Failed to load content. Please try again.';
    } finally {
      loading = false;
    }
  }
  
  function closeModal() {
    show = false;
    reconstructedContent = '';
    chunksNavigation = [];
    currentChunk = 0;
    showChunkNavigation = false;
    dispatch('close');
  }
  
  function switchMode(mode: string) {
    reconstructionMode = mode;
    loadDocumentContent();
  }
  
  function goToChunk(chunkIndex: number) {
    if (chunkIndex >= 0 && chunkIndex < chunksNavigation.length) {
      currentChunk = chunkIndex;
      reconstructedContent = chunksNavigation[chunkIndex].content || '';
    }
  }
  
  function nextChunk() {
    if (currentChunk < chunksNavigation.length - 1) {
      goToChunk(currentChunk + 1);
    }
  }
  
  function previousChunk() {
    if (currentChunk > 0) {
      goToChunk(currentChunk - 1);
    }
  }
  
  function downloadContent() {
    if (!reconstructedContent) return;
    
    const blob = new Blob([reconstructedContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${document.document_name}_reconstructed.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toasts.success('Document content downloaded');
  }
  
  function copyToClipboard() {
    if (!reconstructedContent) return;
    
    navigator.clipboard.writeText(reconstructedContent).then(() => {
      toasts.success('Content copied to clipboard');
    }).catch(() => {
      toasts.error('Failed to copy content');
    });
  }
</script>

{#if show}
  <div class="modal-overlay" on:click={closeModal}>
    <div class="modal-container" on:click|stopPropagation>
      <div class="modal-header">
        <div class="header-content">
          <h2 class="modal-title">
            <i class="fas fa-puzzle-piece"></i>
            Document Reconstruction
          </h2>
          {#if document}
            <div class="document-info">
              <div class="document-name">{document.document_name}</div>
              {#if document.category}
                <div class="document-meta">
                  <span class="meta-tag">
                    <i class="fas fa-folder"></i>
                    {document.category}
                  </span>
                  {#if document.document_type}
                    <span class="meta-tag">
                      <i class="fas fa-file"></i>
                      {document.document_type}
                    </span>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        </div>
        
        <button class="close-button" on:click={closeModal}>
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <!-- Mode Selection -->
      <div class="mode-selection">
        <div class="mode-buttons">
          <button 
            class="mode-btn"
            class:active={reconstructionMode === 'full'}
            on:click={() => switchMode('full')}
          >
            <i class="fas fa-file-alt"></i>
            Full Document
          </button>
          <button 
            class="mode-btn"
            class:active={reconstructionMode === 'chunk_by_chunk'}
            on:click={() => switchMode('chunk_by_chunk')}
          >
            <i class="fas fa-th-list"></i>
            Chunk by Chunk
          </button>
        </div>
        
        <div class="action-buttons">
          <button class="action-btn" on:click={copyToClipboard} disabled={!reconstructedContent}>
            <i class="fas fa-copy"></i>
            Copy
          </button>
          <button class="action-btn" on:click={downloadContent} disabled={!reconstructedContent}>
            <i class="fas fa-download"></i>
            Download
          </button>
        </div>
      </div>
      
      <!-- Chunk Navigation -->
      {#if showChunkNavigation && chunksNavigation.length > 0}
        <div class="chunk-navigation">
          <div class="chunk-info">
            <span class="chunk-counter">
              Chunk {currentChunk + 1} of {chunksNavigation.length}
            </span>
            {#if chunksNavigation[currentChunk]?.section_title}
              <span class="section-title">
                {chunksNavigation[currentChunk].section_title}
              </span>
            {/if}
          </div>
          
          <div class="chunk-controls">
            <button 
              class="chunk-btn"
              on:click={previousChunk}
              disabled={currentChunk === 0}
            >
              <i class="fas fa-chevron-left"></i>
              Previous
            </button>
            
            <div class="chunk-selector">
              <select bind:value={currentChunk} on:change={(e) => goToChunk(parseInt(e.target.value))}>
                {#each chunksNavigation as chunk, index}
                  <option value={index}>
                    Chunk {index + 1}
                    {#if chunk.section_title}
                      - {chunk.section_title}
                    {/if}
                  </option>
                {/each}
              </select>
            </div>
            
            <button 
              class="chunk-btn"
              on:click={nextChunk}
              disabled={currentChunk === chunksNavigation.length - 1}
            >
              Next
              <i class="fas fa-chevron-right"></i>
            </button>
          </div>
        </div>
      {/if}
      
      <!-- Content Display -->
      <div class="modal-content">
        {#if loading}
          <div class="loading-state">
            <div class="spinner"></div>
            <p>Reconstructing document content...</p>
          </div>
        {:else if reconstructedContent}
          <div class="content-container">
            {#if showChunkNavigation && chunksNavigation[currentChunk]?.hierarchical_path}
              <div class="hierarchical-path">
                <i class="fas fa-sitemap"></i>
                <span class="path-text">{chunksNavigation[currentChunk].hierarchical_path}</span>
              </div>
            {/if}
            
            <div class="content-text">
              {reconstructedContent}
            </div>
            
            {#if showChunkNavigation && chunksNavigation[currentChunk]}
              <div class="chunk-metadata">
                <div class="metadata-item">
                  <span class="label">Chunk Type:</span>
                  <span class="value">{chunksNavigation[currentChunk].chunk_type || 'Unknown'}</span>
                </div>
                <div class="metadata-item">
                  <span class="label">Hierarchy Level:</span>
                  <span class="value">{chunksNavigation[currentChunk].hierarchy_level || 'N/A'}</span>
                </div>
                {#if chunksNavigation[currentChunk].chunk_index !== undefined}
                  <div class="metadata-item">
                    <span class="label">Chunk Index:</span>
                    <span class="value">{chunksNavigation[currentChunk].chunk_index}</span>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {:else}
          <div class="no-content">
            <div class="no-content-icon">
              <i class="fas fa-file-alt"></i>
            </div>
            <h3>No Content Available</h3>
            <p>Unable to reconstruct content for this document.</p>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
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
    max-width: 1200px;
    width: 100%;
    max-height: 90vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  
  .modal-header {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
    padding: 24px 32px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  
  .header-content {
    flex: 1;
  }
  
  .modal-title {
    margin: 0 0 12px 0;
    font-size: 1.5rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .document-info {
    margin-top: 8px;
  }
  
  .document-name {
    font-size: 1.125rem;
    font-weight: 500;
    margin-bottom: 6px;
    opacity: 0.95;
  }
  
  .document-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  
  .meta-tag {
    background: rgba(255, 255, 255, 0.2);
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .close-button {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    width: 40px;
    height: 40px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.125rem;
    flex-shrink: 0;
  }
  
  .close-button:hover {
    background: rgba(255, 255, 255, 0.2);
  }
  
  .mode-selection {
    padding: 20px 32px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f8fafc;
  }
  
  .mode-buttons {
    display: flex;
    gap: 8px;
  }
  
  .mode-btn {
    padding: 8px 16px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: white;
    color: #64748b;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .mode-btn:hover {
    background: #f1f5f9;
    color: #475569;
  }
  
  .mode-btn.active {
    background: #002147;
    color: white;
    border-color: #002147;
  }
  
  .action-buttons {
    display: flex;
    gap: 8px;
  }
  
  .action-btn {
    padding: 8px 16px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: white;
    color: #64748b;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .action-btn:hover:not(:disabled) {
    background: #f1f5f9;
    color: #475569;
  }
  
  .action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .chunk-navigation {
    padding: 16px 32px;
    background: #eff6ff;
    border-bottom: 1px solid #dbeafe;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .chunk-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .chunk-counter {
    font-size: 0.875rem;
    font-weight: 500;
    color: #1e40af;
  }
  
  .section-title {
    font-size: 0.75rem;
    color: #64748b;
    font-style: italic;
  }
  
  .chunk-controls {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  
  .chunk-btn {
    padding: 6px 12px;
    border: 1px solid #dbeafe;
    border-radius: 4px;
    background: white;
    color: #1e40af;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .chunk-btn:hover:not(:disabled) {
    background: #f0f9ff;
  }
  
  .chunk-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .chunk-selector select {
    padding: 6px 8px;
    border: 1px solid #dbeafe;
    border-radius: 4px;
    background: white;
    color: #1e40af;
    font-size: 0.75rem;
    min-width: 200px;
  }
  
  .modal-content {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }
  
  .loading-state {
    padding: 64px 32px;
    text-align: center;
    color: #6b7280;
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
  
  .content-container {
    padding: 32px;
  }
  
  .hierarchical-path {
    background: #f0f9ff;
    border: 1px solid #e0f2fe;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.875rem;
    color: #0369a1;
  }
  
  .path-text {
    font-family: monospace;
    font-weight: 500;
  }
  
  .content-text {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 24px;
    font-size: 0.875rem;
    line-height: 1.6;
    color: #374151;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 400px;
    overflow-y: auto;
    margin-bottom: 24px;
  }
  
  .chunk-metadata {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
  }
  
  .metadata-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.875rem;
  }
  
  .metadata-item .label {
    color: #6b7280;
    font-weight: 500;
  }
  
  .metadata-item .value {
    color: #374151;
    font-weight: 500;
  }
  
  .no-content {
    padding: 64px 32px;
    text-align: center;
    color: #6b7280;
  }
  
  .no-content-icon {
    font-size: 4rem;
    margin-bottom: 24px;
    opacity: 0.5;
  }
  
  .no-content h3 {
    margin: 0 0 12px 0;
    color: #374151;
    font-size: 1.25rem;
  }
  
  .no-content p {
    margin: 0;
    font-size: 0.875rem;
  }
  
  @media (max-width: 768px) {
    .modal-container {
      margin: 10px;
      max-width: calc(100% - 20px);
    }
    
    .modal-header {
      padding: 16px 20px;
    }
    
    .mode-selection {
      flex-direction: column;
      gap: 16px;
      padding: 16px 20px;
    }
    
    .chunk-navigation {
      flex-direction: column;
      gap: 12px;
      padding: 16px 20px;
    }
    
    .chunk-controls {
      flex-direction: column;
      gap: 8px;
    }
    
    .content-container {
      padding: 20px;
    }
    
    .content-text {
      max-height: 300px;
    }
  }
</style>
