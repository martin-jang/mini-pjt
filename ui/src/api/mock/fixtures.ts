// 목업 데이터. 대상 사이트를 특정하지 않는 일반적인 "사내 업무 포털" 예시

import type {
  AnalysisDecision,
  AnalysisReview,
  DesignChange,
  DesignScreen,
  GeneratedScreen,
  LayoutSketch,
  RunResult,
} from '../types';

export const TOTAL_COLLECTED_SCREENS = 18;

export function buildAnalysis(): AnalysisReview {
  return {
    profile: {
      domain: '사내 업무 포털 (공지·근태·휴가)',
      users: '임직원, 부서 관리자',
      coreTasks: '공지 확인, 휴가 신청, 근태 조회',
      confidence: 0.92,
      summary:
        '로그인 후 첫 화면에 공지·근태 요약이 있고, 메뉴 18개 중 12개가 신청·조회 화면입니다. 화면 제목과 입력 항목으로 볼 때 임직원이 매일 쓰는 사내 업무 포털로 판단했습니다.',
      evidence: [
        { screen: '메인', path: '/main' },
        { screen: '공지 목록', path: '/notice/list' },
        { screen: '휴가 신청', path: '/leave/apply' },
      ],
    },
    happyPaths: [
      {
        id: 'hp1',
        title: '공지 확인',
        steps: ['로그인', '메인', '공지 목록', '공지 상세'],
        reason: '로그인 직후 가장 먼저 보이는 조회 흐름입니다. 쓰기 동작이 없어 시연이 안전합니다.',
        recommended: true,
      },
      {
        id: 'hp2',
        title: '휴가 신청',
        steps: ['로그인', '휴가 신청 목록', '휴가 신청'],
        reason: '입력 폼과 검증이 있는 대표 업무입니다. 바뀐 입력 경험을 보여주기 좋습니다.',
        recommended: true,
      },
      {
        id: 'hp3',
        title: '사용자 관리',
        steps: ['로그인', '사용자 목록', '사용자 상세'],
        reason: '관리자 메뉴라 수집 중 승인이 필요했고, 1차 시연 범위에서는 빼는 것을 권합니다.',
        recommended: false,
      },
    ],
    dataModes: [
      {
        mode: 'mock',
        title: '목업 데이터',
        summary: '수집한 화면 구조로 합성 데이터를 만들어 앱 안에서만 동작합니다.',
        reasons: [
          '휴가 신청은 쓰기 동작이라 시연 중 실제 데이터가 바뀔 수 있습니다',
          '레거시 응답이 서버에서 그린 HTML이라 API로 바로 쓰기 어렵습니다',
          '개인정보는 자리표시자 형식만 보고 합성 값으로 채웁니다',
        ],
        recommended: true,
      },
      {
        mode: 'legacy',
        title: '레거시 백엔드 호출',
        summary: '생성 앱이 레거시 서버에 직접 요청해 실제 데이터를 보여줍니다.',
        reasons: ['실제 데이터로 화면을 확인할 수 있습니다'],
        caveat: '레거시 세션·CORS 처리가 필요하고, 쓰기 동작은 실제 데이터를 바꿉니다.',
        recommended: false,
      },
    ],
    variants: [
      {
        id: 'v1',
        name: '목록 표',
        selectors: ['table.list', 'table.grid'],
        screenCount: 7,
        decision: 'unify',
        reason: '컬럼 구성과 페이지 이동 위치만 다릅니다. 하나의 표 컴포넌트로 묶습니다.',
      },
      {
        id: 'v2',
        name: '검색 조건 영역',
        selectors: ['.search_box', '.srch_area'],
        screenCount: 5,
        decision: 'prop',
        reason: '기간 선택이 있는 화면과 없는 화면이 나뉩니다. 기간 선택을 옵션으로 둡니다.',
      },
      {
        id: 'v3',
        name: '확인 팝업',
        selectors: ['window.open 팝업', '.layer_pop'],
        screenCount: 2,
        decision: 'hold',
        reason: '새 창 팝업과 레이어 팝업의 동작이 달라 확인이 필요합니다.',
      },
    ],
  };
}

export function recommendedDecision(analysis: AnalysisReview): AnalysisDecision {
  return {
    action: 'approve',
    happyPathIds: analysis.happyPaths.filter((p) => p.recommended).map((p) => p.id),
    dataMode: analysis.dataModes.find((m) => m.recommended)?.mode ?? 'mock',
    variantDecisions: Object.fromEntries(analysis.variants.map((v) => [v.id, v.decision])),
  };
}

const legacyPage: LayoutSketch = { nav: 'left', blocks: ['상단 배너', '본문 표', '하단 버튼'] };

