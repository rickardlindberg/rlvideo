from collections import namedtuple
import os
import time

import mlt

from rlvideolib.debug import timeit
from rlvideolib.domain.cut import Cuts
from rlvideolib.domain.cut import SpaceCut
from rlvideolib.domain.source import FileSource
from rlvideolib.domain.source import Sources
from rlvideolib.domain.source import TextSource
from rlvideolib.events import Event
from rlvideolib.jobs import NonThreadedBackgroundWorker
from rlvideolib.testing import capture_stdout_stderr
from rlvideolib.testing import doctest_absent

class Project:

    @staticmethod
    def new(background_worker=None):
        """
        >>> isinstance(Project.new(), Project)
        True
        """
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
        self.producer_changed_event = Event()
        self.project_data_event = Event()
        self.profile = self.create_profile()
        self.set_project_data(ProjectData.empty())
        self.proxy_source_loader = ProxySourceLoader(
            profile=self.profile,
            project=self,
            background_worker=background_worker
        )
        self.background_worker = background_worker

    def set_project_data(self, project_data):
        self.project_data = project_data
        self.project_data_event.trigger()

    def on_producer_changed(self, fn):
        self.producer_changed_event.listen(fn)
        fn()

    def on_project_data(self, fn):
        self.project_data_event.listen(fn)
        fn()

    def get_preview_profile(self):
        profile = self.create_profile()
        profile.set_width(960)
        profile.set_height(540)
        return profile

    def create_profile(self):
        return mlt.Profile("uhd_2160p_25")

    def export(self):
        """
        >>> project = Project.new()
        >>> with capture_stdout_stderr():
        ...     with project.new_transaction() as transaction:
        ...         cut_id = transaction.add_clip("resources/one.mp4", id="a")
        ...         transaction.modify(cut_id, lambda cut: cut.move(1))
        >>> project.split_into_sections().to_ascii_canvas()
        |%<-a0---------->|
        >>> with capture_stdout_stderr() as export_log:
        ...     project.export()
        >>> doctest_absent(export_log.value, "NaN")
        Yes
        """
        path = "export.mp4"
        producer = self.split_into_sections().to_mlt_producer(
            profile=self.profile,
            cache=ExportSourceLoader(profile=self.profile, project=self)
        )
        def work(progress):
            consumer = mlt.Consumer(self.profile, "avformat")
            consumer.set("target", path)
            consumer.connect(producer)
            consumer.start()
            while consumer.is_stopped() == 0:
                progress(producer.position()/producer.get_playtime())
                time.sleep(0.5)
        self.background_worker.add(
            f"Exporting {path}",
            lambda result: None,
            work,
        )

    def get_label(self, source_id):
        return self.get_source(source_id).get_label()

    def get_source(self, source_id):
        return self.project_data.get_source(source_id)

    def new_transaction(self):
        return Transaction(self)

    def split_into_sections(self):
        return self.project_data.split_into_sections()

    @timeit("Project.get_preview_mlt_producer")
    def get_preview_mlt_producer(self):
        """
        >>> _ = mlt.Factory().init()
        >>> with capture_stdout_stderr():
        ...     project = Project.with_test_clips()
        >>> isinstance(project.get_preview_mlt_producer(), mlt.Playlist)
        True
        """
        playlist = self.split_into_sections().to_mlt_producer(
            profile=self.profile,
            cache=self.proxy_source_loader
        )
        # The one-length space cut allows the playhead cursor to be positioned
        # right after the last clip.
        # TODO: is this the right place to put it?
        SpaceCut(1).add_to_mlt_playlist(
            profile=self.profile,
            cache=self.proxy_source_loader,
            playlist=playlist
        )
        return playlist

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

    def get_source_ids(self):
        return self.sources.get_ids()

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
        self.load_producer = mlt.Producer(self.profile, "pango")
        self.load_producer.set("text", "Loading...")
        self.load_producer.set("bgcolour", "red")

    def ensure_present(self, source_ids):
        for source_id in list(self.mlt_producers.keys()):
            if source_id not in source_ids:
                # TODO: test removal
                self.mlt_producers.pop(source_id)
        for source_id in source_ids:
            if source_id not in self.mlt_producers:
                self.load(source_id)

    def load(self, source_id):
        def store(producer):
            self.mlt_producers[source_id] = producer
            self.project.producer_changed_event.trigger()
        def work(progress):
            return self.project.get_source(source_id).load_proxy(
                self.profile,
                self.project.get_preview_profile(),
                progress
            )
        self.mlt_producers[source_id] = self.load_producer
        self.background_worker.add(
            f"Generating proxy for {self.project.get_source(source_id).get_label()}",
            store,
            work
        )

    def get_source_mlt_producer(self, source_id):
        return self.mlt_producers[source_id]

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
        self.project.proxy_source_loader.ensure_present(self.project.project_data.get_source_ids())
        self.project.producer_changed_event.trigger()

    def modify(self, cut_id, fn):
        self.project.set_project_data(self.project.project_data.modify_cut(cut_id, fn))

    def add_clip(self, path, id=None):
        producer = mlt.Producer(self.project.profile, path)
        source = FileSource(id=id, path=path, length=producer.get_playtime())
        return self.add_source(source, source.length)

    def add_text_clip(self, text, length, id=None):
        return self.add_source(TextSource(id=id, text=text), length)

    def add_source(self, source, length):
        if source.id is None:
            source = source.with_unique_id()
        self.project.set_project_data(self.project.project_data.add_source(source))
        cut = source.create_cut(0, length).move(self.project.project_data.cuts_end)
        self.project.set_project_data(self.project.project_data.add_cut(cut))
        return cut.id
