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

  return (
    <div
      style={{
        background: '#fafafa',
        border: '1px solid #d9d9d9',
        borderRadius: 6,
        padding: '16px 20px',
        marginBottom: 16,
      }}
    >
      <Form
        form={form}
        layout="inline"
        onFinish={handleFinish}
        style={{ flexWrap: 'wrap', gap: '8px 0' }}
      >
        {fields.map((field) => (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={
              field.required
                ? [{ required: true, message: `${field.label}을(를) 입력하세요.` }]
                : undefined
            }
            style={{ marginBottom: 8 }}
          >
            {field.type === 'text' && (
              <Input
                placeholder={`${field.label} 입력`}
                data-testid={field.testId}
                allowClear
              />
            )}
            {field.type === 'password' && (
              <Input.Password
                placeholder={`${field.label} 입력`}
                data-testid={field.testId}
              />
            )}
            {field.type === 'select' && (
              <Select
                placeholder={`${field.label} 선택`}
                data-testid={field.testId}
                allowClear
                style={{ minWidth: 140 }}
              >
                {(field.options ?? []).map((opt) => (
                  <Select.Option key={opt} value={opt}>
                    {opt}
                  </Select.Option>
                ))}
              </Select>
            )}
          </Form.Item>
        ))}

        <Form.Item style={{ marginBottom: 8 }}>
          <Button
            type="primary"
            htmlType="submit"
            data-testid={searchTestId}
          >
            {searchLabel}
          </Button>
        </Form.Item>

        <Form.Item style={{ marginBottom: 8 }}>
          <Button
            htmlType="button"
            onClick={() => form.resetFields()}
          >
            초기화
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
}
