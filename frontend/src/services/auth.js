import api from './api'
import { STORAGE_KEYS } from '@/lib/constants'

/** Auth API calls, isolated from the components that trigger them. */
export const authService = {
  async login(email, password) {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access_token)
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh_token)
    if (data.user?.hospital_id) {
      localStorage.setItem(STORAGE_KEYS.HOSPITAL, data.user.hospital_id)
    }
    return data.user
  },

  async me() {
    const { data } = await api.get('/auth/me')
    return data
  },

  async updateProfile(payload) {
    const { data } = await api.patch('/auth/me', payload)
    return data
  },

  async changePassword(currentPassword, newPassword) {
    const { data } = await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return data
  },

  logout() {
    localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
    localStorage.removeItem(STORAGE_KEYS.HOSPITAL)
  },

  hasToken() {
    return Boolean(localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN))
  },
}
