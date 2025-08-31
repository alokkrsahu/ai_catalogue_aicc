// src/lib/stores/auth.ts
import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';
import type { User } from '$lib/types';

// Initial state from localStorage if available
const storedAuth = browser ? localStorage.getItem('auth') : null;
const initialAuth = storedAuth ? JSON.parse(storedAuth) : {
  user: null,
  token: null,
  refreshToken: null,
  isAuthenticated: false,
};

// Create the store
const authStore = writable(initialAuth);

// Update localStorage when store changes
if (browser) {
  authStore.subscribe(value => {
    localStorage.setItem('auth', JSON.stringify(value));
  });
}

// Derived stores for convenience
export const user = derived(authStore, $auth => $auth.user);
export const isAuthenticated = derived(authStore, $auth => $auth.isAuthenticated);
export const isAdmin = derived(authStore, $auth => $auth.user?.role === 'ADMIN');

// Auth actions
export const login = (userData: User, token: string, refreshToken: string) => {
  authStore.set({
    user: userData,
    token,
    refreshToken,
    isAuthenticated: true,
  });
};

export const logout = () => {
  authStore.set({
    user: null,
    token: null,
    refreshToken: null,
    isAuthenticated: false,
  });
};

export const updateUser = (userData: Partial<User>) => {
  authStore.update(state => ({
    ...state,
    user: state.user ? { ...state.user, ...userData } : null,
  }));
};

export default authStore;
