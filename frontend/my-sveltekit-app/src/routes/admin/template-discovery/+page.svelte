<!-- Admin Template Discovery Page - Phase 3 Showcase -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { createUniversalLogger } from '$lib/logging/logger';
  import TemplateDiscoveryDashboard from '$lib/components/TemplateDiscoveryDashboard.svelte';

  const logger = createUniversalLogger('AdminTemplateDiscovery');

  onMount(() => {
    logger.componentMount('AdminTemplateDiscoveryPage');
    logger.info('Showcasing Phase 3: Enhanced Template Discovery & Registration');
  });
</script>

<svelte:head>
  <title>Admin - Template Discovery - AI Catalogue</title>
</svelte:head>

<div class="admin-discovery-page">
  <!-- Page Header -->
  <div class="page-header">
    <div class="header-content">
      <div class="breadcrumb">
        <a href="/admin">Admin</a>
        <i class="fas fa-chevron-right"></i>
        <span>Template Discovery</span>
      </div>
      <h1>Enhanced Template Discovery & Registration</h1>
      <p class="page-description">
        Phase 3 implementation featuring comprehensive template discovery, 
        architectural analysis, and dynamic route registration with full-stack capability detection.
      </p>
    </div>
    
    <div class="phase-badge">
      <i class="fas fa-rocket"></i>
      Phase 3
    </div>
  </div>

  <!-- Enhanced Dashboard Component -->
  <div class="dashboard-container">
    <TemplateDiscoveryDashboard />
  </div>
</div>

<style>
  .admin-discovery-page {
    min-height: 100vh;
    background: #f8fafc;
    padding: 24px;
  }

  .page-header {
    background: linear-gradient(135deg, #002147 0%, #1e3a5f 100%);
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 32px;
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-size: 0.875rem;
    opacity: 0.8;
  }

  .breadcrumb a {
    color: rgba(255, 255, 255, 0.8);
    text-decoration: none;
    transition: color 0.2s ease;
  }

  .breadcrumb a:hover {
    color: white;
  }

  .header-content h1 {
    margin: 0 0 12px 0;
    font-size: 2.25rem;
    font-weight: 700;
    color: white;
  }

  .page-description {
    margin: 0;
    font-size: 1.125rem;
    line-height: 1.6;
    opacity: 0.9;
    max-width: 600px;
  }

  .phase-badge {
    background: rgba(255, 255, 255, 0.1);
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    padding: 16px 24px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 1.125rem;
    color: white;
  }

  .dashboard-container {
    margin-bottom: 32px;
  }

  /* Responsive Design */
  @media (max-width: 768px) {
    .admin-discovery-page {
      padding: 16px;
    }

    .page-header {
      flex-direction: column;
      gap: 16px;
      text-align: center;
    }

    .header-content h1 {
      font-size: 1.75rem;
    }

    .breadcrumb {
      justify-content: center;
    }
  }
</style>
