# Generated by Django 2.0.5 on 2019-04-10 09:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0087_auto_20190410_1347'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='insurer',
            name='master_policy_number',
        ),
    ]
