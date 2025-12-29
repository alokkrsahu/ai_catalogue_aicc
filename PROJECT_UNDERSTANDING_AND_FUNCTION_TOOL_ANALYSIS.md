# Project Understanding and Function Tool Analysis

## Executive Summary

This document provides a comprehensive understanding of the AICC-IntelliDoc project structure, flow, and an analysis of the Function Tool agent implementation status.

---

## 1. Project Overview

### 1.1 Startup Flow
- **Start Script**: `./scripts/start-dev.sh`
- **Local URL**: `http://localhost:5173/`
- **Architecture**: Docker-based with Django backend and SvelteKit frontend

### 1.2 Main Entry Points
1. **Dashboard** (`http://localhost:5173/`)
   - Lists available features/templates
   - Primary feature: "AICC-IntelliDoc"

2. **Feature Selection** (`http://localhost:5173/features/intellidoc`)
   - Project listing page
   - "Create New Project" button for admin users
   - Project creation requires:
     - Project name
     - Description
     - Template selection ("Aicc Intellidoc V2" template)

3. **Project Interface** (`http://localhost:5173/features/intellidoc/project/{project_id}`)
   - Five navigation sections (left sidebar):
     - (i) Overview (Project Documents)
     - (ii) Agent Orchestration
     - (iii) Evaluation
     - (iv) Deploy
     - (v) Activity Tracker

---

## 2. Project Isolation Architecture

### 2.1 Key Design Principle
**Complete project-level isolation** - Multiple projects can run simultaneously without interference.

### 2.2 Isolation Mechanisms

#### A. Milvus Vector Collections
- **Location**: `backend/vector_search/database.py`
- **Implementation**: `MilvusProjectVectorDatabase` class
- **Collection Naming**: `{sanitized_project_name}_{project_id}`
- **Isolation**: Each project has its own dedicated Milvus collection
- **Code Reference**:
  ```python
  # backend/vector_search/database.py:45-68
  def _generate_collection_name(self, project_id: str) -> str:
      project = IntelliDocProject.objects.get(project_id=project_id)
      sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '', project.name.lower())
      collection_name = f"{sanitized_name}_{project_id.replace('-', '_')}"
  ```

#### B. Processing Threads
- **Location**: `backend/vector_search/api_views.py`
- **Implementation**: `PROCESSING_THREADS` dictionary (project_id → thread)
- **Isolation**: Each project has its own processing thread
- **Code Reference**:
  ```python
  # backend/vector_search/api_views.py:20-48
  PROCESSING_THREADS = {}  # Global thread registry
  
  def run_processing_in_background(project_id: str, processing_mode: str = 'enhanced'):
      # Project-specific processing
      thread = threading.Thread(target=process_project_documents, args=(project_id,))
      PROCESSING_THREADS[project_id] = thread
  ```

#### C. API Key Management
- **Location**: Project-specific API keys stored in database
- **Isolation**: Each project maintains its own encrypted API keys
- **Access**: Keys are retrieved per-project during agent execution

#### D. Conversation History
- **Isolation**: Each project maintains separate conversation histories
- **Storage**: Database records scoped by project_id

---

## 3. Navigation Sections Deep Dive

### 3.1 (i) Overview - Project Documents

#### Document Upload Methods
1. **Select Files**: Individual file upload
2. **Select Folder**: Folder upload
3. **Upload Zip**: ZIP archive upload

#### Start Processing Functionality
- **Location**: `backend/vector_search/api_views.py:52`
- **Endpoint**: `POST /api/projects/{project_id}/start_processing/`
- **Process**:
  1. Validates project exists and user has access
  2. Checks if processing already running (prevents duplicates)
  3. Starts background thread for document processing
  4. Thread executes: `run_processing_in_background(project_id, 'enhanced')`
  5. Documents are:
     - Parsed (PDF, DOCX, TXT, etc.)
     - Chunked into smaller pieces
     - Embedded using sentence-transformers (all-MiniLM-L6-v2)
     - Stored in project-specific Milvus collection
     - Metadata stored in PostgreSQL

#### Project Isolation in Processing
- Each project's processing runs in a separate thread
- Vector searches are scoped to project collection
- No cross-project data leakage possible

### 3.2 (ii) Agent Orchestration

#### Visual Workflow Designer
- **Component**: `frontend/my-sveltekit-app/src/lib/components/WorkflowDesigner.svelte`
- **Features**:
  - Drag-and-drop agent placement
  - Visual connection between agents
  - Property panel for agent configuration

