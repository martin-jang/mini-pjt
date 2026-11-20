import { expect, test } from '@playwright/test';

// T02 완료 기준: 콘솔만으로 요청 → 단계 진행 → 분석 리뷰 승인 → 디자인 확인 → 결과까지 클릭해 볼 수 있다

test('새 요청부터 결과까지 전체 흐름', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/new$/);

  await page.getByTestId('input-url').fill('https://legacy.example.com');
  await page.getByTestId('input-alias').fill('e2e-site');
  await page.getByTestId('submit-request').click();
  await expect(page).toHaveURL(/\/sites\/e2e-site$/);
  await expect(page.getByTestId('site-e2e-site')).toBeVisible();

  // ①② 진행 → 승인 1
  await page.getByTestId('go-analysis-review').click({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/sites\/e2e-site\/analysis$/);
  await expect(page.getByTestId('site-profile')).toContainText('업무 도메인');
  await expect(page.getByTestId('happy-path-hp1')).toBeChecked();
  await expect(page.getByTestId('happy-path-hp3')).not.toBeChecked();
  await expect(page.getByTestId('data-mode-mock')).toBeChecked();
  await page.getByTestId('analysis-approve').click();
  await expect(page).toHaveURL(/\/sites\/e2e-site$/);

  // ③ 진행 → 승인 2: 대폭 변경 화면은 개별 승인, 나머지는 일괄 승인
  await page.getByTestId('go-design-review').click({ timeout: 20_000 });
  await expect(page.getByTestId('major-change-notice')).toBeVisible();
  await expect(page.getByTestId('sketch-asis')).toBeVisible();
  await expect(page.getByTestId('sketch-tobe')).toBeVisible();
  await page.getByTestId('screen-approve').click();
  await expect(page.getByTestId('design-progress')).toContainText('승인 1 /');
  await page.getByTestId('design-approve-regular').click();
  await expect(page).toHaveURL(/\/sites\/e2e-site$/);

  // ④⑤ 진행 → 결과
  await page.getByTestId('go-result').click({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/sites\/e2e-site\/result$/);
  await expect(page.getByTestId('output-dir')).toHaveText('next-pjt/e2e-site/');
  await expect(page.getByTestId('verification')).toContainText('5 / 5 통과');
  await expect(page.getByTestId('result-timing')).toContainText('승인 대기');
  await expect(page.getByTestId('site-e2e-site')).toContainText('완료');
});

test('분석 리뷰 수정 요청은 의견이 있어야 한다', async ({ page }) => {
  await page.goto('/sites/groupware/analysis');
  await page.getByTestId('analysis-revise').click();
  await expect(page.getByTestId('analysis-error')).toContainText('수정 요청 내용');
  await page.getByTestId('analysis-comment').fill('근태 조회 흐름을 먼저 보여 주세요');
  await page.getByTestId('analysis-revise').click();
  await expect(page.getByTestId('analysis-notice')).toBeVisible();
});

test('진행 화면에 SSE 로그와 가드레일 이벤트가 보이고 실행을 중단할 수 있다', async ({ page }) => {
  await page.goto('/sites/hr-portal');
  await expect(page.getByTestId('log-viewer')).toContainText('[explorer]');
  await expect(page.getByTestId('guardrail-events')).toContainText('G2');
  await expect(page.getByTestId('guardrail-events')).toContainText('차단됨');
  await expect(page.getByTestId('stage-explorer')).toHaveAttribute('data-state', 'done');
  await page.getByTestId('stop-run').click();
  await expect(page.getByTestId('run-status')).toHaveText('중단');
});

test('새 요청 입력 검증', async ({ page }) => {
  await page.goto('/new');
  await page.getByTestId('input-url').fill('https://intranet.example.com');
  await page.getByTestId('input-alias').fill('intranet');
  await page.getByTestId('submit-request').click();
  await expect(page.getByTestId('form-error')).toContainText('이미 있습니다');

  await page.getByTestId('input-url').fill('legacy.example.com');
  await page.getByTestId('input-alias').fill('other-site');
  await page.getByTestId('submit-request').click();
  await expect(page.getByTestId('form-error')).toContainText('https://');
});

test('질의: 범위 밖 질문은 거절하고 사이트 질문에는 근거와 함께 답한다', async ({ page }) => {
  await page.goto('/query');
  await page.getByTestId('query-input').fill('오늘 점심 메뉴 추천해줘');
  await page.getByTestId('query-input').press('Enter');
  await expect(page.getByTestId('answer-rejected')).toBeVisible();

  await page.getByTestId('query-input').fill('공통 컴포넌트 알려줘');
  await page.getByTestId('query-send').click();
  await expect(page.getByTestId('answer')).toContainText('DataTable');
  await expect(page.getByTestId('answer')).toContainText('근거');
});
