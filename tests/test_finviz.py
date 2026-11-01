#!/usr/bin/env python3
"""Offline tests: mocked HTTPS export, no credential disclosure."""
import os
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import finviz_api as api

def test():
    assert api.execute_finviz('finviz_connection_status',{})['credential_disclosed'] is False
    with patch.dict(os.environ,{},clear=True):
        try:
            api.get_statements({'ticker':'MSFT'})
            raise AssertionError('Missing token should fail')
        except api.FinvizError as e:
            assert 'not configured' in str(e)

    calls=[]
    class Response:
        headers={'Content-Type':'text/csv',
                 'Content-Disposition':'attachment; filename="MSFT_income_USD.csv"'}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return b'Item,2026-Q2,2026-Q1\nRevenue,100000000,90000000\nNet Income,25000000,24000000\n'
    class Opener:
        def open(self,req,timeout):
            calls.append(req.full_url)
            assert req.full_url.startswith('https://elite.finviz.com/export/')
            return Response()

    with patch.dict(os.environ,{'FINVIZ_API_TOKEN':'private-token-for-testing'},clear=True),patch.object(api,'build_opener',return_value=Opener()):
        data=api.get_statements({'ticker':'msft','statement':'IQ','growth':['yoy_pct']})
        assert data['rows'][0][1]=='100000000'
        assert data['currency_filename']=='MSFT_income_USD.csv'
        assert 'ty=statements' in calls[-1] and 's=IQ' in calls[-1] and 'growth=yoy_pct' in calls[-1]
        api.get_filings({'ticker':'MSFT'})
        assert 'ty=lf' in calls[-1] and 'f=annual-quarterly-current' in calls[-1]
        api.get_earnings_calendar({'date_from':'2026-11-01','date_to':'2026-11-03'})
        assert '/export/calendar/earnings' in calls[-1]

    for bad in [{'ticker':'MSFT;bad'},{'ticker':'MSFT','statement':'BAD'},
                {'ticker':'MSFT','statement':'IA','growth':['qoq_pct']},
                {'ticker':'MSFT','growth':[{}]}]:
        try:
            api.get_statements(bad)
            raise AssertionError('Invalid arguments should fail')
        except api.FinvizError: pass
    for date in ['2026-02-30','2026-01-01?','invalid']:
        try:
            api.get_earnings_calendar({'date_from':date})
            raise AssertionError('Bad date should fail')
        except api.FinvizError: pass
    print('PASS: Finviz offline credential-safe export tests')

if __name__=='__main__':test()
