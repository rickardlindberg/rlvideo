import os

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
        self.cuts = Cuts.empty()
