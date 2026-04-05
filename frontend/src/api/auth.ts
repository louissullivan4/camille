import client from './client'
import type {
  InvitationInfoResponse,
  TokenResponse,
} from './types'

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/auth/login', { email, password })
  return data
}

export async function requestPasswordReset(email: string): Promise<void> {
  await client.post('/auth/password-reset/request', { email })
}

export async function confirmPasswordReset(
  email: string,
  code: string,
  newPassword: string
): Promise<void> {
  await client.post('/auth/password-reset/confirm', {
    email,
    code,
    new_password: newPassword,
  })
}

export async function getInvitationInfo(token: string): Promise<InvitationInfoResponse> {
  const { data } = await client.get<InvitationInfoResponse>('/auth/invitation-info', {
    params: { token },
  })
  return data
}

export interface SignupOrgPayload {
  name: string
  slug: string
  tier: string
  industry?: string
}

export interface SignupPayload {
  token: string
  password: string
  first_name?: string
  last_name?: string
  org?: SignupOrgPayload
}

export async function signup(payload: SignupPayload): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/auth/signup', payload)
  return data
}

export async function getMe() {
  const { data } = await client.get('/auth/me')
  return data
}
