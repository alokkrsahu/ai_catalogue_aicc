// src/lib/styles/universalDarkMode.ts
import { darkMode } from '$lib/stores/darkMode';
import { get } from 'svelte/store';

/**
 * Universal Dark Mode System
 * This system automatically applies dark mode styles to all components
 * without requiring manual dark mode classes for each feature
 */

export interface UniversalDarkModeConfig {
  // Base theme colors
  backgrounds: {
    primary: string;
    secondary: string;
    tertiary: string;
    card: string;
    elevated: string;
  };
  text: {
    primary: string;
    secondary: string;
    muted: string;
    inverse: string;
  };
  borders: {
    primary: string;
    secondary: string;
    focus: string;
  };
  shadows: {
    sm: string;
    md: string;
    lg: string;
  };
}

// Light theme configuration
export const lightTheme: UniversalDarkModeConfig = {
  backgrounds: {
    primary: '#f0f4f8',      // oxford-50
    secondary: '#ffffff',     // white
    tertiary: '#d9e2ec',     // oxford-100
    card: '#ffffff',         // white
    elevated: '#ffffff',     // white
  },
  text: {
    primary: '#243b53',      // oxford-800
    secondary: '#334e68',    // oxford-700
    muted: '#627d98',        // oxford-500
    inverse: '#ffffff',      // white
  },
  borders: {
    primary: '#bcccdc',      // oxford-200
    secondary: '#d9e2ec',    // oxford-100
    focus: '#002147',        // oxford-blue
  },
  shadows: {
    sm: '0 2px 4px rgba(0, 33, 71, 0.1)',
    md: '0 4px 14px rgba(0, 33, 71, 0.15)',
    lg: '0 8px 25px rgba(0, 33, 71, 0.25)',
  }
};

// Dark theme configuration
export const darkTheme: UniversalDarkModeConfig = {
  backgrounds: {
    primary: '#0f0f0f',      // Deep dark
    secondary: '#1a1a1a',    // Dark background
    tertiary: '#2a2a2a',     // Card backgrounds
    card: '#2a2a2a',         // Card backgrounds
    elevated: '#3a3a3a',     // Elevated surfaces
  },
  text: {
    primary: '#f9fafb',      // High contrast white
    secondary: '#e5e7eb',    // Light gray
    muted: '#a3a3a3',        // Muted text
    inverse: '#0f0f0f',      // Dark text for light backgrounds
  },
  borders: {
    primary: '#3a3a3a',      // Dark borders
    secondary: '#525252',    // Secondary borders
    focus: '#002147',        // Oxford blue (preserved)
  },
  shadows: {
    sm: '0 2px 4px rgba(0, 0, 0, 0.3)',
    md: '0 4px 14px rgba(0, 0, 0, 0.4)',
    lg: '0 8px 25px rgba(0, 0, 0, 0.5)',
  }
};

/**
 * Get current theme configuration
 */
export function getCurrentTheme(): UniversalDarkModeConfig {
  const isDark = get(darkMode);
  return isDark ? darkTheme : lightTheme;
}

/**
 * Apply universal theme to document
 */
export function applyUniversalTheme() {
  const theme = getCurrentTheme();
  const root = document.documentElement;
  
  // Apply CSS custom properties
  Object.entries(theme.backgrounds).forEach(([key, value]) => {
    root.style.setProperty(`--theme-bg-${key}`, value);
  });
  
  Object.entries(theme.text).forEach(([key, value]) => {
    root.style.setProperty(`--theme-text-${key}`, value);
  });
  
  Object.entries(theme.borders).forEach(([key, value]) => {
    root.style.setProperty(`--theme-border-${key}`, value);
  });
  
  Object.entries(theme.shadows).forEach(([key, value]) => {
    root.style.setProperty(`--theme-shadow-${key}`, value);
  });
}

/**
 * Universal CSS class generator
 */
export function getUniversalClasses() {
  const theme = getCurrentTheme();
  
  return {
    // Background classes
    bgPrimary: 'bg-theme-primary',
    bgSecondary: 'bg-theme-secondary',
    bgCard: 'bg-theme-card',
    bgElevated: 'bg-theme-elevated',
    
    // Text classes
    textPrimary: 'text-theme-primary',
    textSecondary: 'text-theme-secondary',
    textMuted: 'text-theme-muted',
    
    // Border classes
    borderPrimary: 'border-theme-primary',
    borderSecondary: 'border-theme-secondary',
    borderFocus: 'border-theme-focus',
    
    // Shadow classes
    shadowSm: 'shadow-theme-sm',
    shadowMd: 'shadow-theme-md',
    shadowLg: 'shadow-theme-lg',
  };
}

/**
 * Initialize universal dark mode system
 */
export function initializeUniversalDarkMode() {
  // Apply initial theme
  applyUniversalTheme();
  
  // Subscribe to dark mode changes
  darkMode.subscribe(() => {
    applyUniversalTheme();
  });
  
  // Watch for system theme changes
  if (typeof window !== 'undefined') {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', (e) => {
      // Only auto-switch if user hasn't manually set preference
      const savedPreference = localStorage.getItem('darkMode');
      if (savedPreference === null) {
        darkMode.set(e.matches);
      }
    });
  }
}
