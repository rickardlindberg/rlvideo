from collections import namedtuple

from rlvideolib.graphics.rectangle import Rectangle

class MenuItem(namedtuple("MenuItem", "label,action")):
    pass

NO_ACTION = object()

class Action:

    def left_mouse_down(self, x, y):
        return NO_ACTION

    def right_mouse_down(self, gui):
        return NO_ACTION

    def mouse_move(self, x, y, gui):
        return NO_ACTION

    def mouse_up(self):
        return NO_ACTION

    def scroll_up(self, x, y):
        return NO_ACTION

    def scroll_down(self, x, y):
        return NO_ACTION

    def simulate_click(self, x=0, y=0):
        self.left_mouse_down(x=x, y=y)

class RectangleMap:

    def __init__(self):
        self.map = []

    def clear(self):
        self.map.clear()

    def add_from_context(self, x, y, w, h, context, item):
        rect_x, rect_y = context.user_to_device(x, y)
        rect_w, rect_h = context.user_to_device_distance(w, h)
        if int(rect_w) > 0 and int(rect_h) > 0:
            self.add(
                Rectangle(
                    x=int(rect_x),
                    y=int(rect_y),
                    width=int(rect_w),
                    height=int(rect_h)
                ),
                item
            )

    def add(self, rectangle, item):
        self.map.append((rectangle, item))

    def perform(self, x, y, fn):
        """
        >>> class TestAction(Action):
        ...     def left_mouse_down(self, x, y):
        ...         pass
        >>> no_action = Action()
        >>> some_action = TestAction()
        >>> r = RectangleMap()
        >>> r.add(Rectangle(x=0, y=0, width=10, height=10), some_action)
        >>> r.add(Rectangle(x=0, y=0, width=10, height=10), no_action)
        >>> action = r.perform(10, 10, lambda action: action.left_mouse_down(10, 10))
        >>> action is some_action
        True
        """
        for rectangle, item in reversed(self.map):
            if rectangle.contains(x, y):
                if fn(item) is not NO_ACTION:
                    return item
        return Action()

    def __repr__(self):
        return "\n".join(f"{rectangle}:\n  {item}" for rectangle, item in self.map)

class TestGui:

    def __init__(self, click_context_menu=None):
        self.click_context_menu = click_context_menu

    def show_context_menu(self, menu):
        self.last_context_menu = menu
        for item in menu:
            if item.label == self.click_context_menu:
                item.action()
                return

    def print_context_menu_items(self):
        for item in self.last_context_menu:
            print(item.label)
