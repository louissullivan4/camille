import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Button,
  Form,
  TextInput,
  InlineNotification,
  Stack,
} from '@carbon/react'
import { requestPasswordReset } from '../../api/auth'
import type { AxiosError } from 'axios'

export default function ResetPasswordRequest() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await requestPasswordReset(email)
      // Navigate to confirm page; pass email via state
      navigate('/reset-password/confirm', { state: { email } })
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      setError(axiosErr.response?.data?.detail ?? 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">Reset Password</h1>
          <p className="auth-subtitle">Enter your email to receive a reset code</p>
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
              autoFocus
            />
            <Button
              type="submit"
              disabled={loading}
              style={{ width: '100%', maxWidth: '100%' }}
            >
              {loading ? 'Sending...' : 'Send reset code'}
            </Button>
          </Stack>
        </Form>

        <div className="auth-footer">
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  )
}
