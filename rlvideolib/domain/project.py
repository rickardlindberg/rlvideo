from collections import namedtuple
import contextlib
import json
import os
import tempfile
import time

import mlt

from rlvideolib.debug import timeit
from rlvideolib.domain.clip import Clip
from rlvideolib.domain.clip import ProxySpec
from rlvideolib.domain.cut import Cut
from rlvideolib.domain.cut import Cuts
from rlvideolib.domain.cut import SpaceCut
from rlvideolib.domain.source import FileSource
from rlvideolib.domain.source import Sources
from rlvideolib.domain.source import TextSource
from rlvideolib.events import Event
from rlvideolib.jobs import NonThreadedBackgroundWorker
from rlvideolib.mlthelpers import LoadingProducer
from rlvideolib.testing import capture_stdout_stderr
from rlvideolib.testing import doctest_equal

class Project:

    """
    >>> tmp = tempfile.TemporaryDirectory()
    >>> path = os.path.join(tmp.name, "foo.rlvideo")
    >>> project = Project.new(path=path)
    >>> with capture_stdout_stderr():
    ...     with project.new_transaction() as transaction:
    ...         _ = transaction.add_text_clip("hello", length=10)
    ...         _ = transaction.add_clip("resources/one.mp4")
    >>> saved_json = json.loads(open(path).read())
    >>> loaded_json = Project.new(path=path).project_data.to_json()
    >>> doctest_equal(loaded_json, saved_json)
    Yes
    """

    @staticmethod
    def new(background_worker=None, path=None):
        """
        >>> isinstance(Project.new(), Project)
        True
        """
        return Project(
            NonThreadedBackgroundWorker() if background_worker is None
            else background_worker,
            path=path
        )

    @staticmethod
    def load(args, background_worker=None):
        if args:
            if args[0].endswith(".rlvideo"):
                path = args.pop(0)
            else:
                path = None
            project = Project.new(background_worker=background_worker, path=path)
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

    def __init__(self, background_worker, path):
        self.producer_changed_event = Event()
        self.project_data_event = Event()
        self.profile = self.create_profile()
        self.set_project_data(ProjectData.load(path=path))
        self.proxy_spec = ProxySpec.from_path(path)
        self.proxy_source_loader = ProxySourceLoader(
            profile=self.profile,
            project=self,
            background_worker=background_worker,
            proxy_spec=self.proxy_spec
        )
        self.background_worker = background_worker
        self.path = path
        self.current_transaction = None

    def ripple_delete(self, cut_id):
        with self.new_transaction() as transaction:
            transaction.ripple_delete(cut_id)

    def split(self, cut_id, position):
        with self.new_transaction() as transaction:
            transaction.split(cut_id, position)

    def save(self):
        if self.path:
            tmp_path = self.path + ".tmp"
            self.project_data.write(tmp_path)
            os.rename(tmp_path, self.path)

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
        return self.proxy_spec.adjust_profile(self.create_profile())

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
        >>> export_log.is_absent("NaN")
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

    def get_cut(self, cut_id):
        return self.project_data.get_cut(cut_id)

    def new_transaction(self):
        """
        >>> project = Project.new()
        >>> transaction = project.new_transaction()
        >>> transaction = project.new_transaction()
        Traceback (most recent call last):
          ...
        ValueError: transaction already in progress
        """
        if self.current_transaction is not None:
            raise ValueError("transaction already in progress")
        self.current_transaction = Transaction(self)
        return self.current_transaction

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

    @staticmethod
    def load(path):
        if path and os.path.exists(path):
            with open(path) as f:
                return ProjectData.from_json(json.load(f))
        else:
            return ProjectData.empty()

    def write(self, path):
        with open(path, "w") as f:
            json.dump(self.to_json(), f)

    @staticmethod
    def from_json(json):
        # TODO: validate the cuts point to valid sources and that they have
        # valid in/out points.
        return ProjectData(
            sources=Sources.from_json(json["sources"]),
            cuts=Cuts.from_json(json["cuts"])
        )

    def to_json(self):
        return {
            "sources": self.sources.to_json(),
            "cuts": self.cuts.to_json(),
        }

    @property
    def cuts_end(self):
        return self.cuts.end

    def add_source(self, source):
        return self._replace(sources=self.sources.add(source))

    def add_cut(self, cut):
        """
        In/Out is modified according to source:

        >>> ProjectData.empty(
        ... ).add_source(
        ...     FileSource(id="source_a", path="a.mp4", length=5)
        ... ).add_cut(
        ...     Cut.test_instance(name="source_a", start=0, end=10, id="cut_a")
        ... ).get_cut("cut_a").in_out
        Region(start=0, end=5)
        """
        return self._replace(cuts=self.cuts.add(self.adjust_cut_in_out(cut)))

    def modify_cut(self, cut_id, fn):
        """
        A cut's out point is adjusted if going outside the limit:

        >>> data = ProjectData.empty()
        >>> data = data.add_source(FileSource(id="source_a", path="a.mp4", length=5))
        >>> data = data.add_cut(Cut.test_instance(name="source_a", start=0, end=3, id="cut_a"))
        >>> data = data.modify_cut("cut_a", lambda cut: cut.move_right(10))
        >>> data.get_cut("cut_a").in_out
        Region(start=0, end=5)
        """
        return self._replace(cuts=self.cuts.modify(
            cut_id,
            lambda cut: self.adjust_cut_in_out(fn(cut))
        ))

    def adjust_cut_in_out(self, cut):
        return self.get_source(cut.source.source_id).limit_in_out(cut)

    def ripple_delete(self, cut_id):
        return self._replace(cuts=self.cuts.ripple_delete(cut_id))

    def split(self, cut_id, position):
        return self._replace(cuts=self.cuts.split(cut_id, position))

    def get_source(self, source_id):
        return self.sources.get(source_id)

    def get_cut(self, cut_id):
        return self.cuts.get(cut_id)

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

    def __init__(self, project, profile, background_worker, proxy_spec):
        self.project = project
        self.profile = profile
        self.background_worker = background_worker
        self.mlt_producers = {}
        self.load_producer = LoadingProducer(self.profile)
        self.proxy_spec = proxy_spec

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
                self.proxy_spec,
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

    # TODO: support slowdown of clip and make sure it works with proxies

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

    def get_cut_ids(self, matcher):
        # TODO: fix law of demeter here
        for cut in self.project.project_data.cuts.cut_map.values():
            if matcher(cut):
                yield cut.id

    def rollback(self):
        with self.cleanup():
            self.reset()

    def commit(self):
        with self.cleanup():
            # TODO: retrieval of proxy clip will not work within transaction
            self.project.proxy_source_loader.ensure_present(self.project.project_data.get_source_ids())
            self.project.producer_changed_event.trigger()
            self.project.save()

    def reset(self):
        self.project.set_project_data(self.initial_data)

    @contextlib.contextmanager
    def cleanup(self):
        try:
            yield
        finally:
            self.project.current_transaction = None
            self.project = None
            self.initial_data = None

    def ripple_delete(self, cut_id):
        self.project.set_project_data(self.project.project_data.ripple_delete(cut_id))

    def split(self, cut_id, position):
        self.project.set_project_data(self.project.project_data.split(cut_id, position))

    def modify(self, cut_id, fn):
        self.project.set_project_data(self.project.project_data.modify_cut(cut_id, fn))

    def add_clip(self, path, id=None):
        source = FileSource(
            id=id,
            path=path,
            length=Clip(
                path
            ).calculate_length_at_fps(mlt_profile=self.project.profile)
        )
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
