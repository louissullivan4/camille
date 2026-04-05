import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Grid,
  Column,
  Tile,
  Button,
  SkeletonText,
  Tag,
} from '@carbon/react'
import { ArrowRight } from '@carbon/icons-react'
import { listAdminOrganizations } from '../../api/organizations'

export default function AdminDashboard() {
  const navigate = useNavigate()
  const { data: orgs, isLoading } = useQuery({
    queryKey: ['admin', 'organizations'],
    queryFn: listAdminOrganizations,
  })

  const totalOrgs = orgs?.length ?? 0
  const totalUsers = orgs?.reduce((sum, o) => sum + o.user_count, 0) ?? 0
  const demoOrgs = orgs?.filter((o) => o.is_demo).length ?? 0

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem' }}>Admin Dashboard</h1>

      <Grid>
        <Column lg={4} md={4} sm={4}>
          <Tile style={{ height: '100%' }}>
            <p style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>Total Organizations</p>
            {isLoading ? (
              <SkeletonText width="40%" />
            ) : (
              <p style={{ fontSize: '2rem', fontWeight: 600, margin: '0.5rem 0' }}>{totalOrgs}</p>
            )}
          </Tile>
        </Column>

        <Column lg={4} md={4} sm={4}>
          <Tile style={{ height: '100%' }}>
            <p style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>Total Users</p>
            {isLoading ? (
              <SkeletonText width="40%" />
            ) : (
              <p style={{ fontSize: '2rem', fontWeight: 600, margin: '0.5rem 0' }}>{totalUsers}</p>
            )}
          </Tile>
        </Column>

        <Column lg={4} md={4} sm={4}>
          <Tile style={{ height: '100%' }}>
            <p style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>Demo Accounts</p>
            {isLoading ? (
              <SkeletonText width="40%" />
            ) : (
              <p style={{ fontSize: '2rem', fontWeight: 600, margin: '0.5rem 0' }}>{demoOrgs}</p>
            )}
          </Tile>
        </Column>
      </Grid>

      <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem' }}>
        <Button renderIcon={ArrowRight} onClick={() => navigate('/admin/organizations')}>
          Manage Organizations
        </Button>
        <Button kind="secondary" renderIcon={ArrowRight} onClick={() => navigate('/admin/organizations/invite')}>
          Invite Org Manager
        </Button>
      </div>

      {orgs && orgs.length > 0 && (
        <div style={{ marginTop: '2rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Recent Organizations</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {orgs.slice(0, 5).map((org) => (
              <Tile
                key={org.id}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                onClick={() => navigate('/admin/organizations')}
              >
                <div>
                  <strong>{org.name}</strong>
                  <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem', marginLeft: '0.5rem' }}>
                    {org.slug}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Tag type="blue">{org.tier}</Tag>
                  {org.is_demo && <Tag type="purple">Demo</Tag>}
                  <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.875rem' }}>
                    {org.user_count} user{org.user_count !== 1 ? 's' : ''}
                  </span>
                </div>
              </Tile>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
