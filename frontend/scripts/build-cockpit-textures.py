"""Original schematic cockpit textures, drawn procedurally; no photo pixels used."""
from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import math,random
OUT=Path(__file__).parent/'textures';OUT.mkdir(exist_ok=True)
FONT=next((p for p in ['/System/Library/Fonts/Menlo.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'] if Path(p).exists()),None)
def font(n):return ImageFont.truetype(FONT,n) if FONT else ImageFont.load_default(size=n)
def setup(w=1024,h=1024,bg='#030707'):
 im=Image.new('RGB',(w,h),bg);return im,ImageDraw.Draw(im)
def text(d,xy,s,size=24,fill='#dbe6df',anchor='mm'):d.text(xy,s,font=font(size),fill=fill,anchor=anchor)
def save(im,name):im.save(OUT/(name+'.png'),optimize=True)
im,d=setup()
# PFD: sky/earth attitude sphere, speed and altitude tapes, flight director, FMA.
d.rectangle((235,165,785,735),fill='#925834');d.rectangle((235,165,785,447),fill='#186eb1')
d.line((235,447,785,447),fill='white',width=4)
for n in range(-4,5):
 y=447+n*42;w=100 if n%2==0 else 55;d.line((510-w,y,510+w,y),fill='white',width=3)
 if n and n%2==0:text(d,(510-w-25,y),str(abs(n)*5),19)
d.arc((304,175,716,587),200,340,fill='white',width=4)
for i in range(-4,5):
 a=math.radians(i*15);x=510+math.sin(a)*205;y=381-math.cos(a)*205
 d.line((x,y,x+math.sin(a)*16,y-math.cos(a)*16),fill='white',width=3)
d.polygon([(510,177),(495,199),(525,199)],fill='#f7f7ec')
for x in [185,838]:d.rectangle((x-52,164,x+52,738),fill='#282d2e')
for i in range(-5,6):
 y=449+i*49;d.line((202,y,232,y),fill='white',width=3);text(d,(165,y),str(250-i*10),22)
 d.line((788,y,815,y),fill='white',width=3);text(d,(855,y),str(3000-i*100),20)
for box,value in [((113,420,231,474),'250'),((787,420,906,474),'3000')]:d.rectangle(box,fill='black',outline='white',width=3);text(d,((box[0]+box[2])/2,447),value,28)
d.line((376,449,454,449,454,468),fill='#f4d85d',width=7);d.line((645,449,568,449,568,468),fill='#f4d85d',width=7)
d.line((510,365,510,525),fill='#e35acf',width=5);d.line((415,447,605,447),fill='#e35acf',width=5)
for x,s in [(230,'MCP SPD'),(510,'HDG SEL'),(800,'ALT HOLD')]:text(d,(x,60),s,27,'#65ec8a');d.line((x-120,94,x+120,94),fill='#8b9692',width=2)
text(d,(181,128),'250',28,'#e787e8');text(d,(843,128),'3000',28,'#e787e8');text(d,(510,123),'CMD',26,'#68e78d')
d.rectangle((235,775,785,898),fill='#131b1c')
for i in range(-5,6):x=510+i*48;d.line((x,785,x,810),fill='white',width=3);text(d,(x,842),str((270+i*10)%360).zfill(3),20)
d.polygon([(510,778),(494,759),(526,759)],fill='white');text(d,(510,935),'270 MAG',30,'#6ee5dd');save(im,'pfd')
im,d=setup()
text(d,(160,48),'GS 250 TAS 250',24);text(d,(840,48),'TRK 270 MAG',24,'#70edb0')
cx,cy=512,790
for radius in [220,440,650]:d.arc((cx-radius,cy-radius,cx+radius,cy+radius),205,335,fill='#c9d9d0',width=2)
for deg in range(-60,61,5):
 a=math.radians(deg);r=650;x=cx+math.sin(a)*r;y=cy-math.cos(a)*r;length=22 if deg%10==0 else 12;d.line((x,y,x+math.sin(a)*length,y-math.cos(a)*length),fill='white',width=3)
 if deg%30==0:text(d,(cx+math.sin(a)*(r+48),cy-math.cos(a)*(r+48)),str((270+deg)%360).zfill(3),25)
