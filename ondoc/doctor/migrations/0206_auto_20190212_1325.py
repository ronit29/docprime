# Generated by Django 2.0.5 on 2019-02-12 07:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0205_auto_20190212_1306'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='doctor',
            name='welcome_calling_done',
        ),
        migrations.RemoveField(
            model_name='doctor',
            name='welcome_calling_done_at',
        ),
    ]
