// 구현 예정 플레이스홀더 (Legacy2Next 결정적 생성)
import { PageLayout } from '../components/PageLayout'
import { menu } from '../menu'

export default function SelectbbsuseinfPage() {
  return (
    <PageLayout title="게시판 사용 상세" testId="selectbbsuseinf-page" menu={menu}>
      <p data-testid="selectbbsuseinf-placeholder">[구현 예정] 핵심 업무 흐름(Happy Path) 밖의 화면이라 이번 POC에서는 구조만 제공합니다.</p>
    </PageLayout>
  )
}
