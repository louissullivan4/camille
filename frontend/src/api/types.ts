// TypeScript types mirroring the Pydantic schemas exactly.
// Keep in sync with backend/app/schemas/*.py

export type UserRole = 'admin' | 'org_manager' | 'org_underwriter'

export interface User {
  id: string
  email: string
  role: UserRole
  organization_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface InvitationInfoResponse {
  email: string
  role: UserRole
  org_name: string | null
  org_id: string | null
}

export type OrgTier = 'tier_1' | 'tier_2' | 'enterprise' | 'demo'

export interface Organization {
  id: string
  name: string
  slug: string
  tier: OrgTier
  is_demo: boolean
  org_metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface OrganizationUsage {
  org_id: string
  tier: OrgTier
  is_demo: boolean
  assessments_this_month: number
  monthly_limit: number | null
  estimated_cost_usd: number | null
}

export type AssessmentStatus = 'pending' | 'processing' | 'complete' | 'failed'
export type RiskTier = 'low' | 'medium' | 'high' | 'critical'

export interface DimensionScore {
  score: number
  max_score: number
  flags: Flag[]
}

export interface Flag {
  severity: 'critical' | 'warning' | 'info'
  text: string
}

export interface Assessment {
  id: string
  organization_id: string
  status: AssessmentStatus
  overall_score: number | null
  risk_tier: RiskTier | null
  dimension_scores: Record<string, DimensionScore> | null
  flags: Record<string, Flag[]> | null
  assessment_config: Record<string, unknown> | null
  report_url: string | null
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  assessment_id: string
  filename: string
  status: string
  doc_type: string | null
  classification_confidence: number | null
  created_at: string
}

export interface Invitation {
  id: string
  email: string
  role: UserRole
  organization_id: string | null
  token: string
  invited_by_id: string
  expires_at: string
  accepted_at: string | null
  created_at: string
}

export interface OrganizationAdminView extends Organization {
  user_count: number
}

export interface ApiError {
  detail: string
}
