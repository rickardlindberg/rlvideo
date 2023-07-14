from rlvideolib.domain.cut import Cuts

class Project:

    @staticmethod
    def new():
        """
        >>> isinstance(Project.new(), Project)
        True
        """
        return Project()

    def __init__(self):
        self.cuts = Cuts.empty()
