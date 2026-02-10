from __future__ import annotations
import argparse, json
from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.reports_client import ReportsClient
from aris3_client_sdk.exceptions import ApiError
parser=argparse.ArgumentParser(description='Reports calendar smoke');parser.add_argument('--env-file',default=None);parser.add_argument('--store-id');parser.add_argument('--from-date',dest='from_value');parser.add_argument('--to-date',dest='to_value');parser.add_argument('--timezone',default='UTC');args=parser.parse_args()
try:
 s=ApiSession(load_config(args.env_file));c=ReportsClient(http=s._http(),access_token=s.token);r=c.get_sales_calendar({'store_id':args.store_id,'from':args.from_value,'to':args.to_value,'timezone':args.timezone});
 print(json.dumps({'rows':len(r.rows),'first_row':r.rows[0].model_dump(mode='json') if r.rows else None,'trace_id':r.meta.trace_id},indent=2))
except ApiError as exc:
 print(json.dumps({'error':exc.code,'message':exc.message,'trace_id':exc.trace_id},indent=2));raise SystemExit(1)
