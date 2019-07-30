# Generated by Django 2.0.5 on 2019-07-23 10:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0108_merge_20190718_1833'),
    ]

    operations = [
        migrations.AddField(
            model_name='merchant',
            name='payment_type',
            field=models.PositiveIntegerField(blank=True, choices=[(0, 'NEFT'), (1, 'IFT'), (2, 'IMPS')], null=True),
        ),
    ]
