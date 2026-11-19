import { useLocation } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { ResultPanel } from '../components/ResultPanel'
import type { SubmitResult } from '../api/client'

export default function TransferResultPage() {
  const location = useLocation()
  const state = location.state as SubmitResult | null | undefined

  if (!state) {
    return (
      <PageLayout title="자금 이체 결과" testId="transferResult-page" menu={menu}>
        <ResultPanel
          status="error"
          title="표시할 결과가 없습니다"
          testId="transferResult-result"
        />
      </PageLayout>
    )
  }

  const items = Object.entries(state.submitted).map(([label, value]) => ({ label, value }))

  return (
    <PageLayout title="자금 이체 결과" testId="transferResult-page" menu={menu}>
      <ResultPanel
        status={state.ok ? 'success' : 'error'}
        title="처리 결과"
        message={state.message}
        items={items}
        testId="transferResult-result"
      />
    </PageLayout>
  )
}
