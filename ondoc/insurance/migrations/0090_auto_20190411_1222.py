# Generated by Django 2.0.5 on 2019-04-11 06:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0089_insurancetransaction_user_insurance2'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='insurancetransaction',
            unique_together=set(),
        ),
    ]
