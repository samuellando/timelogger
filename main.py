from flask import Flask, request, abort
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
ar = anyrest.addAnyrestHandlers(app, db, "dev-pnkvmziz4ai48pb8.us.auth0.com", "https://timelogger/api", True)

class Interval:
    def __init__(self, id, title, start, end):
        if (isinstance(id, str) and isinstance(title, str) and isinstance(start, (int, float)) and isinstance(end, (int, float))):
            self.id = id
            self.title = title
            self.start = start
            self.end = end
        else:
            raise AttributeError()

    def __eq__(self, other):
        return self.id == other.id and self.title == other.title and self.start == other.start and self.end == other.end

    @staticmethod 
    def fromDict(d):
        if not "id" in d:
            d["id"] = ""
        if not "start" in d:
            d["start"] = time.time() * 1000
        if 'duration' in d:
            return Interval(d["id"], d["title"], d["start"], d["start"] + d["duration"])
        else:
            return Interval(d["id"], d["title"], d["start"], d["end"])

    def toDict(self):
        return {
                "id": self.id,
                "title": self.title,
                "start": self.start,
                "end": self.end
                }

    def copy(self):
        return Interval.fromDict(self.toDict())


class Running:
    def __init__(self, title, start):
        if (isinstance(title, str) and isinstance(start, (int,float, complex))):
            self.title = title
            self.start = start
        else:
            raise AttributeError()

    @staticmethod 
    def fromDict(d):
        return Running(d["title"], d["start"])


    def toDict(self):
        return {
                "title": self.title,
                "start": self.start,
                }

class FrontendRunning(Running):
    def __init__(self, title, start, end=None, fallback=None):
        super().__init__(title, start)
        if (end == None and fallback == None) or (isinstance(end, (int, float, complex)) and isinstance(fallback, Running)):
            self.end =end
            self.fallback = fallback
        else:
            raise AttributeError()

    @staticmethod 
    def fromInterval(i, r=None):
        return FrontendRunning(i.title, i.start, i.end if r is not None else None, r)

    @staticmethod 
    def fromRunning(r):
        return FrontendRunning(r.title, r.start)

    @staticmethod 
    def fromDict(d):
        return FrontendRunning(d["title"], d["start"])

    def toDict(self):
        d = {
                "title": self.title,
                "start": self.start,
                }
        if self.end != None and self.fallback != None:
            d["end"] = self.end
            d["fallback"] = self.fallback.toDict()
        return d

@app.route('/api/running', methods=["get"])
def getRunning():
    now = time.time() * 1000
    timeline = getTimeline(now, now)

    if len(timeline) > 0:
        interval = Interval.fromDict(timeline[-1])
    else:
        interval = None
    
    try:
        fallback = Running.fromDict(ar.get("running/running"))
    except:
        fallback = Running("No running interval started yet.", time.time() * 1000)

    if interval is not None and interval.id != "running":
        running = FrontendRunning.fromInterval(interval, fallback)
    elif interval is not None:
        running = FrontendRunning.fromInterval(interval)
    else:
        running = FrontendRunning.fromRunning(fallback)

    return running.toDict()

@app.route('/api/running', methods=["POST", "PUT"])
def run():
    data = json.loads(request.data)
    if not 'start' in data:
        data['start'] = time.time() * 1000
    running = Running(data['title'], data['start'])
    try: 
        running = ar.put("running/running", running.toDict())
    except:
        running = ar.post("running/running", running.toDict())

    running = FrontendRunning.fromDict(running)
    return running.toDict()


@app.route('/api/settings', methods=["GET"])
def getSettings():
    try:
        settings =  ar.get("settings/settings")
        del settings["id"]
        return settings
    except:
        return {}

@app.route('/api/settings', methods=["POST", "PATCH"])
def setSetting():
    data = json.loads(request.data)
    try:
        settings = ar.patch("settings/settings", data)
    except:
        settings = ar.post("settings/settings", data)
    settings =  ar.get("settings/settings")
    del settings["id"]
    return settings

