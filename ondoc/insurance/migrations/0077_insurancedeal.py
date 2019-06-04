# Generated by Django 2.0.5 on 2019-04-02 08:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0076_insurer_insurer_merchant_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsuranceDeal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deal_id', models.CharField(max_length=50)),
                ('commission', models.FloatField(default=0)),
                ('tax', models.FloatField(default=0)),
                ('deal_start_date', models.DateField()),
                ('deal_end_date', models.DateField()),
                ('insurer', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='deals', to='insurance.Insurer')),
            ],
            options={
                'db_table': 'insurance_deals',
            },
        ),
    ]