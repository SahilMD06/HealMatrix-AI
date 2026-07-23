import axios from 'axios'

import { STORAGE_KEYS } from '@/lib/constants'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/** Single Axios instance. Every request in the app goes through this client. */
export const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// --- Request: attach the bearer token -------------------------------------
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// --- Response: refresh once on 401, normalise errors otherwise ------------
let refreshPromise = null

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
  if (!refreshToken) throw new Error('No refresh token available')

  const { data } = await axios.post(`${baseURL}/auth/refresh`, { refresh_token: refreshToken })
  localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access_token)
  if (data.refresh_token) {
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh_token)
  }
  return data.access_token
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config

    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true
      try {
        refreshPromise = refreshPromise || refreshAccessToken()
        const token = await refreshPromise
        refreshPromise = null
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      } catch (refreshError) {
        refreshPromise = null
        localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
        localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
        window.location.assign('/login')
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(normaliseError(error))
  }
)

/** Convert any Axios failure into the backend's error envelope shape. */
function normaliseError(error) {
  const envelope = error.response?.data?.error
  return {
    code: envelope?.code || (error.code === 'ECONNABORTED' ? 'timeout' : 'network_error'),
    message: envelope?.message || error.message || 'Something went wrong.',
    details: envelope?.details || {},
    correlationId: envelope?.correlation_id || null,
    status: error.response?.status ?? 0,
  }
}

/** Liveness check against the API root, used by the boot screen and settings page. */
export async function checkApiHealth() {
  const root = baseURL.replace(/\/api\/v1\/?$/, '')
  const { data } = await axios.get(`${root}/health/ready`, { timeout: 8000 })
  return data
}

export default api
