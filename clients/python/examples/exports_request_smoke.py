from __future__ import annotations
import argparse, json
from aris3_client_sdk import ApiSession, load_config, new_idempotency_keys
from aris3_client_sdk.clients.exports_client import ExportsClient
from aris3_client_sdk.exceptions import ApiError
p=argparse.ArgumentParser(description='Exports request smoke');p.add_argument('--env-file',default=None);p.add_argument('--source-type',default='reports_daily');p.add_argument('--format',default='csv');p.add_argument('--store-id');p.add_argument('--from-date',dest='from_value');p.add_argument('--to-date',dest='to_value');p.add_argument('--timezone',default='UTC');a=p.parse_args();k=new_idempotency_keys()
try:
 s=ApiSession(load_config(a.env_file));c=ExportsClient(http=s._http(),access_token=s.token);r=c.request_export({'source_type':a.source_type,'format':a.format,'filters':{'store_id':a.store_id,'from':a.from_value,'to':a.to_value,'timezone':a.timezone},'transaction_id':k.transaction_id},idempotency_key=k.idempotency_key)
 print(json.dumps({'export_id':r.export_id,'status':r.status,'artifact':r.artifact(api_base_url=s.config.api_base_url).model_dump(),'trace_id':r.trace_id},indent=2))
except ApiError as exc:
 print(json.dumps({'error':exc.code,'message':exc.message,'trace_id':exc.trace_id},indent=2));raise SystemExit(1)
