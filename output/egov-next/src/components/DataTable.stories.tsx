import type { Meta, StoryObj } from '@storybook/react-vite';
import { DataTable } from './DataTable';

const meta: Meta<typeof DataTable> = {
  title: 'Common/DataTable',
  component: DataTable,
  tags: ['autodocs'],
};

export default meta;

type Story = StoryObj<typeof DataTable>;

const sampleColumns = [
  { key: 'accountNo', title: '계좌번호' },
  { key: 'owner', title: '예금주' },
  { key: 'bank', title: '은행' },
  { key: 'amount', title: '거래금액' },
  { key: 'date', title: '거래일자' },
];

const sampleRows = [
  { accountNo: '110-123-456789', owner: '홍길동', bank: '신한은행', amount: '$1,200.00', date: '2024-06-01' },
  { accountNo: '220-987-654321', owner: '김철수', bank: '국민은행', amount: '$3,450.75', date: '2024-06-02' },
  { accountNo: '330-111-222333', owner: '이영희', bank: '우리은행', amount: '$800.25', date: '2024-06-03' },
  { accountNo: '440-444-555666', owner: '박민준', bank: '하나은행', amount: '$2,100.00', date: '2024-06-04' },
];

// 스토리 1: 기본 상태 — 링크 컬럼 + 합계 행 포함
export const WithTotalRow: Story = {
  name: '기본 상태 (합계 행 포함)',
  args: {
    columns: sampleColumns,
    rows: sampleRows,
    showTotal: true,
    totalKey: 'amount',
    linkColumn: 'accountNo',
    onLinkClick: () => {},
    linkTestId: 'account-link-first',
    loading: false,
    emptyText: '조회된 데이터가 없습니다',
  },
};

// 스토리 2: 합계 행 없는 변형
export const WithoutTotalRow: Story = {
  name: '변형 — 합계 행 없음',
  args: {
    columns: sampleColumns,
    rows: sampleRows,
    showTotal: false,
    linkColumn: 'accountNo',
    onLinkClick: () => {},
    linkTestId: 'account-link-first',
    loading: false,
    emptyText: '조회된 데이터가 없습니다',
  },
};

// 스토리 3: 빈 상태
export const EmptyState: Story = {
  name: '빈 상태 (데이터 없음)',
  args: {
    columns: sampleColumns,
    rows: [],
    showTotal: false,
    loading: false,
    emptyText: '조회된 데이터가 없습니다',
  },
};

// 스토리 4: 로딩 상태
export const LoadingState: Story = {
  name: '로딩 상태',
  args: {
    columns: sampleColumns,
    rows: [],
    loading: true,
    emptyText: '조회된 데이터가 없습니다',
  },
};
