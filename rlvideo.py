from collections import namedtuple
from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.domain.region import Region
from rlvideolib.domain.region import Regions

class Timeline:

    """
    >>> timeline = Timeline()
    >>> timeline.add(
    ...     5,
    ...     Source(name="A").create_cut(0, 10)
    ... )
    >>> timeline.flatten().to_ascii_canvas()
    |     A0------->|
    """

    def __init__(self):
        self.cuts = Cuts()

    def add(self, position, clip):
        self.cuts.append(clip.at(position))

    def flatten(self):
        return self.cuts.flatten()

class Source(namedtuple("Source", "name")):

    def create_cut(self, start, end):
        return Cut.create(
            source=self,
            in_out=Region(start=start, end=end)
        )

class Cut(namedtuple("Cut", "source,in_out,position")):

    @staticmethod
    def create(source, in_out, position=0):
        return Cut(source=source, in_out=in_out, position=position)

    @property
    def length(self):
        return self.in_out.length

    @property
    def start(self):
        return self.position

    def to_ascii_canvas(self):
        """
        >>> Source("A").create_cut(0, 4).to_ascii_canvas()
        A0->
        """
        canvas = AsciiCanvas()
        text = self.source.name[0]+str(self.in_out.start)
        text = text+"-"*(self.length-len(text)-1)
        text = text+">"
        assert len(text) == self.length
        canvas.add_text(text, self.start, 0)
        return canvas

    @property
    def region(self):
        """
        >>> Cut(source=Source("B"), in_out=Region(start=10, end=20), position=10).region
        Region(start=10, end=20)
        """
        return Region(start=self.position, end=self.position+self.length)

    def at(self, position):
        """
        >>> Cut.create(source=Source("A"), in_out=Region(start=0, end=10)).at(10)
        Cut(source=Source(name='A'), in_out=Region(start=0, end=10), position=10)
        """
        return self._replace(position=position)

    def get_overlap(self, clip):
        """
        >>> a = Cut(source=Source("A"), in_out=Region(start=10, end=20), position=5)
        >>> b = Cut(source=Source("B"), in_out=Region(start=10, end=20), position=10)
        >>> a.get_overlap(b)
        Region(start=10, end=15)
        """
        return self.region.get_overlap(clip.region)

    def cut_region(self, region):
        """
        >>> clip = Cut(source=Source("A"), in_out=Region(start=10, end=20), position=2)
        >>> clip.cut_region(Region(start=5, end=10))
        Cut(source=Source(name='A'), in_out=Region(start=13, end=18), position=5)
        """
        overlap = self.region.get_overlap(region)
        if overlap:
            new_start = self.in_out.start+overlap.start-self.position
            return self._replace(
                position=overlap.start,
                in_out=Region(
                    start=new_start,
                    end=new_start+overlap.length,
                )
            )
        else:
            return None

class Cuts(list):

    def flatten(self):
        """
        A single clip returns a single group with that clip:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0)
        ... ]).flatten().to_ascii_canvas()
        |A0------->|

        Two non-overlapping clips returns two groups with each clip in each:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0),
        ...     Source(name="B").create_cut(0, 10).at(10),
        ... ]).flatten().to_ascii_canvas()
        |A0------->|B0------->|

        Overlap:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0),
        ...     Source(name="B").create_cut(0, 10).at(5),
        ... ]).flatten().to_ascii_canvas()
        |A0-->|A5-->|B5-->|
        |     |B0-->|     |
        """
        sections = Sections()
        start = self.start
        for overlap in self.get_regions_with_overlap():
            for clip in self.cut_region(Region(start=start, end=overlap.start)):
                sections.add(Cuts([clip]))
            sections.add(self.cut_region(overlap))
            start = overlap.end
        for clip in self.cut_region(Region(start=start, end=self.end)):
            sections.add(Cuts([clip]))
        return sections

    def get_regions_with_overlap(self):
        overlaps = Regions()
        clips = list(self)
        while clips:
            clip = clips.pop(0)
            for other in clips:
                overlap = clip.get_overlap(other)
                if overlap:
                    overlaps.add(overlap)
        return overlaps.merge()

    def cut_region(self, region):
        clips = Cuts()
        for clip in self:
            cut = clip.cut_region(region)
            if cut:
                clips.append(cut)
        return clips

    @property
    def start(self):
        return min(clip.region.start for clip in self)

    @property
    def end(self):
        return max(clip.region.end for clip in self)

class Sections:

    def __init__(self):
        self.sections = []

    def add(self, *clips):
        for c in clips:
            self.sections.append(Section(c))

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        offset = 1
        lines = [0]
        for section in self.sections:
            canvas.add_canvas(section.to_ascii_canvas(), dx=offset)
            lines.append(canvas.get_max_x()+1)
            offset += 1
        for line in lines:
            for y in range(canvas.get_max_y()+1):
                canvas.add_text("|", line, y)
        return canvas

class Section:

    def __init__(self, clips):
        self.clips = clips

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        for y, clip in enumerate(self.clips):
            canvas.add_canvas(clip.to_ascii_canvas(), dy=y)
        return canvas
