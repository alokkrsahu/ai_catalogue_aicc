import type { PageLoad } from './$types';

// Load the deployment's public-config on the server so we can pick the right
// render state (not-available / login / chat) before the page is interactive.
export const load: PageLoad = async ({ params, fetch }) => {
  const projectId = params.project_id;
  try {
    const resp = await fetch(`/api/workflow-deploy/${projectId}/public-config/`, {
      credentials: 'include',
    });
    if (resp.status === 404) {
      return { projectId, available: false, config: null };
    }
    if (!resp.ok) {
      return { projectId, available: false, config: null };
    }
    const config = await resp.json();
    return { projectId, available: true, config };
  } catch {
    return { projectId, available: false, config: null };
  }
};

// Always prerender=false — this is a dynamic page whose state depends on the
// deployment being live and the user's login cookie.
export const prerender = false;
// SSR is fine (the load runs on the server); no need to opt out.
