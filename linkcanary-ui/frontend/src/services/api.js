const API_BASE = '/api';

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  
  return response.json();
}

export const crawlsApi = {
  list: (skip = 0, limit = 20, status = null) => {
    const params = new URLSearchParams({ skip, limit });
    if (status) params.append('status', status);
    return fetchJson(`${API_BASE}/crawls?${params}`);
  },
  
  get: (id) => fetchJson(`${API_BASE}/crawls/${id}`),
  
  create: (data) => fetchJson(`${API_BASE}/crawls`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  delete: (id) => fetchJson(`${API_BASE}/crawls/${id}`, { method: 'DELETE' }),
  
  stop: (id) => fetchJson(`${API_BASE}/crawls/${id}/stop`, { method: 'POST' }),
  
  rerun: (id) => fetchJson(`${API_BASE}/crawls/${id}/rerun`, { method: 'POST' }),
  
  getReport: (id) => fetchJson(`${API_BASE}/crawls/${id}/report`),
  
  validateSitemap: (url) => fetchJson(`${API_BASE}/crawls/validate-sitemap`, {
    method: 'POST',
    body: JSON.stringify({ url }),
  }),
};

export const reportsApi = {
  downloadCsvUrl: (id) => `${API_BASE}/reports/${id}/download/csv`,
  downloadHtmlUrl: (id) => `${API_BASE}/reports/${id}/download/html`,
};

export const statsApi = {
  get: () => fetchJson(`${API_BASE}/stats`),
};

export const settingsApi = {
  get: () => fetchJson(`${API_BASE}/settings`),
  update: (data) => fetchJson(`${API_BASE}/settings`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
};

export const backlinksApi = {
  check: (data) => fetchJson(`${API_BASE}/backlinks/check`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

export function createCrawlWebSocket(crawlId, onMessage, onError, onClose) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/crawl/${crawlId}`;
  
  const ws = new WebSocket(wsUrl);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    if (onError) onError(error);
  };
  
  ws.onclose = () => {
    if (onClose) onClose();
  };
  
  return ws;
}
