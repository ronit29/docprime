# Generated by Django 2.0.5 on 2018-11-28 07:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0008_auto_20181127_1903'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='total_count',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]