#### Supported Agent Types
1. **StartNode**: Entry point (no incoming edges)
2. **UserProxyAgent**: Handles human input, can pause workflow
3. **AI Assistant Agent**: General-purpose LLM agent
4. **Group Chat Manager**: Coordinates multiple agents
5. **Delegate Agent**: Represents delegated execution
6. **End Node**: Termination point
7. **Function Tool**: Custom function/tool agent (see analysis below)

#### DocAware System
- **Location**: `backend/agent_orchestration/docaware/service.py`
- **Service**: `EnhancedDocAwareAgentService`
- **When Enabled**:
  - Toggle button in agent property panel
  - Available for: AssistantAgent, UserProxyAgent, GroupChatManager
- **Process Flow**:
  1. **Query Extraction**: Extracts search queries from user messages
  2. **Document Retrieval**: Searches project-specific Milvus collection
  3. **Search Methods**:
     - Semantic search (vector similarity)
     - Hybrid search (semantic + keyword)
     - Keyword search
     - Hierarchical search
  4. **Content Filtering**: Filter by folder paths or specific files
  5. **Context Injection**: Retrieved documents formatted and injected into agent prompts
  6. **Response Generation**: Agent generates response informed by documents

- **Code Flow**:
  ```python
  # backend/agent_orchestration/workflow_executor.py:566-574
  prompt = await self.chat_manager.craft_conversation_prompt_with_docaware(
      aggregated_context, node, str(project_id), conversation_history
  )
  # This internally calls:
  # backend/agent_orchestration/docaware/service.py:EnhancedDocAwareAgentService.search_documents()
  ```

### 3.3 (iii) Evaluation
- **Purpose**: Upload dataset (CSV) to evaluate workflow performance
- **Metrics**: ROUGE, BLEU, BERTScore, semantic similarity
- **Location**: `backend/agent_orchestration/workflow_evaluator.py`

### 3.4 (iv) Deploy
- **Features**:
  - Deploy workflow as public chatbot
  - Add allowed origins (CORS)
  - Set rate limits per origin
  - Generate embed code (HTML/JavaScript)
- **Location**: `backend/agent_orchestration/deployment_views.py`

### 3.5 (v) Activity Tracker
- **Purpose**: View conversation history of deployed workflows
- **Features**: Real-time monitoring of user interactions

---

## 4. Function Tool Agent Analysis

### 4.1 Current Implementation Status

#### ✅ What EXISTS:

1. **UI Definition**
   - **Location**: `frontend/my-sveltekit-app/src/lib/components/WorkflowDesigner.svelte:259-267`
   - **Definition**:
     ```typescript
     'FunctionTool': {
       name: 'Function Tool',
       description: 'Specialized agent that provides custom function capabilities and tool integration',
       icon: 'fa-wrench',
       color: '#6b7280',
       category: 'Tool',
       functionality: 'Provides custom function execution, tool integration, and specialized capabilities for workflow enhancement.',
       useCases: ['Custom functions', 'Tool integration', 'API calls', 'Specialized operations']
     }
     ```

2. **Validation Support**
   - **Location**: `backend/agent_orchestration/validation.py:44-50`
   - **Validation Rules**:
     ```python
     'FunctionTool': {
         'required_fields': ['name', 'function_code'],
         'optional_fields': ['description', 'dependencies'],
         'max_count': 20,
         'input_connections': 0,
         'output_connections': 0
     }
     ```
   - **Flow Validation**: FunctionTool nodes are **skipped** in workflow flow validation (line 230):
     ```python
     # Skip FunctionTool nodes as they don't participate in main flow
     if node_type == 'FunctionTool':
         continue
     ```

3. **Template Support**
   - **Location**: `backend/templates/template_definitions/aicc-intellidoc-v2/definition.py:141`
   - Listed as supported agent type: `'FunctionTool'`

4. **Security Validation**
   - **Location**: `backend/agent_orchestration/validation.py:WorkflowSecurityValidator`
   - Validates function code for dangerous patterns (exec, eval, file operations, etc.)

#### ❌ What is MISSING:

1. **Execution Logic**
   - **Location**: `backend/agent_orchestration/workflow_executor.py`
   - **Status**: **NO execution handler for FunctionTool nodes**
   - **Current Handlers**:
     - `StartNode` (line 316)
     - `AssistantAgent`, `UserProxyAgent`, `GroupChatManager`, `DelegateAgent` (line 354)
     - `EndNode` (line 747)
   - **Missing**: No `elif node_type == 'FunctionTool':` block

