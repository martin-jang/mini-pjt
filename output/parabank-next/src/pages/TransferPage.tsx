import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { FormSection } from '../components/FormSection'
import { getTransferOptions, submitTransfer } from '../api/client'

export default function TransferPage() {
  const navigate = useNavigate()

  const [options, setOptions] = useState<Record<string, string[]>>({})
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [optionsError, setOptionsError] = useState<string | undefined>(undefined)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | undefined>(undefined)

  useEffect(() => {
    setLoadingOptions(true)
    setOptionsError(undefined)
    getTransferOptions()
      .then((data) => {
        setOptions(data)
      })
      .catch(() => {
        setOptionsError('계좌 옵션을 불러오는 중 오류가 발생했습니다.')
      })
      .finally(() => {
        setLoadingOptions(false)
      })
  }, [])

  const handleSubmit = async (values: Record<string, string>) => {
    setSubmitting(true)
    setSubmitError(undefined)
    try {
      const result = await submitTransfer({
        input: values['input'],
        fromaccountid: values['fromaccountid'],
        toaccountid: values['toaccountid'],
      })
      if (result.ok) {
        navigate('/transferResult', { state: result })
      } else {
        setSubmitError(result.message || '이체 처리 중 오류가 발생했습니다.')
      }
    } catch {
      setSubmitError('이체 요청 중 오류가 발생했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  const fields = [
    {
      name: 'input',
      label: 'input',
      type: 'text' as const,
      testId: 'transfer-field-input',
      required: true,
    },
    {
      name: 'fromaccountid',
      label: 'From account',
      type: 'select' as const,
      testId: 'transfer-field-fromaccountid',
      required: true,
      options: options['fromaccountid'] ?? [],
    },
    {
      name: 'toaccountid',
      label: 'to account',
      type: 'select' as const,
      testId: 'transfer-field-toaccountid',
      required: true,
      options: options['toaccountid'] ?? [],
    },
  ]

  return (
    <PageLayout title="자금 이체" testId="transfer-page" menu={menu}>
      <FormSection
        fields={fields}
        submitLabel="이체"
        onSubmit={handleSubmit}
        submitTestId="transfer-submit"
        loading={submitting || loadingOptions}
        error={optionsError ?? submitError}
        confirmStep={true}
      />
    </PageLayout>
  )
}
