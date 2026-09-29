const dashboard = {
  async load() { return api.get('/dashboard'); },
  async transports() { return api.get('/transports'); },
  async sites() { return api.get('/sites'); },
  async vehicles() { return api.get('/vehicles'); },
  async devices() { return api.get('/devices'); },
  async gps() { return api.get('/gps'); },
  async siteSummaries() { return api.get('/dashboard/sites'); },
  async siteSummary(siteId) { return api.get(`/dashboard/sites/${encodeURIComponent(siteId)}`); },
  async siteVehicles(siteId) { return api.get(`/dashboard/sites/${encodeURIComponent(siteId)}/vehicles`); },
  async siteVehicleTransports(siteId, vehicleId) { return api.get(`/dashboard/sites/${encodeURIComponent(siteId)}/vehicles/${encodeURIComponent(vehicleId)}/transports`); }
};
