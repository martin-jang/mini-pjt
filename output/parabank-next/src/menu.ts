// Legacy2Next가 결정적으로 생성하는 메뉴입니다.
import type { MenuItem } from './components/PageLayout'

export const menu: MenuItem[] = [
  {
    "path": "/activity",
    "label": "계좌 활동 내역"
  },
  {
    "path": "/billpay",
    "label": "청구서 납부"
  },
  {
    "path": "/findtrans",
    "label": "거래 내역 검색"
  },
  {
    "path": "/lookup",
    "label": "로그인 정보 찾기"
  },
  {
    "path": "/openaccount",
    "label": "계좌 개설"
  },
  {
    "path": "/overview",
    "label": "계좌 개요"
  },
  {
    "path": "/register",
    "label": "회원 가입"
  },
  {
    "path": "/requestloan",
    "label": "대출 신청"
  },
  {
    "path": "/transaction",
    "label": "거래 상세"
  },
  {
    "path": "/transfer",
    "label": "자금 이체"
  },
  {
    "path": "/updateprofile",
    "label": "프로필 수정"
  }
]
