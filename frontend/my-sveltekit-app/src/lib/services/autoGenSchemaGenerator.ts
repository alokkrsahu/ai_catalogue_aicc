/**
 * AutoGen Schema Generator
 * Converts visual workflow graphs to AutoGen-compatible team configurations
 */

export interface AutoGenComponent {
  component_type: string;
  label?: string;
  description?: string;
  [key: string]: any;
}

export interface AutoGenModelClient extends AutoGenComponent {
  component_type: "OpenAIChatCompletionClient" | "AnthropicChatCompletionClient" | "AzureOpenAIChatCompletionClient";
  model: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  timeout?: number;
  base_url?: string;
  api_version?: string;
  azure_endpoint?: string;
  azure_deployment?: string;
}

export interface AutoGenTool extends AutoGenComponent {
  component_type: "FunctionTool";
  name: string;
  description: string;
  func: string;
  global_imports?: string[];
}

export interface AutoGenAgent extends AutoGenComponent {
  component_type: "AssistantAgent" | "UserProxyAgent" | "MultimodalWebSurfer";
  name: string;
  description?: string;
  system_message?: string;
  model_client: AutoGenModelClient;
  tools?: AutoGenTool[];
  handoffs?: string[];
  human_input_mode?: "ALWAYS" | "NEVER" | "TERMINATE";
  code_execution_config?: {
    work_dir: string;
    use_docker: boolean;
    timeout: number;
  };
}

export interface AutoGenTermination extends AutoGenComponent {
  component_type: "TextMentionTermination" | "MaxMessageTermination" | "TokenUsageTermination" | "TimeoutTermination" | "StopMessageTermination" | "HandoffTermination";
  text?: string;
  max_messages?: number;
  max_total_token?: number;
  max_prompt_token?: number;
  max_completion_token?: number;
  timeout_seconds?: number;
  target?: string;
}

export interface AutoGenTeamConfig extends AutoGenComponent {
  component_type: "SelectorGroupChat" | "RoundRobinGroupChat" | "Swarm";
  participants: AutoGenAgent[];
  termination_condition: AutoGenTermination;
  model_client?: AutoGenModelClient;
  selector_prompt?: string;
  allow_repeated_speaker?: boolean;
}

export class AutoGenSchemaGenerator {
  
  /**
   * Convert visual workflow graph to AutoGen team configuration
   */
  static generateTeamConfig(graph: { nodes: any[], edges: any[] }, projectCapabilities: any): AutoGenTeamConfig {
    console.log('🔧 AUTOGEN SCHEMA: Generating team config from graph', { 
      nodeCount: graph.nodes.length, 
      edgeCount: graph.edges.length 
    });

    // Filter out StartNode and EndNode - they're workflow markers, not AutoGen agents
    const agentNodes = graph.nodes.filter(node => 
      !['StartNode', 'EndNode'].includes(node.type)
    );

    // Convert nodes to AutoGen agents
    const participants = agentNodes.map(node => 
      this.convertNodeToAgent(node, projectCapabilities)
    );

    // Determine team type based on connections
    const teamType = this.determineTeamType(graph.edges, agentNodes);

    // Generate termination condition
    const termination = this.generateTerminationCondition(graph, projectCapabilities);

    // Create base team config
    const teamConfig: AutoGenTeamConfig = {
      component_type: teamType,
      participants,
      termination_condition: termination
    };

    // Add team-specific configuration
    if (teamType === "SelectorGroupChat") {
      teamConfig.model_client = this.createDefaultModelClient();
      teamConfig.selector_prompt = this.generateSelectorPrompt(participants);
      teamConfig.allow_repeated_speaker = true;
    }

    // Add handoffs for Swarm teams
    if (teamType === "Swarm") {
      this.addSwarmHandoffs(teamConfig, graph.edges);
    }

    console.log('✅ AUTOGEN SCHEMA: Generated team config', teamConfig);
    return teamConfig;
  }

