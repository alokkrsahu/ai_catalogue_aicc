# Multi-Select Content Filter - Testing Guide

## Overview

This guide provides comprehensive testing scenarios for the multi-select content filter feature in DocAware.

**Feature:** Users can now select multiple folders and/or files when configuring DocAware content filters, instead of being limited to a single selection.

**Data Format Change:**
- **Old:** `content_filter: "folder_Reports"` (single string)
- **New:** `content_filters: ["folder_Reports", "folder_Legal", "file_doc123"]` (array of strings)

---

## Prerequisites

✅ Containers rebuilt and running
✅ Migration script executed successfully
✅ Frontend dev server running on http://localhost:5173
✅ Backend API running on http://localhost:8000

---

## Test Scenarios

### 1. UI/UX Testing

#### 1.1 Content Filter UI Display

**Steps:**
1. Navigate to a project with processed documents
2. Go to Agent Orchestration tab
3. Create or edit a workflow
4. Select an **AssistantAgent**, **UserProxyAgent**, or **DelegateAgent** node
5. Enable "DocAware" checkbox
6. Scroll to "Content Filters (Multi-Select)" section

**Expected Results:**
- ✅ Label shows "Content Filters (Multi-Select)" with info icon
- ✅ Dropdown shows "Add folder or file filter..." placeholder
- ✅ Dropdown has two optgroups: "Folders" and "Files"
- ✅ Folders show 📁 icon
- ✅ Files show 📄 icon
- ✅ Description shows "No Filter: DocAware will search all project documents"

---

#### 1.2 Single Selection

**Steps:**
1. From content filter dropdown, select a single folder (e.g., "📁 Reports")

**Expected Results:**
- ✅ Selected folder appears as a blue chip/tag with folder icon
- ✅ Chip has a close button (X)
- ✅ Dropdown resets to placeholder
- ✅ Selected folder is now disabled in dropdown
- ✅ Description shows "Active Filters (1):"
- ✅ Description explains OR logic

---

#### 1.3 Multiple Folder Selection

**Steps:**
1. Select first folder: "📁 Reports"
2. Select second folder: "📁 Legal"
3. Select third folder: "📁 Research"

**Expected Results:**
- ✅ All 3 folders appear as separate chips
- ✅ Each chip shows correct folder name with 📁 icon
- ✅ Each chip has its own remove button
- ✅ All 3 are disabled in dropdown
- ✅ Description shows "Active Filters (3):"
- ✅ Chips wrap to multiple lines if needed

---

#### 1.4 Multiple File Selection

**Steps:**
1. Select multiple individual files from the "Files" optgroup

**Expected Results:**
- ✅ Files appear as chips with 📄 icon
- ✅ File names displayed correctly
- ✅ Each file has remove button
- ✅ Selected files disabled in dropdown

---

#### 1.5 Mixed Selection (Folders + Files)

**Steps:**
1. Select folder: "📁 Reports"
2. Select file: "📄 Q1_Summary.pdf"
3. Select another folder: "📁 Legal"
4. Select another file: "📄 Contract.docx"

**Expected Results:**
- ✅ All 4 items appear as chips
- ✅ Folders and files visually distinguished by icons
- ✅ Description shows "Active Filters (4):"
- ✅ Each item removable independently

---

#### 1.6 Removing Filters

**Steps:**
1. Select 3 filters (mix of folders and files)
2. Click X button on the middle chip

**Expected Results:**
- ✅ Middle chip removed
- ✅ Other chips remain
- ✅ Removed item re-enabled in dropdown
- ✅ Filter count updates to (2)
- ✅ Node data auto-saves

---

#### 1.7 Removing All Filters

**Steps:**
1. Select multiple filters
2. Remove them one by one until none remain

**Expected Results:**
- ✅ When last filter removed, description changes to "No Filter"
- ✅ All items re-enabled in dropdown
- ✅ Chips container disappears

---

### 2. Search Functionality Testing

#### 2.1 Test Search with No Filters

