# Generated by Django 2.0.5 on 2019-02-28 06:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0204_auto_20190227_1214'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='source_type',
            field=models.IntegerField(choices=[(1, 'Agent'), (2, 'Provider')], default=None, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='source_type',
            field=models.IntegerField(choices=[(1, 'Agent'), (2, 'Provider')], default=None, editable=False, null=True),
        ),
    ]
