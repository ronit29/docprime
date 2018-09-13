# Generated by Django 2.0.5 on 2018-09-12 12:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0018_auto_20180906_1239'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='author_name',
            field=models.CharField(max_length=256, null=True),
        ),
        migrations.AddField(
            model_name='article',
            name='published_date',
            field=models.DateField(null=True),
        ),
    ]
