# Project Creation Workflow - Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [User Journey](#user-journey)
3. [Frontend Architecture](#frontend-architecture)
4. [Backend Architecture](#backend-architecture)
5. [Template System](#template-system)
6. [Project Structure](#project-structure)
7. [Navigation Pages](#navigation-pages)
8. [API Endpoints](#api-endpoints)
9. [Component Details](#component-details)
10. [Data Flow](#data-flow)

---

## Overview

This document provides a complete understanding of the project creation workflow in the AI Catalogue application. The system follows a **template-independent architecture** where projects are created from templates, and the template configuration is **cloned** into the project at creation time. This ensures that projects are independent of template changes.

### Key Concepts

- **Template Independence**: Projects clone template configuration at creation, making them independent of future template changes
- **Universal API**: All projects use the same API endpoints regardless of their source template
- **Capability-Based UI**: The UI adapts based on project capabilities (cloned from templates) rather than template files
- **Multi-Page Navigation**: Projects can have multiple navigation pages defined in the template configuration

---

## User Journey

### Step 1: Dashboard Access (`http://localhost:5173/`)

**Route**: `src/routes/+page.svelte`

The user starts at the dashboard, which displays available features/applications as icons.

**Flow:**
1. User logs in and is authenticated
2. `onMount()` calls `getMyDashboardIcons()` API
3. Dashboard icons are fetched from `/api/dashboard-icons/`
4. Icons are displayed in a grid with name, description, icon, and color

**Key Code:**
```typescript
// src/routes/+page.svelte
onMount(async () => {
  const response = await getMyDashboardIcons();
  icons = response; // Array of DashboardIcon objects
});

// Each icon has a route property
<a href={icon.route}> // e.g., '/features/intellidoc'
```

**Dashboard Icon Structure** (from backend):
- `name`: "AICC-IntelliDoc"
- `description`: "AI-powered document processing and analysis"
- `route`: "/features/intellidoc"
- `icon_class`: "fa-sitemap"
- `color`: "oxford-blue"

---

### Step 2: Feature Selection (`http://localhost:5173/features/intellidoc`)

**Route**: `src/routes/features/intellidoc/+page.svelte`

When the user clicks on "AICC-IntelliDoc" from the dashboard, they navigate to the IntelliDoc projects list page.

**Flow:**
1. Page loads and calls `cleanUniversalApi.getAllProjects()`
2. Fetches all projects for the authenticated user from `/api/projects/`
3. Displays projects in a grid with cards showing:
   - Project name, description, template type
   - Created date, creator
   - Features and capabilities
   - "Open Project" button
4. Admin users see "Create New Project" button

**Key Code:**
```typescript
// src/routes/features/intellidoc/+page.svelte
async function fetchProjects() {
  const response = await cleanUniversalApi.getAllProjects();
  projects = response; // Array of IntelliDocProject objects
}

function onProjectCreated(event: CustomEvent<IntelliDocProject>) {
  const newProject = event.detail;
  // Navigate to the newly created project
  goto(`/features/intellidoc/project/${newProject.project_id}`);
}
```

**Project List Display:**
- Project cards show template information
- Features are displayed as tags (e.g., "4 pages", "AI Analysis", "Vector Search")
- Each project has an "Open Project" button that navigates to the project detail page

---

### Step 3: Create New Project Modal

**Component**: `src/lib/components/ProjectCreator.svelte`

When admin clicks "Create New Project", a modal opens with the `ProjectCreator` component.

**Flow:**
1. Modal opens showing the project creation form
2. User enters:
   - **Project Name** (required, min 3 characters)
   - **Description** (required, min 10 characters)
   - **Template Selection** (required)
   - **API Keys** (optional, can be added later)

**Template Selection:**
- Uses `TemplateSelector` component
- Loads all available templates from `templateService.loadTemplates()`
- Displays templates in a grid with:
  - Template icon
  - Template name (e.g., "Aicc Intellidoc V2")
  - Template description
  - Visual selection indicator

**Key Code:**
```typescript
// src/lib/components/ProjectCreator.svelte
async function createProject() {
  const projectData = {
    name: projectName.trim(),
    description: projectDescription.trim(),
    template_id: selectedTemplate!.id // e.g., 'aicc-intellidoc-v2'
  };
  
  // Create project via universal API
  const createdProject = await cleanUniversalApi.createProject(projectData);
  
  // Optionally save API keys if provided
  if (providedKeys.length > 0) {
    for (const [provider, key] of providedKeys) {
      await cleanUniversalApi.saveProjectApiKey(createdProject.project_id, {
        provider_type: provider,
        api_key: key.trim(),
        is_active: true
      });
    }
  }
  
  // Dispatch event to parent
  dispatch('projectCreated', createdProject);
}
```

**Template Selection UI:**
- Templates displayed as cards in a grid
- Selected template is highlighted with a green checkmark
- Template preview shows features (e.g., "4 pages", "AI Analysis", "Vector Search")
- User can expand/collapse API Keys section (optional)

---

### Step 4: Project Creation API Call

**Backend Route**: `POST /api/projects/`
**Backend View**: `backend/api/universal_project_views.py::UniversalProjectViewSet.create()`

**Request Payload:**
```json
{
  "name": "TEST2",
  "description": "This is a test project",
  "template_id": "aicc-intellidoc-v2"
}
```

**Backend Flow:**
1. Validates user is admin (only admins can create projects)
2. Validates `template_id` is provided
3. Calls `TemplateDiscoverySystem.get_template_configuration(template_id)`
4. Retrieves complete template configuration from template definition file
5. **Clones template configuration** into the project:
   - Basic fields (name, description, icon, etc.)
   - **Navigation pages** (complete structure)
   - **Processing capabilities**
   - **UI configuration**
   - **Validation rules**
6. Creates `IntelliDocProject` record in database
7. Returns created project with all cloned data

**Key Code:**
```python
# backend/api/universal_project_views.py
def create(self, request, *args, **kwargs):
    template_id = request.data.get('template_id')
    template_data = TemplateDiscoverySystem.get_template_configuration(template_id)
    template_config = template_data.get('configuration', {})
    
    project_data = {
        'name': request.data.get('name'),
        'description': request.data.get('description'),
        'template_name': template_config.get('name'),
        'template_type': template_config.get('template_type'),
        # Clone navigation pages
        'total_pages': template_config.get('total_pages', 1),
        'navigation_pages': template_config.get('navigation_pages', []),
        # Clone capabilities
        'processing_capabilities': template_config.get('processing_capabilities', {}),
        'ui_configuration': template_config.get('ui_configuration', {}),
        # ... other cloned fields
    }
    
    serializer = self.get_serializer(data=project_data)
    project = serializer.save(created_by=request.user)
    return Response(serializer.data, status=HTTP_201_CREATED)
```

**Response:**
```json
{
  "project_id": "04169052-4fbd-451b-ae09-476a40f82e7f",
  "name": "TEST2",
  "description": "This is a test project",
  "template_type": "aicc-intellidoc-v2",
  "template_name": "AICC-IntelliDoc v2",
  "has_navigation": true,
  "total_pages": 4,
  "navigation_pages": [
    {
      "page_number": 1,
      "name": "Overview",
      "short_name": "Overview",
      "icon": "fa-home",
      "features": ["document_management", "upload_interface", "processing_status"]
    },
    {
      "page_number": 2,
      "name": "Agent Orchestration",
      "short_name": "Agents",
      "icon": "fa-sitemap",
      "features": ["visual_workflow_designer", "agent_management", ...]
    },
    // ... pages 3 and 4
  ],
  "processing_capabilities": {
    "supports_ai_analysis": true,
    "supports_vector_search": true,
    "supports_agent_orchestration": true,
    // ... more capabilities
  },
  // ... other fields
}
```

---

### Step 5: Navigate to Project Detail Page

**Route**: `http://localhost:5173/features/intellidoc/project/{project_id}`
**Component**: `src/routes/features/intellidoc/project/[id]/+page.svelte`

After project creation, the user is automatically navigated to the project detail page.

**Flow:**
1. Page component extracts `project_id` from URL params
2. Calls `cleanUniversalApi.getProject(projectId)`
3. Fetches complete project data including:
   - Cloned navigation pages
   - Processing capabilities
   - UI configuration
   - Documents (empty initially)
   - Processing status
4. Checks API key status
5. Renders UI based on project capabilities

**Key Code:**
```typescript
// src/routes/features/intellidoc/project/[id]/+page.svelte
$: projectId = $page.params.id;

async function loadProject() {
  project = await cleanUniversalApi.getProject(projectId);
  
  // Extract capabilities from cloned project data (NOT template files)
  projectCapabilities = project.processing_capabilities || {};
  hasNavigation = project.has_navigation || false;
  navigationPages = project.navigation_pages || [];
  
  // Set up navigation based on cloned project data
  if (hasNavigation && project.total_pages > 1) {
    currentPage = 1;
  }
}
```

---

## Frontend Architecture

### Route Structure

```
src/routes/
├── +page.svelte                    # Dashboard (root)
├── +layout.svelte                  # Main layout with navigation
├── features/
│   └── intellidoc/
│       ├── +page.svelte            # Project list page
│       └── project/
│           └── [id]/
│               └── +page.svelte    # Project detail page
```

### Key Components

#### 1. Dashboard (`src/routes/+page.svelte`)
- Displays dashboard icons fetched from API
- Each icon links to a feature route
- Handles authentication state

#### 2. Project List (`src/routes/features/intellidoc/+page.svelte`)
- Lists all projects for the authenticated user
- Shows "Create New Project" button for admins
- Uses `ProjectCreator` component in a modal

#### 3. Project Creator (`src/lib/components/ProjectCreator.svelte`)
- Form for project name, description
- Template selection via `TemplateSelector`
- Optional API key configuration
- Validates input and creates project

#### 4. Template Selector (`src/lib/components/TemplateSelector.svelte`)
- Loads available templates
- Displays templates in grid or dropdown
- Handles template selection and configuration loading
- Shows selected template preview

#### 5. Project Detail Page (`src/routes/features/intellidoc/project/[id]/+page.svelte`)
- Main project interface
- Renders navigation sidebar based on `navigation_pages`
- Shows different content based on `currentPage`
- Handles document upload, processing, API management

### Component Hierarchy

```
+page.svelte (Dashboard)
└── Dashboard Icons → /features/intellidoc

features/intellidoc/+page.svelte
├── ProjectCreator (modal)
│   ├── TemplateSelector
│   └── API Key Fields (optional)
└── Project Cards

features/intellidoc/project/[id]/+page.svelte
├── Navigation Sidebar (if hasNavigation)
├── Project Header
├── API Key Warning Banner
└── Page Content (based on currentPage)
    ├── Page 1: Overview (Document Upload)
    ├── Page 2: Agent Orchestration
    │   └── AgentOrchestrationInterface
    ├── Page 3: Insights (Coming Soon)
    └── Page 4: Export (Coming Soon)
```

---

## Backend Architecture

### Models

#### IntelliDocProject (`backend/users/models.py`)
```python
class IntelliDocProject(models.Model):
    project_id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    
    # Cloned template data
    template_name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20)
    icon_class = models.CharField(max_length=50)
    
    # Navigation configuration (CLONED)
    has_navigation = models.BooleanField(default=False)
    total_pages = models.IntegerField(default=1)
    navigation_pages = models.JSONField(default=list)  # Complete navigation structure
    
    # Capabilities (CLONED)
    processing_capabilities = models.JSONField(default=dict)
    validation_rules = models.JSONField(default=dict)
    ui_configuration = models.JSONField(default=dict)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Key Points:**
- `navigation_pages` is a JSONField storing the complete navigation structure
- `processing_capabilities` stores all template capabilities
- All template data is **cloned** at creation time, not referenced

### Views

#### UniversalProjectViewSet (`backend/api/universal_project_views.py`)
- `list()`: Get all projects for user
- `create()`: Create project from template (clones configuration)
- `retrieve()`: Get single project details
- `update()`: Update project
- `delete()`: Delete project

### Template System

#### Template Discovery (`backend/templates/discovery.py`)
- Scans `backend/templates/template_definitions/` folder
- Each template has a `definition.py` file with `get_complete_configuration()` method
- Returns complete configuration including navigation pages

#### Template Definition (`backend/templates/template_definitions/aicc-intellidoc-v2/definition.py`)
```python
class AICCIntelliDocTemplateDefinition:
    def get_complete_configuration(self):
        return {
            'name': 'AICC-IntelliDoc v2',
            'template_type': 'aicc-intellidoc-v2',
            'total_pages': 4,
            'navigation_pages': [
                {
                    'page_number': 1,
                    'name': 'Overview',
                    'short_name': 'Overview',
                    'icon': 'fa-home',
                    'features': ['document_management', 'upload_interface', 'processing_status']
                },
                # ... more pages
            ],
            'processing_capabilities': {
                'supports_ai_analysis': True,
                'supports_vector_search': True,
                'supports_agent_orchestration': True,
                # ... more capabilities
            },
            # ... other configuration
        }
```

---

## Template System

### Template Structure

Templates are defined in `backend/templates/template_definitions/{template_id}/definition.py`

Each template provides:
1. **Basic Metadata**: Name, description, icon, color
2. **Navigation Configuration**: Array of navigation pages with features
3. **Processing Capabilities**: What the project can do
4. **UI Configuration**: How the UI should be rendered
5. **Validation Rules**: What's required/allowed

### Template Cloning Process

When a project is created:

1. **Template Discovery**: System finds template by `template_id`
2. **Configuration Retrieval**: Calls `template.get_complete_configuration()`
3. **Data Cloning**: All configuration is **copied** into project fields:
   ```python
   navigation_pages = template_config.get('navigation_pages', []).copy()
   processing_capabilities = template_config.get('processing_capabilities', {}).copy()
   ```
4. **Database Storage**: Project is saved with cloned data
5. **Independence**: Project is now independent of template changes

### Template Examples

#### AICC-IntelliDoc V2 Template
- **4 Navigation Pages**: Overview, Agent Orchestration, Insights, Export
- **Agent Orchestration**: Supports visual workflow designer
- **Multi-page Navigation**: `has_navigation = True`

#### AICC-IntelliDoc Template
- **4 Navigation Pages**: Introduction, Document Upload, Hierarchical Analysis, Advanced Search
- **Hierarchical Processing**: Supports document categorization

---

## Project Structure

### Navigation Pages Structure

Each project has a `navigation_pages` array with the following structure:

```typescript
interface NavigationPage {
  page_number: number;
  name: string;              // Full name (e.g., "Overview")
  short_name: string;        // Short name (e.g., "Overview")
  icon: string;              // Font Awesome icon class (e.g., "fa-home")
  features: string[];        // List of feature identifiers
}
```

**Example for AICC-IntelliDoc V2:**
```json
[
  {
    "page_number": 1,
    "name": "Overview",
    "short_name": "Overview",
    "icon": "fa-home",
    "features": ["document_management", "upload_interface", "processing_status"]
  },
  {
    "page_number": 2,
    "name": "Agent Orchestration",
    "short_name": "Agents",
    "icon": "fa-sitemap",
    "features": ["visual_workflow_designer", "agent_management", "real_time_execution", "workflow_history"]
  },
  {
    "page_number": 3,
    "name": "Insights",
    "short_name": "Insights",
    "icon": "fa-lightbulb",
    "features": ["hierarchical_analysis", "category_filtering", "document_organization", "ai_insights"]
  },
  {
    "page_number": 4,
    "name": "Export",
    "short_name": "Export",
    "icon": "fa-download",
    "features": ["advanced_search", "content_reconstruction", "export_options"]
  }
]
```

### Processing Capabilities Structure

```typescript
interface ProcessingCapabilities {
  supports_ai_analysis: boolean;
  supports_vector_search: boolean;
  supports_agent_orchestration: boolean;
  supports_hierarchical_processing: boolean;
  max_file_size: number;
  supported_formats: string[];
  ai_models: {
    content_analysis: string;
    embedding_model: string;
  };
  // ... more capabilities
}
```

---

## Navigation Pages

### Overview Page (Page 1)

**Features:**
- `document_management`: List and manage uploaded documents
- `upload_interface`: Drag-and-drop file upload
- `processing_status`: View document processing status

**UI Components:**
- Document upload area (drag-and-drop)
- File/folder/zip upload buttons
- Document list with delete functionality
- Project overview stats (documents count, processed count, pages)
- Processing status panel with "Start Processing" button
- API Management button

**Code Location:**
- Rendered when `currentPage === 1` in project detail page
- Component: `src/routes/features/intellidoc/project/[id]/+page.svelte` (lines 570-843)

### Agent Orchestration Page (Page 2)

**Features:**
- `visual_workflow_designer`: Visual drag-and-drop workflow builder
- `agent_management`: Create and configure AI agents
- `real_time_execution`: Real-time workflow execution monitoring
- `workflow_history`: View past workflow executions

**UI Components:**
- Workflow Designer tab
- Execution History tab
- Agent workflow canvas
- Workflow creation/editing interface

**Code Location:**
- Rendered when `currentPage === 2` in project detail page
- Component: `src/lib/components/AgentOrchestrationInterface.svelte`
- Condition: Only shown if `project.processing_capabilities.supports_agent_orchestration === true`

**Key Code:**
```typescript
{#if hasNavigation && currentPage === 2}
  {#if project.processing_capabilities?.supports_agent_orchestration}
    <AgentOrchestrationInterface {project} {projectId} />
  {:else}
    <!-- Show message that agent orchestration is not supported -->
  {/if}
{/if}
```

### Insights Page (Page 3)

**Status**: Coming Soon

**Features** (planned):
- `hierarchical_analysis`: Hierarchical document analysis
- `category_filtering`: Filter documents by category
- `document_organization`: Organize documents hierarchically
- `ai_insights`: AI-generated insights

**Current Implementation:**
- Shows "Coming Soon" placeholder

### Export Page (Page 4)

**Status**: Coming Soon

**Features** (planned):
- `advanced_search`: Advanced document search
- `content_reconstruction`: Reconstruct full document content
- `export_options`: Export documents and data

**Current Implementation:**
- Shows "Coming Soon" placeholder

---

## API Endpoints

### Project Management

#### GET /api/projects/
**Description**: Get all projects for authenticated user
**Response**: Array of project objects with all cloned configuration

#### POST /api/projects/
**Description**: Create new project from template
**Request Body**:
```json
{
  "name": "Project Name",
  "description": "Project Description",
  "template_id": "aicc-intellidoc-v2"
}
```
**Response**: Created project object with all cloned data

#### GET /api/projects/{project_id}/
**Description**: Get single project details
**Response**: Complete project object including:
- Navigation pages
- Processing capabilities
- UI configuration
- Documents count
- Processing status

#### PATCH /api/projects/{project_id}/
**Description**: Update project
**Response**: Updated project object

#### DELETE /api/projects/{project_id}/
**Description**: Delete project (requires password)
**Request Body**: `{ "password": "user_password" }`

### Document Management

#### GET /api/projects/{project_id}/documents/
**Description**: Get all documents for a project
**Response**: Array of document objects

#### POST /api/projects/{project_id}/upload_document/
**Description**: Upload single document
**Request**: FormData with file
**Response**: Document object

#### POST /api/projects/{project_id}/upload_bulk_files/
**Description**: Upload multiple files
**Request**: FormData with multiple files
**Response**: Upload result with success/failure counts

#### POST /api/projects/{project_id}/upload_zip_file/
**Description**: Upload zip file and extract contents
**Request**: FormData with zip file
**Response**: Extraction result with extracted files info

#### DELETE /api/projects/{project_id}/delete_document/
**Description**: Delete a document
**Request Body**: `{ "document_id": "uuid" }`

### Processing

#### POST /api/projects/{project_id}/process_documents/
**Description**: Start document processing
**Response**: Processing status

#### GET /api/projects/{project_id}/vector-status/
**Description**: Get processing status
**Response**: Processing status with progress

### Agent Orchestration

#### GET /api/projects/{project_id}/agent_workflows/
**Description**: Get all agent workflows for project
**Response**: Array of workflow objects

#### POST /api/projects/{project_id}/agent_workflows/
**Description**: Create new agent workflow
**Request Body**: Workflow graph JSON
**Response**: Created workflow object

#### GET /api/projects/{project_id}/agent_workflow/?workflow_id={id}
**Description**: Get single workflow
**Response**: Workflow object

#### PUT /api/projects/{project_id}/agent_workflow/?workflow_id={id}
**Description**: Update workflow
**Request Body**: Updated workflow graph JSON
**Response**: Updated workflow object

#### POST /api/projects/{project_id}/execute_workflow/
**Description**: Execute workflow
**Request Body**: `{ "workflow_id": "uuid", "execution_parameters": {} }`
**Response**: Execution result

### API Key Management

#### GET /api/project-api-keys/project/{project_id}/keys/
**Description**: Get all API keys for project
**Response**: Array of API key objects

#### POST /api/project-api-keys/project/{project_id}/keys/
**Description**: Save/update API key
**Request Body**:
```json
{
  "provider_type": "openai",
  "api_key": "sk-...",
  "is_active": true
}
```
**Response**: API key object

#### DELETE /api/project-api-keys/project/{project_id}/keys/{provider_type}/
**Description**: Delete API key for provider

#### POST /api/project-api-keys/project/{project_id}/keys/{provider_type}/validate/
**Description**: Validate API key
**Response**: Validation result

### Template Discovery

#### GET /api/project-templates/
**Description**: Get all available templates
**Response**: Array of template objects

#### GET /api/templates/{template_id}/discover/
**Description**: Get template configuration
**Response**: Complete template configuration

---

## Component Details

### ProjectCreator Component

**File**: `src/lib/components/ProjectCreator.svelte`

**Props**: None (uses events)

**Events**:
- `projectCreated`: Dispatched when project is successfully created

**State**:
- `projectName`: string
- `projectDescription`: string
- `selectedTemplate`: TemplateInfo | null
- `templateConfiguration`: CompleteTemplateConfig | null
- `apiKeys`: { openai, google, anthropic }
- `showApiKeysSection`: boolean
- `creating`: boolean

**Key Functions**:
- `validateForm()`: Validates all form fields
- `createProject()`: Creates project via API and optionally saves API keys
- `resetForm()`: Clears form state
- `onTemplateSelected()`: Handles template selection from TemplateSelector

### TemplateSelector Component

**File**: `src/lib/components/TemplateSelector.svelte`

**Props**:
- `selectedTemplate`: TemplateInfo | null (bindable)
- `showConfiguration`: boolean (default: false)
- `compact`: boolean (default: false)
- `smallGrid`: boolean (default: false)

**Events**:
- `templateSelected`: Dispatched when template is selected

**State**:
- `templates`: TemplateInfo[]
- `loading`: boolean
- `templateConfiguration`: CompleteTemplateConfig | null

**Key Functions**:
- `loadTemplates()`: Loads templates from templateService
- `selectTemplate()`: Selects template and loads configuration

### Project Detail Page Component

**File**: `src/routes/features/intellidoc/project/[id]/+page.svelte`

**State**:
- `project`: Project object
- `currentPage`: number (1-4)
- `hasNavigation`: boolean
- `navigationPages`: NavigationPage[]
- `uploadedDocuments`: Document[]
- `processing`: boolean
- `processingStatus`: ProcessingStatus
- `showApiManagement`: boolean
- `apiKeyStatus`: APIKeyStatus

**Key Functions**:
- `loadProject()`: Loads project data
- `loadDocuments()`: Loads project documents
- `loadProcessingStatus()`: Loads processing status
- `checkApiKeyStatus()`: Checks if API keys are configured
- `uploadFiles()`: Handles file uploads (single, bulk, zip)
- `processDocuments()`: Starts document processing
- `goToPage()`: Navigates to a specific navigation page

**Conditional Rendering**:
```typescript
{#if hasNavigation && currentPage === 1}
  <!-- Overview page content -->
{:else if hasNavigation && currentPage === 2}
  <!-- Agent Orchestration page -->
{:else if hasNavigation && currentPage === 3}
  <!-- Insights page (Coming Soon) -->
{:else if hasNavigation && currentPage === 4}
  <!-- Export page (Coming Soon) -->
{/if}
```

### AgentOrchestrationInterface Component

**File**: `src/lib/components/AgentOrchestrationInterface.svelte`

**Props**:
- `project`: Project object
- `projectId`: string

**State**:
- `activeTab`: 'designer' | 'history'
- `allWorkflows`: Workflow[]
- `selectedWorkflow`: Workflow | null
- `isExecuting`: boolean
- `conversationHistory`: Message[]

**Key Functions**:
- `loadWorkflows()`: Loads all workflows for project
- `createWorkflow()`: Creates new workflow
- `executeWorkflow()`: Executes a workflow
- `loadConversationHistory()`: Loads execution history

---

## Data Flow

### Project Creation Flow

```
1. User clicks "Create New Project"
   ↓
2. ProjectCreator modal opens
   ↓
3. User selects template via TemplateSelector
   ↓
4. TemplateSelector loads templates from templateService
   ↓
5. User selects "Aicc Intellidoc V2" template
   ↓
6. TemplateSelector dispatches 'templateSelected' event
   ↓
7. ProjectCreator receives template selection
   ↓
8. User fills form and clicks "Create Project"
   ↓
9. ProjectCreator calls cleanUniversalApi.createProject()
   ↓
10. POST /api/projects/ with {name, description, template_id}
    ↓
11. Backend: UniversalProjectViewSet.create()
    ↓
12. TemplateDiscoverySystem.get_template_configuration(template_id)
    ↓
13. Template definition returns complete configuration
    ↓
14. Backend clones configuration into project fields
    ↓
15. IntelliDocProject.objects.create() with cloned data
    ↓
16. Project saved to database with navigation_pages, capabilities, etc.
    ↓
17. Response returns created project
    ↓
18. Frontend receives project object
    ↓
19. ProjectCreator dispatches 'projectCreated' event
    ↓
20. Parent component navigates to /features/intellidoc/project/{project_id}
    ↓
21. Project detail page loads
    ↓
22. cleanUniversalApi.getProject(projectId)
    ↓
23. Project data loaded (including cloned navigation_pages)
    ↓
24. UI renders based on project.navigation_pages
    ↓
25. User sees Overview page (page 1)
```

### Template Cloning Flow

```
Template Definition File
  (backend/templates/template_definitions/aicc-intellidoc-v2/definition.py)
    ↓
get_complete_configuration() returns:
  - navigation_pages: [...]
  - processing_capabilities: {...}
  - ui_configuration: {...}
    ↓
TemplateDiscoverySystem.get_template_configuration()
    ↓
Backend create() method receives template config
    ↓
Configuration is COPIED (cloned) into project fields:
  - project.navigation_pages = template_config.navigation_pages.copy()
  - project.processing_capabilities = template_config.processing_capabilities.copy()
    ↓
Project saved to database
    ↓
Project is now INDEPENDENT of template
    ↓
Future template changes do NOT affect existing projects
```

### Navigation Page Rendering Flow

```
Project Detail Page loads
  ↓
loadProject() fetches project data
  ↓
project.navigation_pages extracted from response
  ↓
navigationPages = project.navigation_pages
  ↓
hasNavigation = project.has_navigation && navigationPages.length > 0
  ↓
If hasNavigation:
  - Render navigation sidebar
  - Display navigation page buttons
  - Set currentPage = 1 (default)
    ↓
User clicks navigation page
  ↓
goToPage(pageNumber) called
  ↓
currentPage = pageNumber
  ↓
Conditional rendering based on currentPage:
  - currentPage === 1 → Overview content
  - currentPage === 2 → Agent Orchestration content
  - currentPage === 3 → Insights content (Coming Soon)
  - currentPage === 4 → Export content (Coming Soon)
```

---

## Key Design Decisions

### 1. Template Independence

**Decision**: Projects clone template configuration at creation time rather than referencing it.

**Rationale**:
- Projects remain stable even if templates are updated
- Historical projects maintain their original configuration
- No dependency on template files after creation

**Implementation**:
- All template configuration is copied using `.copy()` in Python
- Navigation pages, capabilities, UI config all stored in project JSONFields
- Frontend reads from project data, not template files

### 2. Universal API

**Decision**: All projects use the same API endpoints regardless of template.

**Rationale**:
- Simplified API design
- Consistent interface across all projects
- Easier to maintain and extend

**Implementation**:
- Single `UniversalProjectViewSet` handles all projects
- Capability-based logic (e.g., `if supports_agent_orchestration`)
- Frontend adapts UI based on project capabilities

### 3. Capability-Based UI

**Decision**: UI renders based on project capabilities, not template type.

**Rationale**:
- Flexible: Projects can have custom capabilities
- Extensible: Easy to add new capabilities
- Maintainable: Single codebase for all project types

**Implementation**:
- Project stores `processing_capabilities` JSONField
- Frontend checks `project.processing_capabilities.supports_agent_orchestration`
- Components conditionally render based on capabilities

### 4. Navigation Pages as Data

**Decision**: Navigation structure is stored as data in project, not hardcoded.

**Rationale**:
- Flexible navigation structure
- Templates can define custom pages
- Projects can have different navigation even from same template type

**Implementation**:
- `navigation_pages` is a JSONField array
- Each page has `page_number`, `name`, `icon`, `features`
- Frontend iterates over `navigation_pages` to render sidebar

---

## Summary

The project creation workflow follows these principles:

1. **Template-Driven**: Projects are created from templates that define their structure
2. **Template-Independent**: Template configuration is cloned at creation, making projects independent
3. **Capability-Based**: UI adapts based on project capabilities, not template files
4. **Universal API**: All projects use the same endpoints
5. **Data-Driven Navigation**: Navigation structure is stored as data in the project

The flow is:
1. Dashboard → Feature Selection → Project List
2. Create Project → Select Template → Fill Form → Submit
3. Backend clones template configuration → Project created
4. Navigate to project → Load project data → Render based on navigation_pages
5. User interacts with project through navigation pages

This architecture provides flexibility, maintainability, and extensibility while keeping projects stable and independent of template changes.

