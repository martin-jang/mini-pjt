import { Form, Input, Select, Button } from 'antd';
import type { ReactNode } from 'react';

export interface FieldSpec {
  name: string;
  label: string;
  type: 'text' | 'password' | 'select';
  options?: string[];
  required?: boolean;
  testId?: string;
}

export interface SearchPanelProps {
  fields: FieldSpec[];
  searchLabel?: string;
  onSearch: (values: Record<string, string>) => void;
  searchTestId?: string;
}

export function SearchPanel(props: SearchPanelProps): ReactNode {
  const { fields, searchLabel = '조회', onSearch, searchTestId } = props;
  const [form] = Form.useForm<Record<string, string>>();

  const handleFinish = (values: Record<string, string>) => {
    onSearch(values);
  };

  const renderField = (field: FieldSpec): ReactNode => {
    if (field.type === 'select') {
      return (
        <Select
          data-testid={field.testId}
          placeholder={`${field.label} 선택`}
          style={{ minWidth: 160 }}
          allowClear
        >
          {(field.options ?? []).map((opt) => (
            <Select.Option key={opt} value={opt}>
              {opt}
            </Select.Option>
          ))}
        </Select>
      );
    }

    if (field.type === 'password') {
      return (
        <Input.Password
          data-testid={field.testId}
          placeholder={`${field.label} 입력`}
        />
      );
    }

    return (
      <Input
        data-testid={field.testId}
        placeholder={`${field.label} 입력`}
      />
    );
  };

  return (
    <div
      style={{
        background: '#fafafa',
        border: '1px solid #d9d9d9',
        borderRadius: 8,
        padding: '16px 24px',
        marginBottom: 16,
      }}
    >
      <Form
        form={form}
        layout="inline"
        onFinish={handleFinish}
        style={{ rowGap: 8 }}
      >
        {fields.map((field) => (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={
              field.required
                ? [{ required: true, message: `${field.label}을(를) 입력하세요.` }]
                : []
            }
          >
            {renderField(field)}
          </Form.Item>
        ))}

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            data-testid={searchTestId}
          >
            {searchLabel}
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
}
