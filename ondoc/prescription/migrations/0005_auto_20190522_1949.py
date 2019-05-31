# Generated by Django 2.0.5 on 2019-05-22 14:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('prescription', '0004_appointmentprescription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointmentprescription',
            name='content_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='contenttypes.ContentType'),
        ),
        migrations.AlterField(
            model_name='appointmentprescription',
            name='object_id',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
