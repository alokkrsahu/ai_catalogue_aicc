<!-- ConnectionManagementPanel.svelte - Agent Connection Manager -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import AgentConnector from './AgentConnector.svelte';
  
  export let nodes: any[] = [];
  export let edges: any[] = [];
  export let selectedConnection: any = null;
  
  const dispatch = createEventDispatcher();
  
  // Connection management state
  let showCreateConnectionModal = false;
  let newConnectionSource = '';
  let newConnectionTarget = '';
  let newConnectionType = 'default';
  let newConnectionLabel = '';
  
  // Connection types
  const connectionTypes = [
    { id: 'default', name: 'Default Flow', description: 'Standard workflow connection', color: '#002147' },
    { id: 'conditional', name: 'Conditional', description: 'Connection based on condition', color: '#f59e0b' },
    { id: 'parallel', name: 'Parallel', description: 'Parallel execution path', color: '#10b981' },
    { id: 'feedback', name: 'Feedback Loop', description: 'Return to previous agent', color: '#ef4444' },
    { id: 'data', name: 'Data Flow', description: 'Data-only connection', color: '#8b5cf6' }
  ];
  
  // UI state
  let dragSourceAgent: any = null;
  let dragTargetAgent: any = null;
  
  $: availableSourceAgents = nodes.filter(node => node.type !== 'EndNode');
  $: availableTargetAgents = nodes.filter(node => node.type !== 'StartNode');
  $: connectionsWithAgents = edges.map(edge => {
    const sourceAgent = nodes.find(n => n.id === edge.source);
    const targetAgent = nodes.find(n => n.id === edge.target);
    return {
      ...edge,
      sourceAgent,
      targetAgent
    };
  });
  
  console.log('🔗 CONNECTION MANAGER: Initialized with', edges.length, 'connections');
  
  function handleCreateConnection() {
    showCreateConnectionModal = true;
    console.log('➕ CONNECTION MANAGER: Creating new connection');
  }
  
  function handleSaveNewConnection() {
    if (!newConnectionSource || !newConnectionTarget) {
      return;
    }
    
    // Check for duplicate connections
    const existingConnection = edges.find(edge => 
      edge.source === newConnectionSource && edge.target === newConnectionTarget
    );
    
    if (existingConnection) {
      alert('Connection already exists between these agents');
      return;
    }
    
    const newConnection = {
      id: `${newConnectionSource}-${newConnectionTarget}`,
      source: newConnectionSource,
      target: newConnectionTarget,
      type: newConnectionType,
      label: newConnectionLabel || undefined,
      data: {
        connectionType: newConnectionType,
        customLabel: newConnectionLabel
      }
    };
    
    dispatch('connectionCreate', newConnection);
    
    // Reset form
    newConnectionSource = '';
    newConnectionTarget = '';
    newConnectionType = 'default';
    newConnectionLabel = '';
    showCreateConnectionModal = false;
    
    console.log('✅ CONNECTION MANAGER: Connection created', newConnection.id);
  }
  
  function handleConnectionSelect(event: CustomEvent) {
    selectedConnection = event.detail;
    dispatch('connectionSelect', event.detail);
    console.log('🎯 CONNECTION MANAGER: Connection selected', event.detail.id);
  }
  
  function handleConnectionDelete(event: CustomEvent) {
    const connection = event.detail;
    if (confirm(`Delete connection from ${connection.sourceAgent?.name} to ${connection.targetAgent?.name}?`)) {
      dispatch('connectionDelete', connection);
      if (selectedConnection?.id === connection.id) {
        selectedConnection = null;
      }
      console.log('🗑️ CONNECTION MANAGER: Connection deleted', connection.id);
    }
  }
  
  function handleConnectionConfigure(event: CustomEvent) {
    const connection = event.detail;
    selectedConnection = connection;
    // Could open a detailed configuration modal here
    dispatch('connectionConfigure', connection);
    console.log('⚙️ CONNECTION MANAGER: Configuring connection', connection.id);
  }
  
  function handleQuickConnect(sourceAgent: any, targetAgent: any) {
    if (sourceAgent.id === targetAgent.id) return;
    
    // Check for existing connection
    const existingConnection = edges.find(edge => 
      edge.source === sourceAgent.id && edge.target === targetAgent.id
    );
    
    if (existingConnection) {
      alert('Connection already exists between these agents');
      return;
    }
    
    const newConnection = {
      id: `${sourceAgent.id}-${targetAgent.id}`,
      source: sourceAgent.id,
      target: targetAgent.id,
      type: 'default',
      data: { connectionType: 'default' }
    };
    
    dispatch('connectionCreate', newConnection);
    console.log('⚡ CONNECTION MANAGER: Quick connection created', newConnection.id);
  }
  
  function getConnectionTypeColor(typeId: string): string {
    const type = connectionTypes.find(t => t.id === typeId);
    return type ? type.color : '#002147';
  }
  
  function cancelNewConnection() {
    showCreateConnectionModal = false;
    newConnectionSource = '';
    newConnectionTarget = '';
    newConnectionType = 'default';
    newConnectionLabel = '';
  }
</script>

