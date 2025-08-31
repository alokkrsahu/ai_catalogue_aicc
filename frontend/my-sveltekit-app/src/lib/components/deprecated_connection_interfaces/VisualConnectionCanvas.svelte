<!-- VisualConnectionCanvas.svelte - PowerPoint-style Visual Connection System -->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  
  export let nodes: any[] = [];
  export let edges: any[] = [];
  export let selectedConnection: any = null;
  
  const dispatch = createEventDispatcher();
  
  // Canvas state
  let canvasElement: SVGSVGElement;
  let canvasRect: DOMRect;
  let dragging = false;
  let draggedConnection: any = null;
  let tempConnection: any = null;
  
  // Connection creation state
  let isConnecting = false;
  let sourceNode: any = null;
  let mousePosition = { x: 0, y: 0 };
  
  // Connection types
  const connectionTypes = [
    { id: 'default', name: 'Default Flow', color: '#002147', strokeWidth: 2 },
    { id: 'conditional', name: 'Conditional', color: '#f59e0b', strokeWidth: 2 },
    { id: 'parallel', name: 'Parallel', color: '#10b981', strokeWidth: 2 },
    { id: 'feedback', name: 'Feedback Loop', color: '#ef4444', strokeWidth: 2 },
    { id: 'data', name: 'Data Flow', color: '#8b5cf6', strokeWidth: 2 }
  ];
  
  console.log('🎨 VISUAL CANVAS: Initialized with', nodes.length, 'nodes');
  
  onMount(() => {
    updateCanvasRect();
    window.addEventListener('resize', updateCanvasRect);
    
    return () => {
      window.removeEventListener('resize', updateCanvasRect);
    };
  });
  
  function updateCanvasRect() {
    if (canvasElement) {
      canvasRect = canvasElement.getBoundingClientRect();
    }
  }
  
  // Node position management
  function getNodePosition(nodeId: string) {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return { x: 0, y: 0 };
    
    // Use stored position or calculate from grid
    return node.position || calculateGridPosition(nodeId);
  }
  
  function calculateGridPosition(nodeId: string) {
    const index = nodes.findIndex(n => n.id === nodeId);
    const cols = Math.ceil(Math.sqrt(nodes.length));
    const row = Math.floor(index / cols);
    const col = index % cols;
    
    return {
      x: 120 + col * 250,
      y: 80 + row * 150
    };
  }
  
  function updateNodePosition(nodeId: string, position: { x: number; y: number }) {
    const nodeIndex = nodes.findIndex(n => n.id === nodeId);
    if (nodeIndex >= 0) {
      nodes[nodeIndex] = {
        ...nodes[nodeIndex],
        position
      };
      nodes = [...nodes]; // Trigger reactivity
      
      // Save position
      dispatch('nodeUpdate', nodes[nodeIndex]);
    }
  }
  
  // Connection point calculation
  function getConnectionPoint(nodeId: string, side: 'left' | 'right' | 'top' | 'bottom') {
    const position = getNodePosition(nodeId);
    const nodeWidth = 200;
    const nodeHeight = 80;
    
    switch (side) {
      case 'left':
        return { x: position.x, y: position.y + nodeHeight / 2 };
      case 'right':
        return { x: position.x + nodeWidth, y: position.y + nodeHeight / 2 };
      case 'top':
        return { x: position.x + nodeWidth / 2, y: position.y };
      case 'bottom':
        return { x: position.x + nodeWidth / 2, y: position.y + nodeHeight };
      default:
        return { x: position.x + nodeWidth / 2, y: position.y + nodeHeight / 2 };
    }
  }
  
  // Connection path generation
  function generateConnectionPath(sourceId: string, targetId: string) {
    const sourcePos = getConnectionPoint(sourceId, 'right');
    const targetPos = getConnectionPoint(targetId, 'left');
    
    // Create smooth curved path
    const midX = (sourcePos.x + targetPos.x) / 2;
    const controlOffset = Math.abs(targetPos.x - sourcePos.x) * 0.5;
    
    return `M ${sourcePos.x} ${sourcePos.y} C ${sourcePos.x + controlOffset} ${sourcePos.y}, ${targetPos.x - controlOffset} ${targetPos.y}, ${targetPos.x} ${targetPos.y}`;
  }
  
  // Drag and drop handlers
  function handleNodeMouseDown(event: MouseEvent, node: any) {
    if (event.button !== 0) return; // Only left mouse button
    
    event.preventDefault();
    event.stopPropagation();
    
    const startMousePos = { x: event.clientX, y: event.clientY };
    const startNodePos = getNodePosition(node.id);
    
    function handleMouseMove(e: MouseEvent) {
      const deltaX = e.clientX - startMousePos.x;
      const deltaY = e.clientY - startMousePos.y;
      
      updateNodePosition(node.id, {
        x: startNodePos.x + deltaX,
        y: startNodePos.y + deltaY
      });
    }
    
    function handleMouseUp() {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    }
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }
  
  // Connection creation handlers
  function handleConnectionStart(event: MouseEvent, node: any) {
    event.preventDefault();
    event.stopPropagation();
    
    isConnecting = true;
    sourceNode = node;
    mousePosition = { x: event.clientX, y: event.clientY };
    
    console.log('🔗 VISUAL CANVAS: Starting connection from', node.data.name);
    
    function handleMouseMove(e: MouseEvent) {
      if (!isConnecting) return;
      
      mousePosition = {
        x: e.clientX - canvasRect.left,
        y: e.clientY - canvasRect.top
      };
    }
    
    function handleMouseUp(e: MouseEvent) {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      
      // Check if we're over a target node
      const targetElement = document.elementFromPoint(e.clientX, e.clientY);
      const targetNodeId = targetElement?.getAttribute('data-node-id');
      
      if (targetNodeId && targetNodeId !== sourceNode?.id) {
        const targetNode = nodes.find(n => n.id === targetNodeId);
        if (targetNode) {
          createConnection(sourceNode, targetNode);
        }
      }
      
      // Reset state
      isConnecting = false;
      sourceNode = null;
      tempConnection = null;
    }
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }
  
  function createConnection(source: any, target: any) {
    // Check for duplicate
    const existingConnection = edges.find(edge => 
      edge.source === source.id && edge.target === target.id
    );
    
    if (existingConnection) {
      console.log('⚠️ VISUAL CANVAS: Connection already exists');
      return;
    }
    
    const newConnection = {
      id: `${source.id}-${target.id}`,
      source: source.id,
      target: target.id,
      type: 'default',
      data: {
        sourceAgent: source,
        targetAgent: target
      }
    };
    
    dispatch('connectionCreate', newConnection);
    console.log('✅ VISUAL CANVAS: Connection created:', newConnection.id);
  }
  
  function deleteConnection(connection: any) {
    dispatch('connectionDelete', connection);
  }
  
  function selectConnection(connection: any) {
    selectedConnection = connection;
    dispatch('connectionSelect', connection);
  }
  
  // Visual helpers
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
      case 'StartNode': return '#10b981';
      case 'UserProxyAgent': return '#3b82f6';
      case 'AssistantAgent': return '#002147';
      case 'GroupChatManager': return '#8b5cf6';
      default: return '#6b7280';
    }
  }
  
  function getConnectionStyle(connection: any) {
    const type = connectionTypes.find(t => t.id === connection.type) || connectionTypes[0];
    return {
      stroke: type.color,
      strokeWidth: selectedConnection?.id === connection.id ? type.strokeWidth + 1 : type.strokeWidth,
      strokeDasharray: connection.type === 'conditional' ? '8,4' : connection.type === 'parallel' ? '4,4' : 'none'
    };
  }