route=[(512,790),(512,575),(450,395),(578,240),(550,170)];d.line(route,fill='#e071d3',width=5)
for x,y in route[1:]:d.polygon([(x,y-10),(x+10,y),(x,y+10),(x-10,y)],outline='#d87bdd');text(d,(x+65,y),'FIX'+str(y),17,'#9bb9ec')
d.polygon([(512,750),(493,809),(512,795),(531,809)],fill='white');text(d,(100,930),'VOR 1',25,'#64ed8f');text(d,(885,930),'VOR 2',25,'#64ed8f');text(d,(512,970),'MAP  10 NM',24,'#61cbd9');save(im,'nd')
im,d=setup();text(d,(512,62),'ENGINE / SYSTEM',32,'#dbebe9')
for j,label in enumerate(['N1','EGT','N2','FUEL FLOW']):
 y=220+j*170;text(d,(512,y-20),label,23,'#55d4e3')
 for x in [270,755]:
  d.arc((x-95,y-95,x+95,y+95),130,400,fill='#e9efe8',width=4);a=math.radians(300);d.line((x,y,x+math.cos(a)*82,y+math.sin(a)*82),fill='#e9efe8',width=5);text(d,(x,y+35),['92.1','640','88.0','2.45'][j],27)
text(d,(512,927),'FUEL QTY  12.40',30);save(im,'engine')
im,d=setup(768,1024);text(d,(384,70),'IDENT',30)
for j,(left,right) in enumerate([('MODEL','737-800'),('ENG RATING','26K'),('NAV DATA','SIMULATED'),('ACTIVE','RADAR'),('PERF INIT','INDEX')]):
 y=170+j*125;text(d,(65,y),left,21,anchor='lm');text(d,(705,y+40),right,28,anchor='rm')
text(d,(384,920),'MOD  ACT  LEGS',26,'#62d4d7');save(im,'fmc')
im,d=setup(512,768,'#ebe8df');text(d,(256,48),'FLIGHT DECK',23,'#24313a');text(d,(256,88),'REFERENCE CHECK',19,'#24313a')
for i,s in enumerate(['PARKING BRAKE','FLIGHT INSTRUMENTS','ALTIMETERS','AUTOPILOT','FLIGHT DIRECTORS','NAVIGATION','FUEL QUANTITY','FLAPS','TRIM','FLIGHT CONTROLS','CABIN / DOORS','TAKEOFF BRIEF']):
 y=150+i*45;text(d,(28,y),s,15,'#26323b','lm');d.line((25,y+21,485,y+21),fill='#b7b5a9',width=1);d.rectangle((450,y-7,462,y+7),outline='#44525b')
text(d,(256,730),'SIMULATION ONLY',19,'#8b3330');save(im,'checklist')
im,d=setup(1536,1536,'#424b50')
modules=[('FLT CONTROL',0,0),('NAV / IRS',1,0),('FUEL PUMPS',0,1),('ELECTRICAL',1,1),('APU / START',0,2),('AIR CONDITION',1,2),('HYDRAULIC',0,3),('PRESSURIZATION',1,3)]
for title,col,row in modules:
 x=25+col*760;y=25+row*375;d.rounded_rectangle((x,y,x+725,y+350),12,fill='#3b4549',outline='#9ba5a2',width=2);text(d,(x+362,y+32),title,28)
 for i in range(4):
  px=x+110+i*166;d.rounded_rectangle((px-53,y+75,px+53,y+110),3,fill='#1b262a');text(d,(px,y+92),'OFF',17,'#dec58b');text(d,(px,y+154),'ON',18);text(d,(px,y+286),['L','R','AUTO','TEST'][i],18)
save(im,'overhead')
# Fine original upholstery and panel variation, not a photographic asset.
rng=random.Random(737);im,d=setup(256,256,'#a8aaa4')
for y in range(256):
 for x in range(256):
  v=max(0,min(255,165+rng.randint(-28,28)+(8 if (x+y)%4==0 else 0)));im.putpixel((x,y),(v,v,min(255,v+2)))