**Steps:**
1. Ensure content_filters is empty
2. Configure DocAware search method (e.g., "Semantic Search")
3. Click "Test DocAware Search" button
4. Provide a test query (e.g., "financial report analysis")

**Expected Results:**
- ✅ Search executes successfully
- ✅ Results from ALL project documents returned
- ✅ Console logs show: `content_filters: []`

---

#### 2.2 Test Search with Single Folder Filter

**Steps:**
1. Select single folder: "📁 Reports"
2. Click "Test DocAware Search"
3. Provide query: "quarterly sales"

**Expected Results:**
- ✅ Search executes successfully
- ✅ Results only from "Reports" folder and subfolders
- ✅ Console logs show: `content_filters: ["folder_Reports"]`
- ✅ Backend logs show filter expression: `hierarchical_path like 'Reports%'`

---

#### 2.3 Test Search with Multiple Folders

**Steps:**
1. Select folders: "📁 Reports", "📁 Legal"
2. Click "Test DocAware Search"
3. Provide query: "contract terms"

**Expected Results:**
- ✅ Search executes successfully
- ✅ Results from EITHER Reports OR Legal folders
- ✅ Console logs show: `content_filters: ["folder_Reports", "folder_Legal"]`
- ✅ Backend logs show combined filter: `(hierarchical_path like 'Reports%') || (hierarchical_path like 'Legal%')`

---

#### 2.4 Test Search with Specific Files

**Steps:**
1. Select files: "📄 Q1_2024.pdf", "📄 Annual_Report.pdf"
2. Click "Test DocAware Search"
3. Provide query: "revenue growth"

**Expected Results:**
- ✅ Search executes successfully
- ✅ Results only from those 2 specific files
- ✅ Console logs show: `content_filters: ["file_doc123", "file_doc456"]`
- ✅ Backend logs show: `(document_id == 'doc123') || (document_id == 'doc456')`

---

#### 2.5 Test Search with Mixed Filters

**Steps:**
1. Select: "📁 Reports" + "📄 Legal_Contract.pdf"
2. Click "Test DocAware Search"
3. Provide query: "compliance requirements"

**Expected Results:**
- ✅ Search executes successfully
- ✅ Results from Reports folder + specific Legal file
- ✅ Backend logs show mixed filter: `(hierarchical_path like 'Reports%') || (document_id == 'doc789')`

---

### 3. Workflow Execution Testing

#### 3.1 Execute Workflow with Multi-Filter DocAware Agent

**Steps:**
1. Create workflow with DocAware enabled agent
2. Configure multiple content filters
3. Save workflow
4. Execute workflow with a query that should trigger DocAware search

**Expected Results:**
- ✅ Workflow executes without errors
- ✅ DocAware agent searches only specified locations
- ✅ Execution logs show filtered search results
- ✅ Agent responses based on filtered documents

---

#### 3.2 Workflow Persistence

**Steps:**
1. Create workflow with multi-select filters configured
2. Save workflow
3. Refresh browser
4. Re-open workflow

**Expected Results:**
- ✅ All selected filters still present
- ✅ Chips display correctly
- ✅ Filters still functional in execution

---

### 4. Edge Cases & Error Handling

#### 4.1 Empty Folder Selection

**Test:** Select a folder that contains no processed documents

**Expected:**
- ✅ No errors
- ✅ Search returns empty results with message
- ✅ UI shows "No documents found matching filter criteria"

---

#### 4.2 Invalid Filter ID

**Test:** Manually edit workflow JSON to include non-existent filter ID

**Expected:**
- ✅ Backend gracefully ignores invalid filter
- ✅ Search continues with valid filters only
- ✅ Warning logged in backend

---

#### 4.3 Maximum Selections

**Test:** Select 10+ folders and files

**Expected:**
- ✅ All selections handled correctly
- ✅ Chips wrap properly in UI
- ✅ Search filter expression built correctly
- ✅ No performance degradation

---

#### 4.4 Special Characters in Paths

**Test:** Select folder with path like "Reports/O'Reilly/Research"

