# Generated by Django 2.0.5 on 2018-12-12 05:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0135_merge_20181207_1957'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='cashback',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
