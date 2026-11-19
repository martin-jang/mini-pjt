import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { SearchPanel } from '../components/SearchPanel'
import { DataTable } from '../components/DataTable'
import { DetailList } from '../components/DetailList'
import { ResultPanel } from '../components/ResultPanel'
import { getOverview } from '../api/client'
import type { OverviewData } from '../api/client'

export default function OverviewPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [data, setData] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async (params: Record<string, string> = {}) => {
    setLoading(true)
    setError(null)
    try {
      const result = await getOverview(params)
      setData(result)
    } catch (e: unknown) {
      if (e instanceof Error) {
        setError(e.message)
      } else {
        setError('데이터를 불러오는 중 오류가 발생했습니다.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(Object.fromEntries(searchParams))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSearch = (values: Record<string, string>) => {
    const filtered: Record<string, string> = {}
    Object.entries(values).forEach(([k, v]) => {
      if (v !== '') filtered[k] = v
    })
    setSearchParams(filtered)
    fetchData(filtered)
  }

  const columns = [
    { key: 'account', title: 'Account' },
    { key: 'balance', title: 'Balance*' },
    { key: 'availableAmount', title: 'Available Amount' },
  ]

  const detailItems = data
    ? Object.values(data.details).map((d) => ({ label: d.label, value: d.value }))
    : []

  return (
    <PageLayout title="계좌 개요" testId="overview-page" menu={menu}>
      <div style={{ marginBottom: '16px' }}>
        <button
          type="button"
          data-testid="overview-to-transfer"
          onClick={() => navigate('/transfer')}
          style={{
            padding: '8px 20px',
            backgroundColor: '#1677ff',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
          }}
        >
          자금 이체
        </button>
      </div>

      <SearchPanel
        fields={[
          {
            name: 'accountType',
            label: '계좌 유형',
            type: 'select',
            options: ['전체', '입출금', '적금', '대출'],
          },
          {
            name: 'keyword',
            label: '계좌 번호',
            type: 'text',
          },
        ]}
        searchLabel="조회"
        onSearch={handleSearch}
        searchTestId="overview-search"
      />

      {error && (
        <ResultPanel
          status="error"
          title="오류 발생"
          message={error}
        />
      )}

      {!error && (
        <>
          <DataTable
            columns={columns}
            rows={
              data
                ? data.rows.map((r) => ({
                    account: r.account,
                    balance: r.balance,
                    availableAmount: r.availableAmount,
                  }))
                : []
            }
            emptyText="조회된 계좌가 없습니다."
            showTotal
            totalKey="balance"
            linkColumn="account"
            onLinkClick={(row) => navigate('/activity?id=' + row['account'])}
            linkTestId="overview-to-activity"
            loading={loading}
          />

          {data && detailItems.length > 0 && (
            <DetailList
              title="계좌 상세 정보"
              items={detailItems}
            />
          )}
        </>
      )}
    </PageLayout>
  )
}
