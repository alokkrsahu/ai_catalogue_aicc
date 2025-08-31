<!--
Advanced Template Dashboard
Phase 5: Advanced Template Features

Comprehensive dashboard for advanced template management including:
- Template versioning management
- Analytics and performance monitoring
- Testing and validation
- Health monitoring
- System diagnostics
-->

<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import advancedTemplateManagementService from '$lib/services/advanced/templateManagement';
	import type {
		AnalyticsReport,
		SystemHealthReport,
		TemplateHealthReport,
		PopularityRanking,
		TestSuite,
		VersionHistory
	} from '$lib/services/advanced/templateManagement';

	// Component props
	export let templateId: string;
	export let showAnalytics: boolean = true;
	export let showHealth: boolean = true;
	export let showTesting: boolean = true;
	export let showVersioning: boolean = true;

	// Data states
	let analyticsReport: AnalyticsReport | null = null;
	let systemHealth: SystemHealthReport | null = null;
	let templateHealth: TemplateHealthReport | null = null;
	let popularityRankings: PopularityRanking[] = [];
	let versionHistory: VersionHistory[] = [];
	let currentVersion: string = '';
	let testResults: TestSuite | null = null;

	// UI states
	let loading = {
		analytics: false,
		health: false,
		testing: false,
		versioning: false
	};
	let errors = {
		analytics: '',
		health: '',
		testing: '',
		versioning: ''
	};
	let activeTab = 'overview';

	// Analytics period
	let analyticsPeriod = 30;

	onMount(() => {
		if (browser) {
			loadDashboardData();
		}
	});

	async function loadDashboardData() {
		await Promise.all([
			loadAnalyticsData(),
			loadHealthData(),
			loadVersioningData(),
			loadPopularityData()
		]);
	}

	async function loadAnalyticsData() {
		if (!showAnalytics) return;
		
		loading.analytics = true;
		errors.analytics = '';
		
		try {
			analyticsReport = await advancedTemplateManagementService.getAnalyticsReport(
				templateId, 
				analyticsPeriod
			);
		} catch (error) {
			console.error('Failed to load analytics data:', error);
			errors.analytics = error instanceof Error ? error.message : 'Unknown error';
		} finally {
			loading.analytics = false;
		}
	}

	async function loadHealthData() {
		if (!showHealth) return;
		
		loading.health = true;
		errors.health = '';
		
		try {
			const [systemHealthData, templateHealthData] = await Promise.all([
				advancedTemplateManagementService.getSystemHealth(),
				advancedTemplateManagementService.getTemplateHealth(templateId)
			]);
			
			systemHealth = systemHealthData;
			templateHealth = templateHealthData;
		} catch (error) {
			console.error('Failed to load health data:', error);
			errors.health = error instanceof Error ? error.message : 'Unknown error';
		} finally {
			loading.health = false;
		}
	}

	async function loadVersioningData() {
		if (!showVersioning) return;
		
		loading.versioning = true;
		errors.versioning = '';
		
		try {
			const versionData = await advancedTemplateManagementService.getVersionHistory(templateId);
			versionHistory = versionData.history;
			currentVersion = versionData.current_version;
		} catch (error) {
			console.error('Failed to load versioning data:', error);
			errors.versioning = error instanceof Error ? error.message : 'Unknown error';
		} finally {
			loading.versioning = false;
		}
	}

	async function loadPopularityData() {
		try {
			const popularityData = await advancedTemplateManagementService.getPopularityRankings();
			popularityRankings = popularityData.rankings;
		} catch (error) {
			console.error('Failed to load popularity data:', error);
		}
	}

	async function runTests() {
		if (!showTesting) return;
		
		loading.testing = true;
		errors.testing = '';
		
		try {
			testResults = await advancedTemplateManagementService.runTests(templateId, {
				include_benchmarks: true,
				include_regression: true,
				include_compatibility: true
			});
		} catch (error) {
			console.error('Failed to run tests:', error);
			errors.testing = error instanceof Error ? error.message : 'Unknown error';
		} finally {
			loading.testing = false;
		}
	}

	async function updateAnalyticsPeriod() {
		await loadAnalyticsData();
	}

	function getHealthStatusClass(status: string): string {
		switch (status) {
			case 'healthy':
				return 'bg-green-100 text-green-800 border-green-200';
			case 'warning':
				return 'bg-yellow-100 text-yellow-800 border-yellow-200';
			case 'critical':
				return 'bg-red-100 text-red-800 border-red-200';
			default:
				return 'bg-gray-100 text-gray-800 border-gray-200';
		}
	}

	function getTestStatusClass(status: string): string {
		switch (status) {
			case 'passed':
				return 'text-green-600';
			case 'failed':
				return 'text-red-600';
			case 'error':
				return 'text-orange-600';
			case 'skipped':
				return 'text-gray-600';
			default:
				return 'text-gray-600';
		}
	}

	function formatDuration(seconds: number): string {
		return advancedTemplateManagementService.formatDuration(seconds);
	}

	function formatPercentage(value: number): string {
		return advancedTemplateManagementService.formatPercentage(value);
	}
