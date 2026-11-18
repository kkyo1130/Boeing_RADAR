import {test,expect} from '@playwright/test';

test('light/dark changes backgrounds, persists after reload and keeps print light',async({page},testInfo)=>{
 await page.goto('/operations');
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 await expect(page.locator('.op-panel').first()).toHaveCSS('background-color','rgb(255, 255, 255)');
 await page.getByRole('button',{name:/다크 모드/}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await expect(page.locator('.op-panel').first()).toHaveCSS('background-color','rgb(16, 35, 56)');
 await expect(page.getByRole('button',{name:/라이트 모드/})).toHaveAttribute('aria-pressed','true');
 await page.screenshot({path:testInfo.outputPath('dark.png'),fullPage:true});
 await page.route('**/api/demo/status',route=>route.fulfill({json:{speech_ready:true,camera_ready:true}}));
 await page.getByLabel('등록된 호출부호').fill('RADAR123');
 await page.getByRole('button',{name:'START FLIGHT',exact:true}).click();
 await expect(page.locator('.demo-results')).toBeVisible();
 await expect(page.locator('.demo-results')).toHaveCSS('background-color','rgb(16, 35, 56)');
 await expect(page.locator('.demo-result').first()).toHaveCSS('background-color','rgb(18, 43, 65)');
 await page.screenshot({path:testInfo.outputPath('dark-active.png'),fullPage:true});
 await page.reload();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await page.emulateMedia({media:'print'});
 await expect(page.locator('.operations')).toHaveCSS('color','rgb(17, 17, 17)');
 await page.emulateMedia({media:'screen'});
 await page.getByRole('button',{name:/라이트 모드/}).click();
 await expect(page.locator('.op-panel').first()).toHaveCSS('background-color','rgb(255, 255, 255)');
 await page.reload();
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 await page.screenshot({path:testInfo.outputPath('light.png'),fullPage:true});
});

test('mode still changes when browser storage is unavailable',async({page})=>{
 await page.addInitScript(()=>{Storage.prototype.setItem=()=>{throw new DOMException('Blocked','SecurityError');};});
 await page.goto('/operations');
 await page.getByRole('button',{name:/다크 모드/}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
 await page.getByRole('button',{name:/라이트 모드/}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
});
