# Generated by Django 2.0.5 on 2018-12-11 12:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0172_auto_20181211_1650'),
    ]

    operations = [
        migrations.RenameField(
            model_name='doctormobileotp',
            old_name='doctor',
            new_name='doctor_mobile',
        ),
    ]