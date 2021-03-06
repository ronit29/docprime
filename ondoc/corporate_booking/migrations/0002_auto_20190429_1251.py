# Generated by Django 2.0.5 on 2019-04-29 07:21

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0038_merge_20190422_1443'),
        ('corporate_booking', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorporateDeal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deal_start_date', models.DateTimeField()),
                ('deal_end_date', models.DateTimeField()),
                ('payment_date', models.DateTimeField()),
                ('gross_amount', models.IntegerField(default=None)),
                ('tds_deducted', models.IntegerField(choices=[(1, 'Yes'), (2, 'No')], default=2)),
                ('expected_provider_fee', models.IntegerField(default=None)),
                ('employee_count', models.IntegerField(default=None)),
                ('service_description', models.TextField(default='N/A')),
                ('receipt_no', models.CharField(default='', max_length=1000)),
                ('receipt_image', models.FileField(default=None, upload_to='corporate/receipt', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])),
            ],
            options={
                'db_table': 'corporate_deal',
            },
        ),
        migrations.CreateModel(
            name='CorporateDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document_type', models.PositiveSmallIntegerField(choices=[(1, 'PAN Card'), (2, 'Address Proof'), (3, 'GST Certificate'), (4, 'Company Registration Certificate'), (5, 'Bank Statement'), (6, 'LOGO'), (9, 'Email Confirmation')])),
                ('name', models.FileField(upload_to='corporate/images', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])),
            ],
            options={
                'db_table': 'corporate_document',
            },
        ),
        migrations.RemoveField(
            model_name='corporatebooking',
            name='corporate_documents',
        ),
        migrations.RemoveField(
            model_name='corporatebooking',
            name='corporate_id',
        ),
        migrations.AddField(
            model_name='corporatebooking',
            name='PIN',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='PIN Code'),
        ),
        migrations.AddField(
            model_name='corporatebooking',
            name='locality',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='corporatebooking',
            name='matrix_city',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.CASCADE, to='common.MatrixMappedCity'),
        ),
        migrations.AddField(
            model_name='corporatebooking',
            name='matrix_state',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.CASCADE, to='common.MatrixMappedState'),
        ),
        migrations.AddField(
            model_name='corporatebooking',
            name='sublocality',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='corporatebooking',
            name='corporate_address',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='corporatebooking',
            name='corporate_name',
            field=models.CharField(default='', max_length=1000),
        ),
        migrations.AlterField(
            model_name='corporatebooking',
            name='gst_no',
            field=models.CharField(default='', max_length=10000, verbose_name='GST no.'),
        ),
        migrations.AlterField(
            model_name='corporatebooking',
            name='pan_no',
            field=models.CharField(default='', max_length=10000, verbose_name='PAN no.'),
        ),
        migrations.AlterModelTable(
            name='corporatebooking',
            table='corporate_booking',
        ),
        migrations.AddField(
            model_name='corporatedocument',
            name='corporate_booking',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='corporate_documents', to='corporate_booking.CorporateBooking'),
        ),
        migrations.AddField(
            model_name='corporatedeal',
            name='corporate_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='corporate_booking.CorporateBooking', verbose_name='Corporate Name'),
        ),
    ]
