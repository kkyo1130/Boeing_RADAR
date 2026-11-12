"""Local simulated display synchronization. Labels always come from the operator."""
import json
import time
from urllib.request import Request, urlopen

PRESETS = [('270','03000'),('120','05500'),('090','12000'),('315','08500'),
           ('180','25000'),('045','10500'),('359','00900'),('006','36000')]

def validate_labels(h, a):
    if not (len(h)==3 and h.isascii() and h.isdigit() and int(h)<=359 and
            len(a)==5 and a.isascii() and a.isdigit() and int(a)<=99900):
        raise ValueError('HDG: 000–359; ALT: 00000–99900')

class DisplaySync:
    def __init__(self, base, client, settle=1.0):
        self.base, self.client, self.settle = base.rstrip('/'), client, settle
        self.command = None
        self.ready_since = None

    def request(self, path, data=None):
        body = None if data is None else json.dumps(data).encode()
        with urlopen(Request(self.base+'/api/mcp-auto/'+path, data=body,
                            headers={'Content-Type':'application/json'}), timeout=1) as response:
            return json.load(response)

    def set(self, h, a):
        validate_labels(h,a)
        self.command = None
        self.ready_since = None
        self.command = self.request('set', dict(heading=int(h), altitude=int(a), client=self.client))

    def ready(self):
        try:
            state = self.request('state')
            valid = self.command and state.get('ready') and all(
                state.get(k)==self.command.get(k) for k in ('seq','client','heading','altitude'))
        except Exception:
            valid = False
        if not valid:
            self.ready_since = None
            return False
        if self.ready_since is None:
            self.ready_since = time.monotonic()
        return time.monotonic()-self.ready_since >= self.settle
