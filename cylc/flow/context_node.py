class ContextNode():
    """A class for defining nested objects.

    Attributes:
        name (str):
            The key identifier for this node.
            Nodes belonging to the same parent must have not have the same
            name.

    Examples:
        Define the tree:
        >>> with ContextNode('a') as a:
        ...     # create parent nodes using a context
        ...     # manager
        ...     with ContextNode('b') as b:
        ...         # create "leaf" nodes without
        ...         # a context manager
        ...         c = ContextNode('c')
        ...     d = ContextNode('d')

        The "key" for this node:
        >>> str(c)
        'c'
        >>> repr(c)
        'a/b/c'

        List ancestry:
        >>> list(c.parents())
        [a/b, a]

        Iterate through children:
        >>> list(a)
        [a/b, a/d]

        Summarise the tree:
        >>> print(a.tree())
        a
            b
                c
            d

    Node Terminology:
        Root/
            Parent/
                Leaf
            Leaf

    Class Attributes:
        ROOT_NAME_FMT (str):
            String representation for *root* nodes to be evaluated as a format
            string. Can use any of the instance attributes.
        ROOT_NAME_FMT (str):
            String representation for parent nodes.
        ROOT_NAME_FMT (str):
            String representation for leaf nodes.
        SEP (str):
            String to separate components in a nodes repr().

    """

    __slots__ = ('name', '_parent', '_children')

    ROOT_NAME_FMT = '{name}'
    NODE_NAME_FMT = '{name}'
    LEAF_NAME_FMT = '{name}'
    SEP = '/'

    DATA = {}

    def __init__(self, name):
        self.name = name
        self._parent = None
        self._children = None
        self.DATA[self] = set(self.DATA)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # list the nodes already present on this node
        older_siblings = self._children or {}
        # list the nodes which were created since we
        # __entered__ this node
        new_borns = {
            value.name: value
            for value in self.DATA
            if value is not self
            if value not in self.DATA.get(self, {})
        }
        self._children = {
            **older_siblings,
            **new_borns
        }
        for child in new_borns.values():
            # remove our children from self.DATA
            del self.DATA[child]
            # set our children to see us as their parent
            child._parent = self
        if len(self.DATA) == 1:
            # this is a root node, clean up after ourselves
            # self.DATA *should* be clean after each tree
            del self.DATA[self]

    def __iter__(self):
        if self._children:
            return iter(self._children.values())
        return iter([])

    def __contains__(self, name):
        return name in self._children

    def __getitem__(self, name):
        if self._children:
            return self._children.__getitem__(name)
        raise TypeError('This is not a leaf node')

    def __str__(self):
        if self.is_root():
            fmt = self.ROOT_NAME_FMT
        elif not self.is_leaf():
            fmt = self.NODE_NAME_FMT
        else:
            fmt = self.LEAF_NAME_FMT
        return fmt.format_map({
            key: getattr(self, key)
            for key in self.__slots__
        })

    def __repr__(self):
        return self.SEP.join(
            [
                str(node)
                for node in reversed(list(self.parents()))
            ] + [
                str(self)
            ]
        )

    def is_root(self):
        """Return True if this is a root node.

        Returns:
            bool

        """
        return self._parent is None

    def is_leaf(self):
        """Return True if this is a leaf node.

        Returns:
            bool

        """
        return self._children is None

    def parents(self):
        """Yield the linearised parents of this node.

        Yields:
            ContextNode

        Examples:
            >>> with ContextNode('a') as a:
            ...     with ContextNode('b') as b:
            ...         c = ContextNode('c')
            >>> c.parents().__next__()
            a/b
            >>> list(c.parents())
            [a/b, a]

        """
        pointer = self._parent
        while pointer:
            yield pointer
            pointer = pointer._parent

    def walk(self, depth=None, level=0):
        """Walk the context tree starting at this node.

        Args:
            depth (int):
                The max depth below the current node to yield.
            level (int):
                For recursive use, do not specify.

        Yields:
            tuple - (level, node)

            level (int):
                The tree level measured from this node.
            node (ContextNode):
                The context node.

        Examples:
            >>> with ContextNode('a') as a:
            ...     with ContextNode('b') as b:
            ...         c = ContextNode('c')
            >>> list(a.walk())
            [(0, a), (1, a/b), (2, a/b/c)]
            >>> list(c.walk())
            [(0, a/b/c)]

        """
        if depth is not None and level >= depth:
            return
        if level == 0:
            yield (0, self)
        for child in self:
            yield (level + 1, child)
            yield from child.walk(depth=depth, level=level + 1)

    def tree(self):
        """Return a string representation of the tree starting at this node.

        Returns:
            str

        Examples:
            >>> with ContextNode('a') as a:
            ...     with ContextNode('b') as b:
            ...         c = ContextNode('c')
            >>> print(a.tree())
            a
                b
                    c

        """
        return '\n'.join((
            f'{"    " * level}{node}'
            for level, node in self.walk()
        ))
