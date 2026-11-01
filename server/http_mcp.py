"""Stateless Streamable-HTTP MCP bridge for Earnings Graphic Studio.

Set MCP_BEARER_TOKEN in production. Accepts JSON-RPC single requests at /mcp.
No generated files are published publicly: previews return as MCP image contents.
"""
from __future__ import annotations
import base64
import hmac
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from renderer.engine import validate, write_outputs, STYLE
from server.oauth import router as oauth_router, validate_access_token, BASE as OAUTH_BASE
from server.mcp_server import TOOLS, PROTOCOL
from server.finviz_api import FINVIZ_TOOLS, execute_finviz, FinvizError

app = FastAPI(title="Earnings Graphic Studio MCP", docs_url=None, redoc_url=None)
app.include_router(oauth_router)

@app.get('/health')
def health():
    return {'ok':True,'service':'earnings-graphic-studio','protocol':'streamable-http'}

@app.post('/mcp')
async def mcp(request: Request, authorization: str | None = Header(default=None)):
    if int(request.headers.get('content-length', '0') or '0') > 2500000:
        raise HTTPException(status_code=413,detail='Request too large')
    data=await request.json()
    if not isinstance(data,dict):
        return JSONResponse({'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Request must be object'}},status_code=400)
    mid=data.get('id'); method=data.get('method'); params=data.get('params') or {}
    if method == 'notifications/initialized':
        from fastapi.responses import Response
        return Response(status_code=202)
    def response(result):return JSONResponse({'jsonrpc':'2.0','id':mid,'result':result}, headers={'MCP-Protocol-Version':PROTOCOL})
    def content(payload,error=False, png=None):
        result=[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]
        if png:
            result.append({'type':'image','mimeType':'image/png','data':base64.b64encode(Path(png).read_bytes()).decode('ascii')})
        return {'content':result,'isError':error}
    if method=='initialize':
        return response({'protocolVersion':PROTOCOL,'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'earnings-graphic-studio','version':'0.3.0'}})
    if method=='ping':return response({})
    if method=='tools/list':
        # Tool metadata is safe to discover anonymously. Per-tool securitySchemes
        # are required by ChatGPT to display the OAuth connection flow.
        public_tools=[{**tool,'securitySchemes':[{'type':'oauth2','scopes':['earnings:render']}]} for tool in (TOOLS + FINVIZ_TOOLS)]
        return response({'tools':public_tools})
    if method=='tools/call' and not validate_access_token(authorization):
        # MCP tool-level challenge, in addition to the OAuth discovery endpoints.
        # OpenAI requires both error and error_description in the challenge.
        challenge=(f'Bearer resource_metadata="{OAUTH_BASE}/.well-known/oauth-protected-resource", '
                   'error="invalid_token", error_description="Connect Earnings Graphic Studio to continue"')
        return response({'content':[{'type':'text','text':'OAuth authorization required to use this tool.'}],
                         'isError':True,'_meta':{'mcp/www_authenticate':[challenge]}})
    if not validate_access_token(authorization):
        challenge=(f'Bearer resource_metadata="{OAUTH_BASE}/.well-known/oauth-protected-resource", '
                   'error="invalid_token", error_description="Connect Earnings Graphic Studio to continue"')
        raise HTTPException(status_code=401,detail='OAuth authentication required',
                            headers={'WWW-Authenticate':challenge})
    if method=='tools/call':
        name=params.get('name'); args=params.get('arguments') or {}
        if name in {tool['name'] for tool in FINVIZ_TOOLS}:
            try:
                return response(content(execute_finviz(name,args)))
            except FinvizError as exc:
                # Only sanitized domain-specific errors reach the model. No URLs
                # containing auth tokens, and never expose the environment value.
                return response(content({'error':str(exc)},True))
        if name=='get_earnings_template':
            return response(content({'template':STYLE['template'],'canvas':STYLE['canvas'],'positions':STYLE['x_positions'],'requires_verified_ledger':True,'source_data_fetched':False,'independent_visual_review':False,'deployment':'Hosted HTTP'}))
        if name in ('validate_earnings_ledger','render_earnings_sankey'):
            ledger=args.get('ledger')
            if not isinstance(ledger,dict):return response(content({'error':'ledger must be object'},True))
            if name=='validate_earnings_ledger':
                report=validate(ledger)
                return response(content(report,not report['passed']))
            stem=args.get('output_name','earnings-graphic')
            if not isinstance(stem,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,62}',stem):
                return response(content({'error':'Invalid output_name'},True))
            try:
                with tempfile.TemporaryDirectory(prefix='earnings-mcp-') as tmp:
                    svg=Path(tmp)/(stem+'.svg'); png=Path(tmp)/(stem+'.png') if args.get('include_png',True) else None
                    result=write_outputs(ledger,svg,png)
                    info={'status':'RENDERED_NEEDS_VISUAL_QA','svg_base64':base64.b64encode(svg.read_bytes()).decode('ascii'),'financial_validation':result['validation'],'image_dimensions':{'width':2400,'height':1350},'next_step':'Review actual PNG/SVG visually before publishing.'}
                    if png and png.exists(): info['png_base64']=base64.b64encode(png.read_bytes()).decode('ascii')
                    return response(content(info))
            except Exception as exc:
                return response(content({'error':str(exc)[:300]},True))
        return response(content({'error':'Unknown tool'},True))
    return JSONResponse({'jsonrpc':'2.0','id':mid,'error':{'code':-32601,'message':'Unknown method'}})
