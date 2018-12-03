# Generated by Django 2.0.5 on 2018-11-28 11:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0167_merge_20181122_1240'),
        ('authentication', '0075_auto_20181120_1808'),
    ]

    operations = [
        migrations.AlterField(
            model_name='genericadmin',
            name='permission_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Appointment'), (2, 'Billing')], default=1),
        ),
        migrations.AlterField(
            model_name='genericlabadmin',
            name='permission_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Appointment'), (2, 'Billing')], default=1),
        ),
        migrations.AlterUniqueTogether(
            name='doctornumber',
            unique_together={('doctor', 'hospital')},
        ),
    ]
