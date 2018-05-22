from django.contrib.admin.views.autocomplete import AutocompleteJsonView

class CustomAutoComplete(AutocompleteJsonView):
    def has_perm(self, request, obj=None):
        return True
        """Check if user has permission to access the related model."""
        #return self.model_admin.has_change_permission(request, obj=obj)
