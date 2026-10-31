#!/usr/bin/env python3
"""Local MCP stdio server for deterministic earnings Sankey rendering.

JSON-RPC 2.0 over newline-separated stdio. No network, no account access.
Outputs only under a dedicated temporary directory, with optional inline PNG content.
"""
from __future__ import annotations
import base64, json, os, re, sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from renderer.engine import validate, write_outputs, STYLE

PROTOCOL="2025-06-18"
OUTPUT=Path(tempfile.gettempdir())/"earnings-graphic-studio"

def respond(obj:dict)->None:
    sys.stdout.write(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')
    sys.stdout.flush()

def ok(id, result):respond({"jsonrpc":"2.0","id":id,"result":result})
def fail(id, code,message):respond({"jsonrpc":"2.0","id":id,"error":{"code":code,"message":str(message)[:1200]}})

def tool_result(payload:dict,is_error=False, png:Path|None=None)->dict:
    contents=[{"type":"text","text":json.dumps(payload,ensure_ascii=False)}]
    if png and png.exists():
        contents.append({"type":"image","data":base64.b64encode(png.read_bytes()).decode('ascii'),"mimeType":"image/png"})
    return {"content":contents,"isError":is_error}

TOOLS=[
    {"name":"get_earnings_template","description":"Get the available editorial layout, input format and QA boundaries. Renderer is deterministic and local; does not fetch filings or verify source truth.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"validate_earnings_ledger","description":"Check revenue, expense, gross, operating, pretax and net reconciliations, and classify rounding and loss-layout cautions. Primary financial source verification is separate.",
     "inputSchema":{"type":"object","properties":{"ledger":{"type":"object","description":"Financial ledger per skills/earnings-sankey/references/ledger-format.md"}},"required":["ledger"],"additionalProperties":False}},
    {"name":"render_earnings_sankey","description":"Render a verified ledger to original Amazon-inspired, vector-editable Sankey SVG and optional PNG preview. Requires positive income stages for full proportional layout; refuses invalid ledgers. Does not imply independent visual QA.",
     "inputSchema":{"type":"object","properties":{"ledger":{"type":"object"},"output_name":{"type":"string","description":"Safe filename stem"},"include_png":{"type":"boolean","default":True},"include_preview":{"type":"boolean","default":True}},"required":["ledger"],"additionalProperties":False}}
]

def dispatch(req:dict):
    mid=req.get('id')
    method=req.get('method','')
    params=req.get('params') or {}
    if method=='initialize':
        ok(mid,{"protocolVersion":PROTOCOL,"capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"earnings-graphic-studio","version":"0.1.0"}});return
    if method in ('notifications/initialized','notifications/cancelled','ping/notification'):
        return
    if method=='ping':ok(mid,{});return
    if method=='tools/list':ok(mid,{"tools":TOOLS});return
    if method=='tools/call':
        name=params.get('name');args=params.get('arguments') or {}
        if name=='get_earnings_template':
            ok(mid,tool_result({"name":STYLE["template"],"canvas":STYLE["canvas"],"positions":STYLE["x_positions"],
                "supports":["positive-profit GAAP Sankeys","tax benefits","positive or negative nonoperating adjustments","editable SVG","optional PNG"],
                "requires_verified_ledger":True,"source_data_fetched":False,"independent_visual_review":False,
                "deployment":"LOCAL stdio only. ChatGPT web/mobile require real hosted MCP endpoint."}));return
        if name=='validate_earnings_ledger':
            if not isinstance(args.get('ledger'),dict):
                ok(mid,tool_result({"error":"ledger must be an object"},True));return
            report=validate(args['ledger'])
            ok(mid,tool_result(report,not report['passed']));return
        if name=='render_earnings_sankey':
            if not isinstance(args.get('ledger'),dict):
                ok(mid,tool_result({"error":"ledger must be an object"},True));return
            name=args.get('output_name','earnings-graphic')
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,62}',name):
                ok(mid,tool_result({"error":"output_name must be 1–63 filename-safe characters"},True));return
            OUTPUT.mkdir(parents=True,exist_ok=True)
            svg=OUTPUT/(name+'.svg')
            png=OUTPUT/(name+'.png') if args.get('include_png',True) else None
            try:
                result=write_outputs(args['ledger'],svg,png)
                body={"status":"RENDERED_NEEDS_VISUAL_QA","files":{"svg":result['svg'],"png":result['png']},
                      "financial_validation":result['validation'],"image_dimensions":{"width":2400,"height":1350},
                      "layout":"amazon_editorial_v1","next_step":"Inspect actual exported PNG/SVG at full resolution. Rendering success does not imply design QA approval."}
                if result.get('warning'):body['warning']=result['warning']
                ok(mid,tool_result(body,False,png if args.get('include_preview',True) else None));return
            except Exception as exc:
                ok(mid,tool_result({"status":"FAILED","error":str(exc)},True));return
        ok(mid,tool_result({"error":f"Unknown tool {name}"},True));return
    if mid is not None:fail(mid,-32601,f"Unknown method {method}")


def main():
    for line in sys.stdin:
        if not line.strip():continue
        try:
            req=json.loads(line)
            if isinstance(req,list):
                for each in req:
                    if isinstance(each,dict):dispatch(each)
            elif isinstance(req,dict):dispatch(req)
            else:fail(None,-32600,"Request must be an object")
        except Exception as exc:
            print('earnings-studio error:',str(exc),file=sys.stderr)
            fail(None,-32603,'Invalid request')

if __name__=='__main__': main()
