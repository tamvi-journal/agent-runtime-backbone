"""Synthetic only: loopback fixture, no upstream network calls or credentials."""
from http.server import BaseHTTPRequestHandler,HTTPServer
import json

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        if self.path!="/v1/read/sample":
            self.send_error(404)
            return
        payload=json.dumps({"resource":"sample","value":42}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

def main():
    with HTTPServer(("127.0.0.1",18765),Handler) as server:
        server.serve_forever()

if __name__=="__main__":
    main()
