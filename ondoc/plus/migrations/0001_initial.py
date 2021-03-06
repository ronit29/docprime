# Generated by Django 2.0.5 on 2019-08-27 10:14

from django.conf import settings
import django.contrib.postgres.fields.jsonb
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('account', '0098_auto_20190823_1213'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlusPlans',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan_name', models.CharField(max_length=300)),
                ('internal_name', models.CharField(max_length=200, null=True)),
                ('amount', models.PositiveIntegerField(default=0)),
                ('tenure', models.PositiveIntegerField(default=1)),
                ('enabled', models.BooleanField(default=False)),
                ('is_live', models.BooleanField(default=False)),
                ('total_allowed_members', models.PositiveSmallIntegerField(default=0)),
                ('is_selected', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'plus_plans',
            },
        ),
        migrations.CreateModel(
            name='PlusProposer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=250)),
                ('min_float', models.PositiveIntegerField(default=None)),
                ('logo', models.ImageField(null=True, upload_to='plus/images', verbose_name='Plus Logo')),
                ('website', models.CharField(max_length=100, null=True)),
                ('phone_number', models.BigIntegerField(null=True)),
                ('email', models.EmailField(max_length=100, null=True)),
                ('address', models.CharField(default='', max_length=500, null=True)),
                ('company_name', models.CharField(default='', max_length=100, null=True)),
                ('intermediary_name', models.CharField(default='', max_length=100, null=True)),
                ('intermediary_code', models.CharField(default='', max_length=100, null=True)),
                ('intermediary_contact_number', models.BigIntegerField(null=True)),
                ('gstin_number', models.CharField(default='', max_length=50, null=True)),
                ('signature', models.ImageField(null=True, upload_to='plus/images', verbose_name='Plus Signature')),
                ('is_live', models.BooleanField(default=False)),
                ('enabled', models.BooleanField(default=True)),
                ('plus_document', models.FileField(null=True, upload_to='plus/documents', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf'])])),
            ],
            options={
                'db_table': 'plus_proposer',
            },
        ),
        migrations.CreateModel(
            name='PlusThreshold',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('opd_amount_limit', models.PositiveIntegerField(default=0)),
                ('lab_amount_limit', models.PositiveIntegerField(default=0)),
                ('package_amount_limit', models.PositiveIntegerField(default=0)),
                ('custom_validation', django.contrib.postgres.fields.jsonb.JSONField()),
                ('enabled', models.BooleanField(default=False)),
                ('is_live', models.BooleanField(default=False)),
                ('plus_plan', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='plus_threshold', to='plus.PlusPlans')),
            ],
            options={
                'db_table': 'plus_threshold',
            },
        ),
        migrations.CreateModel(
            name='PlusUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('purchase_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('expire_date', models.DateTimeField()),
                ('status', models.PositiveIntegerField(choices=[(1, 'Active'), (2, 'Cancelled'), (3, 'Expired'), (4, 'Onhold'), (5, 'Cancel Initiate'), (6, 'Cancellation Approved')], default=1)),
                ('cancel_reason', models.CharField(blank=True, max_length=300, null=True)),
                ('amount', models.PositiveIntegerField(default=0)),
                ('invoice', models.FileField(default=None, null=True, upload_to='plus/invoice', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf'])])),
                ('price_data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('matrix_lead_id', models.IntegerField(null=True)),
                ('money_pool', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='account.MoneyPool')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='account.Order')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='purchased_plus', to='plus.PlusPlans')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='active_plus_users', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'plus_users',
            },
        ),
        migrations.AddField(
            model_name='plusplans',
            name='proposer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='plus_plans', to='plus.PlusProposer'),
        ),
    ]
