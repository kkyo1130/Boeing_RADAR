"""Paginated English PDF from exactly the same frozen safety report as the UI."""
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape
from app.services.reports.summary import english_summary
from .presentation import error_timeline
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Flowable

FONT='RADAR-NanumGothic'
_LOCK=Lock()
NAVY=colors.HexColor('#142c42');RED=colors.HexColor('#b4323e');GREEN=colors.HexColor('#167457')

class ClassificationBar(Flowable):
    def __init__(self,items):
        super().__init__();self.items=items;self.width=510;self.height=60
    def draw(self):
        c=self.canv;c.setFont(FONT,9)
        for i,item in enumerate(self.items):
            y=42-i*26;c.setFillColor(NAVY);c.drawString(0,y,item['label'])
            c.setFillColor(colors.HexColor('#e5ebef'));c.rect(170,y-2,260,12,fill=1,stroke=0)
            c.setFillColor(RED);c.rect(170,y-2,260*item['ratio'],12,fill=1,stroke=0)
            c.setFillColor(NAVY);c.drawString(438,y,f"{item['count']} / {item['ratio']:.1%}")


def render_pdf(safety,*,raw_events=()):
    with _LOCK:
        if FONT not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT,str(Path(__file__).resolve().parents[2]/'assets/fonts/NanumGothic-Regular.ttf')))
    styles={name:ParagraphStyle(name,fontName=FONT,fontSize=size,leading=leading,textColor=NAVY,
        wordWrap='LTR',spaceAfter=6,keepWithNext=name in ('title','heading')) for name,size,leading in
        [('title',21,28),('heading',13,20),('body',9,14),('small',7.5,11)]}
    def p(text,style='body'):
        value='Not recorded' if text is None else str(text)
        # Escape transcripts and all user strings before ReportLab markup parsing.
        text=escape(value).replace('\n','<br/>')
        if value.startswith(('RESOLVED','NORMAL')):text='<font color="#167457">'+text+'</font>'
        elif value.startswith(('UNRESOLVED','MISMATCH')):text='<font color="#b4323e">'+text+'</font>'
        return Paragraph(text,styles[style])
    output=BytesIO();doc=SimpleDocTemplate(output,pagesize=A4,leftMargin=38,rightMargin=38,
        topMargin=60,bottomMargin=45,title='Flight Safety Report',author='')
    width=A4[0]-76
    def table(rows,widths=None):
        result=Table([[p(cell,'small') for cell in row] for row in rows],colWidths=widths or [width/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign='LEFT')
        result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eef3')),
            ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd6df')),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        return result
    story=[p('Flight Safety Report','title'),p(f"Session {safety['flight_id']} | Callsign {safety['callsign']}"),
        p(f"Started: {safety['started_at']}\nEnded: {safety['ended_at']}\nGenerated: {safety['generated_at']}",'small'),
        p('Simulation support record | All times UTC | '+('Includes fixture inputs' if safety['provenance']=='FIXTURE_PRESENT' else 'Stored inputs; real/synthetic origin not verified'),'small')]
    facts=safety['summary'];rate=f"{facts['correction_rate']:.1%}" if facts['correction_rate'] is not None else 'Not applicable (no incidents)'
    story += [p('1. Flight Summary','heading'),table([
        ['Metric','Stored result'],['Total ATC instructions',facts['instruction_count']],['Complete-match instructions without incidents',facts['normal_instruction_count']],
        ['Instructions with incidents / Unverified instructions',f"{facts['error_instruction_count']} / {facts['unverified_instruction_count']}"],
        ['Incidents / Resolved incidents',f"{facts['incident_count']} / {facts['resolved_count']}"],
        ['Unresolved / Including superseded incidents',f"{facts['unresolved_count']} / {facts['superseded_count']}"],['Incident resolution rate',rate]]),Spacer(1,12)]
    story += [p('Error Classification','heading'),ClassificationBar(safety['classification']),
        table([['Error type','Count','Share']]+[[i['label'],i['count'],f"{i['ratio']:.1%}"] for i in safety['classification']]),Spacer(1,12),
        p('2. Correction Trace','heading')]
    if not safety['correction_trace']:story.append(p('No stored incidents. Missing inputs have not been classified as normal.'))
    for item in safety['correction_trace']:
        story.append(p(f"{item['stage']} / {item['field']} · {item['state']}"))
        story.append(p(f"Incident: {item['occurrence_id']}\nInstruction: {item['instruction_id']}\nTarget: {item['expected']} | First observed: {item['initial_actual']} | Last observed: {item['final_actual']}\nLast validation: {item['verification']} | Resolved at: {item['resolved_at'] or 'Not recorded'}",'small'))
        story.append(p(f"Readback: {item.get('readback_actual')} | Cockpit: {item.get('cockpit_actual')} | Resolution seconds: {item.get('resolution_seconds')}",'small'))
        story.append(Spacer(1,8))
    story += [p('3. Error Timeline','heading'),p('One incident per timeline. Repeated observations and full input/validation records are available in the screen details and original JSON. Missing warning or correction evidence is not completion.','small')]
    for incident in error_timeline(safety['correction_trace']):
        story.append(p(f"{incident['stage']} / {incident['field']} | {incident['occurrence_id']}",'small'))
        story.append(table([['Milestone','Recorded time (UTC)','Count']]+[
            [step['state'],step.get('at') or 'Not recorded',str(step['count'])] for step in incident['milestones']]))
    if not safety['correction_trace']:story.append(p('No stored error incidents. Missing inputs are not classified as normal.'))
    ai=safety['ai_summary']
    story += [p('4. AI Safety Summary','heading'),p('AI-assisted factual summary (English rendering)' if ai['source']=='AI_ASSISTED_FACTS' else 'Rule-based summary (AI unavailable or response not verified)','small'),p(ai.get('text_en') or english_summary(facts,ai.get('fact_ids'))),p('Missing data is not verifiable. Advisory eligibility and completed playback are separate records. This report does not certify safety for actual flight operations.','small'),
        p(f"Ended flight record | Generated: {safety['generated_at']}",'small')]
    def decorate(canvas,document):
        canvas.saveState();canvas.setStrokeColor(NAVY);canvas.circle(45,A4[1]-29,8);canvas.line(33,A4[1]-29,57,A4[1]-29);canvas.line(45,A4[1]-41,45,A4[1]-17)
        canvas.setFont(FONT,7)
        canvas.drawString(38,25,'SIMULATION RECORD / UTC');canvas.drawRightString(A4[0]-38,25,f'Page {document.page}')
        canvas.restoreState()
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    return output.getvalue()
