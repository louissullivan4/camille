import { useNavigate } from 'react-router-dom'
import { Grid, Column, Tile, Button, SkeletonText, Tag } from '@carbon/react'
import { Add } from '@carbon/icons-react'
import { useAuth } from '../contexts/AuthContext'
import { useOrg } from '../hooks/useOrg'

const TIER_LABELS: Record<string, string> = {
  tier_1: 'Starter',
  tier_2: 'Professional',
  enterprise: 'Enterprise',
  demo: 'Demo',
}

function ManagerDashboard() {
  const navigate = useNavigate()
  const { org, usage, isLoading } = useOrg()

  const assessmentsThisMonth = usage?.assessments_this_month ?? 0
  const monthlyLimit = usage?.monthly_limit ?? null
  const estimatedCost = usage?.estimated_cost_usd ?? null

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
        <div>
          <h1>{isLoading ? 'Loading...' : org?.name ?? 'Dashboard'}</h1>
          {org && (
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', alignItems: 'center' }}>
              <Tag type="blue">{TIER_LABELS[org.tier] ?? org.tier}</Tag>
              {org.is_demo && <Tag type="purple">Demo</Tag>}
            </div>
          )}
        </div>
        <Button renderIcon={Add} onClick={() => navigate('/assessments/new')}>
          New Assessment
        </Button>
      </div>

      <Grid>
        <Column lg={4} md={4} sm={4}>
          <Tile style={{ height: '100%' }}>
            <p style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>Assessments This Month</p>
            {isLoading ? (
              <SkeletonText width="40%" />
            ) : (
              <p style={{ fontSize: '2rem', fontWeight: 600, margin: '0.5rem 0' }}>
                {assessmentsThisMonth}
                {monthlyLimit !== null && (
                  <span style={{ fontSize: '1rem', fontWeight: 400, color: 'var(--cds-text-secondary)' }}>
                    {' '}/ {monthlyLimit}
                  </span>
                )}
              </p>
            )}
          </Tile>
        </Column>

        <Column lg={4} md={4} sm={4}>
          <Tile style={{ height: '100%' }}>
            <p style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>Estimated Cost This Month</p>
            {isLoading ? (
              <SkeletonText width="40%" />
            ) : (
              <p style={{ fontSize: '2rem', fontWeight: 600, margin: '0.5rem 0' }}>
                {estimatedCost !== null
                  ? `$${estimatedCost.toLocaleString('en-US', { minimumFractionDigits: 0 })}`
                  : org?.tier === 'enterprise'
                    ? 'Annual Plan'
                    : 'Free'}
              </p>
            )}
          </Tile>
        </Column>

        <Column lg={4} md={4} sm={4}>
          <Tile style={{ height: '100%' }}>
            <p style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>Remaining Quota</p>
            {isLoading ? (
              <SkeletonText width="40%" />
            ) : (
              <p style={{ fontSize: '2rem', fontWeight: 600, margin: '0.5rem 0' }}>
                {monthlyLimit !== null
                  ? Math.max(0, monthlyLimit - assessmentsThisMonth)
                  : <span style={{ fontSize: '1.25rem' }}>Unlimited</span>}
              </p>
            )}
          </Tile>
        </Column>
      </Grid>

      <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <Button kind="secondary" onClick={() => navigate('/assessments')}>
          View All Assessments
        </Button>
        <Button kind="secondary" onClick={() => navigate('/team')}>
          Manage Team
        </Button>
      </div>
    </div>
  )
}

function UnderwriterDashboard() {
  const navigate = useNavigate()
  const { user } = useAuth()

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1>My Dashboard</h1>
          <p style={{ color: 'var(--cds-text-secondary)', marginTop: '0.25rem' }}>
            Welcome back, {user?.email}
          </p>
        </div>
        <Button renderIcon={Add} onClick={() => navigate('/assessments/new')}>
          New Assessment
        </Button>
      </div>

      <Tile>
        <p style={{ color: 'var(--cds-text-secondary)' }}>
          Your assessments will appear here. Click "New Assessment" to get started.
        </p>
        <Button kind="ghost" onClick={() => navigate('/assessments')} style={{ marginTop: '1rem', paddingLeft: 0 }}>
          View my assessments
        </Button>
      </Tile>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()

  if (user?.role === 'admin') {
    return (
      <div>
        <h1>Dashboard</h1>
        <p style={{ color: 'var(--cds-text-secondary)', marginTop: '0.5rem' }}>
          Welcome back, {user.email}. Use the navigation to manage organizations.
        </p>
      </div>
    )
  }

  if (user?.role === 'org_manager') {
    return <ManagerDashboard />
  }

  return <UnderwriterDashboard />
}
