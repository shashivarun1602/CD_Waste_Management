const dashboard = {
  async load() { return api.get('/dashboard'); },
  async transports() { return api.get('/transports'); },
  async sites() { return api.get('/sites'); },
  async vehicles() { return api.get('/vehicles'); },
  async devices() { return api.get('/devices'); },
  async gps() { return api.get('/gps'); }
};
