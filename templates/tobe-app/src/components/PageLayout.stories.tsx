import type { Meta, StoryObj } from '@storybook/react-vite'
import { PageLayout } from './PageLayout'

const meta: Meta<typeof PageLayout> = { title: 'Common/PageLayout', component: PageLayout }
export default meta
type Story = StoryObj<typeof PageLayout>

export const Default: Story = { args: { title: '기본', children: '내용' } }
export const Empty: Story = { args: { title: '빈 화면' } }