interface ScreenTemplate {
  path: string;
  majorChange: boolean;
  changes: DesignChange[];
  asis: LayoutSketch;
  tobe: LayoutSketch;
  preserved: number;
  total: number;
}

const screenCatalog: Record<string, ScreenTemplate> = {
  로그인: {
    path: '/login',
    majorChange: false,
    changes: [
      {
        what: '입력란·버튼 위치 유지, 간격과 글자 크기만 정리',
        why: '로그인은 매일 쓰는 익숙한 화면이라 배치는 그대로 두고 읽기 쉬운 정도만 높였습니다',
      },
    ],
    asis: { nav: 'none', blocks: ['로고', '아이디·비밀번호', '로그인 버튼'] },
    tobe: { nav: 'none', blocks: ['로고', '아이디·비밀번호', '로그인 버튼'] },
    preserved: 4,
    total: 4,
  },
  메인: {
    path: '/main',
    majorChange: false,
    changes: [
      {
        what: '요약 박스 3개를 카드로 바꿈, 배치는 유지',
        why: '같은 정보를 카드로 묶어 영역이 한눈에 구분되게 했습니다. 위치는 그대로라 찾던 자리에서 찾을 수 있습니다',
      },
    ],
    asis: legacyPage,
    tobe: { nav: 'left', blocks: ['상단 헤더', '요약 카드', '최근 공지'] },
    preserved: 9,
    total: 9,
  },
  '공지 목록': {
    path: '/notice/list',
    majorChange: false,
    changes: [
      {
        what: '검색 조건과 표 구성 유지, 공통 표 컴포넌트 적용',
        why: '분석 리뷰에서 승인한 "목록 표: 통일" 결정에 따라 7개 화면의 표를 하나의 컴포넌트로 맞췄습니다',
      },
    ],
    asis: { nav: 'left', blocks: ['검색 조건', '공지 표', '페이지 이동'] },
    tobe: { nav: 'left', blocks: ['검색 조건', '공지 표', '페이지 이동'] },
    preserved: 7,
    total: 7,
  },
  '공지 상세': {
    path: '/notice/detail',
    majorChange: false,
    changes: [
      {
        what: '본문·첨부 영역 유지',
        why: '본문을 읽는 것이 주 목적인 화면이라 구조를 바꿀 이유가 없었습니다',
      },
    ],
    asis: { nav: 'left', blocks: ['제목', '본문', '첨부', '목록 버튼'] },
    tobe: { nav: 'left', blocks: ['제목', '본문', '첨부', '목록 버튼'] },
    preserved: 6,
    total: 6,
  },
  '휴가 신청 목록': {
    path: '/leave/list',
    majorChange: false,
    changes: [
      {
        what: '상태 열을 배지로 표시, 표 구성 유지',
        why: '신청 상태를 글자 대신 배지로 보여 승인·반려 건을 빨리 구분하게 했습니다',
      },
    ],
    asis: { nav: 'left', blocks: ['검색 조건', '신청 표', '신청 버튼'] },
    tobe: { nav: 'left', blocks: ['검색 조건', '신청 표', '신청 버튼'] },
    preserved: 8,
    total: 8,
  },
  '휴가 신청': {
    path: '/leave/apply',
    majorChange: true,
    changes: [
      {
        what: '한 화면에 있던 입력 11개를 "기간 선택 → 사유·결재자" 2단계로 나눔',
        why: '입력 11개가 한 화면에 몰려 있어 필수 항목을 놓치기 쉬웠습니다. 단계마다 확인하게 해 입력 실수를 줄입니다',
      },
      {
        what: '왼쪽 아래에 있던 신청 버튼을 오른쪽 아래로 옮김',
        why: '입력을 마치고 다음으로 가는 버튼을 오른쪽 아래에 두는 일반적인 폼 흐름에 맞췄습니다',
      },
      {
        what: '새 창으로 뜨던 결재자 선택을 화면 안 대화상자로 바꿈',
        why: '새 창은 팝업 차단에 막히고 창을 오가야 합니다. 화면 안 대화상자로 바꿔 흐름이 끊기지 않게 했습니다',
      },
    ],
    asis: { nav: 'left', blocks: ['입력 11개 (한 화면)', '결재자 새 창', '신청 버튼(왼쪽)'] },
    tobe: { nav: 'left', blocks: ['1단계: 기간 선택', '2단계: 사유·결재자', '신청 버튼(오른쪽)'] },
    preserved: 11,
    total: 11,
  },
  '사용자 목록': {
    path: '/admin/user/list',
    majorChange: false,
    changes: [
      {
        what: '공통 표 컴포넌트 적용',
        why: '분석 리뷰에서 승인한 "목록 표: 통일" 결정을 따릅니다',
      },
    ],
    asis: { nav: 'left', blocks: ['검색 조건', '사용자 표'] },
    tobe: { nav: 'left', blocks: ['검색 조건', '사용자 표'] },
    preserved: 6,
    total: 6,
  },
  '사용자 상세': {
    path: '/admin/user/detail',
    majorChange: false,
    changes: [
      {
        what: '입력 항목 그룹 유지',
        why: '권한 설정은 실수하면 위험한 화면이라 기존 그룹 구성을 그대로 두었습니다',
      },
    ],
    asis: { nav: 'left', blocks: ['기본 정보', '권한'] },
    tobe: { nav: 'left', blocks: ['기본 정보', '권한'] },
    preserved: 8,
    total: 8,
  },
};

