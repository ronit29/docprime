# Generated by Django 2.0.5 on 2018-10-23 08:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0140_auto_20181023_1318'),
    ]

    operations = [
        migrations.RenameField(
            model_name='doctorpopularity',
            old_name='reviews',
            new_name='reviews_count',
        ),
        migrations.RenameField(
            model_name='doctorpopularity',
            old_name='votes',
            new_name='votes_count',
        ),
    ]
