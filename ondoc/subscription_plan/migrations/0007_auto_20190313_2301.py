# Generated by Django 2.0.5 on 2019-03-13 17:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subscription_plan', '0006_auto_20190313_2246'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='planfeaturemapping',
            unique_together={('plan', 'feature')},
        ),
    ]