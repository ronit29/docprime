# Generated by Django 2.0.5 on 2018-09-21 14:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0112_auto_20180920_1712'),
    ]

    operations = [
        migrations.AddField(
            model_name='generalspecialization',
            name='synonyms',
            field=models.CharField(blank=True, max_length=4000, null=True),
        ),
    ]
