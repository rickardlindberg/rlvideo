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

    >>> class MockThreading:
    ...     def __init__(self):
    ...         self.threads = []
    ...     def Thread(self, target):
    ...        class MockThread:
    ...            daemon = False
    ...            def start(self):
    ...               pass
    ...            def give_time_slot(self):
    ...               target()
    ...        self.threads.append(MockThread())
    ...        return self.threads[-1]
    ...     def run_one(self):
    ...        self.threads.pop(0).give_time_slot()
    >>> mock_threading = MockThreading()

    >>> worker = BackgroundWorker(
    ...     display_status=display_status,
    ...     on_main_thread_fn=on_main_thread_fn,
    ...     threading=mock_threading
    ... )
    STATUS = Ready

    >>> worker.add("add", on_result, lambda a, b: a+b, 1, 2)
    STATUS = (0 pending) add

    >>> worker.add("sub", on_result, lambda a, b: a-b, 1, 2)
    STATUS = (1 pending) add

    >>> mock_threading.run_one()
    RESULT = 3
    STATUS = (0 pending) sub

    >>> mock_threading.run_one()
    RESULT = -1
    STATUS = Ready
    """

    def __init__(self, display_status, on_main_thread_fn, threading=threading):
        self.threading = threading
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
            self.display_status(f"({len(self.jobs)} pending) {self.current_job.description}")
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
            thread = self.threading.Thread(target=worker)
            thread.daemon = True
            thread.start()
            self.current_job = job

class Job:

    def __init__(self, description, result_fn, work_fn, args):
        self.description = description
        self.result_fn = result_fn
        self.work_fn = work_fn
        self.args = args

    def do_work(self, worker):
        return self.work_fn(*self.args)