<div class="connection-management-panel bg-white border rounded-lg p-4">
  <!-- Header -->
  <div class="flex items-center justify-between mb-4">
    <div>
      <h4 class="font-semibold text-gray-900 flex items-center">
        <i class="fas fa-link mr-2 text-oxford-blue"></i>
        Agent Connections
      </h4>
      <p class="text-sm text-gray-600">Manage connections between agents</p>
    </div>
    
    <button
      class="px-3 py-1.5 bg-oxford-blue text-white rounded text-sm hover:bg-blue-700 transition-colors flex items-center"
      on:click={handleCreateConnection}
      disabled={nodes.length < 2}
    >
      <i class="fas fa-plus mr-1"></i>
      Add Connection
    </button>
  </div>
  
  <!-- Connection Statistics -->
  <div class="grid grid-cols-3 gap-4 mb-4">
    <div class="text-center p-3 bg-gray-50 rounded-lg">
      <div class="text-lg font-bold text-oxford-blue">{nodes.length}</div>
      <div class="text-xs text-gray-600">Agents</div>
    </div>
    <div class="text-center p-3 bg-gray-50 rounded-lg">
      <div class="text-lg font-bold text-oxford-blue">{edges.length}</div>
      <div class="text-xs text-gray-600">Connections</div>
    </div>
    <div class="text-center p-3 bg-gray-50 rounded-lg">
      <div class="text-lg font-bold text-oxford-blue">{connectionTypes.length}</div>
      <div class="text-xs text-gray-600">Types</div>
    </div>
  </div>
  
  <!-- Connection List -->
  <div class="space-y-2 max-h-64 overflow-y-auto">
    {#if connectionsWithAgents.length === 0}
      <div class="text-center py-8 text-gray-500">
        <i class="fas fa-link text-2xl mb-2 block"></i>
        <p class="text-sm">No connections yet</p>
        <p class="text-xs">Add agents and create connections to build your workflow</p>
      </div>
    {:else}
      {#each connectionsWithAgents as connection}
        <AgentConnector
          {connection}
          sourceAgent={connection.sourceAgent}
          targetAgent={connection.targetAgent}
          isSelected={selectedConnection?.id === connection.id}
          on:connectionSelect={handleConnectionSelect}
          on:connectionDelete={handleConnectionDelete}
          on:connectionConfigure={handleConnectionConfigure}
        />
      {/each}
    {/if}
  </div>
  
  <!-- Quick Connect Section -->
  {#if nodes.length >= 2}
    <div class="mt-4 pt-4 border-t border-gray-200">
      <h5 class="text-sm font-medium text-gray-700 mb-2">
        <i class="fas fa-bolt mr-1"></i>
        Quick Connect
      </h5>
      <div class="grid grid-cols-2 gap-2">
        {#each nodes.slice(0, 4) as agent}
          <button
            class="p-2 text-left border border-gray-200 rounded hover:border-oxford-blue hover:bg-blue-50 transition-all"
            on:click={() => {
              if (dragSourceAgent && dragSourceAgent.id !== agent.id) {
                handleQuickConnect(dragSourceAgent, agent);
                dragSourceAgent = null;
              } else {
                dragSourceAgent = agent;
              }
            }}
            class:bg-blue-100={dragSourceAgent?.id === agent.id}
            class:border-oxford-blue={dragSourceAgent?.id === agent.id}
          >
            <div class="flex items-center space-x-2">
              <div class="w-6 h-6 bg-oxford-blue text-white rounded flex items-center justify-center text-xs">
                <i class="fas {agent.data?.icon || 'fa-robot'}"></i>
              </div>
              <span class="text-sm font-medium truncate">{agent.data?.name || agent.type}</span>
            </div>
          </button>
        {/each}
      </div>
      {#if dragSourceAgent}
        <p class="text-xs text-blue-600 mt-2">
          <i class="fas fa-info-circle mr-1"></i>
          Click another agent to create connection from "{dragSourceAgent.data?.name || dragSourceAgent.type}"
        </p>
      {/if}
    </div>
  {/if}
</div>

<!-- Create Connection Modal -->
{#if showCreateConnectionModal}
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg p-6 w-full max-w-md mx-4">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900">Create New Connection</h3>
        <button
          class="text-gray-400 hover:text-gray-600"
          on:click={cancelNewConnection}
        >
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <div class="space-y-4">
        <!-- Source Agent -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">From Agent</label>
          <select
            bind:value={newConnectionSource}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          >
            <option value="">Select source agent...</option>
            {#each availableSourceAgents as agent}
              <option value={agent.id}>{agent.data?.name || agent.type}</option>
            {/each}
          </select>
        </div>
        
        <!-- Target Agent -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">To Agent</label>
          <select
            bind:value={newConnectionTarget}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          >
            <option value="">Select target agent...</option>
            {#each availableTargetAgents as agent}
              <option value={agent.id} disabled={agent.id === newConnectionSource}>
                {agent.data?.name || agent.type}
              </option>
            {/each}
          </select>
        </div>
        
        <!-- Connection Type -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Connection Type</label>
          <select
            bind:value={newConnectionType}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          >
            {#each connectionTypes as type}
              <option value={type.id}>{type.name}</option>
            {/each}
          </select>
          {#if newConnectionType !== 'default'}
            <p class="text-xs text-gray-600 mt-1">
              {connectionTypes.find(t => t.id === newConnectionType)?.description}
            </p>
          {/if}
        </div>
        
        <!-- Custom Label -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Label (Optional)</label>
          <input
            type="text"
            bind:value={newConnectionLabel}
            placeholder="Custom connection label..."
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue"
          />
        </div>
      </div>
      
      <!-- Modal Actions -->
      <div class="flex justify-end space-x-3 mt-6">
        <button
          class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          on:click={cancelNewConnection}
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 text-sm bg-oxford-blue text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          on:click={handleSaveNewConnection}
          disabled={!newConnectionSource || !newConnectionTarget}
        >
          <i class="fas fa-plus mr-1"></i>
          Create Connection
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  :global(.oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  
  :global(.focus\\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  :global(.focus\\:border-oxford-blue:focus) {
    border-color: #002147;
  }
</style>
