# Local camera tracking response

Existing opt-in `/api/demo/{flight}/frame` accepts calibration token, image, UTC `captured_at`, target revision and optional finite nonnegative `media_time`.

2026-11-16 additive response fields:

- `rois`: `{"ALT":[x1,y1,x2,y2],"HDG":[x1,y1,x2,y2]}` in the submitted image's pixel coordinates, or `null` when no current valid region exists.
- `tracking_status`: `TRACKING` when the current image has valid regions, otherwise `SEARCHING`. This is geometry status, never a NORMAL verdict or OCR accuracy measure. OCR fields can remain unreadable while TRACKING.

AUTO localizes both windows again from each submitted image, without instruction values or previous coordinates as fallback. MANUAL uses panel texture outside the digit windows and updates its reference after valid translation. Large jumps, loss, stale frames, source resumption and changed targets reset three-frame confirmation. Manual scale/rotation recovery is not claimed; failure remains unreadable and requires re-setting the selected regions if needed.

Loss returns null fields and null regions, stores an unreadable observation and DEGRADED camera health, and does not OCR old coordinates. Fresh subsequent frames can recover on the same token. A resumed expired session requires fresh timestamps and a new three-frame sequence. Duplicate/out-of-order capture and media timestamps remain rejected. The former 600-frame demo stop is removed; cache size and calibration expiry remain bounded.

Browser drawing uses each response's current ROIs. Searching, transient capture gaps and tab visibility changes do not terminate the recognition loop. Missing fresh frames clears the displayed result and degrades health; backend watchdog and freshness rules continue to prevent stale NORMAL. A hidden tab may be throttled by the browser: continued real capture is not guaranteed merely by keeping the loop scheduled.
