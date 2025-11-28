#!/usr/bin/env python3
"""
Simple HTTP server for the gallery with delete API.

Usage:
    python server.py --port 8081
"""

import argparse
import json
import os
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).parent.resolve()
MAPPING_FILE = ROOT_DIR / "image_mapping.json"


class GalleryRequestHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/delete":
            self.send_error(HTTPStatus.NOT_FOUND, "Unsupported endpoint")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            return

        image_path = payload.get("path")
        if not image_path:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing 'path' in payload")
            return

        # Ensure the path is inside the project directory
        image_full_path = (ROOT_DIR / image_path).resolve()
        if not str(image_full_path).startswith(str(ROOT_DIR)):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid image path")
            return

        if not MAPPING_FILE.exists():
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Mapping file not found")
            return

        # Load mapping
        try:
            with open(MAPPING_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Mapping file is invalid JSON")
            return

        if image_path not in mapping:
            self.send_error(HTTPStatus.NOT_FOUND, "Image path not found in mapping")
            return

        # Delete image file if exists
        deleted_file = False
        if image_full_path.exists():
            try:
                image_full_path.unlink()
                deleted_file = True
            except OSError as exc:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Failed to delete image: {exc}")
                return

        # Remove from mapping
        removed_entry = mapping.pop(image_path, None)
        try:
            with open(MAPPING_FILE, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Failed to update mapping: {exc}")
            return

        response = {
            "success": True,
            "deleted_file": deleted_file,
            "removed_entry": removed_entry,
            "remaining": len(mapping),
        }
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))


def run_server(port: int):
    server_address = ("", port)
    handler_class = GalleryRequestHandler
    httpd = HTTPServer(server_address, handler_class)
    print(f"Serving gallery on http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gallery HTTP server with delete API")
    parser.add_argument("--port", type=int, default=8081, help="Port to serve on (default: 8081)")
    args = parser.parse_args()
    os.chdir(ROOT_DIR)
    run_server(args.port)