2. **Tool Registration**
   - **Status**: No code extracts FunctionTool nodes from graph and registers them as tools for agents
   - **Expected Behavior**: FunctionTool nodes should be:
     - Extracted from workflow graph
     - Registered as callable functions/tools
     - Made available to agents (AssistantAgent, etc.) for invocation
   - **Current**: FunctionTool nodes are validated but ignored during execution

3. **Tool Invocation**
   - **Status**: No mechanism for agents to invoke FunctionTool functions
   - **Expected**: Agents should be able to call FunctionTool functions during execution
   - **Current**: No integration between agents and FunctionTool nodes

4. **Property Panel Configuration**
   - **Status**: Need to verify if FunctionTool has a property panel in `NodePropertiesPanel.svelte`
   - **Expected**: Should allow users to:
     - Define function name
     - Write function code
     - Specify dependencies
     - Configure function parameters

### 4.2 Intended Design (Based on Research Paper)

According to `AICC_INTELLIDOC_RESEARCH_PAPER.md` (Section 6: Tool Usage):

1. **Tool Definition**: Tools defined with JSON schemas
2. **Tool Registration**: Tools registered with agents
3. **Tool Invocation**: Agents invoke tools during execution
4. **Result Integration**: Tool results integrated into agent context

**FunctionTool nodes should**:
- Define custom functions (via `function_code` field)
- Be registered as tools for agents
- Be invokable by agents during workflow execution
- Return results that are integrated into conversation context

### 4.3 Implementation Gap

**Current State**:
- FunctionTool is a **UI component** and **validation entity**
- FunctionTool is **NOT an execution entity**

**Required Implementation**:
1. **Extract FunctionTool nodes** from workflow graph
2. **Register as tools** for agents (AssistantAgent, etc.)
3. **Execute function code** when agents invoke tools
4. **Integrate results** into agent context

---

## 5. Key Code Locations

### 5.1 Project Isolation
- **Collection Generation**: `backend/vector_search/database.py:45-68`
- **Thread Management**: `backend/vector_search/api_views.py:20-48`
- **Processing Service**: `backend/vector_search/services_enhanced.py`

### 5.2 Workflow Execution
- **Main Executor**: `backend/agent_orchestration/workflow_executor.py`
- **Orchestrator**: `backend/agent_orchestration/conversation_orchestrator.py`
- **Parser**: `backend/agent_orchestration/workflow_parser.py`

### 5.3 DocAware System
- **Service**: `backend/agent_orchestration/docaware/service.py`
- **Handler**: `backend/agent_orchestration/docaware_handler.py`
- **Integration**: `backend/agent_orchestration/workflow_executor.py:566-574`

### 5.4 Function Tool
- **UI**: `frontend/my-sveltekit-app/src/lib/components/WorkflowDesigner.svelte:259-267`
- **Validation**: `backend/agent_orchestration/validation.py:44-50`
- **Template**: `backend/templates/template_definitions/aicc-intellidoc-v2/definition.py:141`
- **Execution**: ❌ **MISSING** - No handler in `workflow_executor.py`

---

## 6. Recommendations

### 6.1 For Function Tool Implementation

1. **Add Execution Handler** in `workflow_executor.py`:
   ```python
   elif node_type == 'FunctionTool':
       # Extract function definition
       function_name = node_data.get('function_name')
       function_code = node_data.get('function_code')
       # Register as tool for agents
       # Store in tool registry for later invocation
   ```

2. **Create Tool Registry**:
   - Extract all FunctionTool nodes from graph
   - Register them as callable tools
   - Make available to agents during execution

3. **Implement Tool Invocation**:
   - Detect tool calls in agent responses
   - Execute corresponding FunctionTool function
   - Return results to agent context

4. **Add Property Panel**:
   - Verify/implement FunctionTool property panel
   - Allow function code editing
   - Validate function code security

### 6.2 For Project Understanding

The project architecture is well-designed with:
- ✅ Strong project isolation
- ✅ Parallel execution support
- ✅ Comprehensive DocAware system
- ✅ Robust workflow orchestration
- ⚠️ Function Tool needs implementation

---

## 7. Conclusion

**Project Understanding**: ✅ **COMPLETE**
- All major components understood
- Project isolation mechanisms identified
- DocAware system flow documented
- Workflow execution flow mapped

**Function Tool Status**: ⚠️ **PARTIALLY IMPLEMENTED**
- UI and validation: ✅ Complete
- Execution logic: ❌ Missing
- Tool registration: ❌ Missing
- Tool invocation: ❌ Missing

**Next Steps**: Implement Function Tool execution, registration, and invocation mechanisms to complete the feature.

