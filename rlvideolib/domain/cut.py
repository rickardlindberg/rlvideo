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
from rlvideolib.gui.framework import Action
from rlvideolib.gui.framework import MenuItem
from rlvideolib.gui.framework import TestGui
from rlvideolib.mlthelpers import MltInconsistencyError
from rlvideolib.mlthelpers import TimewarpProducer

DEFAULT_REGION_GROUP_SIZE = 100

class Cut(namedtuple("Cut", "source,in_out,position,id,mix_strategy,volume,speed")):

    @staticmethod
    def test_instance(name="A", start=0, end=5, position=0, id=None, mix_strategy="under", speed=1):
        return Cut(
            source=CutSource(source_id=name),
            in_out=Region(start=start, end=end),
            position=position,
            id=id,
            mix_strategy=mix_strategy,
            volume=0,
            speed=speed
        )

    @staticmethod
    def new(source, in_out, position=0, id=None, mix_strategy="under", volume=0, speed=1):
        return Cut(
            source=source,
            in_out=in_out,
            position=position,
            id=id,
            mix_strategy=mix_strategy,
            volume=volume,
            speed=speed
        )

    @staticmethod
    def from_json(id, json):
        return Cut(
            source=CutSource(source_id=json["source"]),
            in_out=Region.from_json(json["in_out"]),
            position=json["position"],
            id=id,
            mix_strategy=json["mix_strategy"],
            volume=json.get("volume", 0),
            speed=json.get("speed", 1),
        )

    def to_json(self):
        assert isinstance(self.source, CutSource)
        return {
            "source": self.source.source_id,
            "in_out": self.in_out.to_json(),
            "position": self.position,
            "mix_strategy": self.mix_strategy,
            "volume": self.volume,
            "speed": self.speed,
        }

    def with_mix_strategy(self, mix_strategy):
        return self._replace(mix_strategy=mix_strategy)

    def move_left(self, amount):
        """
        >>> cut = Cut.test_instance(start=5, end=10, position=5).move_left(-5)
        >>> cut.in_out, cut.position
        (Region(start=0, end=10), 0)

        >>> cut = Cut.test_instance(start=5, end=10, position=5).move_left(-6)
        >>> cut.in_out, cut.position
        (Region(start=0, end=10), 0)

        >>> cut = Cut.test_instance(start=9, end=10, position=1).move_left(-6)
        >>> cut.in_out, cut.position
        (Region(start=8, end=10), 0)

        >>> cut = Cut.test_instance(start=8, end=10, position=1).move_left(1)
        >>> cut.in_out, cut.position
        (Region(start=9, end=10), 2)

        >>> cut = Cut.test_instance(start=8, end=10, position=1).move_left(2)
        >>> cut.in_out, cut.position
        (Region(start=9, end=10), 2)
        """
        amount = max(amount, -self.in_out.start)
        amount = max(amount, -self.position)
        amount = min(amount, self.length-1)
        return self._replace(
            in_out=self.in_out._replace(start=self.in_out.start+amount),
            position=self.position+amount
        )

    def move_right(self, amount):
        print("TODO: implement move_right!")
        return self

    def resize_left(self, amount):
        print("TODO: implement resize_left!")
        return self

    def resize_right(self, amount):
        """
        >>> cut = Cut.test_instance(start=5, end=10, position=5)
        >>> cut.in_out, cut.position, cut.speed
        (Region(start=5, end=10), 5, 1)

        >>> cut = cut.resize_right(5)
        >>> cut.in_out, cut.position, cut.speed
        (Region(start=10, end=20), 5, 0.5)

        >>> cut = cut.resize_right(-5)
        >>> cut.in_out, cut.position, cut.speed
        (Region(start=5, end=10), 5, 1.0)
        """
        # TODO: check amount > start
        speed_change = self.in_out.length / self.in_out.move_end(amount).length
        return self._replace(
            in_out=self.in_out.scale(1/speed_change),
            speed=self.speed*speed_change
        )

    def with_volume(self, volume):
        return self._replace(volume=volume)

    def split(self, position):
        delta = position - self.start
        return [
            self._replace(
                in_out=self.in_out.resize_to(delta),
            ).with_unique_id(),
            self._replace(
                in_out=self.in_out.shorten_left(delta),
                position=self.position+delta,
            ).with_unique_id(),
        ]

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
        Cut(source=CutSource(source_id='A'), in_out=Region(start=0, end=20), position=10, id=None, mix_strategy='under', volume=0, speed=1)

        Contains all:

        >>> cut.create_cut(Region(start=0, end=40))
        Cut(source=CutSource(source_id='A'), in_out=Region(start=0, end=20), position=10, id=None, mix_strategy='under', volume=0, speed=1)

        >>> cut.create_cut(Region(start=10, end=30))
        Cut(source=CutSource(source_id='A'), in_out=Region(start=0, end=20), position=10, id=None, mix_strategy='under', volume=0, speed=1)

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

        Error case:

        >>> cut = Cut.test_instance(name="A", start=10, end=20, position=5)
        >>> cut.in_out
        Region(start=10, end=20)
        >>> cut.position
        5
        >>> subcut = cut.create_cut(Region(start=10, end=13))
        >>> subcut.in_out
        Region(start=15, end=18)
        >>> subcut.position
        10
        """
        overlap = self.region.get_overlap(region)
        if overlap:
            if overlap.start == self.start and overlap.end == self.end:
                return self
            else:
                return self._replace(
                    source=self,
                    in_out=Region(
                        start=self.in_out.start+overlap.start-self.start,
                        end=self.in_out.end-self.end+overlap.end
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

    def to_mlt_producer(self, profile, cache, speed=None):
        # TODO: is this `cut` really working? It seems not for cuts of cuts in
        # mixed sections.
        producer = self.source.to_mlt_producer(profile, cache, self.speed).cut(
            self.in_out.start,
            self.in_out.end-1
        )
        if self.volume != 0:
            volume_filter = mlt.Filter(profile, "volume")
            volume_filter.set("level", f"0={self.volume}")
            producer.attach(volume_filter)
        return producer

    def collect_cut_boxes(self, region, boxes, rectangle, pos):
        if self.get_source_cut() in boxes:
            if boxes[self.get_source_cut()][-1].right != rectangle.left:
                raise ValueError("Cut boxes can not have gaps.")
        else:
            boxes[self.get_source_cut()] = []
        boxes[self.get_source_cut()].append(rectangle)

    def draw_cairo(self, context, rectangles, rectangle_map, project, scrollbar, player):
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
            rectangle_map.add_from_context(
                rectangle.x,
                rectangle.y,
                rectangle.width,
                rectangle.height,
                context,
                CutAction(
                    project=project,
                    cut=self.get_source_cut(),
                    scrollbar=scrollbar,
                    player=player
                )
            )
        HANDLE_WIDTH_IN_PX = 5
        left = rectangles[0].left_side(HANDLE_WIDTH_IN_PX)
        rectangle_map.add_from_context(
            left.x,
            left.y,
            left.width,
            left.height,
            context,
            ResizeLeftAction(
                project=project,
                cut=self.get_source_cut(),
                scrollbar=scrollbar,
                player=player
            )
        )
        right = rectangles[-1].right_side(HANDLE_WIDTH_IN_PX)
        rectangle_map.add_from_context(
            right.x,
            right.y,
            right.width,
            right.height,
            context,
            ResizeRightAction(
                project=project,
                cut=self.get_source_cut(),
                scrollbar=scrollbar,
                player=player
            )
        )

class CutDragActionBase(Action):

    def __init__(self, project, cut, scrollbar, player):
        self.project = project
        self.cut = cut
        self.scrollbar = scrollbar
        self.player = player
        self.transaction = None

    def left_mouse_down(self, x, y, ctrl):
        self.transaction = self.project.new_transaction()
        self.x = x
        self.ctrl = ctrl

    def mouse_move(self, x, y, gui):
        self.cursor(gui)
        if self.transaction:
            self.transaction.reset()
            self.drag_operation(
                self.transaction,
                int(round((x-self.x)/self.scrollbar.one_length_in_pixels))
            )

    def drag_operation(self, transaction, delta):
        self.transaction.modify(
            self.cut.id,
            lambda cut: self.modify_cut_on_drag(delta, cut)
        )

    def mouse_up(self):
        if self.transaction:
            self.transaction.commit()
            self.transaction = None

class ResizeLeftAction(CutDragActionBase):

    """
    >>> from rlvideolib.domain.project import Project
    >>> from rlvideolib.gui.generic import Scrollbar
    >>> project = Project.new()
    >>> with project.new_transaction() as transaction:
    ...     hello_id = transaction.add_text_clip("hello", length=10, id="A")
    >>> cut = project.project_data.get_cut(hello_id)
    >>> cut.in_out
    Region(start=0, end=10)
    >>> action = ResizeLeftAction(project=project, cut=cut, scrollbar=Scrollbar.test_instance(), player=None)
    >>> action.simulate_drag(x_start=0, x_end=5)
    >>> project.project_data.get_cut(hello_id).in_out
    Region(start=5, end=10)
    >>> project.current_transaction is None
    True
    """

    def cursor(self, gui):
        gui.set_cursor_resize_left()

    def modify_cut_on_drag(self, delta, cut):
        if self.ctrl:
            return cut.resize_left(delta)
        else:
            return cut.move_left(delta)

class ResizeRightAction(CutDragActionBase):

    def cursor(self, gui):
        gui.set_cursor_resize_right()

    def modify_cut_on_drag(self, delta, cut):
        # TODO: different cursors/tooltips for move/resize. Return different classes from left_mouse_down?
        if self.ctrl:
            return cut.resize_right(delta)
        else:
            return cut.move_right(delta)

class CutAction(CutDragActionBase):

    def modify_cut_on_drag(self, delta, cut):
        """
        >>> from rlvideolib.domain.project import Project
        >>> from rlvideolib.gui.generic import Scrollbar

        I move a cut:

        >>> project = Project.new()
        >>> with project.new_transaction() as transaction:
        ...     hello_id = transaction.add_text_clip("hello", length=10, id="A")
        >>> project.split_into_sections().to_ascii_canvas()
        |<-A0----->|
        >>> action = CutAction(
        ...     project=project,
        ...     cut=project.project_data.get_cut(hello_id),
        ...     scrollbar=Scrollbar.test_instance(),
        ...     player=None,
        ... )
        >>> action.simulate_drag(x_start=0, x_end=5)
        >>> project.split_into_sections().to_ascii_canvas()
        |%%%%%<-A0----->|

        I move all cuts to the right:

        >>> project = Project.new()
        >>> with project.new_transaction() as transaction:
        ...     a_id = transaction.add_text_clip("hello", length=10, id="A")
        ...     b_id = transaction.add_text_clip("hello", length=10, id="B")
        ...     c_id = transaction.add_text_clip("hello", length=10, id="C")
        >>> project.split_into_sections().to_ascii_canvas()
        |<-A0-----><-B0-----><-C0----->|
        >>> action = CutAction(
        ...     project=project,
        ...     cut=project.project_data.get_cut(b_id),
        ...     scrollbar=Scrollbar.test_instance(),
        ...     player=None,
        ... )
        >>> action.simulate_drag(x_start=0, x_end=2, ctrl=True)
        >>> project.split_into_sections().to_ascii_canvas()
        |<-A0----->%%<-B0-----><-C0----->|
        """
        return cut.move(delta)

    def drag_operation(self, transaction, delta):
        if self.ctrl:
            for cut_id in transaction.get_cut_ids(lambda cut: cut.start >= self.cut.start):
                self.transaction.modify(cut_id, lambda cut: cut.move(delta))
        else:
            return CutDragActionBase.drag_operation(self, transaction, delta)

    def cursor(self, gui):
        pass

    def right_mouse_down(self, gui):
        """
        >>> from rlvideolib.domain.project import Project

        I show cut menu items on right click:

        >>> gui = TestGui()
        >>> action = CutAction(project=None, cut=None, scrollbar=None, player=None)
        >>> action.right_mouse_down(gui=gui)
        >>> gui.print_context_menu_items()
        over
        under
        ripple delete
        split at playhead
        volume: -25
        volume: -20
        volume: -15
        volume: -13
        volume: -10
        volume: -8
        volume: -5
        volume: -3
        volume: 0
        volume: 3
        volume: 5
        volume: 8
        volume: 10
        volume: 13
        debug

        I ripple delete:

        >>> project = Project.new()
        >>> with project.new_transaction() as transaction:
        ...     hello_id = transaction.add_text_clip("hello", length=10, id="A")
        ...     _        = transaction.add_text_clip("there", length=10, id="B")
        >>> project.split_into_sections().to_ascii_canvas()
        |<-A0-----><-B0----->|

        >>> CutAction(
        ...     project=project,
        ...     cut=project.project_data.get_cut(hello_id),
        ...     scrollbar=None,
        ...     player=None,
        ... ).right_mouse_down(
        ...     gui=TestGui(click_context_menu="ripple delete")
        ... )
        >>> project.split_into_sections().to_ascii_canvas()
        |<-B0----->|

        I change mix strategy:

        >>> project = Project.new()
        >>> with project.new_transaction() as transaction:
        ...     hello_id = transaction.add_text_clip("hello", length=10, id="A")
        >>> project.project_data.get_cut(hello_id).mix_strategy
        'under'
        >>> CutAction(
        ...     project=project,
        ...     cut=project.project_data.get_cut(hello_id),
        ...     scrollbar=None,
        ...     player=None,
        ... ).right_mouse_down(
        ...     gui=TestGui(click_context_menu="over")
        ... )
        >>> project.project_data.get_cut(hello_id).mix_strategy
        'over'
        """
        def mix_strategy_updater(value):
            def update():
                with self.project.new_transaction() as transaction:
                    transaction.modify(self.cut.id, lambda cut:
                        cut.with_mix_strategy(value))
            return update
        def volume_updater(volume):
            def update():
                with self.project.new_transaction() as transaction:
                    transaction.modify(self.cut.id, lambda cut:
                        cut.with_volume(volume))
            return update
        def ripple_delete():
            self.project.ripple_delete(self.cut.id)
        def split_at_playhead():
            self.project.split(self.cut.id, self.player.position())
        gui.show_context_menu([
            MenuItem(label="over", action=mix_strategy_updater("over")),
            MenuItem(label="under", action=mix_strategy_updater("under")),
            MenuItem(label="ripple delete", action=ripple_delete),
            MenuItem(label="split at playhead", action=split_at_playhead),
        ]+[
            MenuItem(label=f"volume: {volume}", action=volume_updater(volume))
            for volume
            in [
                -25, -20, -15, -13, -10, -8, -5, -3,
                0,
                3, 5, 8, 10, 13
            ]
        ]+[
            MenuItem(label="debug", action=lambda: print(self.cut)),
        ])

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

    # TODO: eliminate nested cuts?

    @staticmethod
    def from_json(json):
        cuts = Cuts.empty()
        for id, json in json.items():
            cuts = cuts.add(Cut.from_json(id, json))
        return cuts

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

    def to_json(self):
        json = {}
        for key, value in self.cut_map.items():
            json[key] = value.to_json()
        return json

    def get(self, id):
        return self.cut_map[id]

    def add(self, *cuts):
        """
        >>> cuts = Cuts.empty()
        >>> list(cuts.cut_map.keys())
        []
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={})

        >>> cuts = cuts.add(Cut.test_instance(id="a"))
        >>> list(cuts.cut_map.keys())
        ['a']
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={0: ['a']})
        """
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

    def remove(self, cut_id):
        """
        >>> cuts = Cuts.empty()
        >>> cuts = cuts.add(Cut.test_instance(id="a"))
        >>> cuts = cuts.add(Cut.test_instance(id="b"))
        >>> list(cuts.cut_map.keys())
        ['a', 'b']
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={0: ['a', 'b']})

        >>> cuts = cuts.remove("b")
        >>> list(cuts.cut_map.keys())
        ['a']
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={0: ['a']})
        """
        old_cut = self.cut_map[cut_id]
        new_cuts = dict(self.cut_map)
        del new_cuts[cut_id]
        return self._replace(
            cut_map=new_cuts,
            region_to_cuts=self.region_to_cuts.remove_cut_from_regions(
                cut_id,
                old_cut.get_region_groups(self.region_group_size)
            ),
        )

    def modify(self, cut_id, fn):
        """
        >>> cuts = Cuts.empty()
        >>> cuts = cuts.add(Cut.test_instance(start=0, end=1, id="a"))
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={0: ['a']})
        >>> cuts = cuts.modify("a", lambda cut: cut.move(DEFAULT_REGION_GROUP_SIZE))
        >>> cuts.region_to_cuts
        RegionToCuts(region_number_to_cut_ids={0: [], 1: ['a']})

        >>> cuts.modify("non-existing-id", lambda cut: cut)
        Traceback (most recent call last):
          ...
        ValueError: cut with id non-existing-id does not exist.
        """
        if cut_id not in self.cut_map:
            raise ValueError(f"cut with id {cut_id} does not exist.")
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

    def ripple_delete(self, cut_id):
        """
        >>> cuts = Cuts.empty()
        >>> cuts = cuts.add(Cut.test_instance(
        ...     name="A", id="a", position=0,
        ...     start=0, end=6,
        ... ))
        >>> cuts = cuts.add(Cut.test_instance(
        ...     name="B", id="b", position=6,
        ...     start=0, end=6,
        ... ))
        >>> cuts = cuts.add(Cut.test_instance(
        ...     name="C", id="c", position=12,
        ...     start=0, end=6,
        ... ))
        >>> cuts.to_ascii_canvas()
        |<-A0->            |
        |      <-B0->      |
        |            <-C0->|
        >>> cuts = cuts.ripple_delete("a")
        >>> cuts.to_ascii_canvas()
        |<-B0->      |
        |      <-C0->|

        >>> cuts = Cuts.empty()
        >>> cuts = cuts.add(Cut.test_instance(
        ...     name="A", id="a", position=0,
        ...     start=0, end=6,
        ... ))
        >>> cuts = cuts.add(Cut.test_instance(
        ...     name="B", id="b", position=3,
        ...     start=0, end=6,
        ... ))
        >>> cuts = cuts.add(Cut.test_instance(
        ...     name="C", id="c", position=6,
        ...     start=0, end=6,
        ... ))
        >>> cuts.to_ascii_canvas()
        |<-A0->      |
        |   <-B0->   |
        |      <-C0->|
        >>> cuts = cuts.ripple_delete("b")
        >>> cuts.to_ascii_canvas()
        |<-A0->   |
        |   <-C0->|
        """
        cut_to_delete = self.get(cut_id)
        cuts = self
        cuts = cuts.remove(cut_id)
        ids = []
        diffs = []
        for cut in cuts.cut_map.values():
            if cut.start > cut_to_delete.start:
                ids.append(cut.id)
                diffs.append(cut.start-cut_to_delete.start)
        delta = -min(diffs)
        for id in ids:
            cuts = cuts.modify(id, lambda cut: cut.move(delta))
        return cuts

    def split(self, cut_id, position):
        """
        >>> cuts = Cuts.empty()
        >>> cuts = cuts.add(Cut.test_instance(
        ...     name="A", id="a", position=10,
        ...     start=0, end=20,
        ... ))
        >>> cuts.to_ascii_canvas()
        |          <-A0--------------->|
        >>> cuts = cuts.split("a", 16)
        >>> cuts.to_ascii_canvas()
        |          <-A0->              |
        |                <-A6--------->|
        """
        cut_to_split = self.get(cut_id)
        cuts = self
        cuts = cuts.remove(cut_to_split.id)
        for new in cut_to_split.split(position):
            cuts = cuts.add(new)
        return cuts

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
        ...     Cut.test_instance(name="A", start=0, end=8, position=0, mix_strategy="over"),
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
            if cut.mix_strategy == "over":
                sorted_cuts.insert(0, cut)
            else:
                assert cut.mix_strategy == "under"
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

    def to_mlt_producer(self, profile, cache, speed):
        return TimewarpProducer(
            producer=cache.get_source_mlt_producer(self.get_source_id()),
            profile=profile,
            speed=speed
        )

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
