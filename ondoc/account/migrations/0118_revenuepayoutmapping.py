# Generated by Django 2.0.5 on 2020-02-20 11:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('account', '0117_merchantpayout_payout_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='RevenuePayoutMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.BigIntegerField()),
                ('content_type', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.ContentType')),
                ('payout', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='account.MerchantPayout')),
            ],
            options={
                'db_table': 'revenue_payout_mapping',
            },
        ),
    ]
