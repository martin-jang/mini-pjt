import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { FormSection } from '../components/FormSection'
import { login } from '../api/client'

export default function EgovloginusrPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | undefined>(undefined)

  const fields = [
    {
      name: 'username',
      label: '아이디',
      type: 'text' as const,
      required: true,
      testId: 'egovloginusr-field-id',
    },
    {
      name: 'password',
      label: '비밀번호',
      type: 'password' as const,
      required: true,
      testId: 'egovloginusr-field-password',
    },
  ]

  const handleSubmit = async (values: Record<string, string>) => {
    setLoading(true)
    setError(undefined)
    try {
      const result = await login({
        username: values['username'] ?? '',
        password: values['password'] ?? '',
      })
      if (result.ok) {
        navigate(searchParams.get('next') ?? '/mainpage')
      } else {
        setError(result.message || '로그인에 실패하였습니다.')
      }
    } catch {
      setError('서버 오류가 발생하였습니다. 잠시 후 다시 시도해 주세요.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageLayout title="로그인" testId="egovloginusr-page" menu={menu}>
      <FormSection
        fields={fields}
        submitLabel="로그인"
        onSubmit={handleSubmit}
        submitTestId="egovloginusr-submit"
        loading={loading}
        error={error}
      />
    </PageLayout>
  )
}
