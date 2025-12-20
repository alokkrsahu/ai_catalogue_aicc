# Duplicate UserProxyAgent Fix

## Problem

User Proxy 1 was being prompted **twice** with the same input:
1. First time: After AI Assistant 1's initial response (via reflection edge)
2. Second time: After AI Assistant 1 processes reflection and workflow continues (in main execution sequence)

## Root Cause

After reflection completes:
1. Reflection context is cleared (to allow workflow to continue)
2. **UserProxyAgent is NOT marked as executed** in `executed_nodes`
3. When workflow continues, it encounters UserProxyAgent in the main execution sequence
4. Since reflection context is cleared, the skip check fails
5. UserProxyAgent executes again → **DUPLICATE!**

## Fix Applied

### Fix 1: Mark UserProxyAgent as Executed After Reflection

**File**: `backend/agent_orchestration/human_input_handler.py`
**Location**: `continue_workflow_from_resumed_state()` method, after reflection completes (lines 197-220)

**Change**: After reflection completes, mark the UserProxyAgent as executed in `executed_nodes`:

```python
# CRITICAL FIX: Mark UserProxyAgent as executed after reflection completes
# This prevents it from being executed again in the main workflow sequence
executed_nodes = execution_record.executed_nodes or {}
if user_proxy_agent_id:
    # Mark UserProxyAgent as executed so it's skipped in main sequence
    executed_nodes[user_proxy_agent_id] = f"UserProxyAgent processed reflection input: {human_input}"
    execution_record.executed_nodes = executed_nodes
    logger.info(f"✅ REFLECTION RESUME: Marked UserProxyAgent {user_proxy_agent_id} as executed after reflection completion")
```

### Fix 2: Check executed_nodes When Context is Cleared

**File**: `backend/agent_orchestration/workflow_executor.py`
**Location**: `continue_workflow_execution()` method, when processing UserProxyAgent nodes (lines 862-867)

**Change**: When reflection context is cleared but UserProxyAgent is encountered, check if it's already in `executed_nodes`:

```python
else:
    # CRITICAL FIX: Check if UserProxyAgent was already executed via reflection
    # If it's in executed_nodes, skip it even if context is cleared
    if node_id in executed_nodes:
        should_skip = True
        logger.info(f"⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent {node_name} (node_id: {node_id}) - already executed via reflection")
    else:
        logger.info(f"✅ CONTINUE WORKFLOW: UserProxyAgent {node_name} (node_id: {node_id}) was in reflection but context cleared - will execute in main workflow")
```

## Expected Behavior After Fix

1. **AI Assistant 1** completes → reflection edge triggers **User Proxy 1**
2. **User Proxy 1** pauses for human input (first time) ✅
3. User provides input "tailor it for indian audience"
4. **AI Assistant 1** processes reflection and produces new response
5. **User Proxy 1 is marked as executed** in `executed_nodes` ✅
6. Reflection context is cleared
7. Workflow continues with main execution sequence
8. Encounters **User Proxy 1** in sequence
9. **Checks executed_nodes** → finds User Proxy 1 already executed
10. **Skips User Proxy 1** → continues to next node ✅
11. **No duplicate prompt!** ✅

## Testing

To verify the fix:
1. Start a workflow with reflection edges to UserProxyAgent
2. Provide human input when UserProxyAgent pauses
3. Verify UserProxyAgent is only prompted **once**
4. Check logs for: `✅ REFLECTION RESUME: Marked UserProxyAgent ... as executed after reflection completion`
5. Check logs for: `⏭️ CONTINUE WORKFLOW: Skipping UserProxyAgent ... - already executed via reflection`

## Files Modified

- `backend/agent_orchestration/human_input_handler.py`: Mark UserProxyAgent as executed after reflection
- `backend/agent_orchestration/workflow_executor.py`: Check executed_nodes when context is cleared

