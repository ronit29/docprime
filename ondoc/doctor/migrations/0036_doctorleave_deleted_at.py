# Generated by Django 2.0.5 on 2018-05-11 09:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0035_auto_20180510_1628'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorleave',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]