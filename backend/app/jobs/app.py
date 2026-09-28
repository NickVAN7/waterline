"""The procrastinate app every job registers on.

Its connector is a placeholder that is never opened: enqueueing always passes the caller's own
connection (app/jobs/enqueue.py), and the worker swaps in a real connector while it runs
(app/jobs/worker.py). Importing this module registers no jobs; only the worker imports them.
"""

import procrastinate

jobs_app = procrastinate.App(connector=procrastinate.PsycopgConnector())
