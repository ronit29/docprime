# Generated by Django 2.0.5 on 2019-08-20 10:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0297_merge_20190819_1555'),
    ]

    operations = [
        migrations.AddField(
            model_name='practicespecialization',
            name='bucket_size',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
