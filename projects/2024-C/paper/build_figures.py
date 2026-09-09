import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper/figures"
OUT.mkdir(parents=True, exist_ok=True)
FONT = r"C:\Windows\Fonts\simhei.ttf"
FONT_SONG = r"C:\Windows\Fonts\simsun.ttc"
W, H = 1800, 1050
BG = "#FFFFFF"
INK = "#17212B"
MUTED = "#5B6773"
GRID = "#D9E1E8"
BLUE = "#245A84"
LIGHT_BLUE = "#79A8CC"
ORANGE = "#D67A35"
GREEN = "#4F8465"
RED = "#B94A48"


def font(size, bold=False):
    return ImageFont.truetype(FONT, size=size)


def canvas(title, subtitle=""):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((90, 55), title, font=font(48), fill=INK)
    if subtitle:
        d.text((90, 120), subtitle, font=font(25), fill=MUTED)
    d.line((90, 165, W - 90, 165), fill=GRID, width=3)
    return im, d


def save(im, name, sources):
    path = OUT / name
    im.save(path, dpi=(180, 180))
    return {"file": f"paper/figures/{name}", "sources": sources,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def text_center(d, xy, text, fnt, fill=INK):
    box = d.textbbox((0, 0), text, font=fnt)
    d.text((xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2), text, font=fnt, fill=fill)


def arrow(d, p1, p2, color=BLUE, width=6):
    d.line((*p1, *p2), fill=color, width=width)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for delta in (2.55, -2.55):
        d.line((p2[0], p2[1], p2[0] + 22 * math.cos(ang + delta), p2[1] + 22 * math.sin(ang + delta)), fill=color, width=width)


def axes(d, box, ymin, ymax, yticks=5, ylabel=""):
    x0, y0, x1, y1 = box
    d.line((x0, y1, x1, y1), fill=INK, width=3)
    d.line((x0, y0, x0, y1), fill=INK, width=3)
    for i in range(yticks + 1):
        val = ymin + (ymax - ymin) * i / yticks
        y = y1 - (y1 - y0) * i / yticks
        d.line((x0, y, x1, y), fill=GRID, width=2)
        label = f"{val:.1f}" if abs(ymax - ymin) < 20 else f"{val:.0f}"
        box_t = d.textbbox((0, 0), label, font=font(22))
        d.text((x0 - 18 - (box_t[2] - box_t[0]), y - 13), label, font=font(22), fill=MUTED)
    if ylabel:
        d.text((x0 - 80, y0 - 40), ylabel, font=font(22), fill=MUTED)
    return lambda v: y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)


manifest = []

