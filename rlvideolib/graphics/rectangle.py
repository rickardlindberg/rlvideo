from collections import namedtuple

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

    @staticmethod
    def from_size(width, height):
        """
        >>> Rectangle.from_size(width=10, height=10)
        Rectangle(x=0, y=0, width=10, height=10)
        """
        return Rectangle(x=0, y=0, width=width, height=height)

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
