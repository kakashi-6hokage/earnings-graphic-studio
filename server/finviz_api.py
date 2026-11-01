"""Read-only Finviz Elite adapter. Token stays on Render; never returned or logged."""
from __future__ import annotations
import csv
import io
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE='https://elite.finviz.com'
SYMBOL_RE=re.compile(r'[A-Za-z0-9][A-Za-z0-9.\-]{0,19}\Z')
DATE_RE=re.compile(r'\d{4}-\d{2}-\d{2}\Z')
STATEMENTS=frozenset({'IA','IQ','BA','BQ','CA','CQ'})
GROWTH=frozenset({'yoy','yoy_pct','qoq','qoq_pct'})
SOURCES={'factset':None,'reuters':'R'}
MAX_BODY=400_000

class FinvizError(ValueError): pass

class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a credential-bearing request to another URL.
        raise FinvizError('Finviz redirected an export; refused to forward authentication.')

def ticker(value):
    if not isinstance(value,str) or not SYMBOL_RE.fullmatch(value.upper()):
        raise FinvizError('ticker must be one valid stock symbol.')
    return value.upper()

def iso_date(value,name):
    if not isinstance(value,str) or not DATE_RE.fullmatch(value):
        raise FinvizError(f'{name} must be YYYY-MM-DD.')
    from datetime import date
    try: return date.fromisoformat(value)
    except ValueError as exc: raise FinvizError(f'{name} must be a valid calendar date.') from exc

def _download(path,params):
    token=os.getenv('FINVIZ_API_TOKEN','').strip()
    if not token: raise FinvizError('Finviz is not configured. Add FINVIZ_API_TOKEN in Render > Environment.')
    if not 8<=len(token)<=256 or any(c.isspace() for c in token):
        raise FinvizError('FINVIZ_API_TOKEN configuration is invalid; check Render.')
    # Endpoint and all parameters come from trusted code; no arbitrary user URLs.
    url=BASE+path+'?'+urlencode({**params,'auth':token})
    req=Request(url,headers={'Accept':'text/csv','User-Agent':'EarningsGraphicStudio/Finviz-Reader'})
    opener=build_opener(NoRedirects())
    try:
        with opener.open(req,timeout=18) as resp:
            data=resp.read(MAX_BODY+1)
            ctype=resp.headers.get('Content-Type','')
            disp=resp.headers.get('Content-Disposition','')
    except HTTPError as exc:
        if exc.code in (401,403): raise FinvizError('Finviz denied access. Verify the Elite token in Render.') from None
        if exc.code==429: raise FinvizError('Finviz rate limit reached; retry shortly.') from None
        if 300<=exc.code<400: raise FinvizError('Finviz redirected the export; no redirect followed.') from None
        raise FinvizError(f'Finviz returned HTTP {exc.code}.') from None
    except FinvizError: raise
    except (URLError,TimeoutError,OSError):
        # Don't include exception text: it may contain the credential-bearing URL.
        raise FinvizError('Finviz request failed; verify connectivity and retry.') from None
    if len(data)>MAX_BODY: raise FinvizError('Finviz CSV exceeds maximum response size.')
    if 'html' in ctype.lower() or data.lstrip().startswith((b'<html',b'<!DOCTYPE',b'<!doctype')):
        raise FinvizError('Finviz returned a web page, not CSV. Check the Elite token.')
    try: rows=list(csv.reader(io.StringIO(data.decode('utf-8-sig'),newline='')))
    except (UnicodeError,csv.Error): raise FinvizError('Finviz CSV could not be decoded.') from None
    if not rows or not rows[0] or not any(x.strip() for x in rows[0]):
        raise FinvizError('Finviz returned an empty CSV.')
    if len(rows)>550 or any(len(r)>28 or any(len(c)>1500 for c in r) for r in rows):
        raise FinvizError('Finviz CSV is unusually large or malformed.')
    match=re.search(r'filename\s*=\s*"?([A-Za-z0-9_.-]{1,140})"?',disp,re.I)
    return {'columns':rows[0],'rows':rows[1:],'row_count':len(rows)-1,
            'currency_filename':match.group(1) if match else None,
            'units':'Amounts are full units; no implicit scaling to millions or billions.',
            'source':'Finviz Elite CSV; verify material amounts against issuer/SEC filings.'}

