from collections import namedtuple

class Timeline:

    """
    A single clip returns a single group with that clip:

    >>> timeline = Timeline()
    >>> timeline.add(
    ...     0,
    ...     Source(name="A").create_cut(0, 10)
    ... )
    >>> timeline.flatten().render_ascii().render()
    |A0------->|

    Two non-overlapping clips returns two groups with each clip in each:

    >>> timeline = Timeline()
    >>> timeline.add(
    ...     0,
    ...     Source(name="A").create_cut(0, 10)
    ... )
    >>> timeline.add(
    ...     10,
    ...     Source(name="B").create_cut(0, 10)
    ... )
    >>> timeline.flatten().render_ascii().render()
    |A0------->|B0------->|

    Overlap:

    >>> timeline = Timeline()
    >>> timeline.add(
    ...     0,
    ...     Source(name="A").create_cut(0, 10)
    ... )
    >>> timeline.add(
    ...     5,
    ...     Source(name="B").create_cut(0, 10)
    ... )
    >>> timeline.flatten().render_ascii().render()
    |A0-->|A5-->|B5-->|
    |     |B0-->|     |
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

    def render_ascii(self):
        """
        >>> Source("A").create_cut(0, 4).render_ascii().render()
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

    def render_ascii(self):
        """
        >>> Cuts([
        ...     Source("A").create_cut(0, 10),
        ...     Source("b").create_cut(0, 10).at(5),
        ... ]).flatten().render_ascii().render()
        |A0-->|A5-->|b5-->|
        |     |b0-->|     |
        """
        canvas = AsciiCanvas()
        offset = 1
        lines = [0]
        for section in self.sections:
            canvas.add_canvas(section.render_ascii(), dx=offset)
            lines.append(canvas.get_max_x()+1)
            offset += 1
        for line in lines:
            for y in range(canvas.get_max_y()+1):
                canvas.add_text("|", line, y)
        return canvas

class Section:

    def __init__(self, clips):
        self.clips = clips

    def render_ascii(self):
        canvas = AsciiCanvas()
        for y, clip in enumerate(self.clips):
            canvas.add_canvas(clip.render_ascii(), dy=y)
        return canvas

class Regions:

    def __init__(self):
        self.regions = []

    def add(self, region):
        self.regions.append(region)

    def merge(self):
        rest = sorted(self.regions, key=lambda x: x.start)
        merged = []
        while rest:
            x = rest.pop(0)
            if merged:
                merge = merged[-1].merge(x)
                if merge:
                    merged.pop(-1)
                    merged.append(merge)
                else:
                    merged.append(x)
            else:
                merged.append(x)
        return merged

class Region(namedtuple("Region", "start,end")):

    def __init__(self, start, end):
        """
        >>> Region(start=0, end=0)
        Traceback (most recent call last):
          ...
        ValueError: Invalid region: start (0) >= end (0).
        """
        if start >= end:
            raise ValueError(f"Invalid region: start ({start}) >= end ({end}).")

    @property
    def length(self):
        return self.end - self.start

    def merge(self, region):
        """
        >>> Region(start=0, end=5).merge(Region(start=6, end=7)) is None
        True

        >>> Region(start=2, end=3).merge(Region(start=0, end=1)) is None
        True

        >>> Region(start=2, end=3).merge(Region(start=3, end=4))
        Region(start=2, end=4)
        """
        if region.end < self.end or region.start > self.end:
            return None
        else:
            return Region(
                start=min(self.start, region.start),
                end=max(self.end, region.end),
            )

    def get_overlap(self, region):
        """
        xxxx
            yyyy

        >>> Region(0, 4).get_overlap(Region(4, 8)) is None
        True

        xxxx
          yyyy

        >>> Region(0, 4).get_overlap(Region(2, 6))
        Region(start=2, end=4)

          xxxx
        yyyy

        >>> Region(2, 6).get_overlap(Region(0, 4))
        Region(start=2, end=4)
        """
        if region.end <= self.start or region.start >= self.end:
            return None
        else:
            return Region(
                start=max(self.start, region.start),
                end=min(self.end, region.end)
            )

class AsciiCanvas:

    def __init__(self):
        self.chars = {}

    def get_max_x(self):
        return max(x for (x, y) in self.chars.keys())

    def get_max_y(self):
        return max(y for (x, y) in self.chars.keys())

    def add_text(self, text, x, y):
        for index, char in enumerate(text):
            self.chars[(x+index, y)] = char

    def add_canvas(self, canvas, dx=0, dy=0):
        for (x, y), value in canvas.chars.items():
            self.chars[(x+dx, y+dy)] = value

    def render(self):
        if self.chars:
            max_y = max(y for (x, y) in self.chars.keys())
            for y in range(max_y+1):
                chars_for_y = {}
                for (x2, y2), char in self.chars.items():
                    if y2 == y:
                        chars_for_y[x2] = char
                if chars_for_y:
                    max_x = max(x for x in chars_for_y.keys())
                    print("".join([
                        chars_for_y.get(x, " ")
                        for x in range(max_x+1)
                    ]))
                else:
                    print()
