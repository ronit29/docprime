# Generated by Django 2.0.5 on 2019-07-23 10:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0281_auto_20190719_1121'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorclinictiming',
            name='insurance_fees',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]