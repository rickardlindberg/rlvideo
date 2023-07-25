import threading

class NonThreadedBackgroundWorker:

    def add(self, description, result_fn, work_fn, *args):
        result_fn(work_fn(*args))

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
        self.current_job = None
        self.on_main_thread_fn = on_main_thread_fn
        self.on_jobs_changed()

    def add(self, description, result_fn, work_fn, *args):
        self.jobs.append(Job(description, result_fn, work_fn, args))
        self.on_jobs_changed()

    def on_jobs_changed(self):
        if self.can_start_another_job():
            self.start_next_job()
        if self.is_job_running():
            self.display_status(f"{self.current_job.description} {len(self.jobs)} left in queue...")
        else:
            self.display_status("Ready")

    def can_start_another_job(self):
        return self.current_job is None

    def is_job_running(self):
        return self.current_job is not None

    def start_next_job(self):
        def on_job_done(*args):
            job.result_fn(*args)
            self.current_job = None
            self.on_jobs_changed()
        def worker():
            self.on_main_thread_fn(on_job_done, job.do_work(self))
        if self.jobs:
            job = self.jobs.pop(-1)
            thread = threading.Thread(target=worker)
            thread.daemon = True
            thread.start()

class Job:

    def __init__(self, description, result_fn, work_fn, args):
        self.description = description
        self.result_fn = result_fn
        self.work_fn = work_fn
        self.args = args

    def do_work(self, worker):
        return self.work_fn(*self.args)
