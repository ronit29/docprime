# Generated by Django 2.0.5 on 2018-09-06 12:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0105_merge_20180904_1747'),
    ]

    operations = [
        migrations.AlterField(
            model_name='competitorinfo',
            name='name',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('', 'Select'), (1, 'Practo'), (2, 'Lybrate')], null=True),
        ),
    ]