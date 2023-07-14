import os

import mlt

from rlvideolib.debug import timeit
from rlvideolib.domain.cut import Cuts
from rlvideolib.domain.source import FileSource
from rlvideolib.domain.source import Sources
from rlvideolib.domain.source import TextSource

class Project:

    @staticmethod
    def new():
        """
        >>> isinstance(Project.new(), Project)
        True
        """
        return Project()

    @staticmethod
    def with_test_clips():
        project = Project.new()
        for i in range(int(os.environ.get("RLVIDEO_PERFORMANCE", "1"))):
            offset = i*50
            project.add_clip("resources/one-to-five.mp4")
            project.add_clip("resources/one.mp4")
            project.add_clip("resources/two.mp4")
            project.add_clip("resources/three.mp4")
        return project

    def __init__(self):
        self.profile = mlt.Profile()
        self.cuts = Cuts.empty()
        self.sources = Sources.empty()
        self.mlt_producer_cache = MltProducerCache()

    def add_clip(self, path):
        # TODO: move to transaction
        producer = mlt.Producer(self.profile, path)
        source = FileSource(id=None, path=path, length=producer.get_playtime()).with_unique_id()
        self.sources = self.sources.add(source)
        self.cuts = self.cuts.add(source.create_cut(0, source.length).move(self.cuts.end))

    def add_text_clip(self, text, length):
        # TODO: move to transaction
        source = TextSource(id=None, text=text).with_unique_id()
        self.sources = self.sources.add(source)
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
        producer = self.split_into_sections().to_mlt_producer(
            profile=self.profile,
            cache=self.mlt_producer_cache
        )
        self.mlt_producer_cache.swap()
        return producer

class MltProducerCache:

    def __init__(self):
        self.previous = {}
        self.next = {}

    def swap(self):
        self.previous = self.next
        self.next = {}

    def get_or_create(self, key, fn):
        if key in self.previous:
            self.next[key] = self.previous[key]
        elif key not in self.next:
            self.next[key] = fn()
        return self.next[key]

class Transaction:

    def __init__(self, project):
        self.project = project
        self.initial_cuts = project.cuts

    def rollback(self):
        self.project.cuts = self.initial_cuts

    def modify(self, cut_to_modify, fn):
        self.project.cuts = self.project.cuts.modify(cut_to_modify, fn)
