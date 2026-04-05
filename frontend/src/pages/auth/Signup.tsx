import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import {
  Button,
  Form,
  TextInput,
  PasswordInput,
  RadioButtonGroup,
  RadioButton,
  InlineNotification,
  Stack,
  Tag,
  Loading,
  Select,
  SelectItem,
} from '@carbon/react'
import { getInvitationInfo, signup } from '../../api/auth'
import { setToken } from '../../api/client'
import type { InvitationInfoResponse } from '../../api/types'
import type { AxiosError } from 'axios'

const TIER_OPTIONS = [
  {
    id: 'tier_1',
    label: 'Starter',
    price: '$500 - $1,500 / assessment',
    limit: '10 assessments/month',
    features: ['Basic governance score', 'Uploaded documents analysis', 'PDF report'],
  },
  {
    id: 'tier_2',
    label: 'Professional',
    price: '$2,000 - $5,000 / assessment',
    limit: '50 assessments/month',
    features: [
      'Full governance score',
      'External signals + litigation data',
      'Detailed PDF report',
      'Evidence trail',
    ],
  },
  {
    id: 'enterprise',
    label: 'Enterprise',
    price: '$50K - $200K / year',
    limit: 'Unlimited assessments',
    features: [
      'All Professional features',
      'Custom dimension weights per carrier',
      'Priority support',
      'SLA guarantee',
    ],
  },
]

const INDUSTRIES = [
  'Financial Services',
  'Insurance',
  'HR Technology',
  'Healthcare',
  'Legal Tech',
  'Insurtech',
  'Fintech',
  'E-commerce',
  'Other',
]

export default function Signup() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''

  const [inviteInfo, setInviteInfo] = useState<InvitationInfoResponse | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteLoading, setInviteLoading] = useState(true)

  // Form fields
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  // Org fields (only for org_manager)
  const [orgName, setOrgName] = useState('')
  const [orgSlug, setOrgSlug] = useState('')
  const [orgIndustry, setOrgIndustry] = useState('')
  const [selectedTier, setSelectedTier] = useState('tier_1')

  const [submitError, setSubmitError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Auto-generate slug from org name
  function handleOrgNameChange(value: string) {
    setOrgName(value)
    setOrgSlug(value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''))
  }

  useEffect(() => {
    if (!token) {
      setInviteError('No invitation token provided.')
      setInviteLoading(false)
      return
    }
    getInvitationInfo(token)
      .then((info) => {
        setInviteInfo(info)
        setInviteLoading(false)
      })
      .catch((err: AxiosError<{ detail: string }>) => {
        const msg = err.response?.data?.detail ?? 'Invalid or expired invitation link.'
        setInviteError(msg)
        setInviteLoading(false)
      })
  }, [token])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitError(null)

    if (password !== confirmPassword) {
      setSubmitError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setSubmitError('Password must be at least 8 characters')
      return
    }

    const isManager = inviteInfo?.role === 'org_manager' && !inviteInfo?.org_id

    if (isManager && !orgName) {
      setSubmitError('Organisation name is required')
      return
    }

    setLoading(true)
    try {
      const response = await signup({
        token,
        password,
        first_name: firstName || undefined,
        last_name: lastName || undefined,
        org: isManager
          ? {
              name: orgName,
              slug: orgSlug,
              tier: selectedTier,
              industry: orgIndustry || undefined,
            }
          : undefined,
      })

      setToken(response.access_token)
      sessionStorage.setItem(
        'camille_user',
        JSON.stringify({ user: response.user, token: response.access_token })
      )
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      setSubmitError(axiosErr.response?.data?.detail ?? 'Signup failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (inviteLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Loading description="Validating invitation..." withOverlay={false} />
      </div>
    )
  }

  if (inviteError) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <InlineNotification kind="error" title="Invalid invitation" subtitle={inviteError} lowContrast />
          <div className="auth-footer" style={{ marginTop: '1rem' }}>
            <Link to="/login">Back to sign in</Link>
          </div>
        </div>
      </div>
    )
  }

  const isNewOrgManager = inviteInfo?.role === 'org_manager' && !inviteInfo?.org_id

  return (
    <div className="auth-page auth-page--wide">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">Create your account</h1>
          {inviteInfo?.org_name ? (
            <p className="auth-subtitle">
              Joining <strong>{inviteInfo.org_name}</strong> as{' '}
              {inviteInfo.role === 'org_underwriter' ? 'Underwriter' : 'Organisation Manager'}
            </p>
          ) : (
            <p className="auth-subtitle">You have been invited to Camille</p>
          )}
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <Tag type="blue">{inviteInfo?.email}</Tag>
        </div>

        {submitError && (
          <InlineNotification
            kind="error"
            title="Error"
            subtitle={submitError}
            lowContrast
            style={{ marginBottom: '1rem' }}
          />
        )}

        <Form onSubmit={handleSubmit}>
          <Stack gap={6}>
            {/* Personal details */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <TextInput
                id="firstName"
                labelText="First name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                autoFocus
              />
              <TextInput
                id="lastName"
                labelText="Last name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>

            <PasswordInput
              id="password"
              labelText="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              helperText="At least 8 characters"
            />
            <PasswordInput
              id="confirmPassword"
              labelText="Confirm password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
            />

            {/* Organisation setup - only for new org managers */}
            {isNewOrgManager && (
              <>
                <hr style={{ borderColor: 'var(--cds-border-subtle)' }} />
                <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Organisation Details</h3>

                <TextInput
                  id="orgName"
                  labelText="Organisation name"
                  value={orgName}
                  onChange={(e) => handleOrgNameChange(e.target.value)}
                  required
                />
                <TextInput
                  id="orgSlug"
                  labelText="URL slug"
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value)}
                  helperText="Used in URLs - lowercase letters, numbers, hyphens only"
                  required
                />

                <Select
                  id="orgIndustry"
                  labelText="Industry"
                  value={orgIndustry}
                  onChange={(e) => setOrgIndustry(e.target.value)}
                >
                  <SelectItem value="" text="Select industry..." />
                  {INDUSTRIES.map((i) => (
                    <SelectItem key={i} value={i} text={i} />
                  ))}
                </Select>

                <div>
                  <p style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '1rem' }}>
                    Select your plan
                  </p>
                  <RadioButtonGroup
                    legendText=""
                    name="tier"
                    valueSelected={selectedTier}
                    onChange={(value) => setSelectedTier(value as string)}
                    orientation="vertical"
                  >
                    {TIER_OPTIONS.map((tier) => (
                      <RadioButton
                        key={tier.id}
                        id={`tier-${tier.id}`}
                        labelText={
                          <div style={{ padding: '0.5rem 0' }}>
                            <div style={{ fontWeight: 600 }}>{tier.label}</div>
                            <div style={{ fontSize: '0.8125rem', color: 'var(--cds-text-secondary)', marginTop: '0.25rem' }}>
                              {tier.price} - {tier.limit}
                            </div>
                            <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.25rem', fontSize: '0.8125rem' }}>
                              {tier.features.map((f) => <li key={f}>{f}</li>)}
                            </ul>
                          </div>
                        }
                        value={tier.id}
                      />
                    ))}
                  </RadioButtonGroup>
                </div>
              </>
            )}

            <Button
              type="submit"
              disabled={loading}
              style={{ width: '100%', maxWidth: '100%' }}
            >
              {loading ? 'Creating account...' : 'Create account'}
            </Button>
          </Stack>
        </Form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  )
}
