const facilitiesApi = {
	list() { return api.get('/facilities'); },
	create(data) { return api.post('/facilities', data); },
	update(facilityId, data) { return api.put(`/facilities/${encodeURIComponent(facilityId)}`, data); },
	deactivate(facilityId) { return api.delete(`/facilities/${encodeURIComponent(facilityId)}`); }
};
