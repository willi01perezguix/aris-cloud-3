from __future__ import annotations
import argparse, json
from aris3_client_sdk import ApiSession, load_config
from aris3_client_sdk.clients.exports_client import ExportsClient
from aris3_client_sdk.exceptions import ApiError, NotFoundError
p=argparse.ArgumentParser(description='Exports download smoke');p.add_argument('--env-file',default=None);p.add_argument('--export-id',required=True);p.add_argument('--out',default='export.bin');a=p.parse_args()
try:
 s=ApiSession(load_config(a.env_file));c=ExportsClient(http=s._http(),access_token=s.token)
 try:
  payload=c.download_export(a.export_id);open(a.out,'wb').write(payload);print(json.dumps({'saved_to':a.out,'bytes':len(payload)},indent=2))
 except (NotFoundError, ApiError) as exc:
  if isinstance(exc, NotFoundError):
   print('not available in contract');raise SystemExit(0)
  raise
except ApiError as exc:
 print(json.dumps({'error':exc.code,'message':exc.message,'trace_id':exc.trace_id},indent=2));raise SystemExit(1)
