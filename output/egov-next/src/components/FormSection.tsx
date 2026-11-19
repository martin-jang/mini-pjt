import type { ReactNode } from 'react';
import { useState } from 'react';
import { Form, Input, Select, Button, Modal, Alert } from 'antd';

export interface FieldSpec {
  name: string;
  label: string;
  type: 'text' | 'password' | 'select';
  options?: string[];
  required?: boolean;
  testId?: string;
}

export interface FormSectionProps {
  fields: FieldSpec[];
  submitLabel: string;
  onSubmit: (values: Record<string, string>) => void;
  submitTestId?: string;
  confirmStep?: boolean;
  loading?: boolean;
  error?: string;
}

export function FormSection(props: FormSectionProps): ReactNode {
  const {
    fields,
    submitLabel,
    onSubmit,
    submitTestId,
    confirmStep = false,
    loading = false,
    error,
  } = props;

  const [form] = Form.useForm<Record<string, string>>();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [pendingValues, setPendingValues] = useState<Record<string, string>>({});

  const handleFinish = (values: Record<string, string>) => {
    if (confirmStep) {
      setPendingValues(values);
      setIsModalOpen(true);
    } else {
      onSubmit(values);
    }
  };

  const handleConfirm = () => {
    setIsModalOpen(false);
    onSubmit(pendingValues);
    form.resetFields();
  };

  const handleCancel = () => {
    setIsModalOpen(false);
  };

  const renderField = (field: FieldSpec): ReactNode => {
    if (field.type === 'password') {
      return (
        <Input.Password
          data-testid={field.testId}
          placeholder={`${field.label}을(를) 입력하세요`}
        />
      );
    }
    if (field.type === 'select') {
      return (
        <Select
          data-testid={field.testId}
          placeholder={`${field.label}을(를) 선택하세요`}
        >
          {(field.options ?? []).map((opt) => (
            <Select.Option key={opt} value={opt}>
              {opt}
            </Select.Option>
          ))}
        </Select>
      );
    }
    return (
      <Input
        data-testid={field.testId}
        placeholder={`${field.label}을(를) 입력하세요`}
      />
    );
  };

  const confirmRows = Object.entries(pendingValues).map(([key, value]) => {
    const matched = fields.find((f) => f.name === key);
    const label = matched ? matched.label : key;
    return { label, value };
  });

  return (
    <>
      {error && (
        <Alert
          message={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        autoComplete="off"
      >
        {fields.map((field) => (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={
              field.required
                ? [{ required: true, message: `${field.label}은(는) 필수 항목입니다.` }]
                : []
            }
          >
            {renderField(field)}
          </Form.Item>
        ))}

        <Form.Item style={{ marginTop: 8 }}>
          <Button
            type="primary"
            htmlType="submit"
            loading={loading}
            data-testid={submitTestId}
            block
          >
            {submitLabel}
          </Button>
        </Form.Item>
      </Form>

      <Modal
        title="입력 내용 확인"
        open={isModalOpen}
        onCancel={handleCancel}
        footer={null}
        destroyOnClose
      >
        <div style={{ marginBottom: 16 }}>
          <p style={{ marginBottom: 12, color: '#595959' }}>
            아래 내용으로 제출하시겠습니까?
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <tbody>
              {confirmRows.map(({ label, value }) => (
                <tr key={label}>
                  <td
                    style={{
                      padding: '8px 12px',
                      fontWeight: 600,
                      width: '40%',
                      background: '#fafafa',
                      border: '1px solid #f0f0f0',
                    }}
                  >
                    {label}
                  </td>
                  <td
                    style={{
                      padding: '8px 12px',
                      border: '1px solid #f0f0f0',
                    }}
                  >
                    {value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={handleCancel}>취소</Button>
          <Button type="primary" onClick={handleConfirm}>
            확인
          </Button>
        </div>
      </Modal>
    </>
  );
}
