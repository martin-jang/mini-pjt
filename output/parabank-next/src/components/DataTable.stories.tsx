import type { Meta, StoryObj } from '@storybook/react-vite';
import { DataTable } from './DataTable';

const meta: Meta<typeof DataTable> = {
  title: 'Common/DataTable',
  component: DataTable,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
};

export default meta;

type Story = StoryObj<typeof DataTable>;

const sampleColumns = [
  { key: 'id', title: '주문번호' },
  { key: 'product', title: '상품명' },
  { key: 'quantity', title: '수량' },
  { key: 'amount', title: '금액' },
  { key: 'status', title: '상태' },
];

const sampleRows = [
  { id: 'ORD-001', product: '노트북 Pro 15', quantity: '1', amount: '$1,200.00', status: '배송완료' },
  { id: 'ORD-002', product: '무선 마우스', quantity: '3', amount: '$89.99', status: '처리중' },
  { id: 'ORD-003', product: '기계식 키보드', quantity: '2', amount: '$345.50', status: '배송완료' },
  { id: 'ORD-004', product: 'USB-C 허브', quantity: '5', amount: '$199.95', status: '취소됨' },
  { id: 'ORD-005', product: '모니터 27인치', quantity: '1', amount: '$599.00', status: '배송중' },
];

// ─── 스토리 1: 기본 상태 (링크 컬럼 + 합계 행 포함) ───────────────────────────
export const Default: Story = {
  name: '기본 상태 (링크 + 합계 행)',
  args: {
    columns: sampleColumns,
    rows: sampleRows,
    showTotal: true,
    totalKey: 'amount',
    linkColumn: 'id',
    onLinkClick: () => {},
    linkTestId: 'order-link-first',
    loading: false,
    emptyText: '조회된 데이터가 없습니다',
  },
};

// ─── 스토리 2: 합계 행 없음 (기본 테이블) ────────────────────────────────────
export const WithoutTotal: Story = {
  name: '합계 행 없음',
  args: {
    columns: sampleColumns,
    rows: sampleRows,
    showTotal: false,
    linkColumn: 'id',
    onLinkClick: () => {},
    linkTestId: 'order-link-first',
    loading: false,
    emptyText: '조회된 데이터가 없습니다',
  },
};

// ─── 스토리 3: 빈 데이터 상태 ────────────────────────────────────────────────
export const Empty: Story = {
  name: '빈 데이터 상태',
  args: {
    columns: sampleColumns,
    rows: [],
    showTotal: false,
    loading: false,
    emptyText: '조회된 데이터가 없습니다',
  },
};

// ─── 스토리 4: 로딩 상태 ─────────────────────────────────────────────────────
export const Loading: Story = {
  name: '로딩 상태',
  args: {
    columns: sampleColumns,
    rows: [],
    showTotal: false,
    loading: true,
    emptyText: '조회된 데이터가 없습니다',
  },
};

// ─── 스토리 5: 링크 없는 단순 테이블 ─────────────────────────────────────────
export const NoLink: Story = {
  name: '링크 없는 단순 테이블',
  args: {
    columns: [
      { key: 'name', title: '이름' },
      { key: 'department', title: '부서' },
      { key: 'role', title: '직책' },
      { key: 'joinDate', title: '입사일' },
    ],
    rows: [
      { name: '김민준', department: '개발팀', role: '시니어 개발자', joinDate: '2020-03-15' },
      { name: '이서연', department: '디자인팀', role: 'UX 디자이너', joinDate: '2021-07-01' },
      { name: '박지호', department: '기획팀', role: '프로덕트 매니저', joinDate: '2019-11-20' },
      { name: '최수아', department: '개발팀', role: '주니어 개발자', joinDate: '2023-01-10' },
    ],
    showTotal: false,
    loading: false,
    emptyText: '조회된 데이터가 없습니다',
  },
};
