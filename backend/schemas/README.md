# AICC Custom Agent Workflow Schema System

## Overview

This is our **custom JSON schema system** for defining agent workflows that has **completely replaced AutoGen**. It provides precise, clear information about how agents are connected, conversation flow, start/end nodes, and execution orchestration.

## 🎯 Why We Replaced AutoGen

- **Complete Control**: Custom implementation tailored to our specific needs
- **Clear Flow Definition**: Precise JSON schema defining agent connections and conversation flow
- **Independent System**: No external dependencies or complex AutoGen configurations
- **Validation & Analysis**: Built-in flow analysis, cycle detection, and validation
- **Template Independence**: Fully aligned with our template independence architecture

## 📋 Schema Features

### 🏗️ Core Components

1. **Agents**: Individual AI agents with specific roles and capabilities
2. **Connections**: Define how agents communicate and conversation flows
3. **Flow Configuration**: Start/end nodes and termination conditions
4. **Execution Settings**: Runtime configuration and parameters
5. **Metadata**: Workflow information and categorization

### 🔗 Connection Types

- **Direct**: Simple agent-to-agent communication
- **Conditional**: Flow based on message content or conditions
- **Broadcast**: One agent sends to multiple agents
- **Handoff**: Transfer control between agents
- **Loop Back**: Return to previous agent for iteration
- **Termination**: End workflow execution

### 🤖 Supported Agent Types

- `DocumentAnalyzerAgent`: Document analysis and processing
- `HierarchicalProcessorAgent`: Multi-level content processing
- `CategoryClassifierAgent`: Content classification
- `ContentReconstructorAgent`: Content synthesis
- `ResearchAgent`: Web research and information gathering
- `UserProxyAgent`: Human interaction
- `CoordinatorAgent`: Workflow coordination
- `ValidationAgent`: Quality validation
- `SummaryAgent`: Content summarization
- `CustomAgent`: User-defined custom agents

## 📁 File Structure

```
backend/schemas/
├── agent_workflow_schema.json      # Main JSON schema definition
├── workflow_validator.py           # Python validation and analysis
├── example_workflow.json          # Example workflow implementation
└── README.md                       # This documentation
```

## 🚀 Usage

### Basic Validation

```python
from schemas.workflow_validator import AgentWorkflowValidator

validator = AgentWorkflowValidator()
is_valid, errors, analysis = validator.validate_workflow(workflow_data)

if is_valid:
    print("✅ Workflow is valid and ready for execution")
else:
    print("❌ Validation errors:", errors)
```

### Building Workflows Programmatically

```python
from schemas.workflow_validator import WorkflowBuilder

# Create builder
builder = WorkflowBuilder("My Workflow", "project-123")

# Add agents
start_agent = builder.add_agent(
    "Document Analyzer", 
    "DocumentAnalyzerAgent",
    "Analyze uploaded documents",
    is_start=True,
    capabilities=["document_analysis", "text_processing"]
)

summary_agent = builder.add_agent(
    "Summary Generator",
    "SummaryAgent", 
    "Create document summary",
    is_end=True,
    capabilities=["summarization"]
)

# Connect agents
builder.add_connection(start_agent, summary_agent, "direct")

# Set flow configuration
builder.set_flow_configuration(start_agent, [summary_agent])

# Build and validate
workflow, is_valid, errors = builder.validate_and_build()
```

### Comprehensive Analysis

```python
# Generate detailed workflow analysis
summary = validator.generate_workflow_summary(workflow_data)

print(f"Complexity Score: {summary['summary_stats']['complexity_score']}/100")
print(f"Execution Paths: {summary['flow']['total_paths']}")
print(f"Recommendations: {summary['recommendations']}")
```

## 🔍 Validation Features

### Structure Validation
- ✅ Agent ID uniqueness
- ✅ Connection validity
- ✅ Start/end node verification
- ✅ Isolated agent detection

### Flow Analysis
- ✅ Reachability analysis
- ✅ Cycle detection
- ✅ Execution path mapping
- ✅ Dead-end identification

### Schema Compliance
- ✅ JSON Schema validation
- ✅ Required field checking
- ✅ Data type validation
- ✅ Enum value verification

## 📊 Example Workflow Definition

