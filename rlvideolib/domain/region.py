from collections import namedtuple

class Region(namedtuple("Region", "start,end")):

    def __init__(self, start, end):
        """
        >>> Region(start=1, end=0)
        Traceback (most recent call last):
          ...
        ValueError: Invalid region: start (1) > end (0).
        """
        if start > end:
            raise ValueError(f"Invalid region: start ({start}) > end ({end}).")

    @property
    def length(self):
        return self.end - self.start

    def merge(self, region):
        """
        No adjacent regions:

        >>> a = Region(start=0, end=5)
        >>> b = Region(start=6, end=7)
        >>> a.merge(b) is None
        True

        >>> a = Region(start=2, end=3)
        >>> b = Region(start=0, end=1)
        >>> a.merge(b) is None
        True

        Adjacent regions:

        >>> a = Region(start=2, end=3)
        >>> b = Region(start=3, end=4)
        >>> a.merge(b)
        Region(start=2, end=4)

        Overlapping regions:

        >>> a = Region(start=0, end=2)
        >>> b = Region(start=1, end=3)
        >>> a.merge(b)
        Region(start=0, end=3)
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
