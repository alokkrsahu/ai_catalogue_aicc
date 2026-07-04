"""
AI Workflow Generator — builds agent orchestration workflows from natural language.
Uses LLM tool-calling to create nodes, configure agents, and connect them.
"""
import uuid
import json
import logging
import time
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
                    "web_search_top_k": {
                        "type": "integer",
                        "description": "URL mode only: number of RAG chunks to retrieve per query (default: 5, range: 1-20)"
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
                    "web_search_top_k": {
                        "type": "integer",
                        "description": "URL mode only: number of RAG chunks to retrieve per query (default: 5, range: 1-20)"
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
            "name": "add_splitter_agent",
            "description": (
                "Add a SplitterAgent — a task-distribution node that reads an input, "
                "looks at each downstream agent's system_message as a capability "
                "description, and allocates a DIFFERENT subtask to each one. "
                "Downstream agents run in parallel, each processing its allocated "
                "subtask. Agents with no relevant subtask for this input are pruned "
                "(their branch skipped). Use when you want intelligent task "
                "decomposition across specialists — as opposed to parallel fan-out "
                "where every agent sees the same input, or classifier routing where "
                "exactly one branch runs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Descriptive name (e.g. 'Task Splitter', 'Work Dispatcher')"
                    },
                    "overlap_allowed": {
                        "type": "boolean",
                        "description": "Default false (strict partition — each piece goes to exactly one agent). Set true for multi-perspective scenarios where the same content benefits from being reviewed by multiple agents."
                    },
                    "llm_provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "google"],
                        "description": "LLM provider for splitter allocation (default: openai — fast + structured outputs)"
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "Model name — use the LIGHTWEIGHT model listed in AVAILABLE LLM MODELS above (not the flagship/content-generation one). This node only makes a structured routing decision, never generates the user-facing answer."
                    },
                    "temperature": {
                        "type": "number",
                        "description": "LLM temperature 0-2 (default: 0.0 — routers want determinism)"
                    }
                },
                "required": ["name"]
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
            "description": "Create a connection between two nodes. Connections define the execution flow. DelegateAgent ↔ GroupChatManager connections are auto-typed as 'delegate'. When source is a ClassifierAgent, source_category IS REQUIRED. When source is a SplitterAgent, DO NOT pass source_category — splitter edges are plain sequential connections (allocation is decided at runtime by the splitter LLM). Use edge_type='reflection' with max_iterations and reflection_prompt to create bounded revision/refinement loops (see REFLECTION LOOPS section of the system prompt).",
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
                        "description": "Connection type (default: sequential). Use 'reflection' ONLY for bounded iterative-refinement loops (review-and-revise, self-critique). Reflection edges may form self-loops or back-edges; sequential edges MUST form a DAG."
                    },
                    "source_category": {
                        "type": "string",
                        "description": "REQUIRED when source is a ClassifierAgent — the category NAME this edge represents (matching one of the classifier's category names). The edge fires only when the classifier picks this category."
                    },
                    "max_iterations": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Only used when edge_type='reflection'. Maximum number of times the reflection loop runs (default 2). Match the user's request (e.g. 'up to 2 revisions' → max_iterations=2)."
                    },
                    "reflection_prompt": {
                        "type": "string",
                        "description": "Only used when edge_type='reflection'. Instructions for the agent receiving the reflection on what to improve or how to incorporate feedback (e.g. 'Revise the draft based on the reviewer's feedback, focusing on accuracy and clarity.')."
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
                        "description": "Properties to update — keys are property names (system_message, llm_provider, llm_model, temperature, documents, web_search_enabled, web_search_max_results, web_search_top_k, doc_tool_calling, doc_aware, plan_mode, etc.), values are new values. Only specified keys are changed; everything else stays the same.",
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
• Every agent must be reachable from StartNode and must have a path to EndNode — EXCEPT reflection-only target agents (agents that receive ONLY a reflection edge and have no sequential incoming or outgoing edges). Reflection-only targets are helpers serving their source agent's internal iteration and are not required to reach EndNode.
• No orphan nodes. No self-connections on SEQUENTIAL edges.
• No cycles on SEQUENTIAL edges — the executor uses a topological sort that will break. Reflection edges (edge_type="reflection") are the ONLY legal way to create a back-edge or self-loop; they are bounded by max_iterations and excluded from the topological sort at runtime. See "REFLECTION LOOPS" section below.

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

SplitterAgent:
  A task-distribution node. Reads the input and each directly-connected downstream
  agent's system_message (as a capability description), then allocates a DIFFERENT
  subtask to each appropriate agent via forced LLM tool-calling. Agents with no
  relevant subtask for a given input are pruned (their branch skipped). Downstream
  agents run in parallel, each with its ALLOCATED SUBTASK as input (not the original
  input — this is the key difference from ClassifierAgent and parallel fan-out).
  Has an `overlap_allowed` toggle: false (default) = strict partition, true = same
  content may appear in multiple subtasks. Requires ≥2 downstream agents. Use when:
  you want intelligent task decomposition across specialists (e.g. "write a report"
  → Researcher gets "find sources", Writer gets "draft prose", Editor gets "polish"),
  a project-manager-style work distributor is needed, or you want dynamic work
  allocation that adapts to each input rather than every agent running on the same text.

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

TASK-SPLITTING (splitter fan-out): Start → Splitter → [Researcher, Writer, Editor] → Synthesizer → End
  The Splitter looks at each downstream agent's system_message and allocates a
  DIFFERENT subtask to each. Agents without a relevant subtask are pruned for
  that input. All allocated agents run in parallel with their own subtask as
  input. Use when the user wants intelligent work distribution across specialists
  (e.g. "split this research task among the three agents"). Requires ≥2 downstream
  agents. Typically followed by a Synthesizer/Aggregator agent that combines the
  outputs before EndNode — the Splitter itself does not aggregate.

Choose the pattern that best fits the user's requirements. Complex workflows may combine multiple patterns.

═══════════════════════════════════════════════════════════
ROUTING DECISION GUIDE — PICK THE RIGHT DISPATCHER
═══════════════════════════════════════════════════════════

When the user wants multiple downstream agents after a single upstream
source, three patterns are available. The right choice depends on what
input each downstream agent should receive and how many should execute:

┌──────────────────────┬────────────────────────┬──────────────────────┬──────────────────┐
│ Pattern              │ Who executes?          │ What input do they   │ Branch pruning?  │
│                      │                        │ receive?             │                  │
├──────────────────────┼────────────────────────┼──────────────────────┼──────────────────┤
│ Parallel fan-out     │ ALL connected agents   │ SAME input (the      │ No — every       │
│ (source → [A,B,C])   │ every run              │ upstream output,     │ branch runs      │
│                      │                        │ unchanged to each)   │                  │
├──────────────────────┼────────────────────────┼──────────────────────┼──────────────────┤
│ ClassifierAgent      │ EXACTLY ONE of N       │ SAME input (the      │ Yes — the N-1    │
│ (Start → Classifier  │ branches per run       │ original text, un-   │ non-chosen       │
│ → [Cat A, Cat B...]) │ (runtime decides)      │ changed — classifier │ branches skip    │
│                      │                        │ is a pure router)    │                  │
├──────────────────────┼────────────────────────┼──────────────────────┼──────────────────┤
│ SplitterAgent        │ A SUBSET of connected  │ DIFFERENT subtask    │ Yes — agents     │
│ (Start → Splitter    │ agents per run (LLM    │ per agent (allocated │ without a sub-   │
│ → [R, W, E] → Syn)   │ picks who's relevant)  │ by splitter at      │ task are pruned  │
│                      │                        │ runtime)             │                  │
└──────────────────────┴────────────────────────┴──────────────────────┴──────────────────┘

How to pick when the user's phrasing is ambiguous:

• "Run these N agents in parallel on the input"         → Parallel fan-out
• "Have them all work on the same text at the same time" → Parallel fan-out
• "Each agent has a different angle but same input"       → Parallel fan-out

• "Route to the right agent for this input"              → ClassifierAgent
• "If X, do A; if Y, do B; if Z, do C"                   → ClassifierAgent
• "Triage / classify / detect category"                   → ClassifierAgent
• "Pick the best agent for this query"                    → ClassifierAgent

• "Split the work among these agents"                     → SplitterAgent
• "Divide the task and give each agent a piece"           → SplitterAgent
• "Break this down and allocate to specialists"           → SplitterAgent
• "One agent researches, another writes, another edits"    → SplitterAgent
• "Project-manager-style distribution"                     → SplitterAgent

If unsure between fan-out and Splitter: fan-out is simpler (same input to all).
Only pick Splitter when the user explicitly wants differentiated per-agent
work or when agent roles are clearly complementary (research + write + edit).

═══════════════════════════════════════════════════════════
WORKED EXAMPLES — FOLLOW THESE TOOL-CALL SEQUENCES
═══════════════════════════════════════════════════════════

Example A — ClassifierAgent routing (customer support triage)
  User request: "Classify support tickets as Billing, Technical, or Other
                 and route each to a specialist."
  Tool calls (in order):
    1. add_start_node(prompt="Incoming support ticket")
    2. add_classifier_agent(name="Ticket Classifier", categories=[
         {name: "Billing",   description: "Payment, invoice, refund questions"},
         {name: "Technical", description: "Product bugs, how-to questions"},
         {name: "Other",     description: "General inquiries and feedback"},
       ])
    3. add_assistant_agent(name="Billing Specialist",   system_message="...")
    4. add_assistant_agent(name="Technical Specialist", system_message="...")
    5. add_assistant_agent(name="General Specialist",   system_message="...")
    6. add_end_node()
    7. connect_nodes(source_name="Start 1",           target_name="Ticket Classifier")
    8. connect_nodes(source_name="Ticket Classifier", target_name="Billing Specialist",   source_category="Billing")
    9. connect_nodes(source_name="Ticket Classifier", target_name="Technical Specialist", source_category="Technical")
   10. connect_nodes(source_name="Ticket Classifier", target_name="General Specialist",   source_category="Other")
   11. connect_nodes(source_name="Billing Specialist",   target_name="End 1")
   12. connect_nodes(source_name="Technical Specialist", target_name="End 1")
   13. connect_nodes(source_name="General Specialist",   target_name="End 1")
  Key points:
    • Each classifier outgoing edge passes source_category (the category name).
    • Three specialists terminate at EndNode independently — allowed because
      only one branch fires at runtime.

Example B — SplitterAgent task decomposition (research report)
  User request: "Build a workflow that splits a research task across three
                 specialists (researcher, writer, editor) in parallel,
                 then combines their outputs."
  Tool calls (in order):
    1. add_start_node(prompt="Research topic and requirements")
    2. add_splitter_agent(name="Task Splitter")   # defaults: openai/gpt-5.4-mini (lightweight — routing only), strict partition
    3. add_assistant_agent(name="Source Researcher", system_message="You find primary sources and raw data...")
    4. add_assistant_agent(name="Draft Writer",      system_message="You compose prose from research findings...")
    5. add_assistant_agent(name="Copy Editor",       system_message="You polish prose for clarity and style...")
    6. add_assistant_agent(name="Synthesizer",       system_message="You combine the three outputs into one coherent report...")
    7. add_end_node()
    8. connect_nodes(source_name="Start 1",          target_name="Task Splitter")
    9. connect_nodes(source_name="Task Splitter",    target_name="Source Researcher")   # plain sequential edge
   10. connect_nodes(source_name="Task Splitter",    target_name="Draft Writer")
   11. connect_nodes(source_name="Task Splitter",    target_name="Copy Editor")
   12. connect_nodes(source_name="Source Researcher", target_name="Synthesizer")
   13. connect_nodes(source_name="Draft Writer",      target_name="Synthesizer")
   14. connect_nodes(source_name="Copy Editor",       target_name="Synthesizer")
   15. connect_nodes(source_name="Synthesizer",       target_name="End 1")
  Key points:
    • Splitter edges use PLAIN connect_nodes (no source_category, no
      source_handle — the allocation is dynamic per-input, decided at runtime
      by the splitter LLM).
    • Always include a Synthesizer/Aggregator downstream of the three
      specialists — the Splitter itself does NOT combine outputs.
    • Each specialist's system_message should clearly describe what they do
      — the Splitter LLM reads those descriptions to decide who gets which
      subtask.

Example C — Classifier routing into a Splitter (combined routers)
  User request: "First classify whether the input is a Research task or a
                 Bug Report. If Research, split the work among a Literature
                 Reviewer, Data Analyst, and Summary Writer, then combine.
                 If Bug Report, send to a single Bug Triage agent."
  Tool calls (in order):
    1. add_start_node(prompt="Incoming task")
    2. add_classifier_agent(name="Task Classifier", categories=[
         {name: "Research",   description: "Literature search, analysis, summarization"},
         {name: "Bug Report", description: "Defects, regressions, unexpected behavior"},
       ])
    3. add_splitter_agent(name="Research Splitter")
    4. add_assistant_agent(name="Literature Reviewer",   system_message="You locate and summarize relevant prior work...")
    5. add_assistant_agent(name="Data Analyst",          system_message="You analyze quantitative data and identify patterns...")
    6. add_assistant_agent(name="Summary Writer",        system_message="You distil findings into a concise summary...")
    7. add_assistant_agent(name="Research Synthesizer",  system_message="You combine the three outputs into one coherent report...")
    8. add_assistant_agent(name="Bug Triage Agent",      system_message="You triage bug reports: severity, component, steps to repro...")
    9. add_end_node()
   10. connect_nodes(source_name="Start 1",            target_name="Task Classifier")
   11. connect_nodes(source_name="Task Classifier",    target_name="Research Splitter", source_category="Research")
   12. connect_nodes(source_name="Task Classifier",    target_name="Bug Triage Agent",  source_category="Bug Report")
   13. connect_nodes(source_name="Research Splitter",  target_name="Literature Reviewer")
   14. connect_nodes(source_name="Research Splitter",  target_name="Data Analyst")
   15. connect_nodes(source_name="Research Splitter",  target_name="Summary Writer")
   16. connect_nodes(source_name="Literature Reviewer", target_name="Research Synthesizer")
   17. connect_nodes(source_name="Data Analyst",        target_name="Research Synthesizer")
   18. connect_nodes(source_name="Summary Writer",      target_name="Research Synthesizer")
   19. connect_nodes(source_name="Research Synthesizer", target_name="End 1")
   20. connect_nodes(source_name="Bug Triage Agent",     target_name="End 1")
  Key points for COMBINED routers:
    • The Classifier has EXACTLY N outgoing edges where N = number of categories
      (here 2: one for Research, one for Bug Report). EACH classifier edge carries
      `source_category`.
    • The Splitter has EXACTLY M outgoing edges where M = number of specialist
      branches (here 3: Reviewer, Analyst, Writer). Splitter edges are PLAIN —
      no source_category.
    • Classifier branches can terminate at EndNode INDEPENDENTLY (this example
      has two: one via Bug Triage Agent, one via Research Synthesizer). That's
      the classifier exception to "EndNode has exactly 1 incoming".
    • Do NOT put the Splitter on the Bug Report branch unless the user asks
      for it there — match the user's topology exactly.

═══════════════════════════════════════════════════════════
REFLECTION LOOPS — WHEN THE USER ASKS FOR ITERATION
═══════════════════════════════════════════════════════════

Reflection edges are the native way to express iterative refinement, revision
loops, feedback cycles, and self-critique. They are DIFFERENT from sequential
edges and have STRICT direction semantics.

Direction rule — READ THIS CAREFULLY:
  A reflection edge always points FROM the content-producing agent (the one
  whose output is being refined) TO the helper/critic (the one providing
  feedback). Runtime semantics per `reflection_handler`:
      Source Agent → Target Agent (reflection)
                  → Source Agent processes the feedback
                  → continue forward flow from Source
  The TARGET of a reflection edge is a side-channel helper. It receives the
  source's content, emits feedback, and then execution RETURNS to the source.
  The target is NOT part of the main sequential flow.

Reflection-only target agents:
  A reflection helper that only gives feedback (never emits downstream
  output) has NO outgoing edges and NO sequential incoming edges — ONLY a
  reflection incoming edge from its source. This is legal and correct. The
  reachability rule ("every agent must have a path to End") does NOT apply
  to reflection-only targets; they serve their source agent.

How to wire a bounded revision loop (writer refines against a reviewer):
  1. Build the MAIN forward chain with SEQUENTIAL edges — and SKIP the
     reviewer/critic. The reviewer is NOT in the main flow:
       Start → Writer → (next agent after revision, e.g. Fact Checker) → ... → End
  2. Add ONE reflection edge FROM the Writer TO the Reviewer, with
     `max_iterations` and a `reflection_prompt`:
       connect_nodes(source_name="Writer", target_name="Reviewer",
                     edge_type="reflection", max_iterations=2,
                     reflection_prompt="Review the draft and suggest specific "
                                       "improvements on X, Y, and Z so the "
                                       "writer can revise.")
  3. The Reviewer has NO outgoing edges. It's a pure reflection sink.
  4. The Writer has TWO outgoing edges: the reflection edge to the Reviewer
     (internal iteration) AND the sequential edge forward to the next agent
     (main flow continues after the Writer's revision budget is exhausted).

Triggers — phrases that mean "use a reflection edge":
  • "revise until approved / until the reviewer accepts"
  • "iterate N times", "up to N revisions", "up to N cycles"
  • "review and revise", "feedback loop", "refinement loop"
  • "if the critic has issues, send it back to X"
  • "self-critique", "self-review", "polish iteratively"

Self-reflection (an agent critiquing its own output) — source and target are
the same agent, no separate helper needed:
  connect_nodes(source_name="Writer", target_name="Writer",
                edge_type="reflection", max_iterations=3,
                reflection_prompt="Review your draft and improve clarity.")

ANTI-PATTERNS — DO NOT DO ANY OF THESE:
  ❌ Wiring the reflection edge BACKWARDS (Reviewer → Writer). That reverses
     the semantics: the runtime would send the Reviewer's (empty) output to
     the Writer for feedback, which deadlocks. The source of a reflection
     edge must be the agent whose output needs refining.
  ❌ Putting the Reviewer INSIDE the main sequential chain
     (Writer → Reviewer → Fact Checker ...). That makes the Reviewer a
     required hop in forward flow, not a reflection helper. The Reviewer
     should be OFF the main sequential path, receiving only a reflection
     edge from the Writer.
  ❌ Faking a revision loop with a ClassifierAgent "Approved / Needs
     Revision" branch whose "Needs Revision" edge points back to an earlier
     agent. That creates a cycle in SEQUENTIAL edges, which the topological-
     sort executor cannot handle, and has NO iteration cap.
  ❌ Duplicating the writer/reviewer ("Writer", "Writer 2", "Writer 3") to
     simulate iteration. Use ONE pair with a reflection edge and
     `max_iterations` instead.
  ❌ Placing a reflection edge on a DelegateAgent (Delegate → external agent
     or external agent → Delegate). DelegateAgents are internal to a
     GroupChatManager team and can ONLY connect to their manager via
     `delegate` edges. If the user asks to "re-run the risk assessment with
     feedback" and Risk Assessor is a delegate, put the reflection on the
     MANAGER instead: `connect_nodes(source_name=<Manager>, target_name=
     <external reviewer>, edge_type="reflection", max_iterations=N, ...)`.
     The manager re-coordinates all delegates each iteration, so the
     re-assessment happens naturally. Alternatively, if the agent doesn't
     need to be part of a team, promote it to a standalone AssistantAgent
     and wire the reflection edge directly.

Example D — Iterative refinement with a bounded revision loop
  User request: "Draft a blog post, have a reviewer evaluate it, and let the
                 writer revise up to 2 times based on the feedback. Then a
                 fact checker verifies with web search and a final editor
                 polishes the output."
  Tool calls (in order):
    1. add_start_node(prompt="Blog topic and requirements")
    2. add_assistant_agent(name="Draft Writer",
         system_message="You write a compelling draft on the given topic. "
                        "When you receive feedback on a reflection pass, "
                        "revise the draft accordingly before emitting the "
                        "next version.")
    3. add_assistant_agent(name="Critical Reviewer",
         system_message="You are invoked on a reflection edge from the "
                        "Draft Writer. Evaluate the draft on accuracy, "
                        "clarity, and engagement and return specific, "
                        "actionable feedback. You do not emit to downstream "
                        "agents — your feedback goes back to the Writer.")
    4. add_assistant_agent(name="Fact Checker", web_search_enabled=true,
         system_message="You verify every technical claim in the revised "
                        "draft against web-search results and flag any that "
                        "are unsupported or incorrect.")
    5. add_assistant_agent(name="Final Editor",
         system_message="You polish the fact-checked draft for publication: "
                        "tighten prose, fix grammar, ensure flow.")
    6. add_end_node()
    7. connect_nodes(source_name="Start 1",      target_name="Draft Writer")         # sequential
    8. connect_nodes(source_name="Draft Writer", target_name="Critical Reviewer",    # reflection
                     edge_type="reflection", max_iterations=2,
                     reflection_prompt="Review this draft for accuracy, "
                                       "clarity, and engagement, then return "
                                       "specific feedback so the Writer can "
                                       "revise.")
    9. connect_nodes(source_name="Draft Writer", target_name="Fact Checker")         # sequential — main flow continues
   10. connect_nodes(source_name="Fact Checker", target_name="Final Editor")
   11. connect_nodes(source_name="Final Editor", target_name="End 1")
  Resulting in/out counts:
    • Start 1:          out=1, in=0
    • Draft Writer:     out=2 (reflection to Reviewer + sequential to Fact Checker), in=1 (from Start)
    • Critical Reviewer: out=0, in=1 (reflection from Writer only — pure helper)
    • Fact Checker:     out=1, in=1
    • Final Editor:     out=1, in=1
    • End 1:            out=0, in=1
  Key points:
    • NO ClassifierAgent. The revision loop is one reflection edge with
      max_iterations=2 — the executor handles the budget, not a classifier.
    • The Critical Reviewer has ZERO outgoing edges. It is a pure reflection
      sink. Do NOT wire it forward to Fact Checker or EndNode.
    • The MAIN sequential flow is Start → Writer → Fact Checker → Editor → End
      — the Reviewer is off the main path.
    • The reflection edge is Writer → Reviewer (source=content producer,
      target=helper). Never the other way.
    • web_search is on the Fact Checker (the claim-verifier), not elsewhere.
    • max_iterations should match what the user asked for ("up to 2
      revisions" → max_iterations=2).

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

web_search_top_k: 1-20 (default 5). URL mode only — how many RAG chunks to retrieve from the configured URLs per query.

temperature: Controls LLM creativity/randomness (0-2, default 0.7).
  Use lower (0.1-0.3) for factual/analytical tasks, higher (0.8-1.2) for creative tasks.

file_attachments: Independent of doc_tool_calling. For direct LLM file access.

═══════════════════════════════════════════════════════════
MODIFYING EXISTING WORKFLOWS — PRESERVATION IS THE DEFAULT
═══════════════════════════════════════════════════════════

PRESERVATION IS THE DEFAULT. Do NOT delete existing agents unless the user
EXPLICITLY uses one of these HARD-DELETE keywords:
  "remove", "delete", "rebuild", "replace", "start over", "wipe",
  "clear", "from scratch", "redo", "recreate", "get rid of",
  "drop", "take out"

SOFT LANGUAGE IS NOT A DELETE AUTHORIZATION. These phrasings sound like
preferences but MUST NOT trigger a delete:
  "rethink …", "reconsider …", "let's try a different approach",
  "maybe have someone else handle it", "maybe we should …",
  "I'm not loving how X does Y", "X seems redundant",
  "X might be worth trimming", "X could be better",
  "let's improve the …", "this feels off", "not sure about X",
  "what if X did Y instead", "consider replacing"

When you see soft language targeting an existing agent, the CORRECT response is
ALWAYS one of:
  1. `update_node_property` on the named agent — change its system_message,
     llm_model, temperature, or other properties IN PLACE. Its name, ID, and
     incoming/outgoing edges stay the same. This is the default.
  2. `add_assistant_agent` + `connect_nodes` — INSERT a new upstream or
     sibling agent (e.g. a Content Strategist) that complements the existing
     one, without removing anything. Use when the user's ask is "I want more
     of X" or "someone should do Y first".
  3. Ask a clarifying question in your text response instead of tool-calling
     — e.g. "Sounds like you want to change the Writer's role. Do you want
     me to (a) update its system_message to focus on X, or (b) add an
     upstream strategist agent? I won't remove anyone without a direct ask."

DO NOT delete-and-re-add an agent when the user's intent could be satisfied
by an update. Renaming an agent via update_node_property (set `name` to the
new name) preserves the ID and all edges. Deleting "Draft Writer" and adding
"Refined Writer" breaks edges and requires re-wiring, which is strictly worse.

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

Worked example — soft-language edit (from P5):
  Existing canvas: Start → Writer → Reviewer → Fact Checker → Final Editor → End
  User says: "I'm not loving how the Writer produces content — let's rethink
             the approach and maybe have someone else handle it. Also the
             Fact Checker seems redundant, might be worth trimming."
  CORRECT response (tool calls, in order):
    1. update_node_property(node_name="Writer",
         properties={"system_message": "<improved writer system_message>",
                     "llm_model": "<better model if needed>"})
       # Keep the Writer node; refine its role in place.
    2. add_assistant_agent(name="Content Strategist",
         system_message="You plan an outline before the Writer drafts...")
       connect_nodes(source_name="Start 1", target_name="Content Strategist")
       connect_nodes(source_name="Content Strategist", target_name="Writer")
       # "Someone else handle it" interpreted as ADD an upstream collaborator,
       # NOT replace the Writer entirely.
    3. update_node_property(node_name="Fact Checker",
         properties={"system_message": "<narrowed scope, only flags major issues>"})
       # "Seems redundant" is soft language → update scope, don't delete.
    4. In your text response: "I updated the Writer's role and added a
       Content Strategist upstream. I narrowed the Fact Checker's scope
       per your note that it seems redundant — I kept it in the flow since
       you didn't explicitly ask to remove it. Let me know if you'd like
       it gone and I'll delete it."
  WRONG response (what NOT to do):
    ❌ delete_node("Writer") + add_assistant_agent("Refined Writer")
    ❌ delete_node("Reviewer")  # User didn't even mention the Reviewer!
    ❌ delete_node("Fact Checker")  # Soft language is not authorization.

Tools for modifications:
• update_node_property — change a specific agent's settings (including `name`,
  which renames the agent while preserving ID and all edges — prefer this over
  delete+re-add for "rename/replace" soft-language asks)
• delete_node — remove one agent (only when user used a HARD-DELETE keyword
  and the target is unambiguous)
• clear_all_agents — wipe everything except Start/End (only for explicit
  "start over" / "from scratch" / "rebuild" requests)
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

CRITICAL — provider/model selection rules:
• ONLY pick providers from the list above. They are the providers this
  project has API keys for in the API Management settings.
• If you pick a provider that is NOT listed, the agent will FAIL at runtime
  with "Failed to create LLM provider — check project API key configuration".
• If multiple providers are listed, prefer the one that fits the task:
  OpenAI for strong tool-calling and structured outputs; Anthropic for
  long-context reasoning; Google for fast/cheap routing.
• When unsure or the user didn't specify, pick the FIRST provider listed.
• The platform will auto-substitute the first available provider if you pick
  an unconfigured one — but it's better to choose correctly the first time.
• SplitterAgent and ClassifierAgent nodes ONLY make a structured routing/
  allocation decision (which downstream agent(s) get the work, or which
  category applies) — they never generate the user-facing answer. ALWAYS use
  the lightweight model listed above (the one NOT marked "recommended for
  content-generation agents"), regardless of which provider you picked,
  UNLESS the user explicitly asks for higher-quality routing. Using the
  flagship model for these nodes buys no routing-quality improvement but
  measurably slows every single query — 2-3+ extra seconds of pure latency
  before the actual answer even starts being generated.

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

    # Sensible default model per provider when we have to fall back because the
    # LLM picked a provider the project has no API key for. Picked for cheap +
    # reliable tool-calling behavior. gpt-4o-mini was retired from some
    # accounts' catalogs; gpt-5.4-mini is the current equivalent lightweight
    # tier (confirmed live against a real project key).
    _PROVIDER_DEFAULT_MODELS = {
        "openai": "gpt-5.4-mini",
        "anthropic": "claude-3-5-haiku-20241022",
        "google": "gemini-2.0-flash",
    }

    def __init__(
        self,
        available_documents: Optional[List[str]] = None,
        available_providers: Optional[List[str]] = None,
    ):
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.node_name_map: Dict[str, str] = {}  # name → node_id
        self.tool_calls_log: List[Dict[str, Any]] = []
        self.available_documents: List[str] = available_documents or []
        # If empty, no project keys were detected — we don't fall back; let
        # the runtime error speak for itself rather than masking the issue.
        self.available_providers: List[str] = available_providers or []

    def _resolve_provider_and_model(
        self,
        requested_provider: Optional[str],
        requested_model: Optional[str],
    ) -> tuple[str, str]:
        """Map (requested_provider, requested_model) to a (provider, model)
        the project actually has an API key for. If the requested provider
        is available, pass through. Otherwise pick the first available provider
        and substitute its sensible default model. If no providers are
        configured, return the request unchanged so the runtime error is
        clear about the missing key.
        """
        provider = (requested_provider or "").lower().strip() or "openai"
        model = requested_model or self._PROVIDER_DEFAULT_MODELS.get(provider, "")
        if not self.available_providers:
            return provider, model
        if provider in self.available_providers:
            return provider, model
        fallback_provider = self.available_providers[0]
        fallback_model = self._PROVIDER_DEFAULT_MODELS.get(fallback_provider, model)
        logger.info(
            f"🔑 WORKFLOW GEN: requested provider '{provider}' not configured; "
            f"falling back to '{fallback_provider}' / {fallback_model}"
        )
        return fallback_provider, fallback_model

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
            "add_splitter_agent": self._add_splitter_agent,
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
        """Enforce toggle dependency chain: doc_tool_calling → doc_aware, web_search, plan_mode.

        Body extracted to graph_invariants.resolve_toggle_dependencies so the
        save-time serializer can apply the same cascade. This delegate keeps
        the call sites in WorkflowBuilder unchanged.
        """
        from .graph_invariants import resolve_toggle_dependencies
        return resolve_toggle_dependencies(args)

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

    def _expand_and_validate_documents(self, docs: Any) -> tuple:
        """Expand wildcards, then drop any filenames that aren't in the
        project's available_documents registry. Returns (valid, dropped).

        When the registry is empty (no docs uploaded yet), we can't validate
        against anything — pass the expanded list through unchanged so the
        LLM's choice is preserved rather than silently zeroed-out.
        """
        expanded = self._expand_documents(docs)
        if not expanded:
            return [], []
        if not self.available_documents:
            # Nothing to validate against — can't tell if the files are real
            # or phantom. Let the runtime surface the issue at execution time.
            return expanded, []
        available_set = set(self.available_documents)
        valid = [d for d in expanded if isinstance(d, str) and d in available_set]
        dropped = [d for d in expanded if isinstance(d, str) and d not in available_set]
        return valid, dropped

    def _format_dropped_docs_warning(self, dropped: List[str]) -> str:
        """Format a warning message the tool-call LLM can act on after
        phantom filenames are stripped from an agent's document list.
        Shown in the tool result so the LLM can either retry with real
        filenames or switch to doc_aware=true for RAG."""
        if not dropped:
            return ""
        if self.available_documents:
            preview = ", ".join(self.available_documents[:5])
            more = (
                f" (+{len(self.available_documents) - 5} more)"
                if len(self.available_documents) > 5 else ""
            )
            avail_text = f"Available documents: {preview}{more}"
        else:
            avail_text = "The project has no documents uploaded"
        return (
            f" | WARNING: filename(s) not in the project were DROPPED: "
            f"{dropped}. {avail_text}. Either re-specify with exact filenames "
            f"from the available list, OR set doc_aware=true for semantic "
            f"search over all project documents, OR drop the documents "
            f"binding if this agent doesn't need them."
        )

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
        # Expand wildcard "*"/"all" and validate against project registry.
        # Phantom filenames are dropped with a WARNING in the tool result so
        # the LLM can correct course (retry with real names or use doc_aware).
        dropped_docs: List[str] = []
        if "documents" in args:
            valid_docs, dropped_docs = self._expand_and_validate_documents(args.get("documents"))
            args["documents"] = valid_docs
        toggles = self._resolve_toggle_dependencies(args)
        provider, model = self._resolve_provider_and_model(
            args.get("llm_provider", "openai"),
            args.get("llm_model", "gpt-5.3-chat-latest"),
        )
        self.nodes.append({
            "id": node_id,
            "type": "AssistantAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "system_message": args.get("system_message", "You are a helpful AI assistant."),
                "description": args.get("description", f"AI assistant: {name}"),
                "llm_provider": provider,
                "llm_model": model,
                "llm_config": model,
                **toggles,
                "file_attachments_enabled": False,
                "file_attachment_documents": [],
                "inline_file_attachments": [],
                "temperature": args.get("temperature", 0.7),
            }
        })
        self.node_name_map[name] = node_id
        return f"Added AssistantAgent '{name}'" + self._format_dropped_docs_warning(dropped_docs)

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
                **dict(zip(("llm_provider", "llm_model"), self._resolve_provider_and_model(
                    args.get("llm_provider", "openai"),
                    args.get("llm_model", "gpt-5.3-chat-latest"),
                ))),
                "temperature": args.get("temperature", 0.7),
            }
        })
        self.node_name_map[name] = node_id
        return f"Added GroupChatManager '{name}'"

    def _add_delegate_agent(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        # Expand wildcard "*"/"all" and validate against project registry.
        dropped_docs: List[str] = []
        if "documents" in args:
            valid_docs, dropped_docs = self._expand_and_validate_documents(args.get("documents"))
            args["documents"] = valid_docs
        toggles = self._resolve_toggle_dependencies(args)
        provider, model = self._resolve_provider_and_model(
            args.get("llm_provider", "openai"),
            args.get("llm_model", "gpt-5.3-chat-latest"),
        )
        self.nodes.append({
            "id": node_id,
            "type": "DelegateAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "system_message": args.get("system_message", "You are a specialized delegate."),
                "description": f"Delegate: {name}",
                "llm_provider": provider,
                "llm_model": model,
                "llm_config": model,
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
        return (
            f"Added DelegateAgent '{name}'"
            + (f" (connected to {manager_name})" if manager_name else "")
            + self._format_dropped_docs_warning(dropped_docs)
        )

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
        provider, model = self._resolve_provider_and_model(
            args.get("llm_provider", "anthropic"),
            args.get("llm_model", "claude-3-5-haiku-20241022"),
        )
        self.nodes.append({
            "id": node_id,
            "type": "ClassifierAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "description": f"Routes input to one of {len(categories)} categories",
                "categories": categories,
                "llm_provider": provider,
                "llm_model": model,
                "temperature": args.get("temperature", 0.0),
            }
        })
        self.node_name_map[name] = node_id
        cat_list = ", ".join(c["name"] for c in categories)
        return f"Added ClassifierAgent '{name}' with {len(categories)} categories: {cat_list}"

    def _add_splitter_agent(self, args: Dict) -> str:
        node_id = str(uuid.uuid4())
        name = args["name"]
        provider, model = self._resolve_provider_and_model(
            args.get("llm_provider", "openai"),
            args.get("llm_model", "gpt-5.4-mini"),
        )
        self.nodes.append({
            "id": node_id,
            "type": "SplitterAgent",
            "position": {"x": 0, "y": 0},
            "data": {
                "name": name,
                "description": "Splits the input into per-agent subtasks based on downstream agents' system_messages.",
                "llm_provider": provider,
                "llm_model": model,
                "temperature": args.get("temperature", 0.0),
                "overlap_allowed": bool(args.get("overlap_allowed", False)),
            }
        })
        self.node_name_map[name] = node_id
        overlap_note = " (overlap allowed)" if args.get("overlap_allowed") else " (strict partition)"
        return f"Added SplitterAgent '{name}'{overlap_note}. Connect 2+ downstream agents — each one's system_message will be used to decide who gets which subtask."

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
        max_iterations = args.get("max_iterations")
        reflection_prompt = (args.get("reflection_prompt") or "").strip()

        source_id = self.node_name_map.get(source_name)
        target_id = self.node_name_map.get(target_name)

        if not source_id:
            return f"Error: source node '{source_name}' not found"
        if not target_id:
            return f"Error: target node '{target_name}' not found"
        # Self-connections are legal ONLY for reflection edges (self-critique).
        if source_id == target_id and edge_type != "reflection":
            return (
                f"Error: cannot connect a node to itself ('{source_name}') with "
                f"edge_type='{edge_type}'. Self-loops are only legal for "
                f"edge_type='reflection' (self-critique)."
            )

        # Auto-detect delegate type
        source_node = next((n for n in self.nodes if n["id"] == source_id), None)
        target_node = next((n for n in self.nodes if n["id"] == target_id), None)
        source_type = source_node["type"] if source_node else ""
        target_type = target_node["type"] if target_node else ""
        if (source_type == "GroupChatManager" and target_type == "DelegateAgent") or \
           (source_type == "DelegateAgent" and target_type == "GroupChatManager"):
            edge_type = "delegate"

        # DelegateAgent isolation: delegates can ONLY connect to their
        # GroupChatManager (and delegate edges are auto-typed above). Any
        # edge where exactly one endpoint is a DelegateAgent and the other
        # is NOT a GroupChatManager is an invariant violation — delegates
        # are internal to their team and must not have external sequential
        # or reflection edges. Return an error so the verifier/build LLM
        # has to pick a valid pattern (reflect on the Manager instead, or
        # promote the delegate to a standalone AssistantAgent).
        if source_type == "DelegateAgent" and target_type != "GroupChatManager":
            tgt_display = f"'{target_name}' ({target_type})" if target_type else f"'{target_name}'"
            return (
                f"Error: DelegateAgent '{source_name}' cannot connect to "
                f"{tgt_display}. Delegates are internal to their GroupChatManager "
                f"team and can ONLY have edges to/from their manager. If you "
                f"need an iterative-refinement loop that involves this delegate's "
                f"output, put the reflection edge on the MANAGER (source = "
                f"GroupChatManager, target = external reviewer) instead. The "
                f"manager will re-coordinate its delegates on each iteration. "
                f"Alternatively, promote '{source_name}' to a standalone "
                f"AssistantAgent if it doesn't belong to a team."
            )
        if target_type == "DelegateAgent" and source_type != "GroupChatManager":
            src_display = f"'{source_name}' ({source_type})" if source_type else f"'{source_name}'"
            return (
                f"Error: DelegateAgent '{target_name}' cannot be the target of "
                f"an edge from {src_display}. Delegates can ONLY receive edges "
                f"from their GroupChatManager. Wire the edge to/from the "
                f"manager instead, or promote '{target_name}' to a standalone "
                f"AssistantAgent if it doesn't belong to a team."
            )

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
            # Refuse to create an edge with an empty source_handle — the
            # router-wiring check keys categories off their UUID, so a
            # handle-less classifier edge is invisible to it and triggers
            # false-positive "missing category" loops.
            if not source_handle:
                return (
                    f"Error: classifier '{source_name}' category '{source_category}' is missing "
                    f"its stable id — this is an internal data corruption. "
                    f"Recreate the classifier or reset its categories before connecting."
                )

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
        # Reflection edges carry iteration budget + prompt. `reflection_handler`
        # reads these via `connection.get("data", {}).get("max_iterations")`.
        # Mirror them on the top level too for log/diff visibility.
        if edge_type == "reflection":
            try:
                iters = int(max_iterations) if max_iterations is not None else 2
            except (TypeError, ValueError):
                iters = 2
            iters = max(1, min(10, iters))
            edge_obj["max_iterations"] = iters
            edge_obj.setdefault("data", {})["max_iterations"] = iters
            if reflection_prompt:
                edge_obj["reflection_prompt"] = reflection_prompt
                edge_obj["data"]["reflection_prompt"] = reflection_prompt
        self.edges.append(edge_obj)
        suffix_parts = []
        if source_category:
            suffix_parts.append(f"category: {source_category}")
        if edge_type == "reflection":
            suffix_parts.append(f"max_iterations: {edge_obj.get('max_iterations', 2)}")
        suffix = f" [{', '.join(suffix_parts)}]" if suffix_parts else ""
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

        # Handle 'documents' shortcut → sets doc_tool_calling_documents + auto-enables.
        # Expand wildcard "*"/"all" then VALIDATE — phantom filenames are dropped
        # with a warning (returned at the end of the tool result) so the LLM can
        # retry with real filenames or switch to doc_aware for RAG.
        dropped_docs: List[str] = []
        if "documents" in properties:
            valid_docs, dropped_docs = self._expand_and_validate_documents(properties.pop("documents"))
            properties["doc_tool_calling_documents"] = valid_docs
            if valid_docs:
                properties["doc_tool_calling"] = True

        # Apply toggle dependencies if any toggle-related props are updated
        toggle_keys = {"doc_tool_calling", "web_search_enabled", "doc_aware", "web_search_max_results", "web_search_top_k"}
        if toggle_keys & set(properties.keys()):
            merged = {**node["data"], **properties}
            resolved = self._resolve_toggle_dependencies(merged)
            properties.update(resolved)

        # If the LLM is changing llm_provider/llm_model, route through the
        # availability resolver so it can't switch the agent to a provider
        # the project has no API key for.
        if "llm_provider" in properties or "llm_model" in properties:
            current_data = node.get("data", {})
            new_provider = properties.get("llm_provider", current_data.get("llm_provider", "openai"))
            new_model = properties.get("llm_model", current_data.get("llm_model", ""))
            resolved_provider, resolved_model = self._resolve_provider_and_model(new_provider, new_model)
            properties["llm_provider"] = resolved_provider
            properties["llm_model"] = resolved_model

        # ClassifierAgent categories: the LLM passes categories as
        # `[{"name": ..., "description": ...}]` without preserving the
        # existing UUID, which silently orphans every source_handle on
        # outgoing edges. Special-case this: match incoming entries to
        # existing categories by name (case-insensitive) and keep the
        # original id. Assign a fresh UUID only for genuinely new
        # categories; cascade-delete edges whose category was removed.
        category_cascade_note = ""
        if node.get("type") == "ClassifierAgent" and "categories" in properties:
            raw_new = properties.get("categories") or []
            if not isinstance(raw_new, list):
                return "Error: categories must be a list"
            old_cats = node.get("data", {}).get("categories", []) or []
            old_by_name = {
                (c.get("name") or "").strip().lower(): c
                for c in old_cats if c.get("name")
            }
            rebuilt: List[Dict[str, Any]] = []
            seen_names: set = set()
            for i, c in enumerate(raw_new):
                if not isinstance(c, dict):
                    continue
                cname = (c.get("name") or f"Category {i + 1}").strip()
                base = cname
                suffix = 2
                while cname.lower() in seen_names:
                    cname = f"{base} {suffix}"
                    suffix += 1
                seen_names.add(cname.lower())
                existing = old_by_name.get(cname.lower())
                # Preserve: existing id if we matched, incoming id if one
                # was passed AND looks valid, else mint a fresh UUID.
                cid = (existing or {}).get("id") or c.get("id") or str(uuid.uuid4())
                rebuilt.append({
                    "id": cid,
                    "name": cname,
                    "description": (c.get("description") or "").strip(),
                })
            if len(rebuilt) < 2:
                return (
                    f"Error: ClassifierAgent '{node_name}' needs at least 2 categories "
                    f"(got {len(rebuilt)} after normalization)"
                )
            if len(rebuilt) > 10:
                rebuilt = rebuilt[:10]
            # Cascade-delete edges whose source_handle references a removed category.
            kept_ids = {c["id"] for c in rebuilt}
            orphan_edges = [
                e for e in self.edges
                if e.get("source") == node_id
                and e.get("source_handle")
                and e.get("source_handle") not in kept_ids
            ]
            for e in orphan_edges:
                self.edges.remove(e)
            if orphan_edges:
                category_cascade_note = f" (cascade-deleted {len(orphan_edges)} edge(s) for removed categories)"
            properties["categories"] = rebuilt

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

        return (
            f"Updated '{node_name}': {', '.join(updated_keys)}"
            f"{category_cascade_note}"
            + self._format_dropped_docs_warning(dropped_docs)
        )

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

                def _traces_back_to_classifier(src_id, _path=frozenset()):
                    # Per-path cycle guard. Using a frozenset (immutable) ensures
                    # sibling branches don't mutate each other's visited set — a
                    # shared-ancestor (e.g. Splitter feeding several specialists)
                    # must be visitable via each sibling independently.
                    if src_id in _path:
                        return False
                    if node_type_by_id.get(src_id) == "ClassifierAgent":
                        return True
                    upstream = [e for e in self.edges if e["target"] == src_id]
                    if not upstream:
                        return False
                    new_path = _path | {src_id}
                    return all(_traces_back_to_classifier(e["source"], new_path) for e in upstream)

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


def _edge_meta_suffix(edge: Dict[str, Any]) -> str:
    """Format reflection metadata for edge-summary lines shown to LLMs.

    The builder stores `max_iterations` and `reflection_prompt` both at the
    top level and under `edge.data` (to match `reflection_handler`'s reader).
    Surface them in the summary so the verifier and critique LLMs don't think
    they're missing and delete-and-recreate the edge to "fix" it.
    """
    if (edge.get("type") or "sequential") != "reflection":
        return ""
    data = edge.get("data") or {}
    iters = edge.get("max_iterations")
    if iters is None:
        iters = data.get("max_iterations")
    rp = edge.get("reflection_prompt") or data.get("reflection_prompt") or ""
    parts: List[str] = []
    if iters is not None:
        parts.append(f"max_iterations={iters}")
    if rp:
        snippet = rp[:100] + ("…" if len(rp) > 100 else "")
        parts.append(f'reflection_prompt="{snippet}"')
    return f" [{', '.join(parts)}]" if parts else ""


def _has_unwired_classifier_categories(builder: WorkflowBuilder) -> bool:
    """True if any ClassifierAgent has a declared category without an outgoing
    edge wired to it (by source_handle UUID).

    When a classifier's branches are not yet wired, auto-repair can't tell
    which branch any given orphan agent belongs to — running aggressive
    orphan-rescue heuristics in that state produces criss-cross wiring
    (every orphan gets routed through the first Splitter / last agent / etc.,
    regardless of which classifier branch owns it). The caller uses this
    guard to skip the dangerous fixes until after the verifier LLM has
    wired the classifier's categories.
    """
    for node in builder.nodes:
        if node.get("type") != "ClassifierAgent":
            continue
        cats = (node.get("data", {}) or {}).get("categories", []) or []
        cat_ids = {c.get("id") for c in cats if c.get("id")}
        if not cat_ids:
            continue
        wired_handles = {
            e.get("source_handle")
            for e in builder.edges
            if e.get("source") == node["id"] and e.get("source_handle")
        }
        if cat_ids - wired_handles:
            return True
    return False


def _detect_sequential_cycles(builder: WorkflowBuilder) -> List[str]:
    """Run Kahn's algorithm on sequential edges only and report cycles.

    Body extracted to graph_invariants.detect_sequential_cycles so the
    save-time serializer can call the same check. This wrapper keeps the
    AI Builder's existing callers unchanged.
    """
    from .graph_invariants import detect_sequential_cycles
    return detect_sequential_cycles(builder.nodes, builder.edges)


def _check_router_wiring(builder: WorkflowBuilder) -> List[str]:
    """Deterministic pre-flight invariant check on Classifier/Splitter wiring.

    Produces human-readable issue strings the verifier LLM can act on.
    Runs AFTER auto-repair, so it catches problems the auto-repair couldn't
    fix (missing classifier source_categories, under-wired splitters, etc.).

    Invariants checked:
      * ClassifierAgent: outgoing_with_handle count >= number_of_categories,
        and each category name has at least one outgoing edge keyed by its UUID
      * SplitterAgent: outgoing edges count >= 2 to non-Start/End targets
      * Global: no cycles in SEQUENTIAL edges (reflection/delegate excluded)
    """
    issues: List[str] = []
    # Cycle detection runs first — if the graph has a cycle the classifier/
    # splitter-wiring messages below may reference nodes that the LLM then
    # reshapes while closing the cycle. Surfacing the cycle early gives the
    # verifier LLM the top-priority fix.
    issues.extend(_detect_sequential_cycles(builder))
    nodes = builder.nodes
    edges = builder.edges
    name_by_id = {n["id"]: (n.get("data", {}) or {}).get("name", n["id"][:8]) for n in nodes}
    type_by_id = {n["id"]: n.get("type") for n in nodes}

    # Start-node-has-no-outgoing invariant: if the auto-repair Fix 1 deferred
    # because multiple rootless agents exist, make sure the verifier LLM gets
    # told about it so it can pick the right entry point.
    start_node = next((n for n in nodes if n.get("type") == "StartNode"), None)
    if start_node:
        start_has_outgoing = any(e.get("source") == start_node["id"] for e in edges)
        if not start_has_outgoing:
            targets_set = {e.get("target") for e in edges}
            rootless = [
                (n.get("data", {}) or {}).get("name", n["id"][:8])
                for n in nodes
                if n.get("type") not in ("StartNode", "EndNode", "DelegateAgent")
                and n["id"] not in targets_set
            ]
            issues.append(
                f"StartNode has NO outgoing edges. Agents with no incoming "
                f"edges (candidate entry points): {rootless}. Pick the ONE "
                f"agent that should be the workflow's entry point and add "
                f"`connect_nodes(source_name='Start 1', target_name='<that "
                f"agent>')`. Then wire the rest of the main sequential flow "
                f"forward from there."
            )

    # Dead-end invariant: non-End, non-reflection-target, non-Classifier,
    # non-Splitter agents must have at least one outgoing edge. Delegates
    # are excluded (their outgoing is via the `delegate` edge to their
    # manager, which is atypical). Reflection-only targets are legal helpers
    # with no outgoing. Everything else that has no outgoing is a dead-end
    # that drops its output on the floor — the critique/verifier should
    # wire it forward (typically to a branch aggregator or EndNode).
    def _is_reflection_only_target_check(agent_id: str) -> bool:
        incoming = [e for e in edges if e.get("target") == agent_id]
        outgoing = [e for e in edges if e.get("source") == agent_id]
        if outgoing or not incoming:
            return False
        return all((e.get("type") or "sequential") == "reflection" for e in incoming)

    dead_ends: List[str] = []
    for node in nodes:
        ntype = node.get("type")
        if ntype in ("EndNode", "StartNode", "ClassifierAgent", "SplitterAgent", "DelegateAgent"):
            continue
        nid = node["id"]
        has_outgoing = any(e.get("source") == nid for e in edges)
        if has_outgoing:
            continue
        if _is_reflection_only_target_check(nid):
            continue
        dead_ends.append((node.get("data", {}) or {}).get("name", nid[:8]))

    if dead_ends:
        issues.append(
            f"Dead-end agent(s) detected (no outgoing edge, not a reflection "
            f"helper): {dead_ends}. Each must either (a) feed into a branch "
            f"aggregator/synthesizer that reaches EndNode, or (b) be the "
            f"terminal of its classifier branch that connects directly to "
            f"EndNode. Look at what the agent's role is and wire accordingly: "
            f"if it's one of N parallel specialists in a classifier branch, "
            f"route it to the branch's aggregator (e.g. `connect_nodes(source_name="
            f"'<dead-end>', target_name='<aggregator-in-same-branch>')`); if it's "
            f"the last step of its branch, connect to End 1."
        )

    for node in nodes:
        t = node.get("type")
        nid = node["id"]
        name = (node.get("data", {}) or {}).get("name", nid[:8])

        if t == "ClassifierAgent":
            cats = (node.get("data", {}) or {}).get("categories", []) or []
            cat_by_id = {c.get("id"): c.get("name", "?") for c in cats if c.get("id")}
            outgoing = [e for e in edges if e.get("source") == nid]
            # Which category UUIDs have at least one outgoing edge wired?
            wired_cat_ids = {e.get("source_handle") for e in outgoing if e.get("source_handle")}
            missing_cat_names = [
                cat.get("name", "?") for cat in cats
                if cat.get("id") not in wired_cat_ids
            ]
            if missing_cat_names:
                issues.append(
                    f"ClassifierAgent '{name}' has {len(outgoing)} outgoing edges but "
                    f"{len(cats)} categories. Categories with NO outgoing edge: "
                    f"{missing_cat_names}. Add `connect_nodes(source_name='{name}', "
                    f"target_name=<some agent>, source_category='<category name>')` for each "
                    f"missing category."
                )

        elif t == "SplitterAgent":
            outgoing = [
                e for e in edges
                if e.get("source") == nid
                and type_by_id.get(e.get("target")) not in ("StartNode", "EndNode")
            ]
            outgoing_names = [name_by_id.get(e.get("target"), "?") for e in outgoing]
            if len(outgoing) < 2:
                issues.append(
                    f"SplitterAgent '{name}' has only {len(outgoing)} downstream edge(s) — "
                    f"it needs at least 2 specialist agents to allocate work across. Add "
                    f"`connect_nodes(source_name='{name}', target_name=<specialist>)` calls "
                    f"(plain sequential, no source_category) for at least 2 downstream agents."
                )
            # Backwards edges INTO the Splitter from non-upstream sources are almost
            # always a generation bug (LLM reversed the direction, or auto-repair
            # mis-connected a sibling). Upstream is typically a StartNode, a
            # ClassifierAgent branch, or a single feeder agent — anything else is
            # suspicious, especially edges from the splitter's own downstream
            # specialists (that's a cycle).
            for e in edges:
                if e.get("target") != nid:
                    continue
                src_id = e.get("source")
                src_type = type_by_id.get(src_id, "")
                src_name = name_by_id.get(src_id, "?")
                # Cycle: an agent that's also a target of this splitter shouldn't
                # feed back into the splitter.
                if src_id in {e.get("target") for e in outgoing}:
                    issues.append(
                        f"SplitterAgent '{name}' has a BACKWARDS edge from its own "
                        f"downstream agent '{src_name}' → '{name}'. This creates a "
                        f"cycle and must be removed with `delete_edge(source_name="
                        f"'{src_name}', target_name='{name}')`."
                    )
            # Specialists that chain through each other instead of all being direct
            # children of the splitter. Heuristic: if an outgoing target of the
            # splitter has OTHER agents pointing to it (agents that aren't the
            # splitter), AND those agents are also outgoing targets of the splitter,
            # that's a chain pattern (A → B where both should be direct Splitter → A
            # and Splitter → B). Too complex to auto-detect reliably — flag a softer
            # suggestion if Splitter has < 3 outgoing but the graph has > 3 non-router
            # agents, suggesting the LLM may have intended more specialists.
            non_router_agents = [
                n for n in nodes
                if n.get("type") not in ("StartNode", "EndNode", "ClassifierAgent",
                                         "SplitterAgent", "GroupChatManager")
            ]
            # Agents specifically DOWNSTREAM of the splitter (direct or chained)
            # that look like specialists (not the synthesizer).
            def _reachable_from(start_id, visited=None):
                visited = visited if visited is not None else set()
                visited.add(start_id)
                for e in edges:
                    if e.get("source") == start_id and e.get("target") not in visited:
                        _reachable_from(e.get("target"), visited)
                return visited
            reachable_from_splitter = _reachable_from(nid) - {nid}
            splitter_downstream_agents = [
                n for n in non_router_agents if n["id"] in reachable_from_splitter
            ]
            # If there are more reachable-downstream agents than direct outgoing,
            # that means some "specialists" are chained rather than direct.
            if len(outgoing) >= 2 and len(splitter_downstream_agents) > len(outgoing) + 1:
                # +1 tolerance for an expected Synthesizer
                direct_targets = {e.get("target") for e in outgoing}
                chained = [
                    n["data"].get("name", n["id"][:8])
                    for n in splitter_downstream_agents
                    if n["id"] not in direct_targets
                ]
                issues.append(
                    f"SplitterAgent '{name}' has {len(outgoing)} direct outgoing "
                    f"edges ({outgoing_names}) but {len(splitter_downstream_agents)} "
                    f"specialist-like agents are downstream — this suggests some "
                    f"specialists are chained through each other instead of each "
                    f"being a direct child of the splitter. If agents {chained} are "
                    f"meant to be parallel specialists working on their own subtasks, "
                    f"wire them DIRECTLY from '{name}' via "
                    f"`connect_nodes(source_name='{name}', target_name='<specialist>')` "
                    f"and remove any intermediate chaining edges."
                )

    return issues


def _auto_repair_connections(
    builder: WorkflowBuilder,
    recently_deleted: Optional[set] = None,
):
    """
    Fix common connection issues the LLM misses:
    0. Unconnected DelegateAgents → connect to their manager
    1. EndNode has no incoming → connect the last non-End non-Start agent
    2. Agents with no outgoing → connect to the next agent or EndNode
    3. Agents with no incoming → connect from StartNode or previous agent

    `recently_deleted` (optional): set of (source_id, target_id) tuples that
    were just deleted by self-critique. Auto-repair will refuse to recreate
    any edge in this set — critique's surgical decisions should not be
    silently reverted on the next pass.
    """
    recently_deleted = recently_deleted or set()
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

    # If any ClassifierAgent still has unwired categories, the main routing
    # skeleton isn't in place yet — we can't safely tell which branch each
    # orphan agent belongs to. Skip the aggressive orphan-rescue fixes
    # (2, 3, 4, 7b) and let the verifier LLM wire the classifier first.
    # The post-verifier auto-repair pass will run with full branch context.
    classifier_incomplete = _has_unwired_classifier_categories(builder)
    if classifier_incomplete:
        logger.info(
            "🔧 AUTO-REPAIR: ClassifierAgent(s) have unwired categories — "
            "deferring orphan-rescue passes (Fix 2/3/4/7b) to post-verifier sweep."
        )

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
        # Respect self-critique's deletions: if this (source, target) pair was
        # just deleted by the critique LLM, don't recreate it. Prevents the
        # delete/re-add ping-pong that kept undoing legitimate semantic fixes
        # (P2 / P3: critique deleted Start→Competitor Analyst; auto-repair
        # immediately re-added it; critique deleted it again next iteration…).
        if (src_id, tgt_id) in recently_deleted:
            src_name = next((n.get("data", {}).get("name") for n in builder.nodes if n["id"] == src_id), src_id[:8])
            tgt_name = next((n.get("data", {}).get("name") for n in builder.nodes if n["id"] == tgt_id), tgt_id[:8])
            logger.info(
                f"🔧 AUTO-REPAIR: skipped adding {src_name}→{tgt_name} "
                f"— recently deleted by self-critique."
            )
            return False
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

    # ── Router-aware helpers for Fix 2/3 and the specialist-chain cleanup (Fix 6) ──
    splitter_nodes = [n for n in builder.nodes if n["type"] == "SplitterAgent"]
    splitter_ids = {s["id"] for s in splitter_nodes}

    def _name_of(node_id: str) -> str:
        n = next((nn for nn in builder.nodes if nn["id"] == node_id), None)
        return (n.get("data", {}).get("name") if n else node_id[:8]) or node_id[:8]

    def _looks_like_synthesizer(node_id: str) -> bool:
        """Heuristic: name contains a synthesizer keyword, OR has ≥2 incoming edges."""
        node = next((nn for nn in builder.nodes if nn["id"] == node_id), None)
        if not node:
            return False
        if node.get("type") in ("StartNode", "EndNode", "SplitterAgent", "ClassifierAgent"):
            return False
        name = (node.get("data", {}).get("name") or "").lower()
        if any(k in name for k in ("synth", "aggreg", "combin", "merge", "consolid")):
            return True
        incoming_count = sum(1 for e in builder.edges if e["target"] == node_id)
        return incoming_count >= 2

    def _count_wired_classifier_branches() -> int:
        """Total count of ClassifierAgent categories that have at least one
        outgoing edge wired (across all classifiers in the graph)."""
        count = 0
        for n in builder.nodes:
            if n.get("type") != "ClassifierAgent":
                continue
            wired = {
                e.get("source_handle")
                for e in builder.edges
                if e.get("source") == n["id"] and e.get("source_handle")
            }
            count += len(wired)
        return count

    def _find_splitter_parent_for_orphan(orphan_id: str):
        """If the orphan's direct outputs flow into a Synthesizer-style node
        or EndNode AND a Splitter exists, return the Splitter's ID. The orphan
        is almost certainly meant to be a Splitter specialist.

        DISABLED in multi-branch classifier topologies: when a ClassifierAgent
        has 2+ wired branches, the Splitter is owned by just ONE branch, and
        routing orphans from other branches through it produces criss-cross
        wiring (P3 regression: Market Sizer / Industry Comparator from the
        Industry branch got wrongly wired from the Academic Splitter)."""
        if not splitter_nodes:
            return None
        if _count_wired_classifier_branches() >= 2:
            # Multi-branch classifier topology — the Splitter belongs to only
            # one branch, so we cannot safely route cross-branch orphans
            # through it. Let the orphan fall through to sibling-source or
            # stay unwired for the verifier/critique to handle explicitly.
            return None
        # Synthesizers themselves aren't specialists — they're the target the
        # specialists feed into. Without this guard, a temporarily-orphan
        # Synthesizer would get connected directly from the Splitter, bypassing
        # the specialists that are supposed to feed it.
        if _looks_like_synthesizer(orphan_id):
            return None
        for e in builder.edges:
            if e["source"] != orphan_id:
                continue
            tgt_id = e["target"]
            tgt_type = next((n["type"] for n in builder.nodes if n["id"] == tgt_id), None)
            if tgt_type == "EndNode" or _looks_like_synthesizer(tgt_id):
                return splitter_nodes[0]["id"]
        return None

    def _is_splitter_specialist(agent_id: str) -> bool:
        """True if the agent has any direct incoming edge from a SplitterAgent."""
        return any(
            e["target"] == agent_id and e["source"] in splitter_ids
            for e in builder.edges
        )

    def _find_synthesizer_for_splitter_specialist():
        """Find a node that looks like the Synthesizer the Splitter specialists
        should feed into. Returns node_id or None."""
        for n in builder.nodes:
            if n["type"] in ("StartNode", "EndNode", "SplitterAgent", "ClassifierAgent"):
                continue
            if _looks_like_synthesizer(n["id"]):
                return n["id"]
        return None

    # Fix 1: StartNode has no outgoing → connect to the SOLE agent with no
    # incoming. We used to fan-connect Start to every rootless agent, but that
    # produces a Frankenstein Start→N fan-out whenever the LLM forgets to wire
    # the main flow (common with multi-subsystem prompts: manager + HITL +
    # classifier). When multiple rootless agents exist, the entry point is
    # ambiguous — defer to the verifier LLM instead of guessing.
    if start["id"] not in sources and agents:
        entry_candidates = [a for a in agents if a["id"] not in targets]
        if len(entry_candidates) == 1:
            _add_edge(start["id"], entry_candidates[0]["id"])
        elif len(entry_candidates) > 1:
            logger.warning(
                f"🔧 AUTO-REPAIR: Start has no outgoing and "
                f"{len(entry_candidates)} agents have no incoming — ambiguous "
                f"entry point, deferring to verifier LLM. Candidates: "
                f"{[(a.get('data', {}) or {}).get('name', a['id'][:8]) for a in entry_candidates]}"
            )

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

    def _is_reflection_only_target(agent_id):
        """True if the agent only receives reflection edges and has no
        outgoing edges at all. Reflection-only targets are intentional
        helpers — they take content from their source, emit feedback, and
        execution RETURNS to the source. Adding a sequential rescue edge
        to or from them breaks the reflection pattern."""
        incoming = [e for e in builder.edges if e.get("target") == agent_id]
        outgoing = [e for e in builder.edges if e.get("source") == agent_id]
        if outgoing or not incoming:
            return False
        return all((e.get("type") or "sequential") == "reflection" for e in incoming)

    last_agent = agents[-1] if agents else None
    # In multi-branch classifier topologies, `last_agent` is arbitrary —
    # it's just whichever agent happened to be created last, which may
    # belong to a totally different branch from the orphan. Routing an
    # orphan there chains unrelated branches together (P3 regression:
    # Market Sizer [Industry branch] → News Fact Checker [News branch]
    # because NFC was added last). Only fall back to `last_agent` when
    # the topology is single-branch.
    multi_branch = _count_wired_classifier_branches() >= 2
    if not classifier_incomplete:
        for a in agents:
            if a["type"] == "ClassifierAgent":
                continue
            # Reflection-only helpers stay terminal by design — no rescue edge.
            if _is_reflection_only_target(a["id"]):
                continue
            if a["id"] not in sources:
                if _is_classifier_branch(a["id"]):
                    # Classifier branch terminal → goes directly to End
                    _add_edge(a["id"], end["id"])
                elif _is_splitter_specialist(a["id"]):
                    # Splitter specialist with no outgoing → route to Synthesizer
                    # if one exists (NOT last_agent, which in combined graphs is
                    # often an unrelated agent like a Classifier branch target).
                    synth = _find_synthesizer_for_splitter_specialist()
                    if synth and synth != a["id"]:
                        _add_edge(a["id"], synth)
                        logger.info(
                            f"🔧 AUTO-REPAIR: Routed Splitter specialist "
                            f"'{_name_of(a['id'])}' → Synthesizer '{_name_of(synth)}'"
                        )
                    else:
                        _add_edge(a["id"], end["id"])
                elif a == last_agent or multi_branch:
                    # Last agent connects to EndNode; in multi-branch
                    # topologies, all sinkless agents go to End directly
                    # (classifier-branch multi-incoming is allowed by the
                    # End-incoming rule and safer than chaining cross-branch).
                    _add_edge(a["id"], end["id"])
                else:
                    # Earlier agents with no outgoing → connect to last agent
                    _add_edge(a["id"], last_agent["id"])

    # Fix 3: Agents with outgoing but NO incoming (unreachable) → connect from sibling's source or StartNode
    sources = {e["source"] for e in builder.edges}
    targets = {e["target"] for e in builder.edges}
    for a in (agents if not classifier_incomplete else []):
        a_id = a["id"]
        has_incoming = a_id in targets
        if not has_incoming and a_id != start["id"]:
            # Router-aware path A: if the orphan is itself a Synthesizer-style
            # node AND a Splitter exists, fan it in from the Splitter's
            # specialists instead of from the Splitter itself. Synthesizers
            # aggregate the specialists' outputs; they should NOT receive
            # input directly from the upstream router. Without this branch,
            # the sibling-source fallback below would copy a specialist's
            # incoming source (= the Splitter) and mis-wire Splitter → Synth.
            if _looks_like_synthesizer(a_id) and splitter_nodes:
                splitter_id = splitter_nodes[0]["id"]
                splitter_specialists = [
                    e["target"] for e in builder.edges
                    if e["source"] == splitter_id and e["target"] != a_id
                ]
                # Skip specialists that are themselves synthesizers — those are
                # siblings of ours at the wrong layer, not our feeders.
                splitter_specialists = [
                    sp for sp in splitter_specialists
                    if not _looks_like_synthesizer(sp)
                ]
                if splitter_specialists:
                    for sp_id in splitter_specialists:
                        _add_edge(sp_id, a_id)
                    logger.info(
                        f"🔧 AUTO-REPAIR: Fanned '{_name_of(a_id)}' in from "
                        f"{len(splitter_specialists)} Splitter specialist(s) "
                        f"(router-aware synthesizer)"
                    )
                    continue  # Synthesizer handled — skip the rest of Fix 3

            # Router-aware path B: if a Splitter exists and this orphan's outputs
            # flow into a Synthesizer-style node or EndNode, it's almost certainly
            # a Splitter specialist — route from the Splitter directly. This
            # prevents the sibling-source fallback below from propagating chain
            # patterns in combined Classifier + Splitter graphs.
            splitter_parent = _find_splitter_parent_for_orphan(a_id)
            if splitter_parent:
                _add_edge(splitter_parent, a_id)
                logger.info(
                    f"🔧 AUTO-REPAIR: Connected '{_name_of(a_id)}' from Splitter "
                    f"'{_name_of(splitter_parent)}' (router-aware)"
                )
                continue
            # Find where this agent's output goes (its target). EXCLUDE EndNode
            # as an anchor — many agents converge at End (especially in multi-
            # branch topologies where Fix 2 routes all sinkless agents to End),
            # so "sibling sharing End as target" is not a reliable signal of
            # branch kinship. Using End as an anchor causes cross-branch
            # mis-wiring (P3 regression: Literature Searcher [Academic] became
            # parent of Citation Verifier, Competitor Analyst [Industry],
            # Market Sizer [Industry] because they all pointed at End).
            a_targets = [
                e["target"] for e in builder.edges
                if e["source"] == a_id and e["target"] != end["id"]
            ]
            # Find siblings: other agents that also connect to the same target.
            # Skip candidates that would require a source_handle to connect
            # from (ClassifierAgent) — auto-repair's `_add_edge` can't supply
            # that. Same for DelegateAgent (isolation rule).
            def _valid_parent(node_id: str) -> bool:
                t = next((n.get("type") for n in builder.nodes if n["id"] == node_id), None)
                return t not in ("ClassifierAgent", "DelegateAgent")
            sibling_source = None
            for t in a_targets:
                for e in builder.edges:
                    if e["target"] == t and e["source"] != a_id:
                        # This is a sibling — find who feeds that sibling
                        for e2 in builder.edges:
                            if e2["target"] == e["source"] and e2["source"] != a_id and _valid_parent(e2["source"]):
                                sibling_source = e2["source"]
                                break
                        if not sibling_source and _valid_parent(e["source"]):
                            sibling_source = e["source"]
                    if sibling_source:
                        break
                if sibling_source:
                    break
            if sibling_source:
                _add_edge(sibling_source, a_id)
                logger.info(f"🔧 AUTO-REPAIR: Connected unreachable '{a['data'].get('name', '?')}' from sibling's source")
            elif multi_branch:
                # In multi-branch topologies, Start→orphan is semantically
                # wrong (the orphan belongs to a classifier branch, not as a
                # Start-direct child). Leave it unwired and let the verifier/
                # critique handle it on the next pass.
                logger.warning(
                    f"🔧 AUTO-REPAIR: '{a['data'].get('name', '?')}' is orphan in a "
                    f"multi-branch graph — leaving unwired (verifier/critique "
                    f"should place it in a classifier branch)."
                )
            else:
                _add_edge(start["id"], a_id)
                logger.info(f"🔧 AUTO-REPAIR: Connected unreachable '{a['data'].get('name', '?')}' from StartNode")

    # Fix 4: EndNode still has no incoming → connect from last agent
    # Gated: when classifier branches are unwired, "last agent" is arbitrary
    # (often a branch-specific terminator that shouldn't be a global End feeder).
    end_incoming = [e for e in builder.edges if e["target"] == end["id"]]
    if not classifier_incomplete and len(end_incoming) == 0 and last_agent:
        _add_edge(last_agent["id"], end["id"])

    # Fix 5: EndNode has multiple incoming (>1) → enforce "one terminal per
    # classifier branch" rule.
    # Rule: EndNode may have multiple incoming only when each edge originates
    # from a DIFFERENT ClassifierAgent branch (identified by classifier node
    # + source_handle). Two agents in the SAME branch both terminating at End
    # is a violation — they must funnel through a single synthesizer/terminal.
    # Implemented as a local helper so we can invoke it TWICE: once here to
    # consolidate edges added by Fix 2, and once at the very end (after Fix
    # 7b's final sweep) to consolidate any edges Fix 7b re-added.
    def _consolidate_end_incoming():
        end_incoming = [e for e in builder.edges if e["target"] == end["id"]]
        if len(end_incoming) <= 1:
            return
        node_type_by_id = {n["id"]: n["type"] for n in builder.nodes}

        def _trace_classifier_branches(src_id: str, _path: frozenset = frozenset()) -> list:
            """Return the set of (classifier_id, source_handle) branch keys
            that src_id descends from. A node can descend from multiple
            branches if it's a fan-in synthesizer — we collect all of them.
            Empty list means src_id doesn't trace to any classifier branch.
            """
            if src_id in _path:
                return []
            new_path = _path | {src_id}
            upstream = [e for e in builder.edges if e["target"] == src_id
                        and (e.get("type") or "sequential") != "reflection"]
            if not upstream:
                return []
            branches: list = []
            for e in upstream:
                src = e["source"]
                if node_type_by_id.get(src) == "ClassifierAgent":
                    # Direct branch edge — key is (classifier_id, source_handle)
                    branches.append((src, e.get("source_handle")))
                else:
                    branches.extend(_trace_classifier_branches(src, new_path))
            # dedup
            return list({b for b in branches})

        def _chain_depth(src_id: str, _path: frozenset = frozenset(), _depth: int = 0) -> int:
            """Depth of the longest upstream chain back to a classifier or
            unreached root. Used to pick the 'most downstream' terminal for a
            given branch (preferring synthesizers over early specialists)."""
            if src_id in _path or _depth > 50:
                return _depth
            upstream = [e for e in builder.edges if e["target"] == src_id
                        and (e.get("type") or "sequential") != "reflection"]
            if not upstream:
                return _depth
            new_path = _path | {src_id}
            return max(
                _chain_depth(e["source"], new_path, _depth + 1)
                for e in upstream
            )

        # Group End-incomings by the (classifier, handle) pair they trace to.
        # Edges tracing to multiple branches (a fan-in synthesizer) get a
        # special "multi-branch" bucket we keep as-is (one edge per synth).
        branch_to_edges: dict = {}
        no_branch_edges = []
        for e in end_incoming:
            branches = _trace_classifier_branches(e["source"])
            if not branches:
                no_branch_edges.append(e)
            elif len(branches) == 1:
                branch_to_edges.setdefault(branches[0], []).append(e)
            else:
                # multi-branch fan-in (e.g. a synthesizer merging two branches) —
                # keep it in its own bucket, indexed by the frozenset of branches
                key = frozenset(branches)
                branch_to_edges.setdefault(key, []).append(e)

        any_removed = False
        for key, candidates in branch_to_edges.items():
            if len(candidates) <= 1:
                continue
            # Keep the End-incoming whose source has the LONGEST upstream chain
            # back to the classifier (the most downstream / aggregator-like).
            candidates_with_depth = [(c, _chain_depth(c["source"])) for c in candidates]
            candidates_with_depth.sort(key=lambda x: x[1], reverse=True)
            keep = candidates_with_depth[0][0]
            for c, _ in candidates_with_depth[1:]:
                if c in builder.edges:
                    builder.edges.remove(c)
                    any_removed = True
                    # Rather than leaving c["source"] as a dead-end (0 outgoing),
                    # reroute it to the kept branch terminal so its output
                    # feeds into the branch's aggregator. This is semantically
                    # correct for parallel specialists in a classifier branch
                    # (e.g. Competitor Analyst AND Market Sizer both feeding
                    # Industry Selector, which picks the better one).
                    # Only reroute if c["source"] doesn't already reach keep
                    # (avoid redundant edges), and the reroute wouldn't close
                    # a cycle (check: is keep["source"] upstream of c["source"]?).
                    c_src = c["source"]
                    keep_src = keep["source"]
                    c_src_has_keep_downstream = any(
                        e["source"] == c_src and e["target"] == keep_src
                        for e in builder.edges
                    )
                    # Cycle-safety: keep's source must not already be an
                    # ancestor of c's source in sequential edges.
                    def _is_ancestor(maybe_ancestor, descendant, _seen=None):
                        _seen = _seen or set()
                        if maybe_ancestor in _seen:
                            return False
                        _seen.add(maybe_ancestor)
                        for e in builder.edges:
                            if e["source"] != maybe_ancestor:
                                continue
                            if (e.get("type") or "sequential") == "reflection":
                                continue
                            if e["target"] == descendant:
                                return True
                            if _is_ancestor(e["target"], descendant, _seen):
                                return True
                        return False
                    creates_cycle = _is_ancestor(keep_src, c_src)
                    if c_src != keep_src and not c_src_has_keep_downstream and not creates_cycle:
                        _add_edge(c_src, keep_src)
                        logger.info(
                            f"🔧 AUTO-REPAIR: consolidated End-incoming — rerouted "
                            f"{_name_of(c_src)} → '{_name_of(keep_src)}' "
                            f"(instead of leaving it as a dead-end after removing its "
                            f"direct edge to End; branch agents should funnel through "
                            f"a single terminal per branch)."
                        )
                    else:
                        logger.info(
                            f"🔧 AUTO-REPAIR: consolidated End-incoming — removed "
                            f"{_name_of(c_src)} → End (same classifier branch "
                            f"as kept '{_name_of(keep_src)}'). Branch agents "
                            f"should funnel through a single terminal per branch."
                        )

        # Handle non-classifier-tracing edges (plain DAG terminators). Standard
        # rule: keep only one (prefer last_agent, else last-added).
        if len(no_branch_edges) > 1:
            preferred = None
            if last_agent:
                preferred = next((e for e in no_branch_edges if e["source"] == last_agent["id"]), None)
            if not preferred:
                preferred = no_branch_edges[-1]
            for e in no_branch_edges:
                if e is not preferred and e in builder.edges:
                    builder.edges.remove(e)
                    any_removed = True
                    logger.info(f"🔧 AUTO-REPAIR: Removed extra EndNode edge {e['id']}")

        if not any_removed:
            logger.info(
                f"🔧 AUTO-REPAIR: Keeping all {len(end_incoming)} EndNode incoming "
                f"edges (each originates from a distinct classifier branch)"
            )

    # First consolidation pass — cleans up duplicate branch terminals added by
    # Fix 2. A second pass runs after Fix 7b (final sweep) so any edges Fix 7b
    # re-adds on sinkless agents get consolidated on the way out.
    _consolidate_end_incoming()

    # ── Fix 6: Router-aware cleanup (runs last, after all other fixes) ──
    # 6a: Specialist chain cleanup. If Splitter → A AND Splitter → B AND there's
    # an edge A → B (or B → A) between them, the inter-specialist edge is almost
    # always a leftover from the LLM's initial chained output — Splitter
    # specialists should run in parallel, not in series. Delete the chain edges.
    # IMPORTANT: EXCLUDE Synthesizer-like nodes from "specialists" — those are
    # aggregators, not parallel workers, and Specialist → Synthesizer edges
    # must be preserved as the fan-in wiring.
    for splitter in splitter_nodes:
        direct_children = {
            e["target"] for e in builder.edges if e["source"] == splitter["id"]
        }
        # Synthesizers/aggregators are not specialists even if the verifier
        # incorrectly added a Splitter → Synthesizer edge. Their role is to
        # collect specialist outputs, so they must be excluded from the
        # chain-cleanup set to avoid stripping legitimate fan-in edges.
        specialists_only = {
            cid for cid in direct_children if not _looks_like_synthesizer(cid)
        }
        chain_edges = [
            e for e in builder.edges
            if e["source"] in specialists_only
            and e["target"] in specialists_only
            and e["source"] != splitter["id"]
        ]
        for e in chain_edges:
            builder.edges.remove(e)
            logger.info(
                f"🔧 AUTO-REPAIR: removed chain edge between Splitter specialists "
                f"({_name_of(e['source'])} → {_name_of(e['target'])})"
            )

    # 6b: Backwards edges INTO a Splitter from its own downstream agents (cycle).
    # The LLM occasionally reverses direction during initial generation.
    for splitter in splitter_nodes:
        direct_children = {
            e["target"] for e in builder.edges if e["source"] == splitter["id"]
        }
        backwards_edges = [
            e for e in builder.edges
            if e["target"] == splitter["id"] and e["source"] in direct_children
        ]
        for e in backwards_edges:
            builder.edges.remove(e)
            logger.info(
                f"🔧 AUTO-REPAIR: removed backwards edge into Splitter "
                f"({_name_of(e['source'])} → {_name_of(e['target'])})"
            )

    # 6c: Remove direct Splitter → Synthesizer edges. Synthesizers aggregate
    # specialists' outputs; the Splitter must not feed them directly, or the
    # fan-in pattern collapses. The verifier occasionally mis-adds this edge
    # when trying to address router-wiring warnings.
    for splitter in splitter_nodes:
        bad_edges = [
            e for e in builder.edges
            if e["source"] == splitter["id"] and _looks_like_synthesizer(e["target"])
        ]
        for e in bad_edges:
            builder.edges.remove(e)
            logger.info(
                f"🔧 AUTO-REPAIR: removed Splitter → Synthesizer direct edge "
                f"({_name_of(e['source'])} → {_name_of(e['target'])})"
            )

    # 6d: Remove Splitter → X edges where X belongs to a different router
    # branch (its incoming includes a ClassifierAgent). Those targets live in
    # a sibling branch of the classifier, not downstream of this splitter.
    classifier_ids_local = {n["id"] for n in builder.nodes if n["type"] == "ClassifierAgent"}
    for splitter in splitter_nodes:
        bad_edges = [
            e for e in builder.edges
            if e["source"] == splitter["id"] and any(
                e2["target"] == e["target"] and e2["source"] in classifier_ids_local
                for e2 in builder.edges
            )
        ]
        for e in bad_edges:
            builder.edges.remove(e)
            logger.info(
                f"🔧 AUTO-REPAIR: removed Splitter → classifier-branch-target edge "
                f"({_name_of(e['source'])} → {_name_of(e['target'])})"
            )

    # ── Fix 7: Terminal integrity sweep (runs last) ──
    # 7a: EndNode is terminal — it must never have outgoing edges. LLM-produced
    # cycles back from End occasionally sneak through earlier fixes.
    end_outgoing = [e for e in builder.edges if e["source"] == end["id"]]
    for e in end_outgoing:
        builder.edges.remove(e)
        logger.info(
            f"🔧 AUTO-REPAIR: removed outgoing edge from EndNode "
            f"({_name_of(e['source'])} → {_name_of(e['target'])})"
        )

    # 7b: Any remaining agent with no outgoing edges → route forward.
    # Earlier fixes (2, 5, 6) can leave an agent stranded if an edge was removed
    # during deduplication or chain-cleanup. This final sweep guarantees every
    # non-Classifier agent has a forward path.
    # Router-aware: Splitter specialists prefer the Synthesizer over End so the
    # fan-in aggregation is preserved; everyone else goes straight to End.
    # EXCEPTION: reflection-only target agents (helpers that only receive a
    # reflection edge from a source content-producer and have no outgoing
    # edges) are intentionally terminal. Their feedback goes back to the
    # source via the reflection handler — they do NOT belong on the main
    # sequential path and must NOT be rescued with a forward edge.
    sources = {e["source"] for e in builder.edges}
    # When classifier branches are still unwired, we don't know which branch
    # each sinkless agent belongs to — defer this sweep to the post-verifier pass.
    if not classifier_incomplete:
        for a in agents:
            if a["type"] == "ClassifierAgent":
                continue
            if a["id"] in sources:
                continue
            if _is_reflection_only_target(a["id"]):
                continue
            if _is_splitter_specialist(a["id"]) and not _looks_like_synthesizer(a["id"]):
                synth = _find_synthesizer_for_splitter_specialist()
                if synth and synth != a["id"]:
                    _add_edge(a["id"], synth)
                    logger.info(
                        f"🔧 AUTO-REPAIR: final sweep — connected Splitter specialist "
                        f"'{_name_of(a['id'])}' → Synthesizer '{_name_of(synth)}'"
                    )
                    continue
            _add_edge(a["id"], end["id"])
            logger.info(
                f"🔧 AUTO-REPAIR: final sweep — connected '{_name_of(a['id'])}' → End "
                f"(no outgoing edges after earlier fixes)"
            )

    # Second End-incoming consolidation pass. Fix 7b above may have re-added
    # edges to End that the earlier Fix-5 pass tried to remove (classic cat-
    # and-mouse: 7b sees an agent with no outgoing and wires it to End; but if
    # that agent's branch already had a terminal, it's now a duplicate). This
    # second pass is final — it runs after all other fixes so whatever ends
    # up at End is our authoritative answer.
    _consolidate_end_incoming()

    # Fix 8: final cycle safety check. The sibling-source heuristic (Fix 3)
    # and other rescues can inadvertently close a cycle on sequential edges
    # (e.g. Fix 3 added A → B while B → A already existed, producing a
    # 2-node cycle). Since cycle detection only runs inside
    # `_check_router_wiring` BEFORE the post-critique auto-repair, cycles
    # introduced here would otherwise escape into the final graph.
    # Strategy: detect a sequential cycle and remove the most-recently-appended
    # sequential edge that participates in it, until the cycle is broken.
    # Reflection and delegate edges are excluded (they're legal back-edges).
    max_removals = 10  # Safety cap — should never need this many in practice.
    while max_removals > 0 and _detect_sequential_cycles(builder):
        max_removals -= 1
        removed_one = False
        for edge in list(reversed(builder.edges)):
            if (edge.get("type") or "sequential") != "sequential":
                continue
            # Protect mission-critical edges we just added: Start → entry, and
            # classifier-branch edges (source_handle present) which the verifier
            # LLM specifically wired.
            if edge.get("source") == start["id"]:
                continue
            if edge.get("source_handle"):
                continue
            builder.edges.remove(edge)
            if not _detect_sequential_cycles(builder):
                logger.warning(
                    f"🔧 AUTO-REPAIR: removed cycle-closing sequential edge "
                    f"{_name_of(edge['source'])} → {_name_of(edge['target'])} "
                    f"(introduced during repair)"
                )
                removed_one = True
                break
            # Undo the try — put the edge back at its original tail position.
            builder.edges.append(edge)
        if not removed_one:
            # Couldn't break the cycle with safe removals — log and give up
            # so the verifier LLM (which runs after) can fix it.
            logger.error(
                "🔧 AUTO-REPAIR: could not break sequential cycle via safe "
                "edge removal; leaving for the verifier LLM to resolve."
            )
            break


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


# ── User-context formatter (used by verifier + self-critique) ──────────


def _format_user_context(
    conversation_history: Optional[List[Dict[str, str]]],
    user_message: str,
) -> str:
    """Package the full prior conversation history + the current user
    message into one labelled block for embedding in a verifier or
    self-critique prompt.

    The verifier and self-critique calls don't replay `conversation_history`
    as native message turns (they're framed as fresh reviews, not chat
    continuations). Without this helper they used to receive only a
    truncated `user_message[:N]` quote and zero prior context — so any
    constraint expressed in an earlier turn (or past the truncation point)
    was invisible to them. This helper hands them the entire conversation
    verbatim so they can spot regressions against any prior constraint.

    `conversation_history` is a flat chronological list of
    `{role, content}` dicts from prior turns. `user_message` is the
    current turn (not yet in history).
    """
    lines: List[str] = []
    turn = 0
    if conversation_history:
        lines.append(
            "=== PRIOR CONVERSATION (full history of this AI Builder session) ==="
        )
        for entry in conversation_history:
            role = (entry.get("role") or "").strip().lower()
            content = (entry.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                turn += 1
                lines.append("")
                lines.append(f"[Turn {turn}] USER:")
                lines.append(content)
            elif role == "assistant":
                lines.append("")
                lines.append(f"[Turn {turn or 1}] ASSISTANT:")
                lines.append(content)
            else:
                lines.append("")
                lines.append(f"[Turn {turn or 1}] {role.upper() or 'UNKNOWN'}:")
                lines.append(content)
        lines.append("")
    current_turn = turn + 1 if turn else 1
    lines.append(f"=== CURRENT USER REQUEST (turn {current_turn}) ===")
    lines.append(user_message)
    return "\n".join(lines)


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
    available_providers: List[str] = []  # Project actually has API keys for these
    # Static fallback only — used when the live model fetch below fails (e.g.
    # network hiccup, invalid key). Kept intentionally generic/stale-tolerant
    # since it's a last resort, not the primary source of truth anymore.
    provider_models_fallback = {
        "openai": "gpt-5.3-chat-latest (recommended), gpt-5.4-mini",
        "anthropic": "claude-sonnet-4-20250514, claude-3-5-haiku-20241022",
        "google": "gemini-2.5-flash, gemini-2.0-flash",
    }
    provider_labels = {"openai": "OpenAI", "anthropic": "Anthropic", "google": "Google"}

    from agent_orchestration.dynamic_models_service import dynamic_models_service

    try:
        from project_api_keys.services import ProjectAPIKeyService
        key_service = ProjectAPIKeyService()
        for provider_name in provider_models_fallback.keys():
            key = await sync_to_async(key_service.get_project_api_key)(project, provider_name)
            if not key:
                continue
            available_providers.append(provider_name)
            label = provider_labels.get(provider_name, provider_name.capitalize())

            # Pick a flagship (content-generation) and a lightweight (routing)
            # model from the project's ACTUAL live model list, rather than a
            # hardcoded string that inevitably goes stale as providers ship
            # new model families. Falls back to the static hint on any error.
            try:
                models = await dynamic_models_service.get_models_for_provider(
                    provider_name, project=project,
                )
                flagship = next(
                    (m for m in models if m.recommended_for and 'AssistantAgent' in m.recommended_for),
                    None,
                )
                lightweight = next(
                    (m for m in models if m.recommended_for and 'SplitterAgent' in m.recommended_for),
                    None,
                )
                if flagship and lightweight and flagship.id != lightweight.id:
                    models_str = (
                        f"{flagship.id} (recommended for content-generation agents), "
                        f"{lightweight.id} (recommended for SplitterAgent/ClassifierAgent "
                        f"routing — fast + cheap, sufficient for structured allocation/"
                        f"category decisions)"
                    )
                elif flagship:
                    models_str = f"{flagship.id} (recommended)"
                else:
                    models_str = provider_models_fallback[provider_name]
            except Exception as model_fetch_err:
                logger.warning(
                    f"⚠️ WORKFLOW GEN: Live model fetch failed for {provider_name}, "
                    f"using static fallback: {model_fetch_err}"
                )
                models_str = provider_models_fallback[provider_name]

            available_models_lines.append(f"- {label}: {models_str}")
    except Exception as e:
        logger.warning(f"⚠️ WORKFLOW GEN: Could not check API keys: {e}")
        # Fallback when key lookup crashes: assume all three are available so
        # we don't block the LLM. Runtime errors will be visible if a chosen
        # provider has no key.
        available_providers = list(provider_models_fallback.keys())
        for provider_name, models_str in provider_models_fallback.items():
            available_models_lines.append(f"- {provider_name.capitalize()}: {models_str}")

    if not available_models_lines:
        available_models_lines.append("No LLM providers configured. Use openai as default.")
    logger.info(f"🔑 WORKFLOW GEN: available providers for project = {available_providers}")

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
            cw_lines.append(f"  - {src} → {tgt} ({e.get('type', 'sequential')}){handle_suffix}{_edge_meta_suffix(e)}")
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
    # Also pass available_providers so handlers can fall back to a provider
    # the project actually has an API key for.
    available_doc_filenames = [d.original_filename for d in project_docs]
    builder = WorkflowBuilder(
        available_documents=available_doc_filenames,
        available_providers=available_providers,
    )
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

    # If nodes exist but no SEQUENTIAL edges, explicitly ask the LLM to create
    # connections. We only count sequential edges because `add_delegate_agent`
    # auto-creates a delegate edge to its manager, which would otherwise mask
    # a fully-unwired main flow (observed in the P2 manager+HITL+classifier
    # prompt: 3 delegate edges existed, zero sequential, retry silently
    # skipped, auto-repair produced a Frankenstein graph).
    sequential_edge_count = sum(
        1 for e in builder.edges
        if (e.get("type") or "sequential") == "sequential"
    )
    if builder.nodes and sequential_edge_count == 0:
        node_names = [n["data"]["name"] for n in builder.nodes]
        delegate_edge_count = sum(1 for e in builder.edges if e.get("type") == "delegate")
        delegate_note = (
            f"Your {delegate_edge_count} delegate edge(s) to the GroupChatManager are "
            f"already in place — do NOT recreate them. "
        ) if delegate_edge_count else ""
        logger.info(
            f"⚠️ WORKFLOW GEN: {len(builder.nodes)} nodes but 0 sequential edges "
            f"({delegate_edge_count} delegate edges present) — requesting connections"
        )
        messages.append({
            "role": "user",
            "content": (
                f"You created these nodes but forgot to wire the main sequential "
                f"flow: {', '.join(node_names)}. {delegate_note}"
                "Now call connect_nodes for EVERY sequential connection that forms the "
                "main flow. Remember:\n"
                "- Start 1 must connect to exactly ONE first agent (the entry point)\n"
                "- Every non-reflection agent must have a forward path toward End 1\n"
                "- A GroupChatManager needs a sequential outgoing edge to the next "
                "agent in the main flow (its delegate edges are INTERNAL to the team)\n"
                "- A ClassifierAgent must wire EVERY category with source_category\n"
                "- EndNode receives exactly ONE incoming connection (classifier "
                "branches are the only exception)\n"
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

    # Phase 3 (Verify) instrumentation — counters for EXP_METRIC_WORKFLOW_VERIFY.
    _verify_t_start = time.time()
    _verifier_iterations = 0
    _verifier_tool_calls = 0

    # Pre-flight router-wiring invariants — surface any classifier/splitter
    # wiring gaps as concrete issues the verifier agent must fix.
    router_issues = _check_router_wiring(builder)
    if router_issues:
        logger.warning(
            f"⚠️ WORKFLOW GEN: router wiring issues detected after auto-repair: {router_issues}"
        )

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
                graph_desc_lines.append(f"  {src} → {tgt} ({e.get('type', 'sequential')}){handle_suffix}{_edge_meta_suffix(e)}")
            graph_desc = "\n".join(graph_desc_lines)

            _plan_block = f"Original plan from the planning phase:\n{plan_text}\n\n" if plan_text else ""
            _issues_block = ""
            if router_issues:
                _issues_block = (
                    "⚠️ KNOWN ROUTER-WIRING ISSUES that MUST be fixed before you return "
                    "'Verification passed' — these are concrete problems detected by the "
                    "pre-flight check:\n"
                    + "\n".join(f"  • {issue}" for issue in router_issues)
                    + "\n\nFix each item above using the appropriate tool (connect_nodes "
                    "for missing edges, etc.) BEFORE reporting verification as passed.\n\n"
                )
            verify_prompt = (
                f"You are verifying a workflow that was just built. Here is the current state:\n\n"
                f"{graph_desc}\n\n"
                f"{_plan_block}"
                f"{_issues_block}"
                f"{_format_user_context(conversation_history, user_message)}\n\n"
                "VERIFY the following and FIX any issues using the available tools:\n"
                "1. Does the orchestration make sense for the user's request? Are the right agents created with the right roles?\n"
                "2. Are all connections valid? Does information flow logically from source to destination?\n"
                "3. Is every agent reachable from StartNode? Does exactly one agent connect to EndNode "
                "(exception: multiple branches from a ClassifierAgent MAY each terminate at EndNode; "
                "reflection-only target agents — agents receiving only a reflection edge and having "
                "no outgoing edges — are side-channel helpers and do NOT need a path to EndNode)?\n"
                "3b. For every reflection edge, verify the DIRECTION is correct: source = the "
                "content-producing agent being refined; target = the helper/critic providing feedback. "
                "If an edge is reversed (e.g. Reviewer → Writer reflection), delete and recreate it "
                "the correct way (Writer → Reviewer reflection). The reflection target should have "
                "NO outgoing edges and should NOT appear on the main sequential flow.\n"
                "4. Are web_search / doc_tool_calling / documents / doc_aware assigned correctly per each agent's role?\n"
                "5. Are system_messages detailed enough for each agent to do its job?\n"
                "6. Are LLM models and temperatures appropriate for each agent's task?\n"
                "7. For any ClassifierAgent: (a) 2-10 categories with unique non-empty names "
                "and clear descriptions; (b) EVERY category MUST have at least one outgoing "
                "edge wired via `connect_nodes` with `source_category=<category name>`. A "
                "classifier with N categories MUST have at least N outgoing edges. If the "
                "count is off, FIX IT now — add the missing `connect_nodes(source_name=<classifier>, "
                "target_name=<some agent>, source_category=<category name>)` calls. Every "
                "category branch leads somewhere meaningful (not dangling).\n"
                "8. For any SplitterAgent: MUST have at least 2 outgoing edges to specialist "
                "agents (plain `connect_nodes` — NO source_category). Each downstream specialist "
                "should have a descriptive system_message so the splitter can route work by role. "
                "If the splitter has 0 or 1 outgoing edges, ADD the missing connections now.\n"
                "9. Did you remove existing agents? If yes, did the user EXPLICITLY request "
                "removal using a HARD-DELETE keyword (remove, delete, rebuild, replace, "
                "start over, wipe, clear, from scratch, get rid of, drop, take out)? "
                "Soft language — 'rethink', 'reconsider', 'maybe have someone else', "
                "'not loving X', 'X seems redundant', 'X might be worth trimming', "
                "'let's improve', 'consider replacing' — is NOT authorization to delete. "
                "If you removed agents on soft language, that is a regression — RESTORE "
                "them via add_assistant_agent (or the appropriate add_*) + connect_nodes, "
                "and instead use update_node_property to update their system_message/name "
                "in place. Renaming via update_node_property(name=...) preserves the ID "
                "and all edges — always prefer that to delete+re-add.\n"
                + ("10. Did the build follow the plan above? Note any drift and fix it.\n\n" if plan_text else "\n")
                + "If everything looks correct, respond with 'Verification passed — workflow is valid.'\n"
                "If there are issues, use update_node_property, delete_node, connect_nodes, or add_* tools to fix them.\n"
                "Do NOT rebuild the workflow from scratch — only fix specific issues."
            )

            verify_messages = [{"role": "system", "content": system_content}]
            verify_messages.append({"role": "user", "content": verify_prompt})

            logger.info(f"🔍 WORKFLOW GEN: Running verification agent on {len(v_nodes)} nodes, {len(v_edges)} edges")

            # Bumped from 3 to 6 — complex combined-router workflows routinely
            # need multiple rounds of fixes (delete backwards edges, add
            # classifier source_categories, rewire chained specialists, etc.).
            for v_iter in range(6):
                _verifier_iterations = v_iter + 1
                v_response = await llm_provider.generate_response(messages=verify_messages, tools=WORKFLOW_TOOLS)
                if v_response.error:
                    logger.warning(f"⚠️ WORKFLOW GEN: Verification agent error: {v_response.error}")
                    break
                if v_response.text:
                    explanation += f"\n\n**Verification:** {v_response.text}"
                    logger.info(f"🔍 WORKFLOW GEN: Verification agent: {v_response.text[:200]}")
                if not v_response.tool_calls:
                    break
                _verifier_tool_calls += len(v_response.tool_calls)
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

                # After tool calls, re-check the pre-flight router-wiring
                # invariants and feed any REMAINING issues back to the
                # verifier so it keeps fixing until the graph is clean.
                _remaining = _check_router_wiring(builder)
                if _remaining:
                    verify_messages.append({
                        "role": "user",
                        "content": (
                            "The pre-flight check STILL reports these router-wiring "
                            "issues after your last round of fixes. Address each "
                            "one now — call the appropriate tools (connect_nodes, "
                            "delete_edge, rewire_edge) and do not respond with "
                            "'Verification passed' until every item below is resolved:\n"
                            + "\n".join(f"  • {i}" for i in _remaining)
                        ),
                    })

        except Exception as verify_err:
            logger.warning(f"⚠️ WORKFLOW GEN: Verification agent failed: {verify_err}")

        # Post-verifier auto-repair: the verifier LLM can call delete_edge /
        # rewire_edge while "fixing" router wiring, which may re-introduce the
        # problems auto-repair already handled (End → X cycles, agents with no
        # outgoing, orphan specialists). Re-run auto-repair so the terminal
        # integrity sweep (Fix 7) catches any post-verifier damage.
        logger.info("🔧 WORKFLOW GEN: running post-verifier auto-repair sweep")
        _auto_repair_connections(builder)

    # Phase 3 (Verify) metric — emitted unconditionally so we record even the
    # case where the verifier-LLM block was skipped (builder.nodes < 3).
    try:
        _verify_final_issues = _check_router_wiring(builder) if builder.nodes else []
        _verify_graph_json = builder.build_graph_json() if builder.nodes else {"nodes": [], "edges": []}
        _verify_duration_ms = round((time.time() - _verify_t_start) * 1000, 1)
        from .metrics_logger import log_experiment_metric
        await log_experiment_metric(
            project_id=str(project.project_id),
            experiment_type="workflow_verify",
            metric_data={
                "experiment": "workflow_verify",
                "first_pass_valid": len(router_issues) == 0,
                "initial_router_issues": len(router_issues),
                "final_router_issues": len(_verify_final_issues),
                "verifier_closed": len(_verify_final_issues) == 0,
                "verifier_iterations": _verifier_iterations,
                "verifier_tool_calls": _verifier_tool_calls,
                "duration_ms": _verify_duration_ms,
                "nodes": len(_verify_graph_json["nodes"]),
                "edges": len(_verify_graph_json["edges"]),
            },
            configuration={"phase": "verify", "max_iterations": 6},
            log_tag="EXP_METRIC_WORKFLOW_VERIFY",
        )
    except Exception as _verify_metric_err:
        logger.warning(f"⚠️ WORKFLOW GEN: verify metric logging failed: {_verify_metric_err}")

    # ── Self-critique phase (4th phase, always-on) ─────────────────────
    # The invariant verifier above checks structural rules (router wiring,
    # terminal reachability, regression guard). The self-critique phase
    # operates one level up: it looks for SEMANTIC / CONFIGURATION issues
    # that a rigid invariant check cannot see — redundant agents, system
    # messages that don't describe the agent's role, wrong provider for
    # the task, classifier categories that don't meaningfully separate
    # cases, edge ordering that puts steps out of logical sequence, etc.
    #
    # Replaces the common manual follow-up prompt: "find the issues in
    # the current workflow and fix the errors". Runs silently; the
    # final diff combines initial-build + verifier + self-critique edits.
    #
    if builder.nodes and len(builder.nodes) >= 3:
        try:
            sc_tool_calls_before = len(builder.tool_calls_log)
            sc_t_start = time.time()

            crit_graph = builder.build_graph_json()
            c_nodes = crit_graph["nodes"]
            c_edges = crit_graph["edges"]
            node_id_to_name_c = {n["id"]: n.get("data", {}).get("name", "?") for n in c_nodes}

            crit_desc_lines = ["Current workflow after invariant verification:"]
            _c_start = next((n for n in c_nodes if n.get("type") == "StartNode"), None)
            if _c_start:
                _csp = (_c_start.get("data", {}).get("prompt") or "").strip()
                if _csp:
                    crit_desc_lines.append(f'StartNode prompt: "{_csp[:500]}{"…" if len(_csp) > 500 else ""}"')
            crit_desc_lines.append(f"Nodes ({len(c_nodes)}):")
            for n in c_nodes:
                d = n.get("data", {})
                nid = n["id"]
                inc = len([e for e in c_edges if e["target"] == nid])
                out = len([e for e in c_edges if e["source"] == nid])
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
                crit_desc_lines.append(line)
                _csm = (d.get("system_message") or "").strip()
                if _csm and n["type"] not in ("StartNode", "EndNode"):
                    _snip = _csm[:500] + ("…" if len(_csm) > 500 else "")
                    crit_desc_lines.append(f"      system_message: {_snip}")
                if n["type"] == "ClassifierAgent":
                    cats = d.get("categories") or []
                    if cats:
                        crit_desc_lines.append("      categories:")
                        for c in cats:
                            _cn = c.get("name", "?")
                            _cd = (c.get("description") or "").strip()
                            crit_desc_lines.append(f"        • {_cn}" + (f" — {_cd[:200]}" if _cd else ""))
            crit_desc_lines.append(f"Connections ({len(c_edges)}):")
            c_classifier_cat_names = {
                n["id"]: {
                    c.get("id"): c.get("name", "?")
                    for c in (n.get("data", {}).get("categories") or [])
                }
                for n in c_nodes if n.get("type") == "ClassifierAgent"
            }
            for e in c_edges:
                src = node_id_to_name_c.get(e["source"], "?")
                tgt = node_id_to_name_c.get(e["target"], "?")
                handle_suffix = ""
                if e.get("source_handle") and e["source"] in c_classifier_cat_names:
                    cat_name = c_classifier_cat_names[e["source"]].get(e["source_handle"])
                    if cat_name:
                        handle_suffix = f" [category: {cat_name}]"
                crit_desc_lines.append(f"  {src} → {tgt} ({e.get('type', 'sequential')}){handle_suffix}{_edge_meta_suffix(e)}")
            crit_desc = "\n".join(crit_desc_lines)

            critique_prompt = (
                "You are performing a final QUALITY REVIEW of a workflow that has "
                "just been built and has already passed structural/invariant "
                "verification (router wiring, terminal reachability, regression "
                "guard). Your job is different from the invariant verifier — find "
                "SEMANTIC and CONFIGURATION issues a rigid check cannot see.\n\n"
                f"{_format_user_context(conversation_history, user_message)}\n\n"
                f"{crit_desc}\n\n"
                "Review the workflow critically and look for issues such as:\n"
                "  • An agent whose system_message is vague, generic, or does not "
                "describe the agent's actual role for THIS user request.\n"
                "  • Two or more agents with overlapping purpose (redundant hops).\n"
                "  • A missing agent needed to accomplish the stated task (e.g. a "
                "'write a report' task with no writer; a 'research topic X' task "
                "with no source-gathering or web_search agent).\n"
                "  • An agent with a provider/model that is a poor fit for its job "
                "(heavy reasoning on a tiny model; creative generation at temperature=0).\n"
                "  • Document or web_search assignments that don't match what the "
                "agent is being asked to do.\n"
                "  • ClassifierAgent categories that overlap or don't meaningfully "
                "separate the routing cases described in the user's request.\n"
                "  • SplitterAgent downstreams whose system_messages don't describe "
                "distinct specialties — the splitter needs to route BY role.\n"
                "  • Edge ordering that puts steps out of logical sequence "
                "(e.g. editor before writer; synthesis before analysis).\n"
                "  • System messages that fail to reference the documents, tools, "
                "or web_search the agent actually has configured.\n\n"
                "If the workflow is already high-quality, respond with "
                "'Self-critique passed — no changes needed.' and DO NOT call any tools.\n\n"
                "If you find issues, FIX them using the available tools. Prefer "
                "surgical edits (update_node_property, rewire_edge, connect_nodes, "
                "delete_edge, add_category) over destructive ones. Do NOT remove "
                "agents the user explicitly asked for. Do NOT rebuild from scratch."
            )

            critique_messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": critique_prompt},
            ]

            logger.info(
                f"🎯 WORKFLOW GEN: Self-critique phase on {len(c_nodes)} nodes, "
                f"{len(c_edges)} edges"
            )

            # 4 iterations is usually enough — LLM either has a short list of
            # fixes or it passes immediately. Early-exit on no tool calls.
            sc_iterations = 0
            sc_final_text = ""
            # Track (source_id, target_id) pairs that the critique LLM deletes
            # across all iterations. Passed to the post-critique auto-repair
            # sweep so it doesn't resurrect edges the critique just removed.
            critique_deleted_edges: set = set()
            for sc_iter in range(4):
                sc_iterations = sc_iter + 1
                sc_response = await llm_provider.generate_response(
                    messages=critique_messages, tools=WORKFLOW_TOOLS,
                )
                if sc_response.error:
                    logger.warning(
                        f"⚠️ WORKFLOW GEN: Self-critique provider error: {sc_response.error}"
                    )
                    break
                if sc_response.text:
                    sc_final_text = sc_response.text
                    logger.info(
                        f"🎯 WORKFLOW GEN: Self-critique iter {sc_iter + 1}: {sc_response.text[:200]}"
                    )
                # No tool calls → the critic is satisfied (or can't find anything).
                if not sc_response.tool_calls:
                    break

                formatted_sc_calls = []
                for tc in sc_response.tool_calls:
                    fn = tc.get("function", {})
                    raw_args = fn.get("arguments", tc.get("arguments", "{}"))
                    args_str = json.dumps(raw_args) if isinstance(raw_args, dict) else str(raw_args)
                    formatted_sc_calls.append({
                        "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        "type": "function",
                        "function": {
                            "name": fn.get("name", tc.get("name", "")),
                            "arguments": args_str,
                        },
                    })
                critique_messages.append({
                    "role": "assistant",
                    "content": sc_response.text or "",
                    "tool_calls": formatted_sc_calls,
                })
                for tc in formatted_sc_calls:
                    fn_args = (
                        json.loads(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], str)
                        else tc["function"]["arguments"]
                    )
                    # Snapshot edge IDs before execution so we can detect what
                    # got removed (for critique-deleted tracking below).
                    edges_before = {(e["source"], e["target"]) for e in builder.edges}
                    result = builder.execute_tool_call(tc["function"]["name"], fn_args)
                    logger.info(
                        f"🔧 WORKFLOW GEN (self-critique): {tc['function']['name']} → {result}"
                    )
                    # Any (source, target) pair that disappeared after this
                    # tool call was deleted (directly via delete_edge, or
                    # indirectly via rewire_edge / delete_node / etc.).
                    edges_after = {(e["source"], e["target"]) for e in builder.edges}
                    critique_deleted_edges.update(edges_before - edges_after)
                    critique_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

            sc_tool_calls_after = len(builder.tool_calls_log)
            sc_tool_calls_made = sc_tool_calls_after - sc_tool_calls_before
            sc_duration_ms = round((time.time() - sc_t_start) * 1000, 1)

            # If self-critique made ANY changes, run the auto-repair sweep
            # once more to catch any structural damage (e.g. a rewire_edge
            # that left an orphan, or a delete_edge that broke a terminal
            # path). When self-critique was a no-op, skip the work.
            if sc_tool_calls_made > 0:
                logger.info(
                    f"🔧 WORKFLOW GEN: self-critique made {sc_tool_calls_made} tool "
                    "call(s) — running post-critique auto-repair sweep"
                )
                _auto_repair_connections(builder, recently_deleted=critique_deleted_edges)
                explanation += f"\n\n**Self-critique:** {sc_final_text or f'applied {sc_tool_calls_made} fix(es)'}"
            else:
                logger.info(
                    f"🎯 WORKFLOW GEN: self-critique passed without changes "
                    f"after {sc_iterations} iteration(s)"
                )

            # Emit an observability metric so we can see how often the critic
            # adds value, and how expensive it is per build.
            try:
                from .metrics_logger import log_experiment_metric
                await log_experiment_metric(
                    project_id=str(project.project_id),
                    experiment_type='workflow_self_critique',
                    metric_data={
                        'experiment': 'workflow_self_critique',
                        'iterations': sc_iterations,
                        'tool_calls_made': sc_tool_calls_made,
                        'duration_ms': sc_duration_ms,
                        'final_status': (
                            'passed' if sc_tool_calls_made == 0 else 'fixes_applied'
                        ),
                        'nodes_before': len(c_nodes),
                        'edges_before': len(c_edges),
                    },
                    configuration={'phase': 'self_critique', 'max_iterations': 4},
                    log_tag='EXP_METRIC_WORKFLOW_SELF_CRITIQUE',
                )
            except Exception as metric_err:
                logger.warning(
                    f"⚠️ WORKFLOW GEN: self-critique metric logging failed: {metric_err}"
                )

        except Exception as sc_err:
            logger.warning(f"⚠️ WORKFLOW GEN: Self-critique phase failed: {sc_err}")

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
