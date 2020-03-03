# Generated by Django 2.0.5 on 2020-02-24 09:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0059_delete_corporategroup'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusplans',
            name='is_prescription_required',
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name='plusplans',
            name='priority',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
