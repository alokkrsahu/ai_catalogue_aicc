/**
 * History Template API Service
 * 
 * Handles template-specific API operations for History template management
 * This service is ONLY for template management operations, NOT for project operations
 */

import { createTemplateLogger } from '../../logging/logger';
import type { 
  HistoryTemplate, 
  TemplateDiscoveryResult, 
  TemplateDuplicationRequest, 
  TemplateDuplicationResult,
  UniversalProject,
  TemplateApiService
} from '../types';

const logger = createTemplateLogger('history', 'ApiService');

export class HistoryTemplateApiService implements TemplateApiService {
  private readonly baseUrl = '/api/templates/history';
  private readonly templateId = 'history';

  constructor() {
    logger.info('Initializing History Template API Service');
  }

  async discover(): Promise<TemplateDiscoveryResult> {
    logger.apiCall('GET', `${this.baseUrl}/discover/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/discover/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Discovery failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      logger.apiResponse(`${this.baseUrl}/discover/`, response.status, result);
      
      return result;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/discover/`, error);
      throw error;
    }
  }

  async getConfiguration(): Promise<HistoryTemplate> {
    logger.apiCall('GET', `${this.baseUrl}/configuration/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/configuration/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Configuration fetch failed: ${response.status} ${response.statusText}`);
      }

      const template = await response.json();
      logger.apiResponse(`${this.baseUrl}/configuration/`, response.status, template);
      
      return template;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/configuration/`, error);
      throw error;
    }
  }

  async duplicate(request: TemplateDuplicationRequest): Promise<TemplateDuplicationResult> {
    logger.templateAction('duplicate', this.templateId, request);
    logger.apiCall('POST', `${this.baseUrl}/duplicate/`, request);
    
    try {
      const response = await fetch(`${this.baseUrl}/duplicate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`Duplication failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      logger.apiResponse(`${this.baseUrl}/duplicate/`, response.status, result);
      logger.templateAction('duplicate_completed', this.templateId, result);
      
      return result;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/duplicate/`, error);
      throw error;
    }
  }

  async createProject(projectData: Partial<UniversalProject>): Promise<UniversalProject> {
    logger.templateAction('create_project', this.templateId, projectData);
    logger.apiCall('POST', `${this.baseUrl}/projects/`, projectData);
    
    try {
      const response = await fetch(`${this.baseUrl}/projects/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...projectData,
          template_id: this.templateId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Project creation failed: ${response.status} ${response.statusText}`);
      }

      const project = await response.json();
      logger.apiResponse(`${this.baseUrl}/projects/`, response.status, project);
      logger.projectAction('created_from_template', project.id, { template_id: this.templateId });
      
      return project;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/projects/`, error);
      throw error;
    }
  }

  async getStatus(): Promise<any> {
    logger.apiCall('GET', `${this.baseUrl}/status/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/status/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Status fetch failed: ${response.status} ${response.statusText}`);
      }

      const status = await response.json();
      logger.apiResponse(`${this.baseUrl}/status/`, response.status, status);
      
      return status;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/status/`, error);
      throw error;
    }
  }

  async testConnection(): Promise<boolean> {
    logger.apiCall('GET', `${this.baseUrl}/health/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/health/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const isHealthy = response.ok;
      logger.apiResponse(`${this.baseUrl}/health/`, response.status, { healthy: isHealthy });
      
      return isHealthy;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/health/`, error);
      return false;
    }
  }
}

export const historyTemplateApi = new HistoryTemplateApiService();
