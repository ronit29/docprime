# Generated by Django 2.0.5 on 2019-05-15 07:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0028_bannerlocation'),
    ]

    operations = [
        migrations.RenameField(
            model_name='bannerlocation',
            old_name='banner_location',
            new_name='banner',
        ),
    ]
