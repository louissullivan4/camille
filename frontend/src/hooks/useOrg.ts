import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../contexts/AuthContext'
import { getOrganization, getOrgUsage } from '../api/organizations'
import type { Organization, OrganizationUsage } from '../api/types'

export function useOrg() {
  const { user } = useAuth()
  const orgId = user?.organization_id ?? null

  const orgQuery = useQuery<Organization>({
    queryKey: ['organization', orgId],
    queryFn: () => getOrganization(orgId!),
    enabled: !!orgId,
  })

  const usageQuery = useQuery<OrganizationUsage>({
    queryKey: ['organization', orgId, 'usage'],
    queryFn: () => getOrgUsage(orgId!),
    enabled: !!orgId,
  })

  return {
    org: orgQuery.data ?? null,
    usage: usageQuery.data ?? null,
    isLoading: orgQuery.isLoading || usageQuery.isLoading,
  }
}
