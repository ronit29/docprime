# Generated by Django 2.0.5 on 2019-05-03 08:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0250_googledetailing_hospital_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorclinictiming',
            name='cod_deal_price',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]