</script>

<div class="advanced-template-dashboard">
	<!-- Dashboard Header -->
	<div class="mb-6">
		<h1 class="text-2xl font-bold text-gray-900 mb-2">
			Advanced Template Management
		</h1>
		<p class="text-gray-600">
			Comprehensive analytics, monitoring, and management for template: 
			<span class="font-semibold text-oxford-blue">{templateId}</span>
		</p>
	</div>

	<!-- Navigation Tabs -->
	<div class="border-b border-gray-200 mb-6">
		<nav class="-mb-px flex space-x-8">
			<button
				class="tab-button {activeTab === 'overview' ? 'active' : ''}"
				on:click={() => activeTab = 'overview'}
			>
				Overview
			</button>
			{#if showAnalytics}
				<button
					class="tab-button {activeTab === 'analytics' ? 'active' : ''}"
					on:click={() => activeTab = 'analytics'}
				>
					Analytics
				</button>
			{/if}
			{#if showHealth}
				<button
					class="tab-button {activeTab === 'health' ? 'active' : ''}"
					on:click={() => activeTab = 'health'}
				>
					Health
				</button>
			{/if}
			{#if showTesting}
				<button
					class="tab-button {activeTab === 'testing' ? 'active' : ''}"
					on:click={() => activeTab = 'testing'}
				>
					Testing
				</button>
			{/if}
			{#if showVersioning}
				<button
					class="tab-button {activeTab === 'versioning' ? 'active' : ''}"
					on:click={() => activeTab = 'versioning'}
				>
					Versioning
				</button>
			{/if}
		</nav>
	</div>

	<!-- Overview Tab -->
	{#if activeTab === 'overview'}
		<div class="overview-tab">
			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
				<!-- Template Health Summary -->
				{#if templateHealth}
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Template Health</h3>
						<div class="space-y-3">
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Status:</span>
								<span class="px-2 py-1 rounded text-sm {getHealthStatusClass(templateHealth.status)}">
									{templateHealth.status.toUpperCase()}
								</span>
							</div>
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Availability:</span>
								<span class="font-semibold">{templateHealth.availability.toFixed(1)}%</span>
							</div>
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Performance:</span>
								<span class="font-semibold">{templateHealth.performance_score.toFixed(1)}/100</span>
							</div>
						</div>
					</div>
				{/if}

				<!-- Analytics Summary -->
				{#if analyticsReport}
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Usage Analytics</h3>
						<div class="space-y-3">
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Total Projects:</span>
								<span class="font-semibold">{analyticsReport.usage_metrics.total_projects}</span>
							</div>
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Success Rate:</span>
								<span class="font-semibold">{formatPercentage(analyticsReport.usage_metrics.success_rate)}</span>
							</div>
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Satisfaction:</span>
								<span class="font-semibold">{analyticsReport.usage_metrics.user_satisfaction_score}/5</span>
							</div>
						</div>
					</div>
				{/if}

				<!-- Version Information -->
				{#if currentVersion}
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Version Info</h3>
						<div class="space-y-3">
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Current Version:</span>
								<span class="font-semibold text-oxford-blue">{currentVersion}</span>
							</div>
							<div class="flex items-center justify-between">
								<span class="text-gray-600">Total Versions:</span>
								<span class="font-semibold">{versionHistory.length}</span>
							</div>
						</div>
					</div>
				{/if}
			</div>

			<!-- System Health Status -->
			{#if systemHealth}
				<div class="mt-6 bg-white rounded-lg shadow p-6">
					<h3 class="text-lg font-semibold mb-4">System Health Status</h3>
					<div class="flex items-center justify-between mb-4">
						<span class="text-gray-600">Overall Status:</span>
						<span class="px-3 py-1 rounded text-sm {getHealthStatusClass(systemHealth.overall_status)}">
							{systemHealth.overall_status.toUpperCase()}
						</span>
					</div>
					<div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
						<div>
							<div class="text-2xl font-bold text-green-600">{systemHealth.system_metrics.healthy_components}</div>
							<div class="text-sm text-gray-600">Healthy</div>
						</div>
						<div>
							<div class="text-2xl font-bold text-yellow-600">{systemHealth.system_metrics.warning_components}</div>
							<div class="text-sm text-gray-600">Warning</div>
						</div>
						<div>
							<div class="text-2xl font-bold text-red-600">{systemHealth.system_metrics.critical_components}</div>
							<div class="text-sm text-gray-600">Critical</div>
						</div>
						<div>
							<div class="text-2xl font-bold text-oxford-blue">{systemHealth.system_metrics.total_components}</div>
							<div class="text-sm text-gray-600">Total</div>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Analytics Tab -->
	{#if activeTab === 'analytics' && showAnalytics}
		<div class="analytics-tab">
			<!-- Analytics Controls -->
			<div class="mb-6 flex items-center justify-between">
				<h2 class="text-xl font-semibold">Analytics Report</h2>
				<div class="flex items-center space-x-4">
					<label class="text-sm text-gray-600">
						Period:
						<select bind:value={analyticsPeriod} on:change={updateAnalyticsPeriod} class="ml-2 border rounded px-3 py-1">
							<option value={7}>Last 7 days</option>
							<option value={30}>Last 30 days</option>
							<option value={90}>Last 90 days</option>
						</select>
					</label>
					<button
						on:click={loadAnalyticsData}
						disabled={loading.analytics}
						class="btn-primary"
					>
						{loading.analytics ? 'Loading...' : 'Refresh'}
					</button>
				</div>
			</div>

			{#if loading.analytics}
				<div class="text-center py-8">
					<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue"></div>
					<p class="mt-2 text-gray-600">Loading analytics data...</p>
				</div>
			{:else if errors.analytics}
				<div class="bg-red-50 border border-red-200 rounded-lg p-4">
					<p class="text-red-800">Error: {errors.analytics}</p>
				</div>
			{:else if analyticsReport}
				<div class="space-y-6">
					<!-- Usage Metrics -->
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Usage Metrics</h3>
						<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
							<div class="text-center">
								<div class="text-3xl font-bold text-oxford-blue">{analyticsReport.usage_metrics.total_projects}</div>
								<div class="text-sm text-gray-600">Total Projects</div>
							</div>
							<div class="text-center">
								<div class="text-3xl font-bold text-green-600">{analyticsReport.usage_metrics.active_projects}</div>
								<div class="text-sm text-gray-600">Active Projects</div>
							</div>
							<div class="text-center">
								<div class="text-3xl font-bold text-blue-600">{analyticsReport.usage_metrics.completed_projects}</div>
								<div class="text-sm text-gray-600">Completed</div>
							</div>
							<div class="text-center">
								<div class="text-3xl font-bold text-purple-600">{analyticsReport.usage_metrics.total_documents_processed}</div>
								<div class="text-sm text-gray-600">Documents</div>
							</div>
						</div>
					</div>

					<!-- Performance Metrics -->
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Performance Metrics</h3>
						<div class="grid grid-cols-2 md:grid-cols-3 gap-4">
							<div class="text-center">
								<div class="text-2xl font-bold text-indigo-600">
									{analyticsReport.performance_metrics.average_processing_time.toFixed(2)}s
								</div>
								<div class="text-sm text-gray-600">Avg Processing Time</div>
							</div>
							<div class="text-center">
								<div class="text-2xl font-bold text-red-600">
									{formatPercentage(analyticsReport.performance_metrics.error_rate)}
								</div>
								<div class="text-sm text-gray-600">Error Rate</div>
							</div>
							<div class="text-center">
								<div class="text-2xl font-bold text-orange-600">
									{analyticsReport.performance_metrics.total_api_calls}
								</div>
								<div class="text-sm text-gray-600">API Calls</div>
							</div>
						</div>
					</div>

					<!-- Insights -->
					{#if analyticsReport.insights && analyticsReport.insights.length > 0}
						<div class="bg-white rounded-lg shadow p-6">
							<h3 class="text-lg font-semibold mb-4">Insights</h3>
							<ul class="space-y-2">
								{#each analyticsReport.insights as insight}
									<li class="flex items-start">
										<span class="text-blue-500 mr-2">💡</span>
										<span class="text-gray-700">{insight}</span>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Health Tab -->
	{#if activeTab === 'health' && showHealth}
		<div class="health-tab">
			<div class="mb-6 flex items-center justify-between">
				<h2 class="text-xl font-semibold">Health Monitoring</h2>
				<button
					on:click={loadHealthData}
					disabled={loading.health}
					class="btn-primary"
				>
					{loading.health ? 'Loading...' : 'Refresh'}
				</button>
			</div>

			{#if loading.health}
				<div class="text-center py-8">
					<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue"></div>
					<p class="mt-2 text-gray-600">Loading health data...</p>
				</div>
			{:else if errors.health}
				<div class="bg-red-50 border border-red-200 rounded-lg p-4">
					<p class="text-red-800">Error: {errors.health}</p>
				</div>
			{:else}
				<div class="space-y-6">
					<!-- Template Health -->
					{#if templateHealth}
						<div class="bg-white rounded-lg shadow p-6">
							<h3 class="text-lg font-semibold mb-4">Template Health: {templateId}</h3>
							<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
								<div class="text-center">
									<div class="text-3xl font-bold {getHealthStatusClass(templateHealth.status).replace('bg-', 'text-').replace('-100', '-600')}">
										{templateHealth.availability.toFixed(1)}%
									</div>
									<div class="text-sm text-gray-600">Availability</div>
								</div>
								<div class="text-center">
									<div class="text-3xl font-bold text-blue-600">{templateHealth.performance_score.toFixed(1)}</div>
									<div class="text-sm text-gray-600">Performance Score</div>
								</div>
								<div class="text-center">
									<div class="text-3xl font-bold text-red-600">{formatPercentage(templateHealth.error_rate)}</div>
									<div class="text-sm text-gray-600">Error Rate</div>
								</div>
							</div>

							{#if templateHealth.issues.length > 0}
								<div class="mt-4">
									<h4 class="font-semibold text-gray-900 mb-2">Issues:</h4>
									<ul class="space-y-1">
										{#each templateHealth.issues as issue}
											<li class="flex items-start">
												<span class="text-red-500 mr-2">⚠️</span>
												<span class="text-gray-700">{issue}</span>
											</li>
										{/each}
									</ul>
								</div>
							{/if}

							{#if templateHealth.recommendations.length > 0}
								<div class="mt-4">
									<h4 class="font-semibold text-gray-900 mb-2">Recommendations:</h4>
									<ul class="space-y-1">
										{#each templateHealth.recommendations as recommendation}
											<li class="flex items-start">
												<span class="text-blue-500 mr-2">💡</span>
												<span class="text-gray-700">{recommendation}</span>
											</li>
										{/each}
									</ul>
								</div>
							{/if}
						</div>
					{/if}

					<!-- System Health Components -->
					{#if systemHealth && systemHealth.components.length > 0}
						<div class="bg-white rounded-lg shadow p-6">
							<h3 class="text-lg font-semibold mb-4">System Components</h3>
							<div class="space-y-3">
								{#each systemHealth.components as component}
									<div class="flex items-center justify-between p-3 border rounded">
										<div>
											<span class="font-medium">{component.component}</span>
											<p class="text-sm text-gray-600">{component.message}</p>
										</div>
										<span class="px-2 py-1 rounded text-sm {getHealthStatusClass(component.status)}">
											{component.status.toUpperCase()}
										</span>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Testing Tab -->
	{#if activeTab === 'testing' && showTesting}
		<div class="testing-tab">
			<div class="mb-6 flex items-center justify-between">
				<h2 class="text-xl font-semibold">Template Testing</h2>
				<button
					on:click={runTests}
					disabled={loading.testing}
					class="btn-primary"
				>
					{loading.testing ? 'Running Tests...' : 'Run Tests'}
				</button>
			</div>

			{#if loading.testing}
				<div class="text-center py-8">
					<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue"></div>
					<p class="mt-2 text-gray-600">Running comprehensive test suite...</p>
				</div>
			{:else if errors.testing}
				<div class="bg-red-50 border border-red-200 rounded-lg p-4">
					<p class="text-red-800">Error: {errors.testing}</p>
				</div>
			{:else if testResults}
				<div class="space-y-6">
					<!-- Test Summary -->
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Test Results Summary</h3>
						<div class="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
							<div>
								<div class="text-2xl font-bold text-green-600">{testResults.test_suite.statistics.passed}</div>
								<div class="text-sm text-gray-600">Passed</div>
							</div>
							<div>
								<div class="text-2xl font-bold text-red-600">{testResults.test_suite.statistics.failed}</div>
								<div class="text-sm text-gray-600">Failed</div>
							</div>
							<div>
								<div class="text-2xl font-bold text-orange-600">{testResults.test_suite.statistics.errors}</div>
								<div class="text-sm text-gray-600">Errors</div>
							</div>
							<div>
								<div class="text-2xl font-bold text-gray-600">{testResults.test_suite.statistics.skipped}</div>
								<div class="text-sm text-gray-600">Skipped</div>
							</div>
							<div>
								<div class="text-2xl font-bold text-oxford-blue">{testResults.test_suite.statistics.total}</div>
								<div class="text-sm text-gray-600">Total</div>
							</div>
						</div>
						<div class="mt-4 text-center">
							<span class="text-gray-600">Duration: </span>
							<span class="font-semibold">{formatDuration(testResults.test_suite.duration)}</span>
						</div>
					</div>

					<!-- Test Results -->
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Detailed Results</h3>
						<div class="space-y-3">
							{#each testResults.test_suite.results as result}
								<div class="flex items-center justify-between p-3 border rounded">
									<div>
										<span class="font-medium">{result.test_name}</span>
										<p class="text-sm text-gray-600">{result.message}</p>
									</div>
									<div class="text-right">
										<span class="px-2 py-1 rounded text-sm {getTestStatusClass(result.status)}">
											{result.status.toUpperCase()}
										</span>
										<p class="text-sm text-gray-600 mt-1">
											{formatDuration(result.execution_time)}
										</p>
									</div>
								</div>
							{/each}
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Versioning Tab -->
	{#if activeTab === 'versioning' && showVersioning}
		<div class="versioning-tab">
			<div class="mb-6 flex items-center justify-between">
				<h2 class="text-xl font-semibold">Version Management</h2>
				<button
					on:click={loadVersioningData}
					disabled={loading.versioning}
					class="btn-primary"
				>
					{loading.versioning ? 'Loading...' : 'Refresh'}
				</button>
			</div>

			{#if loading.versioning}
				<div class="text-center py-8">
					<div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue"></div>
					<p class="mt-2 text-gray-600">Loading version data...</p>
				</div>
			{:else if errors.versioning}
				<div class="bg-red-50 border border-red-200 rounded-lg p-4">
					<p class="text-red-800">Error: {errors.versioning}</p>
				</div>
			{:else}
				<div class="space-y-6">
					<!-- Current Version -->
					<div class="bg-white rounded-lg shadow p-6">
						<h3 class="text-lg font-semibold mb-4">Current Version</h3>
						<div class="text-center">
							<div class="text-4xl font-bold text-oxford-blue mb-2">{currentVersion}</div>
							<p class="text-gray-600">Active version for {templateId}</p>
						</div>
					</div>

					<!-- Version History -->
					{#if versionHistory.length > 0}
						<div class="bg-white rounded-lg shadow p-6">
							<h3 class="text-lg font-semibold mb-4">Version History</h3>
							<div class="space-y-3">
								{#each versionHistory as version}
									<div class="flex items-center justify-between p-3 border rounded">
										<div>
											<span class="font-medium">{version.from_version} → {version.to_version}</span>
											<p class="text-sm text-gray-600">{version.changelog}</p>
										</div>
										<div class="text-right">
											<p class="text-sm text-gray-600">
												{new Date(version.timestamp).toLocaleDateString()}
											</p>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.advanced-template-dashboard {
		@apply max-w-7xl mx-auto p-6;
	}

	.tab-button {
		@apply py-2 px-4 border-b-2 border-transparent text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300;
	}

	.tab-button.active {
		@apply text-oxford-blue border-oxford-blue;
	}

	.btn-primary {
		@apply bg-oxford-blue text-white px-4 py-2 rounded hover:bg-oxford-blue/90 disabled:opacity-50 disabled:cursor-not-allowed;
	}

	:global(.text-oxford-blue) {
		color: #002147;
	}

	:global(.bg-oxford-blue) {
		background-color: #002147;
	}

	:global(.border-oxford-blue) {
		border-color: #002147;
	}

	:global(.hover\\:bg-oxford-blue\\/90:hover) {
		background-color: rgba(0, 33, 71, 0.9);
	}
</style>
