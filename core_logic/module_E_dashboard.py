# module_E_dashboard.py
# 完整 HTML Dashboard (單頁) 127.0.0.1:8787

import threading
import http.server
import socketserver
import json

PORT = 8787

# 由 main.py 塞資料進來
shared_state = {
    "orders": [],
    "positions": [],
    "fills": [],
    "signals": [],
    "health": {"status": "OK", "heartbeat": 0},
}

# -------------------------------------------------
# HTML 模板（單頁）
# -------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Quantty Dashboard</title>
    <style>
        body { font-family: Arial; margin: 20px; background:#f4f4f4; }
        h1 { color: #333; }
        .section { margin-bottom: 40px; padding:20px; background:white; border-radius:8px; }
        table { width: 100%; border-collapse: collapse; margin-top:10px; }
        th { background:#333; color:white; padding:8px; }
        td { border:1px solid #ccc; padding:8px; background:white; }
        .good { color:green; }
        .bad { color:red; }
    </style>
</head>
<body>
    <h1>Quantty Trading Dashboard</h1>

    <div class="section">
        <h2>Health</h2>
        <p>Status: <span id="health_status"></span></p>
        <p>Heartbeat: <span id="heartbeat"></span></p>
    </div>

    <div class="section">
        <h2>Open Orders</h2>
        <table id="orders_table"></table>
    </div>

    <div class="section">
        <h2>Positions</h2>
        <table id="positions_table"></table>
    </div>

    <div class="section">
        <h2>Fills</h2>
        <table id="fills_table"></table>
    </div>

    <div class="section">
        <h2>Pending Signals</h2>
        <table id="signals_table"></table>
    </div>

<script>
function refresh() {
    fetch("/data").then(r => r.json()).then(d => {
        
        document.getElementById("health_status").innerHTML = 
            d.health.status == "OK" ? "<span class='good'>OK</span>" : "<span class='bad'>ERROR</span>";

        document.getElementById("heartbeat").innerText = d.health.heartbeat;

        // table rendering helper
        function renderTable(elemId, data) {
            let html = "<tr>";
            if (data.length === 0) {
                document.getElementById(elemId).innerHTML = "<tr><td>No Data</td></tr>";
                return;
            }
            for (let k of Object.keys(data[0])) html += "<th>" + k + "</th>";
            html += "</tr>";
            for (let row of data) {
                html += "<tr>";
                for (let v of Object.values(row)) html += "<td>" + v + "</td>";
                html += "</tr>";
            }
            document.getElementById(elemId).innerHTML = html;
        }

        renderTable("orders_table", d.orders);
        renderTable("positions_table", d.positions);
        renderTable("fills_table", d.fills);
        renderTable("signals_table", d.signals);
    });
}

setInterval(refresh, 3000);
refresh();
</script>

</body>
</html>
"""

# -------------------------------------------------
# HTTP Handler
# -------------------------------------------------
class DashboardHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())
            return

        if self.path == "/data":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(shared_state).encode())
            return

        self.send_error(404, "Not Found")


# -------------------------------------------------
# 啟動 Dashboard Server（背景 Thread）
# -------------------------------------------------
def start_dashboard():
    def run():
        with socketserver.TCPServer(("127.0.0.1", PORT), DashboardHandler) as httpd:
            httpd.serve_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

