# Generated by Django 2.0.5 on 2019-07-26 10:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0215_availablelabtest_insurance_agreed_price'),
        ('doctor', '0284_auto_20190726_1256'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='purchaseordercreation',
            name='provider_name',
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='provider_name_hospital',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.DO_NOTHING, to='doctor.Hospital'),
        ),
        migrations.AddField(
            model_name='purchaseordercreation',
            name='provider_name_lab',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.DO_NOTHING, to='diagnostic.Lab'),
        ),
    ]
