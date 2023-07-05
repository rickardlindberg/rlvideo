from collections import namedtuple
from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.domain.region import Region
from rlvideolib.domain.region import Regions
from rlvideolib.domain.source import Source
from rlvideolib.graphics.rectangle import Rectangle

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

    @property
    def end(self):
        return self.position+self.length

    def move(self, delta):
        """
        >>> Cut(source=None, in_out=None, position=5).move(-10).position
        0
        """
        return self._replace(position=max(0, self.position+delta))

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

    def get_overlap(self, cut):
        """
        >>> a = Cut(source=Source("A"), in_out=Region(start=10, end=20), position=5)
        >>> b = Cut(source=Source("B"), in_out=Region(start=10, end=20), position=10)
        >>> a.get_overlap(b)
        Region(start=10, end=15)
        """
        return self.region.get_overlap(cut.region)

    def starts_at_original_cut(self):
        """
        >>> cut = Source("A").create_cut(0, 10).at(0)
        >>> cut.starts_at_original_cut()
        True
        >>> cut.create_cut(Region(start=5, end=6)).starts_at_original_cut()
        False
        """
        return self.source.starts_at(self.start)

    def starts_at(self, position):
        return self.start == position

    def ends_at_original_cut(self):
        """
        >>> cut = Source("A").create_cut(0, 10).at(0)
        >>> cut.ends_at_original_cut()
        True
        >>> cut.create_cut(Region(start=5, end=6)).ends_at_original_cut()
        False
        """
        return self.source.ends_at(self.end)

    def ends_at(self, position):
        return self.end == position

    def create_cut(self, region):
        """
        >>> cut = Source("A").create_cut(0, 20).at(10)
        >>> cut
        Cut(source=Source(name='A'), in_out=Region(start=0, end=20), position=10)

        Contains all:

        >>> cut.create_cut(Region(start=0, end=40))
        Cut(source=Source(name='A'), in_out=Region(start=0, end=20), position=10)

        >>> cut.create_cut(Region(start=10, end=30))
        Cut(source=Source(name='A'), in_out=Region(start=0, end=20), position=10)

        Subcut left:

        >>> sub = cut.create_cut(Region(start=15, end=30))
        >>> sub.source is cut
        True
        >>> sub.in_out
        Region(start=5, end=20)
        >>> sub.position
        15

        No overlap:

        >>> cut.create_cut(Region(start=0, end=10)) is None
        True
        """
        overlap = self.region.get_overlap(region)
        if overlap:
            if overlap.start == self.start and overlap.end == self.end:
                return self
            else:
                return self._replace(
                    source=self,
                    in_out=Region(
                        start=overlap.start-self.start,
                        end=overlap.start-self.start+overlap.length
                    ),
                    position=overlap.start
                )
        else:
            return None

    def to_mlt_producer(self, profile):
        return self.source.to_mlt_producer(profile).cut(
            self.in_out.start,
            self.in_out.end-1
        )

    def add_to_mlt_playlist(self, profile, playlist):
        playlist.append(self.to_mlt_producer(profile))

    def to_ascii_canvas(self):
        """
        >>> cut = Source("A").create_cut(0, 10).at(0)

        >>> cut.to_ascii_canvas()
        <-A0----->

        >>> cut.create_cut(Region(start=1, end=9)).to_ascii_canvas()
        -A1-----

        >>> Source("A").create_cut(0, 6).at(0).to_ascii_canvas()
        <-A0->

        >>> Source("A").create_cut(0, 5).at(0).to_ascii_canvas()
        #####
        """
        if self.starts_at_original_cut():
            start_marker = "<-"
        else:
            start_marker = "-"
        if self.ends_at_original_cut():
            end_marker = "->"
        else:
            end_marker = "-"
        text = ""
        text += start_marker
        text += self.get_label()[0]
        text += str(self.in_out.start)
        text += "-"*(self.length-len(text)-len(end_marker))
        text += end_marker
        if len(text) != self.length:
            text = "#"*self.length
        canvas = AsciiCanvas()
        canvas.add_text(text, 0, 0)
        return canvas

    def get_label(self):
        return self.source.get_label()

    def get_source_cut(self):
        if isinstance(self.source, Cut):
            return self.source.get_source_cut()
        else:
            return self

    def draw(self, context, height, x_factor, rectangle_map):
        y = 0
        x = self.start * x_factor
        w = self.length * x_factor
        h = height

        rect_x, rect_y = context.user_to_device(x, y)
        rect_w, rect_h = context.user_to_device_distance(w, h)
        rectangle_map.add(Rectangle(
            x=int(rect_x),
            y=int(rect_y),
            width=int(rect_w),
            height=int(rect_h)
        ), self.get_source_cut())

        context.set_source_rgb(1, 0, 0)
        context.rectangle(x, y, w, h)
        context.fill()

        context.set_source_rgb(0, 0, 0)

        context.move_to(x, y)
        context.line_to(x+w, y)
        context.stroke()

        context.move_to(x, y+height)
        context.line_to(x+w, y+height)
        context.stroke()

        if self.starts_at_original_cut():
            context.set_source_rgb(0, 0, 0)
            context.move_to(x, y)
            context.line_to(x, y+height)
            context.stroke()

        if self.ends_at_original_cut():
            context.set_source_rgb(0, 0, 0)
            context.move_to(x+w, y)
            context.line_to(x+w, y+height)
            context.stroke()

        if self.starts_at_original_cut():
            context.move_to(x+2, y+10)
            context.set_source_rgb(0, 0, 0)
            context.text_path(self.get_label())
            context.fill()

