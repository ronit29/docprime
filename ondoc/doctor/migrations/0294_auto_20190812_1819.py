# Generated by Django 2.0.5 on 2019-08-12 12:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0293_merge_20190812_1450'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchaseordercreation',
            name='provider_name_hospital',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='hospitalpurchaseorder', to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='purchaseordercreation',
            name='provider_name_lab',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='diagnostic.Lab'),
        ),
    ]
