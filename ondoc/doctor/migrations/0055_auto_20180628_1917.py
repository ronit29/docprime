# Generated by Django 2.0.6 on 2018-06-28 13:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0054_merge_20180628_1110'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='doctorhospital',
            name='discounted_price',
        ),
        migrations.AlterField(
            model_name='doctorhospital',
            name='fees',
            field=models.PositiveSmallIntegerField(),
        ),
    ]