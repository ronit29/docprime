# Generated by Django 2.0.5 on 2020-01-27 10:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0347_auto_20200127_1515'),
    ]

    operations = [
        migrations.RenameField(
            model_name='searchscoreparams',
            old_name='weightage',
            new_name='score_weightage',
        ),
    ]