save(im,'fabric')
# Original printed labels for the main grey instrument panel.
im,d=setup(2400,760,'#424d52')
def panelxy(x,y):return ((x+9.9)/19.8*2400,(1.2-y)/5.5*760)
for x in [-9.55,-5.48,-1.78,1.78,5.48,9.55]:
 xx,_=panelxy(x,0);d.line((xx,12,xx,748),fill='#2c363c',width=3)
for side in [-1,1]:
 for j,label in enumerate(['MAIN PANEL DU','LOWER DU','DISPLAYS','LIGHTS','CLOCK','FUEL FLOW','AUTO BRAKE','SPEED REF','NOSE WHEEL']):
  x=side*(3.1+(j%5)*1.12);y=-3.08-(j//5)*.65;px,py=panelxy(x,y+.27)
  text(d,(px,py),label,13)
for x,s in [(-8.8,'CAPTAIN'),(8.8,'FIRST OFFICER'),(0,'ENGINE / SYSTEM')]:text(d,panelxy(x,1.05),s,19)
for x in [-1.48,1.48]:text(d,panelxy(x,.99),'STBY',13)
save(im,'mainpanel')
im,d=setup(1024,440,'#424d52');text(d,(512,35),'ELECTRONIC FLIGHT INSTRUMENT',25)
for j,label in enumerate(['MINS','BARO','MODE','RANGE']):
 x=160+j*233;text(d,(x,106),label,23);d.ellipse((x-50,135,x+50,235),outline='#c4c8bc',width=2);text(d,(x,292),'FPV  MTRS',17);text(d,(x,385),['WXR','STA','WPT','ARPT'][j],19)
save(im,'efis')
im,d=setup(2400,560,'#424d52')
def mcpxy(x,y):return ((x+5.425)/10.85*2400,(1.275-y)/2.55*560)
for x,label in [(-5,'COURSE'),(-2.75,'IAS / MACH'),(-.35,'HEADING'),(2.1,'ALTITUDE'),(4.12,'VERT SPEED'),(5,'COURSE')]:text(d,mcpxy(x,1.07),label,29)
for x,label in [(-3.65,'N1'),(-2.75,'SPEED'),(-1.85,'LVL CHG'),(-1.15,'LNAV'),(-.35,'HDG SEL'),(.45,'VNAV'),(1.1,'ALT HLD'),(2.1,'ALT'),(3.1,'V/S'),(4.12,'CMD A')]:text(d,mcpxy(x,-1.1),label,22)
for x in [-5.18,-1.92,1.92,5.18]:
 px,_=mcpxy(x,0);d.line((px,35,px,525),fill='#6b7473',width=2)
save(im,'mcp')

im,d=setup(768,1024,'#3d474c');text(d,(384,60),'THRUST CONTROL',30)
for x in [235,535]:
 d.rounded_rectangle((x-22,160,x+22,740),18,fill='#111a1d');text(d,(x,130),'REV',24)
for j,label in enumerate(['UP','1','2','5','10','15','25','30','40']):
 y=205+j*67;d.line((635,y,690,y),fill='#e2e5d8',width=3);text(d,(721,y),label,24)
text(d,(115,400),'SPEED',20);text(d,(115,435),'BRAKE',20);text(d,(384,840),'STAB TRIM',28);text(d,(384,940),'CUT OUT',25);save(im,'quadrant')
im,d=setup(1024,340,'#444f54');text(d,(512,25),'VHF COMMUNICATION',22)
for x,s in [(290,'121.500'),(740,'124.850')]:
 d.rounded_rectangle((x-170,65,x+170,145),8,fill='#101719');text(d,(x,106),s,49,'#ffbe70');text(d,(x,180),'ACTIVE' if x==290 else 'STANDBY',22)
for j,s in enumerate(['VHF 1','VHF 2','VHF 3','HF 1','HF 2','AM']):text(d,(110+j*160,265),s,18)
save(im,'radio')

print('Generated original cockpit textures:',len(list(OUT.glob('*.png'))))
