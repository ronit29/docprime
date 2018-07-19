from django.db import models
from django.utils.safestring import mark_safe
from ondoc.authentication.models import TimeStampedModel, CreatedByModel, Image


class ArticleCategory(TimeStampedModel):
    name = models.CharField(blank=False, null=False, max_length=500)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "article_categories"


class Article(TimeStampedModel, CreatedByModel):
    title = models.CharField(blank=False, null=False, max_length=500)
    url = models.CharField(blank=False, null=True, max_length=500)
    body = models.CharField(blank=False, null=False, max_length=20000)
    category = models.ManyToManyField(ArticleCategory, related_name='articles')
    icon = models.ImageField(upload_to='articles/icons', null=True)

    def icon_tag(self):
        if self.icon:
            return mark_safe('<img src="%s" width="150" height="150" />' % (self.icon.url))
        return ""

    def __str__(self):
        return self.title

    class Meta:
        db_table = "article"


class ArticleImage(TimeStampedModel, CreatedByModel, Image):
    name = models.ImageField(upload_to='article/images', height_field='height', width_field='width')

    def image_tag(self):
        if self.name:
            return mark_safe('<img src="%s" width="150" height="150" />' % (self.name.url))
        return ""

    def __str__(self):
        if self.name:
            return self.name.url
        return ""

    class Meta:
        db_table = "article_image"
