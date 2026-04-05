/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useState } from 'react'
import { clearToken, setToken } from '../api/client'
import { login as apiLogin } from '../api/auth'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  isLoading: boolean
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

const USER_KEY = 'camille_user'

function loadStoredSession(): AuthState {
  try {
    const stored = sessionStorage.getItem(USER_KEY)
    if (stored) {
      const { user, token } = JSON.parse(stored) as { user: User; token: string }
      setToken(token)
      return { user, isLoading: false }
    }
  } catch {
    // ignore corrupt storage
  }
  return { user: null, isLoading: false }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Lazy initializer reads sessionStorage synchronously on mount - no useEffect needed
  const [state, setState] = useState<AuthState>(loadStoredSession)

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password)
    setToken(response.access_token)
    sessionStorage.setItem(USER_KEY, JSON.stringify({ user: response.user, token: response.access_token }))
    setState({ user: response.user, isLoading: false })
  }, [])

  const logout = useCallback(() => {
    clearToken()
    sessionStorage.removeItem(USER_KEY)
    setState({ user: null, isLoading: false })
    window.location.href = '/login'
  }, [])

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        isAuthenticated: state.user !== null,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
