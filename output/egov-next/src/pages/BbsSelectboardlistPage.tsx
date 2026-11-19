import { useEffect, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { SearchPanel } from '../components/SearchPanel'
import { DataTable } from '../components/DataTable'
import { DetailList } from '../components/DetailList'
import { getBbsSelectboardlist } from '../api/client'
import type { BbsSelectboardlistRow, Detail } from '../api/client'

export default function BbsSelectboardlistPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()

  const [rows, setRows] = useState<BbsSelectboardlistRow[]>([])
  const [details, setDetails] = useState<Record<string, Detail>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async (params: Record<string, string>) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getBbsSelectboardlist(params)
      setRows(data.rows)
      setDetails(data.details)
    } catch (e) {
      setError('데이터를 불러오는 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(Object.fromEntries(searchParams))
  }, [])

  const handleSearch = (values: Record<string, string>) => {
    fetchData(values)
  }

  const columns = [
    { key: 'col1', title: '번호' },
    { key: 'col2', title: '제목' },
    { key: 'col3', title: '작성자' },
    { key: 'col4', title: '작성일' },
    { key: 'col5', title: '조회수' },
  ]

  const searchFields = [
    {
      name: 'searchCnd',
      label: '검색 조건',
      type: 'select' as const,
      options: ['제목', '내용', '작성자'],
    },
    {
      name: 'searchWrd',
      label: '검색어',
      type: 'text' as const,
    },
  ]

  const tableRows: Record<string, string>[] = rows.map((row) => ({
    col1: row.col1,
    col2: row.col2,
    col3: row.col3,
    col4: row.col4,
    col5: row.col5,
  }))

  const detailItems = Object.values(details).map((d) => ({
    label: d.label,
    value: d.value,
  }))

  return (
    <PageLayout title="공지사항 목록" testId="bbsSelectboardlist-page" menu={menu}>
      <SearchPanel
        fields={searchFields}
        searchLabel="조회"
        onSearch={handleSearch}
      />

      {error ? (
        <DetailList
          title="오류"
          items={[{ label: '오류 메시지', value: error }]}
        />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={tableRows}
            loading={loading}
            emptyText="조회된 데이터가 없습니다"
          />
          {detailItems.length > 0 && (
            <DetailList items={detailItems} />
          )}
        </>
      )}
    </PageLayout>
  )
}
