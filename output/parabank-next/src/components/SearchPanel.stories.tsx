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

/** 기본 상태: 기간·유형 선택 + 키워드 검색 */
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
        name: 'type',
        label: '유형',
        type: 'select',
        options: ['전체', '입금', '출금', '이체'],
        testId: 'select-type',
      },
      {
        name: 'keyword',
        label: '키워드',
        type: 'text',
        testId: 'input-keyword',
      },
    ],
    searchLabel: '조회',
    searchTestId: 'btn-search',
    onSearch: () => {},
  },
};

/** 변형: 로그인 폼 스타일 — 아이디·비밀번호 + 권한 선택 */
export const LoginStyleVariant: Story = {
  args: {
    fields: [
      {
        name: 'userId',
        label: '아이디',
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
        options: ['전체', '관리자', '일반사용자', '게스트'],
        testId: 'select-role',
      },
    ],
    searchLabel: '검색',
    searchTestId: 'btn-login-search',
    onSearch: () => {},
  },
};

/** 빈 상태: 필드 없이 검색 버튼만 표시 */
export const EmptyFields: Story = {
  args: {
    fields: [],
    searchLabel: '전체 조회',
    searchTestId: 'btn-empty-search',
    onSearch: () => {},
  },
};
