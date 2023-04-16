import functools


NoDefault = object()


class EnvironProxy(property):
    """ Proxy attribute lookups to keys in the environ. """

    def __init__(self, name, default=NoDefault):
        """
        An entry will be proxied to the supplied name in the .environ
        object of the property holder. A factory can be supplied, for
        values that need to be preinstantiated. If given as first
        parameter name is taken from the callable too.

        @param name: key (or factory for convenience)
        @param default: literal object or callable
        """
        if not isinstance(name, (str, bytes)):
            default = name
            name = default.__name__
        self.name = 'moin.' + name
        self.default = default
        property.__init__(self, self.get, self.set, self.delete)

    def get(self, obj):
        if self.name in obj.environ:
            res = obj.environ[self.name]
        else:
            factory = self.default
            if factory is NoDefault:
                raise AttributeError(self.name)
            elif hasattr(factory, '__call__'):
                res = obj.environ.setdefault(self.name, factory(obj))
            else:
                res = obj.environ.setdefault(self.name, factory)
        return res

    def set(self, obj, value):
        obj.environ[self.name] = value

    def delete(self, obj):
        del obj.environ[self.name]

    def __repr__(self):
        return "<%s for '%s'>" % (self.__class__.__name__, self.name)


def context_timer(name):
    def wrapper(real_func):
        @functools.wraps(real_func)
        def func(origin_context, *args, **kwargs):
            from MoinMoin.web.contexts import Context

            if isinstance(origin_context, Context):
                context = origin_context
            elif isinstance(getattr(origin_context, "context", None), Context):
                context = origin_context.context
            elif isinstance(getattr(origin_context, "request", None), Context):
                context = origin_context.request
            elif args and isinstance(args[0], Context):
                context = args[0]
            else:
                raise ValueError("No context found")
            context.clock.start(name)
            try:
                return real_func(origin_context, *args, **kwargs)
            finally:
                context.clock.stop(name)

        return func

    return wrapper
