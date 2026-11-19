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

/** ✅ 제출 성공 — 요약 항목 포함 */
export const 제출성공: Story = {
  args: {
    status: 'success',
    title: '제출이 완료되었습니다.',
    message: '입력하신 내용이 정상적으로 처리되었습니다. 담당자가 검토 후 연락드리겠습니다.',
    items: [
      { label: '신청자명', value: '홍길동' },
      { label: '신청 유형', value: '정기 점검 요청' },
      { label: '접수 번호', value: 'REQ-20240601-0042' },
      { label: '처리 일시', value: '2024-06-01 14:32:10' },
    ],
    testId: 'result-panel-success',
  },
};

/** ❌ 제출 실패 — 메시지·항목 없는 최소 상태 */
export const 제출실패_최소: Story = {
  args: {
    status: 'error',
    title: '제출에 실패하였습니다.',
    message: '일시적인 오류가 발생하였습니다. 잠시 후 다시 시도해 주세요.',
    testId: 'result-panel-error',
  },
};

/** ❌ 제출 실패 — 오류 항목 요약 포함 */
export const 제출실패_항목포함: Story = {
  args: {
    status: 'error',
    title: '처리 중 오류가 발생하였습니다.',
    message: '아래 항목을 확인한 후 다시 시도해 주세요.',
    items: [
      { label: '오류 코드', value: 'ERR-5023' },
      { label: '오류 항목', value: '첨부 파일 형식 불일치' },
      { label: '발생 일시', value: '2024-06-01 15:10:05' },
    ],
    testId: 'result-panel-error-detail',
  },
};

/** ✅ 제출 성공 — message·items 없는 최소 상태 */
export const 제출성공_최소: Story = {
  args: {
    status: 'success',
    title: '처리가 완료되었습니다.',
    testId: 'result-panel-success-minimal',
  },
};
