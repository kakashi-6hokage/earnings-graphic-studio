"""Deterministic, Amazon-inspired editorial financial Sankey renderer.

No network calls or arbitrary file access. Full-precision Python floats are used for
widths; Decimal is used to round presentation text. Financial validation is separate
from image review. Generates an editable, self-contained SVG with graceful ribbons.
"""
from __future__ import annotations

import html
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STYLE = json.loads((ROOT / "templates" / "layout.json").read_text(encoding="utf-8"))


def fnum(v: Any, where: str = "number") -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise ValueError(f"{where} must be a finite numeric value")
    return float(v)


def fmt_number(value: float) -> str:
    rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(abs(rounded), "f").rstrip("0").rstrip(".")
    return text or "0"


def money(value: float, d: dict) -> str:
    pre = "−" if value < 0 else ""
    sym = d.get("currency", "$")
    units = d.get("units", "B")
    return f"{pre}{sym}{fmt_number(value)}{units}"


def esc(v: Any) -> str:
    return html.escape(str(v), quote=True)


def tol_for(n: int) -> float:
    # Allow only the small accumulated effect of source displays rounded to cents
    return min(0.04, 0.005 * max(2, n + 1) + 0.001)


def validate(d: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for field in ("company", "quarter", "headline", "source_note"):
        if not isinstance(d.get(field), str) or not d[field].strip():
            errors.append(f"Missing or invalid {field}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d.get("release_date", ""))):
        errors.append("release_date must be YYYY-MM-DD")
    for f in ("currency", "units"):
        if not isinstance(d.get(f), str) or not d[f].strip() or len(d[f]) > 5:
            errors.append(f"{f} must be a nonempty short display string")
    try:
        rev = fnum(d.get("revenue"), "revenue")
        cogs = fnum(d.get("cost_of_revenue"), "cost_of_revenue")
        nonop = fnum(d.get("nonoperating_net", 0), "nonoperating_net")
        tax = fnum(d.get("income_tax"), "income_tax")
        net = fnum(d.get("net_income"), "net_income")
    except ValueError as e:
        errors.append(str(e))
        rev, cogs, nonop, tax, net = 1.0, 0.0, 0.0, 0.0, 0.0
    if rev <= 0:
        errors.append("revenue must be positive")
    if cogs < 0 or cogs > rev:
        errors.append("cost_of_revenue must be between zero and revenue")
    srcs = d.get("sources")
    if not isinstance(srcs, list) or not srcs:
        errors.append("sources must be a nonempty list")
        srcs = []
    expenses = d.get("operating_expenses")
    if not isinstance(expenses, list):
        errors.append("operating_expenses must be a list")
        expenses = []
    for label, entries in (("sources", srcs), ("operating_expenses", expenses)):
        for i, item in enumerate(entries):
            if not isinstance(item, dict):
                errors.append(f"{label}[{i}] must be an object")
                continue
            if not isinstance(item.get("name"), str) or not item["name"].strip():
                errors.append(f"{label}[{i}].name must be nonempty")
            try:
                x = fnum(item.get("amount"), f"{label}[{i}].amount")
                if x < 0:
                    errors.append(f"{label}[{i}].amount must not be negative")
            except ValueError as e:
                errors.append(str(e))
            if "yoy" in item:
                try:
                    fnum(item["yoy"], f"{label}[{i}].yoy")
                except ValueError as e:
                    errors.append(str(e))
    try:
        source_total = sum(fnum(x["amount"]) for x in srcs if isinstance(x, dict))
        expense_total = sum(fnum(x["amount"]) for x in expenses if isinstance(x, dict))
    except (ValueError, KeyError):
        source_total, expense_total = 0, 0
    if abs(source_total - rev) > tol_for(len(srcs)):
        errors.append(f"Sources {source_total:.6f} do not reconcile with revenue {rev:.6f}")
    elif abs(source_total-rev) > 1e-6:
        warnings.append("Source amounts differ slightly due to displayed rounding; geometry is normalized to revenue")
    gross = rev - cogs
    op = gross - expense_total
    pretax = op + nonop
    calculated_net = pretax - tax
    if gross < -1e-6:
        errors.append("Gross profit is negative; unsupported by this positive-flow template")
    if op < -1e-6:
        warnings.append("Operating loss requires signed adjustment rendering")
    if net < -1e-6:
        warnings.append("Net loss requires signed loss rendering; do not show a positive green terminal")
    for key, computed in (("gross_profit", gross), ("operating_profit", op), ("pretax_income", pretax)):
        if key in d:
            try:
                published = fnum(d[key], key)
                if abs(published - computed) > tol_for(2):
                    errors.append(f"{key} {published:.6f} != calculated {computed:.6f}")
            except ValueError as e:
                errors.append(str(e))
    if abs(calculated_net - net) > tol_for(2):
        errors.append(f"net_income {net:.6f} != calculated {calculated_net:.6f}")
    if len(srcs)>8:
        warnings.append("More than eight sources may not fit the editorial template legibly")
    if len(expenses)>6:
        warnings.append("More than six expense categories may require category grouping")
    if len(d.get("headline", ""))>90:
        warnings.append("Long headline will be shrunk to fit")
    return {"passed":not errors,"errors":errors,"warnings":warnings,
            "derived":{"gross_profit":round(gross, 6),"operating_expenses":round(expense_total, 6),
                       "operating_profit":round(op, 6),"pretax_income":round(pretax, 6),
                       "net_income":round(calculated_net,6)},
            "checks":{"source_reconciliation":abs(source_total-rev)<=tol_for(len(srcs)),
                      "net_reconciliation":abs(calculated_net-net)<=tol_for(2),
                      "monetary_display_max_decimals":2,
                      "independent_visual_review":False}}


@dataclass
class Stage:
    x: float
    y: float
    value: float
    kind: str
    label: str

    def top(self, scale: float) -> float:
        return self.y - abs(self.value)*scale/2

    def bottom(self, scale: float) -> float:
        return self.y + abs(self.value)*scale/2


def text_el(x, y, value, size, color, anchor="middle", weight=500, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'font-size="{size:.1f}" font-weight="{weight}" fill="{color}" {extra}>'
            f'{esc(value)}</text>')


def ribbon(x0: float, x1: float, start_center: float, end_center: float, thickness: float,
           color: str, opacity=0.74) -> str:
    if thickness<=0: return ""
    # Cubic boundaries share the exact node-edge thickness and create horizontal tangents.
    a, b = start_center-thickness/2, start_center+thickness/2
    c, d = end_center-thickness/2, end_center+thickness/2
    k=(x1-x0)*0.47
    path=(f"M{x0:.2f},{a:.2f} C{x0+k:.2f},{a:.2f} {x1-k:.2f},{c:.2f} {x1:.2f},{c:.2f} "
          f"L{x1:.2f},{d:.2f} C{x1-k:.2f},{d:.2f} {x0+k:.2f},{b:.2f} {x0:.2f},{b:.2f} Z")
    return f'<path d="{path}" fill="{color}" opacity="{opacity}"/>'


def draw_node(st: Stage, scale, col, nodewidth=52, minimum=0):
    h=max(st.value*scale,minimum)
    return f'<rect x="{st.x-nodewidth/2:.2f}" y="{st.y-h/2:.2f}" width="{nodewidth}" height="{h:.2f}" fill="{col}"/>'


def mark(x, y, label, col, palette):
    # Original editorial marks; no user/company trademarks are reproduced as icon art.
    label=str(label or "").strip()[:9]
    if not label: return ""
    if label.lower()=="aws":
        return text_el(x,y+12,"aws",44,"#253E58",weight=700)+f'<path d="M{x-48} {y+23} Q{x} {y+52} {x+49} {y+21}" stroke="#E59A2D" stroke-width="6" fill="none" stroke-linecap="round"/>'
    if label.lower()=="prime":
        return text_el(x,y+8,"prime",29,"#438AC7",weight=700)
    if len(label)<=4:
        return f'<circle cx="{x}" cy="{y}" r="35" fill="{col}" opacity="0.1"/>'+text_el(x,y+9,label,27,col,weight=700)
    return text_el(x,y+7,label,22,col,weight=650)


def multiline_label(x,y,value,sz,color,anchor="end",weight=600,maxchars=22,leading=30):
    parts=value.split()
    lines=[]; cur=""
    for word in parts:
        if cur and len(cur)+1+len(word)>maxchars:
            lines.append(cur); cur=word
        else:cur=(cur+" "+word).strip()
    if cur: lines.append(cur)
    lines=lines[:3]
    return [text_el(x,y+i*leading,line,sz,color,anchor,weight) for i,line in enumerate(lines)],len(lines)


def render_svg(d: dict) -> str:
    report=validate(d)
    if not report["passed"]:
        raise ValueError("Invalid financial ledger: "+"; ".join(report["errors"]))
    # For now, refuse to misrepresent negative signed stages with a positive-only conservation geometry.
    vals=report["derived"]
    if min(vals["operating_profit"], vals["pretax_income"], vals["net_income"])<0:
        raise ValueError("This template currently requires non-negative operating, pretax and net income; a loss needs an explicit signed-flow layout. Refusing a misleading positive-flow graphic.")
    W=2400;H=1350
    C=STYLE["colors"]
    X=STYLE["x_positions"]
    scale=430/fnum(d["revenue"])
    revenue=Stage(X["revenue"],720,fnum(d["revenue"]),"blue","Revenue")
    gross=Stage(X["gross"],560,vals["gross_profit"],"green","Gross profit")
    cost=Stage(X["gross"],960,fnum(d["cost_of_revenue"]),"red","Cost of revenue")
    op=Stage(X["operating"],455,vals["operating_profit"],"green","Operating profit")
    opex=Stage(X["operating"],795,vals["operating_expenses"],"red","Operating expenses")
    pre=Stage(X["pretax"],398,vals["pretax_income"],"green","Pretax income")
    net=Stage(X["right"],312,fnum(d["net_income"]),"green","Net profit")
    tax=Stage(X["right"],534,max(0,fnum(d["income_tax"])),"red","Income tax")
    nonop=fnum(d.get("nonoperating_net",0))
    hrev=revenue.value*scale
    page=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
          '<defs><style>text{font-family:DejaVu Sans,Arial,Helvetica,sans-serif}</style></defs>',
          f'<rect width="{W}" height="{H}" fill="{C.get("background",STYLE["canvas"]["background"])}"/>',
          f'<rect width="{W}" height="{H}" fill="{STYLE["canvas"]["background"]}"/>']
    # Title. Fit to the editorial line rather than wrapping awkwardly.
    title=f'{d["company"]} {d["quarter"]} | {d["headline"]}'
    # Fit the entire editorial headline, accounting for wide capitals and punctuation.
    weighted_width = sum((.35 if ch in "iltj !,.:;|" else .88 if ch in "MW@#%" else .74 if ch.isupper() else .63 if ch.isdigit() else .59) for ch in title)
    title_font=min(62,max(28,2040/max(1,weighted_width)))
    page.append(text_el(78,93,title,title_font,C["navy"],"start",700))
    from datetime import date
    date_display=date.fromisoformat(d["release_date"]).strftime("%B %-d, %Y")
    curr={"$":"USD", "₸":"KZT", "€":"EUR", "£":"GBP", "₹":"INR"}.get(d.get("currency","$"),d.get("currency","$"))
    units_display={"B":"billions", "M":"millions", "T":"trillions"}.get(d.get("units","B"),d.get("units","B"))
    page.append(text_el(82,146,f'Reported {date_display}   ·   {curr} {units_display}   ·   Quarterly earnings',21,C["muted"],"start",400))
    # Company name centered high over main revenue pillar.
    brand=d.get("brand",d["company"])
    brand_font=(92 if len(brand)<10 else min(72,max(42,650/(len(brand)*.59))))
    page.append(text_el(revenue.x,285,brand,brand_font,"#2B2B2C",weight=700))
    if brand.lower()=="amazon":
        page.append(f'<path d="M{revenue.x-128} 303 Q{revenue.x} 377 {revenue.x+131} 296" stroke="#E89919" stroke-width="12" fill="none" stroke-linecap="round"/>')
    # Source input bands. Independent row spacing preserves readable names even for tiny categories.
    srcs=d["sources"];ns=len(srcs)
    if ns==1: ys=[740]
    else:
        start,end=(420,1010) if ns<=4 else (350,1150)
        ys=[start+i*(end-start)/(ns-1) for i in range(ns)]
    source_amt_sum=sum(float(s["amount"]) for s in srcs)
    src_factor=revenue.value/source_amt_sum if source_amt_sum else 1.0
    accumulation=revenue.top(scale)
    for i,(s,yy) in enumerate(zip(srcs,ys)):
        amt=float(s["amount"])*src_factor
        hh=amt*scale
        src_col=C["orange"] if s.get("color")=="gold" else C["blue"]
        ribbon_col=C["ribbon_gold"] if s.get("color")=="gold" else C["ribbon_blue"]
        receive_center=accumulation+hh/2
        page.append(ribbon(X["source"]+22,revenue.x-26,yy,receive_center,hh,ribbon_col,0.89))
        accumulation+=hh
    # Revenue -> gross and cost; contiguous segment edges at revenue node.
    gross_h=gross.value*scale;cost_h=cost.value*scale
    page.append(ribbon(revenue.x+26,gross.x-26,revenue.top(scale)+gross_h/2,gross.y,gross_h,C["ribbon_green"],0.89))
    page.append(ribbon(revenue.x+26,cost.x-26,revenue.top(scale)+gross_h+cost_h/2,cost.y,cost_h,C["ribbon_red"],0.88))
    # Gross -> operating and opex.
    op_h=op.value*scale;exp_h=opex.value*scale
    page.append(ribbon(gross.x+26,op.x-26,gross.top(scale)+op_h/2,op.y,op_h,C["ribbon_green"],0.89))
    page.append(ribbon(gross.x+26,opex.x-26,gross.top(scale)+op_h+exp_h/2,opex.y,exp_h,C["ribbon_red"],0.89))
    # Operating expense categories flow to distinct right side destinations.
    exp_categories=d["operating_expenses"]
    n=len(exp_categories)
    if n<=1: exp_ys=[815]*n
    else:
        top_e=733; bottom_e=1178
        exp_ys=[top_e+i*(bottom_e-top_e)/(n-1) for i in range(n)]
    accum=opex.top(scale)
    for exp,y in zip(exp_categories,exp_ys):
        height=float(exp["amount"])*scale
        page.append(ribbon(opex.x+26,X["expense_end"]-23,accum+height/2,y,height,C["ribbon_red"],0.89))
        accum+=height
    # Operating profit -> pretax, with a nonoperating gain/loss accurately separated.
    if nonop<=0:
        pre_h=pre.value*scale
        loss_h=-nonop*scale
        page.append(ribbon(op.x+26,pre.x-26,op.top(scale)+pre_h/2,pre.y,pre_h,C["ribbon_green"],0.89))
        if loss_h>0:
            page.append(ribbon(op.x+26,1957,op.top(scale)+pre_h+loss_h/2,616,loss_h,C["ribbon_red"],0.88))
            page.append(f'<rect x="1957" y="{616-loss_h/2:.2f}" width="27" height="{max(loss_h,1):.2f}" fill="{C["red"]}"/>')
    else:
        opval_h=op.value*scale
        other_h=nonop*scale
        page.append(ribbon(op.x+26,pre.x-26,op.y,pre.top(scale)+opval_h/2,opval_h,C["ribbon_green"],0.89))
        page.append(ribbon(1688,pre.x-26,625,pre.top(scale)+opval_h+other_h/2,other_h,C["ribbon_gold"],0.87))
        page.append(f'<rect x="1665" y="{625-other_h/2:.2f}" width="25" height="{max(other_h,1):.2f}" fill="{C["green"]}"/>')
    # Pretax -> net and tax, or tax-benefit contributor.
    taxv=fnum(d["income_tax"])
    if taxv>=0:
        net_h=net.value*scale;tax_h=taxv*scale
        page.append(ribbon(pre.x+26,net.x-25,pre.top(scale)+net_h/2,net.y,net_h,C["ribbon_green"],0.90))
        if tax_h>0:
            page.append(ribbon(pre.x+26,tax.x-25,pre.top(scale)+net_h+tax_h/2,tax.y,tax_h,C["ribbon_red"],0.89))
    else:
        page.append(ribbon(pre.x+26,net.x-25,pre.y,net.top(scale)+pre.value*scale/2,pre.value*scale,C["ribbon_green"],0.89))
        t_h=-taxv*scale
        page.append(ribbon(1968,net.x-25,560,net.top(scale)+pre.value*scale+t_h/2,t_h,C["ribbon_green"],0.86))
        page.append(f'<rect x="1947" y="{560-t_h/2:.2f}" width="26" height="{max(t_h,1):.2f}" fill="{C["green"]}"/>')
    # Nodes above all ribbons.
    for st in (revenue,gross,cost,op,opex,pre,net):
        page.append(draw_node(st,scale,C[st.kind]))
    if taxv>=0 and taxv>0:
        page.append(draw_node(tax,scale,C["red"],nodewidth=32,minimum=1))
    # Left source nodes and decorative marks + text.
    for s,y in zip(srcs,ys):
        hh=float(s["amount"])*src_factor*scale
        color=C["orange"] if s.get("color")=="gold" else C["blue"]
        page.append(f'<rect x="{X["source"]-24}" y="{y-hh/2:.2f}" width="46" height="{hh:.2f}" fill="{color}"/>')
        page.append(mark(93,y,s.get("mark",s["name"][:3]),color,C))
        # Use compact two-line labels; keep values max two decimals.
        lines,nlines=multiline_label(352,y-31,s["name"],25,C["navy"],maxchars=19,leading=29)
        page.extend(lines)
        value_y=y+6+(nlines-1)*19
        page.append(text_el(352,value_y,money(float(s["amount"]),d),32,color,"end",700))
        if "yoy" in s:
            page.append(text_el(352,value_y+30,f'{float(s["yoy"]):+.0f}% YoY',19,C["muted"],"end",400))
    # Labels above primary stages.
    def label(stage,name,ty,ay, yoy_key=None,align="middle"):
        col=C[stage.kind]
        page.append(text_el(stage.x,ty,name,32,C["navy"],align,650))
        page.append(text_el(stage.x,ay,money(stage.value,d),46,col,align,700))
        if yoy_key and yoy_key in d:
            page.append(text_el(stage.x,ay+31,f'{float(d[yoy_key]):+.0f}% YoY',18,C["muted"],align,400))
    label(revenue,"Revenue",369,418,"revenue_yoy")
    label(gross,"Gross profit",344,396,"gross_yoy")
    label(op,"Operating profit",316,365,"operating_yoy")
    label(pre,"Pretax income",236,285)
    page.append(text_el(net.x+40,236,"Net profit",27,C["navy"],"start",650))
    page.append(text_el(net.x+40,278,money(net.value,d),35,C["green"],"start",700))
    if "net_yoy" in d:
        page.append(text_el(net.x+40,309,f'{float(d["net_yoy"]):+.0f}% YoY',17,C["muted"],"start",400))
    # Terminal cost labels. No redundant large boxes/panels.
    page.append(text_el(cost.x,1122,"Cost of revenue",29,C["red"],weight=650))
    page.append(text_el(cost.x,1167,money(cost.value,d),42,C["red"],weight=700))
    page.append(text_el(opex.x-43,925,"Operating expenses",26,C["red"],"end",650))
    page.append(text_el(opex.x-43,965,money(opex.value,d),34,C["red"],"end",700))
    if nonop<0:
        page.append(text_el(1997,585,"Non-operating, net",20,C["navy"],"start",550))
        page.append(text_el(1997,620,money(nonop,d),25,C["red"],"start",700))
    elif nonop>0:
        page.append(text_el(1665,594,"Other income",20,C["green"],"end",600))
        page.append(text_el(1665,618,money(nonop,d),22,C["green"],"end",700))
    page.append(text_el(tax.x+40,500,"Income tax" if taxv>=0 else "Income tax benefit",20,C["red"] if taxv>=0 else C["green"],"start",600))
    page.append(text_el(tax.x+40,531,money(taxv,d),27,C["red"] if taxv>=0 else C["green"],"start",700))
    # Expense endpoints.
    for item,y in zip(exp_categories,exp_ys):
        hh=float(item["amount"])*scale
        page.append(f'<rect x="{X["expense_end"]-21}" y="{y-hh/2:.2f}" width="42" height="{max(hh,1):.2f}" fill="{C["red"]}"/>')
        lines,nlines=multiline_label(X["expense_end"]+52,y-12,item["name"],23,C["navy"],"start",650,maxchars=23,leading=26)
        page.extend(lines)
        page.append(text_el(X["expense_end"]+52,y+22+(nlines-1)*18,money(float(item["amount"]),d),29,C["red"],"start",700))
        if "yoy" in item:
            page.append(text_el(X["expense_end"]+52,y+44+(nlines-1)*18,f'{float(item["yoy"]):+.0f}% YoY',16,C["muted"],"start",400))
    # Footer: no watermark or publisher branding.
    page.append(f'<line x1="80" x2="2320" y1="1280" y2="1280" stroke="#D3D6D7" stroke-width="2"/>')
    footer=str(d["source_note"])
    if len(footer)>166:footer=footer[:163]+"..."
    page.append(text_el(83,1318,footer,16,C["muted"],"start",400))
    page.append('</svg>')
    svg='\n'.join(page)
    # The renderer itself never creates unsupported 3-decimal financial values.
    return svg


def write_outputs(d: dict, svg_path: Path, png_path: Path|None=None) -> dict:
    svg=render_svg(d)
    svg_path.parent.mkdir(parents=True,exist_ok=True)
    svg_path.write_text(svg,encoding="utf-8")
    result={"svg":str(svg_path),"png":None,"validation":validate(d)}
    if png_path is not None:
        try:
            import cairosvg
            png_path.parent.mkdir(parents=True,exist_ok=True)
            cairosvg.svg2png(bytestring=svg.encode("utf-8"),write_to=str(png_path),output_width=2400,output_height=1350)
            result["png"]=str(png_path)
        except ImportError:
            result["warning"]="CairoSVG not installed: SVG was generated; PNG unavailable"
    return result
