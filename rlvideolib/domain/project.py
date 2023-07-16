import os
import time

import mlt

from rlvideolib.debug import timeit
from rlvideolib.domain.cut import Cuts
from rlvideolib.domain.source import FileSource
from rlvideolib.domain.source import Sources
from rlvideolib.domain.source import TextSource

class Event:

    """
    >>> def listener():
    ...     print("got event")
    >>> event = Event()
    >>> event.trigger()
    >>> event.listen(listener)
    >>> event.trigger()
    got event
    """

    def __init__(self):
        self.listeners = []

    def trigger(self):
        for fn in self.listeners:
            fn()

    def listen(self, fn):
        self.listeners.append(fn)

class Project:

    # TODO: make observable and GUI listens for change events

    @staticmethod
    def new(background_worker=None):
        """
        >>> isinstance(Project.new(), Project)
        True
        """
        class NonThreadedBackgroundWorker:
            def add(self, description, result_fn, work_fn, *args, **kwargs):
                result_fn(work_fn(*args, **kwargs))
        return Project(
            NonThreadedBackgroundWorker() if background_worker is None
            else background_worker
        )

    @staticmethod
    def load(args, background_worker=None):
        if args:
            project = Project.new(background_worker)
            for arg in args:
                project.add_clip(arg)
            return project
        else:
            return Project.with_test_clips(background_worker)

    @staticmethod
    def with_test_clips(background_worker=None):
        project = Project.new(background_worker)
        for i in range(int(os.environ.get("RLVIDEO_PERFORMANCE", "1"))):
            offset = i*50
            project.add_clip("resources/one-to-five.mp4")
            project.add_clip("resources/one.mp4")
            project.add_clip("resources/two.mp4")
            project.add_clip("resources/three.mp4")
        return project

    def __init__(self, background_worker):
        self.profile = self.create_profile()
        self.cuts = Cuts.empty()
        self.sources = Sources.empty()
        self.proxy_source_loader = ProxySourceLoader(
            profile=self.profile,
            project=self,
            background_worker=background_worker
        )

    def get_preview_profile(self):
        profile = self.create_profile()
        profile.set_width(960)
        profile.set_height(540)
        return profile

    def create_profile(self):
        return mlt.Profile("uhd_2160p_25")

    def export(self):
        path = "export.mp4"
        producer = self.split_into_sections().to_mlt_producer(
            profile=self.profile,
            cache=ExportSourceLoader(profile=self.profile, project=self)
        )
        consumer = mlt.Consumer(self.profile, "avformat")
        consumer.set("target", path)
        consumer.connect(producer)
        consumer.start()
        while consumer.is_stopped() == 0:
            print(f"Progress {producer.position()}/{producer.get_playtime()}")
            time.sleep(1)
        print(f"Done: {path}")

    def get_label(self, source_id):
        return self.get_source(source_id).get_label()

    def get_source(self, source_id):
        return self.sources.get(source_id)

    def add_clip(self, path):
        # TODO: move to transaction
        producer = mlt.Producer(self.profile, path)
        source = FileSource(id=None, path=path, length=producer.get_playtime()).with_unique_id()
        self.sources = self.sources.add(source)
        self.proxy_source_loader.load(source.id)
        self.cuts = self.cuts.add(source.create_cut(0, source.length).move(self.cuts.end))

    def add_text_clip(self, text, length, id=None):
        # TODO: move to transaction
        source = TextSource(id=id, text=text)
        if id is None:
            source = source.with_unique_id()
        self.sources = self.sources.add(source)
        self.proxy_source_loader.load(source.id)
        self.cuts = self.cuts.add(source.create_cut(0, length).move(self.cuts.end))

    def new_transaction(self):
        return Transaction(self)

    @timeit("Project.split_into_sections")
    def split_into_sections(self):
        return self.cuts.split_into_sections()

    @timeit("Project.get_preview_mlt_producer")
    def get_preview_mlt_producer(self):
        """
        >>> _ = mlt.Factory().init()
        >>> isinstance(Project.with_test_clips().get_preview_mlt_producer(), mlt.Playlist)
        True
        """
        return self.split_into_sections().to_mlt_producer(
            profile=self.profile,
            cache=self.proxy_source_loader
        )

class ExportSourceLoader:

    def __init__(self, profile, project):
        self.profile = profile
        self.project = project

    def get_source_mlt_producer(self, source_id):
        return self.project.get_source(source_id).load(self.profile)

class ProxySourceLoader:

    def __init__(self, project, profile, background_worker):
        self.project = project
        self.profile = profile
        self.background_worker = background_worker
        self.mlt_producers = {}

    def load(self, source_id):
        def store(producer):
            self.mlt_producers[source_id] = producer
        self.background_worker.add(
            f"Generating proxy for {self.project.get_source(source_id).get_label()}.",
            store,
            self.project.get_source(source_id).load_proxy,
            self.profile,
            self.project.get_preview_profile().width(),
            self.project.get_preview_profile().height(),
        )

    def get_source_mlt_producer(self, source_id):
        if source_id in self.mlt_producers:
            return self.mlt_producers[source_id]
        else:
            producer = mlt.Producer(self.profile, "pango")
            producer.set("text", "Loading...")
            producer.set("bgcolour", "red")
            return producer

class Transaction:

    def __init__(self, project):
        self.project = project
        self.initial_cuts = project.cuts

    def rollback(self):
        self.project.cuts = self.initial_cuts

    def modify(self, cut_to_modify, fn):
        self.project.cuts = self.project.cuts.modify(cut_to_modify, fn)
