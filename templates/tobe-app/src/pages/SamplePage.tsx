// 템플릿 동작 확인용 샘플 화면 (교육용 더미). 생성 시 삭제됩니다.
import { useEffect, useState } from 'react'
import { PageLayout } from '../components/PageLayout'
import { getSample } from '../api/client'

export default function SamplePage() {
  const [message, setMessage] = useState('불러오는 중')
  useEffect(() => {
    getSample().then((r) => setMessage(r.message)).catch(() => setMessage('오류'))
  }, [])
  return (
    <PageLayout title="샘플">
      <p data-testid="sample-message">{message}</p>
    </PageLayout>
  )
}
