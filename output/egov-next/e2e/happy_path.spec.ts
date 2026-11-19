// Legacy2Next가 happy_paths.json 에서 결정적으로 생성한 흐름 검증입니다.
import { expect, test } from '@playwright/test'

test('hp1 공지사항 조회', async ({ page }) => {
  await page.goto('/login?next=/mainpage')
  // hp1-s1 로그인 (login)
  await expect(page.getByTestId('egovloginusr-page')).toBeVisible()
  await page.getByTestId('egovloginusr-field-id').fill('1')
  await page.getByTestId('egovloginusr-field-password').fill('demo')
  await page.getByTestId('egovloginusr-submit').first().click()
  // hp1-s2 메인 홈(대시보드) (view)
  await expect(page.getByTestId('mainpage-page')).toBeVisible()
  await page.getByTestId('mainpage-to-bbsSelectboardlist').first().click()
  // hp1-s3 공지사항 목록 (view)
  await expect(page.getByTestId('bbsSelectboardlist-page')).toBeVisible()
})
