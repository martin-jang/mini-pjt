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

  return (
    <>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        style={{ width: '100%', maxWidth: 480 }}
      >
        {error && (
          <Form.Item>
            <Alert
              type="error"
              message={error}
              showIcon
              style={{ marginBottom: 8 }}
            />
          </Form.Item>
        )}

        {fields.map((field) => (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={
              field.required
                ? [{ required: true, message: `${field.label}을(를) 입력해 주세요.` }]
                : []
            }
          >
            {field.type === 'text' && (
              <Input
                placeholder={`${field.label} 입력`}
                data-testid={field.testId}
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
                options={(field.options ?? []).map((opt) => ({
                  label: opt,
                  value: opt,
                }))}
              />
            )}
          </Form.Item>
        ))}

        <Form.Item>
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
        title="제출 확인"
        open={isModalOpen}
        onCancel={handleCancel}
        footer={null}
        destroyOnClose
      >
        <p>입력하신 내용을 제출하시겠습니까?</p>
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {Object.entries(pendingValues).map(([key, value]) => {
            const fieldSpec = fields.find((f) => f.name === key);
            const label = fieldSpec?.label ?? key;
            const displayValue =
              fieldSpec?.type === 'password' ? '••••••••' : String(value ?? '');
            return (
              <div
                key={key}
                style={{ display: 'flex', gap: 8, fontSize: 14 }}
              >
                <span style={{ fontWeight: 600, minWidth: 80 }}>{label}:</span>
                <span>{displayValue}</span>
              </div>
            );
          })}
        </div>
        <div
          style={{
            marginTop: 24,
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 8,
          }}
        >
          <Button onClick={handleCancel}>취소</Button>
          <Button type="primary" onClick={handleConfirm}>
            확인
          </Button>
        </div>
      </Modal>
    </>
  );
}
