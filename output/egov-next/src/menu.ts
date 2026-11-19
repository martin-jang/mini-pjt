// Legacy2Next가 결정적으로 생성하는 메뉴입니다.
import type { MenuItem } from './components/PageLayout'

export const menu: MenuItem[] = [
  {
    "path": "/mainpage",
    "label": "메인 홈(대시보드)"
  },
  {
    "path": "/addbbsmaster",
    "label": "게시판 템플릿 등록"
  },
  {
    "path": "/bbsAddboardarticle",
    "label": "공지사항 글 등록"
  },
  {
    "path": "/adminAddboardarticle",
    "label": "공지사항 글 등록(관리자)"
  },
  {
    "path": "/adminSelectboardlist",
    "label": "공지사항 목록(관리자)"
  },
  {
    "path": "/selectbbsmasterinf",
    "label": "게시판 생성 상세"
  },
  {
    "path": "/selectbbsmasterinfs",
    "label": "게시판 생성 목록"
  },
  {
    "path": "/bbsSelectboardlist",
    "label": "공지사항 목록"
  },
  {
    "path": "/addbbsuseinf",
    "label": "게시판 사용 등록"
  },
  {
    "path": "/selectbbsuseinf",
    "label": "게시판 사용 상세"
  },
  {
    "path": "/selectbbsuseinfs",
    "label": "게시판 사용 목록"
  }
]
