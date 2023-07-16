from collections import namedtuple
import os
import time

import mlt

from rlvideolib.debug import timeit
from rlvideolib.domain.cut import Cuts
from rlvideolib.domain.source import FileSource
from rlvideolib.domain.source import Sources
from rlvideolib.domain.source import TextSource
from rlvideolib.events import Event

class Project:

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
            with project.new_transaction() as transaction:
                for arg in args:
                    transaction.add_clip(arg)
            return project
        else:
            return Project.with_test_clips(background_worker)

    @staticmethod
    def with_test_clips(background_worker=None):
        project = Project.new(background_worker)
        with project.new_transaction() as transaction:
            for i in range(int(os.environ.get("RLVIDEO_PERFORMANCE", "1"))):
                offset = i*50
                transaction.add_clip("resources/one-to-five.mp4")
                transaction.add_clip("resources/one.mp4")
                transaction.add_clip("resources/two.mp4")
                transaction.add_clip("resources/three.mp4")
        return project

    def __init__(self, background_worker):
        self.profile = self.create_profile()
        self.set_project_data(ProjectData.empty())
        self.proxy_source_loader = ProxySourceLoader(
            profile=self.profile,
            project=self,
            background_worker=background_worker
        )
        self.producer_changed_event = Event()

    def set_project_data(self, project_data):
        self.project_data = project_data

    def on_producer_changed(self, fn):
        self.producer_changed_event.listen(fn)
        fn()

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
        return self.project_data.get_source(source_id)

    def new_transaction(self):
        return Transaction(self)

    @timeit("Project.split_into_sections")
    def split_into_sections(self):
        return self.project_data.split_into_sections()

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

class ProjectData(namedtuple("ProjectData", "sources,cuts")):

    @staticmethod
    def empty():
        return ProjectData(sources=Sources.empty(), cuts=Cuts.empty())

    @property
    def cuts_end(self):
        return self.cuts.end

    def add_source(self, source):
        return self._replace(sources=self.sources.add(source))

    def add_cut(self, cut):
        return self._replace(cuts=self.cuts.add(cut))

    def modify_cut(self, cut_id, fn):
        return self._replace(cuts=self.cuts.modify(cut_id, fn))

    def get_source(self, source_id):
        return self.sources.get(source_id)

    def split_into_sections(self):
        return self.cuts.split_into_sections()

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
            self.project.producer_changed_event.trigger()
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
        self.initial_data = self.project.project_data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if (exc_type, exc_value, traceback) == (None, None, None):
            self.commit()
        else:
            self.rollback()

    def rollback(self):
        self.project.set_project_data(self.initial_data)

    def commit(self):
        self.project.producer_changed_event.trigger()

    def modify(self, cut_id, fn):
        self.project.set_project_data(self.project.project_data.modify_cut(cut_id, fn))

    def add_clip(self, path):
        producer = mlt.Producer(self.project.profile, path)
        source = FileSource(id=None, path=path, length=producer.get_playtime())
        self.add_source(source, source.length)

    def add_text_clip(self, text, length, id=None):
        self.add_source(TextSource(id=id, text=text), length)

    def add_source(self, source, length):
        if source.id is None:
            source = source.with_unique_id()
        self.project.set_project_data(self.project.project_data.add_source(source))
        self.project.set_project_data(self.project.project_data.add_cut(source.create_cut(0, length).move(self.project.project_data.cuts_end)))
        # TODO: sync proxy loader clips when sources changes
        self.project.proxy_source_loader.load(source.id)
