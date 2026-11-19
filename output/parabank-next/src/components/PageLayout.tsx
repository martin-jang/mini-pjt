import type { ReactNode } from 'react'
import { Layout, Menu, Typography } from 'antd'
import { useNavigate } from 'react-router'

const { Sider, Content } = Layout

export interface MenuItem {
  path: string
  label: string
}

export interface PageLayoutProps {
  title: string
  testId?: string
  menu?: MenuItem[]
  children?: ReactNode
}

export function PageLayout(props: PageLayoutProps) {
  const { title, testId, menu = [], children } = props
  const navigate = useNavigate()

  const menuItems = menu.map((item) => ({
    key: item.path,
    label: item.label,
  }))

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  return (
    <Layout
      data-testid={testId}
      style={{ minHeight: '100vh' }}
    >
      <Sider
        width={220}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
        }}
      >
        <div
          style={{
            padding: '24px 16px 16px',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <Typography.Title level={4} style={{ margin: 0 }}>
            {title}
          </Typography.Title>
        </div>

        {menuItems.length > 0 && (
          <Menu
            mode="inline"
            items={menuItems}
            onClick={handleMenuClick}
            style={{ borderRight: 0, marginTop: 8 }}
          />
        )}

        {menuItems.length === 0 && (
          <div
            style={{
              padding: '16px',
              color: '#bfbfbf',
              fontSize: 13,
              textAlign: 'center',
            }}
          >
            메뉴가 없습니다.
          </div>
        )}
      </Sider>

      <Layout>
        <Content
          style={{
            padding: 24,
            background: '#fafafa',
            minHeight: '100vh',
          }}
        >
          {children ?? (
            <div style={{ color: '#bfbfbf', fontSize: 14 }}>
              콘텐츠가 없습니다.
            </div>
          )}
        </Content>
      </Layout>
    </Layout>
  )
}
