const api = {
  async request(path, options = {}) {
    const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.success === false) throw new Error(body.message || 'Request failed');
    return body.data;
  },
  get(path) { return this.request(path); },
  post(path, data, headers = {}) { return this.request(path, { method: 'POST', headers, body: JSON.stringify(data) }); },
  put(path, data) { return this.request(path, { method: 'PUT', body: JSON.stringify(data) }); },
  delete(path) { return this.request(path, { method: 'DELETE' }); }
};
