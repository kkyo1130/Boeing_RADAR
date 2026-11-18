"""One-page executive summary followed by the complete frozen instruction register."""
import re
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from .register import instruction_register

FONT = 'RADAR-NanumGothic'
_LOCK = Lock()
NAVY = colors.HexColor('#172d42')
MUTED = colors.HexColor('#64737f')
LINE = colors.HexColor('#d7dfe5')
PALE = colors.HexColor('#f2f5f7')
RED = '#a54343'
AMBER = '#906419'
GREEN = '#326c60'
WIDTH = A4[0] - 88


def _value(value):
    return 'Not recorded' if value is None else str(value)


def _time(value):
    # Keep the date: multi-day flights must not have ambiguous time-only rows.
    return re.sub(r'\.(\d+)', lambda match: '.' + match[1].rstrip('0') if match[1].rstrip('0') else '',
                  _value(value).replace('T', ' ').replace('Z', ''))


def render_pdf(safety, *, raw_events=()):
    with _LOCK:
        if FONT not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT, str(Path(__file__).resolve().parents[2] /
                'assets/fonts/NanumGothic-Regular.ttf')))
    styles = {name: ParagraphStyle(name, fontName=font, fontSize=size, leading=leading,
        textColor=NAVY, spaceAfter=0, splitLongWords=True)
        for name, font, size, leading in [('title', 'Times-Roman', 27, 32),
            ('heading', 'Helvetica-Bold', 11, 15), ('body', FONT, 9, 13),
            ('small', FONT, 7.5, 10), ('tiny', FONT, 7, 9),
            ('metric', 'Helvetica', 25, 29)]}

    def p(value, style='body', color=None):
        content = escape(_value(value)).replace('\n', '<br/>')
        if color:
            content = f'<font color="{color}">{content}</font>'
        return Paragraph(content, styles[style])

    def table(rows, widths, *, header=True):
        cells = [[cell if isinstance(cell, (Paragraph, list)) else p(cell, 'small')
                  for cell in row] for row in rows]
        result = Table(cells, colWidths=widths, repeatRows=1 if header else 0,
                       hAlign='LEFT', splitInRow=1)
        commands = [('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LINEBELOW', (0, 0), (-1, -1), .4, LINE)]
        start = 1 if header else 0
        if header:
            commands.append(('BACKGROUND', (0, 0), (-1, 0), NAVY))
            for col, value in enumerate(rows[0]):
                cells[0][col] = p(value, 'tiny', '#ffffff')
            result = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT', splitInRow=1)
        for row in range(start, len(rows)):
            if (row - start) % 2 == 0:
                commands.append(('BACKGROUND', (0, row), (-1, row), PALE))
        result.setStyle(TableStyle(commands))
        return result

    register = instruction_register(safety, raw_events)
    facts = safety['summary']
    traces = safety.get('correction_trace', [])
    refs = {(row['instruction_id'], row['field']): f'I{n:03}'
            for n, row in enumerate(register['items'], 1)}
    source = ('Includes fixture inputs' if safety.get('provenance') == 'FIXTURE_PRESENT'
              else 'Stored inputs; real/synthetic origin not verified')
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=44, rightMargin=44,
        topMargin=73, bottomMargin=51, title='Flight Safety Report', author='')
    story = [p('OVERALL FLIGHT SUMMARY', 'small'), Spacer(1, 10),
        p('Flight Safety Report', 'title'), Spacer(1, 9),
        p(f"Callsign: {safety.get('callsign')} | Session: {safety.get('flight_id')}", 'small'),
        p(f"Started: {_time(safety.get('started_at'))} | Ended: {_time(safety.get('ended_at'))}", 'tiny'),
        p(source + ' | All times UTC', 'tiny'), Spacer(1, 15)]
    metrics = [('ATC INSTRUCTIONS', facts['instruction_count']),
        ('ALT / HDG ITEMS', len(register['items'])),
        ('RESOLVED / INCIDENTS', f"{facts['resolved_count']} / {facts['incident_count']}"),
        ('UNVERIFIED INSTRUCTIONS', facts['unverified_instruction_count'])]
    story += [table([[ [p(value, 'metric'), p(label, 'tiny')] for label, value in metrics]],
                    [WIDTH/4]*4, header=False), Spacer(1, 12)]
    story += [p('01  Recorded outcomes', 'heading'), Spacer(1, 6),
        p(f"The stored record contains {facts['instruction_count']} ATC instruction(s). "
          f"Complete match without incidents: {facts['normal_instruction_count']}; "
          f"instructions with incidents: {facts['error_instruction_count']}; "
          f"unverified: {facts['unverified_instruction_count']}.", 'small'),
        p(f"{facts['resolved_count']} incident(s) resolved. {facts['unresolved_count']} "
          f"{'incident remains' if facts['unresolved_count']==1 else 'incidents remain'} unresolved; "
          f"{facts['superseded_count']} closed by replacement, not correction.", 'small'),
        Spacer(1, 9), table([['ERROR TYPE', 'INCIDENTS', 'SHARE'],
            *[[row['label'], row['count'], f"{row['ratio']:.0%}"] for row in safety.get('classification', [])]],
            [WIDTH*.6, WIDTH*.2, WIDTH*.2]), Spacer(1, 12),
        p('02  Key events and corrections', 'heading'), Spacer(1, 6)]
    # A bounded summary stays on page one, but every incident is in the register.
    selected = sorted(traces, key=lambda r: (r['state'] == 'RESOLVED', r.get('detected_at') or ''))[:3]
    if selected:
        rows = [['DETECTED / REF', 'EVENT', 'TARGET / INITIAL', 'OUTCOME']]
        for row in selected:
            ref = refs.get((row['instruction_id'], row['field']), 'Other incident')
            outcome = row.get('stored_status') if row.get('stored_status') == 'SUPERSEDED' else row['state']
            rows.append([f"{_time(row.get('detected_at'))}\n{ref}",
                f"{row['stage']} / {row['field']}",
                f"{_value(row.get('expected'))} / {_value(row.get('initial_actual'))}",
                p(outcome + '\nResolved: ' + _time(row.get('resolved_at')), 'tiny',
                  GREEN if row['state'] == 'RESOLVED' else RED)])
        story.append(table(rows, [WIDTH*.27, WIDTH*.23, WIDTH*.22, WIDTH*.28]))
        story.append(p(f'Showing {len(selected)} of {len(traces)} incidents, unresolved first. All incidents follow in the register.', 'tiny'))
    else:
        story.append(p('No recorded incidents. Missing inputs are not classified as normal.', 'small'))
    story += [Spacer(1, 12), p('03  Debrief focus', 'heading'), Spacer(1, 6),
        p(f"Readback incidents: {facts['readback_error_count']}. Cockpit setting incidents: "
          f"{facts['setting_error_count']}. Review the linked instruction, observed values and correction evidence.", 'small'),
        Spacer(1, 8), p('Route and flight phase are not recorded. No location or phase is inferred. '
            'Counts describe stored records, not pilot proficiency or model accuracy.', 'tiny'),
        p('Instructions and ALT/HDG items are different counts. Log checks are the latest stored snapshot; '
          'historical complete matches and incidents remain in the summary. Selected altitude is not actual altitude.', 'tiny'),
        PageBreak(), p('Complete instruction register', 'title'), Spacer(1, 7),
        p('ALT: feet | HDG: degrees | UTC | Readback and cockpit values include their stored verdicts.', 'small'),
        p('Times under values are observation times; Check time is validation time. Unknown provenance stays Not recorded. '
          'Repeated identical camera frames are not additional instruction items.', 'tiny'), Spacer(1, 10)]

    def observed(check):
        if not check:
            return p('Not recorded\nUNVERIFIED', 'tiny', AMBER)
        status = check.get('result', 'UNVERIFIED')
        color = GREEN if status == 'NORMAL' else RED if status == 'MISMATCH' else AMBER
        return p(f"{_value(check.get('actual'))}\n{_time(check.get('observed_at'))}\n"
                 f"{status}\n{check.get('reason') or 'Not recorded'}", 'tiny', color)

    def incident_detail(row):
        warned = next((step.get('at') for step in row.get('steps', [])
                       if step['state'] == 'WARNED'), None) if row.get('warning_completed') else None
        status = row.get('stored_status') if row.get('stored_status') == 'SUPERSEDED' else row['state']
        return p(f"{refs.get((row['instruction_id'], row['field']), 'Other incident')} | Incident {row['occurrence_id']} | {row['stage']} / {row['field']} | {status}\n"
            f"Detected: {_time(row.get('detected_at'))} | Target / initial: "
            f"{_value(row.get('expected'))} / {_value(row.get('initial_actual'))}\n"
            f"Last actual: {_value(row.get('final_actual'))} | Last verdict: {row.get('verification')}\n"
            f"Resolved: {_time(row.get('resolved_at'))} | Seconds from detection: {_value(row.get('resolution_seconds'))}\n"
            f"Warning playback completed: {_time(warned)}", 'tiny',
            GREEN if row['state'] == 'RESOLVED' else RED)

    rows = [['REF / ISSUED', 'ATC TARGET', 'READBACK', 'COCKPIT', 'LATEST CHECK']]
    for n, row in enumerate(register['items'], 1):
        call = row.get('callsign') or {}
        rows.append([p(f"I{n:03}\n{_time(row['issued_at'])}\n{row['instruction_id'] or 'Unlinked instruction'}", 'tiny'),
            p(f"{row['field']} {_value(row['expected'])}", 'small'), observed(row['readback']),
            observed(row['cockpit']), p(f"{_time(row['checks_at'])}\nCallsign: {call.get('result') or 'UNVERIFIED'}\n"
                f"{call.get('reason') or 'Not recorded'}\nIncidents: {len(row['incidents'])}", 'tiny')])
        for incident in row['incidents']:
            # A full-width detail row follows its item; recurrence stays distinct.
            rows.append([incident_detail(incident), '', '', '', ''])
    if len(rows) > 1:
        log = table(rows, [WIDTH*.22, WIDTH*.15, WIDTH*.21, WIDTH*.21, WIDTH*.21])
        for idx, row in enumerate(rows):
            if idx and row[1:] == ['', '', '', '']:
                log.setStyle(TableStyle([('SPAN', (0, idx), (-1, idx)),
                    ('BACKGROUND', (0, idx), (-1, idx), colors.white)]))
        story.append(log)
    else:
        story.append(p('No applied ALT/HDG instruction items are available in the frozen record.'))
    if register['orphan_incidents']:
        story += [Spacer(1, 12), p('Additional recorded incidents', 'heading')]
        for incident in register['orphan_incidents']:
            story += [p('Instruction: ' + incident['instruction_id'], 'tiny'), incident_detail(incident), Spacer(1, 8)]
    story += [Spacer(1, 10), p('Unavailable and stale inputs remain unverified. A resolved incident does not certify '
        'complete flight verification. Full input events, rejected inputs and transcripts remain in the original JSON.', 'tiny')]

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(44, A4[1]-55, A4[0]-44, A4[1]-55)
        canvas.line(44, 39, A4[0]-44, 39)
        canvas.setFillColor(MUTED)
        canvas.setFont('Helvetica', 7)
        canvas.drawRightString(A4[0]-44, A4[1]-37, 'FLIGHT ANALYSIS / SIMULATION SUPPORT RECORD')
        canvas.drawString(44, 25, 'FLIGHT SAFETY REPORT / UTC')
        canvas.drawRightString(A4[0]-44, 25, f'Page {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()
