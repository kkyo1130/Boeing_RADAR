// MCP is the enclosing group of observed ALT/HDG windows, not a panel classifier.
export function recognitionBoxes(rois, [width, height], [targetWidth, targetHeight]) {
  if (![width, height, targetWidth, targetHeight].every(n => Number.isFinite(n) && n > 0)) return [];
  const valid = box => Array.isArray(box) && box.length === 4 && box.every(Number.isFinite)
    && box[0] >= 0 && box[1] >= 0 && box[0] < box[2] && box[1] < box[3]
    && box[2] <= width && box[3] <= height;
  if (!valid(rois?.hdg) || !valid(rois?.alt)) return [];
  const hdg = rois.hdg, alt = rois.alt;
  const pad = Math.max(hdg[3] - hdg[1], alt[3] - alt[1]) * .4;
  const mcp = [Math.max(0, Math.min(hdg[0], alt[0]) - pad),
    Math.max(0, Math.min(hdg[1], alt[1]) - pad),
    Math.min(width, Math.max(hdg[2], alt[2]) + pad),
    Math.min(height, Math.max(hdg[3], alt[3]) + pad)];
  return [['MCP · ALT/HDG', mcp, '#80baff'], ['HDG', hdg, '#ffbc66'], ['ALT', alt, '#63e6b5']]
    .map(([label, box, color]) => ({ label, color,
      box: box.map((value, index) => value * (index % 2 ? targetHeight / height : targetWidth / width)) }));
}

export function drawRecognitionBoxes(canvas, rois, imageSize, videoSize) {
  canvas.width = videoSize[0]; canvas.height = videoSize[1];
  const ctx = canvas.getContext('2d');
  const boxes = recognitionBoxes(rois, imageSize, videoSize);
  const lineWidth = Math.max(2, canvas.width / 400), fontSize = Math.max(16, canvas.width / 65);
  ctx.lineWidth = lineWidth; ctx.font = `bold ${fontSize}px sans-serif`;
  for (const { label, box: [x, y, right, bottom], color } of boxes) {
    ctx.strokeStyle = color; ctx.strokeRect(x, y, right - x, bottom - y);
    const textWidth = ctx.measureText(label).width + 12;
    const labelX = Math.min(x, Math.max(0, canvas.width - textWidth));
    const labelY = y >= fontSize + 12 ? y - fontSize - 10 : y + 4;
    ctx.fillStyle = '#07131fed'; ctx.fillRect(labelX, labelY, textWidth, fontSize + 8);
    ctx.fillStyle = color; ctx.fillText(label, labelX + 6, labelY + fontSize + 1);
  }
}
