# Generated by Django 2.0.5 on 2019-01-11 09:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0048_merge_20190111_1042'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userreferrals',
            name='completion_cashback',
        ),
        migrations.RemoveField(
            model_name='userreferrals',
            name='signup_cashback',
        ),
    ]