  /**
   * Convert workflow node to AutoGen agent
   */
  static convertNodeToAgent(node: any, projectCapabilities: any): AutoGenAgent {
    const nodeData = node.data || {};
    
    console.log(`🤖 AUTOGEN SCHEMA: Converting ${node.type} to AutoGen agent`, nodeData);

    // Create model client from node configuration
    const modelClient = this.createModelClient(nodeData);

    // Base agent configuration
    const agent: AutoGenAgent = {
      component_type: this.mapNodeTypeToAutoGenType(node.type),
      name: nodeData.name || `${node.type}_${node.id.slice(-8)}`,
      description: nodeData.description || this.getDefaultDescription(node.type),
      model_client: modelClient
    };

    // Add type-specific configuration
    switch (node.type) {
      case 'AssistantAgent':
      case 'DocumentAnalyzerAgent':
      case 'HierarchicalProcessorAgent':
      case 'CategoryClassifierAgent':
      case 'ContentReconstructorAgent':
        agent.system_message = this.generateSystemMessage(node.type, nodeData, projectCapabilities);
        agent.tools = this.generateTools(node.type, nodeData, projectCapabilities);
        break;

      case 'UserProxyAgent':
        agent.human_input_mode = nodeData.require_human_input ? "ALWAYS" : "NEVER";
        agent.code_execution_config = {
          work_dir: `/tmp/autogen_${node.id.slice(-8)}`,
          use_docker: projectCapabilities.sandbox_execution || true,
          timeout: nodeData.timeout || 60
        };
        break;

      case 'GroupChatManager':
        agent.component_type = "AssistantAgent"; // GroupChatManager is handled at team level
        agent.system_message = this.generateGroupManagerSystemMessage(nodeData);
        break;
    }

    return agent;
  }

  /**
   * Map workflow node types to AutoGen agent types
   */
  static mapNodeTypeToAutoGenType(nodeType: string): string {
    const mapping: Record<string, string> = {
      'UserProxyAgent': 'UserProxyAgent',
      'AssistantAgent': 'AssistantAgent',
      'DocumentAnalyzerAgent': 'AssistantAgent',
      'HierarchicalProcessorAgent': 'AssistantAgent',
      'CategoryClassifierAgent': 'AssistantAgent',
      'ContentReconstructorAgent': 'AssistantAgent',
      'GroupChatManager': 'AssistantAgent',
      'FunctionTool': 'AssistantAgent'
    };
    
    return mapping[nodeType] || 'AssistantAgent';
  }

  /**
   * Create model client from node data
   */
  static createModelClient(nodeData: any): AutoGenModelClient {
    const provider = nodeData.llm_provider || 'openai';
    const model = nodeData.llm_model || 'gpt-4';

    const baseConfig = {
      model,
      temperature: nodeData.temperature || 0.7,
      max_tokens: nodeData.max_tokens || 2048,
      top_p: nodeData.top_p || 1.0,
      timeout: nodeData.timeout || 30
    };

    switch (provider) {
      case 'openai':
        return {
          component_type: "OpenAIChatCompletionClient",
          api_key: "placeholder", // Will be set from environment
          ...baseConfig
        };

      case 'anthropic':
        return {
          component_type: "AnthropicChatCompletionClient",
          api_key: "placeholder", // Will be set from environment
          model: model.includes('claude') ? model : 'claude-3-sonnet-20240229',
          temperature: baseConfig.temperature,
          max_tokens: baseConfig.max_tokens,
          timeout: baseConfig.timeout
        };

      case 'google':
        // Map to OpenAI-compatible for now, or implement Google client
        return {
          component_type: "OpenAIChatCompletionClient",
          base_url: "https://generativelanguage.googleapis.com/v1",
          api_key: "placeholder",
          model: model.includes('gemini') ? model : 'gemini-pro',
          ...baseConfig
        };

      default:
        return {
          component_type: "OpenAIChatCompletionClient",
          api_key: "placeholder",
          ...baseConfig
        };
    }
  }

