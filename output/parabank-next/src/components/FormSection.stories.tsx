import type { Meta, StoryObj } from '@storybook/react-vite';
import { FormSection } from './FormSection';

const meta: Meta<typeof FormSection> = {
  title: 'Common/FormSection',
  component: FormSection,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;

type Story = StoryObj<typeof FormSection>;

// ─── 스토리 1: 기본 상태 (텍스트 + 선택 필드, confirmStep 없음) ───────────────
export const Default: Story = {
  name: '기본 상태',
  args: {
    fields: [
      {
        name: 'username',
        label: '사용자 이름',
        type: 'text',
        required: true,
        testId: 'input-username',
      },
      {
        name: 'email',
        label: '이메일',
        type: 'text',
        required: true,
        testId: 'input-email',
      },
      {
        name: 'role',
        label: '역할',
        type: 'select',
        options: ['관리자', '편집자', '뷰어'],
        required: true,
        testId: 'select-role',
      },
    ],
    submitLabel: '등록',
    submitTestId: 'btn-submit',
    confirmStep: false,
    loading: false,
    onSubmit: () => {},
  },
};

// ─── 스토리 2: 확인 단계 변형 (confirmStep=true, 비밀번호 포함) ────────────────
export const WithConfirmStep: Story = {
  name: '확인 단계 변형',
  args: {
    fields: [
      {
        name: 'userId',
        label: '아이디',
        type: 'text',
        required: true,
        testId: 'input-userId',
      },
      {
        name: 'password',
        label: '비밀번호',
        type: 'password',
        required: true,
        testId: 'input-password',
      },
      {
        name: 'department',
        label: '부서',
        type: 'select',
        options: ['개발팀', '디자인팀', '기획팀', '마케팅팀'],
        required: false,
        testId: 'select-department',
      },
    ],
    submitLabel: '계정 생성',
    submitTestId: 'btn-create-account',
    confirmStep: true,
    loading: false,
    onSubmit: () => {},
  },
};

// ─── 스토리 3: 오류 메시지 표시 상태 ─────────────────────────────────────────
export const WithError: Story = {
  name: '오류 메시지 상태',
  args: {
    fields: [
      {
        name: 'productName',
        label: '상품명',
        type: 'text',
        required: true,
        testId: 'input-productName',
      },
      {
        name: 'category',
        label: '카테고리',
        type: 'select',
        options: ['전자기기', '의류', '식품', '도서'],
        required: true,
        testId: 'select-category',
      },
    ],
    submitLabel: '상품 등록',
    submitTestId: 'btn-register-product',
    confirmStep: false,
    loading: false,
    error: '서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
    onSubmit: () => {},
  },
};

// ─── 스토리 4: 로딩 상태 ──────────────────────────────────────────────────────
export const LoadingState: Story = {
  name: '로딩 상태',
  args: {
    fields: [
      {
        name: 'title',
        label: '제목',
        type: 'text',
        required: true,
        testId: 'input-title',
      },
      {
        name: 'content',
        label: '내용',
        type: 'text',
        required: false,
        testId: 'input-content',
      },
    ],
    submitLabel: '저장',
    submitTestId: 'btn-save',
    confirmStep: false,
    loading: true,
    onSubmit: () => {},
  },
};
