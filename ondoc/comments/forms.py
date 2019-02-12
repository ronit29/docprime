from django import forms
from ondoc.comments.models import CustomComment
from django_comments.forms import CommentForm


class CustomCommentForm(forms.ModelForm):
    is_author = forms.BooleanField(required=False)
    new_comment = forms.CharField(widget=forms.Textarea, required=False)
    email = forms.CharField(required=False)
    name = forms.CharField(required=False)

    def get_comment_create_data(self):
        # Use the data of the superclass, and add in the title field
        data = super(CustomComment, self).get_comment_create_data()
        data['author_id'] = self.cleaned_data['author_id']
        return data