```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_name": "Document Analysis Workflow",
  "project_id": "4c9f79dd-6537-4298-a79f-7c8351d765f0",
  "agents": [
    {
      "agent_id": "agent-001",
      "agent_name": "Document Analyzer",
      "agent_type": "DocumentAnalyzerAgent",
      "system_message": "Analyze uploaded documents and extract key information.",
      "is_start_node": true,
      "llm_configuration": {
        "provider": "openai",
        "model": "gpt-4-turbo",
        "temperature": 0.3
      }
    },
    {
      "agent_id": "agent-002", 
      "agent_name": "Summary Generator",
      "agent_type": "SummaryAgent",
      "system_message": "Create comprehensive summaries.",
      "is_end_node": true,
      "llm_configuration": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022"
      }
    }
  ],
  "connections": [
    {
      "connection_id": "conn-001",
      "from_agent_id": "agent-001",
      "to_agent_id": "agent-002",
      "connection_type": "direct"
    }
  ],
  "flow_configuration": {
    "start_agent_id": "agent-001",
    "end_agent_ids": ["agent-002"],
    "max_total_messages": 50,
    "flow_mode": "selective"
  }
}
```

## 🔗 API Integration

### New API Endpoints

- `POST /api/projects/{id}/validate_workflow/` - Validate workflow schema
- `GET/POST /api/projects/{id}/agent_workflows/` - Manage workflows with validation
- `PUT /api/projects/{id}/agent_workflow/` - Update with schema validation
- `POST /api/projects/{id}/execute_workflow/` - Execute with custom implementation

### Enhanced Responses

All workflow-related endpoints now include:
- `agent_system: "custom_aicc_schema"`
- `schema_version: "1.0.0"`
- Validation results and analysis
- Flow analysis and recommendations

## 🧪 Testing

Run the test suite to verify the system:

```bash
cd backend
python test_custom_schema_system.py
```

Expected output:
```
🔍 Testing AICC Custom Agent Workflow Schema System
============================================================

📋 Test 1: Validating Example Workflow
✅ Loaded example workflow: Document Analysis and Summary Workflow
📊 Validation Result: PASSED
🎯 Agents: 6
🔗 Connections: 8
🚀 Execution Paths: 3

🏗️ Test 2: Building Workflow Programmatically
✅ Built workflow: Test Document Analysis
📊 Validation Result: PASSED

🎉 AICC Custom Schema System Tests Complete!
✅ AutoGen successfully removed and replaced with custom implementation
```

## 🎯 Key Advantages

### 1. **Precise Flow Control**
- Exact definition of agent connections
- Clear start and end points
- Conditional flow based on content or status
- Loop prevention and cycle detection

### 2. **Multi-Provider LLM Support**
- Different LLM providers per agent (OpenAI, Anthropic, Google, Azure)
- Cost optimization through provider selection
- Model-specific configurations

### 3. **Comprehensive Validation**
- JSON Schema compliance checking
- Flow analysis and reachability
- Structural validation
- Performance recommendations

### 4. **Template Independence**
- Works with any project template
- No runtime dependencies on templates
- Complete workflow isolation

### 5. **Human-in-the-Loop**
- Explicit human interaction points
- Conditional human input modes
- Interactive approval flows

## 🔄 Migration from AutoGen

### What Was Removed
- ✅ All AutoGen Python packages (`pyautogen`, `autogen-*`)
- ✅ AutoGen-specific code generation
- ✅ AutoGen team configurations
- ✅ AutoGen execution dependencies
- ✅ Docker sandbox requirements

### What Was Added
- ✅ Custom JSON schema definition
- ✅ Python validation framework
- ✅ Flow analysis engine
- ✅ Programmatic workflow builder
- ✅ Comprehensive testing suite

### Compatibility
- ✅ All existing API endpoints maintained
- ✅ Database models unchanged
- ✅ Frontend integration compatible
- ✅ Template system unaffected

## 🚀 Future Development

### Phase 1: Execution Engine
- Custom agent orchestration implementation
- Real-time message passing
- State management and persistence

### Phase 2: Advanced Features
- Dynamic agent creation
- Workflow templates
- Performance optimization
- Monitoring and analytics

### Phase 3: UI Enhancements
- Visual workflow designer updates
- Schema-aware form validation
- Real-time flow preview
- Interactive debugging

## 📖 Schema Documentation

The complete JSON schema is defined in `agent_workflow_schema.json` and includes:

- **$schema**: JSON Schema version compliance
- **$defs**: Reusable schema definitions
- **Properties**: All workflow properties with validation rules
- **Required Fields**: Mandatory workflow elements
- **Validation Rules**: Data type and format requirements

For detailed schema reference, see the JSON schema file and inline documentation.

---

## ✨ Summary

Our custom AICC Agent Workflow Schema System provides:

🎯 **Complete Control** over agent orchestration
📋 **Clear Documentation** of workflow structure and flow
🔍 **Comprehensive Validation** with detailed error reporting
🚀 **Template Independence** aligned with our architecture
🤖 **Multi-Provider Support** for cost-optimized AI
👥 **Human Integration** for interactive workflows
📊 **Flow Analysis** for optimization and debugging

**This system completely replaces AutoGen** while providing superior control, validation, and integration with our Template Independence Platform.
