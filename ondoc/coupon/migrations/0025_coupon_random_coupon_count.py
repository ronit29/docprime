# Generated by Django 2.0.5 on 2019-05-01 07:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0024_auto_20190218_1240'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='random_coupon_count',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
