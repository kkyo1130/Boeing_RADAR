import { useEffect, useRef } from 'react';

// Run inside the tablet's CockpitVision component.
export function useMcpAutoControl(setValues) {
  const seen = useRef(0);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const response = await fetch('/api/mcp-auto/state', { cache: 'no-store' });
        if (!response.ok) return;
        const state = await response.json();
        if (!alive || !state.seq || state.seq === seen.current) return;
        seen.current = state.seq;
        setValues(v => ({ ...v, heading: state.heading, altitude: state.altitude }));
        // Wait for React and Three.js to paint the new digits.
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        if (!alive) return;
        await fetch('/api/mcp-auto/ack', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ seq: state.seq }),
        });
      } catch (error) { console.warn('MCP auto control polling:', error); }
    };
    tick();
    const interval = setInterval(tick, 250);
    return () => { alive = false; clearInterval(interval); };
  }, [setValues]);
}
