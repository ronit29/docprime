# Generated by Django 2.0.5 on 2018-11-15 11:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0004_auto_20181029_1226'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coupon',
            name='validity',
            field=models.PositiveIntegerField(),
        ),
    ]