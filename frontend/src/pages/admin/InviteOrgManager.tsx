import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import {
  Form,
  TextInput,
  Button,
  InlineNotification,
  Stack,
  Tile,
} from '@carbon/react'
import { ArrowLeft, Send } from '@carbon/icons-react'
import { inviteOrgManager } from '../../api/invitations'

interface FormValues {
  email: string
  org_name: string
  org_slug: string
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export default function InviteOrgManager() {
  const navigate = useNavigate()
  const [successEmail, setSuccessEmail] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>()

  const orgName = watch('org_name', '')

  // Auto-generate slug from org name
  const handleOrgNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue('org_name', e.target.value)
    setValue('org_slug', slugify(e.target.value))
  }

  const onSubmit = async (data: FormValues) => {
    setIsSubmitting(true)
    setErrorMsg(null)
    setSuccessEmail(null)
    try {
      await inviteOrgManager({
        email: data.email,
        org_name: data.org_name,
        org_slug: data.org_slug,
      })
      setSuccessEmail(data.email)
      reset()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErrorMsg(detail ?? 'Failed to send invitation. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: '600px' }}>
      <Button
        kind="ghost"
        renderIcon={ArrowLeft}
        onClick={() => navigate('/admin/organizations')}
        style={{ marginBottom: '1rem', paddingLeft: 0 }}
      >
        Back to Organizations
      </Button>

      <h1 style={{ marginBottom: '0.5rem' }}>Invite Org Manager</h1>
      <p style={{ color: 'var(--cds-text-secondary)', marginBottom: '1.5rem' }}>
        Send an invitation email to a new organization manager. They will receive a link to create their
        account and organization.
      </p>

      {successEmail && (
        <InlineNotification
          kind="success"
          title="Invitation sent"
          subtitle={`An invitation email has been sent to ${successEmail}.`}
          onCloseButtonClick={() => setSuccessEmail(null)}
          style={{ marginBottom: '1.5rem' }}
        />
      )}

      {errorMsg && (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={errorMsg}
          onCloseButtonClick={() => setErrorMsg(null)}
          style={{ marginBottom: '1.5rem' }}
        />
      )}

      <Tile>
        <Form onSubmit={handleSubmit(onSubmit)}>
          <Stack gap={6}>
            <TextInput
              id="email"
              labelText="Manager email address"
              placeholder="manager@company.com"
              type="email"
              invalid={!!errors.email}
              invalidText={errors.email?.message}
              {...register('email', {
                required: 'Email is required',
                pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Enter a valid email' },
              })}
            />

            <TextInput
              id="org_name"
              labelText="Organization name"
              placeholder="Acme Insurance"
              invalid={!!errors.org_name}
              invalidText={errors.org_name?.message}
              value={orgName}
              onChange={handleOrgNameChange}
            />

            <TextInput
              id="org_slug"
              labelText="Organization slug"
              helperText="URL-safe identifier, auto-generated from name"
              placeholder="acme-insurance"
              invalid={!!errors.org_slug}
              invalidText={errors.org_slug?.message}
              {...register('org_slug', {
                required: 'Slug is required',
                pattern: {
                  value: /^[a-z0-9-]+$/,
                  message: 'Slug must be lowercase letters, numbers, and hyphens only',
                },
              })}
            />

            <Button renderIcon={Send} type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Sending...' : 'Send Invitation'}
            </Button>
          </Stack>
        </Form>
      </Tile>
    </div>
  )
}
