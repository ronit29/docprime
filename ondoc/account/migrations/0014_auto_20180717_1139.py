# Generated by Django 2.0.5 on 2018-07-17 06:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0013_invoice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='doctor/documents/invoices'),
        ),
    ]
