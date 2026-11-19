import type { ReactNode } from 'react';
import { Descriptions, Typography } from 'antd';

export interface DetailItem {
  label: string;
  value: string;
}

export interface DetailListProps {
  items: DetailItem[];
  title?: string;
}

export function DetailList(props: DetailListProps): ReactNode {
  const { items, title } = props;

  if (!items || items.length === 0) {
    return null;
  }

  const descriptionsItems = items.map((item, index) => ({
    key: index,
    label: item.label,
    children: item.value,
  }));

  return (
    <div>
      {title && (
        <Typography.Title level={5} style={{ marginBottom: 12 }}>
          {title}
        </Typography.Title>
      )}
      <Descriptions
        bordered
        column={2}
        items={descriptionsItems}
      />
    </div>
  );
}
