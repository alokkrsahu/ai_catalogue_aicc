/**
 * Enhanced AutoGen Workflow Execution Service
 * Integrates with existing AICC-IntelliDoc architecture
 */

import { AutoGenSchemaGenerator, type AutoGenTeamConfig } from './autoGenSchemaGenerator';
import { cleanUniversalApi } from './cleanUniversalApi';
import { toasts } from '$lib/stores/toast';

export interface WorkflowExecutionRequest {
  workflowId: string;
  projectId: string;
  initialMessage: string;
  graph: { nodes: any[], edges: any[] };
  projectCapabilities: any;
}

export interface WorkflowExecutionResult {
  success: boolean;
  runId?: string;
  teamConfig?: AutoGenTeamConfig;
  error?: string;
  executionType: 'autogen' | 'simulation';
}

export class EnhancedWorkflowExecutor {
  
  /**
   * Execute workflow with AutoGen integration
   */
  static async executeWorkflow(request: WorkflowExecutionRequest): Promise<WorkflowExecutionResult> {
    console.log('🚀 ENHANCED EXECUTOR: Starting workflow execution', {
      workflowId: request.workflowId,
      projectId: request.projectId,
      nodeCount: request.graph.nodes.length
    });

    try {
      // Step 1: Generate AutoGen team configuration
      const teamConfig = AutoGenSchemaGenerator.generateTeamConfig(
        request.graph, 
        request.projectCapabilities
      );

      console.log('✅ ENHANCED EXECUTOR: Generated AutoGen team config', teamConfig);

      // Step 2: Validate the team configuration
      const validation = this.validateTeamConfig(teamConfig);
      if (!validation.valid) {
        throw new Error(`Team validation failed: ${validation.errors.join(', ')}`);
      }

      // Step 3: Start execution via universal API
      const executionResult = await cleanUniversalApi.executeWorkflow(
        request.projectId,
        request.workflowId,
        {
          team_config: teamConfig,
          initial_message: request.initialMessage,
          execution_type: 'autogen',
          project_capabilities: request.projectCapabilities
        }
      );

      console.log('✅ ENHANCED EXECUTOR: Workflow execution started', executionResult);

      return {
        success: true,
        runId: executionResult.run_id,
        teamConfig,
        executionType: 'autogen'
      };

    } catch (error) {
      console.error('❌ ENHANCED EXECUTOR: Execution failed', error);
      
      // Fallback to simulation if AutoGen execution fails
      return await this.fallbackToSimulation(request, error);
    }
  }

