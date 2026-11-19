import type { Meta, StoryObj } from '@storybook/react-vite';
import { ResultPanel } from './ResultPanel';

const meta: Meta<typeof ResultPanel> = {
  title: 'Common/ResultPanel',
  component: ResultPanel,
  tags: ['autodocs'],
  argTypes: {
    status: {
      control: 'radio',
      options: ['success', 'error'],
      description: '처리 결과 상태',
    },
    title: {
      control: 'text',
      description: '결과 제목',
    },
    message: {
      control: 'text',
      description: '부가 설명 메시지',
    },
    testId: {
      control: 'text',
      description: 'data-testid 속성값',
    },
  },
};

export default meta;

type Story = StoryObj<typeof ResultPanel>;

/** ✅ 제출 성공 — items 요약 포함 */
export const 제출성공: Story = {
  args: {
    status: 'success',
    title: '제출이 완료되었습니다.',
    message: '입력하신 정보가 성공적으로 처리되었습니다. 담당자가 확인 후 연락드리겠습니다.',
    items: [
      { label: '신청자 이름', value: '홍길동' },
      { label: '신청 일시', value: '2025-07-10 14:32:00' },
      { label: '처리 번호', value: 'REQ-20250710-0042' },
      { label: '처리 상태', value: '접수 완료' },
    ],
    testId: 'result-panel-success',
  },
};

/** ❌ 제출 실패 — items 없음 (최소 상태) */
export const 제출실패_최소: Story = {
  args: {
    status: 'error',
    title: '제출에 실패하였습니다.',
    message: '일시적인 오류가 발생하였습니다. 잠시 후 다시 시도해 주세요.',
    testId: 'result-panel-error',
  },
};

/** ❌ 제출 실패 — items 요약 포함 */
export const 제출실패_상세: Story = {
  args: {
    status: 'error',
    title: '처리 중 오류가 발생하였습니다.',
    message: '아래 항목을 확인하고 다시 제출해 주세요.',
    items: [
      { label: '오류 코드', value: 'ERR-4022' },
      { label: '오류 항목', value: '주민등록번호 형식 오류' },
      { label: '발생 일시', value: '2025-07-10 15:01:44' },
    ],
    testId: 'result-panel-error-detail',
  },
};

/** ✅ 제출 성공 — message·items 모두 없음 (타이틀만) */
export const 제출성공_타이틀만: Story = {
  args: {
    status: 'success',
    title: '처리가 완료되었습니다.',
    testId: 'result-panel-success-minimal',
  },
};
