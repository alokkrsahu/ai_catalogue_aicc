<!-- src/lib/components/AuthErrorBoundary.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { logout } from '$lib/stores/auth';
  import { toasts } from '$lib/stores/toast';

  interface Props {
    fallbackMessage?: string;
  }
  
  let { fallbackMessage = 'Authentication error occurred. Please log in again.' }: Props = $props();
  
  let hasError = $state(false);
  let errorMessage = $state('');
  
  // User Activity Tracking for 2-hour inactivity timeout
  let lastActivityTime = $state(Date.now());
  let inactivityTimer: NodeJS.Timeout | null = null;
  let activityWarningTimer: NodeJS.Timeout | null = null;
  let showInactivityWarning = $state(false);
  
  const INACTIVITY_TIMEOUT = 2 * 60 * 60 * 1000; // 2 hours in milliseconds
  const WARNING_TIME = 5 * 60 * 1000; // Show warning 5 minutes before logout
  
  // Track user activity
  function updateLastActivity() {
    lastActivityTime = Date.now();
    console.log('🕐 ACTIVITY: User activity detected, resetting inactivity timer');
    
    // Reset timers
    if (inactivityTimer) clearTimeout(inactivityTimer);
    if (activityWarningTimer) clearTimeout(activityWarningTimer);
    showInactivityWarning = false;
    
    // Set warning timer (warn 5 minutes before logout)
    activityWarningTimer = setTimeout(() => {
      showInactivityWarning = true;
      toasts.warning('You will be logged out in 5 minutes due to inactivity. Move your mouse or click to stay logged in.', {
        duration: 300000 // 5 minutes
      });
      console.log('⚠️ INACTIVITY: Warning shown - 5 minutes remaining');
    }, INACTIVITY_TIMEOUT - WARNING_TIME);
    
    // Set logout timer
    inactivityTimer = setTimeout(() => {
      console.log('🛑 INACTIVITY: 2-hour timeout reached, logging out user');
      handleInactivityLogout();
    }, INACTIVITY_TIMEOUT);
  }
  
  // Handle inactivity logout (different from auth errors)
  function handleInactivityLogout() {
    hasError = true;
    errorMessage = 'You have been logged out due to 2 hours of inactivity for security purposes.';
    showInactivityWarning = false;
    
    // Show user-friendly message
    toasts.info('Session expired due to inactivity. Please log in again.');
    
    // Perform logout
    logout();
    
    // Redirect to login
    setTimeout(() => {
      goto('/login', { replaceState: true });
    }, 2000);
  }

  // Handle authentication errors (much less aggressive)
  function handleAuthError(error: any) {
    console.warn('AuthErrorBoundary: Authentication error caught (not auto-logging out):', error);
    
    // Only handle CRITICAL authentication errors, not network/websocket issues
    if (error?.response?.status === 401 && error?.config?.url?.includes('/api/users/me')) {
      // Only logout if the user profile endpoint specifically returns 401
      console.log('🚨 CRITICAL AUTH: User profile endpoint returned 401, this is a real auth failure');
      
      hasError = true;
      errorMessage = 'Your session has expired. Please log in again.';
      
      toasts.error(errorMessage);
      logout();
      
      setTimeout(() => {
        goto('/login', { replaceState: true });
      }, 2000);
    } else if (error?.response?.status === 403 && error?.config?.url?.includes('/api/')) {
      // Only show permission error, don't logout
      toasts.error('You do not have permission to access this resource.');
      console.log('⚠️ PERMISSION: 403 error detected, showing warning but not logging out');
    } else {
      // For all other errors (network, websocket, etc.) just log them, don't logout
      console.log('ℹ️ NON-CRITICAL: Ignoring error that would previously cause logout:', error?.message || error);
    }
  }

  onMount(() => {
    console.log('✅ AUTH BOUNDARY: Initialized with 2-hour inactivity timeout');
    
    // Start activity tracking
    updateLastActivity();
    
    // Activity event listeners
    const activityEvents = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    
    const throttledActivityUpdate = throttle(updateLastActivity, 30000); // Update at most once every 30 seconds
    
    activityEvents.forEach(event => {
      document.addEventListener(event, throttledActivityUpdate, { passive: true });
    });
    
    // Much more selective error handling
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      // Only handle critical API authentication failures, not websocket or other network errors
      if (event.reason?.response?.status === 401 && 
          event.reason?.config?.url?.includes('/api/users/me')) {
        event.preventDefault();
        handleAuthError(event.reason);
      }
      // Ignore all other rejections (websocket failures, network errors, etc.)
    };

    // Only handle critical auth-related errors
    const handleGlobalError = (event: ErrorEvent) => {
      // Only handle actual authentication token errors, not websocket/network errors
      if (event.error?.response?.status === 401 && 
          event.error?.config?.url?.includes('/api/users/me')) {
        event.preventDefault();
        handleAuthError(event.error);
      }
      // Ignore websocket, network, and other non-critical errors
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleGlobalError);

    return () => {
      // Cleanup
      activityEvents.forEach(event => {
        document.removeEventListener(event, throttledActivityUpdate);
      });
      
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleGlobalError);
      
      if (inactivityTimer) clearTimeout(inactivityTimer);
      if (activityWarningTimer) clearTimeout(activityWarningTimer);
    };
  });
  
  // Throttle function to limit activity updates
  function throttle(func: Function, delay: number) {
    let timeoutId: NodeJS.Timeout | null = null;
    let lastExecTime = 0;
    
    return function (...args: any[]) {
      const currentTime = Date.now();
      
      if (currentTime - lastExecTime > delay) {
        func(...args);
        lastExecTime = currentTime;
      } else {
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
          func(...args);
          lastExecTime = Date.now();
        }, delay - (currentTime - lastExecTime));
      }
    };
  }

  // Reset error state
  function resetError() {
    hasError = false;
    errorMessage = '';
    showInactivityWarning = false;
  }

  // Manual error trigger (for components to call) - now less aggressive
  export function triggerAuthError(error: any) {
    handleAuthError(error);
  }
  
  // Manual activity update (for components to call)
  export function reportActivity() {
    updateLastActivity();
  }
