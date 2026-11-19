import type { Meta, StoryObj } from '@storybook/react-vite';
import { FormSection } from './FormSection';

const meta: Meta<typeof FormSection> = {
  title: 'Common/FormSection',
  component: FormSection,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <div style={{ width: 480, padding: 24, background: '#fff', borderRadius: 8 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;

type Story = StoryObj<typeof FormSection>;

// ─── 스토리 1: 기본 상태 — 금액·계좌 입력 폼 (confirmStep 없음) ───────────────
export const 기본금액계좌입력: Story = {
  name: '기본 — 금액·계좌 입력',
  args: {
    fields: [
      {
        name: 'accountNumber',
        label: '계좌번호',
        type: 'text',
        required: true,
        testId: 'input-account-number',
      },
      {
        name: 'bankName',
        label: '은행',
        type: 'select',
        options: ['국민은행', '신한은행', '우리은행', '하나은행', '카카오뱅크'],
        required: true,
        testId: 'select-bank-name',
      },
      {
        name: 'amount',
        label: '이체 금액 (원)',
        type: 'text',
        required: true,
        testId: 'input-amount',
      },
      {
        name: 'memo',
        label: '메모',
        type: 'text',
        required: false,
        testId: 'input-memo',
      },
    ],
    submitLabel: '이체하기',
    submitTestId: 'btn-submit',
    confirmStep: false,
    loading: false,
    onSubmit: () => {},
  },
};

// ─── 스토리 2: 변형 — 제출 전 확인 단계 (confirmStep=true) ───────────────────
export const 확인단계포함이체: Story = {
  name: '변형 — 제출 전 확인 단계',
  args: {
    fields: [
      {
        name: 'accountNumber',
        label: '계좌번호',
        type: 'text',
        required: true,
        testId: 'input-account-number',
      },
      {
        name: 'bankName',
        label: '은행',
        type: 'select',
        options: ['국민은행', '신한은행', '우리은행', '하나은행', '카카오뱅크'],
        required: true,
        testId: 'select-bank-name',
      },
      {
        name: 'amount',
        label: '이체 금액 (원)',
        type: 'text',
        required: true,
        testId: 'input-amount',
      },
      {
        name: 'password',
        label: '출금 비밀번호',
        type: 'password',
        required: true,
        testId: 'input-password',
      },
    ],
    submitLabel: '이체 신청',
    submitTestId: 'btn-submit-confirm',
    confirmStep: true,
    loading: false,
    onSubmit: () => {},
  },
};

// ─── 스토리 3: 오류 메시지 표시 상태 ─────────────────────────────────────────
export const 오류메시지표시: Story = {
  name: '오류 — 서버 오류 메시지 표시',
  args: {
    fields: [
      {
        name: 'accountNumber',
        label: '계좌번호',
        type: 'text',
        required: true,
        testId: 'input-account-number',
      },
      {
        name: 'amount',
        label: '이체 금액 (원)',
        type: 'text',
        required: true,
        testId: 'input-amount',
      },
    ],
    submitLabel: '이체하기',
    submitTestId: 'btn-submit-error',
    confirmStep: false,
    loading: false,
    error: '잔액이 부족합니다. 이체 금액을 확인해 주세요.',
    onSubmit: () => {},
  },
};

// ─── 스토리 4: 로딩 상태 ──────────────────────────────────────────────────────
export const 로딩중: Story = {
  name: '로딩 — 제출 처리 중',
  args: {
    fields: [
      {
        name: 'accountNumber',
        label: '계좌번호',
        type: 'text',
        required: true,
        testId: 'input-account-number',
      },
      {
        name: 'amount',
        label: '이체 금액 (원)',
        type: 'text',
        required: true,
        testId: 'input-amount',
      },
    ],
    submitLabel: '이체하기',
    submitTestId: 'btn-submit-loading',
    confirmStep: false,
    loading: true,
    onSubmit: () => {},
  },
};
