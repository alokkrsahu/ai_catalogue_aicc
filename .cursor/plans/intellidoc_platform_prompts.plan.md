# IntelliDoc platform system prompt (hybrid)

## Goal

Append a **non-UI-exposed** platform addendum to effective system prompts: a **global core** plus **per-`agent_node.type`** snippets. Order: user `system_message` and `instructions`, then IntelliDoc block, then DocAware / attachments / web search (injected context).

## Design

- **New module** [`backend/agent_orchestration/intellidoc_system_prompt.py`](backend/agent_orchestration/intellidoc_system_prompt.py): constants `INTELLIDOC_CORE`, `INTELLIDOC_BY_AGENT_TYPE`, and `intellidoc_addendum_for_node(agent_node) -> str`.
- **Integration** [`backend/agent_orchestration/chat_manager.py`](backend/agent_orchestration/chat_manager.py):
  - `craft_conversation_prompt` and `craft_conversation_prompt_with_docaware`: append after user lines, before document/file/web sections.
  - `execute_delegate_conversation_with_multiple_inputs`: after delegate system message line.
  - `execute_delegate_conversation` (single-input): after `System Message:` block in `system_message_parts`.
  - `execute_group_chat_manager`, `execute_group_chat_manager_with_multiple_inputs`, and `execute_group_chat_manager_intelligent_delegation`: inject addendum into `final_prompt` via `_intellidoc_addendum_string(chat_manager_node)` (GroupChatManager type snippet).
- **Helpers** on `ChatManager`: `_append_intellidoc_platform_prompt` (list-based system assembly), `_intellidoc_addendum_string` (for f-string final prompts).
- **No frontend** changes; prompts are code-owned only.

## Status

Implemented: module + full `chat_manager.py` wiring (conversation, delegate, group-chat final synthesis including intelligent delegation). `python -m py_compile` on touched modules passes.

## Types covered

`AssistantAgent`, `UserProxyAgent`, `DelegateAgent`, `GroupChatManager`, `MCPServer`, `StartNode`, `EndNode` (empty snippets where not applicable).

## Verification

- Run any workflow with an assistant that has a custom system message; inspect outbound LLM messages (logs or proxy) for `=== IntelliDoc platform guidance` section.
- Delegate and group-chat paths still run without errors.
