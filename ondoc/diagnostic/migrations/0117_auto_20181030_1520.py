# Generated by Django 2.0.5 on 2018-10-30 09:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0150_auto_20181030_1520'),
        ('diagnostic', '0116_remove_lab_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='cancellation_comments',
            field=models.CharField(blank=True, max_length=5000, null=True),
        ),
        migrations.AddField(
            model_name='labappointment',
            name='cancellation_reason',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.CancellationReason'),
        ),
    ]