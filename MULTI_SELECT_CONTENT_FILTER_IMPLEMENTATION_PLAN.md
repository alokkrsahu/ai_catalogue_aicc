# Multi-Select Content Filter Implementation Plan

**Feature**: Allow users to select multiple folders, multiple files, or a combination of both for DocAware content filtering

**Date**: 2025-11-26

---

## Table of Contents
1. [Current Implementation Summary](#current-implementation-summary)
2. [Required Changes Overview](#required-changes-overview)
3. [Backend Changes](#backend-changes)
4. [Frontend Changes](#frontend-changes)
5. [Data Structure Changes](#data-structure-changes)
6. [Implementation Steps](#implementation-steps)
7. [Testing Requirements](#testing-requirements)
8. [Performance Considerations](#performance-considerations)

---

## Current Implementation Summary

### Current Behavior:
- **Single Selection**: Users can select ONE folder OR ONE file (file selection not exposed in UI)
- **Data Format**: `content_filter` is a string: `"folder_Reports/Financial"` or `"file_doc123"`
- **Filter Expression**: Single `LIKE` or `==` expression in Milvus
- **UI**: Single `<select>` dropdown with one value

### Current Data Flow:
```
Frontend Selection → Single String → Backend Validation → Single Filter Expression → Milvus Query
```

---

## Required Changes Overview

### New Behavior:
- **Multi-Selection**: Users can select MULTIPLE folders AND/OR files
- **Data Format**: `content_filters` will be an array: `["folder_Reports/Financial", "folder_Legal", "file_doc123"]`
- **Filter Expression**: Multiple expressions combined with OR logic
- **UI**: Multi-select component with chips/tags display

### New Data Flow:
```
Frontend Multi-Selection → Array of Strings → Backend Validation → Combined Filter Expression → Milvus Query
```

### ⚠️ Breaking Change:
- **NO Backward Compatibility**: Old workflows using `content_filter` (single string) will need to be updated
- **Migration Required**: A one-time migration script will update existing workflows

---

## Backend Changes

### 1. **`backend/agent_orchestration/docaware_views.py`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/backend/agent_orchestration/docaware_views.py`

#### Changes Required:

##### A. **`hierarchical_paths` endpoint (Lines 314-393)**
**Change**: Add file entries to the response alongside folders

**Current**:
```python
def hierarchical_paths(self, request):
    # Returns only folders
    hierarchical_data = docaware_service.get_hierarchical_paths()
```

**New Implementation**:
```python
def hierarchical_paths(self, request):
    # Parameters
    include_files = request.query_params.get('include_files', 'true').lower() == 'true'

    # Get hierarchical data (folders + files if requested)
    hierarchical_data = docaware_service.get_hierarchical_paths(include_files=include_files)

    return Response({
        'project_id': project_id,
        'hierarchical_paths': hierarchical_data,
        'folders_count': len([p for p in hierarchical_data if p['type'] == 'folder']),
        'files_count': len([p for p in hierarchical_data if p['type'] == 'file']),
        'total_count': len(hierarchical_data)
    })
```

##### B. **`test_search` endpoint (Lines 118-271)**
**Change**: Accept array of content filters instead of single string

**Current** (Line 134):
```python
content_filter = request.data.get('content_filter')  # Single string
```

**New Implementation**:
```python
content_filters = request.data.get('content_filters', [])  # Array of strings

# Validate array
if content_filters and not isinstance(content_filters, list):
    return Response(
        {'error': 'content_filters must be an array'},
        status=status.HTTP_400_BAD_REQUEST
    )

logger.info(f"🔍 DEBUG: Extracted - content_filters: {content_filters}")
```

**Search Call Update** (Line 222-227):
```python
# NEW
search_results = docaware_service.search_documents(
    query=query,
    search_method=search_method,
    method_parameters=parameters,
    content_filters=content_filters  # Array of strings
)
```

---

### 2. **`backend/agent_orchestration/docaware/service.py`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/backend/agent_orchestration/docaware/service.py`

#### Changes Required:

##### A. **`search_documents` method signature (Lines 51-109)**

**Current**:
```python
def search_documents(
    self,
    query: str,
    search_method: SearchMethod = SearchMethod.SEMANTIC_SEARCH,
    method_parameters: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[List[str]] = None,
    content_filter: Optional[str] = None  # Single string
) -> List[Dict[str, Any]]:
```

**New Implementation**:
```python
def search_documents(
    self,
    query: str,
    search_method: SearchMethod = SearchMethod.SEMANTIC_SEARCH,
    method_parameters: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[List[str]] = None,
    content_filters: Optional[List[str]] = None  # Array of strings
) -> List[Dict[str, Any]]:
    """
    Search documents using the specified method

    Args:
        query: Search query text
        search_method: Method to use for searching
        method_parameters: Parameters specific to the search method
        conversation_context: Recent conversation context for contextual search
        content_filters: List of content filter IDs (e.g., ["folder_Reports", "file_doc123"])

    Returns:
        List of search results with content and metadata
    """
    logger.info(f"📚 SEARCH: Starting {search_method.value} search for: '{query[:50]}...'")

    # Build combined content filter expression
    content_filter_expr = self._build_multi_content_filter_expression(content_filters) if content_filters else None

    if content_filter_expr:
        logger.info(f"📚 SEARCH: Applying multi-filter expression with {len(content_filters)} filters")
        logger.debug(f"📚 SEARCH: Filter expression: {content_filter_expr}")

    # Rest of the method remains the same...
    # Pass content_filter_expr to all search methods
```

##### B. **NEW METHOD: `_build_multi_content_filter_expression`**
**Insert after** `_build_content_filter_expression` method (after line 268)

```python
def _build_multi_content_filter_expression(self, content_filters: List[str]) -> str:
    """
    Build Milvus filter expression from multiple content filter IDs
    Combines multiple filters with OR logic

    Args:
        content_filters: List of content filter IDs
            Examples:
            - ["folder_Reports/Financial", "folder_Legal"]
            - ["file_doc123", "file_doc456"]
            - ["folder_Reports", "file_doc789"]  # Mixed

    Returns:
        Combined Milvus filter expression string with OR logic

    Examples:
        Input: ["folder_Reports", "folder_Legal"]
        Output: "(hierarchical_path like 'Reports%') || (hierarchical_path like 'Legal%')"

        Input: ["folder_Reports", "file_doc123"]
        Output: "(hierarchical_path like 'Reports%') || (document_id == 'doc123')"
    """
    if not content_filters or len(content_filters) == 0:
        return ""

    try:
        filter_expressions = []

        for content_filter in content_filters:
            if not content_filter or not isinstance(content_filter, str):
                logger.warning(f"🔍 MULTI-FILTER: Skipping invalid filter: {content_filter}")
                continue

            # Build individual filter expression
            individual_expr = self._build_content_filter_expression(content_filter)

            if individual_expr:
                filter_expressions.append(individual_expr)

        if not filter_expressions:
            logger.warning(f"🔍 MULTI-FILTER: No valid filter expressions generated from {len(content_filters)} filters")
            return ""

        # Combine with OR logic
        if len(filter_expressions) == 1:
            combined_expr = filter_expressions[0]
        else:
            # Wrap each expression in parentheses and join with ||
            combined_expr = " || ".join([f"({expr})" for expr in filter_expressions])

        logger.info(f"🔍 MULTI-FILTER: Generated combined expression with {len(filter_expressions)} filters")
        logger.debug(f"🔍 MULTI-FILTER: Expression: {combined_expr}")

        return combined_expr

    except Exception as e:
        logger.error(f"❌ MULTI-FILTER: Failed to build multi-filter expression: {e}")
        import traceback
        logger.error(f"❌ MULTI-FILTER: Traceback: {traceback.format_exc()}")
        return ""
```

##### C. **Update ALL search method calls (Lines 94-108)**

**Current**:
```python
if search_method == SearchMethod.SEMANTIC_SEARCH:
    return self._semantic_search(query, validated_params, content_filter_expr)
elif search_method == SearchMethod.HYBRID_SEARCH:
    return self._hybrid_search(query, validated_params, content_filter_expr)
# ... etc
```

**No changes needed** - All methods already accept `content_filter_expr` parameter, which will now contain the combined expression.

##### D. **`get_hierarchical_paths` method (Lines 849-920)**
**Change**: Add support for including individual files

**Current**:
```python
def get_hierarchical_paths(self) -> List[Dict[str, Any]]:
    """
    Get unique hierarchical paths for content filtering from Milvus collection
    Returns unique folder paths only (no individual files)
    """
```

**New Implementation**:
```python
def get_hierarchical_paths(self, include_files: bool = False) -> List[Dict[str, Any]]:
    """
    Get unique hierarchical paths for content filtering from Milvus collection

    Args:
        include_files: If True, include individual file entries alongside folders

    Returns:
        List of folder entries (and optionally file entries)
    """
    try:
        logger.info(f"📚 HIERARCHICAL PATHS: Getting paths (include_files={include_files}) for {self.collection_name}")

        # Create search request to get all documents
        dummy_query = [0.0] * 384
        detected_metric = self.get_collection_metric_type(self.collection_name)

        search_request = SearchRequest(
            collection_name=self.collection_name,
            query_vectors=[dummy_query],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType(detected_metric),
            limit=10000,
            output_fields=["hierarchical_path", "document_id", "file_name"]  # Add document_id and file_name
        )

        search_result = self.milvus_service.search(search_request)

        # Extract unique folder paths
        unique_folder_paths = set()
        unique_files = {}  # Map: document_id -> file info

        for hit in search_result.hits:
            hierarchical_path = hit.get("hierarchical_path", "")
            document_id = hit.get("document_id", "")
            file_name = hit.get("file_name", "Unknown")

            if hierarchical_path and hierarchical_path.strip():
                clean_path = hierarchical_path.strip().strip('/')

                if clean_path:
                    # Extract folder path (remove #chunk_XXX suffix)
                    if '#chunk_' in clean_path:
                        file_path = clean_path.split('#chunk_')[0]
                        folder_path = '/'.join(file_path.split('/')[:-1])

                        # Add all parent folder paths
                        if folder_path:
                            unique_folder_paths.add(folder_path)
                            path_parts = folder_path.split('/')
                            for i in range(1, len(path_parts)):
                                parent_path = '/'.join(path_parts[:i])
                                if parent_path:
                                    unique_folder_paths.add(parent_path)

                        # Track file for optional inclusion
                        if include_files and document_id and document_id not in unique_files:
                            unique_files[document_id] = {
                                'document_id': document_id,
                                'file_name': file_name,
                                'file_path': file_path,
                                'folder_path': folder_path
                            }

        # Build result list
        result_list = []

        # Add folders
        for folder_path in sorted(unique_folder_paths):
            result_list.append({
                "id": f"folder_{folder_path}",
                "name": folder_path.split('/')[-1],
                "path": folder_path,
                "type": "folder",
                "displayName": folder_path,
                "isFolder": True
            })

        # Add files if requested
        if include_files:
            for doc_id, file_info in sorted(unique_files.items(), key=lambda x: x[1]['file_name']):
                result_list.append({
                    "id": f"file_{doc_id}",
                    "name": file_info['file_name'],
                    "path": file_info['file_path'],
                    "type": "file",
                    "displayName": f"{file_info['folder_path']}/{file_info['file_name']}" if file_info['folder_path'] else file_info['file_name'],
                    "isFolder": False,
                    "document_id": doc_id
                })

        logger.info(f"📚 HIERARCHICAL PATHS: Found {len(result_list)} entries (folders + files)")
        return result_list

    except Exception as e:
        logger.error(f"📚 HIERARCHICAL PATHS: Failed to get paths: {e}")
        import traceback
        logger.error(f"📚 HIERARCHICAL PATHS: Traceback: {traceback.format_exc()}")
        return []
```

---

### 3. **`backend/agent_orchestration/docaware_handler.py`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/backend/agent_orchestration/docaware_handler.py`

#### Changes Required:

##### A. **Update method calls that use DocAware service** (Lines 62-67, 136-141)

**Current**:
```python
def perform_search():
    return docaware_service.search_documents(
        query=search_query,
        search_method=SearchMethod(search_method),
        method_parameters=search_parameters,
        conversation_context=conversation_context
        # No content_filter parameter
    )
```

**New Implementation**:
```python
def perform_search():
    # Extract content_filters from agent config
    content_filters = agent_data.get('content_filters', [])

    return docaware_service.search_documents(
        query=search_query,
        search_method=SearchMethod(search_method),
        method_parameters=search_parameters,
        conversation_context=conversation_context,
        content_filters=content_filters  # NEW: Pass filters array
    )
```

**Affected Methods**:
- `get_docaware_context_from_conversation_query` (Lines 30-109)
- `get_docaware_context` (Lines 111-169)
- `get_docaware_context_from_query` (Lines 294-373)

---

### 4. **`backend/agent_orchestration/human_input_handler.py`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/backend/agent_orchestration/human_input_handler.py`

#### Changes Required:

##### A. **`process_userproxy_docaware` method (Lines 321-399)**

**Current** (Lines 331-333):
```python
search_method = node_data.get('search_method', 'semantic_search')
search_parameters = node_data.get('search_parameters', {})
content_filter = node_data.get('content_filter', '')
```

**New Implementation**:
```python
search_method = node_data.get('search_method', 'semantic_search')
search_parameters = node_data.get('search_parameters', {})

# Get multi-select content filters
content_filters = node_data.get('content_filters', [])
```

**Search Call Update** (Lines 352-358):
```python
# NEW
search_results = await sync_to_async(docaware_service.execute_search)(
    project_id=project_id,
    search_method=search_method,
    search_parameters=search_parameters,
    query=human_input,
    content_filters=content_filters  # Array
)
```

---

### 5. **`backend/vector_search/database.py`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/backend/vector_search/database.py`

#### Changes Required:

##### A. **Add index for `hierarchical_path` field** (Line 254)

**Current** (Lines 239-254):
```python
def _create_indices(self):
    # Vector index
    self.collection.create_index(field_name="embedding", index_params=...)

    # Scalar indices
    self.collection.create_index(field_name="document_id")
    self.collection.create_index(field_name="file_type")
    self.collection.create_index(field_name="file_name")
    self.collection.create_index(field_name="category")
    self.collection.create_index(field_name="subcategory")
    self.collection.create_index(field_name="document_type")
    self.collection.create_index(field_name="chunk_type")
    # MISSING: hierarchical_path index
```

**New Implementation** (Add after line 253):
```python
def _create_indices(self):
    # ... existing indices ...

    self.collection.create_index(field_name="chunk_type")

    # ⭐ NEW: Index for hierarchical_path to optimize LIKE queries
    self.collection.create_index(field_name="hierarchical_path")

    logger.info(f"Created enhanced indices for collection {self.collection_name}")
```

**Impact**: This will significantly improve performance for multi-filter queries with `LIKE` operators.

---

## Frontend Changes

### 6. **`frontend/my-sveltekit-app/src/lib/components/NodePropertiesPanel.svelte`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/frontend/my-sveltekit-app/src/lib/components/NodePropertiesPanel.svelte`

#### Changes Required:

##### A. **State Management** (Add new variables at component top)

**Add after existing state declarations**:
```svelte
<script lang="ts">
  // ... existing imports and state ...

  // ⭐ NEW: Multi-select content filter state
  let selectedContentFilters: string[] = [];  // Array of selected filter IDs
  let showFilterDropdown = false;
  let filterSearchQuery = '';

  // Initialize from nodeConfig
  $: if (nodeConfig.content_filters && Array.isArray(nodeConfig.content_filters)) {
    selectedContentFilters = [...nodeConfig.content_filters];
  } else {
    selectedContentFilters = [];
  }

  // Computed: Get display names for selected filters
  $: selectedFilterObjects = selectedContentFilters
    .map(filterId => hierarchicalPaths.find(p => p.id === filterId))
    .filter(Boolean);

  // Computed: Available filters (not yet selected)
  $: availableFilters = hierarchicalPaths.filter(
    path => !selectedContentFilters.includes(path.id)
  );

  // Computed: Filtered available options based on search
  $: filteredAvailableFilters = availableFilters.filter(path => {
    if (!filterSearchQuery) return true;
    const searchLower = filterSearchQuery.toLowerCase();
    return (
      path.displayName.toLowerCase().includes(searchLower) ||
      path.name.toLowerCase().includes(searchLower)
    );
  });
</script>
```

##### B. **Replace Single Select Dropdown** (Lines 1181-1232)

**Current**:
```svelte
<div class="mb-4">
  <label class="block text-sm font-medium text-gray-700 mb-2">Content Filter</label>
  {#if !hierarchicalPathsLoaded}
    <div class="loading">Loading...</div>
  {:else if hierarchicalPaths.length === 0}
    <div class="warning">No folders available</div>
  {:else}
    <select bind:value={nodeConfig.content_filter} on:change={updateNodeData}>
      <option value="">All project files (no filter)</option>
      {#each hierarchicalPaths as folder}
        <option value={folder.id}>📁 {folder.displayName}</option>
      {/each}
    </select>
  {/if}
</div>
```

**New Implementation**:
```svelte
<div class="mb-4">
  <label class="block text-sm font-medium text-gray-700 mb-2">
    Content Filters
    <span class="text-xs text-gray-500 font-normal ml-1">
      (Select multiple folders and/or files)
    </span>
  </label>

  {#if !hierarchicalPathsLoaded}
    <!-- Loading State -->
    <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
      <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
      <span class="text-sm text-blue-700">Loading content filter data...</span>
    </div>

  {:else if hierarchicalPaths.length === 0}
    <!-- Empty State -->
    <div class="w-full px-3 py-2 border border-yellow-300 rounded-lg bg-yellow-50">
      <div class="text-yellow-700 text-sm flex items-center">
        <i class="fas fa-info-circle mr-2"></i>
        No folders available for filtering. Upload and process documents first.
      </div>
    </div>

  {:else}
    <!-- Multi-Select Component -->
    <div class="content-filter-multi-select">

      <!-- Selected Filters Display (Chips/Tags) -->
      {#if selectedContentFilters.length > 0}
        <div class="selected-filters-container mb-2 p-2 border border-gray-200 rounded-lg bg-gray-50">
          <div class="flex flex-wrap gap-2">
            {#each selectedFilterObjects as filter}
              <div class="filter-chip flex items-center bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
                <span class="mr-1">
                  {#if filter.isFolder}
                    📁
                  {:else}
                    📄
                  {/if}
                </span>
                <span class="font-medium">{filter.name}</span>
                <button
                  type="button"
                  on:click={() => removeFilter(filter.id)}
                  class="ml-2 text-blue-600 hover:text-blue-800 focus:outline-none"
                  title="Remove filter"
                >
                  <i class="fas fa-times"></i>
                </button>
              </div>
            {/each}

            <!-- Clear All Button -->
            <button
              type="button"
              on:click={clearAllFilters}
              class="filter-chip flex items-center bg-red-100 text-red-800 px-3 py-1 rounded-full text-sm hover:bg-red-200"
              title="Clear all filters"
            >
              <i class="fas fa-times-circle mr-1"></i>
              Clear All
            </button>
          </div>
        </div>
      {/if}

      <!-- Add Filter Dropdown -->
      <div class="relative">
        <button
          type="button"
          on:click={() => showFilterDropdown = !showFilterDropdown}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-blue-600 focus:ring-2 focus:ring-blue-600 focus:ring-opacity-20 bg-white flex items-center justify-between hover:bg-gray-50"
        >
          <span class="text-sm text-gray-700">
            {#if selectedContentFilters.length === 0}
              <i class="fas fa-plus mr-2"></i>Add content filters...
            {:else}
              <i class="fas fa-plus mr-2"></i>Add more filters... ({selectedContentFilters.length} selected)
            {/if}
          </span>
          <i class="fas fa-chevron-down text-gray-400"></i>
        </button>

        <!-- Dropdown Menu -->
        {#if showFilterDropdown}
          <div class="absolute z-50 mt-1 w-full bg-white border border-gray-300 rounded-lg shadow-lg max-h-80 overflow-hidden">

            <!-- Search Box -->
            <div class="p-2 border-b border-gray-200">
              <input
                type="text"
                bind:value={filterSearchQuery}
                placeholder="Search folders or files..."
                class="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:border-blue-600 focus:ring-1 focus:ring-blue-600"
              />
            </div>

            <!-- Options List -->
            <div class="overflow-y-auto max-h-60">
              {#if filteredAvailableFilters.length === 0}
                <div class="px-3 py-4 text-center text-sm text-gray-500">
                  {#if filterSearchQuery}
                    No results matching "{filterSearchQuery}"
                  {:else}
                    All items selected
                  {/if}
                </div>
              {:else}
                <!-- Group by Type: Folders first, then Files -->
                {@const folders = filteredAvailableFilters.filter(p => p.isFolder)}
                {@const files = filteredAvailableFilters.filter(p => !p.isFolder)}

                {#if folders.length > 0}
                  <div class="px-3 py-1 bg-gray-100 text-xs font-semibold text-gray-600 sticky top-0">
                    FOLDERS ({folders.length})
                  </div>
                  {#each folders as folder}
                    <button
                      type="button"
                      on:click={() => addFilter(folder.id)}
                      class="w-full px-3 py-2 text-left text-sm hover:bg-blue-50 flex items-center group"
                    >
                      <span class="mr-2">📁</span>
                      <span class="flex-1">{folder.displayName}</span>
                      <i class="fas fa-plus text-gray-400 group-hover:text-blue-600 opacity-0 group-hover:opacity-100"></i>
                    </button>
                  {/each}
                {/if}

                {#if files.length > 0}
                  <div class="px-3 py-1 bg-gray-100 text-xs font-semibold text-gray-600 sticky top-0">
                    FILES ({files.length})
                  </div>
                  {#each files as file}
                    <button
                      type="button"
                      on:click={() => addFilter(file.id)}
                      class="w-full px-3 py-2 text-left text-sm hover:bg-blue-50 flex items-center group"
                    >
                      <span class="mr-2">📄</span>
                      <span class="flex-1 truncate" title={file.displayName}>{file.name}</span>
                      <i class="fas fa-plus text-gray-400 group-hover:text-blue-600 opacity-0 group-hover:opacity-100"></i>
                    </button>
                  {/each}
                {/if}
              {/if}
            </div>
          </div>
        {/if}
      </div>

      <!-- No Selection State -->
      {#if selectedContentFilters.length === 0}
        <div class="mt-2 p-2 bg-gray-100 rounded text-xs text-gray-600">
          <i class="fas fa-globe mr-1"></i>
          <strong>No Filters:</strong> DocAware will search all project documents
        </div>
      {/if}

      <!-- Active Filters Summary -->
      {#if selectedContentFilters.length > 0}
        <div class="mt-2 p-2 bg-green-100 rounded text-xs text-green-700">
          <div class="flex items-center mb-1">
            <i class="fas fa-filter mr-1"></i>
            <strong>Active Filters ({selectedContentFilters.length}):</strong>
          </div>
          <div class="text-xs text-green-600">
            DocAware will only search selected folders/files
          </div>
        </div>
      {/if}

    </div>
  {/if}
</div>
```

##### C. **Add Handler Functions**

**Add these functions in the `<script>` section**:
```svelte
<script lang="ts">
  // ... existing code ...

  function addFilter(filterId: string) {
    if (!selectedContentFilters.includes(filterId)) {
      selectedContentFilters = [...selectedContentFilters, filterId];
      nodeConfig.content_filters = selectedContentFilters;
      updateNodeData();

      // Clear search and close dropdown after selection
      filterSearchQuery = '';
      // Keep dropdown open for multiple selections
      // showFilterDropdown = false;  // Optionally close

      console.log('✅ Added filter:', filterId);
    }
  }

  function removeFilter(filterId: string) {
    selectedContentFilters = selectedContentFilters.filter(id => id !== filterId);
    nodeConfig.content_filters = selectedContentFilters;
    updateNodeData();

    console.log('❌ Removed filter:', filterId);
  }

  function clearAllFilters() {
    selectedContentFilters = [];
    nodeConfig.content_filters = [];
    updateNodeData();
    showFilterDropdown = false;

    console.log('🗑️ Cleared all filters');
  }

  // Close dropdown when clicking outside
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (showFilterDropdown && !target.closest('.content-filter-multi-select')) {
      showFilterDropdown = false;
    }
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  });
</script>
```

---

### 7. **`frontend/my-sveltekit-app/src/lib/components/AgentOrchestrationInterface.svelte`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/frontend/my-sveltekit-app/src/lib/components/AgentOrchestrationInterface.svelte`

#### Changes Required:

##### A. **Update `loadHierarchicalPaths` function** (Lines 243-272)

**Current**:
```typescript
async function loadHierarchicalPaths() {
  try {
    const response = await api.get(`/agent-orchestration/docaware/hierarchical_paths/?project_id=${projectId}`);
    const pathsData = response.data || response;
    const rawPaths = pathsData.hierarchical_paths || [];

    // Filter to show only folders (not individual chunks)
    hierarchicalPaths = rawPaths.filter(path => {
      if (!path?.id || !path?.displayName || path.type !== 'folder') return false;
      return !path.path?.includes('#chunk_');
    });
```

**New Implementation**:
```typescript
async function loadHierarchicalPaths() {
  try {
    hierarchicalPathsLoading = true;
    hierarchicalPathsError = null;

    console.log('📚 AGENT ORCHESTRATION: Loading hierarchical paths for content filtering');

    // Request both folders AND files
    const response = await api.get(
      `/agent-orchestration/docaware/hierarchical_paths/?project_id=${projectId}&include_files=true`
    );

    const pathsData = response.data || response;
    const rawPaths = pathsData.hierarchical_paths || [];

    // Filter out individual chunks (keep folders and complete files only)
    hierarchicalPaths = rawPaths.filter(path => {
      if (!path?.id || !path?.displayName) return false;

      // Keep folders
      if (path.type === 'folder' && !path.path?.includes('#chunk_')) {
        return true;
      }

      // Keep files (but not individual chunks)
      if (path.type === 'file' && !path.path?.includes('#chunk_')) {
        return true;
      }

      return false;
    });

    console.log(`✅ AGENT ORCHESTRATION: Loaded ${hierarchicalPaths.length} content filter options`);
    console.log(`   - Folders: ${hierarchicalPaths.filter(p => p.isFolder).length}`);
    console.log(`   - Files: ${hierarchicalPaths.filter(p => !p.isFolder).length}`);

  } catch (error) {
    console.error('❌ AGENT ORCHESTRATION: Failed to load hierarchical paths:', error);
    hierarchicalPathsError = error.message || 'Failed to load content filter data';
    hierarchicalPaths = [];
  } finally {
    hierarchicalPathsLoading = false;
  }
}
```

---

### 8. **`frontend/my-sveltekit-app/src/lib/services/docAwareService.ts`**
**File Path**: `/Users/alok/Documents/AICC/ai_catalogue/ai_catalogue_aicc/ai_catalogue_aicc/frontend/my-sveltekit-app/src/lib/services/docAwareService.ts`

#### Changes Required:

##### A. **Update TypeScript Interfaces** (Add/modify at top of file)

**Add new interface**:
```typescript
export interface HierarchicalPathItem {
  id: string;
  name: string;
  path: string;
  type: 'folder' | 'file';
  displayName: string;
  isFolder: boolean;
  document_id?: string;  // Present for files
}

export interface HierarchicalPathsResponse {
  project_id: string;
  hierarchical_paths: HierarchicalPathItem[];
  folders_count: number;
  files_count: number;
  total_count: number;
}
```

##### B. **Update `TestSearchResponse` interface**

**Add content_filters field**:
```typescript
export interface TestSearchRequest {
  project_id: string;
  method: string;
  parameters: Record<string, any>;
  query: string;
  content_filters?: string[];  // ⭐ NEW: Array of filter IDs
}

export interface TestSearchResponse {
  success: boolean;
  query: string;
  method: string;
  results_count: number;
  sample_results: Array<{
    content_preview: string;
    score: number;
    source: string;
    page?: number;
    search_method: string;
  }>;
  parameters_used: Record<string, any>;
  content_filters_used?: string[];  // ⭐ NEW: Echo back filters used
  error?: string;
}
```

##### C. **Update `testSearch` method** (Lines 124-165)

**Current**:
```typescript
async testSearch(
  projectId: string,
  method: string,
  parameters: Record<string, any>,
  query?: string,
  contentFilter?: string
): Promise<TestSearchResponse> {
```

**New Implementation**:
```typescript
async testSearch(
  projectId: string,
  method: string,
  parameters: Record<string, any>,
  query?: string,
  contentFilters?: string[]  // ⭐ Changed to array
): Promise<TestSearchResponse> {
  try {
    console.log('📚 DOCAWARE SERVICE: Testing search for project:', projectId, 'method:', method);
    console.log('📚 DOCAWARE SERVICE: Content filters:', contentFilters);

    const searchQuery = query || 'quarterly business performance analysis and market trends';

    console.log('📚 DOCAWARE SERVICE: Using search query:', searchQuery);

    const response = await api.post('/agent-orchestration/docaware/test_search/', {
      project_id: projectId,
      method,
      parameters,
      query: searchQuery,
      content_filters: contentFilters || []  // ⭐ Send array
    });

    console.log('✅ DOCAWARE SERVICE: Search test completed:', response.data.results_count, 'results');
    return response.data;

  } catch (error) {
    console.error('❌ DOCAWARE SERVICE: Search test failed:', error);
    if (error.response?.data) {
      return {
        success: false,
        query: query || 'quarterly business performance analysis and market trends',
        method,
        results_count: 0,
        sample_results: [],
        parameters_used: parameters,
        content_filters_used: contentFilters || [],
        error: error.response.data.error || 'Search test failed'
      };
    }
    throw error;
  }
}
```

##### D. **Add new method for fetching hierarchical paths**

```typescript
/**
 * Get hierarchical paths (folders and files) for content filtering
 */
async getHierarchicalPaths(
  projectId: string,
  includeFiles: boolean = true
): Promise<HierarchicalPathsResponse> {
  try {
    console.log('📚 DOCAWARE SERVICE: Fetching hierarchical paths for project:', projectId);

    const response = await api.get('/agent-orchestration/docaware/hierarchical_paths/', {
      params: {
        project_id: projectId,
        include_files: includeFiles
      }
    });

    console.log('✅ DOCAWARE SERVICE: Got hierarchical paths:', response.data.total_count);
    return response.data;

  } catch (error) {
    console.error('❌ DOCAWARE SERVICE: Failed to get hierarchical paths:', error);
    throw error;
  }
}
```

---

## Data Structure Changes

### Request/Response Formats

#### 1. **Hierarchical Paths Endpoint**

**Endpoint**: `GET /api/agent-orchestration/docaware/hierarchical_paths/`

**Request Query Parameters**:
```typescript
{
  project_id: string,
  include_files?: boolean  // Default: true (NEW parameter)
}
```

**Response** (NEW format):
```json
{
  "project_id": "abc123",
  "hierarchical_paths": [
    {
      "id": "folder_Reports",
      "name": "Reports",
      "path": "Reports",
      "type": "folder",
      "displayName": "Reports",
      "isFolder": true
    },
    {
      "id": "folder_Reports/Financial",
      "name": "Financial",
      "path": "Reports/Financial",
      "type": "folder",
      "displayName": "Reports/Financial",
      "isFolder": true
    },
    {
      "id": "file_doc123",
      "name": "Q1_Report.pdf",
      "path": "Reports/Financial/Q1_Report.pdf",
      "type": "file",
      "displayName": "Reports/Financial/Q1_Report.pdf",
      "isFolder": false,
      "document_id": "doc123"
    }
  ],
  "folders_count": 2,
  "files_count": 1,
  "total_count": 3
}
```

#### 2. **Test Search Endpoint**

**Endpoint**: `POST /api/agent-orchestration/docaware/test_search/`

**Request Body** (CHANGED):
```json
{
  "project_id": "abc123",
  "method": "semantic_search",
  "parameters": {
    "search_limit": 5,
    "relevance_threshold": 0.7
  },
  "query": "quarterly financial analysis",
  "content_filters": [
    "folder_Reports/Financial",
    "folder_Legal",
    "file_doc789"
  ]
}
```


**Response**:
```json
{
  "success": true,
  "query": "quarterly financial analysis",
  "method": "semantic_search",
  "results_count": 5,
  "sample_results": [...],
  "parameters_used": {...},
  "content_filters_used": [
    "folder_Reports/Financial",
    "folder_Legal",
    "file_doc789"
  ]
}
```

#### 3. **Agent Node Configuration** (Workflow JSON)

**New Format**:
```json
{
  "id": "agent_1",
  "type": "AssistantAgent",
  "data": {
    "name": "Financial Analyst",
    "doc_aware": true,
    "search_method": "semantic_search",
    "search_parameters": {...},
    "content_filters": [
      "folder_Reports/Financial",
      "folder_Legal/Contracts",
      "file_doc123"
    ]
  }
}
```

---

## Implementation Steps

### Phase 1: Backend Foundation (Days 1-2)

1. ✅ **Update `docaware/service.py`**:
   - Add `_build_multi_content_filter_expression` method
   - Update `search_documents` signature to accept `content_filters` array
   - Update `get_hierarchical_paths` to include files
   - Add backward compatibility for single `content_filter`

2. ✅ **Update `docaware_views.py`**:
   - Modify `hierarchical_paths` endpoint to return files
   - Modify `test_search` endpoint to accept `content_filters` array
   - Add backward compatibility handling

3. ✅ **Update `vector_search/database.py`**:
   - Add index for `hierarchical_path` field

4. ✅ **Test Backend Changes**:
   - Test multi-filter expression generation
   - Test Milvus query with combined OR expressions
   - Test hierarchical paths endpoint with files
   - Test empty filters array handling

---

### Phase 2: Backend Integration (Days 3-4)

5. ✅ **Update `docaware_handler.py`**:
   - Update all method calls to use `content_filters` array
   - Add migration logic for old `content_filter` → `content_filters`

6. ✅ **Update `human_input_handler.py`**:
   - Update UserProxy DocAware processing to use `content_filters`

7. ✅ **Create Migration Script**:
   - Script to update existing workflows from `content_filter` to `content_filters`

8. ✅ **Test Integration**:
   - Test agent execution with multi-filter
   - Test UserProxy with multi-filter
   - Test conversation orchestration with filters

---

### Phase 3: Frontend UI (Days 5-6)

9. ✅ **Update `docAwareService.ts`**:
   - Add new TypeScript interfaces
   - Update `testSearch` method signature
   - Add `getHierarchicalPaths` method

10. ✅ **Update `AgentOrchestrationInterface.svelte`**:
   - Update `loadHierarchicalPaths` to request files
   - Update state management for multi-select

11. ✅ **Update `NodePropertiesPanel.svelte`**:
    - Replace single select with multi-select component
    - Add chip/tag display for selected filters
    - Add dropdown with search functionality
    - Add "Clear All" and individual remove buttons
    - Add folder/file grouping in dropdown

---

### Phase 4: Testing & Polish (Days 7-8)

12. ✅ **Integration Testing**:
    - Test selecting multiple folders
    - Test selecting multiple files
    - Test mixed selection (folders + files)
    - Test filter search functionality
    - Test backward compatibility with old workflows

13. ✅ **UI/UX Polish**:
    - Add loading states
    - Add empty states
    - Add error handling
    - Add tooltips and help text
    - Test responsive design

14. ✅ **Performance Testing**:
    - Test with large number of folders/files
    - Test search query performance with multiple filters
    - Test UI performance with many selected filters

---

### Phase 5: Documentation & Deployment (Day 9)

15. ✅ **Documentation**:
    - Update API documentation
    - Update user documentation
    - Add migration guide for existing workflows

16. ✅ **Run Migration Script**:
   - Backup database
   - Run migration script to update existing workflows
   - Verify all workflows updated correctly

17. ✅ **Deployment**:
    - Create database migration if needed
    - Deploy backend changes
    - Deploy frontend changes
    - Monitor for issues

---

## Testing Requirements

### Unit Tests

#### Backend Tests:
```python
# test_multi_content_filter.py

def test_build_multi_filter_expression_folders():
    """Test combining multiple folder filters with OR logic"""
    filters = ["folder_Reports/Financial", "folder_Legal"]
    expected = "(hierarchical_path like 'Reports/Financial%') || (hierarchical_path like 'Legal%')"
    # Assert expression matches

def test_build_multi_filter_expression_files():
    """Test combining multiple file filters"""
    filters = ["file_doc123", "file_doc456"]
    expected = "(document_id == 'doc123') || (document_id == 'doc456')"
    # Assert expression matches

def test_build_multi_filter_expression_mixed():
    """Test combining folders and files"""
    filters = ["folder_Reports", "file_doc123"]
    expected = "(hierarchical_path like 'Reports%') || (document_id == 'doc123')"
    # Assert expression matches


def test_hierarchical_paths_include_files():
    """Test that files are included when requested"""
    paths = service.get_hierarchical_paths(include_files=True)
    # Assert both folders and files present

def test_empty_filters_array():
    """Test that empty filters array returns no filter expression"""
    filters = []
    result = service._build_multi_content_filter_expression(filters)
    assert result == ""

def test_invalid_filters_skipped():
    """Test that invalid filters are skipped"""
    filters = ["folder_Reports", None, "", "invalid_format", "file_doc123"]
    # Assert only valid filters are used
```

#### Frontend Tests:
```typescript
// docAwareService.test.ts

test('testSearch accepts array of content filters', async () => {
  const filters = ['folder_Reports', 'file_doc123'];
  const result = await docAwareService.testSearch(
    'project123',
    'semantic_search',
    {},
    'test query',
    filters
  );
  // Assert request sent with content_filters array
});

test('getHierarchicalPaths returns folders and files', async () => {
  const result = await docAwareService.getHierarchicalPaths('project123', true);
  expect(result.folders_count).toBeGreaterThan(0);
  expect(result.files_count).toBeGreaterThan(0);
});
```

### Integration Tests

```python
# test_docaware_integration.py

def test_multi_filter_search_execution():
    """Test full search execution with multiple filters"""
    # Create workflow with multi-filter agent
    # Execute workflow
    # Assert search results only from selected folders/files

def test_userproxy_multi_filter():
    """Test UserProxy with multi-filter DocAware"""
    # Create UserProxy with multi-filter
    # Provide human input
    # Assert DocAware search respects multiple filters

def test_workflow_migration_script():
    """Test migration script updates workflows correctly"""
    # Create workflow with old content_filter format
    # Run migration script
    # Assert workflow now has content_filters array
    # Assert old content_filter field removed
```

### Manual Testing Checklist

- [ ] Select single folder - verify results
- [ ] Select multiple folders - verify results from all folders
- [ ] Select single file - verify results only from that file
- [ ] Select multiple files - verify results from all files
- [ ] Select mixed (folders + files) - verify combined results
- [ ] Search filters in dropdown - verify filtering works
- [ ] Remove individual filter chip - verify removal
- [ ] Clear all filters - verify all removed
- [ ] Save workflow with multi-filters - verify persistence
- [ ] Load workflow with multi-filters - verify restoration
- [ ] Run migration script on test workflows - verify success
- [ ] Test with 50+ folders/files - verify performance
- [ ] Test UI responsiveness on mobile
- [ ] Test with no documents uploaded - verify empty state
- [ ] Test with loading state - verify spinner shows

---

## Performance Considerations

### Database Performance

#### Before (Single Filter):
```sql
-- Single LIKE query
SELECT * FROM collection
WHERE embedding <similarity_search>
  AND hierarchical_path LIKE 'Reports/Financial%'
LIMIT 5
```

#### After (Multi Filter):
```sql
-- Multiple LIKE queries with OR
SELECT * FROM collection
WHERE embedding <similarity_search>
  AND (
    hierarchical_path LIKE 'Reports/Financial%' OR
    hierarchical_path LIKE 'Legal%' OR
    document_id == 'doc123'
  )
LIMIT 5
```

**Performance Impact**:
- ✅ **With Index**: Adding `hierarchical_path` index will make OR queries fast
- ⚠️ **Without Index**: Multiple LIKE with OR can be slow (requires index!)
- 📊 **Expected**: <100ms for 3-5 filters with index

### Frontend Performance

**Concerns**:
1. Large number of folders/files in dropdown (1000+)
2. Re-rendering selected chips on every change

**Optimizations**:
1. **Virtual Scrolling**: If >500 items, implement virtual scrolling
2. **Debounced Search**: Debounce filter search input (300ms)
3. **Memoization**: Use computed properties for filtered lists
4. **Lazy Loading**: Load hierarchical paths only when panel opens

### Memory Considerations

**Backend**:
- Milvus query with OR: No significant memory increase
- Filter expression string: Negligible (<10KB even with 100 filters)

**Frontend**:
- Hierarchical paths array: ~1MB for 1000 items
- Selected filters array: Negligible

---

## Migration Strategy

### ⚠️ Breaking Change - No Backward Compatibility

**Approach**: One-time migration script to update all existing workflows

### Migration Script

**Location**: `backend/migrations/migrate_content_filters.py`

```python
"""
Migration Script: Convert content_filter to content_filters
============================================================

This script updates all existing workflows to use the new content_filters array format.

Usage:
    python manage.py shell
    >>> from migrations.migrate_content_filters import migrate_workflows
    >>> migrate_workflows()
"""

import json
import logging
from users.models import Workflow  # Adjust import based on your models

logger = logging.getLogger(__name__)

def migrate_workflows():
    """
    Migrate all workflows from content_filter (string) to content_filters (array)
    """
    logger.info("🔄 Starting workflow migration: content_filter → content_filters")

    workflows = Workflow.objects.all()
    total_count = workflows.count()
    updated_count = 0
    error_count = 0

    logger.info(f"📊 Found {total_count} workflows to check")

    for workflow in workflows:
        try:
            # Parse workflow JSON
            graph_data = json.loads(workflow.graph_json) if isinstance(workflow.graph_json, str) else workflow.graph_json

            modified = False

            # Check all nodes in the workflow
            for node in graph_data.get('nodes', []):
                node_data = node.get('data', {})

                # Check if node has old content_filter field
                if 'content_filter' in node_data and 'content_filters' not in node_data:
                    old_filter = node_data['content_filter']

                    # Convert to array
                    if old_filter and old_filter.strip():
                        node_data['content_filters'] = [old_filter]
                        logger.info(f"   ✅ Migrated node '{node_data.get('name')}': '{old_filter}' → ['{old_filter}']")
                    else:
                        node_data['content_filters'] = []
                        logger.info(f"   ✅ Migrated node '{node_data.get('name')}': empty → []")

                    # Remove old field
                    del node_data['content_filter']
                    modified = True

            # Save if modified
            if modified:
                workflow.graph_json = json.dumps(graph_data) if not isinstance(workflow.graph_json, str) else json.dumps(graph_data)
                workflow.save()
                updated_count += 1
                logger.info(f"✅ Updated workflow: {workflow.name} (ID: {workflow.id})")

        except Exception as e:
            error_count += 1
            logger.error(f"❌ Error migrating workflow {workflow.id}: {e}")

    logger.info(f"""
╔════════════════════════════════════════════════╗
║         MIGRATION COMPLETE                     ║
╠════════════════════════════════════════════════╣
║  Total workflows checked:  {total_count:>4}                  ║
║  Workflows updated:        {updated_count:>4}                  ║
║  Errors encountered:       {error_count:>4}                  ║
╚════════════════════════════════════════════════╝
""")

    return {
        'total': total_count,
        'updated': updated_count,
        'errors': error_count
    }


def rollback_migration():
    """
    Rollback migration: Convert content_filters back to content_filter
    Use this if you need to rollback the migration
    """
    logger.info("⏪ Starting rollback: content_filters → content_filter")

    workflows = Workflow.objects.all()
    total_count = workflows.count()
    rolled_back_count = 0

    for workflow in workflows:
        try:
            graph_data = json.loads(workflow.graph_json) if isinstance(workflow.graph_json, str) else workflow.graph_json
            modified = False

            for node in graph_data.get('nodes', []):
                node_data = node.get('data', {})

                if 'content_filters' in node_data:
                    filters = node_data['content_filters']

                    # Convert array to single string (take first filter)
                    if filters and len(filters) > 0:
                        node_data['content_filter'] = filters[0]
                        if len(filters) > 1:
                            logger.warning(f"   ⚠️ Multiple filters found, keeping only first: {filters[0]}")
                    else:
                        node_data['content_filter'] = ''

                    del node_data['content_filters']
                    modified = True

            if modified:
                workflow.graph_json = json.dumps(graph_data) if not isinstance(workflow.graph_json, str) else json.dumps(graph_data)
                workflow.save()
                rolled_back_count += 1

        except Exception as e:
            logger.error(f"❌ Error rolling back workflow {workflow.id}: {e}")

    logger.info(f"⏪ Rollback complete: {rolled_back_count} workflows restored")
    return rolled_back_count
```

### Running the Migration

**Step 1: Backup Database**
```bash
# Backup PostgreSQL database
docker compose exec postgres pg_dump -U ai_catalogue_user ai_catalogue_db > backup_before_migration.sql
```

**Step 2: Run Migration Script**
```bash
# Enter Django shell
docker compose exec backend python manage.py shell

# Run migration
>>> from migrations.migrate_content_filters import migrate_workflows
>>> result = migrate_workflows()
>>> print(f"Updated {result['updated']} workflows")
```

**Step 3: Verify Migration**
```bash
# Query a workflow to verify format
>>> from users.models import Workflow
>>> w = Workflow.objects.first()
>>> import json
>>> data = json.loads(w.graph_json)
>>> # Check nodes have content_filters (array) not content_filter (string)
```

### Database Schema

**No schema changes needed** - Using existing fields:
- `hierarchical_path` (already exists)
- `document_id` (already exists)

**Only need to add**:
- Index on `hierarchical_path` field

### User Notification

**On first load after upgrade**:
```
🔄 System Update: Multi-Select Content Filters

Your workflows have been automatically updated to support multiple content filters!

What's New:
✅ Select multiple folders for broader searches
✅ Select multiple files for targeted analysis
✅ Mix folders and files in one search

Your existing content filters have been preserved.
You can now add more filters to any DocAware agent!
```

---

## Security Considerations

### SQL Injection Prevention

**Already Implemented** (but verify for array):
```python
# Escape single quotes in each filter
for content_filter in content_filters:
    if content_filter.startswith('folder_'):
        folder_path = content_filter[7:]
        escaped_path = folder_path.replace("'", "''")  # SQL injection prevention
```

### Validation

**Add validation for array size**:
```python
# Limit maximum number of filters
MAX_FILTERS = 50

if len(content_filters) > MAX_FILTERS:
    return Response(
        {'error': f'Maximum {MAX_FILTERS} filters allowed'},
        status=status.HTTP_400_BAD_REQUEST
    )
```

### Access Control

**Already Implemented** (no changes needed):
```python
# Verify project ownership before returning filters
project = get_object_or_404(IntelliDocProject, project_id=project_id)
if project.created_by != request.user:
    return Response({'error': 'Access denied'}, status=403)
```

---

## Error Handling

### Backend Error Cases

1. **Empty filters array**: Return all documents (no filter)
2. **Invalid filter format**: Skip invalid filters, log warning
3. **All filters invalid**: Proceed with no filter
4. **Milvus query fails**: Return error message to frontend
5. **Too many filters**: Return 400 error

### Frontend Error Cases

1. **Failed to load hierarchical paths**: Show error message with retry
2. **Search fails with filters**: Show error, allow removing filters
3. **Invalid filter ID**: Skip and log warning
4. **Network error**: Show error toast, preserve selected filters

---

## Rollback Plan

### If Issues Arise:

1. **Code Rollback**:
   - Revert all backend file changes (use git)
   - Revert all frontend file changes (use git)
   - Keep index on `hierarchical_path` (doesn't hurt performance)

2. **Data Rollback**:
   - Run `rollback_migration()` function from migration script
   - Restores `content_filter` (single string) from first item in `content_filters` array
   - **WARNING**: Multi-filter selections will be lost (only first filter kept)

3. **Database Restore** (if migration script fails):
   - Restore from backup: `backup_before_migration.sql`
   ```bash
   docker compose exec postgres psql -U ai_catalogue_user ai_catalogue_db < backup_before_migration.sql
   ```

---

## Success Metrics

### Functional Metrics:
- ✅ Users can select 2+ folders
- ✅ Users can select 2+ files
- ✅ Users can select mixed (folders + files)
- ✅ Search results respect all selected filters
- ✅ Old workflows still work

### Performance Metrics:
- ⏱️ Hierarchical paths load: <2 seconds
- ⏱️ Multi-filter search: <500ms (3-5 filters)
- ⏱️ UI responsiveness: <100ms per interaction

### User Experience Metrics:
- 👍 Intuitive UI (user testing)
- 👍 Clear visual feedback
- 👍 Easy to add/remove filters
- 👍 Search functionality works well

---

## Summary Checklist

### Backend Files to Modify:
- [x] `backend/agent_orchestration/docaware_views.py`
- [x] `backend/agent_orchestration/docaware/service.py`
- [x] `backend/agent_orchestration/docaware_handler.py`
- [x] `backend/agent_orchestration/human_input_handler.py`
- [x] `backend/vector_search/database.py`

### Frontend Files to Modify:
- [x] `frontend/my-sveltekit-app/src/lib/components/NodePropertiesPanel.svelte`
- [x] `frontend/my-sveltekit-app/src/lib/components/AgentOrchestrationInterface.svelte`
- [x] `frontend/my-sveltekit-app/src/lib/services/docAwareService.ts`

### New Features:
- [x] Multi-select dropdown component
- [x] Filter chips/tags display
- [x] Search functionality in dropdown
- [x] Folder/file grouping
- [x] Clear all button
- [x] Individual remove buttons

### Migration:
- [x] Migration script to convert old workflows
- [x] Database backup before migration
- [x] Rollback capability if needed

### Performance Optimizations:
- [x] Add `hierarchical_path` index
- [x] Debounced search input
- [x] Efficient filter expression building

### Testing:
- [x] Unit tests for backend
- [x] Unit tests for frontend
- [x] Integration tests
- [x] Manual testing checklist

---

**End of Implementation Plan**

**Estimated Total Effort**: 7-9 days (1 developer)

**Priority**: High (User-requested feature enhancement)

**Risk Level**: Medium (Requires careful testing of filter logic)

**Dependencies**: None (Standalone feature)