@app.route('/api/timeline', methods=["POST"])
def postTimeline():
    new = Interval.fromDict(json.loads(request.data))

    logsdb = ar.get("intervals", False)
    for v in logsdb:
        v = Interval.fromDict(v)
        if v.start >= new.start and v.start <= new.end and v.end >= new.end:
            v.start = new.end
            ar.patch("intervals/"+v.id, v.toDict())
        elif v.start >= new.start and v.end <= new.end:
            ar.delete("intervals/"+v.id, v.toDict())

    return ar.post("intervals", new.toDict())

@app.route('/api/timeline/<id>', methods=["PATCH"])
def patchTimeline(id):
    data = json.loads(request.data)
    return ar.patch("intervals/" + id, {"title": data["title"]})

@app.route('/api/timeline', methods=["GET"])
def getTimeline(start=None, end=None):
    args = request.args
    if "start" in args:
        start = float(args["start"])
    else: 
        start = 0
    if "end" in args:
        end = float(args["end"])
    else: 
        end = time.time() * 1000

    running = Running.fromDict(ar.get("running/running"))
    db = ar.get("intervals", False)

    intervals = []
    for v in db:
        intervals.append(Interval.fromDict(v))

    intervals.append(Interval("running", running.title, running.start, end))

    intervals = cutOverlaps(intervals)

    out = []
    for i in intervals:
        insert = True
        if i.end < start:
            insert = False
        elif i.start < start:
            i.start = start

        if i.start > end:
            insert = False
        elif i.end > end:
            i.end = end

        if insert:
            out.append(i.toDict())

    return out

def cutOverlaps(all, backfill=True):
    intervals = sorted(all, key=lambda x: x.start)

    if len(intervals) == 0:
        return []

    results = []

    starts = []
    s = [] # Stack of events at this time.

    t = 0

    for interval in intervals:
        while len(s) > 0 and s[-1].end < interval.start:
            # Clear all the passed events in stack.
            t = s.pop().end
            while len(s) > 0 and s[-1].end <= t:
                s.pop()

            # If there are any events left, cut it around.
            if len(s) > 0:
                p = s[-1]
                starts.append({"start": t, "ref": p})

        # Add the interval to starts
        if len(starts) > 0 and interval.start == starts[-1]["start"]:
            if not interval.id == "running":
                starts[-1]["ref"] = interval
        else:
            starts.append({"start": interval.start, "ref": interval})
        s.append(interval)

    t = starts[-1]["ref"].end

    # Clear the stack.
    while len(s) > 0:
        while len(s) > 0 and s[-1].end <= t:
            s.pop()
        if len(s) > 0:
            p = s.pop()
            starts.append({"start": t, "ref": p})
            t = p.end


    # Convert starts to actual events.
    for i, s in enumerate(starts):
        interval = s["ref"].copy()
        istart = s["start"]
        nextStart = starts[i+1]["start"] if i < len(starts) - 1 else interval.end
        iend = min(nextStart, interval.end)

        interval.start = istart
        interval.end = iend


        if backfill: 
            if interval.start != s["ref"].start and not (i == len(starts) - 1 and  interval.id == "running"):
                res = ar.post("intervals", interval.toDict())
                interval = Interval.fromDict(res)
            elif interval.end != s["ref"].end:
                if interval.id != "":
                    ar.patch("intervals/"+interval.id, interval.toDict())
                else:
                   res = ar.post("intervals", interval.toDict())
                   interval = Interval.fromDict(res)

        results.append(interval)

    return results

@app.route('/')
def index():
    return send_from_directory("build", "index.html")

@app.route('/<path:path>')
def frontend(path):
    try:
        return send_from_directory("build", path)
    except:
        return send_from_directory("build", path+".html")

if __name__ == '__main__':
    from flask_cors import CORS
    CORS(app)
    app.run(host='127.0.0.1', port=8080, debug=True)
    #client = app.test_client()
    #client.get("/api/timeline?start=1681876800000&end=1681963200000", headers={"api-key": ""})