function selectedScreenNames(analysis: AnalysisReview, happyPathIds: string[]): string[] {
  const names = analysis.happyPaths
    .filter((p) => happyPathIds.includes(p.id))
    .flatMap((p) => p.steps);
  return [...new Set(names)];
}

export function buildDesignScreens(
  analysis: AnalysisReview,
  happyPathIds: string[],
): DesignScreen[] {
  return selectedScreenNames(analysis, happyPathIds).map((name, index) => {
    const t = screenCatalog[name];
    return {
      id: `s${index + 1}`,
      name,
      path: t?.path ?? '/',
      majorChange: t?.majorChange ?? false,
      changes: t?.changes ?? [],
      state: 'pending',
      asis: t?.asis ?? legacyPage,
      tobe: t?.tobe ?? legacyPage,
    };
  });
}

const dataModeLabel = { mock: '목업 데이터', legacy: '레거시 백엔드 호출' } as const;
const variantLabel = { unify: '통일', prop: '변형 prop', hold: '보류' } as const;

export function buildResult(
  alias: string,
  analysis: AnalysisReview,
  decision: AnalysisDecision,
  designScreens: DesignScreen[],
): RunResult {
  const screens: GeneratedScreen[] = designScreens.map((s) => {
    const hp = analysis.happyPaths.find(
      (p) => decision.happyPathIds.includes(p.id) && p.steps.includes(s.name),
    );
    const t = screenCatalog[s.name];
    return {
      name: s.name,
      path: s.path,
      happyPath: hp?.title,
      preserved: t?.preserved ?? 1,
      total: t?.total ?? 1,
    };
  });
  const variantSummary = analysis.variants
    .map((v) => `${v.name} ${variantLabel[decision.variantDecisions[v.id] ?? v.decision]}`)
    .join(', ');
  return {
    outputDir: `next-pjt/${alias}/`,
    previewUrl: 'http://localhost:5174/',
    totalScreens: TOTAL_COLLECTED_SCREENS,
    screens,
    components: [
      'AppLayout',
      'DataTable',
      'SearchForm',
      'FormField',
      'DateRangePicker',
      'StatusBadge',
      'ConfirmDialog',
      'StepIndicator',
      'Pagination',
    ],
    decisions: [
      {
        label: 'Happy Path',
        value: analysis.happyPaths
          .filter((p) => decision.happyPathIds.includes(p.id))
          .map((p) => p.title)
          .join(', '),
      },
      { label: '데이터 연결 방식', value: dataModeLabel[decision.dataMode] },
      { label: '변이 통일', value: variantSummary },
    ],
    verification: [
      { id: 'build', label: '빌드', detail: 'npm run build 성공, 타입 오류 0건', passed: true },
      {
        id: 'flow',
        label: 'Happy Path 흐름 테스트',
        detail: `Playwright ${decision.happyPathIds.length}개 흐름 통과`,
        passed: true,
      },
      {
        id: 'preserve',
        label: '기능 보존 대조',
        detail: '레거시 입력 필드·버튼·조회 항목 ↔ data-testid 대조',
        passed: true,
      },
      {
        id: 'secret',
        label: '계정 원문 검색',
        detail: '생성 결과물에서 계정 값 0건',
        passed: true,
      },
      {
        id: 'guard',
        label: '가드레일',
        detail: '의존성 템플릿과 일치(G7), 쓰기 경로 범위 안(G9)',
        passed: true,
      },
    ],
  };
}

export const COMPONENT_USAGE: Record<string, string> = {
  AppLayout: '전체 화면',
  DataTable: '공지 목록, 휴가 신청 목록',
  SearchForm: '공지 목록, 휴가 신청 목록',
  FormField: '로그인, 휴가 신청',
  DateRangePicker: '휴가 신청, 공지 목록',
  StatusBadge: '휴가 신청 목록',
  ConfirmDialog: '휴가 신청',
  StepIndicator: '휴가 신청',
  Pagination: '공지 목록, 휴가 신청 목록',
};
