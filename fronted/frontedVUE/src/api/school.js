import api from './http'
export const searchSchools = (keyword) =>
  api.get('schools', { params: { keyword } })