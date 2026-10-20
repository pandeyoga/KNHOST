"""Local browser test harness: same-origin API proxy and runtime API base adaptation.
Production source remains untouched. Built JS API base is adapted in-memory only.
"""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,unquote
import http.client,mimetypes,json
ROOT=Path(__file__).resolve().parent/'KNHOST-frontend-audit-2026-10-20/frontend/build'
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):self.handle_request()
    def do_POST(self):self.handle_request()
    def do_PUT(self):self.handle_request()
    def do_PATCH(self):self.handle_request()
    def do_DELETE(self):self.handle_request()
    def do_OPTIONS(self):self.handle_request()
    def handle_request(self):
        if self.path.startswith('/api/'):
            size=int(self.headers.get('Content-Length','0'))
            body=self.rfile.read(size) if size else None
            headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','connection','content-length')}
            conn=http.client.HTTPConnection('127.0.0.1',8020,timeout=30)
            try:
                conn.request(self.command,self.path,body=body,headers=headers)
                response=conn.getresponse();data=response.read();self.send_response(response.status)
                for k,v in response.getheaders():
                    if k.lower() not in ('connection','content-length','transfer-encoding','content-encoding'):self.send_header(k,v)
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except Exception as e:
                data=json.dumps({'audit_proxy_error':str(e)}).encode();self.send_response(502);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            finally:conn.close()
            return
        parsed=unquote(urlsplit(self.path).path).lstrip('/')
        target=(ROOT/parsed).resolve()
        if not target.is_relative_to(ROOT.resolve()):self.send_error(400);return
        if not target.is_file():
            if parsed.startswith('static/'):self.send_error(404);return
            target=ROOT/'index.html'
        data=target.read_bytes()
        if target.suffix=='.js':data=data.replace(b'http://127.0.0.1:8020',b'')
        self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target.name)[0] or 'application/octet-stream');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
print('Audit browser same-origin server http://127.0.0.1:3021 -> backend8020',flush=True)
ThreadingHTTPServer(('127.0.0.1',3021),Handler).serve_forever()
