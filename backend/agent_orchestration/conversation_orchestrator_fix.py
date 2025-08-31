# Critical Fix for Conversation History Saving
# This file contains the missing code patterns that need to be added to conversation_orchestrator.py

# Pattern 1: After GroupChatManager execution (around line 1950)
# Add this right after: agent_response = await self.execute_group_chat_manager(...)

# Update conversation history with agent response
conversation_history += f"\n{node_name}: {agent_response}"

# Store node output for multi-input support  
executed_nodes[node_id] = agent_response

# CRITICAL FIX: Save updated conversation history to database
execution_record.conversation_history = conversation_history
await sync_to_async(execution_record.save)()

# Pattern 2: After AssistantAgent execution (search for similar pattern)
# Add this after any agent response generation

# Update conversation history with agent response
conversation_history += f"\n{node_name}: {agent_response}"

# Store node output for multi-input support
executed_nodes[node_id] = agent_response

# CRITICAL FIX: Save updated conversation history to database
execution_record.conversation_history = conversation_history
await sync_to_async(execution_record.save)()

# Pattern 3: At the very end of execute_workflow method (final save)
# Add before the final return statement

# Final update of execution record with complete conversation history
execution_record.conversation_history = conversation_history
execution_record.status = WorkflowExecutionStatus.COMPLETED
execution_record.end_time = timezone.now()
execution_record.result_summary = "Workflow completed successfully"
await sync_to_async(execution_record.save)()
