"""Authenticated stateless Streamable HTTP MCP for Earnings Graphic Studio."""
from __future__ import annotations
import base64,hmac,json,os,re,sys,tempfile
from pathlib import Path
from fastapi import FastAPI,Header,HTTPException,Request
from fastapi.responses import JSONResponse,Response
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from renderer.engine import validate,write_outputs,STYLE
from server.mcp_server import TOOLS,PROTOCOL
app=FastAPI(title="Earnings Graphic Studio MCP",docs_url=None,redoc_url=None)
@app.get("/health")
def health(): return {"ok":True,"service":"earnings-graphic-studio","protocol":"streamable-http"}
@app.post("/mcp")
async def mcp(request:Request,authorization:str|None=Header(default=None)):
    secret=os.environ.get("MCP_BEARER_TOKEN")
    if not secret: raise HTTPException(status_code=503,detail="MCP_BEARER_TOKEN not configured")
    if not authorization or not hmac.compare_digest(authorization,"Bearer "+secret):
        raise HTTPException(status_code=401,detail="Invalid authorization",headers={"WWW-Authenticate":"Bearer"})
    obj=await request.json()
    if not isinstance(obj,dict): return JSONResponse({"jsonrpc":"2.0","id":None,"error":{"code":-32600,"message":"Request must be object"}},status_code=400)
    mid=obj.get("id");method=obj.get("method");params=obj.get("params") or {}
    if method=="notifications/initialized": return Response(status_code=202)
    def wrap(result):return JSONResponse({"jsonrpc":"2.0","id":mid,"result":result},headers={"MCP-Protocol-Version":PROTOCOL})
    def tool_result(info,error=False,png=None):
        c=[{"type":"text","text":json.dumps(info,ensure_ascii=False)}]
        if png and Path(png).exists():
            c.append({"type":"image","mimeType":"image/png","data":base64.b64encode(Path(png).read_bytes()).decode("ascii")})
        return {"content":c,"isError":error}
    if method=="initialize":return wrap({"protocolVersion":PROTOCOL,"capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"earnings-graphic-studio","version":"0.2.0"}})
    if method=="ping":return wrap({})
    if method=="tools/list":return wrap({"tools":TOOLS})
    if method=="tools/call":
        name=params.get("name");args=params.get("arguments") or {}
        if name=="get_earnings_template":
            return wrap(tool_result({"template":STYLE["template"],"canvas":STYLE["canvas"],"positions":STYLE["x_positions"],"requires_verified_ledger":True,"source_data_fetched":False,"independent_visual_review":False}))
        if name in ("validate_earnings_ledger","render_earnings_sankey"):
            ledger=args.get("ledger")
            if not isinstance(ledger,dict):return wrap(tool_result({"error":"ledger must be object"},True))
            if name=="validate_earnings_ledger":
                result=validate(ledger);return wrap(tool_result(result,not result["passed"]))
            stem=args.get("output_name","earnings-graphic")
            if not isinstance(stem,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}",stem):
                return wrap(tool_result({"error":"Invalid output name"},True))
            try:
                with tempfile.TemporaryDirectory(prefix="earnings-mcp-") as tmp:
                    svg=Path(tmp)/(stem+".svg")
                    png=Path(tmp)/(stem+".png") if args.get("include_png",True) else None
                    rendered=write_outputs(ledger,svg,png)
                    result={"status":"RENDERED_NEEDS_VISUAL_QA","svg_base64":base64.b64encode(svg.read_bytes()).decode("ascii"),"financial_validation":rendered["validation"],"image_dimensions":{"width":2400,"height":1350}}
                    if png and png.exists():result["png_base64"]=base64.b64encode(png.read_bytes()).decode("ascii")
                    return wrap(tool_result(result,False,png if args.get("include_preview",True) else None))
            except Exception as ex:return wrap(tool_result({"error":str(ex)[:300]},True))
        return wrap(tool_result({"error":"Unknown tool"},True))
    return JSONResponse({"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":"Unknown method"}},status_code=400)
