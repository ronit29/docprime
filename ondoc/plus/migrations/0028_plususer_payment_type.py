# Generated by Django 2.0.5 on 2019-10-01 09:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0027_plusplans_is_retail'),
    ]

    operations = [
        migrations.AddField(
            model_name='plususer',
            name='payment_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Prepaid'), (2, 'COD'), (3, 'Insurance'), (4, 'Subscription Plan'), (5, 'VIP')], default=1),
        ),
    ]