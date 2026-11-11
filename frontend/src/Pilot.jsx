import React, { useState } from 'react';
import { useFlight } from './Operations.jsx';
import { numberLabel } from './flight-client.js';
import './pilot.css';
const pilotValue = (value, field) => value == null ? 'Unavailable' : numberLabel(value, field);
const labels = { ALT: 'Altitude', HDG: 'Heading', CALLSIGN: 'Callsign' };
const reasons = { STALE_OBSERVATION: 'Awaiting fresh observation', CHANNEL_UNAVAILABLE: 'Check input device', INPUT_QUALITY_UNVERIFIED: 'Check input quality', INPUT_NOT_AVAILABLE: 'Awaiting input', TARGET_NOT_AVAILABLE: 'Awaiting ATC instruction', READBACK_NOT_CONFIRMED: 'Awaiting readback confirmation', LATEST_READBACK_UNVERIFIED: 'Awaiting new readback', LATEST_ATC_NOT_ADOPTED: 'Awaiting new ATC review' };
export function PilotDisplay({ snapshot, connected }) {
  const ended = snapshot?.status === 'ENDED';
  const usable = connected && snapshot && !ended;
  // Server verdicts only: no numeric comparison or local incident resolution.
  const rows = usable ? [['readback', 'Readback'], ['setting', 'MCP setting']].flatMap(([key, stage]) => snapshot.validation[key].fields.filter(row => row.result !== 'NORMAL').map(row => ({ ...row, stage, stageKey: key }))) : [];
  rows.sort((a, b) => Number(b.result === 'MISMATCH') - Number(a.result === 'MISMATCH'));
  const devices = usable ? [['CAMERA', 'Camera'], ['MICROPHONE', 'Microphone'], ['SPEECH_API', 'Speech processing']].filter(([key]) => ['DISCONNECTED', 'DEGRADED', 'UNKNOWN'].includes(snapshot.channels[key]?.status)) : [];
  const mismatch = rows.some(row => row.result === 'MISMATCH');
  const normal = usable && snapshot.result === 'NORMAL' && !rows.length && !devices.length;
  const hold = usable && snapshot.result === 'UNVERIFIED';
  const holdReason = reasons[snapshot?.reason || snapshot?.validation?.reason] || 'Recheck with new input';
  const heading = !connected ? 'Check connection' : !snapshot ? 'Loading flight status' : ended ? 'Flight ended' : hold ? 'Unverified' : mismatch ? 'Check required' : normal ? 'Matches ATC' : 'Checking';
  return <section className={`pilot-display ${normal ? 'pilot-normal' : mismatch ? 'pilot-mismatch' : 'pilot-unverified'}`} aria-label="Pilot status" aria-live="polite" aria-atomic="true">
    <div className="pilot-status"><span className="pilot-dot" />{heading}{hold && <span className="pilot-hold-reason"> · {holdReason}</span>}</div>
    {!usable ? <div className="pilot-empty"><h1>{ended && connected ? 'Flight ended' : 'Status unavailable'}</h1><p>{ended && connected ? 'Select the next flight in Operations' : 'Rechecking when connected to the server'}</p></div> : <>
      <div className={`pilot-cards ${rows.length > 1 ? 'pilot-multiple' : ''}`}>{rows.map(row => <article className={`pilot-card pilot-${row.result.toLowerCase()}`} key={`${row.stageKey}/${row.instruction_id}/${row.field}`}>
        <p className="pilot-stage">{row.stage}</p><h1>{labels[row.field]} <span>{row.result === 'MISMATCH' ? 'Mismatch' : row.reason === 'INITIAL_ADJUSTMENT_WAIT' ? 'Adjustment pending' : 'Unverified'}</span></h1>
        {row.result === 'MISMATCH' ? <dl className="pilot-values"><div><dt>{row.stageKey === 'readback' ? 'ATC' : 'Instruction'}</dt><dd>{pilotValue(row.expected, row.field)}</dd></div><div><dt>{row.stageKey === 'readback' ? 'Readback' : 'MCP selected'}</dt><dd>{pilotValue(row.actual, row.field)}</dd></div></dl> : <p className="pilot-reason">{row.reason === 'INITIAL_ADJUSTMENT_WAIT' ? 'Awaiting setting change' : reasons[row.reason] || 'Recheck with new input'}</p>}
      </article>)}</div>
      {!rows.length && <div className="pilot-empty"><h1>{normal ? 'Matches ATC' : snapshot.validation.phase === 'WAITING_ATC' ? 'Awaiting ATC instruction' : 'Unverified'}</h1><p>{normal ? 'Readback · MCP setting' : 'Awaiting new input'}</p></div>}
      {devices.length > 0 && <div className="pilot-devices">{devices.map(([key, label]) => <p key={key}>{label} · {{ DISCONNECTED: 'Disconnected', DEGRADED: 'Degraded', UNKNOWN: 'Status unknown' }[snapshot.channels[key].status]}</p>)}</div>}
    </>}
  </section>;
}
function initialFlight() { return typeof window === 'undefined' ? '' : new URLSearchParams(window.location.search).get('flight') || ''; }
export default function Pilot() {
  const [flightId, setFlightId] = useState(initialFlight), [draft, setDraft] = useState(''), [refresh, setRefresh] = useState(0);
  const { snapshot, connected } = useFlight(flightId, refresh);
  return <main className="pilot-shell" lang="en"><header className="pilot-header"><a href="/operations">RADAR</a><span>{snapshot?.callsign || 'PILOT DISPLAY'}</span><a href="/operations">Operations</a></header>
    {flightId ? <><PilotDisplay snapshot={snapshot} connected={connected} />{!connected && <button className="pilot-reconnect" onClick={() => setRefresh(value => value + 1)}>Reconnect</button>}</> : <form className="pilot-connect" onSubmit={event => { event.preventDefault(); if (draft.trim()) { const id = draft.trim(); window.history.replaceState(null, '', `/pilot?flight=${encodeURIComponent(id)}`); setFlightId(id); } }}>
      <h1>Connect to flight</h1><p>Open the pilot display from Operations, or enter a flight ID.</p><label htmlFor="pilot-flight">Flight ID</label><input id="pilot-flight" required value={draft} maxLength={160} onChange={event => setDraft(event.target.value)} /><button disabled={!draft.trim()}>Connect</button>
    </form>}<footer className="pilot-footer">Simulation · MCP selected values</footer></main>;
}
