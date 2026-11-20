import { expect, test } from '@playwright/test';

// T04 완료 기준: 실제 에이전트 서버의 스텁 그래프가 콘솔에서 처음부터 끝까지 돌고, 승인 → 재개가 된다

test('실제 서버: 새 요청 → 승인 2곳 → 결과', async ({ page }) => {
  const alias = `real-${Date.now() % 100000}`;
  await page.goto('/new');
  await page.getByTestId('input-url').fill('https://legacy.example.com');
  await page.getByTestId('input-alias').fill(alias);
  await page.getByTestId('submit-request').click();
  await expect(page).toHaveURL(new RegExp(`/sites/${alias}$`));
  await expect(page.getByTestId(`site-${alias}`)).toBeVisible();
  await expect(page.getByTestId('log-viewer')).toContainText('[explorer]');

  // 승인 1
  await page.getByTestId('go-analysis-review').click({ timeout: 20_000 });
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
