# Generated by Django 2.0.5 on 2020-01-21 08:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0344_searchscoreparams'),
    ]

    operations = [
        migrations.RenameField(
            model_name='searchscoreparams',
            old_name='value',
            new_name='max_score',
        ),
    ]
