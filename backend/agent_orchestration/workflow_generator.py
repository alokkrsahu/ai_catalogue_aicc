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
                    },
                    "llm_provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "google"],
                        "description": "LLM provider for coordination (default: openai)"
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "Model name for coordination (default: gpt-5.3-chat-latest)"
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
            "name": "add_classifier_agent",
            "description": (
                "Add a ClassifierAgent — a routing node that picks exactly ONE category "
                "from a user-defined list using forced LLM tool-calling, then routes "
                "execution down that branch only. Non-selected branches are pruned at "
                "runtime and never execute. Use for intent triage, language routing, "
                "or any 'which path?' decision. Downstream agents receive the ORIGINAL "
                "input unchanged — the classifier itself produces no content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Descriptive name (e.g. 'Intent Router', 'Ticket Triage')"
                    },
                    "categories": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 10,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Short category label (e.g. 'Billing', 'Bug Report')"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "When to pick this category — guides the LLM's choice"
                                }
                            },
                            "required": ["name"]
                        },
                        "description": "2-10 categories. Each needs a unique name; descriptions are strongly recommended so the classifier LLM picks the right one."
                    },
                    "llm_provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "google"],
                        "description": "LLM provider for classification (default: anthropic)"
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "Model name (default: claude-3-5-haiku-20241022 — fast/cheap works well for routing)"
                    },
                    "temperature": {
                        "type": "number",
                        "description": "LLM temperature 0-2 (default: 0.0 — routers want determinism)"
                    }
                },
                "required": ["name", "categories"]
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
            "description": "Create a connection between two nodes. Connections define the execution flow. DelegateAgent ↔ GroupChatManager connections are auto-typed as 'delegate'. When source is a ClassifierAgent, source_category is REQUIRED.",
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
                    },
                    "source_category": {
                        "type": "string",
                        "description": "REQUIRED when source is a ClassifierAgent — the category NAME this edge represents (matching one of the classifier's category names). The edge fires only when the classifier picks this category."
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
                        "description": "Properties to update — keys are property names (system_message, llm_provider, llm_model, temperature, documents, web_search_enabled, web_search_max_results, doc_tool_calling, doc_aware, plan_mode, etc.), values are new values. Only specified keys are changed; everything else stays the same.",
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
    # ─── Surgical-edit tools (Pillar 3) — prefer these over delete_node + recreate
    {
        "type": "function",
        "function": {
            "name": "delete_edge",
            "description": "Remove a specific edge between two existing agents WITHOUT deleting the agents. For ClassifierAgent sources, pass source_category to disambiguate which branch to remove.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "description": "Source agent name"},
                    "target_name": {"type": "string", "description": "Target agent name"},
                    "source_category": {
                        "type": "string",
                        "description": "REQUIRED when source is a ClassifierAgent and you want to remove only one branch — the category name."
                    }
                },
                "required": ["source_name", "target_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_category",
            "description": "Add ONE new category to an existing ClassifierAgent without re-passing the entire categories array. Use this for incremental category additions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "classifier_name": {"type": "string", "description": "Name of the ClassifierAgent"},
                    "name": {"type": "string", "description": "New category name (must be unique within this classifier)"},
                    "description": {"type": "string", "description": "When to pick this category — guides the LLM's choice"}
                },
                "required": ["classifier_name", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_category",
            "description": "Remove ONE category from an existing ClassifierAgent by name. Also cascade-deletes any outgoing edges that referenced this category. Errors if it would drop the classifier below 2 categories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "classifier_name": {"type": "string", "description": "Name of the ClassifierAgent"},
                    "name": {"type": "string", "description": "Category name to remove"}
                },
                "required": ["classifier_name", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_edge_type",
            "description": "Switch the type of an existing edge between 'sequential' and 'reflection' without recreating the agents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "description": "Source agent name"},
                    "target_name": {"type": "string", "description": "Target agent name"},
                    "new_type": {"type": "string", "enum": ["sequential", "reflection"], "description": "New edge type"}
                },
                "required": ["source_name", "target_name", "new_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rewire_edge",
            "description": "Re-point an existing edge from old_target_name to new_target_name in one atomic call. Equivalent to delete_edge + connect_nodes but cannot half-fail. For ClassifierAgent sources, pass source_category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_name": {"type": "string", "description": "Source agent name"},
                    "old_target_name": {"type": "string", "description": "Current target — the edge to detach"},
                    "new_target_name": {"type": "string", "description": "New target — the edge will point here"},
                    "source_category": {
                        "type": "string",
                        "description": "REQUIRED when source is a ClassifierAgent — the category name whose branch is being rewired."
                    }
                },
                "required": ["source_name", "old_target_name", "new_target_name"]
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
• EndNode accepts exactly ONE incoming connection — EXCEPT when incoming edges all originate from different branches of a ClassifierAgent (because only one branch will reach EndNode at runtime; the others are pruned).
• If multiple non-classifier agents produce output, funnel them through a single aggregator/synthesis agent before EndNode.
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

ClassifierAgent:
  A pure routing/triage node. Receives input, picks EXACTLY ONE of 2-10 user-defined
  categories via forced LLM tool-calling, and routes execution down only that branch.
  Non-selected branches are PRUNED at runtime (their agents never execute).
  Downstream agents receive the ORIGINAL input unchanged — the classifier produces
  no content of its own, it only picks a path. Use for: intent routing ("bug report"
  vs "feature request" vs "billing question"), language branching, triage/escalation,
  any conditional workflow selection. Each category must have a clear name and a
  short description that tells the LLM when to pick it.

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

ROUTING (classifier branches): Start → Classifier → [Cat A → Agent A → End,
                                                     Cat B → Agent B → End,
                                                     Cat C → Agent C → End]
  The Classifier picks exactly ONE branch at runtime; non-selected branches are
  pruned and never execute. When calling connect_nodes to wire a classifier's
  outgoing edges, you MUST pass source_category (the category name). Each
  category should have its own outgoing edge. Different branches may independently
  terminate at EndNode — this is the ONE exception to the "EndNode has exactly
  1 incoming" rule. Use when the user wants conditional/routed workflows.

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

  When you set documents=[...], doc_aware=true, or web_search_enabled=true, doc_tool_calling auto-enables.

DOCUMENT ACCESS — TWO MODES (can be used together):

  documents (File API — targeted full-document access):
    • Assigns specific files from the project for the agent to read in full
    • Best for: analyzing 1-5 specific files, comparing documents side by side,
      extracting structured data from a known file
    • The agent gets the COMPLETE content of each assigned file via tool calls
    • You must specify exact filenames from the available project documents list
    • SHORTCUT: documents=["*"] or documents=["all"] assigns ALL available project
      documents to the agent. Use when the user explicitly asks for "all documents"
      or when the agent genuinely needs broad access to the entire project library —
      avoids having to enumerate every filename and scales to large collections.

  doc_aware (RAG — semantic search across ALL project documents):
    • Enables vector-based semantic chunk search across the entire document collection
    • Best for: answering questions that could be in any document, finding info
      across a large collection (10+ documents), discovering relevant content
      without knowing which file contains it
    • The agent searches by meaning and retrieves the most relevant chunks
    • No need to specify filenames — it searches everything indexed in the project

  WHEN TO USE WHICH:
    • User asks about a specific named file → documents=["that_file.pdf"]
    • User asks a broad question across many docs → doc_aware=true
    • User needs both full file detail AND broad search → use BOTH together
    • Small project with 1-3 docs → documents is usually sufficient
    • Large project with 10+ docs → doc_aware is usually better

web_search_max_results: 1-20 (default 5). Set higher for broad research tasks.

temperature: Controls LLM creativity/randomness (0-2, default 0.7).
  Use lower (0.1-0.3) for factual/analytical tasks, higher (0.8-1.2) for creative tasks.

file_attachments: Independent of doc_tool_calling. For direct LLM file access.

═══════════════════════════════════════════════════════════
MODIFYING EXISTING WORKFLOWS — PRESERVATION IS THE DEFAULT
═══════════════════════════════════════════════════════════

PRESERVATION IS THE DEFAULT. Do NOT delete existing agents unless the user
EXPLICITLY uses words like: "remove", "delete", "rebuild", "replace",
"start over", "wipe", "clear", "from scratch", "redo", "recreate".

When a current workflow is shown:
• ADD or UPDATE in place. New requirements → add new agents and connect them.
  Behavioral changes → update_node_property on the existing agent.
• A long pasted system prompt or specification is NOT permission to delete
  existing structure. Treat it as either:
    (a) A new system_message for an EXISTING agent (use update_node_property),
        when the prompt's role matches an existing agent's role; OR
    (b) The system_message for a NEW agent you add via add_assistant_agent
        and connect into the existing graph.
• If genuinely unsure between modification and rebuild, choose preservation.
  The user can always ask you to "start over" explicitly if they want a fresh build.

Tools for modifications:
• update_node_property — change a specific agent's settings
• delete_node — remove one agent (only when user explicitly asked)
• clear_all_agents — wipe everything except Start/End (only for explicit
  "start over" requests)
• add_* + connect_nodes — add new agents to existing workflow

Surgical edits — PREFER these on existing workflows over delete + recreate:
• delete_edge(source, target [, source_category]) — remove one specific connection
  without deleting the agents.
• add_category(classifier_name, name, description) — add ONE category to an
  existing ClassifierAgent. Don't replace the whole array via update_node_property
  unless the user wants to wipe all categories.
• remove_category(classifier_name, name) — remove ONE category. Cascade-deletes
  branch edges. Errors if it would drop below the 2-category minimum.
• change_edge_type(source, target, new_type) — flip an edge between
  'sequential' and 'reflection'.
• rewire_edge(source, old_target, new_target [, source_category]) — re-point
  an edge atomically. Equivalent to delete_edge + connect_nodes but rolls back
  if the new edge can't be created.

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

    def __init__(self, available_documents: Optional[List[str]] = None):
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.node_name_map: Dict[str, str] = {}  # name → node_id
        self.tool_calls_log: List[Dict[str, Any]] = []
        self.available_documents: List[str] = available_documents or []

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
            "add_classifier_agent": self._add_classifier_agent,
            "add_end_node": self._add_end_node,
            "connect_nodes": self._connect_nodes,
            "update_node_property": self._update_node_property,
            "delete_node": self._delete_node,
            "clear_all_agents": self._clear_all_agents,
            # ── Surgical-edit tools for modifications (Pillar 3) ──
            "delete_edge": self._delete_edge,
            "add_category": self._add_category,
            "remove_category": self._remove_category,
            "change_edge_type": self._change_edge_type,
            "rewire_edge": self._rewire_edge,
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
        # Read from "documents" OR already-stored "doc_tool_calling_documents" so
        # updates via _update_node_property (which pops "documents") don't wipe the list.
        docs_val = args.get("documents") or args.get("doc_tool_calling_documents", [])
        has_docs = bool(docs_val)
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
            "doc_tool_calling_documents": docs_val,
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

    def _expand_documents(self, docs: Any) -> List[str]:
        """Expand wildcard ('*' or 'all') to the full list of available project documents.

        Accepts a list, a single string (auto-wrapped), or falsy (returns []).
        If any element in the list is '*', 'all', or 'ALL' (case-insensitive), returns
        the complete available_documents list. Otherwise passes the list through unchanged.
        """
        if not docs:
            return []
        if isinstance(docs, str):
            docs = [docs]
        if not isinstance(docs, list):
            return []
        if any(isinstance(d, str) and d.strip().lower() in ("*", "all") for d in docs):
            return list(self.available_documents)
        return docs

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
        # Expand wildcard "*"/"all" to full document list before resolving toggles
        if "documents" in args:
            args["documents"] = self._expand_documents(args.get("documents"))
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
                "llm_provider": args.get("llm_provider", "openai"),
                "llm_model": args.get("llm_model", "gpt-5.3-chat-latest"),
                "temperature": args.get("temperature", 0.7),
            }
        })
        self.node_name_map[name] = node_id
        return f"Added GroupChatManager '{name}'"

    def _add_delegate_agent(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        # Expand wildcard "*"/"all" to full document list before resolving toggles
        if "documents" in args:
            args["documents"] = self._expand_documents(args.get("documents"))
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
                "temperature": args.get("temperature", 0.7),
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

    def _add_classifier_agent(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        raw_cats = args.get("categories") or []
        if not isinstance(raw_cats, list) or len(raw_cats) < 2:
            return f"Error: ClassifierAgent '{name}' needs at least 2 categories (got {len(raw_cats) if isinstance(raw_cats, list) else 0})"
        if len(raw_cats) > 10:
            raw_cats = raw_cats[:10]
        # Normalize, assign UUIDs, dedup category names (case-insensitive).
        seen_names: set = set()
        categories: List[Dict[str, Any]] = []
        for i, c in enumerate(raw_cats):
            if not isinstance(c, dict):
                continue
            cname = (c.get("name") or f"Category {i + 1}").strip()
            base = cname
            suffix = 2
            while cname.lower() in seen_names:
                cname = f"{base} {suffix}"
                suffix += 1
            seen_names.add(cname.lower())
            categories.append({
                "id": str(uuid.uuid4()),
                "name": cname,
                "description": (c.get("description") or "").strip(),
            })
        if len(categories) < 2:
            return f"Error: ClassifierAgent '{name}' has fewer than 2 valid categories after normalization"
        self.nodes.append({
            "id": node_id,
            "type": "ClassifierAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "description": f"Routes input to one of {len(categories)} categories",
                "categories": categories,
                "llm_provider": args.get("llm_provider", "anthropic"),
                "llm_model": args.get("llm_model", "claude-3-5-haiku-20241022"),
                "temperature": args.get("temperature", 0.0),
            }
        })
        self.node_name_map[name] = node_id
        cat_list = ", ".join(c["name"] for c in categories)
        return f"Added ClassifierAgent '{name}' with {len(categories)} categories: {cat_list}"

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
        source_category = (args.get("source_category") or "").strip()

        source_id = self.node_name_map.get(source_name)
        target_id = self.node_name_map.get(target_name)

        if not source_id:
            return f"Error: source node '{source_name}' not found"
        if not target_id:
            return f"Error: target node '{target_name}' not found"
        if source_id == target_id:
            return f"Error: cannot connect a node to itself ('{source_name}')"

        # Auto-detect delegate type
        source_node = next((n for n in self.nodes if n["id"] == source_id), None)
        target_node = next((n for n in self.nodes if n["id"] == target_id), None)
        source_type = source_node["type"] if source_node else ""
        target_type = target_node["type"] if target_node else ""
        if (source_type == "GroupChatManager" and target_type == "DelegateAgent") or \
           (source_type == "DelegateAgent" and target_type == "GroupChatManager"):
            edge_type = "delegate"

        # Classifier edges carry a source_handle = the chosen category's UUID.
        # Each category gets its own outgoing edge; the executor prunes branches
        # whose source_handle differs from the classifier's runtime decision.
        source_handle = None
        if source_type == "ClassifierAgent":
            if not source_category:
                cats = (source_node or {}).get("data", {}).get("categories", []) or []
                cat_names = ", ".join(f"'{c.get('name', '?')}'" for c in cats) or "(no categories)"
                return (
                    f"Error: source '{source_name}' is a ClassifierAgent — "
                    f"you MUST pass source_category. Available categories: {cat_names}"
                )
            cats = (source_node or {}).get("data", {}).get("categories", []) or []
            match = next((c for c in cats if (c.get("name") or "").strip().lower() == source_category.lower()), None)
            if match is None:
                cat_names = ", ".join(f"'{c.get('name', '?')}'" for c in cats) or "(no categories)"
                return (
                    f"Error: classifier '{source_name}' has no category named '{source_category}'. "
                    f"Available: {cat_names}"
                )
            source_handle = match.get("id")

        # Check duplicate — classifier edges must be unique per (source, target, category)
        # so include source_handle in the edge id when present.
        edge_id = f"{source_id}-{target_id}" + (f"-{source_handle}" if source_handle else "")
        if any(e["id"] == edge_id for e in self.edges):
            suffix = f" (category: {source_category})" if source_category else ""
            return f"Connection already exists: {source_name} → {target_name}{suffix}"

        edge_obj: Dict[str, Any] = {
            "id": edge_id,
            "source": source_id,
            "target": target_id,
            "type": edge_type,
            "label": "", "description": "", "condition": "",
            "priority": 1, "retryCount": 0, "timeout": 30,
        }
        if source_handle:
            edge_obj["source_handle"] = source_handle
        self.edges.append(edge_obj)
        suffix = f" [category: {source_category}]" if source_category else ""
        return f"Connected '{source_name}' → '{target_name}' ({edge_type}){suffix}"

    # ── Update / Delete ──

    def _update_node_property(self, args: Dict) -> str:
        node_name = args.get("node_name", "")
        properties = args.get("properties", {})

        # LLM often sends flat args (system_message alongside node_name)
        # instead of nesting under "properties" — handle both formats
        if not properties:
            properties = {k: v for k, v in args.items() if k != "node_name"}

        if not node_name or not properties:
            return "Error: node_name and properties are required"

        node_id = self.node_name_map.get(node_name)
        if not node_id:
            return f"Error: node '{node_name}' not found. Available: {', '.join(self.node_name_map.keys())}"

        node = next((n for n in self.nodes if n["id"] == node_id), None)
        if not node:
            return f"Error: node '{node_name}' not found in nodes list"

        # Handle 'documents' shortcut → sets doc_tool_calling_documents + auto-enables
        # Also expand wildcard "*"/"all" to the full available-documents list.
        if "documents" in properties:
            docs = self._expand_documents(properties.pop("documents"))
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

    # ── Surgical-edit tools (Pillar 3) ──
    # Prefer these on existing workflows over delete_node + recreate.

    def _delete_edge(self, args: Dict) -> str:
        source_name = args.get("source_name", "")
        target_name = args.get("target_name", "")
        source_category = (args.get("source_category") or "").strip()
        src_id = self.node_name_map.get(source_name)
        tgt_id = self.node_name_map.get(target_name)
        if not src_id or not tgt_id:
            return f"Error: edge endpoint not found ({source_name} → {target_name})"

        candidates = [e for e in self.edges if e["source"] == src_id and e["target"] == tgt_id]
        if not candidates:
            return f"Error: no edge {source_name} → {target_name}"

        # If source is a classifier and source_category given, narrow to that branch
        src_node = next((n for n in self.nodes if n["id"] == src_id), None)
        if src_node and src_node.get("type") == "ClassifierAgent" and source_category:
            cats = src_node.get("data", {}).get("categories", []) or []
            match = next((c for c in cats if (c.get("name") or "").strip().lower() == source_category.lower()), None)
            if not match:
                return f"Error: classifier '{source_name}' has no category '{source_category}'"
            candidates = [e for e in candidates if e.get("source_handle") == match.get("id")]
            if not candidates:
                return f"Error: no edge for category '{source_category}' from {source_name}"

        for e in candidates:
            self.edges.remove(e)
        suffix = f" [{source_category}]" if source_category else ""
        return f"Deleted {len(candidates)} edge(s): {source_name} → {target_name}{suffix}"

    def _add_category(self, args: Dict) -> str:
        classifier_name = args.get("classifier_name", "")
        cat_name = (args.get("name") or "").strip()
        desc = (args.get("description") or "").strip()
        if not cat_name:
            return "Error: category name is required"
        cls_id = self.node_name_map.get(classifier_name)
        if not cls_id:
            return f"Error: classifier '{classifier_name}' not found"
        node = next((n for n in self.nodes if n["id"] == cls_id), None)
        if not node or node.get("type") != "ClassifierAgent":
            return f"Error: '{classifier_name}' is not a ClassifierAgent"
        cats = node["data"].setdefault("categories", [])
        if any((c.get("name") or "").strip().lower() == cat_name.lower() for c in cats):
            return f"Error: category '{cat_name}' already exists in '{classifier_name}'"
        if len(cats) >= 10:
            return f"Error: '{classifier_name}' already has the max 10 categories"
        cats.append({"id": str(uuid.uuid4()), "name": cat_name, "description": desc})
        return f"Added category '{cat_name}' to '{classifier_name}' (now {len(cats)} categories)"

    def _remove_category(self, args: Dict) -> str:
        classifier_name = args.get("classifier_name", "")
        cat_name = (args.get("name") or "").strip()
        cls_id = self.node_name_map.get(classifier_name)
        if not cls_id:
            return f"Error: classifier '{classifier_name}' not found"
        node = next((n for n in self.nodes if n["id"] == cls_id), None)
        if not node or node.get("type") != "ClassifierAgent":
            return f"Error: '{classifier_name}' is not a ClassifierAgent"
        cats = node["data"].get("categories", []) or []
        match = next((c for c in cats if (c.get("name") or "").strip().lower() == cat_name.lower()), None)
        if not match:
            return f"Error: classifier '{classifier_name}' has no category '{cat_name}'"
        if len(cats) <= 2:
            return (
                f"Error: '{classifier_name}' has only {len(cats)} categories — cannot drop below the minimum of 2. "
                "Add a replacement category first, then remove this one."
            )
        cat_id = match.get("id")
        node["data"]["categories"] = [c for c in cats if c is not match]
        # Cascade-delete edges that referenced this category's source_handle
        removed_edges = [e for e in self.edges if e.get("source") == cls_id and e.get("source_handle") == cat_id]
        for e in removed_edges:
            self.edges.remove(e)
        edge_note = f" (and {len(removed_edges)} branch edge(s))" if removed_edges else ""
        return f"Removed category '{cat_name}' from '{classifier_name}'{edge_note}"

    def _change_edge_type(self, args: Dict) -> str:
        source_name = args.get("source_name", "")
        target_name = args.get("target_name", "")
        new_type = args.get("new_type", "")
        if new_type not in ("sequential", "reflection"):
            return "Error: new_type must be 'sequential' or 'reflection'"
        src_id = self.node_name_map.get(source_name)
        tgt_id = self.node_name_map.get(target_name)
        if not src_id or not tgt_id:
            return f"Error: edge endpoint not found ({source_name} → {target_name})"
        edges = [e for e in self.edges if e["source"] == src_id and e["target"] == tgt_id]
        if not edges:
            return f"Error: no edge {source_name} → {target_name}"
        for e in edges:
            e["type"] = new_type
        return f"Changed {len(edges)} edge(s) {source_name} → {target_name} to type '{new_type}'"

    def _rewire_edge(self, args: Dict) -> str:
        source_name = args.get("source_name", "")
        old_target = args.get("old_target_name", "")
        new_target = args.get("new_target_name", "")
        source_category = (args.get("source_category") or "").strip()
        # Snapshot the edge list before mutating so we can roll back if the
        # add half fails — no half-rewires that leave the graph orphaned.
        edges_snapshot = list(self.edges)
        del_result = self._delete_edge({
            "source_name": source_name,
            "target_name": old_target,
            "source_category": source_category,
        })
        if del_result.startswith("Error:"):
            return f"Rewire failed at delete: {del_result}"
        add_result = self._connect_nodes({
            "source_name": source_name,
            "target_name": new_target,
            "source_category": source_category,
            "edge_type": "sequential",
        })
        if add_result.startswith("Error:"):
            # Roll back — restore the original edges
            self.edges = edges_snapshot
            return f"Rewire failed at add (rolled back): {add_result}"
        suffix = f" [{source_category}]" if source_category else ""
        return f"Rewired{suffix}: {source_name} → {old_target} replaced with {source_name} → {new_target}"

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

        # EndNode should have exactly 1 incoming edge — UNLESS all incoming trace
        # back to a ClassifierAgent (classifier branches each independently terminate).
        if end_nodes:
            end_id = end_nodes[0]["id"]
            incoming = [e for e in self.edges if e["target"] == end_id]
            if len(incoming) > 1:
                node_type_by_id = {n["id"]: n["type"] for n in self.nodes}

                def _traces_back_to_classifier(src_id, seen=None):
                    seen = seen if seen is not None else set()
                    if src_id in seen:
                        return False
                    seen.add(src_id)
                    if node_type_by_id.get(src_id) == "ClassifierAgent":
                        return True
                    upstream = [e for e in self.edges if e["target"] == src_id]
                    if not upstream:
                        return False
                    return all(_traces_back_to_classifier(e["source"], seen) for e in upstream)

                if not all(_traces_back_to_classifier(e["source"]) for e in incoming):
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

    # Fix 2: Agents with no outgoing → connect to the last agent or EndNode.
    # Strategy: find agents that are "sinks" (no outgoing) and connect them forward.
    # The last agent in the list is likely the synthesizer/final agent.
    # Skip ClassifierAgent: its outgoing edges are per-category and cannot be
    # auto-added here (we'd need a source_handle / category UUID).
    # EXCEPTION: if an agent has an incoming edge directly from a ClassifierAgent,
    # it's a branch terminal — connect it straight to EndNode, not to last_agent
    # (otherwise classifier branches get incorrectly chained through a shared agent).
    classifier_ids = {n["id"] for n in builder.nodes if n["type"] == "ClassifierAgent"}

    def _is_classifier_branch(agent_id):
        return any(
            e["target"] == agent_id and e["source"] in classifier_ids
            for e in builder.edges
        )

    last_agent = agents[-1] if agents else None
    for a in agents:
        if a["type"] == "ClassifierAgent":
            continue
        if a["id"] not in sources:
            if _is_classifier_branch(a["id"]):
                # Classifier branch terminal → goes directly to End
                _add_edge(a["id"], end["id"])
            elif a == last_agent:
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
    # EXCEPTION: if every incoming edge traces back to a ClassifierAgent branch,
    # this is a legitimate routing pattern (only one branch fires at runtime).
    end_incoming = [e for e in builder.edges if e["target"] == end["id"]]
    if len(end_incoming) > 1:
        node_type_by_id = {n["id"]: n["type"] for n in builder.nodes}

        def _traces_back_to_classifier(src_id: str, seen: Optional[set] = None) -> bool:
            """True iff every path leading into src_id originates from a classifier branch."""
            seen = seen if seen is not None else set()
            if src_id in seen:
                return False
            seen.add(src_id)
            if node_type_by_id.get(src_id) == "ClassifierAgent":
                return True
            upstream = [e for e in builder.edges if e["target"] == src_id]
            if not upstream:
                return False
            return all(_traces_back_to_classifier(e["source"], seen) for e in upstream)

        if all(_traces_back_to_classifier(e["source"]) for e in end_incoming):
            logger.info(
                f"🔧 AUTO-REPAIR: Keeping all {len(end_incoming)} EndNode incoming edges "
                "(all originate from classifier branches)"
            )
        else:
            keep_source = last_agent["id"] if last_agent else end_incoming[-1]["source"]
            edges_to_remove = [e for e in end_incoming if e["source"] != keep_source]
            for e in edges_to_remove:
                builder.edges.remove(e)
                logger.info(f"🔧 AUTO-REPAIR: Removed extra EndNode edge {e['id']}")


# ── Diff helper (Pillar 4) ─────────────────────────────────────────────

def _compute_graph_diff(
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Compute a by-name diff between the previous canvas and the freshly built
    graph so the preview UI can show "+ X, - Y, ~ Z" before the user accepts.

    Returns None for fresh builds (no preview needed — there's nothing to
    compare against).

    Operates by NAME, not UUID, because every rebuild reassigns node IDs.
    """
    if not before or not before.get("nodes"):
        return None

    before_nodes = before.get("nodes", []) or []
    after_nodes = (after or {}).get("nodes", []) or []
    before_edges = before.get("edges", []) or []
    after_edges = (after or {}).get("edges", []) or []

    before_by_name = {
        n["data"].get("name"): n
        for n in before_nodes
        if n.get("data", {}).get("name")
    }
    after_by_name = {
        n["data"].get("name"): n
        for n in after_nodes
        if n.get("data", {}).get("name")
    }

    added = [name for name in after_by_name if name not in before_by_name]
    removed = [name for name in before_by_name if name not in after_by_name]

    # Watch only fields that meaningfully change agent behavior
    watched = (
        "system_message", "llm_provider", "llm_model", "temperature",
        "doc_aware", "web_search_enabled", "doc_tool_calling_documents",
        "categories", "prompt", "type",
    )
    updated: List[Dict[str, Any]] = []
    for name, after_n in after_by_name.items():
        before_n = before_by_name.get(name)
        if not before_n:
            continue
        if before_n.get("type") != after_n.get("type"):
            updated.append({"name": name, "fields": ["type"]})
            continue
        bd = before_n.get("data", {}) or {}
        ad = after_n.get("data", {}) or {}
        changed = [k for k in watched if bd.get(k) != ad.get(k)]
        if changed:
            updated.append({"name": name, "fields": changed})

    # Edges keyed by (source_name, target_name, source_handle) — handle is the
    # classifier category UUID, so it survives rebuilds only if the category
    # name does. Fall back to the human category name for cross-rebuild parity.
    def _edge_key(edge: Dict[str, Any], nodes: List[Dict[str, Any]]) -> tuple:
        id_to_name = {n["id"]: n.get("data", {}).get("name", n["id"]) for n in nodes}
        # Resolve source_handle (UUID) to category name when the source is a classifier
        cat_name = None
        h = edge.get("source_handle")
        if h:
            src_node = next((n for n in nodes if n["id"] == edge.get("source")), None)
            if src_node and src_node.get("type") == "ClassifierAgent":
                cats = src_node.get("data", {}).get("categories") or []
                cat = next((c for c in cats if c.get("id") == h), None)
                if cat:
                    cat_name = cat.get("name")
        return (
            id_to_name.get(edge.get("source")),
            id_to_name.get(edge.get("target")),
            cat_name,
        )

    before_edge_set = {_edge_key(e, before_nodes) for e in before_edges}
    after_edge_set = {_edge_key(e, after_nodes) for e in after_edges}

    added_edges = [
        {"source": k[0], "target": k[1], "category": k[2]}
        for k in (after_edge_set - before_edge_set)
    ]
    removed_edges = [
        {"source": k[0], "target": k[1], "category": k[2]}
        for k in (before_edge_set - after_edge_set)
    ]

    return {
        "added_nodes": added,
        "removed_nodes": removed,
        "updated_nodes": updated,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
    }


# ── Planning helper (Pillar 1) ─────────────────────────────────────────

async def _run_planning_phase(
    llm_provider,
    system_content: str,
    conversation_history: Optional[List[Dict]],
    user_message: str,
) -> str:
    """First-pass planning call that mirrors the AssistantAgent's `plan_mode`:
    NO `tools` parameter is passed, so the LLM physically cannot tool-call.
    Returns the plan text (empty string on any failure — gracefully degrades).
    """
    plan_prompt = (
        "Before building, output a structured PLAN as a numbered list:\n"
        "1. List every agent you will ADD (with role and one-line system_message gist).\n"
        "2. List every agent you will REMOVE (by name). REMOVE ONLY if the user "
        "EXPLICITLY asked to delete/remove/rebuild/replace/start over. "
        "If they did not use those words, this list MUST be empty — preserve "
        "all existing agents.\n"
        "3. List every agent you will UPDATE (by name) and which properties change.\n"
        "4. List every edge you will ADD or REMOVE.\n"
        "5. State the final flow as: Start → ... → End.\n\n"
        "Output ONLY the numbered plan. No tool calls, no prose preamble. "
        "Be specific — name actual agents and properties, not generic placeholders."
    )
    plan_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
    if conversation_history:
        plan_messages.extend(conversation_history)
    plan_messages.append({"role": "user", "content": user_message})
    plan_messages.append({"role": "user", "content": plan_prompt})

    try:
        # CRITICAL: omit `tools` parameter so the LLM physically cannot tool-call.
        response = await llm_provider.generate_response(messages=plan_messages)
    except Exception as e:
        logger.warning(f"⚠️ WORKFLOW GEN: planning phase crashed: {e}")
        return ""
    if response.error:
        logger.warning(f"⚠️ WORKFLOW GEN: planning phase error: {response.error}")
        return ""
    return (response.text or "").strip()


# ── Main generator function ────────────────────────────────────────────

async def generate_workflow(
    project,
    user_message: str,
    conversation_history: Optional[List[Dict]] = None,
    current_graph: Optional[Dict[str, Any]] = None,
    attached_files_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a workflow from natural language requirements.

    Args:
        project: IntelliDocProject instance
        user_message: The user's requirements
        conversation_history: Previous messages in the conversation
        attached_files_text: Optional pre-extracted text from files the user
            attached to this turn. When present, it is appended to the user
            message under an "ATTACHED FILES" header so the LLM treats the
            content as additional context for the workflow it builds.

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
            "with exact filenames from the list above. By default, assign only documents relevant "
            "to each agent's task. If the user explicitly asks for all documents on all agents "
            "(or similar bulk assignment), use documents=[\"*\"] as a shortcut instead of "
            "enumerating every filename."
        )

    # Build current workflow description (if modifying an existing workflow)
    current_workflow_section = ""
    if current_graph and current_graph.get("nodes"):
        cw_nodes = current_graph["nodes"]
        cw_edges = current_graph.get("edges", [])
        node_id_to_name = {n["id"]: n.get("data", {}).get("name", n["id"][:8]) for n in cw_nodes}
        cw_lines = [f"\n\nCURRENT WORKFLOW ON CANVAS ({len(cw_nodes)} nodes, {len(cw_edges)} connections):"]
        # Show StartNode prompt (the workflow's purpose) so the LLM knows what
        # the existing graph is FOR before deciding how to modify it.
        _start_node = next((n for n in cw_nodes if n.get("type") == "StartNode"), None)
        if _start_node:
            _sp = (_start_node.get("data", {}).get("prompt") or "").strip()
            if _sp:
                cw_lines.append(f'StartNode prompt: "{_sp[:500]}{"…" if len(_sp) > 500 else ""}"')
        cw_lines.append("Nodes:")
        for n in cw_nodes:
            d = n.get("data", {})
            line = f'  - {n["type"]}: "{d.get("name", "?")}"'
            if d.get("llm_provider") or d.get("llm_model"):
                line += f" [{d.get('llm_provider', 'openai')}/{d.get('llm_model', '?')}]"
            temp = d.get("temperature")
            if temp is not None and temp != 0.7:
                line += f" [temp={temp}]"
            docs = d.get("doc_tool_calling_documents", [])
            if docs:
                line += f" [documents: {', '.join(docs)}]"
            if d.get("doc_aware"):
                line += " [doc_aware]"
            if d.get("web_search_enabled"):
                line += " [web_search]"
            if d.get("plan_mode") is False:
                line += " [plan_mode=off]"
            cw_lines.append(line)
            # Pillar 2: show truncated system_message (so the LLM knows what
            # each agent currently does before rewriting it).
            sys_msg = (d.get("system_message") or "").strip()
            if sys_msg and n["type"] not in ("StartNode", "EndNode"):
                snippet = sys_msg[:500] + ("…" if len(sys_msg) > 500 else "")
                cw_lines.append(f"      system_message: {snippet}")
            # Pillar 2: show categories WITH descriptions on their own lines
            if n["type"] == "ClassifierAgent":
                cats = d.get("categories") or []
                if cats:
                    cw_lines.append("      categories:")
                    for c in cats:
                        cname = c.get("name", "?")
                        cdesc = (c.get("description") or "").strip()
                        cw_lines.append(f"        • {cname}" + (f" — {cdesc[:200]}" if cdesc else ""))
        cw_lines.append("Connections:")
        # Map classifier node_id → {category_id: category_name} so we can
        # annotate classifier-branch edges with the human-readable category name.
        cw_classifier_cat_names = {
            n["id"]: {
                c.get("id"): c.get("name", "?")
                for c in (n.get("data", {}).get("categories") or [])
            }
            for n in cw_nodes if n.get("type") == "ClassifierAgent"
        }
        for e in cw_edges:
            src = node_id_to_name.get(e["source"], "?")
            tgt = node_id_to_name.get(e["target"], "?")
            handle_suffix = ""
            if e.get("source_handle") and e["source"] in cw_classifier_cat_names:
                cat_name = cw_classifier_cat_names[e["source"]].get(e["source_handle"])
                if cat_name:
                    handle_suffix = f" [category: {cat_name}]"
            cw_lines.append(f"  - {src} → {tgt} ({e.get('type', 'sequential')}){handle_suffix}")
        cw_lines.append("")
        cw_lines.append(
            "The user wants to MODIFY this existing workflow. PRESERVE all "
            "current agents and edges by default. Use update_node_property, "
            "add_*, connect_nodes, delete_edge, add_category, etc. for "
            "incremental edits. Only delete agents if the user explicitly "
            "asked to remove them (words like remove/delete/rebuild/replace/"
            "start over). A pasted system prompt is NOT a delete request — "
            "it's either a new system_message for an existing agent or for a "
            "new agent you add."
        )
        current_workflow_section = "\n".join(cw_lines)

    # Build messages — fill in dynamic sections
    system_content = SYSTEM_PROMPT.replace("{available_models_section}", available_models_section) + doc_listing + current_workflow_section
    # ── Pillar 1: enforced planning phase when modifying an existing workflow ──
    # Run a tools-disabled LLM call first so the plan is grounded in the current
    # canvas state. Skip for fresh builds (nothing to modify against).
    plan_text = ""
    if current_graph and current_graph.get("nodes"):
        plan_text = await _run_planning_phase(
            llm_provider, system_content, conversation_history, user_message
        )
        logger.info(
            f"📋 WORKFLOW GEN: planning phase produced {len(plan_text)} chars"
            + (" (empty — falling back to single-pass build)" if not plan_text else "")
        )

    # If the caller passed pre-extracted text from user-attached files, fold it
    # into the user turn so the LLM sees the document content as context.
    effective_user_message = user_message
    if attached_files_text:
        effective_user_message = (
            f"{user_message}\n\n"
            "The user attached the following file(s) to this message — "
            "use this content as context for the workflow you build:\n\n"
            f"{attached_files_text}"
        )

    # Prepend the plan so the build phase executes against an explicit plan.
    if plan_text:
        effective_user_message = (
            f"Here is your PLAN (from the planning phase — execute it now):\n"
            f"{plan_text}\n\n"
            "Stick to the plan unless you discover a real issue while building.\n\n"
            f"User request: {effective_user_message}"
        )

    messages = [{"role": "system", "content": system_content}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": effective_user_message})

    # Call LLM with tools — pass available document filenames so the builder
    # can expand wildcard `documents=["*"]` to the full project document list.
    available_doc_filenames = [d.original_filename for d in project_docs]
    builder = WorkflowBuilder(available_documents=available_doc_filenames)
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

    # Auto-repair: fix common issues the LLM misses (deterministic)
    _auto_repair_connections(builder)

    # ── Verification Agent: LLM reviews the graph and fixes issues ──
    if builder.nodes and len(builder.nodes) >= 3:
        try:
            verify_graph = builder.build_graph_json()
            v_nodes = verify_graph["nodes"]
            v_edges = verify_graph["edges"]
            node_id_to_name_v = {n["id"]: n.get("data", {}).get("name", "?") for n in v_nodes}

            graph_desc_lines = ["Current workflow after auto-repair:"]
            # StartNode prompt for purpose context
            _v_start = next((n for n in v_nodes if n.get("type") == "StartNode"), None)
            if _v_start:
                _vsp = (_v_start.get("data", {}).get("prompt") or "").strip()
                if _vsp:
                    graph_desc_lines.append(f'StartNode prompt: "{_vsp[:500]}{"…" if len(_vsp) > 500 else ""}"')
            graph_desc_lines.append(f"Nodes ({len(v_nodes)}):")
            for n in v_nodes:
                d = n.get("data", {})
                nid = n["id"]
                inc = len([e for e in v_edges if e["target"] == nid])
                out = len([e for e in v_edges if e["source"] == nid])
                line = f'  {n["type"]}: "{d.get("name", "?")}" ({out} out, {inc} in)'
                if d.get("llm_provider") or d.get("llm_model"):
                    line += f" [{d.get('llm_provider', 'openai')}/{d.get('llm_model', '?')}]"
                temp = d.get("temperature")
                if temp is not None and temp != 0.7:
                    line += f" [temp={temp}]"
                if d.get("doc_tool_calling_documents"):
                    line += f" [docs: {len(d['doc_tool_calling_documents'])}]"
                if d.get("doc_aware"):
                    line += " [doc_aware]"
                if d.get("web_search_enabled"):
                    line += " [web_search]"
                if d.get("plan_mode") is False:
                    line += " [plan_mode=off]"
                graph_desc_lines.append(line)
                # Pillar 2: truncated system_message
                _vsm = (d.get("system_message") or "").strip()
                if _vsm and n["type"] not in ("StartNode", "EndNode"):
                    _snip = _vsm[:500] + ("…" if len(_vsm) > 500 else "")
                    graph_desc_lines.append(f"      system_message: {_snip}")
                # Pillar 2: classifier categories with descriptions
                if n["type"] == "ClassifierAgent":
                    cats = d.get("categories") or []
                    if cats:
                        graph_desc_lines.append("      categories:")
                        for c in cats:
                            _cn = c.get("name", "?")
                            _cd = (c.get("description") or "").strip()
                            graph_desc_lines.append(f"        • {_cn}" + (f" — {_cd[:200]}" if _cd else ""))
            graph_desc_lines.append(f"Connections ({len(v_edges)}):")
            v_classifier_cat_names = {
                n["id"]: {
                    c.get("id"): c.get("name", "?")
                    for c in (n.get("data", {}).get("categories") or [])
                }
                for n in v_nodes if n.get("type") == "ClassifierAgent"
            }
            for e in v_edges:
                src = node_id_to_name_v.get(e["source"], "?")
                tgt = node_id_to_name_v.get(e["target"], "?")
                handle_suffix = ""
                if e.get("source_handle") and e["source"] in v_classifier_cat_names:
                    cat_name = v_classifier_cat_names[e["source"]].get(e["source_handle"])
                    if cat_name:
                        handle_suffix = f" [category: {cat_name}]"
                graph_desc_lines.append(f"  {src} → {tgt} ({e.get('type', 'sequential')}){handle_suffix}")
            graph_desc = "\n".join(graph_desc_lines)

            _plan_block = f"Original plan from the planning phase:\n{plan_text}\n\n" if plan_text else ""
            verify_prompt = (
                f"You are verifying a workflow that was just built. Here is the current state:\n\n"
                f"{graph_desc}\n\n"
                f"{_plan_block}"
                f"The user's original request was: \"{user_message[:500]}\"\n\n"
                "VERIFY the following and FIX any issues using the available tools:\n"
                "1. Does the orchestration make sense for the user's request? Are the right agents created with the right roles?\n"
                "2. Are all connections valid? Does information flow logically from source to destination?\n"
                "3. Is every agent reachable from StartNode? Does exactly one agent connect to EndNode "
                "(exception: multiple branches from a ClassifierAgent MAY each terminate at EndNode)?\n"
                "4. Are web_search / doc_tool_calling / documents / doc_aware assigned correctly per each agent's role?\n"
                "5. Are system_messages detailed enough for each agent to do its job?\n"
                "6. Are LLM models and temperatures appropriate for each agent's task?\n"
                "7. For any ClassifierAgent: 2-10 categories with unique non-empty names and "
                "clear descriptions; every outgoing edge specifies a source_category matching "
                "an existing category name; each category branch leads somewhere meaningful.\n"
                "8. Did you remove existing agents? If yes, did the user EXPLICITLY request "
                "removal (words like remove/delete/rebuild/replace/start over)? If you removed "
                "agents WITHOUT explicit user request, that is a regression — RESTORE them via "
                "add_assistant_agent (or the appropriate add_*) + connect_nodes.\n"
                + ("9. Did the build follow the plan above? Note any drift and fix it.\n\n" if plan_text else "\n")
                + "If everything looks correct, respond with 'Verification passed — workflow is valid.'\n"
                "If there are issues, use update_node_property, delete_node, connect_nodes, or add_* tools to fix them.\n"
                "Do NOT rebuild the workflow from scratch — only fix specific issues."
            )

            verify_messages = [{"role": "system", "content": system_content}]
            verify_messages.append({"role": "user", "content": verify_prompt})

            logger.info(f"🔍 WORKFLOW GEN: Running verification agent on {len(v_nodes)} nodes, {len(v_edges)} edges")

            for v_iter in range(3):
                v_response = await llm_provider.generate_response(messages=verify_messages, tools=WORKFLOW_TOOLS)
                if v_response.error:
                    logger.warning(f"⚠️ WORKFLOW GEN: Verification agent error: {v_response.error}")
                    break
                if v_response.text:
                    explanation += f"\n\n**Verification:** {v_response.text}"
                    logger.info(f"🔍 WORKFLOW GEN: Verification agent: {v_response.text[:200]}")
                if not v_response.tool_calls:
                    break
                # Process verification tool calls
                formatted_v_calls = []
                for tc in v_response.tool_calls:
                    fn = tc.get("function", {})
                    raw_args = fn.get("arguments", tc.get("arguments", "{}"))
                    args_str = json.dumps(raw_args) if isinstance(raw_args, dict) else str(raw_args)
                    formatted_v_calls.append({
                        "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        "type": "function",
                        "function": {"name": fn.get("name", tc.get("name", "")), "arguments": args_str}
                    })
                verify_messages.append({"role": "assistant", "content": v_response.text or "", "tool_calls": formatted_v_calls})
                for tc in formatted_v_calls:
                    fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                    result = builder.execute_tool_call(tc["function"]["name"], fn_args)
                    logger.info(f"🔧 WORKFLOW GEN (verify): {tc['function']['name']} → {result}")
                    verify_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        except Exception as verify_err:
            logger.warning(f"⚠️ WORKFLOW GEN: Verification agent failed: {verify_err}")

    # Build and validate
    graph_json = builder.build_graph_json()
    is_valid, errors = builder.validate()

    if not is_valid:
        explanation += f"\n\nNote: The generated workflow has validation issues: {', '.join(errors)}"

    # Pillar 4: compute the diff for the preview UX (None for fresh builds)
    diff = _compute_graph_diff(current_graph, graph_json)

    return {
        "graph_json": graph_json,
        "explanation": explanation.strip(),
        "tool_calls": builder.tool_calls_log,
        "errors": errors,
        "plan": plan_text,  # Pillar 1 — empty string for fresh builds or on planning failure
        "diff": diff,        # Pillar 4 — None for fresh builds
    }
