from collections import namedtuple

import cairo
import mlt

from rlvideolib.debug import timeit
from rlvideolib.domain.cut import Cut
from rlvideolib.domain.project import Project
from rlvideolib.domain.region import Region
from rlvideolib.events import Event
from rlvideolib.graphics.rectangle import Rectangle
from rlvideolib.gui.framework import Action
from rlvideolib.gui.framework import RectangleMap
from rlvideolib.gui.framework import TestGui

GUI_SPACING = 7

class Timeline:

    """
    >>> _ = mlt.Factory().init()

    >>> project = Project.new()
    >>> with project.new_transaction() as transaction:
    ...     cut_id = transaction.add_text_clip("hello", length=10, id="hello")

    >>> timeline = Timeline(
    ...     project=project,
    ...     player=None,
    ...     rectangle_map=RectangleMap()
    ... )
    >>> width, height = 300, 100
    >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    >>> context = cairo.Context(surface)
    >>> timeline.draw_cairo(
    ...     context=context,
    ...     player=MockPlayer(position=0),
    ...     width=width,
    ...     height=height
    ... )

    >>> timeline.split_into_sections().to_ascii_canvas()
    |<-h0----->|

    >>> timeline.rectangle_map # doctest: +ELLIPSIS
    Rectangle(x=0, y=20, width=10, height=50):
      <rlvideolib.domain.cut.CutAction object at ...>
    Rectangle(x=0, y=0, width=300, height=20):
      <rlvideolib.gui.generic.ScrubAction object at ...>
    Rectangle(x=0, y=77, width=300, height=23):
      <rlvideolib.gui.generic.ScrollbarDragAction object at ...>
    """

    def __init__(self, project, player, rectangle_map):
        self.scrollbar_event = Event()
        self.project = project
        self.player = player
        self.set_scrollbar(Scrollbar(
            content_length=0,
            content_desired_start=0,
            one_length_in_pixels=1,
            ui_size=10,
        ))
        self.rectangle_map = rectangle_map

    def get_cut(self, cut_id):
        return self.project.get_cut(cut_id)

    def set_scrollbar(self, scrollbar):
        self.scrollbar = scrollbar
        self.scrollbar_event.trigger()

    def on_scrollbar(self, fn):
        self.scrollbar_event.listen(fn)
        fn()

    def scroll_up(self, x, y):
        self.set_zoom_factor(self.scrollbar.one_length_in_pixels*1.5)

    def scroll_down(self, x, y):
        self.set_zoom_factor(self.scrollbar.one_length_in_pixels/1.5)

    def set_zoom_factor(self, zoom_factor):
        self.set_scrollbar(self.scrollbar._replace(one_length_in_pixels=zoom_factor))

    def split_into_sections(self):
        return self.project.split_into_sections()

    @timeit("Timeline.draw_cairo")
    def draw_cairo(self, context, player, width, height):
        """
        >>> _ = mlt.Factory().init()
        >>> height = 200
        >>> width, total_height = 700, height*2
        >>> surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, total_height)
        >>> context = cairo.Context(surface)
        >>> project = Project.new()
        >>> with project.new_transaction() as transaction:
        ...     _ = transaction.add_text_clip("hello", length=30)
        ...     x = transaction.add_text_clip("world", length=35)
        ...     _ = transaction.add_text_clip("end", length=20)
        ...     _ = transaction.add_text_clip("end", length=20)
        ...     transaction.modify(x, lambda cut: cut.move(-10))
        >>> timeline = Timeline(
        ...     project=project,
        ...     player=None,
        ...     rectangle_map=RectangleMap()
        ... )
        >>> context.translate(0, 0)
        >>> timeline.set_zoom_factor(5)
        >>> timeline.draw_cairo(
        ...     context=context,
        ...     player=MockPlayer(position=40),
        ...     width=width,
        ...     height=height
        ... )
        >>> context.translate(0, height)
        >>> timeline.set_zoom_factor(10)
        >>> timeline.draw_cairo(
        ...     context=context,
        ...     player=MockPlayer(position=40),
        ...     width=width,
        ...     height=height
        ... )
        >>> surface.write_to_png("timeline.png")
        """
        clip_area, scroll_area = Rectangle.from_size(
            width=width,
            height=height
        ).split_height_from_bottom(
            bottom_height=30,
        )
        border_area, scroll_area = scroll_area.split_height_from_top(GUI_SPACING)
        sections = self.split_into_sections()
        self.scrollbar = self.scrollbar._replace(
            content_length=sections.length,
            ui_size=clip_area.width
        )
        # TODO: only update scrollbar on resize and split_into_sections change event
        with clip_area.cairo_clip_translate(context) as area:
            self.draw_clips(context, area, player, sections)
        with scroll_area.cairo_clip_translate(context) as area:
            self.draw_scrollbar(context, area, player)

    def draw_clips(self, context, area, player, sections):
        ruler_area, clip_area = area.split_height_from_top(top_height=20)

        with ruler_area.cairo_clip_translate(context) as ruler_area:
            self.draw_ruler(context, ruler_area)

        context.set_source_rgba(0.4, 0.9, 0.4, 0.5)
        context.rectangle(clip_area.x, clip_area.y, clip_area.width, clip_area.height)
        context.fill()
        with clip_area.cairo_clip_translate(context) as clip_area:
            with clip_area.move(
                dx=self.scrollbar.content_to_pixels(-self.scrollbar.content_start)
            ).resize(
                width=self.scrollbar.content_to_pixels(max(1, sections.length))
            ).cairo_clip_translate(context) as sections_area:
                for cut, boxes in sections.to_cut_boxes(self.scrollbar.region_shown, sections_area).items():
                    cut.draw_cairo(
                        context=context,
                        rectangles=boxes,
                        rectangle_map=self.rectangle_map,
                        project=self.project,
                        scrollbar=self.scrollbar,
                        player=player
                    )
        context.set_source_rgb(0.1, 0.1, 0.1)
        context.move_to(self.scrollbar.content_to_pixels(player.position()-self.scrollbar.content_start), 0)
        context.line_to(self.scrollbar.content_to_pixels(player.position()-self.scrollbar.content_start), area.height)
        context.stroke()

        x, y, w, h = (
            ruler_area.x,
            ruler_area.y,
            ruler_area.width,
            ruler_area.height,
        )
        self.rectangle_map.add_from_context(
            x,
            y,
            w,
            h,
            context,
            ScrubAction(self.player, self.scrollbar)
        )

    def draw_ruler(self, context, area):
        context.set_source_rgba(0.4, 0.9, 0.9)
        context.rectangle(area.x, area.y, area.width, area.height)
        context.fill()

        step = 5
        while self.scrollbar.content_to_pixels(step) < 50:
            step += 5
        start = self.scrollbar.region_shown.start
        end = self.scrollbar.region_shown.end
        pos = int((start // step) * step)

        while pos <= end:
            x = self.scrollbar.content_to_pixels(pos-self.scrollbar.content_start)

            text = str(pos)
            extents = context.text_extents(text)

            context.move_to(x-extents.width/2, area.height/2-1)
            context.text_path(text)
            context.set_source_rgb(0.1, 0.1, 0.1)
            context.fill()

            context.move_to(x, area.height/2)
            context.line_to(x, area.height)
            context.set_source_rgb(0.1, 0.1, 0.1)
            context.stroke()

            pos += step

        context.set_source_rgb(0.2, 0.2, 0.2)
        area.draw_pixel_perfect_line(context, 1, "bottom")

    def draw_scrollbar(self, context, area, player):
        x_start = self.scrollbar.region_shown.start / self.scrollbar.whole_region.length * area.width
        x_end = self.scrollbar.region_shown.end / self.scrollbar.whole_region.length * area.width
        playhead_x = player.position() / self.scrollbar.whole_region.length * area.width

        x, y, w, h = (
            area.x+x_start,
            area.y,
            x_end-x_start,
            area.height
        )
        self.rectangle_map.add_from_context(
            x,
            y,
            w,
            h,
            context,
            ScrollbarDragAction(self, self.scrollbar)
        )

        context.rectangle(area.x, area.y, area.width, area.height)
        context.set_source_rgba(0.4, 0.9, 0.4, 0.5)
        context.fill()

        scroll_box = Rectangle(x, y, w, h)
        context.rectangle(scroll_box.x, scroll_box.y, scroll_box.width, scroll_box.height)
        context.set_source_rgba(0.4, 0.9, 0.4, 0.5)
        context.fill()

        # Playhead
        context.set_source_rgb(0.1, 0.1, 0.1)
        context.move_to(playhead_x, area.top)
        context.line_to(playhead_x, area.bottom)
        context.stroke()

        context.set_source_rgb(0.1, 0.1, 0.1)
        scroll_box.draw_pixel_perfect_border(context, 2)

class Scrollbar(namedtuple("Scrollbar", "content_length,one_length_in_pixels,ui_size,content_desired_start")):

    # TODO: clean up Scrollbar interface

    """
    >>> zoom_scroll = Scrollbar(
    ...     content_length=10,
    ...     one_length_in_pixels=1,
    ...     ui_size=100,
    ...     content_desired_start=0
    ... )
    >>> zoom_scroll.content_start
    0
    """

    @property
    def content_start(self):
        """
        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=1
        ... ).content_start
        1

        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=-10
        ... ).content_start
        0

        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=100
        ... ).content_start
        90.0
        """
        # TODO: content_start -> x_offset | pixel_offset
        max_start = max(0, self.content_length - self.length_shown)
        if self.content_desired_start < 0:
            return 0
        elif self.content_desired_start > max_start:
            return max_start
        else:
            return self.content_desired_start

    def move_scrollbar(self, pixels):
        """
        >>> Scrollbar(
        ...     content_length=100,
        ...     one_length_in_pixels=1,
        ...     ui_size=10,
        ...     content_desired_start=0
        ... ).move_scrollbar(1).content_desired_start
        10.0
        """
        one_pixel_in_length = self.content_length / self.ui_size
        delta = pixels * one_pixel_in_length
        return self._replace(
            content_desired_start=self.content_start+delta
        )

    @property
    def whole_region(self):
        return Region(
            start=0,
            end=max(self.content_length, self.length_shown)
        )

    @property
    def region_shown(self):
        return Region(
            start=self.content_start,
            end=self.content_start+self.length_shown
        )

    @property
    def length_shown(self):
        return max(1, self.ui_size / self.one_length_in_pixels)

    def content_to_pixels(self, length):
        return length * self.one_length_in_pixels

class ScrollbarDragAction(Action):

    def __init__(self, timeline, scrollbar):
        self.timeline = timeline
        self.scrollbar = scrollbar
        self.mouse_up()

    def left_mouse_down(self, x, y):
        self.x = x

    def mouse_up(self):
        self.x = None

    def mouse_move(self, x, y):
        if self.x is not None:
            self.timeline.set_scrollbar(
                self.scrollbar.move_scrollbar(
                    x - self.x
                )
            )

class ScrubAction(Action):

    """
    I scrub the player when clicked:

    >>> class MockScrollbar:
    ...     content_start = 0
    ...     one_length_in_pixels = 1
    >>> action = ScrubAction(player=MockPlayer(), scrollbar=MockScrollbar())
    >>> action.simulate_click(x=10)
    scrub 10
    """

    def __init__(self, player, scrollbar):
        self.player = player
        self.scrollbar = scrollbar
        self.mouse_up()

    def left_mouse_down(self, x, y):
        self.x = x
        self.scrub(x)

    def mouse_up(self):
        self.x = None

    def mouse_move(self, x, y):
        if self.x is not None:
            self.scrub(x)

    def scrub(self, x):
        self.player.scrub(
            int(round(
                self.scrollbar.content_start
                +
                x/self.scrollbar.one_length_in_pixels
            ))
        )

class MockPlayer:

    def __init__(self, position=0):
        self.position_ = position

    def position(self):
        return self.position_

    def scrub(self, position):
        print(f"scrub {position}")
