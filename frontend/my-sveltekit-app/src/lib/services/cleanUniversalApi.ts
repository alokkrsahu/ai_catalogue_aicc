/**
 * Clean Universal API Service - Template Independent
 * 
 * CRITICAL: This is the ONLY API service that projects should use
 * ALL projects use these SAME endpoints regardless of source template
 * 
 * Architecture: Universal endpoints only, no template-specific calls
 */

import { get } from 'svelte/store';
import authStore, { logout } from '$lib/stores/auth';

const API_BASE = '/api';

export class CleanUniversalApiService {
  
  /**
   * 🔧 Handle 401 errors with automatic token refresh
   * Similar to api.ts Axios interceptor but for fetch-based calls
   */
  private async handleAuthenticatedRequest(url: string, options: RequestInit, retryCount = 0): Promise<Response> {
    const response = await fetch(url, options);
    
    // If 401 and we have a refresh token, try to refresh
    if (response.status === 401 && retryCount === 0) {
      const auth = get(authStore);
      
      if (auth.refreshToken) {
        console.log('🔄 UNIVERSAL: Token expired, attempting refresh...');
        
        try {
          // Attempt token refresh using the same refresh mechanism as api.ts
          const refreshResponse = await fetch('/api/token/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: auth.refreshToken })
          });
          
          if (refreshResponse.ok) {
            const refreshData = await refreshResponse.json();
            
            // Update auth store with new token
            authStore.update(state => ({
              ...state,
              token: refreshData.access,
            }));
            
            console.log('✅ UNIVERSAL: Token refreshed successfully');
            
            // Retry original request with new token
            const newHeaders = {
              ...options.headers,
              'Authorization': `Bearer ${refreshData.access}`
            };
            
            return await fetch(url, {
              ...options,
              headers: newHeaders
            });
          } else {
            console.error('❌ UNIVERSAL: Token refresh failed');
            logout();
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
          }
        } catch (refreshError) {
          console.error('❌ UNIVERSAL: Token refresh error:', refreshError);
          logout();
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
        }
      } else {
        console.error('❌ UNIVERSAL: No refresh token available');
        logout();
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
      }
    }
    
