import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import {
  Button,
  Form,
  TextInput,
  PasswordInput,
  InlineNotification,
  Stack,
} from '@carbon/react'
import { confirmPasswordReset } from '../../api/auth'
import type { AxiosError } from 'axios'

export default function ResetPasswordConfirm() {
  const navigate = useNavigate()
  const location = useLocation()
  const prefillEmail = (location.state as { email?: string })?.email ?? ''

  const [email, setEmail] = useState(prefillEmail)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)
    try {
      await confirmPasswordReset(email, code, password)
      navigate('/login', { state: { successMessage: 'Password reset successfully. Please sign in.' } })
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      setError(axiosErr.response?.data?.detail ?? 'Invalid or expired code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">Enter Reset Code</h1>
          <p className="auth-subtitle">Check your email for the 6-digit code</p>
        </div>

        {error && (
          <InlineNotification
            kind="error"
            title="Error"
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
              labelText="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              readOnly={!!prefillEmail}
            />
            <TextInput
              id="code"
              labelText="Reset code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="6-digit code"
              required
              maxLength={6}
              autoFocus={!prefillEmail}
            />
            <PasswordInput
              id="password"
              labelText="New password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
            <PasswordInput
              id="confirm"
              labelText="Confirm new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              autoComplete="new-password"
            />
            <Button
              type="submit"
              disabled={loading}
              style={{ width: '100%', maxWidth: '100%' }}
            >
              {loading ? 'Resetting...' : 'Reset password'}
            </Button>
          </Stack>
        </Form>

        <div className="auth-footer">
          <Link to="/reset-password">Resend code</Link>
          {' - '}
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  )
}
