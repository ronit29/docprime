# Generated by Django 2.0.5 on 2018-10-12 11:59

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('insurance', '0012_insuredmembers_profile'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsuranceTransaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product_id', models.SmallIntegerField(choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')])),
                ('reference_id', models.PositiveIntegerField(blank=True, null=True)),
                ('order_id', models.PositiveIntegerField()),
                ('type', models.SmallIntegerField(choices=[(0, 'Credit'), (1, 'Debit')])),
                ('payment_mode', models.CharField(max_length=50)),
                ('response_code', models.IntegerField()),
                ('bank_id', models.CharField(max_length=50)),
                ('transaction_date', models.CharField(max_length=80)),
                ('bank_name', models.CharField(max_length=100)),
                ('currency', models.CharField(max_length=15)),
                ('status_code', models.IntegerField()),
                ('pg_name', models.CharField(max_length=100)),
                ('status_type', models.CharField(max_length=50)),
                ('transaction_id', models.CharField(max_length=100, unique=True)),
                ('pb_gateway_name', models.CharField(max_length=100)),
                ('insurance_plan', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.InsurancePlans')),
            ],
            options={
                'db_table': 'insurance_transaction',
            },
        ),
        migrations.RemoveField(
            model_name='pginsurance',
            name='insurance',
        ),
        migrations.RemoveField(
            model_name='pginsurance',
            name='user',
        ),
        migrations.RemoveField(
            model_name='profileinsurance',
            name='insurance',
        ),
        migrations.RemoveField(
            model_name='profileinsurance',
            name='profile',
        ),
        migrations.RemoveField(
            model_name='profileinsurance',
            name='user',
        ),
        migrations.RenameField(
            model_name='insurer',
            old_name='is_disabeld',
            new_name='is_disabled',
        ),
        migrations.RemoveField(
            model_name='insuredmembers',
            name='insurance_plan',
        ),
        migrations.RemoveField(
            model_name='userinsurance',
            name='insurance',
        ),
        migrations.AddField(
            model_name='insurancethreshold',
            name='child_min_age',
            field=models.PositiveIntegerField(default=None),
        ),
        migrations.AddField(
            model_name='userinsurance',
            name='insurance_plan',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.InsurancePlans'),
        ),
        migrations.AddField(
            model_name='userinsurance',
            name='insurer',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.Insurer'),
        ),
        migrations.AlterField(
            model_name='insurance',
            name='product_id',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')]),
        ),
        migrations.AlterField(
            model_name='userinsurance',
            name='product_id',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')]),
        ),
        migrations.DeleteModel(
            name='PgInsurance',
        ),
        migrations.DeleteModel(
            name='ProfileInsurance',
        ),
        migrations.AddField(
            model_name='insurancetransaction',
            name='insurer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.Insurer'),
        ),
        migrations.AddField(
            model_name='insurancetransaction',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
        ),
    ]