  /**
   * Validate AutoGen team configuration
   */
  static validateTeamConfig(teamConfig: AutoGenTeamConfig): { valid: boolean, errors: string[] } {
    const errors: string[] = [];

    // Check required fields
    if (!teamConfig.component_type) {
      errors.push('Team component_type is required');
    }

    if (!teamConfig.participants || teamConfig.participants.length === 0) {
      errors.push('Team must have at least one participant');
    }

    if (!teamConfig.termination_condition) {
      errors.push('Team must have a termination condition');
    }

    // Validate participants
    teamConfig.participants?.forEach((agent, index) => {
      if (!agent.component_type) {
        errors.push(`Agent ${index}: component_type is required`);
      }
      
      if (!agent.name) {
        errors.push(`Agent ${index}: name is required`);
      }

      if (!agent.model_client) {
        errors.push(`Agent ${index}: model_client is required`);
      } else {
        // Validate model client
        if (!agent.model_client.component_type) {
          errors.push(`Agent ${index}: model_client.component_type is required`);
        }
        if (!agent.model_client.model) {
          errors.push(`Agent ${index}: model_client.model is required`);
        }
      }
    });

    // Validate termination condition
    if (teamConfig.termination_condition && !teamConfig.termination_condition.component_type) {
      errors.push('Termination condition component_type is required');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Fallback to simulation when AutoGen execution fails
   */
  static async fallbackToSimulation(request: WorkflowExecutionRequest, originalError: any): Promise<WorkflowExecutionResult> {
    console.log('🎭 ENHANCED EXECUTOR: Falling back to simulation', originalError);

    try {
      // Use existing simulation execution
      const simulationResult = await cleanUniversalApi.executeWorkflow(
        request.projectId,
        request.workflowId,
        {
          execution_type: 'simulation',
          initial_message: request.initialMessage,
          fallback_reason: originalError.message
        }
      );

      toasts.warning('AutoGen execution failed - using enhanced simulation mode');

      return {
        success: true,
        runId: simulationResult.run_id,
        executionType: 'simulation',
        error: `AutoGen fallback: ${originalError.message}`
      };

    } catch (fallbackError) {
      console.error('❌ ENHANCED EXECUTOR: Simulation fallback also failed', fallbackError);

      return {
        success: false,
        executionType: 'simulation',
        error: `Both AutoGen and simulation failed: ${originalError.message} | ${fallbackError.message}`
      };
    }
  }

  /**
   * Stream workflow execution results
   */
  static async *streamWorkflowExecution(runId: string, projectId: string): AsyncGenerator<any, void, unknown> {
    // This would connect to your WebSocket streaming
    // For now, we'll use polling as a fallback
    
    console.log('📡 ENHANCED EXECUTOR: Starting result streaming for run', runId);

    try {
      let lastMessageCount = 0;
      let isComplete = false;

      while (!isComplete) {
        // Poll for new messages
        const runData = await cleanUniversalApi.getSimulationRun(projectId, runId);
        
        if (runData.messages && runData.messages.length > lastMessageCount) {
          // Yield new messages
          const newMessages = runData.messages.slice(lastMessageCount);
          for (const message of newMessages) {
            yield {
              type: 'message',
              data: message
            };
          }
          lastMessageCount = runData.messages.length;
        }

        // Check if run is complete
        if (['completed', 'failed', 'stopped'].includes(runData.status)) {
          isComplete = true;
          yield {
            type: 'completion',
            data: runData,
            status: runData.status
          };
        }

        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

    } catch (error) {
      console.error('❌ ENHANCED EXECUTOR: Streaming error', error);
      yield {
        type: 'error',
        error: error.message
      };
    }
  }

  /**
   * Get execution status and results
   */
  static async getExecutionStatus(runId: string, projectId: string): Promise<any> {
    try {
      const runData = await cleanUniversalApi.getSimulationRun(projectId, runId);
      
      return {
        status: runData.status,
        messageCount: runData.messages?.length || 0,
        duration: runData.duration_seconds,
        result: runData.result_summary,
        error: runData.error_message
      };

    } catch (error) {
      console.error('❌ ENHANCED EXECUTOR: Failed to get execution status', error);
      throw error;
    }
  }

  /**
   * Preview team configuration without execution
   */
  static generateTeamConfigPreview(graph: { nodes: any[], edges: any[] }, projectCapabilities: any): {
    teamConfig: AutoGenTeamConfig;
    validation: { valid: boolean, errors: string[] };
    executionEstimate: {
      agentCount: number;
      estimatedDuration: string;
      complexity: 'low' | 'medium' | 'high';
      requirements: string[];
    };
  } {
    // Generate team config
    const teamConfig = AutoGenSchemaGenerator.generateTeamConfig(graph, projectCapabilities);
    
    // Validate
    const validation = this.validateTeamConfig(teamConfig);
    
    // Generate execution estimate
    const agentCount = teamConfig.participants.length;
    const complexity = agentCount <= 2 ? 'low' : agentCount <= 5 ? 'medium' : 'high';
    
    const executionEstimate = {
      agentCount,
      estimatedDuration: this.estimateExecutionTime(agentCount, graph.edges.length),
      complexity,
      requirements: this.getExecutionRequirements(teamConfig, projectCapabilities)
    };

    return {
      teamConfig,
      validation,
      executionEstimate
    };
  }

  /**
   * Estimate execution time based on workflow complexity
   */
  static estimateExecutionTime(agentCount: number, connectionCount: number): string {
    const baseTime = 30; // Base 30 seconds
    const agentTime = agentCount * 15; // 15 seconds per agent
    const connectionTime = connectionCount * 5; // 5 seconds per connection
    
    const totalSeconds = baseTime + agentTime + connectionTime;
    
    if (totalSeconds < 60) {
      return `${totalSeconds} seconds`;
    } else if (totalSeconds < 300) {
      return `${Math.round(totalSeconds / 60)} minutes`;
    } else {
      return `${Math.round(totalSeconds / 60)} - ${Math.round(totalSeconds / 60) + 2} minutes`;
    }
  }

  /**
   * Get execution requirements
   */
  static getExecutionRequirements(teamConfig: AutoGenTeamConfig, projectCapabilities: any): string[] {
    const requirements: string[] = [];

    // Check LLM providers
    const providers = new Set(teamConfig.participants.map(agent => 
      agent.model_client.component_type.replace('ChatCompletionClient', '')
    ));
    
    providers.forEach(provider => {
      requirements.push(`${provider} API key required`);
    });

    // Check for special capabilities
    const hasDocAware = teamConfig.participants.some(agent => 
      agent.tools?.some(tool => tool.name === 'retrieve_documents')
    );
    
    if (hasDocAware) {
      requirements.push('Document processing and vector search');
    }

    const hasCodeExecution = teamConfig.participants.some(agent => 
      agent.code_execution_config
    );
    
    if (hasCodeExecution) {
      requirements.push('Code execution environment');
    }

    const hasHumanInput = teamConfig.participants.some(agent => 
      agent.human_input_mode === 'ALWAYS'
    );
    
    if (hasHumanInput) {
      requirements.push('Human interaction required');
    }

    return requirements;
  }

  /**
   * Export team configuration for external use
   */
  static exportTeamConfig(teamConfig: AutoGenTeamConfig, format: 'json' | 'yaml' = 'json'): string {
    if (format === 'json') {
      return JSON.stringify(teamConfig, null, 2);
    } else {
      // Simple YAML conversion (you might want to use a proper YAML library)
      return this.objectToYaml(teamConfig);
    }
  }

  /**
   * Simple object to YAML converter
   */
  static objectToYaml(obj: any, indent = 0): string {
    const spaces = '  '.repeat(indent);
    let yaml = '';

    for (const [key, value] of Object.entries(obj)) {
      if (value === null || value === undefined) {
        yaml += `${spaces}${key}: null\n`;
      } else if (typeof value === 'object' && !Array.isArray(value)) {
        yaml += `${spaces}${key}:\n${this.objectToYaml(value, indent + 1)}`;
      } else if (Array.isArray(value)) {
        yaml += `${spaces}${key}:\n`;
        value.forEach(item => {
          if (typeof item === 'object') {
            yaml += `${spaces}  -\n${this.objectToYaml(item, indent + 2)}`;
          } else {
            yaml += `${spaces}  - ${item}\n`;
          }
        });
      } else if (typeof value === 'string') {
        yaml += `${spaces}${key}: "${value}"\n`;
      } else {
        yaml += `${spaces}${key}: ${value}\n`;
      }
    }

    return yaml;
  }
}

export default EnhancedWorkflowExecutor;
