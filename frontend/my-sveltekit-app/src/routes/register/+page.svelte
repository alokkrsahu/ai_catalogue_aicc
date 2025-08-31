<!-- src/routes/register/+page.svelte -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { registerUser } from '$lib/services/api';
  import { login, isAuthenticated } from '$lib/stores/auth';

  import type { RegisterData } from '$lib/types';

  let formData: RegisterData = {
    email: '',
    password: '',
    password2: '',
    first_name: '',
    last_name: ''
  };
  
  let loading = false;
  let errors: Record<string, string> = {};
  
  $: if ($isAuthenticated) {
    goto('/');
  }

  async function handleSubmit() {
    errors = {};
    loading = true;
    
    // Basic validation
    if (formData.password !== formData.password2) {
      errors.password2 = 'Passwords do not match';
      loading = false;
      return;
    }
    
    try {
      const response = await registerUser(formData);
      login(response.user, response.access, response.refresh);
      goto('/');
    } catch (err: any) {
      if (err.response?.data) {
        // API validation errors
        errors = err.response.data;
      } else {
        errors.general = 'Registration failed. Please try again later.';
      }
    } finally {
      loading = false;
    }
  }
</script>



<div class="min-h-screen bg-gray-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
  <div class="sm:mx-auto sm:w-full sm:max-w-md">
    <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
      Create a new account
    </h2>
    <p class="mt-2 text-center text-sm text-gray-600">
      Or
      <a href="/login" class="font-medium text-blue-600 hover:text-blue-500">
        sign in to your existing account
      </a>
    </p>
  </div>

  <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
    <div class="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
      <form on:submit|preventDefault={handleSubmit} class="space-y-6">
        {#if errors.general}
          <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {errors.general}
          </div>
        {/if}
        
        <div>
          <label for="email" class="form-label">
            Email address
          </label>
          <div class="mt-1">
            <input
              id="email"
              name="email"
              type="email"
              autocomplete="email"
              required
              bind:value={formData.email}
              class="form-input"
            />
            {#if errors.email}
              <p class="form-error">{errors.email}</p>
            {/if}
          </div>
        </div>

        <div class="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
          <div>
            <label for="first_name" class="form-label">
              First name
            </label>
            <div class="mt-1">
              <input
                id="first_name"
                name="first_name"
                type="text"
                autocomplete="given-name"
                bind:value={formData.first_name}
                class="form-input"
              />
              {#if errors.first_name}
                <p class="form-error">{errors.first_name}</p>
              {/if}
            </div>
          </div>

          <div>
            <label for="last_name" class="form-label">
              Last name
            </label>
            <div class="mt-1">
              <input
                id="last_name"
                name="last_name"
                type="text"
                autocomplete="family-name"
                bind:value={formData.last_name}
                class="form-input"
              />
              {#if errors.last_name}
                <p class="form-error">{errors.last_name}</p>
              {/if}
            </div>
          </div>
        </div>

        <div>
          <label for="password" class="form-label">
            Password
          </label>
          <div class="mt-1">
            <input
              id="password"
              name="password"
              type="password"
              autocomplete="new-password"
              required
              bind:value={formData.password}
              class="form-input"
            />
            {#if errors.password}
              <p class="form-error">{errors.password}</p>
            {/if}
          </div>
        </div>

        <div>
          <label for="password2" class="form-label">
            Confirm Password
          </label>
          <div class="mt-1">
            <input
              id="password2"
              name="password2"
              type="password"
              autocomplete="new-password"
              required
              bind:value={formData.password2}
              class="form-input"
            />
            {#if errors.password2}
              <p class="form-error">{errors.password2}</p>
            {/if}
          </div>
        </div>

        <div>
          <button
            type="submit"
            disabled={loading}
            class="w-full btn btn-primary {loading ? 'opacity-70 cursor-not-allowed' : ''}"
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
