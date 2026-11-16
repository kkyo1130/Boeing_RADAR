import {test,expect} from '@playwright/test';

test('compact Vision MCP preserves zero input, ray picking and camera presets',async({page})=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/cockpit');
 await expect(page.locator('.cockpit-3d')).toHaveAttribute('data-state','ready');
 await page.getByRole('button',{name:'MCP 정면',exact:true}).click();
 const canvas=page.locator('.cockpit-3d canvas');const box=await canvas.boundingBox();
 // Project the HDG screen center using the unchanged MCP camera preset.
 const distance=Math.max(16,6.8/(Math.tan(16*Math.PI/180)*(box.width/box.height)));
 const pixels=box.height/(2*(distance-.208)*Math.tan(16*Math.PI/180));
 page.once('dialog',dialog=>dialog.accept('0'));
 await page.mouse.click(box.x+box.width/2+(-.35*1.05)*pixels,box.y+box.height/2-(.5*.8)*pixels);
 await expect(page.getByRole('button',{name:'HEADING 0',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'조종석 시점',exact:true}).click();
 await expect(page.getByRole('button',{name:'HEADING 0',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'전체 조종석',exact:true}).click();
 await expect(page.getByRole('button',{name:'전체 조종석',exact:true})).toHaveAttribute('aria-pressed','true');
 expect(errors).toEqual([]);
});
