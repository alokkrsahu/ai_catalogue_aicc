# Expected Workflow Execution Flow

## Workflow Graph Structure

Based on the attached workflow graph:

**Nodes:**
1. **Start 1** (StartNode) - 2 outgoing edges, 0 incoming
2. **AI Assistant 1** (AssistantAgent) - 2 outgoing, 1 incoming (from Start 1)
3. **AI Assistant 2** (AssistantAgent) - 2 outgoing, 1 incoming (from Start 1)
4. **User Proxy 1** (UserProxyAgent) - 0 outgoing, 1 incoming (from AI Assistant 1 - reflection edge)
5. **User Proxy 2** (UserProxyAgent) - 0 outgoing, 1 incoming (from AI Assistant 2 - reflection edge)
6. **AI Assistant 3** (AssistantAgent) - 1 outgoing, 2 incoming (from AI Assistant 1 and AI Assistant 2 - sequential edges)
7. **End 1** (EndNode) - 0 outgoing, 1 incoming (from AI Assistant 3)

**Edges:**
- Start 1 → AI Assistant 1 (sequential)
- Start 1 → AI Assistant 2 (sequential)
- AI Assistant 1 → User Proxy 1 (reflection)
- AI Assistant 1 → AI Assistant 3 (sequential)
- AI Assistant 2 → User Proxy 2 (reflection)
- AI Assistant 2 → AI Assistant 3 (sequential)
- AI Assistant 3 → End 1 (sequential)

## Expected Execution Sequence

### Phase 1: Initial Execution

1. **StartNode (Start 1)**
   - Executes first
   - Output: Start prompt (e.g., "Tell me a joke")
   - Saved to `executed_nodes[Start1_id]`
   - Message logged: `Start: "Tell me a joke"`

### Phase 2: Parallel Execution

2. **AI Assistant 1 & AI Assistant 2** (Execute in Parallel)
   - Both depend only on StartNode
   - Both detected as ready simultaneously
   - Execute concurrently using `asyncio.gather()`
   - Both receive StartNode output as input
   - **AI Assistant 1** produces response (e.g., "Why couldn't the bicycle stand up by itself? Because it was two tired!")
   - **AI Assistant 2** produces response (e.g., "Why did the idli refuse to fight with the dosa? Because it didn't want any beef!")
   - Both saved to `executed_nodes`
   - Messages logged: `AI Assistant 1: [response]` and `AI Assistant 2: [response]`

### Phase 3: Reflection Processing

3. **AI Assistant 1 → User Proxy 1** (Reflection Edge)
   - After AI Assistant 1 completes, reflection edge triggers
   - **User Proxy 1** pauses for human input
   - Shows AI Assistant 1's output in modal
   - User provides input (e.g., "tailor it for indian audience")
   - **AI Assistant 1** processes reflection and produces revised response
   - User Proxy 1 marked as executed in `executed_nodes[UserProxy1_id]`
   - Message logged: `User Proxy 1: "tailor it for indian audience"`
   - Message logged: `AI Assistant 1: [revised response]`

4. **AI Assistant 2 → User Proxy 2** (Reflection Edge)
   - After AI Assistant 2 completes, reflection edge triggers
   - **User Proxy 2** pauses for human input
   - Shows AI Assistant 2's output in modal
   - User provides input (e.g., "tailor it for indian audience")
   - **AI Assistant 2** processes reflection and produces revised response
   - User Proxy 2 marked as executed in `executed_nodes[UserProxy2_id]`
   - Message logged: `User Proxy 2: "tailor it for indian audience"`
   - Message logged: `AI Assistant 2: [revised response]`

**Note**: User Proxy 1 and User Proxy 2 can be processed in parallel if both AI Assistant 1 and AI Assistant 2 complete at the same time, but they require separate human inputs.

### Phase 4: Multi-Input Aggregation

5. **AI Assistant 3** (Multi-Input Node)
   - Depends on both AI Assistant 1 and AI Assistant 2
   - Waits for both to complete (including reflection processing)
   - Receives inputs from both AI Assistant 1 and AI Assistant 2
   - Aggregates both inputs
   - Produces combined response
   - Saved to `executed_nodes[AI_Assistant_3_id]`
   - Message logged: `AI Assistant 3: [combined response]`

### Phase 5: Completion

6. **EndNode (End 1)**
   - Executes after AI Assistant 3 completes
   - Output: "Workflow completed successfully."
   - Message logged: `End: "Workflow completed successfully."`

## Expected Message Sequence

Based on the expected flow, the conversation history should show:

1. **Start** → "Tell me a joke" (or start prompt)
2. **AI Assistant 1** → Initial response
3. **AI Assistant 2** → Initial response (may appear before or after AI Assistant 1, depending on parallel execution completion order)
4. **User Proxy 1** → Human input (e.g., "tailor it for indian audience")
5. **AI Assistant 1** → Revised response after reflection
6. **User Proxy 2** → Human input (e.g., "tailor it for indian audience")
7. **AI Assistant 2** → Revised response after reflection
8. **AI Assistant 3** → Combined response from both AI Assistant 1 and AI Assistant 2
9. **End** → "Workflow completed successfully."

## Key Points

1. **Parallel Execution**: AI Assistant 1 and AI Assistant 2 should execute simultaneously
2. **Reflection Edges**: User Proxy 1 and User Proxy 2 are triggered via reflection edges, not sequential edges
3. **No Duplicates**: Each UserProxyAgent should only appear once (after our fix)
4. **Multi-Input**: AI Assistant 3 waits for both AI Assistant 1 and AI Assistant 2 to complete
5. **Execution Order**: The exact order of AI Assistant 1 and AI Assistant 2 messages may vary due to parallel execution, but both should complete before AI Assistant 3

## Potential Issues to Check

1. Are AI Assistant 1 and AI Assistant 2 executing in parallel?
2. Is User Proxy 1 appearing only once (not duplicated)?
3. Is User Proxy 2 appearing only once (not duplicated)?
4. Does AI Assistant 3 receive inputs from both AI Assistant 1 and AI Assistant 2?
5. Are reflection responses being processed correctly?