  /**
   * Generate system message based on agent type
   */
  static generateSystemMessage(nodeType: string, nodeData: any, projectCapabilities: any): string {
    // If user provided custom system message, use it
    if (nodeData.system_message && nodeData.system_message.trim()) {
      return nodeData.system_message;
    }

    // Generate based on agent type
    switch (nodeType) {
      case 'DocumentAnalyzerAgent':
        return `You are a DocumentAnalyzerAgent specialized in comprehensive document analysis for the AICC-IntelliDoc platform.

Your primary responsibilities:
1. Analyze document structure and organization
2. Extract key sections and important content
3. Identify document types and classify content
4. Assess content complexity and processing requirements
5. Provide detailed analysis reports

${nodeData.doc_aware ? 'You have access to retrieve_documents() function to search project documents for context.' : ''}

Always provide structured, actionable insights that help users understand their documents better.`;

      case 'HierarchicalProcessorAgent':
        return `You are a HierarchicalProcessorAgent specialized in organizing and structuring document content.

Your primary responsibilities:
1. Create logical document hierarchies
2. Organize content into meaningful levels
3. Establish relationships between sections
4. Generate navigation structures
5. Maintain content integrity during organization

${nodeData.doc_aware ? 'Use retrieve_documents() to understand existing document structure and relationships.' : ''}

Always preserve the original meaning while improving organization and accessibility.`;

      case 'CategoryClassifierAgent':
        return `You are a CategoryClassifierAgent specialized in intelligent document categorization and tagging.

Your primary responsibilities:
1. Classify documents into appropriate categories
2. Assign relevant content tags
3. Determine subject areas and domains
4. Assess document importance and priority
5. Support multi-label classification

Categories include: legal, medical, technical, business, academic, personal

${nodeData.doc_aware ? 'Use retrieve_documents() to understand existing categorization patterns.' : ''}

Provide confidence scores and reasoning for your classifications.`;

      case 'ContentReconstructorAgent':
        return `You are a ContentReconstructorAgent specialized in rebuilding and organizing fragmented content.

Your primary responsibilities:
1. Reconstruct complete documents from chunks
2. Merge related content sections
3. Preserve original formatting and structure
4. Maintain content integrity and flow
5. Generate coherent, complete documents

${nodeData.doc_aware ? 'Use retrieve_documents() to access document chunks and metadata.' : ''}

Always ensure that reconstructed content maintains the original meaning and improves readability.`;

      case 'AssistantAgent':
      default:
        return `You are a helpful AI assistant specialized in document analysis and processing.

${nodeData.doc_aware ? 'You have access to retrieve_documents() function to search and analyze uploaded documents. Use this to provide context-aware responses based on the actual document content.' : ''}

Provide clear, accurate, and helpful responses. When analyzing documents, cite specific sections and provide actionable insights.`;
    }
  }

  /**
   * Generate tools for agents based on type and capabilities
   */
  static generateTools(nodeType: string, nodeData: any, projectCapabilities: any): AutoGenTool[] {
    const tools: AutoGenTool[] = [];

    // Add document-aware tools if enabled
    if (nodeData.doc_aware && projectCapabilities.supports_rag_agents) {
      tools.push({
        component_type: "FunctionTool",
        name: "retrieve_documents",
        description: "Search and retrieve relevant documents from the project collection",
        func: "retrieve_documents"
      });

      if (projectCapabilities.supports_hierarchical_processing) {
        tools.push({
          component_type: "FunctionTool",
          name: "hierarchical_search",
          description: "Search documents with hierarchical context and structure",
          func: "hierarchical_search"
        });
      }
    }

    // Add agent-specific tools
    switch (nodeType) {
      case 'DocumentAnalyzerAgent':
        tools.push({
          component_type: "FunctionTool",
          name: "analyze_document_structure",
          description: "Analyze the structure and organization of documents",
          func: "analyze_document_structure"
        });
        break;

      case 'CategoryClassifierAgent':
        tools.push({
          component_type: "FunctionTool",
          name: "classify_document",
          description: "Classify documents into predefined categories",
          func: "classify_document"
        });
        break;

      case 'ContentReconstructorAgent':
        tools.push({
          component_type: "FunctionTool",
          name: "reconstruct_content",
          description: "Reconstruct complete content from document chunks",
          func: "reconstruct_content"
        });
        break;
    }

    return tools;
  }

