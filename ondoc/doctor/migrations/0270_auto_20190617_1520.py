# Generated by Django 2.0.5 on 2019-06-17 09:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0269_merge_20190614_2143'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='new_about',
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='use_new_about',
            field=models.BooleanField(default=False),
        ),
    ]