class Cuts:

    """
    >>> a = Source("A").create_cut(0, 20).at(0)
    >>> b = Source("b").create_cut(0, 20).at(10)
    >>> cuts = Cuts()
    >>> cuts = cuts.add(a)
    >>> cuts = cuts.add(b)
    >>> cuts.split_into_sections().to_ascii_canvas()
    |<-A0------|-A10----->|-b10----->|
    |          |<-b0------|          |
    >>> cuts.modify(b, lambda cut: cut.move(1)).split_into_sections().to_ascii_canvas()
    |<-A0-------|-A11---->|-b9------->|
    |           |<-b0-----|           |
    """

    def __init__(self, cuts=[]):
        self.cuts = list(cuts)

    def add(self, cut):
        return Cuts(self.cuts+[cut])

    def modify(self, cut_to_modify, fn):
        return Cuts([
            fn(cut) if cut is cut_to_modify else cut
            for cut in self.cuts
        ])

    def create_cut(self, period):
        """
        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 8).at(0),
        ...     Source(name="B").create_cut(0, 8).at(5),
        ... ])
        >>> cuts.to_ascii_canvas()
        |<-A0--->     |
        |     <-B0--->|
        >>> cuts.create_cut(Region(start=2, end=13)).to_ascii_canvas()
        |  -A2-->     |
        |     <-B0--->|
        """
        cuts = []
        for cut in self.cuts:
            sub_cut = cut.create_cut(period)
            if sub_cut:
                cuts.append(sub_cut)
        return Cuts(cuts)

    def split_into_sections(self):
        """
        A single cut returns a single section with that cut:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0)
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0----->|

        Two non-overlapping cuts returns two sections with each cut in each:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(0),
        ...     Source(name="B").create_cut(0, 10).at(10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0-----><-B0----->|

        Overlap:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 20).at(0),
        ...     Source(name="B").create_cut(0, 20).at(10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0------|-A10----->|-B10----->|
        |          |<-B0------|          |

        No cuts:

        >>> Cuts().split_into_sections().to_ascii_canvas()
        <BLANKLINE>

        Initial space:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(5)
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%<-A0----->|

        BUG:

        >>> Cuts([
        ...     Source(name="A").create_cut(0, 10).at(5),
        ...     Source(name="B").create_cut(0, 10).at(5),
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%|<-A0----->|
        |     |<-B0----->|

        BUG:

        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 20).at(30),
        ...     Source(name="B").create_cut(0, 20).at(0),
        ...     Source(name="C").create_cut(0, 20).at(10),
        ... ])
        >>> cuts.split_into_sections().to_ascii_canvas()
        |<-B0------|-B10----->|-C10-----><-A0--------------->|
        |          |<-C0------|                              |
        """
        # TODO: fix circular import?
        from rlvideo import Sections
        sections = Sections()
        start = 0
        for overlap in self.get_regions_with_overlap():
            if overlap.start > start:
                sections.add(self.extract_playlist_section(Region(
                    start=start,
                    end=overlap.start
                )))
            sections.add(self.extract_mix_section(overlap))
            start = overlap.end
        if self.end > start:
            sections.add(self.extract_playlist_section(Region(
                start=start,
                end=self.end
            )))
        return sections

    def extract_playlist_section(self, region):
        """
        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 8).at(1),
        ...     Source(name="B").create_cut(0, 8).at(10),
        ... ])
        >>> cuts.to_ascii_canvas()
        | <-A0--->         |
        |          <-B0--->|
        >>> cuts.extract_playlist_section(Region(start=0, end=20)).to_ascii_canvas()
        %<-A0--->%<-B0--->%%
        """
        # TODO: fix circular import?
        from rlvideo import PlaylistSection
        return PlaylistSection(region=region, cuts=self.create_cut(region))

    def extract_mix_section(self, region):
        """
        >>> cuts = Cuts([
        ...     Source(name="A").create_cut(0, 8).at(1),
        ...     Source(name="B").create_cut(0, 8).at(5),
        ... ])
        >>> cuts.to_ascii_canvas()
        | <-A0--->    |
        |     <-B0--->|
        >>> cuts.extract_mix_section(Region(start=0, end=15)).to_ascii_canvas()
        %<-A0--->%%%%%%
        %%%%%<-B0--->%%
        """
        # TODO: fix circular import?
        from rlvideo import MixSection
        return MixSection(region=region, cuts=self.create_cut(region))

    def get_regions_with_overlap(self):
        overlaps = Regions()
        cuts = list(self.cuts)
        while cuts:
            cut = cuts.pop(0)
            for other in cuts:
                overlap = cut.get_overlap(other)
                if overlap:
                    overlaps.add(overlap)
        return overlaps.merge()

    @property
    def start(self):
        """
        >>> Cuts().start
        0

        >>> Cuts([Source("A").create_cut(0, 5).at(5)]).start
        5
        """
        if self.cuts:
            return min(cut.start for cut in self.cuts)
        else:
            return 0

    @property
    def end(self):
        """
        >>> Cuts().end
        0

        >>> Cuts([Source("A").create_cut(0, 5).at(5)]).end
        10
        """
        if self.cuts:
            return max(cut.end for cut in self.cuts)
        else:
            return 0

    def to_ascii_canvas(self):
        """
        >>> Cuts([
        ...     Source(name="A").create_cut(0, 8).at(10),
        ...     Source(name="B").create_cut(0, 8).at(0),
        ...     Source(name="C").create_cut(0, 8).at(5),
        ... ]).to_ascii_canvas()
        |          <-A0--->|
        |<-B0--->          |
        |     <-C0--->     |
        """
        canvas = AsciiCanvas()
        for y, cut in enumerate(self.cuts):
            canvas.add_canvas(cut.to_ascii_canvas(), dy=y, dx=cut.start+1)
        x = canvas.get_max_x()+1
        for y in range(len(self.cuts)):
            canvas.add_text("|", 0, y)
            canvas.add_text("|", x, y)
        return canvas

class SpaceCut(namedtuple("SpaceCut", "length")):

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        canvas.add_text("%"*self.length, 0, 0)
        return canvas

    def add_to_mlt_playlist(self, profile, playlist):
        playlist.blank(self.length-1)

    def draw(self, context, height, x_factor, rectangle_map):
        pass
