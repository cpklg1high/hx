import api from './http'
export const searchSalespersons = (keyword) =>
  api.get('users/salespersons', { params: { keyword } })

