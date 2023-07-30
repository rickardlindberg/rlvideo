import threading

class NonThreadedBackgroundWorker:

    def add(self, description, result_fn, work_fn):
        result_fn(work_fn(lambda progress: None))

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

    >>> worker.add("add", on_result, lambda progress: 1+2)
    STATUS = add | 0 jobs pending

    >>> worker.add("sub", on_result, lambda progress: progress(0.5) or 1-2)
    STATUS = add | 1 jobs pending

    >>> mock_threading.run_one()
    RESULT = 3
    STATUS = sub | 0 jobs pending

    >>> mock_threading.run_one()
    STATUS = sub (50%) | 0 jobs pending
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

    def add(self, description, result_fn, work_fn):
        self.jobs.append(Job(description, result_fn, work_fn))
        self.on_jobs_changed()

    def on_jobs_changed(self):
        if self.can_start_another_job():
            self.start_next_job()
        if self.is_job_running():
            self.display_status(f"{self.current_job.render_description()} | {len(self.jobs)} jobs pending")
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
            # TODO: call on_job_done even on exception
            self.on_main_thread_fn(on_job_done, job.work_fn(progress))
        def progress(progress):
            def foo():
                job.set_progress(progress)
                self.on_jobs_changed()
            self.on_main_thread_fn(foo)
        if self.jobs:
            job = self.jobs.pop(-1)
            thread = self.threading.Thread(target=worker)
            thread.daemon = True
            thread.start()
            self.current_job = job

class Job:

    def __init__(self, description, result_fn, work_fn):
        self.description = description
        self.result_fn = result_fn
        self.work_fn = work_fn
        self.progress = None

    def set_progress(self, progress):
        self.progress = progress

    def render_description(self):
        """
        >>> job = Job("Render foo.mp4", None, None)
        >>> job.render_description()
        'Render foo.mp4'
        >>> job.set_progress(0.4)
        >>> job.render_description()
        'Render foo.mp4 (40%)'
        """
        if self.progress is not None:
            return f"{self.description} ({int(self.progress*100)}%)"
        else:
            return self.description
