// Convert pointer coordinates to the exact encoded frame coordinate system.
export function framePoint(x,y,rect,width,height){
 if(rect.width<=0||rect.height<=0||width<=0||height<=0)throw Error('영상 크기를 확인하세요.');
 return [Math.round(Math.max(0,Math.min(1,(x-rect.left)/rect.width))*width),Math.round(Math.max(0,Math.min(1,(y-rect.top)/rect.height))*height)];
}
export function selectedBox(start,end){
 const box=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];
 if(box[2]-box[0]<10||box[3]-box[1]<10)throw Error('숫자 창 전체를 10픽셀 이상 선택하세요.');
 return box;
}
