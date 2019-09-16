# Generated by Django 2.0.5 on 2019-09-10 14:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0313_merge_20190904_1219'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opdappointment',
            name='payment_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Prepaid'), (2, 'COD'), (3, 'Insurance'), (4, 'Subscription Plan'), (5, 'VIP')], default=1),
        ),
    ]
