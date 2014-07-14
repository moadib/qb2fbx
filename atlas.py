from collections import namedtuple


__all__ = ['Atlas']


Rect = namedtuple('Rect', 'x y width height')


class AtlasNode(object):
    def __init__(self, rect):
        self.rect = rect
        self.is_leaf = True
        self.left = None
        self.right = None
        self.data = None
        self.vertical_split = True
        self.coord = 0
        
    def insert(self, w, h, data):
        if not self.is_leaf:
            node = self.left.insert(w, h, data)
            if node is not None:
                return node
            return self.right.insert(w, h, data)
        else:
            if self.data is not None:
                return None
            if w == self.rect.width and h == self.rect.height:
                self.data = data
                return self
            elif w > self.rect.width or h > self.rect.height:
                return None

            dw = self.rect.width - w
            dh = self.rect.height - h

            if dw > dh:
                r1 = Rect(self.rect.x, self.rect.y,
                            w, self.rect.height)
                r2 = Rect(self.rect.x + w, self.rect.y,
                            self.rect.width - w, self.rect.height)
            else:
                r1 = Rect(self.rect.x, self.rect.y,
                            self.rect.width, h)
                r2 = Rect(self.rect.x, self.rect.y + h,
                            self.rect.width, self.rect.height -h)

            self.is_leaf = False
            self.left = AtlasNode(r1)
            self.right = AtlasNode(r2)
            return self.left.insert(w, h, data)


class AtlasIterator(object):
    def __init__(self, node):
        self.nodes = []
        def traverse(node):
            if not node.is_leaf:
                traverse(node.left)
                traverse(node.right)
            elif node.data is not None:
                self.nodes.append((node.rect.x, node.rect.y, node.data))
        traverse(node)
        self.index = -1

    def __iter__(self):
        return self

    def next(self):
        if self.index < len(self.nodes) - 1:
            self.index += 1         
            return self.nodes[self.index]
        else:
            raise StopIteration


class Atlas(object):
    def __init__(self, width, height):
        self.root = AtlasNode(Rect(0, 0, width, height))

    def append(self, width, height, data):
        return self.root.insert(width, height, data) is not None

    def __iter__(self):
        return AtlasIterator(self.root)