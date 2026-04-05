import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DataTable,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  Button,
  Tag,
  Toggle,
  InlineNotification,
  DataTableSkeleton,
} from '@carbon/react'
import { Add } from '@carbon/icons-react'
import { useNavigate } from 'react-router-dom'
import { listAdminOrganizations, toggleOrgDemo } from '../../api/organizations'
import type { OrganizationAdminView } from '../../api/types'

const TIER_LABELS: Record<string, string> = {
  tier_1: 'Starter',
  tier_2: 'Professional',
  enterprise: 'Enterprise',
  demo: 'Demo',
}

const TIER_TAG_TYPE: Record<string, 'gray' | 'blue' | 'purple' | 'green'> = {
  tier_1: 'gray',
  tier_2: 'blue',
  enterprise: 'purple',
  demo: 'green',
}

const headers = [
  { key: 'name', header: 'Organization' },
  { key: 'tier', header: 'Tier' },
  { key: 'user_count', header: 'Users' },
  { key: 'is_demo', header: 'Demo' },
  { key: 'created_at', header: 'Created' },
]

export default function OrganizationList() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const { data: orgs, isLoading } = useQuery({
    queryKey: ['admin', 'organizations'],
    queryFn: listAdminOrganizations,
  })

  const toggleMutation = useMutation({
    mutationFn: (orgId: string) => toggleOrgDemo(orgId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'organizations'] })
      setErrorMsg(null)
    },
    onError: () => setErrorMsg('Failed to toggle demo status. Please try again.'),
  })

  const filtered: OrganizationAdminView[] = (orgs ?? []).filter(
    (o) =>
      !search ||
      o.name.toLowerCase().includes(search.toLowerCase()) ||
      o.slug.toLowerCase().includes(search.toLowerCase()),
  )

  const rows = filtered.map((o) => ({
    id: o.id,
    name: o.name,
    slug: o.slug,
    tier: o.tier,
    user_count: o.user_count,
    is_demo: o.is_demo,
    created_at: new Date(o.created_at).toLocaleDateString(),
    _raw: o,
  }))

  if (isLoading) {
    return <DataTableSkeleton headers={headers} rowCount={8} />
  }

  return (
    <div>
      <h1 style={{ marginBottom: '1.5rem' }}>Organizations</h1>

      {errorMsg && (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={errorMsg}
          onCloseButtonClick={() => setErrorMsg(null)}
          style={{ marginBottom: '1rem' }}
        />
      )}

      <DataTable rows={rows} headers={headers}>
        {({ rows: tableRows, headers: tableHeaders, getTableProps, getHeaderProps, getRowProps, getToolbarProps }) => (
          <TableContainer>
            <TableToolbar {...getToolbarProps()}>
              <TableToolbarContent>
                <TableToolbarSearch
                  placeholder="Search organizations..."
                  onChange={(_e, value) => setSearch(value ?? '')}
                  value={search}
                />
                <Button renderIcon={Add} onClick={() => navigate('/admin/organizations/invite')}>
                  Invite Org Manager
                </Button>
              </TableToolbarContent>
            </TableToolbar>
            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
                  {tableHeaders.map((header) => (
                    <TableHeader {...getHeaderProps({ header })} key={header.key}>
                      {header.header}
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {tableRows.map((row) => {
                  const org = filtered.find((o) => o.id === row.id)
                  return (
                    <TableRow {...getRowProps({ row })} key={row.id}>
                      <TableCell>
                        <div>
                          <strong>{row.cells[0].value}</strong>
                          <div style={{ color: 'var(--cds-text-secondary)', fontSize: '0.75rem' }}>
                            {org?.slug}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Tag type={TIER_TAG_TYPE[row.cells[1].value] ?? 'gray'}>
                          {TIER_LABELS[row.cells[1].value] ?? row.cells[1].value}
                        </Tag>
                      </TableCell>
                      <TableCell>{row.cells[2].value}</TableCell>
                      <TableCell>
                        <Toggle
                          id={`demo-toggle-${row.id}`}
                          size="sm"
                          toggled={row.cells[3].value as boolean}
                          onToggle={() => toggleMutation.mutate(row.id as string)}
                          labelA="No"
                          labelB="Yes"
                          hideLabel
                        />
                      </TableCell>
                      <TableCell>{row.cells[4].value}</TableCell>
                    </TableRow>
                  )
                })}
                {tableRows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <p style={{ color: 'var(--cds-text-secondary)', padding: '1rem 0' }}>
                        No organizations found.
                      </p>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>
    </div>
  )
}
