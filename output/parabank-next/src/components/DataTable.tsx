import type { ReactNode } from 'react';
import { Table, Typography, Button } from 'antd';
import type { TableColumnsType } from 'antd';

export interface Column {
  key: string;
  title: string;
}

export interface DataTableProps {
  columns: Column[];
  rows: Record<string, string>[];
  emptyText?: string;
  showTotal?: boolean;
  totalKey?: string;
  linkColumn?: string;
  onLinkClick?: (row: Record<string, string>) => void;
  linkTestId?: string;
  loading?: boolean;
}

function parseCurrency(value: string): number {
  if (!value) return 0;
  const cleaned = value.replace(/[$,]/g, '');
  const num = parseFloat(cleaned);
  return isNaN(num) ? 0 : num;
}

function formatCurrency(value: number): string {
  return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function DataTable(props: DataTableProps): ReactNode {
  const {
    columns,
    rows,
    emptyText = '조회된 데이터가 없습니다',
    showTotal = false,
    totalKey,
    linkColumn,
    onLinkClick,
    linkTestId,
    loading = false,
  } = props;

  const antdColumns: TableColumnsType<Record<string, string>> = columns.map((col) => ({
    key: col.key,
    dataIndex: col.key,
    title: col.title,
    render: (text: string, record: Record<string, string>, index: number) => {
      if (col.key === linkColumn) {
        const isFirst = index === 0;
        return (
          <Typography.Link
            onClick={() => onLinkClick?.(record)}
            data-testid={isFirst && linkTestId ? linkTestId : undefined}
            style={{ cursor: 'pointer' }}
          >
            {text}
          </Typography.Link>
        );
      }
      return text ?? '-';
    },
  }));

  const totalAmount =
    showTotal && totalKey
      ? rows.reduce((acc, row) => acc + parseCurrency(row[totalKey] ?? ''), 0)
      : 0;

  const summaryRow = (): ReactNode => {
    if (!showTotal) return null;

    return (
      <Table.Summary.Row style={{ fontWeight: 'bold', background: '#fafafa' }}>
        {columns.map((col, colIndex) => {
          if (colIndex === 0) {
            return (
              <Table.Summary.Cell key={col.key} index={colIndex}>
                합계
              </Table.Summary.Cell>
            );
          }
          if (col.key === totalKey) {
            return (
              <Table.Summary.Cell key={col.key} index={colIndex}>
                {formatCurrency(totalAmount)}
              </Table.Summary.Cell>
            );
          }
          return (
            <Table.Summary.Cell key={col.key} index={colIndex}>
              -
            </Table.Summary.Cell>
          );
        })}
      </Table.Summary.Row>
    );
  };

  return (
    <Table<Record<string, string>>
      columns={antdColumns}
      dataSource={rows}
      rowKey={(_, index) => String(index)}
      loading={loading}
      pagination={false}
      locale={{ emptyText }}
      summary={showTotal ? summaryRow : undefined}
      bordered
      size="middle"
    />
  );
}
