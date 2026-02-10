from __future__ import annotations
import argparse, json
from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.exports_client import ExportsClient
from aris3_client_sdk.exceptions import ApiError
p=argparse.ArgumentParser(description='Exports status smoke');p.add_argument('--env-file',default=None);p.add_argument('--export-id',required=True);a=p.parse_args()
try:
 s=ApiSession(load_config(a.env_file));c=ExportsClient(http=s._http(),access_token=s.token);r=c.get_export_status(a.export_id)
 print(json.dumps({'export_id':r.export_id,'status':r.status,'row_count':r.row_count,'trace_id':r.trace_id},indent=2))
except ApiError as exc:
 print(json.dumps({'error':exc.code,'message':exc.message,'trace_id':exc.trace_id},indent=2));raise SystemExit(1)
