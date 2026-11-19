import { useEffect, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { DataTable } from '../components/DataTable'
import { DetailList } from '../components/DetailList'
import { ResultPanel } from '../components/ResultPanel'
import { getTransaction } from '../api/client'
import type { Detail, TransactionRow } from '../api/client'

export default function TransactionPage() {
  const [searchParams] = useSearchParams()

  const [rows, setRows] = useState<TransactionRow[]>([])
  const [details, setDetails] = useState<{ label: string; value: string }[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = Object.fromEntries(searchParams)
    setLoading(true)
    setError(null)
    getTransaction(params)
      .then((data) => {
        setRows(data.rows)
        setDetails(Object.values(data.details))
      })
      .catch(() => {
        setError('거래 데이터를 불러오는 중 오류가 발생했습니다.')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [searchParams])

  return (
    <PageLayout title="거래 상세" testId="transaction-page" menu={menu}>
      {error ? (
        <ResultPanel
          status="error"
          title="오류"
          message={error}
        />
      ) : (
        <>
          <DataTable
            columns={[]}
            rows={rows}
            loading={loading}
            emptyText="조회된 거래 내역이 없습니다"
          />
          <DetailList
            title="거래 상세 정보"
            items={details}
          />
        </>
      )}
    </PageLayout>
  )
}
