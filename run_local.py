"""
Local Dev Server — Value Bet Finder

Sirve el frontend estático y las funciones API de Python localmente
sin necesidad de instalar Vercel CLI ni Node.js.
"""

import os
import sys
import http.server
import socketserver
from urllib.parse import urlparse

# Agregar la raíz del proyecto al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Cargar variables de entorno del archivo .env si está python-dotenv instalado
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[LocalServer] Archivo .env cargado con éxito.")
except ImportError:
    print("[LocalServer] Advertencia: python-dotenv no está instalado. Asegúrate de tener las variables en tu sistema.")

# Importar los controladores de la API
try:
    from api.matches import handler as MatchesHandler
    from api.match import handler as MatchDetailHandler
    from api.analyze import handler as AnalyzeHandler
    from api.value_bets import handler as ValueBetsHandler
    print("[LocalServer] Controladores API cargados correctamente.")
except ImportError as e:
    print(f"[LocalServer] Error al importar los controladores de la API: {e}")
    sys.exit(1)

PORT = 8000
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

class LocalDevHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/api/matches":
            MatchesHandler.do_GET(self)
        elif path == "/api/match":
            MatchDetailHandler.do_GET(self)
        elif path == "/api/value-bets":
            ValueBetsHandler.do_GET(self)
        else:
            # Soporte para ruteo estático del frontend
            if path == "/" or path == "":
                self.path = "/index.html"
            elif path.startswith("/match") and not path.endswith(".html") and not "." in path:
                self.path = "/match.html"
            
            # Servir archivo estático
            super().do_GET()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/api/analyze":
            AnalyzeHandler.do_POST(self)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Endpoint no encontrado")

    def do_OPTIONS(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path in ["/api/matches", "/api/match", "/api/value-bets"]:
            MatchesHandler.do_OPTIONS(self)
        elif path == "/api/analyze":
            AnalyzeHandler.do_OPTIONS(self)
        else:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    print("=" * 60)
    print(f"  VALUE BET FINDER — Servidor de Desarrollo Local")
    print("=" * 60)
    print(f"➔ Servidor web iniciado en: http://localhost:{PORT}")
    print(f"➔ Sirviendo frontend desde: {WEB_DIR}")
    print(f"➔ Endpoints API activos: /api/matches, /api/match, /api/value-bets, /api/analyze")
    print(f"➔ Presiona Ctrl+C para detener el servidor")
    print("-" * 60)

    with socketserver.TCPServer(("", PORT), LocalDevHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[LocalServer] Servidor detenido por el usuario.")
