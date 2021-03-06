# Generated by Django 2.0.5 on 2019-08-05 08:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0288_merge_20190802_1217'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='purchaseordercreation',
            name='active_till',
        ),
        migrations.RemoveField(
            model_name='purchaseordercreation',
            name='appointment_count',
        ),
        migrations.AddField(
            model_name='hospital',
            name='enabled_poc',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='opdappointment',
            name='purchase_order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='doctor.PurchaseOrderCreation'),
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='appointment_booked_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='current_appointment_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='end_date',
            field=models.DateField(default=None),
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='is_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='start_date',
            field=models.DateField(default=None),
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='total_appointment_count',
            field=models.IntegerField(default=0),
        ),
    ]
