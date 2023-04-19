from flask import Flask, request
from flask import send_from_directory
import json
import firebase_admin
from firebase_admin import firestore
import anyrest
import time
from datetime import datetime

import os
os.environ['GRPC_DNS_RESOLVER'] = 'native'

firebase_app = firebase_admin.initialize_app(options={'projectId': 'timelogger-slando'})
db = firestore.client()

app = Flask(__name__)
ar = anyrest.addAnyrestHandlers(app, db, "dev-pnkvmziz4ai48pb8.us.auth0.com", "https://timelogger/api")

@app.route('/api/run', methods=["POST"])
def run():
    cur = ar["GET"]("run")
    data = json.loads(request.data)
    data["start"] = time.time() * 1000
    l = list(cur.items())
    if len(l) == 0:
        return ar["POST"]("run", data)
    else:
        past = l[0][1]
        past["end"] = data["start"]
        ar["POST"]("logs", past)
        return ar["PATCH"]("run/"+l[0][0], data)

@app.route('/api/logs', methods=["POST"])
def log():
    data = json.loads(request.data)
    if "duration" in data:
        data["start"] = time.time() * 1000
        data["end"] = data["start"] + data["duration"]
    return ar["POST"]("logs", data)

@app.route('/api/timeline', methods=["GET"])
def getTimeline():
    args = request.args;
    start = float(args.get("start"))
    end = float(args.get("end"))
    cur = ar["GET"]("run")
    logs = []
    for k, v in ar["GET"]("logs").items():
        v["id"] = k
        logs.append(v)

    c = list(cur.values())
    if len(c) != 0:
        c[0]["end"] = time.time() * 1000
        logs.append(c[0])

    logs = cutOverlaps(logs, start, end)
    return logs

def cutOverlaps(intervals, start=None, end=None):

    intervals = sorted(intervals, key=lambda x: x["start"])


    s = 0
    e = len(intervals)

    if start is not None:
        for i in intervals:
            if i["end"] < start:
                s += 1
            elif i["start"] < start:
                i["start"] = start
            else:
                break
    if end is not None:
        for i in reversed(intervals):
            if i["start"] > end:
                e -= 1
            elif i["end"] > end:
                i["end"] = end
            else:
                break

    intervals = intervals[s:e]

    result = [intervals[0]]
    for interval in intervals[1:]:
        result.append(interval)
        if interval["start"] < result[-2]["end"]:
            end = result[-2]["end"]
            result[-2]["end"] = interval["start"]
            if interval["end"] < end:
                n = result[-2].copy()
                n["end"] = end
                n["start"] = interval["end"]
                result.append(n)

    return result

@app.route('/')
def index():
    return send_from_directory("build", "index.html")

@app.route('/<path:path>')
def frontend(path):
    return send_from_directory("build", path)

if __name__ == '__main__':
    from flask_cors import CORS
    CORS(app)
    app.run(host='127.0.0.1', port=8080, debug=True)