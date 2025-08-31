// src/lib/stores/darkMode.ts
import { writable } from 'svelte/store';
import { browser } from '$app/environment';

// Create a writable store for dark mode
function createDarkModeStore() {
  // Initialize with system preference or saved preference
  const getInitialValue = () => {
    if (!browser) return false;
    
    // Check localStorage first
    const saved = localStorage.getItem('darkMode');
    if (saved !== null) {
      return JSON.parse(saved);
    }
    
    // Fall back to system preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  };

  const { subscribe, set, update } = writable(getInitialValue());

  return {
    subscribe,
    toggle: () => update(value => {
      const newValue = !value;
      
      // Save to localStorage
      if (browser) {
        localStorage.setItem('darkMode', JSON.stringify(newValue));
        
        // Apply to document class
        if (newValue) {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
        
        // Trigger custom event for universal theme system
        window.dispatchEvent(new CustomEvent('darkModeChanged', { detail: newValue }));
      }
      
      return newValue;
    }),
    set: (value: boolean) => {
      // Save to localStorage
      if (browser) {
        localStorage.setItem('darkMode', JSON.stringify(value));
        
        // Apply to document class
        if (value) {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
        
        // Trigger custom event for universal theme system
        window.dispatchEvent(new CustomEvent('darkModeChanged', { detail: value }));
      }
      
      set(value);
    },
    // Initialize the document class on first load
    init: () => {
      if (browser) {
        const value = getInitialValue();
        if (value) {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
        
        // Trigger initial event for universal theme system
        window.dispatchEvent(new CustomEvent('darkModeChanged', { detail: value }));
      }
    }
  };
}

export const darkMode = createDarkModeStore();
