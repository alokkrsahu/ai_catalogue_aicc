import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  
  // Server configuration with improved WebSocket handling and API proxy
  server: {
    hmr: {
      overlay: true,
      clientPort: 5173,
    },
    port: 5173,
    strictPort: false,
    host: 'localhost',
    allowedHosts: ['aicc.uksouth.cloudapp.azure.com'],
    // Add watch configuration to ignore node_modules
    watch: {
      ignored: ['**/node_modules/**', '**/dist/**', '**/.DS_Store']
    },
    // Proxy API calls to Django backend (development only)
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => {
          console.log(`🔄 Proxying: ${path} -> ${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}${path}`);
          return path;
        },
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('❌ Proxy Error:', err.message);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('📡 Proxy Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('✅ Proxy Response:', proxyRes.statusCode, req.url);
          });
        }
      }
    }
  },
  
  // Updated optimizeDeps configuration with explicit exclusions
  optimizeDeps: {
    include: [
      'svelte',
      'svelte/store',
      'svelte/transition',
      'axios'
    ],
    esbuildOptions: {
      target: 'esnext'
    }
  },
  
  // Build configuration
  build: {
    reportCompressedSize: false,
    target: 'esnext',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000
  },
  
  // Use a different cache directory
  cacheDir: '.vite_cache',
  
  // Resolve configuration
  resolve: {
    dedupe: ['svelte', 'svelte/transition', 'svelte/store']
  }
});
