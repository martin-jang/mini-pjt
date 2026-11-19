// 템플릿 샘플 공통 컴포넌트. antd는 components/ 안에서만 import 합니다.
import type { ReactNode } from 'react'
import { Card, Typography } from 'antd'

export interface PageLayoutProps {
  title: string
  children?: ReactNode
}

export function PageLayout({ title, children }: PageLayoutProps) {
  return (
    <Card style={{ margin: 24 }}>
      <Typography.Title level={3}>{title}</Typography.Title>
      {children}
    </Card>
  )
}
