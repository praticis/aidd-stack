"""Adds to a copy of the prototype a probe of the parent's garbage collection (AIDD_GCPROBE) and a variant that
freezes the parent's heap after map 1 (AIDD_GCFREEZE).   gc_patch.py CODE_DIR"""

import sys
from pathlib import Path
p = Path(sys.argv[1]) / "aidd_indexer/core/pipeline.py"
t = p.read_text()
probe = '''

def _gc_probe() -> None:
    import atexit, gc
    acc = {"t": 0.0, "n": [0, 0, 0], "s": 0.0}
    def cb(phase, info):
        if phase == "start":
            acc["s"] = time.perf_counter()
        else:
            acc["t"] += time.perf_counter() - acc["s"]
            acc["n"][info["generation"]] += 1
    gc.callbacks.append(cb)
    pid = os.getpid()
    atexit.register(lambda: os.getpid() == pid and print(
        f"[gc] seconds={acc['t']:.2f} collections={acc['n']} frozen={gc.get_freeze_count()}", file=sys.stderr))


def _timed('''
assert t.count("\n\ndef _timed(") == 1
t = t.replace("\n\ndef _timed(", probe, 1)
a = '    STATS.clear()\n'
assert t.count(a) == 1
t = t.replace(a, a + '    if os.getenv("AIDD_GCPROBE"):\n        _gc_probe()\n', 1)
b = '    t = _timed("map1", t)\n'
assert t.count(b) == 1
t = t.replace(b, b + '    if os.getenv("AIDD_GCFREEZE"):\n        import gc\n        gc.freeze()\n', 1)
c = '    _timed("compose", t)\n'
assert t.count(c) == 1
t = t.replace(c, c + '    if os.getenv("AIDD_GCFREEZE"):\n        for s in sums:\n            s.scan = None\n', 1)
p.write_text(t)
print("patched", p)
