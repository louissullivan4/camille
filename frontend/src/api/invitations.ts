import apiClient from './client'
import type { Invitation } from './types'

export interface InviteManagerPayload {
  email: string
  org_name?: string
  org_slug?: string
  organization_id?: string
}

export async function inviteOrgManager(payload: InviteManagerPayload): Promise<Invitation> {
  const res = await apiClient.post<Invitation>('/invitations/manager', payload)
  return res.data
}

export async function inviteUnderwriter(email: string): Promise<Invitation> {
  const res = await apiClient.post<Invitation>('/invitations/underwriter', { email })
  return res.data
}
