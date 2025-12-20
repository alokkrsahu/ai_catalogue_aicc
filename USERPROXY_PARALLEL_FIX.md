# UserProxyAgent Parallel Execution Fix

## Problem Summary

User Proxy 1 was showing "[No output from AI Assistant 1]" because:
1. `_find_ready_nodes()` only checked sequential edges for dependencies
2. User Proxy 1 depends on AI Assistant 1 via a **reflection edge** (not sequential)
3. User Proxy 1 was incorrectly marked as "ready" before AI Assistant 1 executed
4. User Proxy 1 was executed sequentially, skipping AI Assistant 1's parallel execution

## Fixes Implemented

### Fix 1: Include Reflection Edges in Dependency Map for UserProxyAgent

**File**: `backend/agent_orchestration/workflow_executor.py`
**Location**: `_find_ready_nodes()` method, lines 1073-1095

**Change**: Modified dependency map building to include reflection edges that target UserProxyAgent nodes:

```python
# Build dependency map: node_id -> set of source node_ids it depends on
dependency_map = {}
nodes = graph_json.get('nodes', [])
node_map = {node.get('id'): node for node in nodes}  # Create lookup for fast access

for edge in edges:
    edge_type = edge.get('type', 'sequential')
    source_id = edge.get('source')
    target_id = edge.get('target')
    
    # Get target node to check if it's a UserProxyAgent
    target_node = node_map.get(target_id)
    is_user_proxy = (target_node and 
                    target_node.get('type') == 'UserProxyAgent' and
                    target_node.get('data', {}).get('require_human_input', True))
    
    # Include sequential edges for all nodes
    # Include reflection edges ONLY for UserProxyAgent nodes (they depend on reflection sources)
    if edge_type == 'sequential' or (edge_type == 'reflection' and is_user_proxy):
        if target_id not in dependency_map:
            dependency_map[target_id] = set()
        dependency_map[target_id].add(source_id)
```

**Impact**: UserProxyAgent nodes now correctly wait for their reflection edge dependencies to complete.

### Fix 2: Filter UserProxyAgent from Parallel Execution if Dependencies Not Satisfied

**File**: `backend/agent_orchestration/workflow_executor.py`
**Location**: Main execution loop, lines 216-299

**Change**: Added logic to check if UserProxyAgent's dependencies are actually satisfied before executing it:

1. **Build dependency map** (including reflection edges for UserProxyAgent)
2. **Separate nodes** into:
   - `ready_user_proxy_nodes`: UserProxyAgent nodes with satisfied dependencies
   - `other_ready_nodes`: Non-UserProxyAgent nodes ready to execute
3. **Execute logic**:
   - If only UserProxyAgent nodes ready → execute sequentially to pause
   - If other nodes ready → execute them in parallel first, then check UserProxyAgent again
   - If both ready → execute other nodes first, UserProxyAgent waits

**Key Code**:
```python
# Separate UserProxyAgent nodes from other nodes
ready_user_proxy_nodes = []
other_ready_nodes = []

for idx, node in ready_nodes:
    if node.get('type') == 'UserProxyAgent' and node.get('data', {}).get('require_human_input', True):
        node_id = node.get('id')
        dependencies = dependency_map.get(node_id, set())
        # Check if all dependencies (including reflection edges) are satisfied
        if all(dep_id in executed_nodes for dep_id in dependencies):
            ready_user_proxy_nodes.append((idx, node))
        else:
            # Dependencies not satisfied - don't execute yet
            missing_deps = [dep_id for dep_id in dependencies if dep_id not in executed_nodes]
            logger.info(f"⏳ PARALLEL: UserProxyAgent {node.get('data', {}).get('name')} waiting for dependencies: {missing_deps}")
    else:
        other_ready_nodes.append((idx, node))
```

**Impact**: UserProxyAgent nodes only execute when their dependencies (including reflection edges) are satisfied.

## Expected Behavior After Fix

1. **StartNode** → Executes first
2. **AI Assistant 1 & AI Assistant 2** → Detected as ready (both depend only on StartNode), execute in parallel
3. **User Proxy 1** → Detected as ready BUT dependency check shows it depends on AI Assistant 1 (reflection edge), so it waits
4. **After AI Assistant 1 completes** → User Proxy 1's dependencies satisfied, it executes and pauses with AI Assistant 1's output visible

## Testing

To verify the fix:
1. Start a new workflow execution
2. Check logs for:
   - `⏳ PARALLEL: UserProxyAgent User Proxy 1 waiting for dependencies: [AI Assistant 1 node_id]`
   - `🔀 PARALLEL: Executing 2 nodes in parallel` (AI Assistant 1 & AI Assistant 2)
   - `✅ PARALLEL: UserProxyAgent User Proxy 1 dependencies satisfied` (after AI Assistant 1 completes)
3. Verify User Proxy 1 modal shows AI Assistant 1's actual output (not "[No output...]")

## Files Modified

- `backend/agent_orchestration/workflow_executor.py`:
  - `_find_ready_nodes()` method: Added reflection edge support for UserProxyAgent
  - Main execution loop: Added dependency checking before executing UserProxyAgent

