<!-- src/lib/components/Navigation.svelte -->

<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { isAuthenticated, isAdmin, user, logout } from '$lib/stores/auth';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { toasts } from '$lib/stores/toast';
  import PasswordChangeModal from './PasswordChangeModal.svelte';
  
  let isMenuOpen = false;
  let isDropdownOpen = false;
  let showPasswordModal = false;
  
  // Initialize with default values in case page is not loaded yet
  $: pathname = $page?.url?.pathname || '/';
  
  // Close dropdowns when navigating to a new page
  $: if (pathname) {
    closeDropdown();
    closeMenu();
  }
  
  function handleLogout() {
    logout();
    toasts.success('Logged out successfully');
    goto('/login');
  }
  
  function toggleMenu() {
    isMenuOpen = !isMenuOpen;
  }
  
  function toggleDropdown() {
    isDropdownOpen = !isDropdownOpen;
  }
  
  function closeMenu() {
    isMenuOpen = false;
  }
  
  function closeDropdown() {
    isDropdownOpen = false;
  }
  
  // Close dropdown when clicking outside
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('[data-dropdown-container]')) {
      closeDropdown();
    }
  }
  
  function handleProfileClick() {
    // You can implement navigation to profile page here
    goto('/profile');
    closeDropdown();
  }
  
  function openPasswordModal() {
    showPasswordModal = true;
    closeDropdown();
  }
  
  function handlePasswordChanged() {
    // Optional: Show success message or perform any additional actions
    toasts.success('Password updated successfully');
  }
  
  // Setup click outside listener on mount
  onMount(() => {
    if (typeof document !== 'undefined') {
      document.addEventListener('click', handleClickOutside);
    }
  });
  
  // Cleanup click outside listener on destroy
  onDestroy(() => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('click', handleClickOutside);
    }
  });
</script>

