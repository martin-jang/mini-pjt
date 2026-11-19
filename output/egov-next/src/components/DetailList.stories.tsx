import type { Meta, StoryObj } from '@storybook/react-vite';
import { DetailList } from './DetailList';

const meta: Meta<typeof DetailList> = {
  title: 'Common/DetailList',
  component: DetailList,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
};

export default meta;

type Story = StoryObj<typeof DetailList>;

export const 기본상태: Story = {
  args: {
    title: '사용자 상세 정보',
    items: [
      { label: '이름', value: '홍길동' },
      { label: '이메일', value: 'hong@example.com' },
      { label: '전화번호', value: '010-1234-5678' },
      { label: '부서', value: '개발팀' },
      { label: '직급', value: '선임 개발자' },
      { label: '입사일', value: '2021-03-15' },
    ],
  },
};

export const 제목없음: Story = {
  args: {
    items: [
      { label: '주문번호', value: 'ORD-20240101-001' },
      { label: '주문일시', value: '2024-01-01 10:30:00' },
      { label: '상품명', value: '노트북 프로 15인치' },
      { label: '수량', value: '2개' },
      { label: '결제금액', value: '3,200,000원' },
      { label: '결제수단', value: '신용카드' },
      { label: '배송지', value: '서울특별시 강남구 테헤란로 123' },
      { label: '배송상태', value: '배송 중' },
    ],
  },
};

export const 홀수항목: Story = {
  args: {
    title: '프로젝트 정보',
    items: [
      { label: '프로젝트명', value: '차세대 시스템 구축' },
      { label: '프로젝트 코드', value: 'PRJ-2024-007' },
      { label: '시작일', value: '2024-01-01' },
      { label: '종료일', value: '2024-12-31' },
      { label: '담당자', value: '김철수' },
    ],
  },
};

export const 빈상태: Story = {
  args: {
    title: '빈 목록 (렌더링 안 됨)',
    items: [],
  },
};
