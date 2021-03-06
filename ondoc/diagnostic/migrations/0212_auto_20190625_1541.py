# Generated by Django 2.0.5 on 2019-06-25 10:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0274_opdappointment_hospital_reference_id'),
        ('diagnostic', '0211_merge_20190624_1827'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='is_ipd_lab',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='lab',
            name='related_hospital',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='ipd_hospital', to='doctor.Hospital'),
        ),
    ]
