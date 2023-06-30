from collections import namedtuple

class Timeline:

    """
    A single clip returns a single group with that clip:

    >>> timeline = Timeline()
    >>> timeline.add(
    ...     0,
    ...     Source(name="A").create_clip(0, 10)
    ... )
    >>> timeline.get_groups().print_test_repr()
    Group
      Clip(source=Source(name='A'), in_out=Region(start=0, end=10), position=0)

    Two non-overlapping clips returns two groups with each clip in each:

    >>> timeline = Timeline()
    >>> timeline.add(
    ...     0,
    ...     Source(name="A").create_clip(0, 10)
    ... )
    >>> timeline.add(
    ...     10,
    ...     Source(name="B").create_clip(0, 10)
    ... )
    >>> timeline.get_groups().print_test_repr()
    Group
      Clip(source=Source(name='A'), in_out=Region(start=0, end=10), position=0)
    Group
      Clip(source=Source(name='B'), in_out=Region(start=0, end=10), position=10)

    Overlap:

    >>> timeline = Timeline()                   # 01234|56789|.....
    >>> timeline.add(
    ...     0,
    ...     Source(name="A").create_clip(0, 10) # xxxxx|xxxxx|
    ... )
    >>> timeline.add(
    ...     5,
    ...     Source(name="B").create_clip(0, 10) #      |xxxxx|xxxxx
    ... )
    >>> timeline.get_groups().print_test_repr()
    Group
      Clip(source=Source(name='A'), in_out=Region(start=0, end=5), position=0)
    Group
      Clip(source=Source(name='A'), in_out=Region(start=5, end=10), position=5)
      Clip(source=Source(name='B'), in_out=Region(start=0, end=5), position=5)
    Group
      Clip(source=Source(name='B'), in_out=Region(start=5, end=10), position=10)
    """

    def __init__(self):
        self.clips = []

    def add(self, position, clip):
        self.clips.append(clip.at(position))

    def get_groups(self):
        overlaps = Regions()
        clips = list(self.clips)
        while clips:
            clip = clips.pop(0)
            for other in clips:
                overlap = clip.get_overlap(other)
                if overlap:
                    overlaps.append(overlap)
        start = 0
        groups = Groups()
        for overlap in overlaps.merge():
            groups.extend(self.get_single_groups(Region(start=start, end=overlap.start)))
            groups.append(self.extract_region(overlap))
            start = overlap.end
        groups.extend(self.get_single_groups(Region(start=start, end=self.last)))
        return groups

    def get_single_groups(self, region):
        groups = []
        for clip in self.extract_region(region):
            groups.append([clip])
        return groups

    @property
    def last(self):
        return max(clip.region.end for clip in self.clips)

    def extract_region(self, region):
        clips = []
        for clip in self.clips:
            y = clip.extract_region(region)
            if y:
                clips.append(y)
        return clips

class Regions(list):

    def print_test_repr(self):
        for x in self:
            print(x)

    def merge(self):
        rest = sorted(self, key=lambda x: x.start)
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

class Source(namedtuple("Source", "name")):

    def create_clip(self, start, end):
        return Clip.create(
            source=self,
            in_out=Region(start=start, end=end)
        )

class Clip(namedtuple("Clip", "source,in_out,position")):

    @staticmethod
    def create(source, in_out, position=0):
        return Clip(source=source, in_out=in_out, position=position)

    @property
    def length(self):
        return self.in_out.length

    @property
    def region(self):
        """
        >>> Clip(source=Source("B"), in_out=Region(start=10, end=20), position=10).region
        Region(start=10, end=20)
        """
        return Region(start=self.position, end=self.position+self.length)

    def at(self, position):
        """
        >>> Clip.create(source=Source("A"), in_out=Region(start=0, end=10)).at(10)
        Clip(source=Source(name='A'), in_out=Region(start=0, end=10), position=10)
        """
        return self._replace(position=position)

    def get_overlap(self, clip):
        """
        >>> a = Clip(source=Source("A"), in_out=Region(start=10, end=20), position=5)
        >>> b = Clip(source=Source("B"), in_out=Region(start=10, end=20), position=10)
        >>> a.get_overlap(b)
        Region(start=10, end=15)
        """
        return self.region.get_overlap(clip.region)

    def extract_region(self, region):
        """
        >>> clip = Clip(source=Source("A"), in_out=Region(start=10, end=20), position=2)
        >>> clip.extract_region(Region(start=5, end=10))
        Clip(source=Source(name='A'), in_out=Region(start=13, end=18), position=5)
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

class Groups(list):

    def print_test_repr(self):
        for clips in self:
            print(f"Group")
            for clip in clips:
                print(f"  {clip}")
