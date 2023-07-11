import os
import sys
import time

def timeit(name):
    def decorator(fn):
        def fn_with_timing(*args, **kwargs):
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            t1 = time.perf_counter()
            sys.stderr.write(f"{name} = {int((t1-t0)*1000)}ms\n")
            return result
        if os.environ.get("RLVIDEO_PERFORMANCE"):
            return fn_with_timing
        else:
            return fn
    return decorator

