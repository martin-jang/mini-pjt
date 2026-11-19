import type { ReactNode } from 'react';
import { Result, Descriptions } from 'antd';

export interface ResultPanelProps {
  status: 'success' | 'error';
  title: string;
  message?: string;
  items?: { label: string; value: string }[];
  testId?: string;
}

export function ResultPanel(props: ResultPanelProps): ReactNode {
  const { status, title, message, items, testId } = props;

  const extra: ReactNode =
    items && items.length > 0 ? (
      <Descriptions
        bordered
        column={1}
        size="small"
        style={{ marginTop: 24, textAlign: 'left', maxWidth: 480, margin: '24px auto 0' }}
      >
        {items.map((item) => (
          <Descriptions.Item key={item.label} label={item.label}>
            {item.value}
          </Descriptions.Item>
        ))}
      </Descriptions>
    ) : null;

  return (
    <div data-testid={testId}>
      <Result
        status={status}
        title={title}
        subTitle={message}
        extra={extra}
      />
    </div>
  );
}
