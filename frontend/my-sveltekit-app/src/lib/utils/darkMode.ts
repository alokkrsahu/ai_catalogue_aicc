// src/lib/utils/darkMode.ts
import { darkMode } from '$lib/stores/darkMode';
import { get } from 'svelte/store';

/**
 * Utility function to conditionally apply dark mode classes
 * @param lightClass - Classes to apply in light mode
 * @param darkClass - Classes to apply in dark mode
 * @returns The appropriate class string based on current mode
 */
export function darkModeClass(lightClass: string, darkClass: string = ''): string {
  const isDark = get(darkMode);
  return isDark ? darkClass : lightClass;
}

/**
 * Utility function to get a class that works with both light and dark modes
 * @param baseClass - Base classes that work in both modes
 * @param darkOverride - Additional classes for dark mode
 * @returns Combined class string
 */
export function adaptiveClass(baseClass: string, darkOverride: string = ''): string {
  const isDark = get(darkMode);
  return isDark ? `${baseClass} ${darkOverride}` : baseClass;
}

/**
 * Reactive utility to get classes based on dark mode state
 * Subscribe to this to get reactive class updates
 */
export function createDarkModeClasses(lightClasses: string, darkClasses: string) {
  return {
    subscribe: darkMode.subscribe,
    get: () => get(darkMode) ? darkClasses : lightClasses
  };
}
