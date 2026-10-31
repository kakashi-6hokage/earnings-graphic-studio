#!/usr/bin/env python3
import json, os, re, subprocess, sys, tempfile
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from renderer.engine import validate, render_svg, write_outputs

def test():
  example=json.loads((ROOT/'examples/amazon_illustrative.json').read_text())
  report=validate(example)
  assert report['passed'],report
  assert report['derived']['gross_profit']==107.37
  assert report['derived']['operating_profit']==28.08
  assert report['derived']['net_income']==20.69
  bad=deepcopy(example);bad['revenue']=190
  assert not validate(bad)['passed']
  bad2=deepcopy(example);bad2['net_income']=-9.29
  assert not validate(bad2)['passed']
  bad3=deepcopy(example);bad3['operating_expenses'][0]['amount']+=10
  assert not validate(bad3)['passed']
  svg=render_svg(example)
  assert '<svg ' in svg and '</svg>' in svg
  assert svg.count('<path')>=len(example['sources'])+len(example['operating_expenses'])+5
  assert not re.search(r'\$\d+\.\d{3,}',svg), '3+ monetary decimals in graphic'
  assert 'Third-party sellers' in svg
  with tempfile.TemporaryDirectory() as t:
    p=Path(t);r=write_outputs(example,p/'a.svg',p/'a.png')
    assert (p/'a.svg').is_file()
    if r['png']:assert (p/'a.png').stat().st_size>10000
  # Direct MCP smoke test: initialize, tools/list, validate, render without preview.
  srv=subprocess.Popen([sys.executable,str(ROOT/'server/mcp_server.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=str(ROOT))
  try:
    requests=[
      {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1"}}},
      {"jsonrpc":"2.0","method":"notifications/initialized"},
      {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}},
      {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"validate_earnings_ledger","arguments":{"ledger":example}}},
      {"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"render_earnings_sankey","arguments":{"ledger":example,"output_name":"test-illustrative","include_preview":False}}}]
    for x in requests:srv.stdin.write(json.dumps(x)+'\n')
    srv.stdin.flush()
    results=[json.loads(srv.stdout.readline()) for _ in range(4)]
    assert all('result' in r for r in results),results
    assert any(len(r.get('result',{}).get('tools',[]))==3 for r in results)
    render_result=json.loads(results[-1]['result']['content'][0]['text'])
    assert render_result['status']=='RENDERED_NEEDS_VISUAL_QA'
    assert Path(render_result['files']['svg']).exists()
  finally:
    srv.terminate()
    try:srv.communicate(timeout=4)
    except subprocess.TimeoutExpired:srv.kill()
  print('PASS: financial ledger, decimals, SVG, PNG, MCP initialize/tools/list/validate/render')

if __name__=='__main__':test()
