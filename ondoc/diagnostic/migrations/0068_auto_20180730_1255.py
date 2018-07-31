# Generated by Django 2.0.5 on 2018-07-30 07:25

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0067_auto_20180727_1721'),
    ]

    operations = [
        migrations.CreateModel(
            name='LabNetworkDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document_type', models.PositiveSmallIntegerField(choices=[(1, 'PAN Card'), (2, 'Address Proof'), (3, 'GST Certificate'), (4, 'Registration Certificate'), (5, 'Cancel Cheque Copy'), (6, 'LOGO'), (9, 'Email Confirmation')])),
                ('name', models.FileField(upload_to='lab_network/documents', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])),
                ('lab_network', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='lab_documents', to='diagnostic.LabNetwork')),
            ],
            options={
                'db_table': 'lab_network_document',
            },
        ),
        migrations.AlterField(
            model_name='labdocument',
            name='document_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'PAN Card'), (2, 'Address Proof'), (3, 'GST Certificate'), (4, 'Registration Certificate'), (5, 'Cancel Cheque Copy'), (6, 'LOGO'), (9, 'Email Confirmation')]),
        ),
    ]