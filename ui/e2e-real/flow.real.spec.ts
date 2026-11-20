import { expect, test } from '@playwright/test';

// T04 완료 기준: 실제 에이전트 서버의 스텁 그래프가 콘솔에서 처음부터 끝까지 돌고, 승인 → 재개가 된다

test('실제 서버: 새 요청 → 승인 2곳 → 결과', async ({ page }) => {
  const alias = `real-${Date.now() % 100000}`;
  await page.goto('/new');
  await page.getByTestId('input-url').fill('http://127.0.0.1:8766/');
  await page.getByTestId('input-alias').fill(alias);
  await page.getByTestId('submit-request').click();
  await expect(page).toHaveURL(new RegExp(`/sites/${alias}$`));
  await expect(page.getByTestId(`site-${alias}`)).toBeVisible();
  await expect(page.getByTestId('log-viewer')).toContainText('[explorer]');
  // T06 (EXP-02): 실제 브라우저로 시험 사이트를 돌며 다른 origin 이동을 막고 콘솔에 남긴다
  await expect(page.getByTestId('log-viewer')).toContainText('Playwright MCP 브라우저 시작');
  await expect(page.getByTestId('guardrail-events')).toContainText('G2', { timeout: 30_000 });
  await expect(page.getByTestId('guardrail-events')).toContainText('차단됨');
  await expect(page.getByTestId('guardrail-events')).toContainText('localhost:8766');
  await expect(page.getByTestId('log-viewer')).toContainText('이동 후');
  // T07b: 화면마다 원본·파생 파일을 저장한다 (next-pjt/<별칭>/crawl/)
  await expect(page.getByTestId('log-viewer')).toContainText('화면 저장: board-html-');

  // 승인 1
  await page.getByTestId('go-analysis-review').click({ timeout: 40_000 });
  await expect(page.getByTestId('site-profile')).toContainText('업무 도메인');
  await page.getByTestId('analysis-approve').click();
  await expect(page).toHaveURL(new RegExp(`/sites/${alias}$`));

  // 승인 2: 대폭 변경 화면은 따로, 나머지는 일괄
  await page.getByTestId('go-design-review').click({ timeout: 20_000 });
  await expect(page.getByTestId('major-change-notice')).toBeVisible();
  await expect(page.getByTestId('change-why').first()).toContainText('입력 실수');
  await page.getByTestId('screen-approve').click();
  await expect(page.getByTestId('design-progress')).toContainText('승인 1 /');
  await page.getByTestId('design-approve-regular').click();
  await expect(page).toHaveURL(new RegExp(`/sites/${alias}$`));

  await page.getByTestId('go-result').click({ timeout: 20_000 });
  await expect(page.getByTestId('output-dir')).toHaveText(`next-pjt/${alias}/`);
  await expect(page.getByTestId(`site-${alias}`)).toContainText('완료');
  await expect(page.getByTestId('result-timing')).toContainText('승인 대기');
});

test('실제 서버: 입력 검증 오류가 콘솔에 보인다', async ({ page }) => {
  await page.goto('/new');
  await page.getByTestId('input-url').fill('https://legacy.example.com');
  await page.getByTestId('input-alias').fill('X');
  await page.getByTestId('submit-request').click();
  await expect(page.getByTestId('form-error')).toContainText('별칭');
});

// T05: Router 분류 결과가 콘솔 질의 화면에 보인다 (실제 서버, 가짜 LLM)
test('실제 서버: 범위 밖 질문은 거절, URL 요청은 새 요청으로 안내', async ({ page }) => {
  await page.goto('/query');
  await page.getByTestId('query-input').fill('오늘 점심 메뉴 추천해줘');
  await page.getByTestId('query-input').press('Enter');
  await expect(page.getByTestId('answer-rejected')).toContainText('레거시 웹 시스템');

  await page.getByTestId('query-input').fill('https://legacy.example.com 분석해서 POC 만들어줘');
  await page.getByTestId('query-send').click();
  await expect(page.getByTestId('answer-start')).toContainText('새 POC 생성');
  await page.getByTestId('answer-start-link').click();
  await expect(page).toHaveURL(/\/new\?/);
  await expect(page.getByTestId('input-url')).toHaveValue('https://legacy.example.com');
  await expect(page.getByTestId('input-alias')).toHaveValue('legacy-example');
});

// T07a: 로그인과 사용자 인증 넘김 (실제 브라우저 + 시험 사이트 + 가짜 LLM)
test('실제 서버: ID/PW 자동 로그인 → 수집 → 결과에서 세션 삭제', async ({ page }) => {
  // 계정은 에이전트 환경 변수 SITE_IDPW_E2E_USERNAME/PASSWORD (playwright.real.config.ts)
  const alias = 'idpw-e2e';
  await page.goto('/new');
  await page.getByTestId('input-url').fill('http://127.0.0.1:8766/idpw/home');
  await page.getByTestId('input-alias').fill(alias);
  await page.getByTestId('submit-request').click();
  const log = page.getByTestId('log-viewer');
  await expect(log).toContainText('로그인 화면 감지: 아이디·비밀번호', { timeout: 30_000 });
  await expect(log).toContainText('ID/PW 로그인 성공');
  await expect(log).toContainText('화면 확인: 공지사항', { timeout: 30_000 });

  await page.getByTestId('go-analysis-review').click({ timeout: 40_000 });
  await page.getByTestId('analysis-approve').click();
  await page.getByTestId('go-design-review').click({ timeout: 20_000 });
  await page.getByTestId('screen-approve').click();
  await expect(page.getByTestId('design-progress')).toContainText('승인 1 /');
  await page.getByTestId('design-approve-regular').click();
  await page.getByTestId('go-result').click({ timeout: 20_000 });

  // G10: 저장된 세션을 결과 화면에서 지운다
  await expect(page.getByTestId('session-notice')).toBeVisible();
  await page.getByTestId('delete-session').click();
  await expect(page.getByTestId('session-notice')).toBeHidden();
});

test('실제 서버: 간편인증은 사용자에게 넘기고, 인증 완료 후 이어서 진행', async ({
  page,
  request,
}) => {
  const alias = 'cert-e2e';
  await page.goto('/new');
  await page.getByTestId('input-url').fill('http://127.0.0.1:8766/cert/home');
  await page.getByTestId('input-alias').fill(alias);
  await page.getByTestId('submit-request').click();

  const card = page.getByTestId('auth-card');
  await expect(card).toContainText('브라우저에서 인증을 완료해 주세요', { timeout: 30_000 });
  await expect(page.getByTestId('auth-reason')).toContainText('간편인증');
  await expect(page.getByTestId('run-status')).toContainText('인증 대기');
  await expect(page.getByTestId('stage-explorer')).toContainText('인증 대기');

  // 사용자가 휴대폰에서 승인한 것으로 흉내 낸다 → 인증 브라우저 화면이 세션을 받는다
  await request.post('http://127.0.0.1:8766/_test/approve');
  await page.waitForTimeout(1500);
  await page.getByTestId('auth-done').click();
  await expect(card).toBeHidden({ timeout: 20_000 });
  await expect(page.getByTestId('log-viewer')).toContainText('인증 완료: 세션을 저장했습니다');
  await expect(page.getByTestId('log-viewer')).toContainText('화면 확인: 민원 신청 내역', {
    timeout: 30_000,
  });
  await expect(page.getByTestId('go-analysis-review')).toBeVisible({ timeout: 40_000 });
});
