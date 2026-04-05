import axios, { AxiosError } from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT from memory before every request
client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// Redirect to /login on 401
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearToken()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// In-memory token storage (survives re-renders, cleared on tab close)
let _token: string | null = null

export function setToken(token: string): void {
  _token = token
}

export function getToken(): string | null {
  return _token
}

export function clearToken(): void {
  _token = null
}

export default client
