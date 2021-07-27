class classproperty(property):
    """
    An implementation of a property callable on a class. Used to decorate a
    classmethod but to then treat it like a property.
    :see: keyring.util.properties.ClassProperty (in Py3.8 and above)
    """
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()
