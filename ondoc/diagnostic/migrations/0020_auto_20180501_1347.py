# Generated by Django 2.0.2 on 2018-05-01 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0019_auto_20180430_1916'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labdocument',
            name='document_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'PAN Card'), (2, 'Address Proof'), (3, 'GST Certificate'), (4, 'Registration Certificate'), (5, 'Cancel Cheque Copy'), (6, 'LOGO')]),
        ),
    ]
