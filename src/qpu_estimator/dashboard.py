"""Simple web dashboard for QPU-Estimator."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

from qiskit import QuantumCircuit

from .orchestrator import QPUEstimator
from .export import ReportExporter


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the QPU-Estimator dashboard."""

    def do_GET(self):
        if self.path == "/":
            self._serve_dashboard()
        elif self.path == "/api/backends":
            self._serve_backends()
        else:
            self._send_error(404, "Not found")

    def do_POST(self):
        if self.path == "/api/estimate":
            self._handle_estimate()
        else:
            self._send_error(404, "Not found")

    def _serve_dashboard(self):
        html = """<!DOCTYPE html>
<html>
<head>
    <title>QPU-Estimator Dashboard</title>
    <style>
        body { font-family: sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f4f4f4; }
        .metric { display: inline-block; padding: 10px 20px; margin: 5px; background: #e3f2fd; border-radius: 4px; }
        .warning { color: #ff6f00; }
        .error { color: #d32f2f; }
    </style>
</head>
<body>
    <h1>QPU-Estimator Dashboard</h1>
    <p>Real-time quantum hardware resource estimation</p>
    <div id="metrics"></div>
    <h2>Backend Comparison</h2>
    <table id="results">
        <thead>
            <tr><th>Backend</th><th>Depth</th><th>Time (ms)</th><th>Shots</th><th>Fidelity</th><th>Credits</th></tr>
        </thead>
        <tbody></tbody>
    </table>
    <script>
        async function loadBackends() {
            const res = await fetch('/api/backends');
            const data = await res.json();
            document.getElementById('metrics').innerHTML =
                '<div class="metric">Available backends: ' + data.length + '</div>';
        }
        loadBackends();
    </script>
</body>
</html>"""
        self._send_response(200, "text/html", html.encode())

    def _serve_backends(self):
        estimator = QPUEstimator(use_live=False)
        backends = estimator.list_live_backends() + estimator.profiler.list_backends()
        self._send_json({"backends": backends})

    def _handle_estimate(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)

        circuit_data = data.get("circuit", [])
        backend = data.get("backend", "ibm_heron")

        circuit = QuantumCircuit(len(circuit_data))
        for gate in circuit_data:
            if gate["type"] == "h":
                circuit.h(gate["qubit"])
            elif gate["type"] == "cx":
                circuit.cx(gate["control"], gate["target"])
            elif gate["type"] == "measure":
                circuit.measure_all()

        estimator = QPUEstimator(use_live=False)
        report = estimator.estimate(circuit, backend)

        self._send_json({
            "backend": report.backend_name,
            "depth": report.transpiled_depth,
            "time_ms": report.estimated_execution_time_ms,
            "shots": report.optimal_shots,
            "fidelity": report.estimated_fidelity,
            "credits": report.estimated_credits,
            "notes": report.notes,
        })

    def _send_response(self, status: int, content_type: str, data: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, data: dict):
        self._send_response(200, "application/json", json.dumps(data).encode())

    def _send_error(self, status: int, message: str):
        self._send_response(status, "text/plain", message.encode())

    def log_message(self, format, *args):
        pass  # Suppress logs


def run_dashboard(host: str = "localhost", port: int = 8080):
    """Run the QPU-Estimator dashboard."""
    server = HTTPServer((host, port), DashboardHandler)
    print(f"QPU-Estimator dashboard running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    run_dashboard()