**Expected:**
- ✅ Path properly escaped in filter expression
- ✅ SQL injection prevented (single quotes escaped)
- ✅ Search works correctly

---

#### 4.5 API Endpoint Error Handling

**Test:** Send invalid content_filters format to API

```bash
curl -X POST http://localhost:8000/api/agent-orchestration/docaware/test_search/ \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test",
    "method": "semantic_search",
    "query": "test",
    "content_filters": "invalid_string"
  }'
```

**Expected:**
- ✅ API returns 400 Bad Request
- ✅ Error message: "content_filters must be an array"

---

### 5. Performance Testing

#### 5.1 Search with Many Filters

**Test:** Configure 20+ content filters, execute search

**Expected:**
- ✅ Search completes within 3 seconds
- ✅ No timeout errors
- ✅ Results accurate

---

#### 5.2 Large Document Collection

**Test:** Project with 1000+ documents, use multi-folder filter

**Expected:**
- ✅ Filter reduces search space significantly
- ✅ Indexed hierarchical_path provides fast filtering
- ✅ Search faster than unfiltered search

---

### 6. Browser Compatibility

**Test on:**
- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari

**Verify:**
- Chips render correctly
- Dropdown works properly
- Icons display correctly
- No console errors

---

## Validation Checklist

### Backend Validation

```bash
# Check logs for filter expressions
docker compose logs backend --tail 100 | grep "CONTENT FILTER"

# Verify Milvus index exists
docker compose exec backend python manage.py shell
>>> from vector_search.database import MilvusProjectVectorDatabase
>>> db = MilvusProjectVectorDatabase("your_project_id")
>>> db.collection.indexes  # Should show hierarchical_path index
```

### Frontend Validation

```bash
# Check frontend console for errors
# Open browser DevTools → Console
# Look for:
# - "📚 DOCAWARE SERVICE: Content filters (array): [...]"
# - "📚 AGENT ORCHESTRATION: Loaded X content filter options"
```

### API Validation

```bash
# Test hierarchical paths endpoint
curl "http://localhost:8000/api/agent-orchestration/docaware/hierarchical_paths/?project_id=YOUR_PROJECT_ID&include_files=true"

# Expected response structure:
{
  "project_id": "...",
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
      "id": "file_doc123",
      "name": "Q1_Report.pdf",
      "path": "Reports/Q1_Report.pdf",
      "type": "file",
      "displayName": "Reports/Q1_Report.pdf",
      "isFolder": false,
      "document_id": "doc123"
    }
  ],
  "folders_count": 5,
  "files_count": 12,
  "total_count": 17
}
```

---

## Known Limitations

1. **OR Logic Only**: Multiple filters use OR logic (not AND). Results come from ANY selected location.
2. **No Nested Multi-Select**: Cannot select "all files within selected folders" - must select individually.
3. **UI Space**: With many selections, chip container may require scrolling.

---

## Troubleshooting

### Issue: Chips not displaying

**Solution:** Check browser console for JavaScript errors. Verify hierarchicalPaths loaded correctly.

### Issue: Search returns no results with filter

**Solution:** Verify filter IDs match actual document paths. Check backend logs for filter expression.

### Issue: Dropdown doesn't reset after selection

**Solution:** Check updateNodeData() is being called. Verify nodeConfig.content_filters is array.

### Issue: Migration failed

**Solution:** Ensure Workflow model imported correctly. Check `users.models.WorkflowTemplate`.

---

## Success Criteria

✅ Multi-select UI works smoothly
✅ Chips display and removal works
✅ Search with filters returns correct results
✅ OR logic properly combines multiple filters
✅ Workflows persist filter configuration
✅ No errors in browser or backend logs
✅ Performance acceptable with many filters

---

## Contact

If you encounter issues not covered in this guide, check:
- Backend logs: `docker compose logs backend --tail 200`
- Frontend console: Browser DevTools → Console
- Implementation plan: `MULTI_SELECT_CONTENT_FILTER_IMPLEMENTATION_PLAN.md`
