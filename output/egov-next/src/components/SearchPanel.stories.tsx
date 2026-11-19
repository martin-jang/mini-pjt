import type { Meta, StoryObj } from '@storybook/react-vite';
import { SearchPanel } from './SearchPanel';

const meta: Meta<typeof SearchPanel> = {
  title: 'Common/SearchPanel',
  component: SearchPanel,
  parameters: {
    layout: 'padded',
  },
};

export default meta;

type Story = StoryObj<typeof SearchPanel>;

/** 기본 상태: 텍스트·셀렉트 필드 조합 */
export const Default: Story = {
  args: {
    fields: [
      {
        name: 'startDate',
        label: '시작일',
        type: 'text',
        required: true,
        testId: 'input-start-date',
      },
      {
        name: 'endDate',
        label: '종료일',
        type: 'text',
        required: true,
        testId: 'input-end-date',
      },
      {
        name: 'category',
        label: '유형',
        type: 'select',
        options: ['전체', '입금', '출금', '이체'],
        testId: 'select-category',
      },
    ],
    searchLabel: '조회',
    searchTestId: 'btn-search',
    onSearch: () => {},
  },
};

/** 변형 상태: 비밀번호 필드 포함 + 커스텀 버튼 라벨 */
export const WithPasswordAndCustomLabel: Story = {
  args: {
    fields: [
      {
        name: 'userId',
        label: '사용자 ID',
        type: 'text',
        required: true,
        testId: 'input-user-id',
      },
      {
        name: 'password',
        label: '비밀번호',
        type: 'password',
        required: true,
        testId: 'input-password',
      },
      {
        name: 'role',
        label: '권한',
        type: 'select',
        options: ['관리자', '일반 사용자', '게스트'],
        testId: 'select-role',
      },
    ],
    searchLabel: '검색',
    searchTestId: 'btn-custom-search',
    onSearch: () => {},
  },
};

/** 빈 상태: 필드 없이 버튼만 표시 */
export const EmptyFields: Story = {
  args: {
    fields: [],
    searchLabel: '조회',
    searchTestId: 'btn-empty-search',
    onSearch: () => {},
  },
};
