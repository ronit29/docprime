# Generated by Django 2.0.5 on 2019-07-26 07:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0109_merchant_payment_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='source',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
