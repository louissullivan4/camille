import apiClient from './client'
import type { Organization, OrganizationAdminView } from './types'

export async function listAdminOrganizations(): Promise<OrganizationAdminView[]> {
  const res = await apiClient.get<OrganizationAdminView[]>('/admin/organizations')
  return res.data
}

export async function toggleOrgDemo(orgId: string): Promise<Organization> {
  const res = await apiClient.patch<Organization>(`/admin/organizations/${orgId}/demo`)
  return res.data
}

export async function getOrganization(orgId: string): Promise<Organization> {
  const res = await apiClient.get<Organization>(`/organizations/${orgId}`)
  return res.data
}

export async function getOrgUsage(orgId: string) {
  const res = await apiClient.get(`/organizations/${orgId}/usage`)
  return res.data
}
