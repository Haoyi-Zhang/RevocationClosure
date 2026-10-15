"""Draw the three protocol schematics directly as font-embedded vector PDFs.

These diagrams encode the stated protocol, not experimental measurements.
Run: python figures/draw_schematics.py --output figures
Only ReportLab and the manuscript's TeX-distributed URW Times font are needed.
"""
from pathlib import Path
import argparse,subprocess,math
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

CM=72/2.54
FONT='ProtocolTimes'

def setup_font():
    afm=subprocess.check_output(['kpsewhich','utmr8a.afm'],text=True).strip()
    pfb=subprocess.check_output(['kpsewhich','utmr8a.pfb'],text=True).strip()
    if not afm or not pfb:raise RuntimeError('URW Times font files not found.')
    face=pdfmetrics.EmbeddedType1Face(afm,pfb)
    pdfmetrics.registerTypeFace(face)
    pdfmetrics.registerFont(pdfmetrics.Font(FONT,face.name,'WinAnsiEncoding'))

def new(out,name,bounds):
    x0,y0,x1,y1=bounds
    c=canvas.Canvas(str(out/(name+'.pdf')),pagesize=((x1-x0)*CM,(y1-y0)*CM),
                    pageCompression=1,invariant=1,initialFontName=FONT)
    c.setTitle('');c.setAuthor('');c.setLineWidth(.55)
    c.translate(-x0*CM,-y0*CM)
    return c

def label(c,x,y,lines,size=8.5):
    c.setFont(FONT,size);c.setFillGray(0)
    leading=size*1.17
    for i,line in enumerate(lines):
        c.drawCentredString(x*CM,y*CM+(len(lines)-1)*leading/2-i*leading-size*.32,line)

def box(c,x,y,w,h,lines,dashed=False,gray=1):
    c.saveState();c.setFillGray(gray)
    if dashed:c.setDash(3,2)
    c.rect((x-w/2)*CM,(y-h/2)*CM,w*CM,h*CM,stroke=1,fill=1)
    c.restoreState();label(c,x,y,lines)
    return (x-w/2,y-h/2,x+w/2,y+h/2)

def comparison(c,x,y,left,right,greater=False,size=8.5):
    """Typeset <= or >= as vector mathematical strokes, not code punctuation."""
    c.setFont(FONT,size)
    lw=pdfmetrics.stringWidth(left,FONT,size);rw=pdfmetrics.stringWidth(right,FONT,size)
    sw=5.2;gap=3.2;start=x*CM-(lw+rw+sw+2*gap)/2;baseline=y*CM-size*.32
    c.drawString(start,baseline,left);sx=start+lw+gap
    # Open chevron and lower rule form the conventional mathematical relation.
    path=c.beginPath()
    path.moveTo(sx if greater else sx+sw,baseline+6.6)
    path.lineTo(sx+sw if greater else sx,baseline+3.9)
    path.lineTo(sx if greater else sx+sw,baseline+1.2)
    c.drawPath(path);c.line(sx,baseline-.6,sx+sw,baseline-.6)
    c.drawString(sx+sw+gap,baseline,right)

def arrow(c,p,q,dashed=False):
    c.saveState()
    if dashed:c.setDash(3,2)
    c.line(p[0]*CM,p[1]*CM,q[0]*CM,q[1]*CM)
    c.setDash();a=math.atan2(q[1]-p[1],q[0]-p[0]);s=.115
    path=c.beginPath();path.moveTo(q[0]*CM,q[1]*CM)
    for angle in [a+2.68,a-2.68]:
        path.lineTo((q[0]+s*math.cos(angle))*CM,(q[1]+s*math.sin(angle))*CM)
    path.close();c.setFillGray(0);c.drawPath(path,fill=1,stroke=0);c.restoreState()

def architecture(out):
    c=new(out,'architecture',(-1.43,-2.78,13.72,2.47))
    box(c,0,.90,2.68,1.30,['Issuer / revoker','grant / revoke'])
    box(c,0,-.90,2.68,1.30,['Offline delegator','attenuated child'])
    box(c,4,0,3.98,2.60,['Fixed gateway','audience G','local ancestry checks','durable exclusion','+ receipts'])
    box(c,8.2,0,3.48,1.70,['Completion collector','join receipts','and lower time'])
    box(c,12.1,0,2.98,1.70,['commit bound evidence','(K, A)'],gray=.95)
    box(c,12.1,-2.10,2.98,1.04,['reply after commit','closed / open'])
    box(c,8.2,1.85,2.98,1.02,['bounded clock','observations'])
    arrow(c,(1.34,.90),(2.01,.90));arrow(c,(1.34,-.90),(2.01,-.90))
    arrow(c,(5.99,0),(6.46,0));arrow(c,(9.94,0),(10.61,0))
    arrow(c,(8.2,1.34),(8.2,.85),True);arrow(c,(12.1,-.85),(12.1,-1.58))
    c.showPage();c.save()

def transactions(out):
    c=new(out,'transactions',(-.91,-.88,6.76,.88))
    for x,ls in [(0,['Validate','revoke']),(1.95,['Insert','in tx']),(3.90,['Durable','commit']),(5.85,['Release','receipt'])]:
        box(c,x,0,1.65,1.20,ls)
    for x in [0,1.95,3.90]:arrow(c,(x+.825,0),(x+1.95-.825,0))
    c.setDash(3,2)
    for x in [2.90,4.88]:c.line(x*CM,-.8*CM,x*CM,.8*CM)
    c.setDash();c.showPage();c.save()

def barrier(out):
    c=new(out,'barrier',(-1.50,-1.34,5.60,3.30))
    box(c,0,2.1,2.7,1.00,['g: target grant'])
    box(c,4,2.1,2.7,1.00,['h: descendant'])
    arrow(c,(1.35,2.1),(2.65,2.1));comparison(c,2,3.05,'d(h)','d(g)')
    box(c,0,.7,2.72,1.00,['Gateways 0-2','durable receipts'])
    box(c,4,.7,2.9,1.00,[],True)
    label(c,4,.88,['Gateways 3-4']);comparison(c,4,.52,'lower time','200',True)
    box(c,2,-.7,3.0,1.04,['All five covered','future checks reject'])
    arrow(c,(0,1.6),(0,1.2));arrow(c,(0,.2),(.5,-.18));arrow(c,(4,.2),(3.5,-.18),True)
    c.showPage();c.save()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    out=p.parse_args().output;out.mkdir(parents=True,exist_ok=True);setup_font()
    architecture(out);transactions(out);barrier(out)

if __name__=='__main__':main()
