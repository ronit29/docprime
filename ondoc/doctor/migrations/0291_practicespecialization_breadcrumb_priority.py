# Generated by Django 2.0.5 on 2019-08-12 08:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0290_merge_20190809_1656'),
    ]

    operations = [
        migrations.AddField(
            model_name='practicespecialization',
            name='breadcrumb_priority',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]