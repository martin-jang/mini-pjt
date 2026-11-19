// Legacy2Next가 결정적으로 생성하는 라우트입니다.
import type { ReactElement } from 'react'
import { Navigate } from 'react-router'
import ActivityPage from './pages/ActivityPage'
import BillpayPage from './pages/BillpayPage'
import FindtransPage from './pages/FindtransPage'
import IndexPage from './pages/IndexPage'
import LookupPage from './pages/LookupPage'
import OpenaccountPage from './pages/OpenaccountPage'
import OverviewPage from './pages/OverviewPage'
import RegisterPage from './pages/RegisterPage'
import RequestloanPage from './pages/RequestloanPage'
import TransactionPage from './pages/TransactionPage'
import TransferPage from './pages/TransferPage'
import TransferResultPage from './pages/TransferResultPage'
import UpdateprofilePage from './pages/UpdateprofilePage'

export interface AppRoute { path: string; title: string; element: ReactElement }

export const routes: AppRoute[] = [
  { path: '/', title: '시작', element: <Navigate to="/login" replace /> },
  { path: '/activity', title: '계좌 활동 내역', element: <ActivityPage /> },
  { path: '/billpay', title: '청구서 납부', element: <BillpayPage /> },
  { path: '/findtrans', title: '거래 내역 검색', element: <FindtransPage /> },
  { path: '/login', title: '로그인 (홈)', element: <IndexPage /> },
  { path: '/lookup', title: '로그인 정보 찾기', element: <LookupPage /> },
  { path: '/openaccount', title: '계좌 개설', element: <OpenaccountPage /> },
  { path: '/overview', title: '계좌 개요', element: <OverviewPage /> },
  { path: '/register', title: '회원 가입', element: <RegisterPage /> },
  { path: '/requestloan', title: '대출 신청', element: <RequestloanPage /> },
  { path: '/transaction', title: '거래 상세', element: <TransactionPage /> },
  { path: '/transfer', title: '자금 이체', element: <TransferPage /> },
  { path: '/transferResult', title: '자금 이체 결과', element: <TransferResultPage /> },
  { path: '/updateprofile', title: '프로필 수정', element: <UpdateprofilePage /> },
]
