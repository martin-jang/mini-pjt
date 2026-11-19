import { useEffect, useState } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router'
import { menu } from '../menu'
import { PageLayout } from '../components/PageLayout'
import { SearchPanel } from '../components/SearchPanel'
import { DataTable } from '../components/DataTable'
import { DetailList } from '../components/DetailList'
import { ResultPanel } from '../components/ResultPanel'
import { getMainpage } from '../api/client'
import type { MainpageRow, MainpageData } from '../api/client'

export default function MainpagePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [rows, setRows] = useState<Record<string, string>[]>([])
  const [details, setDetails] = useState<{ label: string; value: string }[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async (params: Record<string, string> = {}) => {
    setLoading(true)
    setError(null)
    try {
      const data: MainpageData = await getMainpage(params)
      const mappedRows: Record<string, string>[] = data.rows.map((row: MainpageRow) => ({
        f5New: row.f5New,
        col2: row.col2,
        f20261119: row.f20261119,
      }))
      setRows(mappedRows)
      setDetails(Object.values(data.details))
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '데이터를 불러오는 중 오류가 발생했습니다.'
      setError(message)
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
    { key: 'f5New', title: '홈페이지 샘플공지5 NEW' },
    { key: 'col2', title: '관리자' },
    { key: 'f20261119', title: '2026-11-19' },
  ]

  return (
    <PageLayout title="메인 홈(대시보드)" testId="mainpage-page" menu={menu}>
      <SearchPanel
        fields={[
          {
            name: 'keyword',
            label: '검색어',
            type: 'text',
            testId: 'mainpage-search-keyword',
          },
        ]}
        searchLabel="조회"
        onSearch={handleSearch}
        searchTestId="mainpage-search-btn"
      />

      {error ? (
        <ResultPanel
          status="error"
          title="오류 발생"
          message={error}
          testId="mainpage-error-panel"
        />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            emptyText="조회된 데이터가 없습니다"
            linkColumn="f5New"
            linkTestId="mainpage-to-bbsSelectboardlist"
            onLinkClick={(row: Record<string, string>) =>
              navigate('/bbsSelectboardlist?id=' + row['f5New'])
            }
          />

          {details.length > 0 && (
            <DetailList
              title="상세 정보"
              items={details}
            />
          )}
        </>
      )}
    </PageLayout>
  )
}
