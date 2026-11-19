import type { Meta, StoryObj } from '@storybook/react-vite'
import { MemoryRouter } from 'react-router'
import { PageLayout } from './PageLayout'

const meta: Meta<typeof PageLayout> = {
  title: 'Common/PageLayout',
  component: PageLayout,
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={['/']}>
        <Story />
      </MemoryRouter>
    ),
  ],
  parameters: {
    layout: 'fullscreen',
  },
}

export default meta

type Story = StoryObj<typeof PageLayout>

/** 기본 상태: 제목·메뉴·콘텐츠가 모두 있는 일반적인 화면 */
export const 기본상태: Story = {
  args: {
    title: '관리자 화면',
    testId: 'page-layout-default',
    menu: [
      { path: '/dashboard', label: '대시보드' },
      { path: '/users', label: '사용자 관리' },
      { path: '/settings', label: '설정' },
      { path: '/reports', label: '보고서' },
    ],
    children: (
      <div>
        <h2 style={{ marginTop: 0 }}>대시보드</h2>
        <p>여기에 메인 콘텐츠가 표시됩니다.</p>
        <p>좌측 메뉴를 클릭하면 해당 경로로 이동합니다.</p>
      </div>
    ),
  },
}

/** 빈 상태: 메뉴와 콘텐츠가 없는 최소 구성 화면 */
export const 빈상태: Story = {
  args: {
    title: '빈 화면',
    testId: 'page-layout-empty',
    menu: [],
    children: undefined,
  },
}

/** 메뉴만 있고 콘텐츠가 없는 상태 */
export const 메뉴만있는상태: Story = {
  args: {
    title: '메뉴 전용 화면',
    testId: 'page-layout-menu-only',
    menu: [
      { path: '/home', label: '홈' },
      { path: '/profile', label: '내 프로필' },
      { path: '/notifications', label: '알림' },
    ],
    children: undefined,
  },
}
