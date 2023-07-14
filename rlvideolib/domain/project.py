import os

import mlt

from rlvideolib.debug import timeit
from rlvideolib.domain.cut import Cuts
from rlvideolib.domain.source import Source

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
            project.cuts = project.cuts.add(Source("resources/one-to-five.mp4").create_cut(0, 5).move(offset+0))
            project.cuts = project.cuts.add(Source("resources/one.mp4").create_cut(0, 15).move(offset+5))
            project.cuts = project.cuts.add(Source("resources/two.mp4").create_cut(0, 15).move(offset+20))
            project.cuts = project.cuts.add(Source("resources/three.mp4").create_cut(0, 15).move(offset+35))
        return project

    def __init__(self):
        self.profile = mlt.Profile()
        self.cuts = Cuts.empty()
        self.mlt_producer_cache = MltProducerCache()

    @timeit("Project.split_into_sections")
    def split_into_sections(self):
        return self.cuts.split_into_sections()

    @timeit("Project.get_preview_mlt_producer")
    def get_preview_mlt_producer(self):
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
