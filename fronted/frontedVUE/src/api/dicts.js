import api from './http'

export const getGrades = () => api.get('dicts/grades')
export const getRelations = () => api.get('dicts/relations')
export const getVisitChannels = () => api.get('dicts/visit_channels')
