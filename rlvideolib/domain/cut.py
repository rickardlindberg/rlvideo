from collections import namedtuple

from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.domain.region import Region
from rlvideolib.domain.region import UnionRegions
from rlvideolib.domain.section import MixSection
from rlvideolib.domain.section import PlaylistSection
from rlvideolib.domain.section import Sections
from rlvideolib.graphics.rectangle import Rectangle

class Cut(namedtuple("Cut", "source,in_out,position")):

    @staticmethod
    def test_instance(name="A", start=0, end=5, position=0):
        from rlvideolib.domain.source import Source
        return Cut(
            source=Source(name=name),
            in_out=Region(start=start, end=end),
            position=position
        )

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
        >>> Cut.test_instance(position=5).move(-10).position
        0
        """
        return self._replace(position=max(0, self.position+delta))

    @property
    def region(self):
        """
        >>> Cut.test_instance(start=10, end=20, position=10).region
        Region(start=10, end=20)
        """
        return Region(start=self.position, end=self.position+self.length)

    def get_overlap(self, cut):
        """
        >>> a = Cut.test_instance(start=10, end=20, position=5)
        >>> b = Cut.test_instance(start=10, end=20, position=10)
        >>> a.get_overlap(b)
        Region(start=10, end=15)
        """
        return self.region.get_overlap(cut.region)

    def starts_at_original_cut(self):
        """
        >>> cut = Cut.test_instance(start=0, end=10, position=0)
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
        >>> cut = Cut.test_instance(start=0, end=10, position=0)
        >>> cut.ends_at_original_cut()
        True
        >>> cut.create_cut(Region(start=5, end=6)).ends_at_original_cut()
        False
        """
        return self.source.ends_at(self.end)

    def ends_at(self, position):
        return self.end == position

    def get_label(self):
        return self.source.get_label()

    def get_source_cut(self):
        if isinstance(self.source, Cut):
            return self.source.get_source_cut()
        else:
            return self

    def create_cut(self, region):
        """
        >>> cut = Cut.test_instance(name="A", start=0, end=20, position=10)
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

    def to_ascii_canvas(self):
        """
        >>> cut = Cut.test_instance(name="A", start=0, end=10, position=0)

        >>> cut.to_ascii_canvas()
        <-A0----->

        >>> cut.create_cut(Region(start=1, end=9)).to_ascii_canvas()
        -A1-----

        >>> Cut.test_instance(name="A", start=0, end=6, position=0).to_ascii_canvas()
        <-A0->

        >>> Cut.test_instance(name="A", start=0, end=5, position=0).to_ascii_canvas()
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

    def add_to_mlt_playlist(self, profile, playlist):
        playlist.append(self.to_mlt_producer(profile))

    def to_mlt_producer(self, profile):
        return self.source.to_mlt_producer(profile).cut(
            self.in_out.start,
            self.in_out.end-1
        )

    def draw_cairo(self, context, height, one_length_in_pixels, rectangle_map):
        y = 0
        x = 0
        w = self.length * one_length_in_pixels
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

class SpaceCut(namedtuple("SpaceCut", "length")):

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        canvas.add_text("%"*self.length, 0, 0)
        return canvas

    def add_to_mlt_playlist(self, profile, playlist):
        playlist.blank(self.length-1)

    def draw_cairo(self, context, height, one_length_in_pixels, rectangle_map):
        pass

class Cuts:

    """
    >>> a = Cut.test_instance(name="A", start=0, end=20, position=0)
    >>> b = Cut.test_instance(name="b", start=0, end=20, position=10)
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
        ...     Cut.test_instance(name="A", start=0, end=8, position=0),
        ...     Cut.test_instance(name="B", start=0, end=8, position=5),
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
        ...     Cut.test_instance(name="A", start=0, end=10, position=0)
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0----->|

        Two non-overlapping cuts returns two sections with each cut in each:

        >>> Cuts([
        ...     Cut.test_instance(name="A", start=0, end=10, position=0),
        ...     Cut.test_instance(name="B", start=0, end=10, position=10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0-----><-B0----->|

        Overlap:

        >>> Cuts([
        ...     Cut.test_instance(name="A", start=0, end=20, position=0),
        ...     Cut.test_instance(name="B", start=0, end=20, position=10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0------|-A10----->|-B10----->|
        |          |<-B0------|          |

        No cuts:

        >>> Cuts().split_into_sections().to_ascii_canvas()
        <BLANKLINE>

        Initial space:

        >>> Cuts([
        ...     Cut.test_instance(name="A", start=0, end=10, position=5)
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%<-A0----->|

        BUG:

        >>> Cuts([
        ...     Cut.test_instance(name="A", start=0, end=10, position=5),
        ...     Cut.test_instance(name="B", start=0, end=10, position=5),
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%|<-A0----->|
        |     |<-B0----->|

        BUG:

        >>> cuts = Cuts([
        ...     Cut.test_instance(name="A", start=0, end=20, position=30),
        ...     Cut.test_instance(name="B", start=0, end=20, position=0),
        ...     Cut.test_instance(name="C", start=0, end=20, position=10),
        ... ])
        >>> cuts.split_into_sections().to_ascii_canvas()
        |<-B0------|-B10----->|-C10-----><-A0--------------->|
        |          |<-C0------|                              |
        """
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
        ...     Cut.test_instance(name="A", start=0, end=8, position=1),
        ...     Cut.test_instance(name="B", start=0, end=8, position=10),
        ... ])
        >>> cuts.to_ascii_canvas()
        | <-A0--->         |
        |          <-B0--->|
        >>> cuts.extract_playlist_section(Region(start=0, end=20)).to_ascii_canvas()
        %<-A0--->%<-B0--->%%
        """
        # TODO: test value errors
        parts = []
        start = region.start
        for cut in sorted(self.create_cut(region).cuts, key=lambda cut: cut.start):
            if cut.start > start:
                parts.append(SpaceCut(cut.start-start))
            elif cut.start < start:
                raise ValueError("Cut overlaps start")
            parts.append(cut)
            start = cut.end
        if region.end > start:
            parts.append(SpaceCut(region.end-start))
        elif region.end < start:
            raise ValueError("Cut overlaps end")
        return PlaylistSection(length=region.length, parts=parts)

    def extract_mix_section(self, region):
        """
        >>> cuts = Cuts([
        ...     Cut.test_instance(name="A", start=0, end=8, position=1),
        ...     Cut.test_instance(name="B", start=0, end=8, position=5),
        ... ])
        >>> cuts.to_ascii_canvas()
        | <-A0--->    |
        |     <-B0--->|
        >>> cuts.extract_mix_section(Region(start=0, end=15)).to_ascii_canvas()
        %<-A0--->%%%%%%
        %%%%%<-B0--->%%
        """
        playlists = []
        for cut in self.create_cut(region).cuts:
            playlists.append(Cuts([cut]).extract_playlist_section(region))
        return MixSection(length=region.length, playlists=playlists)

    def get_regions_with_overlap(self):
        overlaps = UnionRegions()
        cuts = list(self.cuts)
        while cuts:
            cut = cuts.pop(0)
            for other in cuts:
                overlap = cut.get_overlap(other)
                if overlap:
                    overlaps.add(overlap)
        return overlaps

    @property
    def end(self):
        """
        >>> Cuts().end
        0

        >>> Cuts([Cut.test_instance(start=0, end=5, position=5)]).end
        10
        """
        if self.cuts:
            return max(cut.end for cut in self.cuts)
        else:
            return 0

    def to_ascii_canvas(self):
        """
        >>> Cuts([
        ...     Cut.test_instance(name="A", start=0, end=8, position=10),
        ...     Cut.test_instance(name="B", start=0, end=8, position=0),
        ...     Cut.test_instance(name="C", start=0, end=8, position=5),
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
