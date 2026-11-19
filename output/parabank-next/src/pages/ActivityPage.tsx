import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { SearchPanel } from '../components/SearchPanel'
import { DataTable } from '../components/DataTable'
import { DetailList } from '../components/DetailList'
import { ResultPanel } from '../components/ResultPanel'
import { getActivity } from '../api/client'
import type { ActivityRow } from '../api/client'
import type { DetailItem } from '../components/DetailList'

export default function ActivityPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [rows, setRows] = useState<Record<string, string>[]>([])
  const [details, setDetails] = useState<DetailItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchActivity = async (params: Record<string, string>) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getActivity(params)
      const mappedRows: Record<string, string>[] = data.rows.map((row: ActivityRow) => ({
        date: row.date,
        transaction: row.transaction,
        debit: row.debit,
        credit: row.credit,
      }))
      setRows(mappedRows)
      setDetails(Object.values(data.details))
    } catch (e) {
      setError('데이터를 불러오는 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchActivity(Object.fromEntries(searchParams))
  }, [])

  const handleSearch = (values: Record<string, string>) => {
    fetchActivity(values)
  }

  const handleLinkClick = (row: Record<string, string>) => {
    navigate('/transaction?id=' + row['date'])
  }

  return (
    <PageLayout title="계좌 활동 내역" testId="activity-page" menu={menu}>
      <SearchPanel
        fields={[
          {
            name: 'month',
            label: '월',
            type: 'text',
            testId: 'search-month',
          },
          {
            name: 'transactionType',
            label: '거래 유형',
            type: 'text',
            testId: 'search-transaction-type',
          },
        ]}
        searchLabel="조회"
        onSearch={handleSearch}
        searchTestId="search-button"
      />

      {error ? (
        <ResultPanel
          status="error"
          title="오류 발생"
          message={error}
        />
      ) : (
        <>
          <DataTable
            columns={[
              { key: 'date', title: 'Date' },
              { key: 'transaction', title: 'Transaction' },
              { key: 'debit', title: 'Debit (-)' },
              { key: 'credit', title: 'Credit (+)' },
            ]}
            rows={rows}
            emptyText="조회된 데이터가 없습니다"
            linkColumn="date"
            onLinkClick={handleLinkClick}
            linkTestId="activity-to-transaction"
            loading={loading}
          />

          {details.length > 0 && (
            <DetailList
              title="계좌 상세 정보"
              items={details}
            />
          )}
        </>
      )}
    </PageLayout>
  )
}