<nav class="nav-oxford">
  <div class="w-full px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <div class="flex items-center">
        <div class="flex-shrink-0">
          <a href="/" class="flex items-center space-x-3">
            <img src="/logo.svg" alt="AI and ML Competency Centre Logo" class="h-12 w-auto" />
            <span class="logo-text text-xl hidden sm:block">AI and ML Competency Centre</span>
            <span class="logo-text text-lg block sm:hidden">AIMLCC</span>
          </a>
        </div>
        <div class="hidden md:block">
          <div class="ml-10 flex items-baseline space-x-4">
            {#if $isAuthenticated}
              <a 
                href="/" 
                class={pathname === '/' 
                  ? 'bg-[#001122] text-white px-3 py-2 rounded-md text-sm font-medium' 
                  : 'text-gray-300 hover:bg-[#003366] hover:text-white px-3 py-2 rounded-md text-sm font-medium'}
                aria-current={pathname === '/' ? 'page' : undefined}
              >
                Dashboard
              </a>
              
              {#if $isAdmin}
                <a 
                  href="/admin" 
                  class={pathname?.startsWith('/admin') 
                    ? 'bg-[#001122] text-white px-3 py-2 rounded-md text-sm font-medium' 
                    : 'text-gray-300 hover:bg-[#003366] hover:text-white px-3 py-2 rounded-md text-sm font-medium'}
                  aria-current={pathname?.startsWith('/admin') ? 'page' : undefined}
                >
                  Admin
                </a>
              {/if}
            {:else}
              <a 
                href="/login" 
                class={pathname === '/login' 
                  ? 'bg-[#001122] text-white px-3 py-2 rounded-md text-sm font-medium' 
                  : 'text-gray-300 hover:bg-[#003366] hover:text-white px-3 py-2 rounded-md text-sm font-medium'}
                aria-current={pathname === '/login' ? 'page' : undefined}
              >
                Login
              </a>
            {/if}
          </div>
        </div>
      </div>
      
      {#if $isAuthenticated}
        <div class="hidden md:block">
          <div class="ml-4 flex items-center md:ml-6 space-x-2">
            
            <!-- Profile dropdown -->
            <div class="ml-3 relative" data-dropdown-container>
              <div>
                <button 
                  type="button" 
                  class="max-w-xs bg-[#002147] rounded-full flex items-center text-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#002147] focus:ring-white" 
                  id="user-menu-button" 
                  aria-expanded={isDropdownOpen} 
                  aria-haspopup="true"
                  on:click={toggleDropdown}
                >
                  <span class="sr-only">Open user menu</span>
                  <div class="h-8 w-8 rounded-full bg-gray-500 flex items-center justify-center text-white">
                    {$user?.first_name ? $user.first_name[0] : $user?.email?.[0]?.toUpperCase() || '?'}
                  </div>
                </button>
              </div>
              
              {#if isDropdownOpen}
                <div 
                  class="origin-top-right absolute right-0 mt-2 w-48 rounded-md shadow-xl py-1 bg-white ring-1 ring-black ring-opacity-5 focus:outline-none z-50 border border-gray-200" 
                  role="menu" 
                  aria-orientation="vertical" 
                  aria-labelledby="user-menu-button" 
                  tabindex="-1"
                  style="z-index: 9999;"
                  on:mouseleave={closeDropdown}
                >
                  <div class="block px-4 py-2 text-sm text-gray-700 border-b border-gray-100">
                    <div class="font-medium">{$user?.first_name || ''} {$user?.last_name || ''}</div>
                    <div class="text-gray-500">{$user?.email || ''}</div>
                  </div>
                  
                  {#if $isAdmin}
                    <a 
                      href="/admin" 
                      class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100" 
                      role="menuitem" 
                      tabindex="-1" 
                      id="user-menu-item-0"
                    >
                      Admin Dashboard
                    </a>
                  {/if}
                  
                  <button 
                    on:click={handleProfileClick}
                    class="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100" 
                    role="menuitem" 
                    tabindex="-1" 
                    id="user-menu-item-1"
                  >
                    <i class="fas fa-user mr-2"></i>
                    Profile
                  </button>
                  
                  <button 
                    on:click={openPasswordModal}
                    class="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100" 
                    role="menuitem" 
                    tabindex="-1" 
                    id="user-menu-item-2"
                  >
                    <i class="fas fa-key mr-2"></i>
                    Change Password
                  </button>
                  
                  <button 
                    on:click={handleLogout}
                    class="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 focus:outline-none" 
                    role="menuitem" 
                    tabindex="-1" 
                    id="user-menu-item-3"
                  >
                    <i class="fas fa-sign-out-alt mr-2"></i>
                    Sign out
                  </button>
                </div>
              {/if}
            </div>
          </div>
        </div>
      {/if}
      
      <div class="-mr-2 flex md:hidden">
        <!-- Mobile menu button -->
        <button 
          type="button" 
          class="bg-[#002147] inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-white hover:bg-[#003366] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#002147] focus:ring-white" 
          aria-controls="mobile-menu" 
          aria-expanded={isMenuOpen}
          on:click={toggleMenu}
        >
          <span class="sr-only">Open main menu</span>
          <!-- Icon when menu is closed -->
          <svg 
            class={isMenuOpen ? 'hidden' : 'block'} 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor" 
            aria-hidden="true"
            width="24"
            height="24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <!-- Icon when menu is open -->
          <svg 
            class={isMenuOpen ? 'block' : 'hidden'} 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor" 
            aria-hidden="true"
            width="24"
            height="24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Mobile menu, show/hide based on menu state. -->
  <div class={isMenuOpen ? 'block' : 'hidden'} id="mobile-menu">
    <div class="px-2 pt-2 pb-3 space-y-1 sm:px-3">
      {#if $isAuthenticated}
        <a 
          href="/" 
          class={pathname === '/' 
            ? 'bg-[#001122] text-white block px-3 py-2 rounded-md text-base font-medium' 
            : 'text-gray-300 hover:bg-[#003366] hover:text-white block px-3 py-2 rounded-md text-base font-medium'}
          aria-current={pathname === '/' ? 'page' : undefined}
          on:click={closeMenu}
        >
          Dashboard
        </a>
        
        {#if $isAdmin}
          <a 
            href="/admin" 
            class={pathname?.startsWith('/admin') 
              ? 'bg-[#001122] text-white block px-3 py-2 rounded-md text-base font-medium' 
              : 'text-gray-300 hover:bg-[#003366] hover:text-white block px-3 py-2 rounded-md text-base font-medium'}
            aria-current={pathname?.startsWith('/admin') ? 'page' : undefined}
            on:click={closeMenu}
          >
            Admin
          </a>
        {/if}
      {:else}
        <a 
          href="/login" 
          class={pathname === '/login' 
            ? 'bg-[#001122] text-white block px-3 py-2 rounded-md text-base font-medium' 
            : 'text-gray-300 hover:bg-[#003366] hover:text-white block px-3 py-2 rounded-md text-base font-medium'}
          aria-current={pathname === '/login' ? 'page' : undefined}
          on:click={closeMenu}
        >
          Login
        </a>
      {/if}
    </div>
    
    {#if $isAuthenticated}
      <div class="pt-4 pb-3 border-t border-gray-700">
        <div class="flex items-center px-5">
          <div class="flex-shrink-0">
            <!-- Logo in mobile menu -->
            <img src="/logo.svg" alt="AI and ML Competency Centre Logo" class="h-12 w-auto" />
          </div>
          <div class="ml-3">
            <div class="text-base font-medium leading-none text-white">
              {$user?.first_name || ''} {$user?.last_name || ''}
            </div>
            <div class="text-sm font-medium leading-none text-gray-400 mt-1">
              {$user?.email || ''}
            </div>
          </div>
        </div>
        <div class="mt-3 px-2 space-y-1">
          
          {#if $isAdmin}
            <a 
              href="/admin" 
              class="block px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
              on:click={closeMenu}
            >
              Admin Dashboard
            </a>
          {/if}
          
          <button 
            on:click={handleProfileClick}
            class="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
          >
            <i class="fas fa-user mr-2"></i>
            Profile
          </button>
          
          <button 
            on:click={() => { openPasswordModal(); closeMenu(); }}
            class="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
          >
            <i class="fas fa-key mr-2"></i>
            Change Password
          </button>
          
          <button 
            on:click={handleLogout}
            class="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
          >
            <i class="fas fa-sign-out-alt mr-2"></i>
            Sign out
          </button>
        </div>
      </div>
    {/if}
  </div>
</nav>

<!-- Password Change Modal -->
<PasswordChangeModal 
  bind:isOpen={showPasswordModal}
  on:passwordChanged={handlePasswordChanged}
  on:close={() => showPasswordModal = false}
/>
