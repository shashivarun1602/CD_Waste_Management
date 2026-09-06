const api = {
  async request(path, options = {}) {
    const response = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...options });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.success === false) throw new Error(body.message || 'Request failed');
    return body.data;
  },
  get(path) { return this.request(path); },
  post(path, data) { return this.request(path, { method: 'POST', body: JSON.stringify(data) }); },
  put(path, data) { return this.request(path, { method: 'PUT', body: JSON.stringify(data) }); },
  delete(path) { return this.request(path, { method: 'DELETE' }); }
};