def get_statements(a):
    t=ticker(a.get('ticker')); s=a.get('statement','IQ')
    if not isinstance(s,str) or s not in STATEMENTS: raise FinvizError('statement must be IA, IQ, BA, BQ, CA or CQ.')
    order=a.get('order','newest')
    if order not in ('newest','oldest'): raise FinvizError('order must be newest or oldest.')
    source=a.get('source','factset')
    if not isinstance(source,str) or source not in SOURCES: raise FinvizError('source must be factset or reuters.')
    growth=a.get('growth',[])
    if (not isinstance(growth,list) or len(growth)>4 or
        not all(isinstance(x,str) and x in GROWTH for x in growth) or len(set(growth))!=len(growth)):
        raise FinvizError('growth must be a unique list of yoy, yoy_pct, qoq, qoq_pct.')
    if s.endswith('A') and any(x.startswith('qoq') for x in growth):
        raise FinvizError('QoQ growth requires quarterly statements.')
    params={'t':t,'ty':'statements','s':s,'order':order}
    if SOURCES[source]: params['so']=SOURCES[source]
    if growth: params['growth']=','.join(growth)
    return {'ticker':t,'statement':s,'order':order,'data_source':source,'growth':growth,
            **_download('/export/stock',params)}

def get_filings(a):
    t=ticker(a.get('ticker')); cat=a.get('category','annual-quarterly-current')
    if not isinstance(cat,str) or cat not in {'annual-quarterly-current','proxy-materials','registration-statements'}:
        raise FinvizError('Unsupported filing category.')
    return {'ticker':t,'category':cat,
            **_download('/export/stock',{'t':t,'ty':'lf','f':cat,'o':'-filingDate'})}

def get_earnings_calendar(a):
    start=iso_date(a.get('date_from'),'date_from')
    end=iso_date(a['date_to'],'date_to') if a.get('date_to') is not None else start
    if end<start or (end-start).days>90: raise FinvizError('Date range must be 0 to 90 days.')
    params={'dateFrom':start.isoformat()}
    if end!=start: params['dateTo']=end.isoformat()
    return {'date_from':start.isoformat(),'date_to':end.isoformat(),
            **_download('/export/calendar/earnings',params)}

FINVIZ_TOOLS=[
 {'name':'finviz_connection_status','description':'Check Finviz Elite credential configuration on Render without revealing its value.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
 {'name':'get_finviz_statements','description':'Fetch exact, unscaled Finviz Elite financial statements (8 periods). Defaults to quarterly income; corroborate amounts with SEC/issuer filings before publishing.','inputSchema':{'type':'object','properties':{
    'ticker':{'type':'string'},'statement':{'type':'string','enum':sorted(STATEMENTS),'default':'IQ'},
    'source':{'type':'string','enum':['factset','reuters'],'default':'factset'},
    'order':{'type':'string','enum':['newest','oldest'],'default':'newest'},
    'growth':{'type':'array','items':{'type':'string','enum':sorted(GROWTH)},'default':[]}},
    'required':['ticker'],'additionalProperties':False}},
 {'name':'get_finviz_filings','description':'Fetch latest SEC filings for one ticker from Finviz Elite, newest filing date first.','inputSchema':{'type':'object','properties':{'ticker':{'type':'string'},
    'category':{'type':'string','enum':['annual-quarterly-current','proxy-materials','registration-statements'],'default':'annual-quarterly-current'}},
    'required':['ticker'],'additionalProperties':False}},
 {'name':'get_finviz_earnings_calendar','description':'Fetch Finviz Elite earnings calendar and reported-vs-estimated data for a date range of up to 90 days.','inputSchema':{'type':'object','properties':{
    'date_from':{'type':'string','description':'YYYY-MM-DD'},'date_to':{'type':'string','description':'YYYY-MM-DD (optional)'}},
    'required':['date_from'],'additionalProperties':False}}
]

def execute_finviz(name,args):
    if not isinstance(args,dict): raise FinvizError('arguments must be an object.')
    if name=='finviz_connection_status':
        return {'configured':bool(os.getenv('FINVIZ_API_TOKEN','').strip()),
                'credential_source':'Render environment variable FINVIZ_API_TOKEN',
                'credential_disclosed':False,'note':'Does not test Finviz acceptance.'}
    if name=='get_finviz_statements': return get_statements(args)
    if name=='get_finviz_filings': return get_filings(args)
    if name=='get_finviz_earnings_calendar': return get_earnings_calendar(args)
    raise FinvizError('Unknown Finviz tool.')