</script>

{#if hasError}
  <!-- Error fallback UI -->
  <div class="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md">
      <div class="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
        <div class="text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
            <svg class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 18.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          
          <h3 class="mt-4 text-lg font-medium text-gray-900">Authentication Error</h3>
          
          <p class="mt-2 text-sm text-gray-600">
            {errorMessage}
          </p>
          
          <div class="mt-4 flex items-center justify-center">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span class="ml-2 text-sm text-gray-500">Redirecting to login...</span>
          </div>
          
          <div class="mt-6">
            <button
              onclick={() => goto('/login', { replaceState: true })}
              class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Go to Login
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
{:else}
  <!-- Normal content -->
  <slot />
{/if}

{#if showInactivityWarning}
  <!-- Inactivity warning overlay -->
  <div class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
    <div class="bg-white p-6 rounded-lg shadow-xl max-w-md">
      <div class="flex items-center mb-4">
        <div class="flex-shrink-0">
          <svg class="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 18.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <div class="ml-3">
          <h3 class="text-lg font-medium text-gray-900">Session Expiring Soon</h3>
        </div>
      </div>
      
      <p class="text-sm text-gray-600 mb-6">
        You will be logged out in 5 minutes due to inactivity. Click anywhere or move your mouse to stay logged in.
      </p>
      
      <div class="flex space-x-3">
        <button
          onclick={() => { showInactivityWarning = false; updateLastActivity(); }}
          class="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          Stay Logged In
        </button>
        <button
          onclick={() => handleInactivityLogout()}
          class="flex-1 bg-gray-300 text-gray-700 px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500"
        >
          Logout Now
        </button>
      </div>
    </div>
  </div>
{/if}