<!-- ManualConnectionInterface.svelte - Drag and Drop Agent Connection System -->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  
  export let nodes: any[] = [];
  export let edges: any[] = [];
  export let selectedConnection: any = null;
  
  const dispatch = createEventDispatcher();
  
  // Connection state
  let isConnecting = false;
  let sourceNode: any = null;
  let targetNode: any = null;
  let connectionType = 'default';
  let connectionLabel = '';
  
  // UI state
  let hoveredNode: any = null;
  let draggedConnection: any = null;
  let showConnectionModal = false;
  
  // Connection types
  const connectionTypes = [
    { id: 'default', name: 'Default Flow', color: '#002147', icon: 'fa-arrow-right', description: 'Standard sequential flow' },
    { id: 'conditional', name: 'Conditional', color: '#f59e0b', icon: 'fa-question-circle', description: 'Based on condition' },
    { id: 'parallel', name: 'Parallel', color: '#10b981', icon: 'fa-code-branch', description: 'Parallel execution' },
    { id: 'feedback', name: 'Feedback Loop', color: '#ef4444', icon: 'fa-undo', description: 'Return to previous agent' },
    { id: 'data', name: 'Data Flow', color: '#8b5cf6', icon: 'fa-database', description: 'Data-only connection' }
  ];
  
  console.log('🔗 MANUAL CONNECTION: Interface initialized with', nodes.length, 'nodes');
  
  // Connection mode management
  function startConnectionMode() {
    isConnecting = true;
    sourceNode = null;
    targetNode = null;
    console.log('🎯 MANUAL CONNECTION: Connection mode started');
  }
  
  function cancelConnectionMode() {
    isConnecting = false;
    sourceNode = null;
    targetNode = null;
    console.log('❌ MANUAL CONNECTION: Connection mode cancelled');
  }
  
  // Node click handlers
  function handleNodeClick(node: any) {
    if (!isConnecting) return;
    
    if (!sourceNode) {
      // First click - select source
      sourceNode = node;
      console.log('📍 MANUAL CONNECTION: Source selected:', node.data.name);
    } else if (sourceNode.id !== node.id) {
      // Second click - select target and create connection
      targetNode = node;
      showConnectionModal = true;
      console.log('🎯 MANUAL CONNECTION: Target selected:', node.data.name);
    }
  }
  
  // Create connection
  function createConnection() {
    if (!sourceNode || !targetNode) return;
    
    // Check for duplicate connection
    const existingConnection = edges.find(edge => 
      edge.source === sourceNode.id && edge.target === targetNode.id
    );
    
    if (existingConnection) {
      alert('Connection already exists between these agents');
      return;
    }
    
    const newConnection = {
      id: `${sourceNode.id}-${targetNode.id}`,
      source: sourceNode.id,
      target: targetNode.id,
      type: connectionType,
      label: connectionLabel || undefined,
      data: {
        connectionType,
        customLabel: connectionLabel,
        sourceAgent: sourceNode,
        targetAgent: targetNode
      }
    };
    
    dispatch('connectionCreate', newConnection);
    
    // Reset state
    showConnectionModal = false;
    sourceNode = null;
    targetNode = null;
    connectionType = 'default';
    connectionLabel = '';
    isConnecting = false;
    
    console.log('✅ MANUAL CONNECTION: Connection created successfully');
  }
  
  // Delete connection
  function deleteConnection(connection: any) {
    if (confirm(`Delete connection from ${connection.data?.sourceAgent?.data?.name} to ${connection.data?.targetAgent?.data?.name}?`)) {
      dispatch('connectionDelete', connection);
      console.log('🗑️ MANUAL CONNECTION: Connection deleted');
    }
  }
  
  // Get node color based on state
  function getNodeStateClass(node: any): string {
    if (isConnecting) {
      if (sourceNode?.id === node.id) {
        return 'ring-4 ring-green-400 bg-green-50 border-green-500';
      }
      if (sourceNode && sourceNode.id !== node.id) {
        return 'ring-2 ring-blue-300 hover:ring-blue-500 cursor-pointer';
      }
      return 'ring-2 ring-gray-300 hover:ring-oxford-blue cursor-pointer';
    }
    return 'hover:shadow-lg cursor-pointer';
  }
  
  // Get connection style
  function getConnectionStyle(connection: any) {
    const type = connectionTypes.find(t => t.id === connection.type) || connectionTypes[0];
    return {
      color: type.color,
      strokeWidth: selectedConnection?.id === connection.id ? '3' : '2',
      strokeDasharray: connection.type === 'conditional' ? '5,5' : connection.type === 'parallel' ? '3,3' : 'none'
    };
  }
  
  function getAgentIcon(agentType: string): string {
    switch (agentType) {
      case 'StartNode': return 'fa-play';
      case 'UserProxyAgent': return 'fa-user';
      case 'AssistantAgent': return 'fa-robot';
      case 'GroupChatManager': return 'fa-users';
      default: return 'fa-cog';
    }
  }
  
  function getAgentColor(agentType: string): string {
    switch (agentType) {
      case 'StartNode': return 'bg-green-600';
      case 'UserProxyAgent': return 'bg-blue-600';
      case 'AssistantAgent': return 'bg-oxford-blue';
      case 'GroupChatManager': return 'bg-purple-600';
      default: return 'bg-gray-600';
    }
  }
