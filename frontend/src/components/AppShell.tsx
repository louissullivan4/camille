import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  SideNav,
  SideNavItems,
  SideNavLink,
  SideNavMenu,
  SideNavMenuItem,
  Header,
  HeaderName,
  HeaderGlobalBar,
  HeaderGlobalAction,
  Content,
} from '@carbon/react'
import { Dashboard, UserAdmin, Settings, Logout, Report, Group, Money } from '@carbon/icons-react'
import { useAuth } from '../contexts/AuthContext'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const isActive = (path: string) => location.pathname.startsWith(path)

  return (
    <>
      <Header aria-label="Camille">
        <HeaderName prefix="Camille" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }}>
          Risk Assessment
        </HeaderName>
        <HeaderGlobalBar>
          <HeaderGlobalAction aria-label="Sign out" tooltipAlignment="end" onClick={logout}>
            <Logout size={20} />
          </HeaderGlobalAction>
        </HeaderGlobalBar>
      </Header>

      <SideNav
        aria-label="Side navigation"
        expanded
        isPersistent
        style={{ marginTop: '3rem' }}
      >
        <SideNavItems>
          {/* Admin nav */}
          {user?.role === 'admin' && (
            <>
              <SideNavLink
                renderIcon={Dashboard}
                onClick={() => navigate('/admin')}
                isActive={location.pathname === '/admin'}
              >
                Admin Dashboard
              </SideNavLink>
              <SideNavMenu renderIcon={UserAdmin} title="Organizations" defaultExpanded>
                <SideNavMenuItem
                  onClick={() => navigate('/admin/organizations')}
                  isActive={isActive('/admin/organizations')}
                >
                  All Organizations
                </SideNavMenuItem>
                <SideNavMenuItem
                  onClick={() => navigate('/admin/organizations/invite')}
                  isActive={isActive('/admin/organizations/invite')}
                >
                  Invite Org Manager
                </SideNavMenuItem>
              </SideNavMenu>
            </>
          )}

          {/* Org manager + underwriter nav */}
          {user?.role !== 'admin' && (
            <>
              <SideNavLink
                renderIcon={Dashboard}
                onClick={() => navigate('/dashboard')}
                isActive={location.pathname === '/dashboard'}
              >
                Dashboard
              </SideNavLink>
              <SideNavLink
                renderIcon={Report}
                onClick={() => navigate('/assessments')}
                isActive={isActive('/assessments')}
              >
                Assessments
              </SideNavLink>
              {user?.role === 'org_manager' && (
                <>
                  <SideNavLink
                    renderIcon={Group}
                    onClick={() => navigate('/team')}
                    isActive={isActive('/team')}
                  >
                    Team
                  </SideNavLink>
                  <SideNavLink
                    renderIcon={Money}
                    onClick={() => navigate('/billing')}
                    isActive={isActive('/billing')}
                  >
                    Billing
                  </SideNavLink>
                </>
              )}
              <SideNavLink
                renderIcon={Settings}
                onClick={() => navigate('/settings')}
                isActive={isActive('/settings')}
              >
                Settings
              </SideNavLink>
            </>
          )}
        </SideNavItems>
      </SideNav>

      <Content style={{ marginLeft: '16rem', marginTop: '3rem', padding: '2rem' }}>
        {children}
      </Content>
    </>
  )
}
