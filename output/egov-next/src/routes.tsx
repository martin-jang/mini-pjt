// Legacy2Next가 결정적으로 생성하는 라우트입니다.
import type { ReactElement } from 'react'
import { Navigate } from 'react-router'
import MainpagePage from './pages/MainpagePage'
import AddbbsmasterPage from './pages/AddbbsmasterPage'
import BbsAddboardarticlePage from './pages/BbsAddboardarticlePage'
import AdminAddboardarticlePage from './pages/AdminAddboardarticlePage'
import AdminSelectboardlistPage from './pages/AdminSelectboardlistPage'
import SelectbbsmasterinfPage from './pages/SelectbbsmasterinfPage'
import SelectbbsmasterinfsPage from './pages/SelectbbsmasterinfsPage'
import BbsSelectboardlistPage from './pages/BbsSelectboardlistPage'
import AddbbsuseinfPage from './pages/AddbbsuseinfPage'
import SelectbbsuseinfPage from './pages/SelectbbsuseinfPage'
import SelectbbsuseinfsPage from './pages/SelectbbsuseinfsPage'
import EgovloginusrPage from './pages/EgovloginusrPage'

export interface AppRoute { path: string; title: string; element: ReactElement }

export const routes: AppRoute[] = [
  { path: '/', title: '시작', element: <Navigate to="/login" replace /> },
  { path: '/mainpage', title: '메인 홈(대시보드)', element: <MainpagePage /> },
  { path: '/addbbsmaster', title: '게시판 템플릿 등록', element: <AddbbsmasterPage /> },
  { path: '/bbsAddboardarticle', title: '공지사항 글 등록', element: <BbsAddboardarticlePage /> },
  { path: '/adminAddboardarticle', title: '공지사항 글 등록(관리자)', element: <AdminAddboardarticlePage /> },
  { path: '/adminSelectboardlist', title: '공지사항 목록(관리자)', element: <AdminSelectboardlistPage /> },
  { path: '/selectbbsmasterinf', title: '게시판 생성 상세', element: <SelectbbsmasterinfPage /> },
  { path: '/selectbbsmasterinfs', title: '게시판 생성 목록', element: <SelectbbsmasterinfsPage /> },
  { path: '/bbsSelectboardlist', title: '공지사항 목록', element: <BbsSelectboardlistPage /> },
  { path: '/addbbsuseinf', title: '게시판 사용 등록', element: <AddbbsuseinfPage /> },
  { path: '/selectbbsuseinf', title: '게시판 사용 상세', element: <SelectbbsuseinfPage /> },
  { path: '/selectbbsuseinfs', title: '게시판 사용 목록', element: <SelectbbsuseinfsPage /> },
  { path: '/login', title: '로그인', element: <EgovloginusrPage /> },
]