</script>

<div class="manual-connection-interface w-full h-full flex flex-col bg-gray-50">
  <!-- Header Controls -->
  <div class="bg-white border-b border-gray-200 p-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-4">
        <h3 class="text-lg font-semibold text-gray-900">
          <i class="fas fa-link mr-2 text-oxford-blue"></i>
          Manual Agent Connections
        </h3>
        <div class="text-sm text-gray-600">
          {nodes.length} agents • {edges.length} connections
        </div>
      </div>
      
      <div class="flex items-center space-x-3">
        {#if isConnecting}
          <!-- Connection Mode Active -->
          <div class="flex items-center space-x-2">
            <div class="px-3 py-1.5 bg-green-100 text-green-800 rounded-lg text-sm font-medium">
              <i class="fas fa-mouse-pointer mr-1"></i>
              {sourceNode ? 'Select Target Agent' : 'Select Source Agent'}
            </div>
            <button
              class="px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 text-sm font-medium transition-colors"
              on:click={cancelConnectionMode}
            >
              <i class="fas fa-times mr-1"></i>
              Cancel
            </button>
          </div>
        {:else}
          <!-- Normal Mode -->
          <button
            class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors font-medium shadow-lg hover:shadow-xl"
            on:click={startConnectionMode}
            disabled={nodes.length < 2}
          >
            <i class="fas fa-plus mr-2"></i>
            Connect Agents
          </button>
        {/if}
      </div>
    </div>
    
    <!-- Connection Instructions -->
    {#if isConnecting}
      <div class="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div class="flex items-start space-x-3">
          <i class="fas fa-info-circle text-blue-500 mt-0.5"></i>
          <div class="text-sm text-blue-800">
            {#if !sourceNode}
              <p class="font-medium">Step 1: Click on the source agent to start connection</p>
              <p class="text-blue-600 mt-1">Click on any agent below to begin creating a connection</p>
            {:else}
              <p class="font-medium">Step 2: Click on the target agent to complete connection</p>
              <p class="text-blue-600 mt-1">
                Source: <span class="font-medium">{sourceNode.data.name}</span> → Click target agent to connect
              </p>
            {/if}
          </div>
        </div>
      </div>
    {/if}
  </div>
  
  <!-- Agent Canvas -->
  <div class="flex-1 p-6 overflow-auto">
    {#if nodes.length === 0}
      <!-- Empty State -->
      <div class="flex items-center justify-center h-full">
        <div class="text-center">
          <div class="w-20 h-20 bg-gray-200 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
            <i class="fas fa-robot text-3xl"></i>
          </div>
          <h3 class="text-lg font-medium text-gray-700 mb-2">No Agents Available</h3>
          <p class="text-gray-500">Add agents to the workflow to start creating connections</p>
        </div>
      </div>
    {:else}
      <!-- Agent Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {#each nodes as node}
          <div 
            class="agent-node p-4 bg-white border-2 rounded-xl transition-all duration-200 {getNodeStateClass(node)}"
            on:click={() => handleNodeClick(node)}
            role="button"
            tabindex="0"
            on:keydown={(e) => e.key === 'Enter' && handleNodeClick(node)}
          >
            <!-- Agent Header -->
            <div class="flex items-center space-x-3 mb-3">
              <div class="w-12 h-12 {getAgentColor(node.type)} text-white rounded-lg flex items-center justify-center shadow-lg">
                <i class="fas {getAgentIcon(node.type)} text-lg"></i>
              </div>
              <div class="flex-1 min-w-0">
                <h4 class="font-semibold text-gray-900 truncate">{node.data.name || node.type}</h4>
                <p class="text-sm text-gray-600">{node.type}</p>
              </div>
            </div>
            
            <!-- Agent Description -->
            {#if node.data.description}
              <p class="text-sm text-gray-600 mb-3 line-clamp-2">{node.data.description}</p>
            {/if}
            
            <!-- Connection Info -->
            <div class="flex items-center justify-between text-xs text-gray-500">
              <span class="flex items-center">
                <i class="fas fa-arrow-right mr-1"></i>
                {edges.filter(e => e.source === node.id).length} outgoing
              </span>
              <span class="flex items-center">
                <i class="fas fa-arrow-left mr-1"></i>
                {edges.filter(e => e.target === node.id).length} incoming
              </span>
            </div>
            
            <!-- Selection Indicator -->
            {#if sourceNode?.id === node.id}
              <div class="mt-3 flex items-center justify-center">
                <div class="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
                  <i class="fas fa-check mr-1"></i>
                  Source Selected
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
      
      <!-- Connections Visualization -->
      {#if edges.length > 0}
        <div class="mt-8 bg-white rounded-xl border border-gray-200 p-6">
          <h4 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <i class="fas fa-project-diagram mr-2 text-oxford-blue"></i>
            Active Connections ({edges.length})
          </h4>
          
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {#each edges as connection}
              {@const sourceAgent = nodes.find(n => n.id === connection.source)}
              {@const targetAgent = nodes.find(n => n.id === connection.target)}
              {@const connectionTypeInfo = connectionTypes.find(t => t.id === connection.type) || connectionTypes[0]}
              
              <div class="connection-item p-4 border rounded-lg hover:shadow-md transition-all {selectedConnection?.id === connection.id ? 'border-oxford-blue bg-blue-50' : 'border-gray-200'}">
                <div class="flex items-center space-x-3">
                  <!-- Source Agent -->
                  <div class="flex items-center space-x-2">
                    <div class="w-8 h-8 {getAgentColor(sourceAgent?.type)} text-white rounded-lg flex items-center justify-center text-sm">
                      <i class="fas {getAgentIcon(sourceAgent?.type)}"></i>
                    </div>
                    <span class="text-sm font-medium text-gray-900 truncate max-w-24">{sourceAgent?.data?.name}</span>
                  </div>
                  
                  <!-- Connection Arrow -->
                  <div class="flex items-center space-x-2">
                    <div class="flex items-center">
                      <div 
                        class="h-0.5 w-8 transition-colors"
                        style="background-color: {connectionTypeInfo.color};"
                      ></div>
                      <div 
                        class="w-0 h-0 border-l-4 border-t-2 border-b-2 border-transparent"
                        style="border-left-color: {connectionTypeInfo.color};"
                      ></div>
                    </div>
                    
                    <!-- Connection Type -->
                    <span 
                      class="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                      style="background-color: {connectionTypeInfo.color}20; color: {connectionTypeInfo.color};"
                    >
                      <i class="fas {connectionTypeInfo.icon} mr-1"></i>
                      {connectionTypeInfo.name}
                    </span>
                  </div>
                  
                  <!-- Target Agent -->
                  <div class="flex items-center space-x-2">
                    <div class="w-8 h-8 {getAgentColor(targetAgent?.type)} text-white rounded-lg flex items-center justify-center text-sm">
                      <i class="fas {getAgentIcon(targetAgent?.type)}"></i>
                    </div>
                    <span class="text-sm font-medium text-gray-900 truncate max-w-24">{targetAgent?.data?.name}</span>
                  </div>
                  
                  <!-- Delete Button -->
                  <button
                    class="ml-auto p-1.5 text-gray-400 hover:text-red-600 transition-colors"
                    on:click={() => deleteConnection(connection)}
                    title="Delete Connection"
                  >
                    <i class="fas fa-trash text-xs"></i>
                  </button>
                </div>
                
                <!-- Connection Label -->
                {#if connection.label}
                  <div class="mt-2 text-xs text-gray-600">
                    <i class="fas fa-tag mr-1"></i>
                    {connection.label}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>

<!-- Connection Configuration Modal -->
{#if showConnectionModal && sourceNode && targetNode}
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-lg w-full max-w-md">
      <div class="p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-900">Configure Connection</h3>
          <button
            class="text-gray-400 hover:text-gray-600"
            on:click={() => showConnectionModal = false}
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <!-- Connection Preview -->
        <div class="mb-6 p-4 bg-gray-50 rounded-lg">
          <div class="flex items-center space-x-3">
            <div class="flex items-center space-x-2">
              <div class="w-8 h-8 {getAgentColor(sourceNode.type)} text-white rounded-lg flex items-center justify-center text-sm">
                <i class="fas {getAgentIcon(sourceNode.type)}"></i>
              </div>
              <span class="text-sm font-medium">{sourceNode.data.name}</span>
            </div>
            
            <i class="fas fa-arrow-right text-gray-400"></i>
            
            <div class="flex items-center space-x-2">
              <div class="w-8 h-8 {getAgentColor(targetNode.type)} text-white rounded-lg flex items-center justify-center text-sm">
                <i class="fas {getAgentIcon(targetNode.type)}"></i>
              </div>
              <span class="text-sm font-medium">{targetNode.data.name}</span>
            </div>
          </div>
        </div>
        
        <!-- Connection Type -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">Connection Type</label>
          <select
            bind:value={connectionType}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          >
            {#each connectionTypes as type}
              <option value={type.id}>
                {type.name} - {type.description}
              </option>
            {/each}
          </select>
        </div>
        
        <!-- Connection Label -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">Label (Optional)</label>
          <input
            type="text"
            bind:value={connectionLabel}
            placeholder="Custom connection label..."
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          />
        </div>
        
        <!-- Actions -->
        <div class="flex justify-end space-x-3">
          <button
            class="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
            on:click={() => showConnectionModal = false}
          >
            Cancel
          </button>
          <button
            class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors"
            on:click={createConnection}
          >
            <i class="fas fa-link mr-2"></i>
            Create Connection
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .agent-node {
    min-height: 140px;
  }
  
  .connection-item {
    transition: all 0.2s ease;
  }
  
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  :global(.oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  
  :global(.focus\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  :global(.focus\:border-oxford-blue:focus) {
    border-color: #002147;
  }
</style>
