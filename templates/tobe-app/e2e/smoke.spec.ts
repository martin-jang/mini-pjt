// 템플릿 동작 확인: MSW 응답이 화면에 표시되는지 (생성 시 happy_path.spec.ts로 교체)
import { expect, test } from '@playwright/test'

test('MSW mock 응답이 화면에 표시된다', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('sample-message')).toHaveText('MSW 동작 확인')
})
