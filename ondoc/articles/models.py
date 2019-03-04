from django.db import models
from django.utils.safestring import mark_safe
from ondoc.authentication.models import TimeStampedModel, CreatedByModel, Image
import datetime
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from ondoc.doctor.models import Doctor


class ArticleCategory(TimeStampedModel):

    name = models.CharField(blank=False, null=False, max_length=500)
    identifier = models.CharField(max_length=48, blank=False, null=True)
    url = models.CharField(blank=False, null=True, max_length=500, unique=True)
    title = models.CharField(max_length=500, null=True, blank=True)
    description = models.CharField(max_length=200000, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "article_categories"

    def save(self, *args, **kwargs):
        if hasattr(self, 'url'):
            self.url = self.url.strip('/').lower()
        super(ArticleCategory, self).save(*args, **kwargs)


class Article(TimeStampedModel, CreatedByModel):
    title = models.CharField(blank=False, null=False, max_length=500, unique=True)
    url = models.CharField(blank=False, null=True, max_length=500, unique=True)
    heading_title = models.CharField(blank=True, null=False, max_length=500)
    body = models.CharField(blank=False, null=False, max_length=200000)
    category = models.ForeignKey(ArticleCategory, null=True, related_name='articles', on_delete=models.SET_NULL)
    header_image = models.ImageField(upload_to='articles/header/images', null=True, blank=True, default='')
    header_image_alt = models.CharField(max_length=512, blank=True, null=True, default='')
    icon = models.ImageField(upload_to='articles/icons', null=True, blank=True, default='')
    is_published = models.BooleanField(default=False, verbose_name='Published')
    description = models.CharField(max_length=500, blank=True, null=True)
    keywords = models.CharField(max_length=256, blank=True, null=True)
    author_name = models.CharField(max_length=256, null=True, blank=True)
    author = models.ForeignKey(Doctor, null=True, blank=True, related_name='published_articles', on_delete=models.SET_NULL)
    published_date = models.DateField(default=datetime.date.today)
    linked_articles = models.ManyToManyField('self', symmetrical=False, through='LinkedArticle',
                                             through_fields=('article', 'linked_article'))

    def get_absolute_url(self):
        content_type = ContentType.objects.get_for_model(self)
        return reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model), args=[self.id])

    def icon_tag(self):
        if self.icon:
            return mark_safe('<img src="%s" width="150" height="150" />' % (self.icon.url))
        return ""

    def save(self, *args, **kwargs):
        self.published_date = self.published_date if self.published_date else datetime.date.today()
        if hasattr(self, 'url'):
            self.url = self.url.strip('/').lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        db_table = "article"


class ArticleImage(TimeStampedModel, CreatedByModel):
    name = models.ImageField(upload_to='article/images')

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

class ArticleContentBox(TimeStampedModel):
    name = models.CharField(max_length=1000)
    title = models.CharField(max_length=1000)
    rank = models.PositiveSmallIntegerField(default=0, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'article_content_box'


class ArticleLinkedUrl(TimeStampedModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    url = models.CharField(max_length=2000, unique=True)
    title = models.CharField(max_length=500)
    content_box = models.ForeignKey(ArticleContentBox,null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.title

    class Meta:
        db_table = 'article_linked_urls'


class LinkedArticle(TimeStampedModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='related_articles')
    linked_article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='related_article')
    title = models.CharField(max_length=500, null=True, blank=False)
    content_box = models.ForeignKey(ArticleContentBox,null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return "{}-{}".format(self.article.title, self.linked_article.title)

    class Meta:
        db_table = 'linked_articles'
        unique_together = (('article', 'linked_article'),)
