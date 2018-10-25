class Choices(object):
    @classmethod
    def as_choices(cls):
        properties = list(filter(lambda x : not x.startswith ("__"), dir(cls)))
        properties.remove ("as_choices")
        properties.remove ("availabilities")
        choices = []
        for prop in properties:
            val = getattr(cls, prop)
            choices.append((prop, val))
        return choices

    @classmethod
    def availabilities(cls):
        props = list(filter(lambda x: not x.startswith("__"), dir(cls)))
        props.remove("as_choices")
        props.remove("availabilities")
        return props
