/**
 * AICC-IntelliDoc Template API Service (COMPLIANT)
 * 
 * TEMPLATE INDEPENDENCE COMPLIANT: This service handles ONLY template management operations
 * - Template discovery
 * - Template configuration  
 * - Template duplication
 * 
 * ❌ DOES NOT handle project operations (use cleanUniversalApi for ALL project operations)
 */

import { createTemplateLogger } from '../../logging/logger';
import type { 
  TemplateDiscoveryResult, 
  TemplateDuplicationRequest, 
  TemplateDuplicationResult,
  TemplateApiService
} from '../types';

const logger = createTemplateLogger('aicc-intellidoc-v4', 'ApiService');

export class AICCIntelliDocTemplateApiService implements TemplateApiService {
  private readonly baseUrl = '/api/templates/aicc-intellidoc-v4';
  private readonly templateId = 'aicc-intellidoc-v4';

  constructor() {
    logger.info('Initializing AICC-IntelliDoc Template API Service (Template Independence Compliant)');
  }

  /**
   * ✅ COMPLIANT: Discover AICC-IntelliDoc template configuration
   * Used for template selection page only
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
   * ✅ COMPLIANT: Get AICC-IntelliDoc template configuration
   * Used for template selection and project creation data cloning
   */
  async getConfiguration(): Promise<any> {
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
   * ✅ COMPLIANT: Duplicate AICC-IntelliDoc template with complete independence
   * Creates new template with zero dependencies on original
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
   * ✅ COMPLIANT: Get template status and health metrics
   * Template management only
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
   * ✅ COMPLIANT: Test template API connectivity
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

// Export singleton instance for template management operations only
export const aiccIntelliDocTemplateApi = new AICCIntelliDocTemplateApiService();
