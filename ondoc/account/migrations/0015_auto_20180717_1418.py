# Generated by Django 2.0.5 on 2018-07-17 08:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0014_auto_20180717_1139'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='invoices'),
        ),
    ]
