# Generated by Django 2.0.5 on 2018-05-31 13:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0022_auto_20180531_1014'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userpermission',
            name='permission',
        ),
        migrations.AddField(
            model_name='userpermission',
            name='delete_permission',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='permission_type',
            field=models.CharField(choices=[('appointment', 'Appointment')], default='appointment', max_length=20),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='read_permission',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userpermission',
            name='write_permission',
            field=models.BooleanField(default=False),
        ),
    ]
