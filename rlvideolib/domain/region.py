from collections import namedtuple

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

    def get_groups(self, group_size):
        """
        >>> Region(start=0, end=1).get_groups(1)
        {0}

        >>> Region(start=0, end=5).get_groups(1)
        {0, 1, 2, 3, 4}

        >>> Region(start=0, end=6).get_groups(2)
        {0, 1, 2}

        >>> Region(start=0, end=7).get_groups(2)
        {0, 1, 2, 3}
        """
        return set(range(self.start//group_size, ((self.end-1)//group_size)+1))

    def union(self, region):
        """
        No adjacent regions:

        >>> a = Region(start=0, end=5)
        >>> b = Region(start=6, end=7)
        >>> a.union(b)
        [Region(start=0, end=5), Region(start=6, end=7)]

        >>> a = Region(start=2, end=3)
        >>> b = Region(start=0, end=1)
        >>> a.union(b)
        [Region(start=2, end=3), Region(start=0, end=1)]

        Adjacent regions:

        >>> a = Region(start=2, end=3)
        >>> b = Region(start=3, end=4)
        >>> a.union(b)
        [Region(start=2, end=4)]

        Overlapping regions:

        >>> a = Region(start=0, end=2)
        >>> b = Region(start=1, end=3)
        >>> a.union(b)
        [Region(start=0, end=3)]

        Containing regions:

        >>> a = Region(start=0, end=10)
        >>> b = Region(start=2, end=3)
        >>> a.union(b)
        [Region(start=0, end=10)]
        """
        if region.end < self.start or region.start > self.end:
            return [self, region]
        else:
            return [Region(
                start=min(self.start, region.start),
                end=max(self.end, region.end),
            )]

    def get_overlap(self, region):
        """
        No overlapping regions:

        >>> a = Region(0, 4)
        >>> b = Region(4, 8)
        >>> a.get_overlap(b) is None
        True

        Overlapping regions:

        >>> a = Region(0, 4)
        >>> b = Region(2, 6)
        >>> a.get_overlap(b)
        Region(start=2, end=4)

        >>> a = Region(2, 6)
        >>> b = Region(0, 4)
        >>> a.get_overlap(b)
        Region(start=2, end=4)
        """
        if region.end <= self.start or region.start >= self.end:
            return None
        else:
            return Region(
                start=max(self.start, region.start),
                end=min(self.end, region.end)
            )

class UnionRegions:

    def __init__(self):
        self.regions = []

    def add(self, region):
        self.regions.append(region)

    def __iter__(self):
        """
        >>> r = UnionRegions()
        >>> r.add(Region(start=0, end=100))
        >>> r.add(Region(start=5, end=10))
        >>> list(r)
        [Region(start=0, end=100)]
        """
        merged = []
        rest = sorted(self.regions, key=lambda region: region.start)
        while rest:
            region = rest.pop(0)
            if merged:
                merged.extend(merged.pop(-1).union(region))
            else:
                merged.append(region)
        return iter(merged)
