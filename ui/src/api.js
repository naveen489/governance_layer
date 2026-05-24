let accessToken = null;

async function fetchToken() {
  const payload = {
    user_id: "admin_01",
    role: "admin",
    workspace_id: "default"
  };

  const response = await fetch('/api/governance/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error('Failed to fetch authentication token');
  }

  const data = await response.json();
  accessToken = data.access_token;
  return accessToken;
}

export async function fetchApi(url, options = {}) {
  if (!accessToken) {
    await fetchToken();
  }

  const headers = {
    'Authorization': `Bearer ${accessToken}`,
    ...options.headers
  };

  let response = await fetch(url, { ...options, headers });
  
  // Basic retry once if token expired
  if (response.status === 401) {
    await fetchToken();
    headers['Authorization'] = `Bearer ${accessToken}`;
    response = await fetch(url, { ...options, headers });
  }

  return response;
}
