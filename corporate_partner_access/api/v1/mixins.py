"""Mixins for corporate_partner_access API v1."""


class InjectNestedFKMixin:
    """Generic mixin to inject/override a nested FK id from URL kwargs into serializer data.

    Subclasses set:
      nested_lookup_kwarg: name of kwarg added by nested router.
      target_field_name: serializer field to populate.
    """

    nested_lookup_kwarg = None
    target_field_name = None

    def get_serializer(self, *args, **kwargs):
        """Inject the nested FK id into serializer data if applicable."""
        if (
            "data" in kwargs
            and self.nested_lookup_kwarg
            and self.target_field_name
            and self.kwargs.get(self.nested_lookup_kwarg)
        ):
            data = kwargs["data"]
            if hasattr(data, "copy"):
                data = data.copy()
            data[self.target_field_name] = self.kwargs[self.nested_lookup_kwarg]
            kwargs["data"] = data
        return super().get_serializer(*args, **kwargs)
