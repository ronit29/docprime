# Generated by Django 2.0.5 on 2018-10-23 10:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0142_auto_20181023_1403'),
    ]

    operations = [
        migrations.AddField(
            model_name='practicespecialization',
            name='synonyms',
            field=models.CharField(blank=True, max_length=4000, null=True),
        ),
    ]
