import { useState } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import {
  Button,
  Form,
  TextInput,
  PasswordInput,
  InlineNotification,
  Stack,
} from '@carbon/react'
import { useAuth } from '../../contexts/AuthContext'
import type { AxiosError } from 'axios'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      setError(axiosErr.response?.data?.detail ?? 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">Camille</h1>
          <p className="auth-subtitle">AI Liability Risk Assessment</p>
        </div>

        {error && (
          <InlineNotification
            kind="error"
            title="Login failed"
            subtitle={error}
            lowContrast
            style={{ marginBottom: '1rem' }}
          />
        )}

        <Form onSubmit={handleSubmit}>
          <Stack gap={5}>
            <TextInput
              id="email"
              type="email"
              labelText="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              autoFocus
            />
            <PasswordInput
              id="password"
              labelText="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
            <Button
              type="submit"
              disabled={loading}
              style={{ width: '100%', maxWidth: '100%' }}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </Stack>
        </Form>

        <div className="auth-footer">
          <Link to="/reset-password">Forgot password?</Link>
        </div>
      </div>
    </div>
  )
}