  /**
   * Determine team type based on workflow structure
   */
  static determineTeamType(edges: any[], nodes: any[]): "SelectorGroupChat" | "RoundRobinGroupChat" | "Swarm" {
    // If only 1 agent, use RoundRobin
    if (nodes.length <= 1) {
      return "RoundRobinGroupChat";
    }

    // Check for handoff patterns (Swarm)
    const hasHandoffs = edges.some(edge => edge.type === 'handoff');
    if (hasHandoffs) {
      return "Swarm";
    }

    // Check for complex routing patterns (SelectorGroupChat)
    const hasComplexRouting = edges.some(edge => 
      ['conditional', 'broadcast', 'group_chat'].includes(edge.type)
    );
    if (hasComplexRouting || nodes.length > 2) {
      return "SelectorGroupChat";
    }

    // Default to RoundRobin for simple workflows
    return "RoundRobinGroupChat";
  }

  /**
   * Generate termination condition
   */
  static generateTerminationCondition(graph: any, projectCapabilities: any): AutoGenTermination {
    // For now, use a simple combined termination
    // In the future, this could be made configurable in the UI
    
    // Create TextMentionTermination OR MaxMessageTermination
    return {
      component_type: "MaxMessageTermination",
      max_messages: projectCapabilities.max_messages || 20
    };
  }

  /**
   * Generate selector prompt for SelectorGroupChat
   */
  static generateSelectorPrompt(participants: AutoGenAgent[]): string {
    const roleDescriptions = participants.map(agent => 
      `${agent.name}: ${agent.description || 'AI assistant'}`
    ).join('\n');

    return `You are coordinating a team conversation. The following team members are available:
${roleDescriptions}

Given the current context and conversation, select the most appropriate team member to speak next.
Base your selection on:
1. The expertise needed for the current task
2. The flow of conversation
3. Which agent can best contribute to solving the problem

Read the following conversation. Then select the next role from {participants} to play. Only return the role.

{history}

Read the above conversation. Then select the next role from {participants} to play. Only return the role.`;
  }

  /**
   * Add handoff configuration for Swarm teams
   */
  static addSwarmHandoffs(teamConfig: AutoGenTeamConfig, edges: any[]): void {
    // Add handoffs based on edge connections
    teamConfig.participants.forEach(agent => {
      const handoffs: string[] = [];
      edges.forEach(edge => {
        if (edge.source === agent.name && edge.type === 'handoff') {
          const targetAgent = teamConfig.participants.find(p => p.name === edge.target);
          if (targetAgent) {
            handoffs.push(targetAgent.name);
          }
        }
      });
      if (handoffs.length > 0) {
        agent.handoffs = handoffs;
      }
    });
  }

  /**
   * Create default model client for team-level operations
   */
  static createDefaultModelClient(): AutoGenModelClient {
    return {
      component_type: "OpenAIChatCompletionClient",
      model: "gpt-4o-mini",
      api_key: "placeholder",
      temperature: 0.3,
      max_tokens: 1024,
      timeout: 30
    };
  }

  /**
   * Get default description for agent types
   */
  static getDefaultDescription(nodeType: string): string {
    const descriptions: Record<string, string> = {
      'UserProxyAgent': 'Human-in-the-loop agent for user interaction and code execution',
      'AssistantAgent': 'AI assistant for general task completion and reasoning',
      'DocumentAnalyzerAgent': 'Specialized agent for comprehensive document analysis',
      'HierarchicalProcessorAgent': 'Agent for organizing content into hierarchical structures',
      'CategoryClassifierAgent': 'Agent for intelligent document categorization',
      'ContentReconstructorAgent': 'Agent for reconstructing content from fragments',
      'GroupChatManager': 'Coordinator for multi-agent conversations'
    };
    
    return descriptions[nodeType] || 'AI assistant agent';
  }

  /**
   * Generate system message for group chat managers
   */
  static generateGroupManagerSystemMessage(nodeData: any): string {
    return `You are a group chat manager coordinating a team of AI agents for document analysis and processing.

Your responsibilities:
1. Facilitate smooth conversation flow between agents
2. Ensure all agents contribute their expertise
3. Guide the team toward task completion
4. Summarize results and insights

${nodeData.doc_aware ? 'You can access document content to provide context-aware coordination.' : ''}

Keep the conversation focused and productive while allowing each agent to contribute their specialized knowledge.`;
  }
}
