import { useEffect, useRef, useCallback } from 'react';

// ACK only from the explicitly selected camera-facing display, after Three.js renders.
export function useMcpAutoControl(setValues) {
  const rendered = useRef(null);
  const onRendered = useCallback(values => { rendered.current = { ...values, at: performance.now() }; }, []);
  useEffect(() => {
    const client = new URLSearchParams(location.search).get('display');
    if (!client) return;
    let alive = true, timer;
    const tick = async () => {
      try {
        const response = await fetch('/api/mcp-auto/state', { cache: 'no-store', signal: AbortSignal.timeout(1000) });
        if (!response.ok) throw Error('Sync unavailable');
        const state = await response.json();
        if (alive && state.seq && state.client === client) {
          setValues(v => v.heading === state.heading && v.altitude === state.altitude ? v :
            { ...v, heading: state.heading, altitude: state.altitude });
          const frame = rendered.current;
          if (document.visibilityState === 'visible' && frame && performance.now() - frame.at < 500 &&
              frame.heading === state.heading && frame.altitude === state.altitude) {
            await fetch('/api/mcp-auto/ack', { method: 'POST', headers: { 'Content-Type': 'application/json' },
              signal: AbortSignal.timeout(1000), body: JSON.stringify({ seq: state.seq, client,
                heading: frame.heading, altitude: frame.altitude }) });
          }
        }
      } catch { /* Missing ACK expires at the server; collection fails closed. */ }
      finally { if (alive) timer = setTimeout(tick, 200); }
    };
    tick(); return () => { alive = false; clearTimeout(timer); };
  }, [setValues]);
  return onRendered;
}
