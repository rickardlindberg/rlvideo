from collections import namedtuple
import itertools
import uuid

import mlt

from rlvideolib.asciicanvas import AsciiCanvas
from rlvideolib.debug import timeit
from rlvideolib.domain.region import Region
from rlvideolib.domain.region import UnionRegions
from rlvideolib.domain.section import MixSection
from rlvideolib.domain.section import PlaylistSection
from rlvideolib.domain.section import Sections
from rlvideolib.graphics.rectangle import Rectangle

DEFAULT_REGION_GROUP_SIZE = 100

class Cut(namedtuple("Cut", "source,in_out,position,id,cut")):

    @staticmethod
    def test_instance(name="A", start=0, end=5, position=0, id=None, cut="under"):
        return Cut(
            source=CutSource(source_id=name),
            in_out=Region(start=start, end=end),
            position=position,
            id=id,
            cut=cut
        )

    def get_region_groups(self, group_size):
        """
        >>> Cut.test_instance(start=0, end=10).get_region_groups(5)
        {0, 1}
        """
        return self.region.get_groups(group_size)

    def with_unique_id(self):
        return self.with_id(uuid.uuid4().hex)

    def with_id(self, id):
        return self._replace(id=id)

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

    def get_source_id(self):
        return self.source.get_source_id()

    def get_source_cut(self):
        if isinstance(self.source, Cut):
            return self.source.get_source_cut()
        else:
            return self

    def create_cut(self, region):
        """
        >>> cut = Cut.test_instance(name="A", start=0, end=20, position=10)
        >>> cut
        Cut(source=CutSource(source_id='A'), in_out=Region(start=0, end=20), position=10, id=None, cut='under')

        Contains all:

        >>> cut.create_cut(Region(start=0, end=40))
        Cut(source=CutSource(source_id='A'), in_out=Region(start=0, end=20), position=10, id=None, cut='under')

        >>> cut.create_cut(Region(start=10, end=30))
        Cut(source=CutSource(source_id='A'), in_out=Region(start=0, end=20), position=10, id=None, cut='under')

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
        text += self.get_source_id()[0]
        text += str(self.in_out.start)
        text += "-"*(self.length-len(text)-len(end_marker))
        text += end_marker
        if len(text) != self.length:
            text = "#"*self.length
        canvas = AsciiCanvas()
        canvas.add_text(text, 0, 0)
        return canvas

    def add_to_mlt_playlist(self, profile, cache, playlist):
        playlist.append(self.to_mlt_producer(profile, cache))

    def to_mlt_producer(self, profile, cache):
        return self.source.to_mlt_producer(profile, cache).cut(
            self.in_out.start,
            self.in_out.end-1
        )

    def collect_cut_boxes(self, region, boxes, rectangle, pos):
        if self.get_source_cut() in boxes:
            if boxes[self.get_source_cut()][-1].right != rectangle.left:
                raise ValueError("Cut boxes can not have gaps.")
        else:
            boxes[self.get_source_cut()] = []
        boxes[self.get_source_cut()].append(rectangle)

    def draw_cairo(self, context, rectangles, rectangle_map, project):
        context.save()
        CutRectangles(rectangles).cairo_fill_path(context)
        context.clip_preserve()
        context.set_source_rgb(0.9, 0.2, 0.2)
        context.fill()
        context.move_to(rectangles[0].x+4, rectangles[0].y+13)
        context.set_source_rgb(0, 0, 0)
        context.text_path(project.get_label(self.get_source_id()))
        context.fill()
        context.restore()
        CutRectangles(rectangles).cairo_stroke_path(context, 2)
        context.set_source_rgba(0.1, 0.1, 0.1)
        context.stroke()
        for rectangle in rectangles:
            rect_x, rect_y = context.user_to_device(rectangle.x, rectangle.y)
            rect_w, rect_h = context.user_to_device_distance(rectangle.width, rectangle.height)
            if int(rect_w) > 0 and int(rect_h) > 0:
                rectangle_map.add(Rectangle(
                    x=int(rect_x),
                    y=int(rect_y),
                    width=int(rect_w),
                    height=int(rect_h)
                ), self.get_source_cut())

class SpaceCut(namedtuple("SpaceCut", "length")):

    def to_ascii_canvas(self):
        canvas = AsciiCanvas()
        canvas.add_text("%"*self.length, 0, 0)
        return canvas

    def add_to_mlt_playlist(self, profile, cache, playlist):
        producer = mlt.Producer(profile, "color:#00000000") # transparent
        playlist.append(producer.cut(0, self.length-1))

    def collect_cut_boxes(self, region, boxes, rectangle, pos):
        pass

    def draw_cairo(self, context, rectangle, rectangle_map, project):
        pass

class Cuts(namedtuple("Cuts", "cut_map,region_to_cuts,region_group_size")):

    """
    >>> a = Cut.test_instance(name="A", start=0, end=20, position=0, id=0)
    >>> b = Cut.test_instance(name="b", start=0, end=20, position=10, id=1)
    >>> cuts = Cuts.empty()
    >>> cuts = cuts.add(a)
    >>> cuts = cuts.add(b)
    >>> cuts.split_into_sections().to_ascii_canvas()
    |<-A0------|-A10----->|-b10----->|
    |          |<-b0------|          |
    >>> cuts.modify(b.id, lambda cut: cut.move(1)).split_into_sections().to_ascii_canvas()
    |<-A0-------|-A11---->|-b9------->|
    |           |<-b0-----|           |

    Cut boxes:

    >>> cut_boxes = cuts.split_into_sections().to_cut_boxes(
    ...     Region(start=0, end=30),
    ...     Rectangle.from_size(200, 50)
    ... )
    >>> for cut, boxes in cut_boxes.items():
    ...    print(f"{cut.source}: {boxes}")
    CutSource(source_id='A'): [Rectangle(x=0, y=0, width=67, height=50), Rectangle(x=67, y=0, width=66, height=25)]
    CutSource(source_id='b'): [Rectangle(x=67, y=25, width=66, height=25), Rectangle(x=133, y=0, width=67, height=50)]

    >>> cut_boxes = cuts.split_into_sections().to_cut_boxes(
    ...     Region(start=10, end=30),
    ...     Rectangle.from_size(200, 50)
    ... )
    >>> for cut, boxes in cut_boxes.items():
    ...    print(f"{cut.source}: {boxes}")
    CutSource(source_id='A'): [Rectangle(x=67, y=0, width=66, height=25)]
    CutSource(source_id='b'): [Rectangle(x=67, y=25, width=66, height=25), Rectangle(x=133, y=0, width=67, height=50)]

    >>> cut_boxes = cuts.split_into_sections().to_cut_boxes(
    ...     Region(start=10, end=20),
    ...     Rectangle.from_size(200, 50)
    ... )
    >>> for cut, boxes in cut_boxes.items():
    ...    print(f"{cut.source}: {boxes}")
    CutSource(source_id='A'): [Rectangle(x=67, y=0, width=66, height=25)]
    CutSource(source_id='b'): [Rectangle(x=67, y=25, width=66, height=25)]
    """

    @staticmethod
    def from_list(cuts):
        return Cuts.empty().add(*[
            cut.with_unique_id()
            for cut in cuts
        ])

    @staticmethod
    def empty():
        return Cuts(
            cut_map={},
            region_to_cuts=RegionToCuts.empty(),
            region_group_size=DEFAULT_REGION_GROUP_SIZE
        )

    def add(self, *cuts):
        new_region_to_cuts = self.region_to_cuts
        new_cuts = dict(self.cut_map)
        for cut in cuts:
            if cut.id in new_cuts:
                raise ValueError(f"Cut with id = {cut.id} already exists.")
            new_region_to_cuts = new_region_to_cuts.add_cut_to_regions(
                cut.id,
                cut.get_region_groups(self.region_group_size)
            )
            new_cuts[cut.id] = cut
        return self._replace(
            cut_map=new_cuts,
            region_to_cuts=new_region_to_cuts,
        )

    def modify(self, cut_id, fn):
        """
        It updates groups correctly:

        >>> cut = Cut.test_instance(start=0, end=1, id=99)
        >>> cuts = Cuts.empty()
        >>> cuts = cuts.add(cut)
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={0: [99]})
        >>> cuts = cuts.modify(cut.id, lambda cut: cut.move(DEFAULT_REGION_GROUP_SIZE))
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={0: [], 1: [99]})
        """
        # TODO: custom exception if not found
        old_cut = self.cut_map[cut_id]
        new_cut = fn(old_cut)
        new_cuts = dict(self.cut_map)
        new_cuts[cut_id] = new_cut
        return self._replace(
            cut_map=new_cuts,
            region_to_cuts=self.region_to_cuts.remove_cut_from_regions(
                old_cut.id,
                old_cut.get_region_groups(self.region_group_size)
            ).add_cut_to_regions(
                new_cut.id,
                new_cut.get_region_groups(self.region_group_size)
            ),
        )

    def yield_cuts_in_period(self, period):
        yielded = set()
        for group in period.get_groups(self.region_group_size):
            for cut_id in self.region_to_cuts.get_cuts_in_region(group):
                if cut_id not in yielded:
                    yield self.cut_map[cut_id]
                    yielded.add(cut_id)

    def create_cut(self, period):
        """
        >>> cuts = Cuts.from_list([
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
        for cut in self.yield_cuts_in_period(period):
            sub_cut = cut.create_cut(period)
            if sub_cut:
                cuts.append(sub_cut)
        return Cuts.empty().add(*cuts)

    def split_into_sections(self):
        """
        A single cut returns a single section with that cut:

        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=10, position=0)
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0----->|

        Two non-overlapping cuts returns two sections with each cut in each:

        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=10, position=0),
        ...     Cut.test_instance(name="B", start=0, end=10, position=10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0-----><-B0----->|

        Overlap:

        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=20, position=0),
        ...     Cut.test_instance(name="B", start=0, end=20, position=10),
        ... ]).split_into_sections().to_ascii_canvas()
        |<-A0------|-A10----->|-B10----->|
        |          |<-B0------|          |

        No cuts:

        >>> Cuts.empty().split_into_sections().to_ascii_canvas()
        <BLANKLINE>

        Initial space:

        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=10, position=5)
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%<-A0----->|

        BUG:

        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=10, position=5),
        ...     Cut.test_instance(name="B", start=0, end=10, position=5),
        ... ]).split_into_sections().to_ascii_canvas()
        |%%%%%|<-A0----->|
        |     |<-B0----->|

        BUG:

        >>> cuts = Cuts.from_list([
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
        >>> cuts = Cuts.from_list([
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
        for cut in sorted(self.create_cut(region).cut_map.values(), key=lambda cut: cut.start):
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
        >>> cuts = Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=8, position=1),
        ...     Cut.test_instance(name="B", start=0, end=8, position=5),
        ... ])
        >>> cuts.to_ascii_canvas()
        | <-A0--->    |
        |     <-B0--->|
        >>> cuts.extract_mix_section(Region(start=0, end=15)).to_ascii_canvas()
        %<-A0--->%%%%%%
        %%%%%<-B0--->%%

        >>> region = Region(start=0, end=15)
        >>> a_cut = Cut.test_instance(name="A", start=0, end=8, position=1)
        >>> b_cut = Cut.test_instance(name="B", start=0, end=8, position=5)

        >>> Cuts.from_list([
        ...     a_cut,
        ...     b_cut,
        ... ]).extract_mix_section(region).to_ascii_canvas()
        %<-A0--->%%%%%%
        %%%%%<-B0--->%%

        >>> Cuts.from_list([
        ...     b_cut,
        ...     a_cut,
        ... ]).extract_mix_section(region).to_ascii_canvas()
        %<-A0--->%%%%%%
        %%%%%<-B0--->%%

        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=8, position=0),
        ...     Cut.test_instance(name="B", start=0, end=7, position=0),
        ... ]).extract_mix_section(Region(start=0, end=10)).to_ascii_canvas()
        <-B0-->%%%
        <-A0--->%%

        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=8, position=0, cut="over"),
        ...     Cut.test_instance(name="B", start=0, end=7, position=0),
        ... ]).extract_mix_section(Region(start=0, end=10)).to_ascii_canvas()
        <-A0--->%%
        <-B0-->%%%
        """
        # TODO: sort based on cut (j-cut, l-cut, overlay, background).
        playlists = []
        for cut in self.sort_cuts(self.create_cut(region).cut_map.values()):
            playlists.append(Cuts.empty().add(cut).extract_playlist_section(region))
        return MixSection(length=region.length, playlists=playlists)

    def sort_cuts(self, cuts):
        sorted_cuts = []
        for cut in sorted(cuts, key=lambda cut: (
            cut.get_source_cut().start,
            cut.get_source_cut().end
        )):
            if cut.cut == "over":
                sorted_cuts.insert(0, cut)
            else:
                assert cut.cut == "under"
                sorted_cuts.append(cut)
        return sorted_cuts

    @timeit("Cuts.get_regions_with_overlap")
    def get_regions_with_overlap(self):
        overlaps = UnionRegions()
        for cut_ids in self.region_to_cuts.iter_groups():
            for (id1, id2) in itertools.combinations(cut_ids, 2):
                overlap = self.cut_map[id1].get_overlap(self.cut_map[id2])
                if overlap:
                    overlaps.add(overlap)
        return overlaps

    @property
    def end(self):
        """
        >>> Cuts.empty().end
        0

        >>> Cuts.from_list([Cut.test_instance(start=0, end=5, position=5)]).end
        10
        """
        if self.cut_map:
            return max(cut.end for cut in self.cut_map.values())
        else:
            return 0

    def to_ascii_canvas(self):
        """
        >>> Cuts.from_list([
        ...     Cut.test_instance(name="A", start=0, end=8, position=10),
        ...     Cut.test_instance(name="B", start=0, end=8, position=0),
        ...     Cut.test_instance(name="C", start=0, end=8, position=5),
        ... ]).to_ascii_canvas()
        |          <-A0--->|
        |<-B0--->          |
        |     <-C0--->     |
        """
        canvas = AsciiCanvas()
        for y, cut in enumerate(self.cut_map.values()):
            canvas.add_canvas(cut.to_ascii_canvas(), dy=y, dx=cut.start+1)
        x = canvas.get_max_x()+1
        for y in range(len(self.cut_map)):
            canvas.add_text("|", 0, y)
            canvas.add_text("|", x, y)
        return canvas

class RegionToCuts(namedtuple("RegionToCuts", "region_number_to_cut_ids")):

    @staticmethod
    def empty():
        """
        >>> RegionToCuts.empty()
        RegionToCuts(region_number_to_cut_ids={})
        """
        return RegionToCuts({})

    def iter_groups(self):
        return iter(self.region_number_to_cut_ids.values())

    def add_cut_to_regions(self, cut_id, group_numbers):
        """
        >>> RegionToCuts.empty().add_cut_to_regions(5, [1, 2, 3])
        RegionToCuts(region_number_to_cut_ids={1: [5], 2: [5], 3: [5]})
        """
        new_region_to_cuts = dict(self.region_number_to_cut_ids)
        for region_number in group_numbers:
            new_ids = new_region_to_cuts.get(region_number, [])
            if cut_id not in new_ids:
                new_ids = new_ids + [cut_id]
            new_region_to_cuts[region_number] = new_ids
        return self._replace(region_number_to_cut_ids=new_region_to_cuts)

    def remove_cut_from_regions(self, cut_id, group_numbers):
        """
        >>> RegionToCuts.empty().add_cut_to_regions(5, [1, 2, 3]).remove_cut_from_regions(5, [1])
        RegionToCuts(region_number_to_cut_ids={1: [], 2: [5], 3: [5]})
        """
        new_region_to_cuts = dict(self.region_number_to_cut_ids)
        for region_number in group_numbers:
            new_ids = list(new_region_to_cuts[region_number])
            new_ids.remove(cut_id)
            new_region_to_cuts[region_number] = new_ids
        return self._replace(region_number_to_cut_ids=new_region_to_cuts)

    def get_cuts_in_region(self, region_number):
        """
        >>> RegionToCuts.empty().get_cuts_in_region(5)
        []

        >>> RegionToCuts.empty().add_cut_to_regions(5, [1]).get_cuts_in_region(1)
        [5]
        """
        return self.region_number_to_cut_ids.get(region_number, [])

class CutSource(namedtuple("CutSource", "source_id")):

    def to_mlt_producer(self, profile, cache):
        return cache.get_source_mlt_producer(self.get_source_id())

    def starts_at(self, position):
        return True

    def ends_at(self, position):
        return True

    def get_source_id(self):
        return self.source_id

class CutRectangles:

    def __init__(self, rectangles):
        self.rectangles = rectangles

    def cairo_fill_path(self, context):
        def curve(endx, endy, x, y):
            context.curve_to(endx, endy, x, y, x, y)
        for index, (x1, y1, x2, y2, endx, endy) in enumerate(self.get_segments(7)):
            if index == 0:
                start = (x1, y1)
                context.move_to(x1, y1)
                context.line_to(x2, y2)
            else:
                curve(last[2], last[3], x1, y1)
                context.line_to(x2, y2)
            last = (x2, y2, endx, endy)
        curve(last[2], last[3], start[0], start[1])

    def cairo_stroke_path(self, context, size):
        # TODO: shrink stroke path so that border is contained within fill path
        self.cairo_fill_path(context)

    def get_segments(self, size):
        # TODO: fix subtle issues with rounded corners
        last = None
        for point in self.get_corner_points():
            if last is not None:
                last_x, last_y = last
                x, y = point
                if last_x == x:
                    y_size = min(size, abs(last_y-y)/2)
                    if y > last_y:
                        yield (x, last_y+y_size, x, y-y_size, x, y)
                    else:
                        yield (x, last_y-y_size, x, y+y_size, x, y)
                else:
                    x_size = min(size, abs(last_x-x)/2)
                    if x > last_x:
                        yield (last_x+x_size, y, x-x_size, y, x, y)
                    else:
                        yield (last_x-x_size, y, x+x_size, y, x, y)
            last = point

    def get_corner_points(self):
        def add(point):
            if point != points[-1]:
                points.append(point)
        start = (self.rectangles[0].left, self.rectangles[0].top)
        points = [start]
        for r in self.rectangles:
            add((r.left, r.bottom))
            add((r.right, r.bottom))
        for r in reversed(self.rectangles):
            add((r.right, r.top))
            add((r.left, r.top))
        return points
