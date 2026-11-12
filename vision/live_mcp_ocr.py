"""Run saved MCP OCR v3 checkpoints with automatic readout localization.

Example:
 python vision/live_mcp_ocr.py --source 0 --checkpoints vision/checkpoints/mcp_ocr_v3
 python vision/live_mcp_ocr.py --source demo.mp4 --checkpoints vision/checkpoints/mcp_ocr_v3
Keys: H/A manual fallback ROI, R reset, Q quit. Automatic mode is default.
"""
from mcp_preprocessing import prepare_camera_crop, normalize_aligned
import argparse
from collections import deque
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="0", help="Camera index or video file path")
    p.add_argument("--checkpoints", type=Path, default=Path("vision/checkpoints/mcp_ocr_v3"))
    p.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    p.add_argument("--stable-frames", type=int, default=3)
    p.add_argument("--width", type=int, default=0, help="Optional camera capture width")
    p.add_argument("--manual", action="store_true", help="Disable automatic detection; select ROIs with H and A")
    p.add_argument("--yolo-weights", type=Path, default=None, help="Optional trained YOLO MCP best.pt")
    p.add_argument("--yolo-conf", type=float, default=0.5)
    p.add_argument("--debug-ocr", action="store_true", help="Save OCR preprocessing images")
    p.add_argument('--yolo-imgsz',type=int,default=960)
    p.add_argument('--yolo-stable-frames',type=int,default=3)
    p.add_argument('--character-checkpoint',type=Path,help='Explicit shared-character CNN candidate; requires YOLO and fixed minimum safety gates')
    p.add_argument('--window-readouts',action='store_true',help='Use complete glass-backed glyph groups inside the YOLO panel')
    args = p.parse_args()
    if args.character_checkpoint and (not args.yolo_weights or args.manual or args.yolo_conf<.5 or args.yolo_stable_frames<3 or args.stable_frames<3):
        p.error('Character candidate requires automatic YOLO mode, confidence>=.5 and panel/OCR stability>=3')
    if args.window_readouts and not args.yolo_weights:p.error('--window-readouts requires a YOLO panel')
    if args.stable_frames < 1:
        p.error("--stable-frames must be positive")
    try:
        import cv2
        import numpy as np
        import torch
        from torch import nn
        from PIL import Image
        from preprocess_mcp_ocr import align
        from auto_detect_mcp import detect_readouts
        from camera_digit_preprocess import camera_to_amber
    except ImportError as exc:
        p.error(f"Missing dependency: {exc}. Install opencv-python, torch, pillow, numpy")

    class DigitCNN(nn.Module):
        # Same architecture as train_mcp_ocr_v2.py.
        def __init__(self, n):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.Conv2d(128, 128, 3, padding=1), nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, n)),
            )
            self.head = nn.Linear(128, 10)

        def forward(self, x):
            return self.head(self.features(x).squeeze(2).transpose(1, 2))

    character=None
    if args.character_checkpoint:
        from mcp_character_ocr import CharacterOCR
        character=CharacterOCR(args.character_checkpoint,args.device)
    if args.window_readouts or character is not None:
        from mcp_window_readouts import detect_mcp_readouts
        panel_readouts=detect_mcp_readouts
    else:panel_readouts=detect_readouts
    models = {}
    for kind, n in (() if character is not None else (("hdg", 3), ("alt", 5))):
        path = args.checkpoints / f"{kind}_best.pt"
        if not path.is_file():
            p.error(f"Checkpoint not found: {path}")
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if checkpoint.get("kind") != kind or checkpoint.get("digits") != n:
            p.error(f"Unexpected checkpoint metadata: {path}")
        model = DigitCNN(n)
        model.load_state_dict(checkpoint["model"])
        model.to(args.device).eval()
        models[kind] = model

    from mcp_yolo_gate import PanelGate, detect_panel_readouts, validate_detector
    gate=PanelGate(args.yolo_conf,args.yolo_stable_frames)
    yolo = None
    if args.yolo_weights:
        if not args.yolo_weights.is_file():
            p.error(f"Missing YOLO weights: {args.yolo_weights}")
        try:
            from ultralytics import YOLO
        except ImportError:
            p.error("Install ultralytics for --yolo-weights")
        yolo = YOLO(str(args.yolo_weights))
        validate_detector(yolo)

    source = int(args.source) if args.source.isdecimal() else args.source
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        p.error(f"Could not open video source: {args.source}")
    if args.width:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    window = "MCP character CNN AUTO - Q:Quit R:Reset" if character is not None else "MCP OCR v3 AUTO - Q:Quit R:Reset"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    regions = {"hdg": None, "alt": None}
    history = {"hdg": deque(maxlen=args.stable_frames), "alt": deque(maxlen=args.stable_frames)}

    def infer(frame, kind, roi):
        x, y, w, h = roi
        crop = frame[y:y+h, x:x+w]
        if crop.size == 0:
            return None, None
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        # Camera readouts are white/cream, whereas synthetic training digits were amber.
        # Normalize camera colors before applying the original alignment pipeline.
        aligned = prepare_camera_crop(Image.fromarray(rgb), kind)
        if aligned is None:
            return None, None
        # Match training preprocessing: RGB aligned image -> grayscale -> bilinear resize.
        gray = normalize_aligned(aligned, kind)
        n = 3 if kind == "hdg" else 5
        gray = gray.resize((36*n, 48), Image.Resampling.BILINEAR)
        if args.debug_ocr:
            debug_dir = Path("vision/reports/ocr_debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_dir / f"{kind}_raw.png"), crop)
            aligned.save(debug_dir / f"{kind}_aligned.png")
            gray.save(debug_dir / f"{kind}_cnn_input.png")
        if character is not None:
            result=character.infer_aligned(aligned,kind)
            return result['value'],result['model_score']
        tensor = torch.from_numpy(np.asarray(gray, dtype=np.float32).copy()).unsqueeze(0).unsqueeze(0).to(args.device) / 255.
        with torch.no_grad():
            probabilities = models[kind](tensor).softmax(-1)[0]
        digits = probabilities.argmax(-1)
        value = "".join(str(v) for v in digits.tolist())
        confidence = float(probabilities.max(-1).values.min().item())
        return value, confidence

    print("Character CNN + YOLO automatic mode. R reset, Q quit. Model scores are not accuracy." if character is not None else "Automatic HDG/ALT detection enabled. H/A select manual fallback ROIs, R reset, Q quit.",flush=True)
    auto_history = deque(maxlen=5)
    manual_override = False
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("End of video or camera read failed.")
                break
            raw_frame=frame.copy()
            if not args.manual and not manual_override:
                if yolo is None:
                    detected = detect_readouts(frame)
                else:
                    detected,reason=detect_panel_readouts(yolo,frame,gate,panel_readouts,args.device,imgsz=args.yolo_imgsz)
                    if reason:
                        cv2.putText(frame,reason,(12,45),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,180,255),1)
                # Never reuse previous ROIs after low score, motion, partial readouts or detector failure.
                regions={'hdg':None,'alt':None}
                auto_history.append(detected)
                if not detected:
                    regions = {"hdg": None, "alt": None}
                    for h in history.values():
                        h.clear()
                # Require repeated matching candidate positions to avoid jumping between bright UI elements.
                if len(auto_history) >= 3 and all(set(item) == {"hdg", "alt"} for item in list(auto_history)[-3:]):
                    for kind in ("hdg", "alt"):
                        boxes = [item[kind] for item in list(auto_history)[-3:]]
                        centers = [(b[0]+b[2]/2, b[1]+b[3]/2) for b in boxes]
                        tolerance = max(8, frame.shape[1]*.015)
                        if max(x for x,y in centers)-min(x for x,y in centers) <= tolerance and max(y for x,y in centers)-min(y for x,y in centers) <= tolerance:
                            regions[kind] = boxes[-1]
            for kind, color in (("hdg", (0, 230, 255)), ("alt", (255, 190, 40))):
                roi = regions[kind]
                if roi is None:
                    history[kind].clear()
                    continue
                x, y, w, h = roi
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                value, conf = infer(raw_frame, kind, roi)
                if value is None:
                    history[kind].clear()
                    label = f"{kind.upper()}: NO DIGITS"
                else:
                    history[kind].append(value)
                    stable = len(history[kind]) == args.stable_frames and len(set(history[kind])) == 1
                    label = f"{kind.upper()}: {value} {'STABLE' if stable else 'CHECK'} conf={conf:.2f}"
                cv2.putText(frame, label, (max(0, x), max(20, y-8)),
                            cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2, cv2.LINE_AA)
            cv2.putText(frame, "YOLO + character CNN | R: reset | Q: quit" if character is not None else "AUTO detect | H/A: manual fallback | R: reset | Q: quit",
                        (12, max(25, frame.shape[0]-18)), cv2.FONT_HERSHEY_SIMPLEX,
                        .55, (240,240,240), 2, cv2.LINE_AA)
            cv2.imshow(window, frame)
            key = cv2.waitKey(1 if isinstance(source, int) else 30) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                regions = {"hdg": None, "alt": None}
                manual_override = False
                auto_history.clear()
                for h in history.values():
                    h.clear()
            if key in (ord("h"), ord("a")):
                if character is not None:
                    print("Manual ROI override disabled in gated character mode.");continue
                kind = "hdg" if key == ord("h") else "alt"
                # selectROI blocks until ENTER/SPACE; press C to cancel.
                roi = tuple(map(int, cv2.selectROI(window, frame, showCrosshair=True, fromCenter=False)))
                if roi[2] > 0 and roi[3] > 0:
                    regions[kind] = roi
                    manual_override = True
                    history[kind].clear()
                    print(f"{kind.upper()} ROI: {roi}")
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
