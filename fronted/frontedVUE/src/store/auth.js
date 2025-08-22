import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: sessionStorage.getItem('access') || '',
    user: JSON.parse(sessionStorage.getItem('user') || 'null'),
  }),
  getters: {
    isAuthenticated: (s) => !!s.accessToken,
  },
  actions: {
    setAuth(payload) {
      // payload: { access, user }
      this.accessToken = payload.access
      this.user = payload.user
      sessionStorage.setItem('access', payload.access)
      sessionStorage.setItem('user', JSON.stringify(payload.user))
    },
    setAccessToken(token) {
      this.accessToken = token
      sessionStorage.setItem('access', token)
    },
    clear() {
      this.accessToken = ''
      this.user = null
      sessionStorage.removeItem('access')
      sessionStorage.removeItem('user')
    },
  },
})
