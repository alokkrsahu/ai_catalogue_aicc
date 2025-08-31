<!-- HierarchicalSearchInterface.svelte -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { 
    searchProjectDocuments, 
    searchByCategory, 
    searchByDocumentType, 
    searchByHierarchyLevel,
    advancedEnhancedSearch,
    getAvailableCategories,
    getProjectCapabilities 
  } from '$lib/services/api';
  import { toasts } from '$lib/stores/toast';
  
  export let projectId: string;
  export let capabilities: any = null;
  
  const dispatch = createEventDispatcher();
  
  // Search state
  let searchQuery = '';
  let searchResults: any[] = [];
  let searching = false;
  let hasSearched = false;
  
  // Filter state
  let selectedCategory = '';
  let selectedSubcategory = '';
  let selectedDocumentType = '';
  let minHierarchyLevel = 1;
  let maxHierarchyLevel = 10;
  let searchType = 'basic';
  let resultLimit = 5;
  
  // Available options
  let availableCategories: any[] = [];
  let availableDocumentTypes = [
    { id: 'pdf', name: 'PDF Documents' },
    { id: 'docx', name: 'Word Documents' },
    { id: 'txt', name: 'Text Files' },
    { id: 'html', name: 'HTML Documents' },
    { id: 'md', name: 'Markdown Files' }
  ];
  
  // UI state
  let showAdvancedFilters = false;
  let showResults = false;
  
  // Load capabilities and categories on mount
  import { onMount } from 'svelte';
  
  onMount(async () => {
    await loadCategories();
    if (!capabilities) {
      await loadCapabilities();
    }
  });
  
  async function loadCapabilities() {
    try {
      capabilities = await getProjectCapabilities(projectId);
    } catch (error) {
      console.error('Failed to load capabilities:', error);
    }
  }
  
  async function loadCategories() {
    try {
      const response = await getAvailableCategories(projectId);
      availableCategories = response.categories || [];
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  }
  
  async function performSearch() {
    if (!searchQuery.trim()) {
      toasts.error('Please enter a search query');
      return;
    }
    
    try {
      searching = true;
      hasSearched = false;
      searchResults = [];
      
      let results;
      
      // Choose search method based on filters and capabilities
      if (selectedCategory && capabilities?.search?.hierarchical_search) {
        results = await searchByCategory(projectId, searchQuery, selectedCategory, selectedSubcategory, resultLimit);
      } else if (selectedDocumentType && capabilities?.processing?.supports_enhanced_processing) {
        results = await searchByDocumentType(projectId, searchQuery, selectedDocumentType, resultLimit);
      } else if (showAdvancedFilters && (minHierarchyLevel > 1 || maxHierarchyLevel < 10)) {
        results = await searchByHierarchyLevel(projectId, searchQuery, minHierarchyLevel, maxHierarchyLevel, resultLimit);
      } else if (showAdvancedFilters && capabilities?.search?.hierarchical_search) {
        // Use advanced search with all filters
        results = await advancedEnhancedSearch(projectId, {
          query: searchQuery,
          category: selectedCategory,
          subcategory: selectedSubcategory,
          document_type: selectedDocumentType,
          min_hierarchy_level: minHierarchyLevel,
          max_hierarchy_level: maxHierarchyLevel,
          limit: resultLimit,
          search_type: searchType
        });
      } else {
        // Use basic enhanced search
        results = await searchProjectDocuments(projectId, searchQuery, resultLimit);
      }
      
      searchResults = results.results || results || [];
      hasSearched = true;
      showResults = true;
      
      // Dispatch search event
      dispatch('searchCompleted', {
        query: searchQuery,
        results: searchResults,
        searchType: getSearchTypeUsed(),
        filters: getActiveFilters()
      });
      
    } catch (error) {
      console.error('Search failed:', error);
      toasts.error('Search failed. Please try again.');
    } finally {
      searching = false;
    }
  }
  
  function getSearchTypeUsed() {
    if (selectedCategory) return 'category';
    if (selectedDocumentType) return 'document_type';
    if (showAdvancedFilters) return 'advanced';
    return 'basic';
  }
  
  function getActiveFilters() {
    const filters: any = {};
    if (selectedCategory) filters.category = selectedCategory;
    if (selectedSubcategory) filters.subcategory = selectedSubcategory;
    if (selectedDocumentType) filters.document_type = selectedDocumentType;
    if (minHierarchyLevel > 1) filters.min_hierarchy_level = minHierarchyLevel;
    if (maxHierarchyLevel < 10) filters.max_hierarchy_level = maxHierarchyLevel;
    return filters;
  }
  
  function clearFilters() {
    selectedCategory = '';
    selectedSubcategory = '';
    selectedDocumentType = '';
    minHierarchyLevel = 1;
    maxHierarchyLevel = 10;
    searchType = 'basic';
    resultLimit = 5;
    showAdvancedFilters = false;
  }
  
  function clearSearch() {
    searchQuery = '';
    searchResults = [];
    hasSearched = false;
    showResults = false;
    clearFilters();
  }
  
  // Get subcategories for selected category
  $: subcategories = selectedCategory ? 
    availableCategories.find(c => c.id === selectedCategory)?.subcategories || [] : 
    [];
  
  // Reset subcategory when category changes
  $: if (selectedCategory) {
    selectedSubcategory = '';
  }
</script>

<div class="hierarchical-search">
  <div class="search-header">
    <h3 class="search-title">
      <i class="fas fa-search"></i>
      Document Search
      {#if capabilities?.search?.hierarchical_search}
        <span class="hierarchical-badge">Hierarchical</span>
      {/if}
    </h3>
    
    <div class="search-actions">
      <button 
        class="toggle-filters-btn"
        class:active={showAdvancedFilters}
        on:click={() => showAdvancedFilters = !showAdvancedFilters}
      >
        <i class="fas fa-filter"></i>
        {showAdvancedFilters ? 'Hide' : 'Show'} Filters
      </button>
      
      {#if hasSearched}
        <button class="clear-btn" on:click={clearSearch}>
          <i class="fas fa-times"></i>
          Clear
        </button>
      {/if}
    </div>
  </div>
  
  <!-- Main Search Input -->
  <div class="search-input-section">
    <div class="search-input-container">
      <input 
        type="text" 
        class="search-input"
        bind:value={searchQuery}
        placeholder="Enter your search query..."
        on:keydown={(e) => e.key === 'Enter' && performSearch()}
      />
      <button 
        class="search-btn"
        on:click={performSearch}
        disabled={searching || !searchQuery.trim()}
      >
        {#if searching}
          <i class="fas fa-spinner fa-spin"></i>
        {:else}
          <i class="fas fa-search"></i>
        {/if}
        Search
      </button>
    </div>
  </div>
  
  <!-- Advanced Filters -->
  {#if showAdvancedFilters}
    <div class="advanced-filters">
      <div class="filters-grid">
        <!-- Category Filter -->
        {#if capabilities?.search?.hierarchical_search && availableCategories.length > 0}
          <div class="filter-group">
            <label class="filter-label">
              <i class="fas fa-folder"></i>
              Category
            </label>
            <select class="filter-select" bind:value={selectedCategory}>
              <option value="">All Categories</option>
              {#each availableCategories as category}
                <option value={category.id}>{category.name}</option>
              {/each}
            </select>
          </div>
          
          <!-- Subcategory Filter -->
          {#if subcategories.length > 0}
            <div class="filter-group">
              <label class="filter-label">
                <i class="fas fa-folder-open"></i>
                Subcategory
              </label>
              <select class="filter-select" bind:value={selectedSubcategory}>
                <option value="">All Subcategories</option>
                {#each subcategories as subcategory}
                  <option value={subcategory.id}>{subcategory.name}</option>
                {/each}
              </select>
            </div>
          {/if}
        {/if}
        
        <!-- Document Type Filter -->
        {#if capabilities?.processing?.supports_enhanced_processing}
          <div class="filter-group">
            <label class="filter-label">
              <i class="fas fa-file-alt"></i>
              Document Type
            </label>
            <select class="filter-select" bind:value={selectedDocumentType}>
              <option value="">All Types</option>
              {#each availableDocumentTypes as docType}
                <option value={docType.id}>{docType.name}</option>
              {/each}
            </select>
          </div>
        {/if}
        
        <!-- Hierarchy Level Filter -->
        {#if capabilities?.search?.hierarchical_search}
          <div class="filter-group">
            <label class="filter-label">
              <i class="fas fa-layer-group"></i>
              Hierarchy Level
            </label>
            <div class="range-inputs">
              <input 
                type="number" 
                class="range-input" 
                bind:value={minHierarchyLevel}
                min="1" 
                max="10"
                placeholder="Min"
              />
              <span class="range-separator">to</span>
              <input 
                type="number" 
                class="range-input" 
                bind:value={maxHierarchyLevel}
                min="1" 
                max="10"
                placeholder="Max"
              />
            </div>
          </div>
        {/if}
        
        <!-- Result Limit -->
        <div class="filter-group">
          <label class="filter-label">
            <i class="fas fa-list-ol"></i>
            Result Limit
          </label>
          <select class="filter-select" bind:value={resultLimit}>
            <option value={5}>5 results</option>
            <option value={10}>10 results</option>
            <option value={20}>20 results</option>
            <option value={50}>50 results</option>
          </select>
        </div>
      </div>
      
      <div class="filter-actions">
        <button class="clear-filters-btn" on:click={clearFilters}>
          <i class="fas fa-undo"></i>
          Clear Filters
        </button>
      </div>
    </div>
  {/if}
  
  <!-- Search Results -->
  {#if showResults}
    <div class="search-results">
      <div class="results-header">
        <h4 class="results-title">
          <i class="fas fa-search"></i>
          Search Results
          {#if searchResults.length > 0}
            <span class="results-count">({searchResults.length} found)</span>
          {/if}
        </h4>
        
        {#if getActiveFilters() && Object.keys(getActiveFilters()).length > 0}
          <div class="active-filters">
            <span class="filters-label">Active filters:</span>
            {#each Object.entries(getActiveFilters()) as [key, value]}
              <span class="filter-tag">
                {key}: {value}
              </span>
            {/each}
          </div>
        {/if}
      </div>
      
      {#if searchResults.length === 0}
        <div class="no-results">
          <div class="no-results-icon">
            <i class="fas fa-search"></i>
          </div>
          <h5>No results found</h5>
          <p>Try adjusting your search query or filters</p>
        </div>
      {:else}
        <div class="results-list">
          {#each searchResults as result, index}
            <div class="result-item">
              <div class="result-header">
                <h6 class="result-title">{result.document_name}</h6>
                <div class="result-meta">
                  {#if result.category}
                    <span class="meta-tag category">
                      <i class="fas fa-folder"></i>
                      {result.category}
                    </span>
                  {/if}
                  {#if result.document_type}
                    <span class="meta-tag type">
                      <i class="fas fa-file"></i>
                      {result.document_type}
                    </span>
                  {/if}
                  {#if result.hierarchy_level}
                    <span class="meta-tag level">
                      <i class="fas fa-layer-group"></i>
                      Level {result.hierarchy_level}
                    </span>
                  {/if}
                  {#if result.score}
                    <span class="meta-tag score">
                      <i class="fas fa-star"></i>
                      {(result.score * 100).toFixed(1)}%
                    </span>
                  {/if}
                </div>
              </div>
              
              <div class="result-content">
                <p class="result-excerpt">{result.content}</p>
                
                {#if result.hierarchical_path}
                  <div class="hierarchical-path">
                    <i class="fas fa-sitemap"></i>
                    <span class="path">{result.hierarchical_path}</span>
                  </div>
                {/if}
              </div>
              
              <div class="result-actions">
                <button class="result-btn" on:click={() => dispatch('viewDocument', result)}>
                  <i class="fas fa-eye"></i>
                  View
                </button>
                
                {#if capabilities?.processing?.supports_hierarchical_processing}
                  <button class="result-btn" on:click={() => dispatch('reconstructDocument', result)}>
                    <i class="fas fa-puzzle-piece"></i>
                    Reconstruct
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .hierarchical-search {
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    overflow: hidden;
  }
  
  .search-header {
    background: #f8fafc;
    padding: 20px 24px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .search-title {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: #1e293b;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .hierarchical-badge {
    background: #dcfce7;
    color: #16a34a;
    font-size: 0.75rem;
    padding: 4px 8px;
    border-radius: 12px;
    font-weight: 500;
  }
  
  .search-actions {
    display: flex;
    gap: 8px;
  }
  
  .toggle-filters-btn, .clear-btn {
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
  
  .toggle-filters-btn:hover, .clear-btn:hover {
    background: #f1f5f9;
    color: #475569;
  }
  
  .toggle-filters-btn.active {
    background: #002147;
    color: white;
    border-color: #002147;
  }
  
  .search-input-section {
    padding: 24px;
  }
  
  .search-input-container {
    display: flex;
    gap: 12px;
  }
  
  .search-input {
    flex: 1;
    padding: 12px 16px;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 1rem;
    transition: all 0.2s ease;
  }
  
  .search-input:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .search-btn {
    padding: 12px 24px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .search-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.3);
  }
  
  .search-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .advanced-filters {
    padding: 24px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
  }
  
  .filters-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }
  
  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .filter-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: #374151;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .filter-select, .range-input {
    padding: 8px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 0.875rem;
    background: white;
  }
  
  .filter-select:focus, .range-input:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 2px rgba(0, 33, 71, 0.1);
  }
  
  .range-inputs {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .range-input {
    flex: 1;
    width: 60px;
  }
  
  .range-separator {
    font-size: 0.875rem;
    color: #6b7280;
  }
  
  .filter-actions {
    display: flex;
    justify-content: flex-end;
  }
  
  .clear-filters-btn {
    padding: 8px 16px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #dc2626;
    border-radius: 6px;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .clear-filters-btn:hover {
    background: #fee2e2;
  }
  
  .search-results {
    padding: 24px;
    border-top: 1px solid #e2e8f0;
  }
  
  .results-header {
    margin-bottom: 20px;
  }
  
  .results-title {
    margin: 0 0 8px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #1e293b;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .results-count {
    font-size: 0.875rem;
    color: #64748b;
    font-weight: 400;
  }
  
  .active-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
  
  .filters-label {
    font-size: 0.875rem;
    color: #6b7280;
    font-weight: 500;
  }
  
  .filter-tag {
    background: #eff6ff;
    color: #1e40af;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .no-results {
    text-align: center;
    padding: 48px 24px;
    color: #6b7280;
  }
  
  .no-results-icon {
    font-size: 3rem;
    margin-bottom: 16px;
    opacity: 0.5;
  }
  
  .no-results h5 {
    margin: 0 0 8px 0;
    font-size: 1.125rem;
    color: #374151;
  }
  
  .no-results p {
    margin: 0;
    font-size: 0.875rem;
  }
  
  .results-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .result-item {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 16px;
    background: white;
    transition: all 0.2s ease;
  }
  
  .result-item:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  }
  
  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
  }
  
  .result-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: #1e293b;
  }
  
  .result-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  
  .meta-tag {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .meta-tag.category {
    background: #f3f4f6;
    color: #374151;
  }
  
  .meta-tag.type {
    background: #eff6ff;
    color: #1e40af;
  }
  
  .meta-tag.level {
    background: #f0f9ff;
    color: #0369a1;
  }
  
  .meta-tag.score {
    background: #fef3c7;
    color: #d97706;
  }
  
  .result-content {
    margin-bottom: 12px;
  }
  
  .result-excerpt {
    margin: 0 0 8px 0;
    line-height: 1.6;
    color: #4b5563;
    font-size: 0.875rem;
  }
  
  .hierarchical-path {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.75rem;
    color: #6b7280;
    background: #f8fafc;
    padding: 6px 8px;
    border-radius: 4px;
  }
  
  .path {
    font-family: monospace;
  }
  
  .result-actions {
    display: flex;
    gap: 8px;
  }
  
  .result-btn {
    padding: 6px 12px;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    background: white;
    color: #64748b;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .result-btn:hover {
    background: #f1f5f9;
    color: #475569;
  }
  
  @media (max-width: 768px) {
    .search-header {
      flex-direction: column;
      gap: 12px;
      align-items: stretch;
    }
    
    .search-input-container {
      flex-direction: column;
    }
    
    .filters-grid {
      grid-template-columns: 1fr;
    }
    
    .result-header {
      flex-direction: column;
      gap: 8px;
    }
    
    .result-meta {
      justify-content: flex-start;
    }
  }
</style>
