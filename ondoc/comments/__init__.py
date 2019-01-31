def get_model():
    from ondoc.comments.models import CustomComment
    return CustomComment


def get_form():
    from ondoc.comments.forms import CustomCommentForm
    return CustomCommentForm