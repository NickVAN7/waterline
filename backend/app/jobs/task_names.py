"""Task names: the only link between enqueueing and job code.

`enqueue.py` defers jobs by name so it never imports job modules (they call services, often in
higher layers; see design-doc §13, "Transactional enqueue"). Job modules register under the same
names. No imports here, so anything may import this module.
"""

PING = "ping"
