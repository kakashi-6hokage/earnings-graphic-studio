#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from renderer.engine import write_outputs

if __name__=='__main__':
  p=argparse.ArgumentParser(description='Render an editorial earnings Sankey from a verified ledger')
  p.add_argument('input',type=Path);p.add_argument('--svg',type=Path,required=True);p.add_argument('--png',type=Path)
  x=p.parse_args()
  try:
    d=json.loads(x.input.read_text(encoding='utf-8'))
    out=write_outputs(d,x.svg,x.png)
    print(json.dumps(out,indent=2))
  except Exception as ex:
    print('ERROR:',ex,file=sys.stderr);sys.exit(1)
