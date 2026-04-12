"""
AI Workflow Generator — builds agent orchestration workflows from natural language.
Uses LLM tool-calling to create nodes, configure agents, and connect them.
"""
import uuid
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Tool definitions for the LLM ──────────────────────────────────────

WORKFLOW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_start_node",
            "description": "Add the workflow start node. Every workflow MUST begin with exactly one start node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The initial prompt/question that kicks off the workflow"
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of what this workflow does"
                    }
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_assistant_agent",
            "description": "Add an AI Assistant agent. This is the core agent type that processes tasks using an LLM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique descriptive name (e.g. 'Research Analyst', 'Summarizer')"
                    },
                    "system_message": {
                        "type": "string",
                        "description": "Detailed role instructions for this agent"
                    },
                    "llm_provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "google"],
                        "description": "LLM provider (default: openai)"
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "Model name (default: gpt-4o)"
                    },
                    "documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document filenames this agent should analyze. Only include if the agent needs document access. Auto-enables doc_tool_calling."
                    },
                    "doc_tool_calling": {
                        "type": "boolean",
                        "description": "Enable document analysis via tool calls. Auto-set to true when documents are specified."
                    },
                    "plan_mode": {
                        "type": "boolean",
                        "description": "Agent plans before executing tools (default: true)"
                    },
                    "doc_aware": {
                        "type": "boolean",
                        "description": "Enable RAG search over project documents (default: false)"
                    },
                    "web_search_enabled": {
                        "type": "boolean",
                        "description": "Enable web search capabilities (default: false)"
                    },
                    "web_search_max_results": {
                        "type": "integer",
                        "description": "Maximum number of web search results per query (default: 5, range: 1-20)"
                    },
                    "temperature": {
                        "type": "number",
                        "description": "LLM temperature 0-2 (default: 0.7)"
                    }
                },
                "required": ["name", "system_message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_user_proxy_agent",
            "description": "Add a human-in-the-loop agent that pauses the workflow and waits for user input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Descriptive name (e.g. 'User Review', 'Human Feedback')"
                    },
                    "description": {
                        "type": "string",
                        "description": "What input is needed from the user"
                    },
                    "input_mode": {
                        "type": "string",
                        "enum": ["user", "admin"],
                        "description": "'user' for end-user in deployment, 'admin' for admin in UI (default: user)"
                    },
                    "require_human_input": {
                        "type": "boolean",
                        "description": "Whether to actually pause for input (default: true)"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_group_chat_manager",
            "description": "Add a Group Chat Manager that coordinates multiple delegate agents. Use when you need specialized sub-agents working together on a complex task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Descriptive name (e.g. 'Research Coordinator')"
                    },
                    "system_message": {
                        "type": "string",
                        "description": "Instructions for how to coordinate delegates"
                    }
                },
                "required": ["name", "system_message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_delegate_agent",
            "description": "Add a delegate agent that works under a Group Chat Manager. MUST be connected to a GroupChatManager.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Descriptive name (e.g. 'Legal Expert', 'Technical Reviewer')"
                    },
                    "system_message": {
                        "type": "string",
                        "description": "Specialized role instructions"
                    },
                    "llm_provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "google"],
                        "description": "LLM provider (default: openai)"
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "Model name (default: gpt-4o)"
                    },
                    "documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document filenames this delegate should analyze. Auto-enables doc_tool_calling."
                    },
                    "doc_tool_calling": {
                        "type": "boolean",
                        "description": "Enable document analysis. Auto-set when documents specified."
                    },
                    "plan_mode": {
                        "type": "boolean",
                        "description": "Plan before executing tools (default: true)"
                    },
                    "manager_name": {
                        "type": "string",
                        "description": "Name of the GroupChatManager this delegate belongs to"
                    }
                },
                "required": ["name", "system_message", "manager_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_end_node",
            "description": "Add the workflow end node. Every workflow MUST end with exactly one end node. The end node can only receive ONE incoming connection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Optional description of the expected output"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "connect_nodes",
            "description": "Create a connection between two nodes. Connections define the execution flow. DelegateAgent ↔ GroupChatManager connections are auto-typed as 'delegate'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {
                        "type": "string",
                        "description": "Name of the source node"
                    },
                    "target_name": {
                        "type": "string",
                        "description": "Name of the target node"
                    },
                    "edge_type": {
                        "type": "string",
                        "enum": ["sequential", "reflection"],
                        "description": "Connection type (default: sequential)"
                    }
                },
                "required": ["source_name", "target_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_node_property",
            "description": "Update properties of an EXISTING agent in the current workflow. Use this to modify system_message, name, model, temperature, documents, or any other setting without rebuilding the entire workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the existing node to update"
                    },
                    "properties": {
                        "type": "object",
                        "description": "Properties to update — keys are property names (system_message, llm_model, temperature, documents, web_search_enabled, web_search_max_results, doc_tool_calling, etc.), values are new values. Only specified keys are changed; everything else stays the same.",
                        "additionalProperties": True
                    }
                },
                "required": ["node_name", "properties"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_node",
            "description": "Remove an existing agent from the workflow. Also removes all connections to/from this node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the node to delete"
                    }
                },
                "required": ["node_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clear_all_agents",
            "description": "Remove ALL agents from the workflow, keeping only StartNode and EndNode. Use when the user wants to start fresh, delete everything, or completely rebuild the workflow.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]

SYSTEM_PROMPT = """You are an AI workflow architect. You design multi-agent orchestration workflows.

You have tools to create, connect, update, and delete agents on a visual canvas. Your job is to translate user requirements into a working agent graph.

═══════════════════════════════════════════════════════════
STRUCTURAL RULES
═══════════════════════════════════════════════════════════

• Exactly ONE StartNode and ONE EndNode per workflow.
• EndNode accepts exactly ONE incoming connection. If multiple agents produce output, funnel them through a single aggregator/synthesis agent before EndNode.
• StartNode has only outgoing connections. Nothing connects into it.
• Every agent must be reachable from StartNode and must have a path to EndNode.
• No orphan nodes. No self-connections.

═══════════════════════════════════════════════════════════
AGENT TYPES — WHEN TO USE EACH
═══════════════════════════════════════════════════════════

AssistantAgent:
  The general-purpose LLM agent. Use for any task: analysis, writing, research, coding, summarization, comparison, etc. Give it a clear, specific system_message and a descriptive name that reflects its role.

UserProxyAgent:
  Pauses execution and waits for human input. Use when the user needs to review, approve, provide feedback, or make a decision mid-workflow.

GroupChatManager + DelegateAgent:
  For coordinated specialist teams. The manager delegates sub-tasks to specialist delegates. Delegates can ONLY connect to their GroupChatManager. Use when you need internal sub-orchestration within a larger workflow.

═══════════════════════════════════════════════════════════
EXECUTION PATTERNS — CHOOSE BASED ON REQUIREMENTS
═══════════════════════════════════════════════════════════

SEQUENTIAL: A → B → C
  Each agent processes one after another. Use when tasks depend on prior results.

PARALLEL (fan-out): Source → [A, B, C] (all execute simultaneously)
  Connect the same source to multiple targets. Use when independent tasks can run concurrently.

FAN-IN (aggregation): [A, B, C] → Aggregator
  Connect multiple sources to one target. The target receives all their outputs. Use to combine results from parallel agents.

FAN-OUT/FAN-IN: Source → [A, B, C] → Aggregator → End
  The most common pattern for parallel research/analysis. Source dispatches, agents work in parallel, aggregator synthesizes.

PIPELINE WITH REVIEW: A → B → Human → C → End
  Insert a UserProxyAgent wherever human judgment is needed.

Choose the pattern that best fits the user's requirements. Complex workflows may combine multiple patterns.

═══════════════════════════════════════════════════════════
AGENT CAPABILITIES — TOGGLES AND DEPENDENCIES
═══════════════════════════════════════════════════════════

doc_tool_calling (master toggle):
  Enables document analysis and search features. Required for:
  • documents — assign specific project files for the agent to read
  • doc_aware — RAG vector search over project documents
  • web_search_enabled — real-time internet search
  • plan_mode — agent plans before executing tool calls (default: on)

  When you set documents=[...] or web_search_enabled=true, doc_tool_calling auto-enables.

web_search_max_results: 1-20 (default 5). Set higher for broad research tasks.

file_attachments: Independent of doc_tool_calling. For direct LLM file access.

═══════════════════════════════════════════════════════════
MODIFYING EXISTING WORKFLOWS
═══════════════════════════════════════════════════════════

When a current workflow is shown, use targeted modifications:
• update_node_property — change a specific agent's settings
• delete_node — remove one agent
• clear_all_agents — wipe everything except Start/End (for "start over" requests)
• add_* + connect_nodes — add new agents to existing workflow

Only rebuild what the user asked to change.

═══════════════════════════════════════════════════════════
AVAILABLE LLM MODELS (configured for this project)
═══════════════════════════════════════════════════════════

{available_models_section}

═══════════════════════════════════════════════════════════
YOUR PROCESS — FOLLOW THESE 3 PHASES
═══════════════════════════════════════════════════════════

PHASE 1 — PLAN (text only, no tool calls):
  Read the user's requirements carefully. Then output a structured plan:
  • Agent count, names, and roles
  • Execution pattern (sequential / parallel / fan-out-fan-in / delegation)
  • Flow diagram using arrows: Start → [A, B] → C → End
  • Per-agent capabilities: which need web_search, documents, doc_aware
  • Which single agent connects to EndNode

PHASE 2 — BUILD (all tool calls in one response):
  Execute your plan from Phase 1. Create all nodes, then all connections.
  Write detailed system_message for every agent — describe exactly what it does,
  what input it receives, what output it should produce, and any constraints.

PHASE 3 — VERIFY (text):
  Confirm the graph matches your plan. Note any issues.

GUIDELINES:
• Aim for 3-10 agents. More agents doesn't mean better — each agent can handle complex tasks internally.
• Give agents descriptive names that reflect their function.
• Write system_messages that are specific, actionable, and include output format expectations.
• Only enable web_search or doc_tool_calling when the task genuinely requires it.
• For the StartNode prompt, capture the user's core objective clearly."""


# ── Tool call executor ─────────────────────────────────────────────────

class WorkflowBuilder:
    """Executes LLM tool calls to build a graph_json structure."""

    def __init__(self):
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.node_name_map: Dict[str, str] = {}  # name → node_id
        self.tool_calls_log: List[Dict[str, Any]] = []

    def load_existing_graph(self, graph: Dict[str, Any]):
        """Load an existing workflow graph into the builder for modification. Deduplicates Start/End nodes."""
        import copy
        seen_start = False
        seen_end = False
        skipped = 0
        for node in graph.get("nodes", []):
            ntype = node.get("type", "")
            # Keep only the first StartNode and first EndNode
            if ntype == "StartNode":
                if seen_start:
                    skipped += 1
                    continue
                seen_start = True
            elif ntype == "EndNode":
                if seen_end:
                    skipped += 1
                    continue
                seen_end = True
            n = copy.deepcopy(node)
            self.nodes.append(n)
            name = n.get("data", {}).get("name", "")
            if name:
                self.node_name_map[name] = n["id"]

        kept_ids = {n["id"] for n in self.nodes}
        for edge in graph.get("edges", []):
            # Only load edges whose source and target are both kept
            if edge.get("source") in kept_ids and edge.get("target") in kept_ids:
                self.edges.append(copy.deepcopy(edge))

        if skipped:
            logger.info(f"🔧 WORKFLOW GEN: Deduplicated {skipped} duplicate Start/End node(s) during load")
        logger.info(f"📂 WORKFLOW GEN: Loaded existing graph — {len(self.nodes)} nodes, {len(self.edges)} edges")

    def execute_tool_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a single tool call and return a result message."""
        self.tool_calls_log.append({"tool": tool_name, "args": args})

        handler = {
            "add_start_node": self._add_start_node,
            "add_assistant_agent": self._add_assistant_agent,
            "add_user_proxy_agent": self._add_user_proxy_agent,
            "add_group_chat_manager": self._add_group_chat_manager,
            "add_delegate_agent": self._add_delegate_agent,
            "add_end_node": self._add_end_node,
            "connect_nodes": self._connect_nodes,
            "update_node_property": self._update_node_property,
            "delete_node": self._delete_node,
            "clear_all_agents": self._clear_all_agents,
        }.get(tool_name)

        if not handler:
            return f"Unknown tool: {tool_name}"
        try:
            return handler(args)
        except Exception as e:
            return f"Error: {e}"

    # ── Helpers ──

    @staticmethod
    def _resolve_toggle_dependencies(args: Dict) -> Dict:
        """Enforce toggle dependency chain: doc_tool_calling → doc_aware, web_search, plan_mode."""
        has_docs = bool(args.get("documents"))
        doc_tool_calling = has_docs or args.get("doc_tool_calling", False)
        web_search = args.get("web_search_enabled", False)
        doc_aware = args.get("doc_aware", False)

        # web_search and doc_aware force-enable doc_tool_calling
        if web_search or doc_aware:
            doc_tool_calling = True

        # If doc_tool_calling is off, cascade-disable dependents
        if not doc_tool_calling:
            web_search = False
            doc_aware = False

        return {
            "doc_tool_calling": doc_tool_calling,
            "doc_tool_calling_documents": args.get("documents", []),
            "plan_mode": args.get("plan_mode", True) if doc_tool_calling else False,
            "doc_aware": doc_aware,
            "search_method": "hybrid_search" if doc_aware else "",
            "vector_collections": ["project_documents"] if doc_aware else [],
            "web_search_enabled": web_search,
            "web_search_mode": "general" if web_search else "",
            "web_search_cache_ttl": 2592000 if web_search else 0,
            "web_search_max_results": min(max(args.get("web_search_max_results", 5), 1), 20) if web_search else 0,
            "web_search_urls": [],
            "web_search_domains": [],
        }

    # ── Node creators ──

    def _add_start_node(self, args: Dict) -> str:
        # If StartNode already exists, update its prompt instead of creating a duplicate
        existing = next((n for n in self.nodes if n["type"] == "StartNode"), None)
        if existing:
            existing["data"]["prompt"] = args.get("prompt", existing["data"].get("prompt", ""))
            if args.get("description"):
                existing["data"]["description"] = args["description"]
            return f"Updated existing StartNode '{existing['data']['name']}'"

        node_id = str(uuid.uuid4())
        name = "Start 1"
        self.nodes.append({
            "id": node_id,
            "type": "StartNode",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "prompt": args.get("prompt", "Begin the workflow."),
                "description": args.get("description", "Starting point of the workflow"),
            }
        })
        self.node_name_map[name] = node_id
        return f"Added StartNode '{name}'"

    def _add_assistant_agent(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        toggles = self._resolve_toggle_dependencies(args)
        self.nodes.append({
            "id": node_id,
            "type": "AssistantAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "system_message": args.get("system_message", "You are a helpful AI assistant."),
                "description": args.get("description", f"AI assistant: {name}"),
                "llm_provider": args.get("llm_provider", "openai"),
                "llm_model": args.get("llm_model", "gpt-5.3-chat-latest"),
                "llm_config": args.get("llm_model", "gpt-5.3-chat-latest"),
                **toggles,
                "file_attachments_enabled": False,
                "file_attachment_documents": [],
                "inline_file_attachments": [],
                "temperature": args.get("temperature", 0.7),
            }
        })
        self.node_name_map[name] = node_id
        return f"Added AssistantAgent '{name}'"

    def _add_user_proxy_agent(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        self.nodes.append({
            "id": node_id,
            "type": "UserProxyAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "description": args.get("description", "USER INPUT REQUIRED"),
                "require_human_input": args.get("require_human_input", True),
                "input_mode": args.get("input_mode", "user"),
                "code_execution_enabled": False,
                "system_message": "",
                "llm_provider": "openai",
                "llm_model": "gpt-5.3-chat-latest",
                "doc_aware": False,
                "file_attachments_enabled": False,
                "file_attachment_documents": [],
                "inline_file_attachments": [],
                "web_search_enabled": False,
            }
        })
        self.node_name_map[name] = node_id
        return f"Added UserProxyAgent '{name}'"

    def _add_group_chat_manager(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        self.nodes.append({
            "id": node_id,
            "type": "GroupChatManager",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "description": f"Coordinates specialist delegates: {name}",
                "system_message": args.get("system_message", "You are a Group Chat Manager."),
                "delegate_connections": [],
                "llm_provider": "openai",
                "llm_model": "gpt-5.3-chat-latest",
                "temperature": 0.7,
            }
        })
        self.node_name_map[name] = node_id
        return f"Added GroupChatManager '{name}'"

    def _add_delegate_agent(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        toggles = self._resolve_toggle_dependencies(args)
        self.nodes.append({
            "id": node_id,
            "type": "DelegateAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "system_message": args.get("system_message", "You are a specialized delegate."),
                "description": f"Delegate: {name}",
                "llm_provider": args.get("llm_provider", "openai"),
                "llm_model": args.get("llm_model", "gpt-5.3-chat-latest"),
                "llm_config": args.get("llm_model", "gpt-5.3-chat-latest"),
                **toggles,
                "file_attachments_enabled": False,
                "file_attachment_documents": [],
                "inline_file_attachments": [],
                "can_only_connect_to": "GroupChatManager",
            }
        })
        self.node_name_map[name] = node_id
        # Auto-connect to manager
        manager_name = args.get("manager_name", "")
        if manager_name and manager_name in self.node_name_map:
            manager_id = self.node_name_map[manager_name]
            self.edges.append({
                "id": f"{manager_id}-{node_id}",
                "source": manager_id,
                "target": node_id,
                "type": "delegate",
                "label": "", "description": "", "condition": "",
                "priority": 1, "retryCount": 0, "timeout": 30,
            })
        return f"Added DelegateAgent '{name}'" + (f" (connected to {manager_name})" if manager_name else "")

    def _add_end_node(self, args: Dict) -> str:
        # If EndNode already exists, update it instead of creating a duplicate
        existing = next((n for n in self.nodes if n["type"] == "EndNode"), None)
        if existing:
            if args.get("description"):
                existing["data"]["description"] = args["description"]
            return f"Updated existing EndNode '{existing['data']['name']}'"

        node_id = str(uuid.uuid4())
        name = "End 1"
        self.nodes.append({
            "id": node_id,
            "type": "EndNode",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "description": args.get("description", "Workflow termination and result collection"),
                "output_format": "summary",
                "collect_results": True,
            }
        })
        self.node_name_map[name] = node_id
        return f"Added EndNode '{name}'"

    # ── Connection creator ──

    def _connect_nodes(self, args: Dict) -> str:
        source_name = args["source_name"]
        target_name = args["target_name"]
        edge_type = args.get("edge_type", "sequential")

        source_id = self.node_name_map.get(source_name)
        target_id = self.node_name_map.get(target_name)

        if not source_id:
            return f"Error: source node '{source_name}' not found"
        if not target_id:
            return f"Error: target node '{target_name}' not found"
        if source_id == target_id:
            return f"Error: cannot connect a node to itself ('{source_name}')"

        # Auto-detect delegate type
        source_type = next((n["type"] for n in self.nodes if n["id"] == source_id), "")
        target_type = next((n["type"] for n in self.nodes if n["id"] == target_id), "")
        if (source_type == "GroupChatManager" and target_type == "DelegateAgent") or \
           (source_type == "DelegateAgent" and target_type == "GroupChatManager"):
            edge_type = "delegate"

        # Check duplicate
        edge_id = f"{source_id}-{target_id}"
        if any(e["id"] == edge_id for e in self.edges):
            return f"Connection already exists: {source_name} → {target_name}"

        self.edges.append({
            "id": edge_id,
            "source": source_id,
            "target": target_id,
            "type": edge_type,
            "label": "", "description": "", "condition": "",
            "priority": 1, "retryCount": 0, "timeout": 30,
        })
        return f"Connected '{source_name}' → '{target_name}' ({edge_type})"

    # ── Update / Delete ──

    def _update_node_property(self, args: Dict) -> str:
        node_name = args.get("node_name", "")
        properties = args.get("properties", {})

        if not node_name or not properties:
            return "Error: node_name and properties are required"

        node_id = self.node_name_map.get(node_name)
        if not node_id:
            return f"Error: node '{node_name}' not found. Available: {', '.join(self.node_name_map.keys())}"

        node = next((n for n in self.nodes if n["id"] == node_id), None)
        if not node:
            return f"Error: node '{node_name}' not found in nodes list"

        # Handle 'documents' shortcut → sets doc_tool_calling_documents + auto-enables
        if "documents" in properties:
            docs = properties.pop("documents")
            properties["doc_tool_calling_documents"] = docs
            if docs:
                properties["doc_tool_calling"] = True

        # Apply toggle dependencies if any toggle-related props are updated
        toggle_keys = {"doc_tool_calling", "web_search_enabled", "doc_aware", "web_search_max_results"}
        if toggle_keys & set(properties.keys()):
            merged = {**node["data"], **properties}
            resolved = self._resolve_toggle_dependencies(merged)
            properties.update(resolved)

        # Merge into node data
        updated_keys = []
        for key, value in properties.items():
            node["data"][key] = value
            updated_keys.append(key)

        # Handle name change → update node_name_map
        if "name" in properties and properties["name"] != node_name:
            new_name = properties["name"]
            del self.node_name_map[node_name]
            self.node_name_map[new_name] = node_id

        return f"Updated '{node_name}': {', '.join(updated_keys)}"

    def _delete_node(self, args: Dict) -> str:
        node_name = args.get("node_name", "")
        if not node_name:
            return "Error: node_name is required"

        node_id = self.node_name_map.get(node_name)
        if not node_id:
            return f"Error: node '{node_name}' not found. Available: {', '.join(self.node_name_map.keys())}"

        # Prevent deleting Start/End nodes
        node = next((n for n in self.nodes if n["id"] == node_id), None)
        if node and node.get("type") in ("StartNode", "EndNode"):
            return f"Error: Cannot delete {node['type']} — every workflow must have exactly one"

        # Remove node
        self.nodes = [n for n in self.nodes if n["id"] != node_id]
        del self.node_name_map[node_name]

        # Cascade-delete edges
        before = len(self.edges)
        self.edges = [e for e in self.edges if e["source"] != node_id and e["target"] != node_id]
        removed_edges = before - len(self.edges)

        return f"Deleted '{node_name}' and {removed_edges} connection(s)"

    def _clear_all_agents(self, args: Dict) -> str:
        """Remove all agents, keeping only ONE StartNode and ONE EndNode. Deduplicates if multiple exist."""
        # Keep only the FIRST StartNode and FIRST EndNode, remove everything else
        first_start = next((n for n in self.nodes if n["type"] == "StartNode"), None)
        first_end = next((n for n in self.nodes if n["type"] == "EndNode"), None)

        removed_names = [
            n["data"].get("name", "?") for n in self.nodes
            if n is not first_start and n is not first_end
        ]

        keep_nodes = []
        if first_start:
            keep_nodes.append(first_start)
        if first_end:
            keep_nodes.append(first_end)

        keep_ids = {n["id"] for n in keep_nodes}
        self.nodes = keep_nodes
        self.edges = [e for e in self.edges if e["source"] in keep_ids and e["target"] in keep_ids]

        # Rebuild name map from scratch
        self.node_name_map = {n["data"]["name"]: n["id"] for n in self.nodes if n["data"].get("name")}

        return f"Cleared {len(removed_names)} node(s): {', '.join(removed_names)}. Kept 1 StartNode + 1 EndNode."

    # ── Auto-layout ──

    def auto_layout(self):
        """Position nodes in a clean left-to-right layout using BFS layers."""
        if not self.nodes:
            return

        # Build adjacency for non-delegate edges
        children: Dict[str, List[str]] = {n["id"]: [] for n in self.nodes}
        parents: Dict[str, List[str]] = {n["id"]: [] for n in self.nodes}
        for e in self.edges:
            if e["type"] != "delegate":
                children.setdefault(e["source"], []).append(e["target"])
                parents.setdefault(e["target"], []).append(e["source"])

        # Find start node (or any root)
        start_ids = [n["id"] for n in self.nodes if n["type"] == "StartNode"]
        if not start_ids:
            start_ids = [n["id"] for n in self.nodes if not parents.get(n["id"])]
        if not start_ids:
            start_ids = [self.nodes[0]["id"]]

        # BFS to assign layers
        layers: Dict[str, int] = {}
        queue = [(sid, 0) for sid in start_ids]
        visited = set()
        while queue:
            nid, layer = queue.pop(0)
            if nid in visited:
                layers[nid] = max(layers.get(nid, 0), layer)
                continue
            visited.add(nid)
            layers[nid] = max(layers.get(nid, 0), layer)
            for child in children.get(nid, []):
                queue.append((child, layer + 1))

        # Assign unvisited nodes (delegates, disconnected)
        for n in self.nodes:
            if n["id"] not in layers:
                # Delegates: place next to their manager
                if n["type"] == "DelegateAgent":
                    for e in self.edges:
                        if e["type"] == "delegate" and e["target"] == n["id"]:
                            manager_layer = layers.get(e["source"], 1)
                            layers[n["id"]] = manager_layer
                            break
                    else:
                        layers[n["id"]] = 1
                else:
                    layers[n["id"]] = max(layers.values(), default=0) + 1

        # Force EndNode to the last layer (rightmost position)
        max_layer = max(layers.values(), default=0)
        for n in self.nodes:
            if n["type"] == "EndNode":
                layers[n["id"]] = max_layer + 1

        # Group nodes by layer
        layer_groups: Dict[int, List[Dict]] = {}
        for n in self.nodes:
            layer = layers.get(n["id"], 0)
            layer_groups.setdefault(layer, []).append(n)

        # Position: left-to-right (x), centered vertically (y)
        LAYER_SPACING = 350
        NODE_SPACING = 180
        BASE_X = -600

        # Separate delegates — place them below their manager
        for layer_idx in sorted(layer_groups.keys()):
            group = layer_groups[layer_idx]
            main_nodes = [n for n in group if n["type"] != "DelegateAgent"]
            delegate_nodes = [n for n in group if n["type"] == "DelegateAgent"]

            x = BASE_X + layer_idx * LAYER_SPACING

            # Position main nodes
            count = len(main_nodes)
            for i, node in enumerate(main_nodes):
                y = -NODE_SPACING * (count - 1) / 2 + i * NODE_SPACING
                node["position"] = {"x": x, "y": int(y)}

            # Position delegates below their manager
            for i, node in enumerate(delegate_nodes):
                # Find manager position
                manager_y = 0
                for e in self.edges:
                    if e["type"] == "delegate" and e["target"] == node["id"]:
                        manager = next((n for n in self.nodes if n["id"] == e["source"]), None)
                        if manager:
                            manager_y = manager["position"].get("y", 0)
                        break
                node["position"] = {"x": x + 50, "y": int(manager_y + 150 + i * 130)}

    # ── Validation ──

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate the workflow graph."""
        errors = []
        start_nodes = [n for n in self.nodes if n["type"] == "StartNode"]
        end_nodes = [n for n in self.nodes if n["type"] == "EndNode"]

        if len(start_nodes) == 0:
            errors.append("Workflow must have a StartNode")
        if len(start_nodes) > 1:
            errors.append("Workflow should have only one StartNode")
        if len(end_nodes) == 0:
            errors.append("Workflow must have an EndNode")
        if len(end_nodes) > 1:
            errors.append("Workflow should have only one EndNode")

        # EndNode should have exactly 1 incoming edge
        if end_nodes:
            end_id = end_nodes[0]["id"]
            incoming = [e for e in self.edges if e["target"] == end_id]
            if len(incoming) > 1:
                errors.append(f"EndNode has {len(incoming)} incoming connections (max 1)")
            if len(incoming) == 0:
                errors.append("EndNode has no incoming connections")

        # StartNode should have no incoming edges
        if start_nodes:
            start_id = start_nodes[0]["id"]
            start_incoming = [e for e in self.edges if e["target"] == start_id]
            if start_incoming:
                errors.append(f"StartNode has {len(start_incoming)} incoming connections (should have none)")

        # Check for orphan agents (no incoming and no outgoing, excluding Start/End)
        sources = {e["source"] for e in self.edges}
        targets = {e["target"] for e in self.edges}
        for n in self.nodes:
            if n["type"] in ("StartNode", "EndNode", "DelegateAgent"):
                continue
            nid = n["id"]
            if nid not in sources and nid not in targets:
                errors.append(f"Orphan agent '{n['data'].get('name', nid[:8])}' has no connections")

        # DelegateAgents must have delegate edges
        for n in self.nodes:
            if n["type"] == "DelegateAgent":
                has_delegate = any(
                    e["type"] == "delegate" and (e["source"] == n["id"] or e["target"] == n["id"])
                    for e in self.edges
                )
                if not has_delegate:
                    errors.append(f"DelegateAgent '{n['data'].get('name', '')}' is not connected to a GroupChatManager")

        return len(errors) == 0, errors

    def build_graph_json(self) -> Dict[str, Any]:
        """Return the final graph JSON with StartNode first and EndNode last."""
        self.auto_layout()
        # Sort: StartNode first, EndNode last, everything else in middle
        type_order = {"StartNode": 0, "EndNode": 2}
        sorted_nodes = sorted(self.nodes, key=lambda n: type_order.get(n["type"], 1))
        return {
            "nodes": sorted_nodes,
            "edges": self.edges,
        }


def _auto_repair_connections(builder: WorkflowBuilder):
    """
    Fix common connection issues the LLM misses:
    0. Unconnected DelegateAgents → connect to their manager
    1. EndNode has no incoming → connect the last non-End non-Start agent
    2. Agents with no outgoing → connect to the next agent or EndNode
    3. Agents with no incoming → connect from StartNode or previous agent
    """
    if not builder.nodes or len(builder.nodes) < 2:
        return

    node_ids = {n["id"] for n in builder.nodes}
    sources = {e["source"] for e in builder.edges}
    targets = {e["target"] for e in builder.edges}

    start = next((n for n in builder.nodes if n["type"] == "StartNode"), None)
    end = next((n for n in builder.nodes if n["type"] == "EndNode"), None)
    agents = [n for n in builder.nodes if n["type"] not in ("StartNode", "EndNode", "DelegateAgent")]

    if not start:
        return

    # Auto-create missing EndNode
    if not end:
        import uuid as _uuid
        end_id = str(_uuid.uuid4())
        end = {
            "id": end_id, "type": "EndNode", "position": {"x": 0, "y": 0},
            "data": {"name": "End 1", "description": "Workflow termination", "output_format": "summary", "collect_results": True}
        }
        builder.nodes.append(end)
        builder.node_name_map["End 1"] = end_id
        logger.info("🔧 AUTO-REPAIR: Created missing EndNode")

    # Fix 0: Connect unconnected DelegateAgents to their managers
    delegates = [n for n in builder.nodes if n["type"] == "DelegateAgent"]
    managers = {n["data"]["name"]: n["id"] for n in builder.nodes if n["type"] == "GroupChatManager"}
    for d in delegates:
        d_id = d["id"]
        has_delegate_edge = any(
            e["type"] == "delegate" and (e["source"] == d_id or e["target"] == d_id)
            for e in builder.edges
        )
        if not has_delegate_edge and managers:
            # Try to find manager by checking node data or use the first manager
            manager_id = next(iter(managers.values()))
            edge_id = f"{manager_id}-{d_id}"
            if not any(e["id"] == edge_id for e in builder.edges):
                builder.edges.append({
                    "id": edge_id, "source": manager_id, "target": d_id, "type": "delegate",
                    "label": "", "description": "", "condition": "",
                    "priority": 1, "retryCount": 0, "timeout": 30,
                })
                logger.info(f"🔧 AUTO-REPAIR: Connected DelegateAgent '{d['data']['name']}' to GroupChatManager")

    def _add_edge(src_id, tgt_id, etype="sequential"):
        edge_id = f"{src_id}-{tgt_id}"
        if not any(e["id"] == edge_id for e in builder.edges):
            builder.edges.append({
                "id": edge_id, "source": src_id, "target": tgt_id, "type": etype,
                "label": "", "description": "", "condition": "",
                "priority": 1, "retryCount": 0, "timeout": 30,
            })
            logger.info(f"🔧 AUTO-REPAIR: Added edge {edge_id}")
            return True
        return False

    # Fix 1: StartNode has no outgoing → connect to agents with no incoming
    if start["id"] not in sources and agents:
        for a in agents:
            if a["id"] not in targets:
                _add_edge(start["id"], a["id"])

    # Refresh
    sources = {e["source"] for e in builder.edges}
    targets = {e["target"] for e in builder.edges}

    # Fix 2: Agents with no outgoing → connect to the last agent or EndNode
    # Strategy: find agents that are "sinks" (no outgoing) and connect them forward
    # The last agent in the list is likely the synthesizer/final agent
    last_agent = agents[-1] if agents else None
    for a in agents:
        if a["id"] not in sources:
            if a == last_agent:
                # Last agent connects to EndNode
                _add_edge(a["id"], end["id"])
            else:
                # Earlier agents with no outgoing → connect to last agent
                _add_edge(a["id"], last_agent["id"])

    # Fix 3: Agents with outgoing but NO incoming (unreachable) → connect from sibling's source or StartNode
    sources = {e["source"] for e in builder.edges}
    targets = {e["target"] for e in builder.edges}
    for a in agents:
        a_id = a["id"]
        has_incoming = a_id in targets
        if not has_incoming and a_id != start["id"]:
            # Find where this agent's output goes (its target)
            a_targets = [e["target"] for e in builder.edges if e["source"] == a_id]
            # Find siblings: other agents that also connect to the same target
            sibling_source = None
            for t in a_targets:
                for e in builder.edges:
                    if e["target"] == t and e["source"] != a_id:
                        # This is a sibling — find who feeds that sibling
                        for e2 in builder.edges:
                            if e2["target"] == e["source"] and e2["source"] != a_id:
                                sibling_source = e2["source"]
                                break
                        if not sibling_source:
                            sibling_source = e["source"]
                    if sibling_source:
                        break
                if sibling_source:
                    break
            if sibling_source:
                _add_edge(sibling_source, a_id)
                logger.info(f"🔧 AUTO-REPAIR: Connected unreachable '{a['data'].get('name', '?')}' from sibling's source")
            else:
                _add_edge(start["id"], a_id)
                logger.info(f"🔧 AUTO-REPAIR: Connected unreachable '{a['data'].get('name', '?')}' from StartNode")

    # Fix 4: EndNode still has no incoming → connect from last agent
    end_incoming = [e for e in builder.edges if e["target"] == end["id"]]
    if len(end_incoming) == 0 and last_agent:
        _add_edge(last_agent["id"], end["id"])

    # Fix 5: EndNode has multiple incoming (>1) → keep only the last one
    end_incoming = [e for e in builder.edges if e["target"] == end["id"]]
    if len(end_incoming) > 1:
        keep_source = last_agent["id"] if last_agent else end_incoming[-1]["source"]
        edges_to_remove = [e for e in end_incoming if e["source"] != keep_source]
        for e in edges_to_remove:
            builder.edges.remove(e)
            logger.info(f"🔧 AUTO-REPAIR: Removed extra EndNode edge {e['id']}")


# ── Main generator function ────────────────────────────────────────────

async def generate_workflow(
    project,
    user_message: str,
    conversation_history: Optional[List[Dict]] = None,
    current_graph: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a workflow from natural language requirements.

    Args:
        project: IntelliDocProject instance
        user_message: The user's requirements
        conversation_history: Previous messages in the conversation

    Returns:
        {graph_json, explanation, tool_calls, errors}
    """
    from .llm_provider_manager import LLMProviderManager

    # Get LLM provider using project API keys
    provider_manager = LLMProviderManager()
    agent_config = {"llm_provider": "openai", "llm_model": "gpt-5.3-chat-latest"}

    llm_provider = await provider_manager.get_llm_provider(agent_config, project)
    if not llm_provider:
        return {
            "graph_json": None,
            "explanation": "No LLM provider available. Please configure API keys in API Management.",
            "tool_calls": [],
            "errors": ["No LLM provider available"],
        }

    # Detect which LLM providers have API keys configured for this project
    from asgiref.sync import sync_to_async

    available_models_lines = []
    provider_models = {
        "openai": "gpt-5.3-chat-latest (recommended), gpt-4o, gpt-4o-mini, o3-mini",
        "anthropic": "claude-sonnet-4-20250514, claude-3-5-haiku-20241022",
        "google": "gemini-2.5-flash, gemini-2.0-flash",
    }
    try:
        from project_api_keys.services import ProjectAPIKeyService
        key_service = ProjectAPIKeyService()
        for provider_name, models_str in provider_models.items():
            key = await sync_to_async(key_service.get_project_api_key)(project, provider_name)
            if key:
                label = provider_name.capitalize()
                if provider_name == "openai":
                    label = "OpenAI"
                available_models_lines.append(f"- {label}: {models_str}")
    except Exception as e:
        logger.warning(f"⚠️ WORKFLOW GEN: Could not check API keys: {e}")
        # Fallback: show all providers
        for provider_name, models_str in provider_models.items():
            available_models_lines.append(f"- {provider_name.capitalize()}: {models_str}")

    if not available_models_lines:
        available_models_lines.append("No LLM providers configured. Use openai as default.")

    available_models_section = "\n".join(available_models_lines)

    # Fetch project documents + summaries for the LLM to make selection decisions
    from users.models import ProjectDocument

    project_docs = await sync_to_async(list)(
        ProjectDocument.objects.filter(
            project=project, upload_status__in=("completed", "ready")
        ).select_related("document_summary").order_by("original_filename")
    )

    doc_listing = ""
    if project_docs:
        doc_lines = []
        for i, doc in enumerate(project_docs, 1):
            summary_text = ""
            try:
                s = doc.document_summary
                title = ""
                if hasattr(s, 'citation') and isinstance(s.citation, dict) and s.citation.get('title'):
                    title = f'[{s.citation["title"]}] '
                summary_text = f"{title}{s.short_summary[:200]}" if s.short_summary else "(no summary)"
            except Exception:
                summary_text = "(no summary available)"
            doc_lines.append(f'{i}. "{doc.original_filename}" — {summary_text}')
        doc_listing = (
            "\n\nAVAILABLE PROJECT DOCUMENTS:\n"
            + "\n".join(doc_lines)
            + "\n\nWhen creating agents that need document access, use the `documents` parameter "
            "with the exact filenames from the list above. Only assign documents relevant to each agent's task."
        )

    # Build current workflow description (if modifying an existing workflow)
    current_workflow_section = ""
    if current_graph and current_graph.get("nodes"):
        cw_nodes = current_graph["nodes"]
        cw_edges = current_graph.get("edges", [])
        node_id_to_name = {n["id"]: n.get("data", {}).get("name", n["id"][:8]) for n in cw_nodes}
        cw_lines = [f"\n\nCURRENT WORKFLOW ON CANVAS ({len(cw_nodes)} nodes, {len(cw_edges)} connections):"]
        cw_lines.append("Nodes:")
        for n in cw_nodes:
            d = n.get("data", {})
            line = f'  - {n["type"]}: "{d.get("name", "?")}"'
            docs = d.get("doc_tool_calling_documents", [])
            if docs:
                line += f" [documents: {', '.join(docs)}]"
            if d.get("web_search_enabled"):
                line += " [web_search]"
            cw_lines.append(line)
        cw_lines.append("Connections:")
        for e in cw_edges:
            src = node_id_to_name.get(e["source"], "?")
            tgt = node_id_to_name.get(e["target"], "?")
            cw_lines.append(f"  - {src} → {tgt} ({e.get('type', 'sequential')})")
        cw_lines.append("")
        cw_lines.append("The user wants to MODIFY this existing workflow. You should rebuild it with the requested changes.")
        cw_lines.append("Recreate all nodes and connections, keeping existing agents that don't need changes and adding/removing/modifying as requested.")
        current_workflow_section = "\n".join(cw_lines)

    # Build messages — fill in dynamic sections
    system_content = SYSTEM_PROMPT.replace("{available_models_section}", available_models_section) + doc_listing + current_workflow_section
    messages = [{"role": "system", "content": system_content}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    # Call LLM with tools
    builder = WorkflowBuilder()
    if current_graph and current_graph.get("nodes"):
        builder.load_existing_graph(current_graph)
    max_iterations = 10  # Allow multiple rounds of tool calls

    explanation = ""

    for iteration in range(max_iterations):
        response = await llm_provider.generate_response(
            messages=messages,
            tools=WORKFLOW_TOOLS,
        )

        if response.error:
            return {
                "graph_json": None,
                "explanation": f"LLM error: {response.error}",
                "tool_calls": builder.tool_calls_log,
                "errors": [response.error],
            }

        # Collect text response
        if response.text:
            explanation += response.text

        # Process tool calls
        if not response.tool_calls:
            break  # LLM is done

        # Record assistant message with tool calls (ensure OpenAI format)
        formatted_tool_calls = []
        for tc in response.tool_calls:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", tc.get("arguments", "{}"))
            # OpenAI requires arguments as JSON string, not dict
            args_str = json.dumps(raw_args) if isinstance(raw_args, dict) else str(raw_args)
            formatted_tool_calls.append({
                "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                "type": "function",
                "function": {
                    "name": fn.get("name", tc.get("name", "")),
                    "arguments": args_str,
                }
            })
        messages.append({
            "role": "assistant",
            "content": response.text or "",
            "tool_calls": formatted_tool_calls,
        })

        # Execute each tool call
        for tc in formatted_tool_calls:
            fn_name = tc["function"]["name"]
            fn_args_raw = tc["function"]["arguments"]
            tc_id = tc["id"]

            try:
                fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
            except json.JSONDecodeError:
                fn_args = {}

            result = builder.execute_tool_call(fn_name, fn_args)
            logger.info(f"🔧 WORKFLOW GEN: {fn_name}({json.dumps(fn_args)[:100]}) → {result}")

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

    # If nodes exist but no edges, explicitly ask the LLM to create connections
    if builder.nodes and not builder.edges:
        node_names = [n["data"]["name"] for n in builder.nodes]
        logger.info(f"⚠️ WORKFLOW GEN: {len(builder.nodes)} nodes but 0 edges — requesting connections")
        messages.append({
            "role": "user",
            "content": (
                f"You created these nodes but forgot to connect them: {', '.join(node_names)}. "
                "Now call connect_nodes for EVERY connection. Remember:\n"
                "- Start 1 must connect to the first agent(s)\n"
                "- Every agent must connect to the next agent(s)\n"
                "- The last agent before the end must connect to End 1\n"
                "- EndNode receives exactly ONE incoming connection\n"
                "Make ALL connect_nodes calls now."
            ),
        })
        for retry_iter in range(3):
            response = await llm_provider.generate_response(messages=messages, tools=WORKFLOW_TOOLS)
            if response.error:
                break
            if response.text:
                explanation += response.text
            if not response.tool_calls:
                break
            formatted_tool_calls = []
            for tc in response.tool_calls:
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", tc.get("arguments", "{}"))
                args_str = json.dumps(raw_args) if isinstance(raw_args, dict) else str(raw_args)
                formatted_tool_calls.append({
                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {"name": fn.get("name", tc.get("name", "")), "arguments": args_str}
                })
            messages.append({"role": "assistant", "content": response.text or "", "tool_calls": formatted_tool_calls})
            for tc in formatted_tool_calls:
                fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                result = builder.execute_tool_call(tc["function"]["name"], fn_args)
                logger.info(f"🔧 WORKFLOW GEN (retry): {tc['function']['name']} → {result}")
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    # Auto-repair: fix common issues the LLM misses
    _auto_repair_connections(builder)

    # Build and validate
    graph_json = builder.build_graph_json()
    is_valid, errors = builder.validate()

    if not is_valid:
        explanation += f"\n\nNote: The generated workflow has validation issues: {', '.join(errors)}"

    return {
        "graph_json": graph_json,
        "explanation": explanation.strip(),
        "tool_calls": builder.tool_calls_log,
        "errors": errors,
    }
