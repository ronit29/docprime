# Generated by Django 2.0.5 on 2018-06-15 12:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0046_auto_20180612_1946'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorhospital',
            name='discounted_price',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='doctorhospital',
            name='effective_price',
            field=models.PositiveSmallIntegerField(default=0),
        ),

    ]
