import threading

class NonThreadedBackgroundWorker:

    def add(self, description, result_fn, work_fn, *args, **kwargs):
        result_fn(work_fn(*args, **kwargs))

class BackgroundWorker:

    def __init__(self, display_status, on_main_thread_fn):
        self.display_status = display_status
        self.jobs = []
        self.description = None
        self.on_main_thread_fn = on_main_thread_fn

    def add(self, description, result_fn, work_fn, *args, **kwargs):
        self.jobs.append((description, result_fn, work_fn, args, kwargs))
        self.pop()

    def pop(self):
        def result(*args):
            result_fn(*args)
            self.description = None
            self.pop()
            return False # To only schedule it once
        def worker():
            self.on_main_thread_fn(result, work_fn(*args, **kwargs))
        if self.description is None and self.jobs:
            self.description, result_fn, work_fn, args, kwargs = self.jobs.pop(-1)
            thread = threading.Thread(target=worker)
            thread.daemon = True
            thread.start()
        if self.description:
            self.display_status(f"{self.description} {len(self.jobs)} left in queue...")
        else:
            self.display_status("Ready")