# 图1
im, d = canvas("图1  三问递进与共同决策框架", "同一套农业约束下，逐层加入市场与不确定性")
boxes = [
    (100, 270, 430, 500, "共同数据与约束", "土地  季次  轮作\n豆类  管理便利", BLUE),
    (530, 230, 850, 540, "问题一", "稳定参数\n两种滞销规则\n输出两套计划", GREEN),
    (950, 230, 1270, 540, "问题二", "销量  亩产\n成本  价格波动\n留出情形评价", ORANGE),
    (1370, 230, 1690, 540, "问题三", "相关性\n替代与互补\n关系敏感性", RED),
]
for x0, y0, x1, y1, head, body, color in boxes:
    d.rounded_rectangle((x0, y0, x1, y1), radius=24, fill="#F7FAFC", outline=color, width=5)
    text_center(d, ((x0+x1)//2, y0+65), head, font(32), color)
    for i, line in enumerate(body.split("\n")):
        text_center(d, ((x0+x1)//2, y0+135+i*48), line, font(25), INK)
for a, b in [(430, 530), (850, 950), (1270, 1370)]:
    arrow(d, (a+12, 385), (b-12, 385))
d.rounded_rectangle((300, 680, 1500, 865), radius=24, fill="#EEF4F8", outline=BLUE, width=3)
text_center(d, (900, 735), "统一决策", font(30), BLUE)
text_center(d, (900, 800), "2024—2030年每个地块、每季、每种作物的种植面积", font(30), INK)
manifest.append(save(im, "fig01_framework.png", ["report.md", "state/state.json"]))

# 图2
lands = []
with (ROOT / "data/frozen/G1-v1-base/lands.csv").open(encoding="utf-8-sig", newline="") as f:
    lands = list(csv.DictReader(f))
types = ["平旱地", "梯田", "山坡地", "水浇地", "普通大棚", "智慧大棚"]
counts = Counter(r["land_type"] for r in lands)
areas = defaultdict(float)
for r in lands:
    areas[r["land_type"]] += float(r["area_mu"])
im, d = canvas("图2  不同地块类型的数量与面积", "共54个地块，物理面积1213亩")
for panel, values, title, xmax, color in [
    ((110, 250, 840, 900), counts, "地块数量 个", 18, BLUE),
    ((960, 250, 1690, 900), areas, "面积合计 亩", 650, ORANGE),
]:
    x0, y0, x1, y1 = panel
    d.text((x0, y0-55), title, font=font(30), fill=INK)
    for i, t in enumerate(types):
        y = y0 + 45 + i*92
        d.text((x0, y+8), t, font=font(24), fill=INK)
        bx = x0 + 155
        bw = (x1-bx-50) * float(values[t]) / xmax
        d.rounded_rectangle((bx, y, bx+bw, y+45), radius=8, fill=color)
        d.text((bx+bw+12, y+7), f"{values[t]:.1f}" if isinstance(values[t], float) else str(values[t]), font=font(23), fill=MUTED)
manifest.append(save(im, "fig02_land_structure.png", ["data/frozen/G1-v1-base/lands.csv"]))

# Q1 data
with (ROOT / "questions/Q1/deep_runs/main_comparison.csv").open(encoding="utf-8-sig", newline="") as f:
    q1_main = {(r["scenario"], r["sale_case"]): r for r in csv.DictReader(f)}
with (ROOT / "questions/Q1/boost_runs/comparison.csv").open(encoding="utf-8-sig", newline="") as f:
    q1_boost = {r["scenario"]: r for r in csv.DictReader(f)}
scenarios = ["D0", "D05", "D10"]
s1 = [float(q1_boost.get(s, {"profit_yuan": q1_main[(s,"S1")]["M1R3_profit_yuan"]})["profit_yuan"])/1e4 for s in scenarios]
s2 = [float(q1_main[(s, "S2")]["M1R3_profit_yuan"])/1e4 for s in scenarios]
im, d = canvas("图3  问题一两种销售规则下的七年收益", "D0为主口径，D05与D10用于未观测季次销量分配敏感性")
box=(180,270,1650,880); ymap=axes(d,box,0,7000,7,"万元")
x0,y0,x1,y1=box; groupw=(x1-x0)/3
for i,s in enumerate(scenarios):
    cx=x0+groupw*(i+.5)
    for j,(v,c,label) in enumerate([(s1[i],BLUE,"S1 完全滞销"),(s2[i],ORANGE,"S2 超额半价")]):
        left=cx-90+j*95
        d.rectangle((left,ymap(v),left+75,y1),fill=c)
        text_center(d,(left+37,ymap(v)-22),f"{v:.0f}",font(21),c)
    text_center(d,(cx,y1+42),s,font(25),INK)
d.rectangle((1230,205,1260,235),fill=BLUE); d.text((1275,203),"S1 完全滞销",font=font(23),fill=INK)
d.rectangle((1460,205,1490,235),fill=ORANGE); d.text((1505,203),"S2 超额半价",font=font(23),fill=INK)
manifest.append(save(im,"fig03_q1_profit.png",["questions/Q1/deep_runs/main_comparison.csv","questions/Q1/boost_runs/comparison.csv"]))

# 图4
with (ROOT / "questions/Q1/deep_runs/pareto.csv").open(encoding="utf-8-sig", newline="") as f:
    pareto=list(csv.DictReader(f))
im,d=canvas("图4  问题一收益与管理复杂度权衡","横轴为启用安排数，纵轴为七年收益")
for k,case in enumerate(["S1","S2"]):
    vals=[r for r in pareto if r["sale_case"]==case]
    px0=120+k*850; px1=px0+720; py0=290; py1=870
    xs=[int(r["activations"]) for r in vals]; ys=[float(r["profit_yuan"])/1e4 for r in vals]
    xmin,xmax=min(xs)-10,max(xs)+10; ymin=min(ys)-40; ymax=max(ys)+40
    d.text((px0,210),f"{case}情形",font=font(30),fill=BLUE if case=="S1" else ORANGE)
    d.line((px0,py1,px1,py1),fill=INK,width=3); d.line((px0,py0,px0,py1),fill=INK,width=3)
    for r,x,y in zip(vals,xs,ys):
        xx=px0+(x-xmin)/(xmax-xmin)*(px1-px0); yy=py1-(y-ymin)/(ymax-ymin)*(py1-py0)
        d.ellipse((xx-10,yy-10,xx+10,yy+10),fill=BLUE if case=="S1" else ORANGE)
        d.text((xx+14,yy-14),f"{x}项  {y:.0f}万",font=font(19),fill=MUTED)
    text_center(d,((px0+px1)//2,py1+45),"启用安排数",font(23),INK)
manifest.append(save(im,"fig04_q1_pareto.png",["questions/Q1/deep_runs/pareto.csv"]))

# 图5
with (ROOT / "questions/Q2/deep_runs/holdout_summary.csv").open(encoding="utf-8-sig", newline="") as f:
    q2=[r for r in csv.DictReader(f) if r["demand_base"]=="D05" and r["sale_case"]=="S2"]
im,d=canvas("图5  问题二留出集的平均利润与尾部表现","500个共同情形，D05销量代理与S2销售规则")
box=(180,270,1650,880); ymap=axes(d,box,6400,6800,4,"万元")
x0,y0,x1,y1=box; groupw=(x1-x0)/3
for i,r in enumerate(q2):
    cx=x0+groupw*(i+.5)
    vals=[float(r["mean"])/1e4,float(r["worst10_mean"])/1e4]
    for j,(v,c) in enumerate(zip(vals,[BLUE,ORANGE])):
        left=cx-90+j*95; d.rectangle((left,ymap(v),left+75,y1),fill=c)
        text_center(d,(left+37,ymap(v)-20),f"{v:.1f}",font(20),c)
    text_center(d,(cx,y1+42),r["candidate"],font(25),INK)
d.rectangle((1220,205,1250,235),fill=BLUE); d.text((1265,203),"平均利润",font=font(23),fill=INK)
d.rectangle((1440,205,1470,235),fill=ORANGE); d.text((1485,203),"最差10%平均",font=font(23),fill=INK)
manifest.append(save(im,"fig05_q2_holdout.png",["questions/Q2/deep_runs/holdout_summary.csv"]))

# 图6
with (ROOT / "questions/Q2/deep_runs/holdout_pairwise.csv").open(encoding="utf-8-sig", newline="") as f:
    pair=list(csv.DictReader(f))
im,d=canvas("图6  问题二配对平均增益与模拟误差区间","区间反映有限模拟样本误差，不代表现实世界置信区间")
x0,x1=250,1650; y_positions=[400,700]; xmin=-10; xmax=30
d.line((x0,850,x1,850),fill=INK,width=3)
for v in [-10,0,10,20,30]:
    xx=x0+(v-xmin)/(xmax-xmin)*(x1-x0); d.line((xx,250,xx,850),fill=GRID,width=2)
    text_center(d,(xx,895),f"{v}",font(23),MUTED)
d.text((1450,920),"万元",font=font(23),fill=MUTED)
for y,r,c in zip(y_positions,pair,[BLUE,ORANGE]):
    mean=float(r["mean_difference_yuan"])/1e4; lo=float(r["ci95_low_yuan"])/1e4; hi=float(r["ci95_high_yuan"])/1e4
    conv=lambda v:x0+(v-xmin)/(xmax-xmin)*(x1-x0)
    d.line((conv(lo),y,conv(hi),y),fill=c,width=10); d.ellipse((conv(mean)-14,y-14,conv(mean)+14,y+14),fill=c)
    d.text((110,y-18),f"{r['candidate']} 相对 {r['reference']}",font=font(27),fill=INK)
    d.text((conv(hi)+20,y-18),f"{mean:.2f}  [{lo:.2f}, {hi:.2f}]",font=font(23),fill=c)
zero=x0+(0-xmin)/(xmax-xmin)*(x1-x0); d.line((zero,230,zero,850),fill=RED,width=4)
manifest.append(save(im,"fig06_q2_pairwise.png",["questions/Q2/deep_runs/holdout_pairwise.csv"]))

# 图7
with (ROOT / "questions/Q2/deep_runs/sensitivity_summary.csv").open(encoding="utf-8-sig", newline="") as f:
    sens=list(csv.DictReader(f))
groups=defaultdict(dict)
for r in sens:
    key=(r["weight_setting"],r["cost_vegetable_factor"],r["demand_base"],r["sale_case"])
    groups[key][r["candidate"]]=float(r["mean_profit_yuan"])
rowkeys=sorted({(k[0],k[1]) for k in groups}); colkeys=[(demand,sale) for demand in ["D0","D05","D10"] for sale in ["S1","S2"]]
diffs={(rk,ck):(groups[(rk[0],rk[1],ck[0],ck[1])]["M1"]-groups[(rk[0],rk[1],ck[0],ck[1])]["M0"])/1e4 for rk in rowkeys for ck in colkeys}
maxabs=max(abs(v) for v in diffs.values())
im,d=canvas("图7  问题二M1相对M0的假设敏感性","单元格为平均利润差，单位万元；蓝色为M1较高，红色为M1较低")
gx0,gy0=430,290; cw,ch=190,95
for j,ck in enumerate(colkeys): text_center(d,(gx0+j*cw+cw/2,240),f"{ck[0]} {ck[1]}",font(22),INK)
for i,rk in enumerate(rowkeys):
    d.text((90,gy0+i*ch+28),f"{rk[0]}  成本{rk[1]}",font=font(21),fill=INK)
    for j,ck in enumerate(colkeys):
        v=diffs[(rk,ck)]; intensity=min(1,abs(v)/maxabs)
        base=(36,90,132) if v>=0 else (185,74,72); rgb=tuple(int(255-(255-c)*(.25+.65*intensity)) for c in base)
        d.rectangle((gx0+j*cw,gy0+i*ch,gx0+(j+1)*cw-5,gy0+(i+1)*ch-5),fill=rgb,outline="#FFFFFF")
        text_center(d,(gx0+j*cw+cw/2,gy0+i*ch+ch/2),f"{v:+.1f}",font(23),"#FFFFFF" if intensity>.45 else INK)
manifest.append(save(im,"fig07_q2_sensitivity.png",["questions/Q2/deep_runs/sensitivity_summary.csv"]))

# 图8
im,d=canvas("图8  问题三关系情形的构造","保持Q2边际变化，用潜在因子加入共同变化，再施加作物关系")
nodes=[(120,320,440,560,"Q2边际变化","销量 价格 成本 亩产",BLUE),(570,320,890,560,"高斯copula","共同市场与天气因子",GREEN),(1020,230,1340,470,"R0","仅相关性",BLUE),(1020,520,1340,760,"RS","相关性和替代",ORANGE),(1450,375,1740,615,"RSC","相关性\n替代和互补",RED)]
for x0,y0,x1,y1,head,body,c in nodes:
    d.rounded_rectangle((x0,y0,x1,y1),radius=22,fill="#F8FAFC",outline=c,width=5)
    text_center(d,((x0+x1)/2,y0+62),head,font(31),c)
    for idx,line in enumerate(body.split("\n")):text_center(d,((x0+x1)/2,y0+132+idx*42),line,font(23),INK)
arrow(d,(440,440),(570,440)); arrow(d,(890,410),(1020,350)); arrow(d,(890,470),(1020,640)); arrow(d,(1340,350),(1450,450)); arrow(d,(1340,640),(1450,540))
d.text((220,830),"关系参数来自透明模拟设定，不是由一年附件数据估计的现实因果关系。",font=font(28),fill=MUTED)
manifest.append(save(im,"fig08_q3_relation.png",["questions/Q3/protocols/relationship_v1.json"]))

# 图9
with (ROOT / "questions/Q3/deep_runs/sensitivity_summary.csv").open(encoding="utf-8-sig", newline="") as f:
    q3sens=[r for r in csv.DictReader(f) if r["demand_base"]=="D05" and r["sale_rule"]=="S2" and r["candidate"] in {"B0","N10"}]
lookup={(float(r["strength"]),r["candidate"]):float(r["mean"])/1e4 for r in q3sens}
strengths=[.5,1.0,2.0]; b0=[lookup[(s,"B0")] for s in strengths]; n10=[lookup[(s,"N10")] for s in strengths]; gains=[(n-b)/b*100 for b,n in zip(b0,n10)]
im,d=canvas("图9  问题三关系强度敏感性","D05与S2固定评价；N30已排除")
box=(170,280,1100,850); ymap=axes(d,box,6705,6725,4,"万元"); x0,y0,x1,y1=box
for vals,c,label in [(b0,BLUE,"B0"),(n10,ORANGE,"N10")]:
    pts=[]
    for i,v in enumerate(vals):
        xx=x0+(i+.5)*(x1-x0)/3; yy=ymap(v); pts.append((xx,yy)); d.ellipse((xx-10,yy-10,xx+10,yy+10),fill=c); text_center(d,(xx,yy-25),f"{v:.1f}",font(20),c)
    d.line(sum(([p[0],p[1]] for p in pts),[]),fill=c,width=6)
for i,s in enumerate(strengths): text_center(d,(x0+(i+.5)*(x1-x0)/3,y1+40),f"{s:g}倍",font(23),INK)
d.text((1180,280),"N10相对B0增益",font=font(28),fill=INK)
for i,(s,g) in enumerate(zip(strengths,gains)):
    y=380+i*120; d.text((1200,y),f"{s:g}倍",font=font(24),fill=INK); d.rounded_rectangle((1300,y,1300+300*g/.1,y+42),radius=6,fill=ORANGE); d.text((1610,y+4),f"{g:.3f}%",font=font(22),fill=ORANGE)
d.line((1300,760,1600,760),fill=RED,width=4); d.text((1200,800),"替换门槛 0.100%",font=font(24),fill=RED)
manifest.append(save(im,"fig09_q3_strength.png",["questions/Q3/deep_runs/sensitivity_summary.csv"]))

(OUT / "manifest.json").write_text(json.dumps({"figures":manifest},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"figures":len(manifest),"output":str(OUT)},ensure_ascii=False))
