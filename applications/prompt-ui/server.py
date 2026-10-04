#!/usr/bin/env python3
"""
AgenticOS v0.1 Alpha - Local Development Web Server
Zero-dependency static server using Python's standard library.
"""

import http.server
import socketserver
import sys
import os

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class AgenticOSHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Enable CORS and disable aggressive caching for local prototyping
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

def run_server():
    port = PORT
    for attempt in range(5):
        try:
            with socketserver.TCPServer(("", port), AgenticOSHandler) as httpd:
                print("=" * 64)
                print("  AGENTICOS v0.1 ALPHA - LOCAL UI SHELL IS LIVE")
                print("=" * 64)
                print(f"  Directory: {DIRECTORY}")
                print(f"  URL:       http://localhost:{port}")
                print(f"  Alt URL:   http://127.0.0.1:{port}")
                print("=" * 64)
                print("  Open Google Chrome and navigate to the URL above.")
                print("  Press Ctrl+C to terminate the server.\n")
                sys.stdout.flush()
                httpd.serve_forever()
                break
        except OSError as e:
            if "Address already in use" in str(e) or e.errno == 98 or e.errno == 10048:
                print(f"Port {port} is occupied, trying port {port + 1}...")
                port += 1
            else:
                raise e

if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nAgenticOS local server terminated cleanly.")
        sys.exit(0)
