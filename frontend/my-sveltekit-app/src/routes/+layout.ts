// src/routes/+layout.ts
import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { get } from 'svelte/store';
// Import everything needed from the auth store and the API service
import authStore, { isAuthenticated, isAdmin, user as userStore, logout, login } from '$lib/stores/auth';
import { getCurrentUser } from '$lib/services/api';
import type { LayoutLoad } from './$types';

// Disable SSR for this layout load function as it heavily relies on browser APIs (localStorage)
// and client-side store state for initial auth check.
export const ssr = false;

export const load: LayoutLoad = async ({ url }) => {
    // This load function should run primarily in the browser
    if (!browser) {
        // Return minimal data for any potential SSR pass, auth check happens client-side
        return { isAuthenticated: false, user: null, url: url?.pathname || '/' };
    }

    console.log('+layout.ts: Load function started (client-side)');

    // Get the initial state from the store (which reflects localStorage)
    const initialAuth = get(authStore);
    let currentUserData = initialAuth.user; // Assume user data from store initially
    let currentIsAuthenticated = initialAuth.isAuthenticated;

    console.log('+layout.ts: Initial state from store - isAuthenticated:', currentIsAuthenticated, 'User data present:', !!currentUserData);

    // --- Attempt to fetch/validate user data if authenticated state is found ---
    if (currentIsAuthenticated) {
        // Even if user data is in localStorage, fetching validates the token
        // and ensures data is fresh. If user data is MISSING, this is essential.
        console.log('+layout.ts: Attempting to fetch/validate user data with getCurrentUser()');
        try {
            const freshUserData = await getCurrentUser(); // Fetches /api/users/me/
            console.log('+layout.ts: Successfully fetched fresh user data:', freshUserData);

            // If fetch is successful, update the store using the login action
            // This ensures tokens and user data are consistent in the store and localStorage
            // It uses the existing tokens from the initialAuth state.
            if (initialAuth.token && initialAuth.refreshToken) {
                 login(freshUserData, initialAuth.token, initialAuth.refreshToken);
                 currentUserData = freshUserData; // Update local variable for checks below
                 currentIsAuthenticated = true; // Ensure this is true
            } else {
                // This case shouldn't happen if initialAuth.isAuthenticated was true, but handle defensively
                 console.error('+layout.ts: Tokens missing in store despite authenticated state. Logging out.');
                 logout();
                 currentUserData = null;
                 currentIsAuthenticated = false;
            }

        } catch (error: any) {
            console.error('+layout.ts: Failed to fetch/validate user:', error?.response?.data || error.message);
            // If fetching fails (invalid/expired token, network error), logout the user
            logout();
            currentUserData = null;
            currentIsAuthenticated = false;
        }
    }

    // --- Redirect Logic (use the state determined AFTER the fetch attempt) ---
    const finalIsAuthenticated = currentIsAuthenticated;
    const finalIsAdmin = currentUserData?.role === 'ADMIN'; // Check role from potentially updated user data
    const path = url.pathname || '/';

    const publicRoutes = ['/login', '/register', '/reset-password'];
    const isPublicRoute = publicRoutes.some(r => path === r || path.startsWith('/reset-password/'));
    const isAdminRoute = path.startsWith('/admin');

    console.log(`+layout.ts: Redirect check - Path=${path}, Auth=${finalIsAuthenticated}, Admin=${finalIsAdmin}, PublicRoute=${isPublicRoute}, AdminRoute=${isAdminRoute}`);

    if (!finalIsAuthenticated && !isPublicRoute) {
        console.log('+layout.ts: Redirecting unauthenticated user to login.');
        // Use { replaceState: true } to avoid polluting browser history with redirects
        goto('/login', { replaceState: true });
    } else if (finalIsAuthenticated && isPublicRoute) {
        console.log('+layout.ts: Redirecting authenticated user from public route to dashboard.');
        goto('/', { replaceState: true });
    } else if (finalIsAuthenticated && isAdminRoute && !finalIsAdmin) {
        console.log('+layout.ts: Redirecting non-admin user from admin route.');
        goto('/', { replaceState: true });
    }

    console.log('+layout.ts: Load function finished.');
    // Return the final state, making it available to child pages via the `data` prop
    return {
        isAuthenticated: finalIsAuthenticated,
        user: currentUserData,
        url: path
    };
};
