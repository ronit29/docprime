# Generated by Django 2.0.6 on 2018-06-19 06:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_auto_20180618_1253'),
    ]

    operations = [
        migrations.RenameField(
            model_name='order',
            old_name='appointment_id',
            new_name='reference_id',
        ),
        migrations.AlterField(
            model_name='order',
            name='action',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('', 'Select'), (1, 'Opd Reschedule'), (2, 'Opd Create'), (4, 'Lab Create'), (3, 'Lab Reschedule')], null=True),
        ),
    ]