</script>

<div class="visual-canvas-container w-full h-full relative bg-gray-50 overflow-hidden">
  <!-- Canvas Instructions -->
  <div class="absolute top-4 left-4 z-10 bg-white rounded-lg shadow-lg p-3 border border-gray-200">
    <div class="flex items-center space-x-2 text-sm">
      <i class="fas fa-info-circle text-blue-500"></i>
      <span class="font-medium text-gray-900">Visual Connection Mode</span>
    </div>
    <div class="mt-2 text-xs text-gray-600 space-y-1">
      <div>• <strong>Drag agents</strong> to reposition</div>
      <div>• <strong>Ctrl+Click</strong> agent to start connection</div>
      <div>• <strong>Click target</strong> agent to complete connection</div>
      <div>• <strong>Click connection</strong> to select/delete</div>
    </div>
  </div>
  
  <!-- Canvas Statistics -->
  <div class="absolute top-4 right-4 z-10 bg-white rounded-lg shadow-lg p-3 border border-gray-200">
    <div class="text-sm font-medium text-gray-900 mb-1">Workflow Stats</div>
    <div class="text-xs text-gray-600 space-y-1">
      <div><i class="fas fa-robot mr-1"></i> {nodes.length} agents</div>
      <div><i class="fas fa-link mr-1"></i> {edges.length} connections</div>
      {#if selectedConnection}
        <div class="text-blue-600"><i class="fas fa-mouse-pointer mr-1"></i> Connection selected</div>
      {/if}
    </div>
  </div>
  
  <!-- Main Canvas -->
  <div class="w-full h-full relative">
    <!-- SVG Canvas for Connections -->
    <svg 
      bind:this={canvasElement}
      class="absolute inset-0 w-full h-full pointer-events-none"
      style="z-index: 1;"
    >
      <defs>
        <!-- Arrow markers for different connection types -->
        {#each connectionTypes as type}
          <marker 
            id="arrow-{type.id}" 
            viewBox="0 0 10 10" 
            refX="9" 
            refY="3" 
            markerWidth="6" 
            markerHeight="6" 
            orient="auto"
            fill={type.color}
          >
            <path d="M0,0 L0,6 L9,3 z"></path>
          </marker>
        {/each}
      </defs>
      
      <!-- Render existing connections -->
      {#each edges as connection}
        {@const style = getConnectionStyle(connection)}
        {@const path = generateConnectionPath(connection.source, connection.target)}
        
        <g class="connection-group pointer-events-auto cursor-pointer" on:click={() => selectConnection(connection)}>
          <!-- Invisible wider path for easier clicking -->
          <path 
            d={path}
            stroke="transparent"
            stroke-width="12"
            fill="none"
          />
          
          <!-- Visible connection path -->
          <path 
            d={path}
            stroke={style.stroke}
            stroke-width={style.strokeWidth}
            stroke-dasharray={style.strokeDasharray}
            fill="none"
            marker-end="url(#arrow-{connection.type || 'default'})"
            class="transition-all duration-200"
          />
          
          <!-- Connection label -->
          {#if connection.label}
            {@const sourcePos = getConnectionPoint(connection.source, 'right')}
            {@const targetPos = getConnectionPoint(connection.target, 'left')}
            {@const midX = (sourcePos.x + targetPos.x) / 2}
            {@const midY = (sourcePos.y + targetPos.y) / 2}
            
            <text 
              x={midX} 
              y={midY - 5} 
              text-anchor="middle" 
              class="text-xs fill-gray-600 font-medium"
              style="user-select: none;"
            >
              {connection.label}
            </text>
          {/if}
          
          <!-- Delete button for selected connection -->
          {#if selectedConnection?.id === connection.id}
            {@const sourcePos = getConnectionPoint(connection.source, 'right')}
            {@const targetPos = getConnectionPoint(connection.target, 'left')}
            {@const midX = (sourcePos.x + targetPos.x) / 2}
            {@const midY = (sourcePos.y + targetPos.y) / 2}
            
            <circle 
              cx={midX} 
              cy={midY + 15} 
              r="10" 
              fill="white" 
              stroke="#ef4444" 
              stroke-width="2"
              class="cursor-pointer"
              on:click|stopPropagation={() => deleteConnection(connection)}
            />
            <text 
              x={midX} 
              y={midY + 20} 
              text-anchor="middle" 
              class="text-xs fill-red-600 font-bold cursor-pointer"
              style="user-select: none;"
              on:click|stopPropagation={() => deleteConnection(connection)}
            >
              ×
            </text>
          {/if}
        </g>
      {/each}
      
      <!-- Temporary connection line while dragging -->
      {#if isConnecting && sourceNode}
        {@const sourcePos = getConnectionPoint(sourceNode.id, 'right')}
        <line 
          x1={sourcePos.x} 
          y1={sourcePos.y} 
          x2={mousePosition.x} 
          y2={mousePosition.y}
          stroke="#002147"
          stroke-width="2"
          stroke-dasharray="4,4"
          opacity="0.6"
        />
      {/if}
    </svg>
    
    <!-- Agent Nodes -->
    <div class="absolute inset-0" style="z-index: 2;">
      {#each nodes as node}
        {@const position = getNodePosition(node.id)}
        
        <div 
          class="absolute agent-node bg-white border-2 rounded-xl shadow-lg transition-all duration-200 hover:shadow-xl cursor-move select-none"
          style="left: {position.x}px; top: {position.y}px; width: 200px; height: 80px;"
          data-node-id={node.id}
          on:mousedown={(e) => handleNodeMouseDown(e, node)}
        >
          <!-- Agent Content -->
          <div class="h-full flex items-center p-3 space-x-3">
            <!-- Agent Icon -->
            <div 
              class="w-12 h-12 rounded-lg flex items-center justify-center text-white shadow-md"
              style="background-color: {getAgentColor(node.type)};"
            >
              <i class="fas {getAgentIcon(node.type)} text-lg"></i>
            </div>
            
            <!-- Agent Info -->
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-gray-900 truncate text-sm">
                {node.data?.name || node.type}
              </div>
              <div class="text-xs text-gray-600 truncate">
                {node.type}
              </div>
              <div class="text-xs text-gray-500 mt-1">
                <i class="fas fa-arrow-right mr-1"></i>
                {edges.filter(e => e.source === node.id).length} out •
                <i class="fas fa-arrow-left mr-1"></i>
                {edges.filter(e => e.target === node.id).length} in
              </div>
            </div>
          </div>
          
          <!-- Connection Handle -->
          <div 
            class="absolute right-0 top-1/2 transform translate-x-1/2 -translate-y-1/2 w-4 h-4 bg-oxford-blue rounded-full border-2 border-white shadow-lg cursor-crosshair hover:scale-110 transition-transform"
            on:mousedown|stopPropagation={(e) => handleConnectionStart(e, node)}
            title="Drag to create connection"
          >
            <div class="absolute inset-0 rounded-full bg-oxford-blue opacity-50 animate-ping"></div>
          </div>
          
          <!-- Input Handle -->
          <div 
            class="absolute left-0 top-1/2 transform -translate-x-1/2 -translate-y-1/2 w-3 h-3 bg-gray-400 rounded-full border-2 border-white shadow-md"
            title="Connection input"
          ></div>
        </div>
      {/each}
    </div>
    
    <!-- Empty State -->
    {#if nodes.length === 0}
      <div class="absolute inset-0 flex items-center justify-center">
        <div class="text-center">
          <div class="w-20 h-20 bg-gray-200 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
            <i class="fas fa-project-diagram text-3xl"></i>
          </div>
          <h3 class="text-lg font-medium text-gray-700 mb-2">Empty Canvas</h3>
          <p class="text-gray-500 mb-4">Add agents to start building your workflow</p>
          <div class="text-sm text-gray-400">
            <i class="fas fa-info-circle mr-1"></i>
            Use the agent palette to add components
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .agent-node {
    border-color: #e5e7eb;
    transition: all 0.2s ease;
  }
  
  .agent-node:hover {
    border-color: #002147;
    transform: translateY(-1px);
  }
  
  .connection-group:hover path {
    stroke-width: 3;
  }
  
  .visual-canvas-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  
  :global(.oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
</style>
