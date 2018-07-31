# Generated by Django 2.0.5 on 2018-07-28 14:59

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0080_auto_20180724_1612'),
    ]

    operations = [
        migrations.CreateModel(
            name='HospitalNetworkDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document_type', models.PositiveSmallIntegerField(choices=[(1, 'PAN Card'), (2, 'Address Proof'), (3, 'GST Certificate'), (4, 'MCI Registration Number'), (5, 'Cancel Cheque Copy'), (8, 'COI/Company Registration'), (9, 'Email Confirmation')])),
                ('name', models.FileField(upload_to='hospital_network/documents', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])),
                ('hospital_network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork')),
            ],
            options={
                'db_table': 'hospital_network_document',
            },
        ),
        migrations.AddField(
            model_name='hospitaldocument',
            name='document_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'PAN Card'), (2, 'Address Proof'), (3, 'GST Certificate'), (4, 'MCI Registration Number'), (5, 'Cancel Cheque Copy'), (8, 'COI/Company Registration'), (9, 'Email Confirmation')], default=2),
        ),
    ]