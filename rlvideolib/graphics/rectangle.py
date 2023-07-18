from collections import namedtuple
from contextlib import contextmanager

class Rectangle(namedtuple("Rectangle", "x,y,width,height")):

    def __init__(self, x, y, width, height):
        """
        >>> Rectangle(x=0, y=0, width=0, height=10)
        Traceback (most recent call last):
          ...
        ValueError: Width must be > 0.

        >>> Rectangle(x=0, y=0, width=10, height=0)
        Traceback (most recent call last):
          ...
        ValueError: Height must be > 0.
        """
        if width <= 0:
            raise ValueError("Width must be > 0.")
        if height <= 0:
            raise ValueError("Height must be > 0.")

    @property
    def left(self):
        return self.x

    @property
    def right(self):
        return self.x+self.width

    @property
    def top(self):
        return self.y

    @property
    def bottom(self):
        return self.y+self.height

    @staticmethod
    def from_size(width, height):
        """
        >>> Rectangle.from_size(width=10, height=10)
        Rectangle(x=0, y=0, width=10, height=10)
        """
        return Rectangle(x=0, y=0, width=width, height=height)

    def move(self, dx=0, dy=0):
        return self._replace(x=self.x+dx, y=self.y+dy)

    def resize(self, width):
        return self._replace(width=width)

    def contains(self, x, y):
        # TODO: test this
        if x < self.x:
            return False
        elif x > self.x+self.width:
            return False
        elif y < self.y:
            return False
        elif y > self.y+self.height:
            return False
        else:
            return True

    def deflate(self, amount):
        """
        >>> Rectangle(x=0, y=0, width=10, height=10).deflate(2)
        Rectangle(x=2, y=2, width=6, height=6)
        """
        return self._replace(
            x=self.x+amount,
            y=self.y+amount,
            width=self.width-2*amount,
            height=self.height-2*amount,
        )

    def deflate_height(self, amount):
        """
        >>> Rectangle(x=0, y=0, width=10, height=10).deflate_height(2)
        Rectangle(x=0, y=2, width=10, height=6)
        """
        return self._replace(
            x=self.x,
            y=self.y+amount,
            width=self.width,
            height=self.height-2*amount,
        )

    def split_height_from_bottom(self, bottom_height, space):
        """
        >>> Rectangle(x=0, y=10, width=100, height=100).split_height_from_bottom(10, 5)
        [Rectangle(x=0, y=10, width=100, height=85), Rectangle(x=0, y=100, width=100, height=10)]
        """
        return [
            self._replace(
                height=self.height-bottom_height-space,
            ),
            self._replace(
                y=self.y+self.height-bottom_height,
                height=bottom_height,
            ),
        ]

    def divide_width(self, items, fn):
        offset = 0
        for item, distance in Distance(self.width).divide(items, fn):
            if distance > 0:
                yield item, self._replace(x=self.x+offset, width=distance)
                offset += distance

    def divide_height(self, items, fn):
        offset = 0
        for item, distance in Distance(self.height).divide(items, fn):
            if distance > 0:
                yield item, self._replace(y=self.y+offset, height=distance)
                offset += distance

    @contextmanager
    def cairo_clip_translate(self, context):
        context.save()
        context.rectangle(self.x, self.y, self.width, self.height)
        context.clip()
        context.translate(self.x, self.y)
        yield Rectangle.from_size(width=self.width, height=self.height)
        context.restore()

    def draw_pixel_perfect_border(self, context, size):
        self.draw_pixel_perfect_line(context, size, "left")
        self.draw_pixel_perfect_line(context, size, "right")
        self.draw_pixel_perfect_line(context, size, "top")
        self.draw_pixel_perfect_line(context, size, "bottom")

    def draw_pixel_perfect_line(self, context, size, side):
        if side == "left":
            context.move_to(self.left+size/2, self.top)
            context.line_to(self.left+size/2, self.bottom)
        elif side == "right":
            context.move_to(self.right-size/2, self.top)
            context.line_to(self.right-size/2, self.bottom)
        elif side == "top":
            context.move_to(self.left, self.top+size/2)
            context.line_to(self.right, self.top+size/2)
        elif side == "bottom":
            context.move_to(self.left, self.bottom-size/2)
            context.line_to(self.right, self.bottom-size/2)
        else:
            raise ValueError("Invalid size.")
        context.stroke()

class Distance(namedtuple("Distance", "distance")):

    def divide(self, items, size_fn):
        """
        >>> list(Distance(9).divide("abc", lambda item: 3))
        [('a', 3), ('b', 3), ('c', 3)]

        >>> list(Distance(10).divide("abc", lambda item: 3))
        [('a', 3), ('b', 4), ('c', 3)]
        """
        total_size = sum(size_fn(item) for item in items)
        size_so_far = 0
        start = 0
        for item in items:
            item_pos = int(round((
                (size_so_far+size_fn(item)) / total_size) * self.distance
            ))
            item_distance = item_pos-start
            size_so_far += size_fn(item)
            yield (item, item_distance)
            start += item_distance

class RectangleMap:

    """
    >>> r = RectangleMap()
    >>> r.add(Rectangle(x=0, y=0, width=10, height=10), "item")
    >>> r.get(5, 5)
    'item'
    >>> r.get(100, 100) is None
    True
    """

    def __init__(self):
        self.map = []

    def clear(self):
        self.map.clear()

    def add(self, rectangle, item):
        self.map.append((rectangle, item))

    def get(self, x, y):
        for rectangle, item in self.map:
            if rectangle.contains(x, y):
                return item

    def __repr__(self):
        return "\n".join(f"{rectangle}:\n  {item}" for rectangle, item in self.map)