    return response;
  }
  private getAuthHeaders(): HeadersInit {
    const auth = get(authStore);
    if (!auth.token || !auth.isAuthenticated) {
      console.warn('⚠️ UNIVERSAL: No valid authentication token found');
    }
    return {
      'Content-Type': 'application/json',
      'Authorization': auth.token ? `Bearer ${auth.token}` : '',
    };
  }

  private getAuthHeadersForFormData(): HeadersInit {
    const auth = get(authStore);
    return {
      'Authorization': auth.token ? `Bearer ${auth.token}` : '',
    };
  }

  // ============================================================================
  // PROJECT MANAGEMENT (Universal - same for ALL projects)
  // ============================================================================

  /**
   * Create project from template (Universal endpoint)
   */
  async createProject(data: {
    name: string;
    description: string;
    template_id: string;
  }): Promise<any> {
    console.log('🏗️ UNIVERSAL: Creating project via /api/projects/', data);
    
    const response = await fetch(`${API_BASE}/projects/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `Create project failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Project created successfully:', result);
    return result;
  }

  /**
   * Get project details (Universal endpoint)
   */
  async getProject(projectId: string): Promise<any> {
    console.log(`📄 UNIVERSAL: Getting project via /api/projects/${projectId}/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Authentication failed - redirect to login
        console.error('❌ UNIVERSAL: Authentication failed - redirecting to login');
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        throw new Error('Authentication required');
      }
      throw new Error(`Get project failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Project retrieved successfully');
    return result;
  }

  /**
   * Get all projects for user (Universal endpoint)
   */
  async getAllProjects(): Promise<any[]> {
    console.log('📋 UNIVERSAL: Getting all projects via /api/projects/');
    
    const response = await fetch(`${API_BASE}/projects/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Authentication failed - redirect to login
        console.error('❌ UNIVERSAL: Authentication failed - redirecting to login');
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        throw new Error('Authentication required');
      }
      throw new Error(`Get projects failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Retrieved ${result.projects?.length || 0} projects`);
    return result.projects || result;
  }

  /**
   * Update project (Universal endpoint)
   */
  async updateProject(projectId: string, data: any): Promise<any> {
    console.log(`📝 UNIVERSAL: Updating project via /api/projects/${projectId}/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/`, {
      method: 'PATCH',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Update project failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Project updated successfully');
    return result;
  }

  /**
   * Delete project (Universal endpoint)
   */
  async deleteProject(projectId: string, password: string): Promise<void> {
    console.log(`🗑️ UNIVERSAL: Deleting project via /api/projects/${projectId}/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      throw new Error(`Delete project failed: ${response.status}`);
    }

    console.log('✅ UNIVERSAL: Project deleted successfully');
  }

  // ============================================================================
  // DOCUMENT MANAGEMENT (Universal - same for ALL projects)
  // ============================================================================

  /**
   * Get project documents (Universal endpoint)
   */
  async getDocuments(projectId: string): Promise<any[]> {
    console.log(`📄 UNIVERSAL: Getting documents via /api/projects/${projectId}/documents/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/documents/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get documents failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Retrieved ${result.length || 0} documents`);
    return result.documents || result;
  }

  /**
   * Upload documents (Universal endpoint)
   */
  async uploadDocument(projectId: string, file: File): Promise<any> {
    console.log(`📤 UNIVERSAL: Uploading document via /api/projects/${projectId}/upload_document/`);
    
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/projects/${projectId}/upload_document/`, {
      method: 'POST',
      headers: this.getAuthHeadersForFormData(),
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Document uploaded successfully');
    return result;
  }

  /**
   * Upload multiple files (Universal endpoint)
   */
  async uploadBulkFiles(projectId: string, files: File[]): Promise<any> {
    console.log(`📤 UNIVERSAL: Uploading ${files.length} files via /api/projects/${projectId}/upload_bulk_files/`);
    
    const formData = new FormData();
    files.forEach((file, index) => {
      formData.append(`file_${index}`, file);
    });

    const response = await fetch(`${API_BASE}/projects/${projectId}/upload_bulk_files/`, {
      method: 'POST',
      headers: this.getAuthHeadersForFormData(),
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Bulk upload failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Bulk upload completed: ${result.total_successful} successful, ${result.total_failed} failed`);
    return result;
  }

  /**
   * Upload zip file and extract contents (Universal endpoint)
   */
  async uploadZipFile(projectId: string, zipFile: File): Promise<any> {
    console.log(`📦 UNIVERSAL: Uploading zip file via /api/projects/${projectId}/upload_zip_file/`);
    
    const formData = new FormData();
    formData.append('file', zipFile);

    const response = await fetch(`${API_BASE}/projects/${projectId}/upload_zip_file/`, {
      method: 'POST',
      headers: this.getAuthHeadersForFormData(),
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `Zip upload failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Zip extraction completed: ${result.total_extracted} files extracted, ${result.total_failed} failed`);
    return result;
  }

  /**
   * Delete document (Universal endpoint)
   */
  async deleteDocument(projectId: string, documentId: string): Promise<void> {
    console.log(`🗑️ UNIVERSAL: Deleting document via /api/projects/${projectId}/delete_document/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/delete_document/`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ document_id: documentId }),
    });

    if (!response.ok) {
      throw new Error(`Delete document failed: ${response.status}`);
    }

    console.log('✅ UNIVERSAL: Document deleted successfully');
  }

  // ============================================================================
  // DOCUMENT PROCESSING (Universal - same for ALL projects)
  // ============================================================================

  /**
   * Process documents (Universal endpoint)
   */
  async processDocuments(projectId: string): Promise<any> {
    console.log(`🚀 UNIVERSAL: Processing documents via /api/projects/${projectId}/process_documents/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/process_documents/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Process documents failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Document processing started successfully');
    return result;
  }

  /**
   * Get processing status (Universal endpoint)
   */
  async getProcessingStatus(projectId: string): Promise<any> {
    console.log(`📊 UNIVERSAL: Getting status via /api/projects/${projectId}/vector-status/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/vector-status/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get status failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Status retrieved successfully');
    return result;
  }

  // ============================================================================
  // DOCUMENT SEARCH (Universal - same for ALL projects)
  // ============================================================================

  /**
   * Search documents (Universal endpoint)
   */
  async searchDocuments(projectId: string, query: string, limit: number = 5): Promise<any> {
    console.log(`🔍 UNIVERSAL: Searching documents via /api/projects/${projectId}/search/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/search/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ query, limit }),
    });

    if (!response.ok) {
      throw new Error(`Search failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Search completed, ${result.total_results || 0} results`);
    return result;
  }

  // ============================================================================
  // TEMPLATE DISCOVERY (Template management only)
  // ============================================================================

  /**
   * Get available templates (Template management)
   */
  async getTemplates(): Promise<any[]> {
    console.log('🔍 TEMPLATE: Getting templates via /api/project-templates/');
    
    const response = await fetch(`${API_BASE}/project-templates/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get templates failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ TEMPLATE: Retrieved ${result.templates?.length || 0} templates`);
    return result.templates || result;
  }

  /**
   * Get template configuration (Template management)
   */
  async getTemplateConfiguration(templateId: string): Promise<any> {
    console.log(`🔍 TEMPLATE: Getting configuration via /api/templates/${templateId}/discover/`);
    
    const response = await fetch(`${API_BASE}/templates/${templateId}/discover/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get template configuration failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ TEMPLATE: Configuration retrieved successfully');
    return result;
  }

  // ============================================================================
  // AGENT ORCHESTRATION (Universal - same for ALL projects)
  // ============================================================================

  /**
   * Get agent workflows for project (Universal endpoint) - WITH TOKEN REFRESH
   */
  async getAgentWorkflows(projectId: string): Promise<any[]> {
    console.log(`🤖 UNIVERSAL: Getting agent workflows via /api/projects/${projectId}/agent_workflows/`);
    
    const response = await this.handleAuthenticatedRequest(`${API_BASE}/projects/${projectId}/agent_workflows/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get agent workflows failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Retrieved ${result.workflows?.length || 0} agent workflows`);
    return result.workflows || [];
  }

  /**
   * Create agent workflow (Universal endpoint) - WITH TOKEN REFRESH
   */
  async createAgentWorkflow(projectId: string, workflowData: any): Promise<any> {
    console.log(`🤖 UNIVERSAL: Creating agent workflow via /api/projects/${projectId}/agent_workflows/`);
    
    const response = await this.handleAuthenticatedRequest(`${API_BASE}/projects/${projectId}/agent_workflows/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(workflowData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `Create workflow failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Agent workflow created successfully');
    return result;
  }

  /**
   * Get single agent workflow (Universal endpoint) - WITH TOKEN REFRESH
   */
  async getAgentWorkflow(projectId: string, workflowId: string): Promise<any> {
    console.log(`🤖 UNIVERSAL: Getting workflow via /api/projects/${projectId}/agent_workflow/?workflow_id=${workflowId}`);
    
    const response = await this.handleAuthenticatedRequest(`${API_BASE}/projects/${projectId}/agent_workflow/?workflow_id=${workflowId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get workflow failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Agent workflow retrieved successfully');
    return result;
  }

  /**
   * Update agent workflow (Universal endpoint)
   */
  async updateAgentWorkflow(projectId: string, workflowId: string, updateData: any): Promise<any> {
    console.log(`🤖 UNIVERSAL: Updating workflow via /api/projects/${projectId}/agent_workflow/?workflow_id=${workflowId}`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/agent_workflow/?workflow_id=${workflowId}`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(updateData),
    });

    if (!response.ok) {
      throw new Error(`Update workflow failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Agent workflow updated successfully');
    return result;
  }

  /**
   * Delete agent workflow (Universal endpoint)
   */
  async deleteAgentWorkflow(projectId: string, workflowId: string): Promise<void> {
    console.log(`🗑️ UNIVERSAL: Deleting workflow via /api/projects/${projectId}/agent_workflow/?workflow_id=${workflowId}`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/agent_workflow/?workflow_id=${workflowId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Delete workflow failed: ${response.status}`);
    }

    console.log('✅ UNIVERSAL: Agent workflow deleted successfully');
  }

  /**
   * Execute agent workflow (Universal endpoint) - WITH TOKEN REFRESH
   */
  async executeWorkflow(projectId: string, workflowId: string, executionParameters: any = {}): Promise<any> {
    console.log(`🚀 UNIVERSAL: Executing workflow via /api/projects/${projectId}/execute_workflow/`);
    
    const response = await this.handleAuthenticatedRequest(`${API_BASE}/projects/${projectId}/execute_workflow/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({
        workflow_id: workflowId,
        execution_parameters: executionParameters,
        environment: 'production'
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `Execute workflow failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Workflow execution queued successfully');
    return result;
  }

  /**
   * Get simulation runs (Universal endpoint)
   */
  async getSimulationRuns(projectId: string, limit?: number): Promise<any> {
    const url = limit 
      ? `${API_BASE}/projects/${projectId}/simulation_runs/?limit=${limit}`
      : `${API_BASE}/projects/${projectId}/simulation_runs/`;
    
    console.log(`📊 UNIVERSAL: Getting simulation runs via ${url}`);
    
    const response = await fetch(url, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get simulation runs failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Retrieved ${result.simulation_runs?.length || 0} simulation runs`);
    return result;
  }

  /**
   * Get single simulation run with messages (Universal endpoint)
   */
  async getSimulationRun(projectId: string, runId: string): Promise<any> {
    console.log(`📊 UNIVERSAL: Getting simulation run via /api/projects/${projectId}/simulation_run/?run_id=${runId}`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/simulation_run/?run_id=${runId}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get simulation run failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Retrieved simulation run with ${result.messages?.length || 0} messages`);
    return result;
  }

  /**
   * Stop simulation run (Universal endpoint)
   */
  async stopSimulation(projectId: string, runId: string): Promise<any> {
    console.log(`⏹️ UNIVERSAL: Stopping simulation via /api/projects/${projectId}/stop_simulation/`);
    
    const response = await fetch(`${API_BASE}/projects/${projectId}/stop_simulation/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({ run_id: runId }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `Stop simulation failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: Simulation stopped successfully');
    return result;
  }

  /**
   * Validate workflow graph (Universal endpoint)
   */
  async validateWorkflowGraph(projectId: string, graphJson: any): Promise<any> {
    console.log(`✅ UNIVERSAL: Validating workflow graph for project ${projectId}`);
    
    // This would typically be a separate endpoint, but for now we'll validate locally
    // In a full implementation, this could call a dedicated validation endpoint
    
    try {
      // Basic validation
      if (!graphJson.nodes || !Array.isArray(graphJson.nodes)) {
        throw new Error('Graph must contain nodes array');
      }
      
      if (!graphJson.edges || !Array.isArray(graphJson.edges)) {
        throw new Error('Graph must contain edges array');
      }
      
      // Check for start node
      const hasStartNode = graphJson.nodes.some((node: any) => node.type === 'StartNode');
      if (!hasStartNode) {
        throw new Error('Workflow must contain a Start Node');
      }
      
      console.log('✅ UNIVERSAL: Workflow graph validation passed');
      return {
        valid: true,
        message: 'Workflow graph is valid',
        node_count: graphJson.nodes.length,
        edge_count: graphJson.edges.length
      };
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Workflow graph validation failed:', error);
      return {
        valid: false,
        message: error.message,
        node_count: graphJson.nodes?.length || 0,
        edge_count: graphJson.edges?.length || 0
      };
    }
  }

  // ============================================================================
  // PROJECT API KEY MANAGEMENT
  // ============================================================================

  /**
   * Get project API keys
   */
  async getProjectApiKeys(projectId: string): Promise<any[]> {
    console.log(`🔑 UNIVERSAL: Getting API keys for project ${projectId}`);
    
    const response = await fetch(`${API_BASE}/project-api-keys/project/${projectId}/keys/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get API keys failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ UNIVERSAL: Retrieved ${result.api_keys?.length || 0} API keys`);
    return result.api_keys || [];
  }

  /**
   * Save project API key
   */
  async saveProjectApiKey(projectId: string, keyData: any): Promise<any> {
    console.log(`🔑 UNIVERSAL: Saving API key for project ${projectId}`);
    
    const response = await fetch(`${API_BASE}/project-api-keys/project/${projectId}/keys/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(keyData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Save API key failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: API key saved successfully');
    return result.api_key || result;
  }

  /**
   * Update project API key (via re-setting with same provider)
   */
  async updateProjectApiKey(projectId: string, keyId: string, keyData: any): Promise<any> {
    console.log(`🔑 UNIVERSAL: Updating API key ${keyId} for project ${projectId}`);
    
    // For updates, we use the same endpoint as creation but with provider_type from existing key
    const response = await fetch(`${API_BASE}/project-api-keys/project/${projectId}/keys/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({
        ...keyData,
        // Ensure we're updating, not creating a duplicate
        validate_key: keyData.validate_key !== undefined ? keyData.validate_key : false
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Update API key failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: API key updated successfully');
    return result.api_key || result;
  }

  /**
   * Delete project API key
   */
  async deleteProjectApiKey(projectId: string, provider_type: string): Promise<void> {
    console.log(`🗑️ UNIVERSAL: Deleting API key for ${provider_type} in project ${projectId}`);
    
    const response = await fetch(`${API_BASE}/project-api-keys/project/${projectId}/keys/${provider_type}/`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Delete API key failed: ${response.status}`);
    }

    console.log('✅ UNIVERSAL: API key deleted successfully');
  }

  /**
   * Test/validate project API key
   */
  async testProjectApiKey(projectId: string, provider_type: string): Promise<any> {
    console.log(`🔑 UNIVERSAL: Testing API key for ${provider_type} in project ${projectId}`);
    
    const response = await fetch(`${API_BASE}/project-api-keys/project/${projectId}/keys/${provider_type}/validate/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `Test API key failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ UNIVERSAL: API key test completed');
    return result.validation || result;
  }

  // ============================================================================
  // TEMPLATE MANAGEMENT (Enhanced duplication support)
  // ============================================================================

  /**
   * Get enhanced project templates (Template management)
   */
  async getEnhancedProjectTemplates(): Promise<any[]> {
    console.log('🔍 TEMPLATE: Getting enhanced templates via /api/enhanced-project-templates/');
    
    const response = await fetch(`${API_BASE}/enhanced-project-templates/`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Get enhanced templates failed: ${response.status}`);
    }

    const result = await response.json();
    console.log(`✅ TEMPLATE: Retrieved ${result.templates?.length || 0} enhanced templates`);
    return result.templates || result;
  }

  /**
   * Duplicate template (Template management)
   */
  async duplicateTemplate(duplicationData: any): Promise<any> {
    console.log('🔄 TEMPLATE: Duplicating template via /api/enhanced-project-templates/duplicate/');
    
    const response = await fetch(`${API_BASE}/enhanced-project-templates/duplicate/`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(duplicationData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `Template duplication failed: ${response.status}`);
    }

    const result = await response.json();
    console.log('✅ TEMPLATE: Template duplicated successfully');
    return result;
  }
}

// Export singleton instance
export const cleanUniversalApi = new CleanUniversalApiService();
