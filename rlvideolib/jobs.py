import threading

class NonThreadedBackgroundWorker:

    def add(self, description, result_fn, work_fn, *args, **kwargs):
        result_fn(work_fn(*args, **kwargs))

class BackgroundWorker:

    """
    >>> def display_status(text):
    ...     print(f"STATUS = {text}")

    >>> def on_main_thread_fn(fn, *args):
    ...     fn(*args)

    >>> def on_result(result):
    ...     print(f"RESULT = {result}")

    >>> worker = BackgroundWorker(
    ...     display_status=display_status,
    ...     on_main_thread_fn=on_main_thread_fn
    ... )
    STATUS = Ready

    >>> worker.add("foo", on_result, lambda a, b: a+b, 1, 2)
    RESULT = 3
    STATUS = Ready
    STATUS = Ready
    """

    def __init__(self, display_status, on_main_thread_fn):
        self.display_status = display_status
        self.jobs = []
        self.description = None
        self.on_main_thread_fn = on_main_thread_fn
        self.start_next_job_if_idle()

    def add(self, description, result_fn, work_fn, *args, **kwargs):
        self.jobs.append((description, result_fn, work_fn, args, kwargs))
        self.start_next_job_if_idle()

    def start_next_job_if_idle(self):
        if self.description is None:
            self.start_next_job()
        if self.description:
            self.display_status(f"{self.description} {len(self.jobs)} left in queue...")
        else:
            self.display_status("Ready")

    def start_next_job(self):
        def result(*args):
            result_fn(*args)
            self.description = None
            self.start_next_job_if_idle()
        def worker():
            self.on_main_thread_fn(result, work_fn(*args, **kwargs))
        if self.jobs:
            self.description, result_fn, work_fn, args, kwargs = self.jobs.pop(-1)
            thread = threading.Thread(target=worker)
            thread.daemon = True
            thread.start()
