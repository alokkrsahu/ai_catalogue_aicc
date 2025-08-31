/**
 * AICC-IntelliDoc Template API Service
 * 
 * Handles template-specific API operations for AICC-IntelliDoc template management
 * This service is ONLY for template management operations, NOT for project operations
 */

import { createTemplateLogger } from '../../logging/logger';
import type { 
  AICCIntelliDocTemplate, 
  TemplateDiscoveryResult, 
  TemplateDuplicationRequest, 
  TemplateDuplicationResult,
  UniversalProject,
  TemplateApiService
} from '../types';

const logger = createTemplateLogger('aicc-intellidoc', 'ApiService');

export class AICCIntelliDocTemplateApiService implements TemplateApiService {
  private readonly baseUrl = '/api/templates/aicc-intellidoc';
  private readonly templateId = 'aicc-intellidoc';

  constructor() {
    logger.info('Initializing AICC-IntelliDoc Template API Service');
  }

  /**
   * Discover AICC-IntelliDoc template configuration
   */
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

  /**
   * Get AICC-IntelliDoc template configuration
   */
  async getConfiguration(): Promise<AICCIntelliDocTemplate> {
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

  /**
   * Duplicate AICC-IntelliDoc template with complete independence
   */
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

  /**
   * REMOVED: Project creation moved to universal API
   * Templates are for DISCOVERY and MANAGEMENT only
   * Use cleanUniversalApi.createProject() for project creation
   */

  /**
   * Get template status and health metrics
   */
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

  /**
   * Get template metrics and usage statistics
   */
  async getMetrics(): Promise<any> {
    logger.apiCall('GET', `${this.baseUrl}/metrics/`);
    
    try {
      const response = await fetch(`${this.baseUrl}/metrics/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Metrics fetch failed: ${response.status} ${response.statusText}`);
      }

      const metrics = await response.json();
      logger.apiResponse(`${this.baseUrl}/metrics/`, response.status, metrics);
      
      return metrics;
    } catch (error) {
      logger.apiError(`${this.baseUrl}/metrics/`, error);
      throw error;
    }
  }

  /**
   * Test template API connectivity
   */
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

// Export singleton instance for use across the application
export const aiccIntelliDocTemplateApi = new AICCIntelliDocTemplateApiService();
