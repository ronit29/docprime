# Generated by Django 2.0.5 on 2019-01-23 12:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='integratormapping',
            old_name='test_id',
            new_name='test',
        ),
    ]