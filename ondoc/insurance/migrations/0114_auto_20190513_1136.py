# Generated by Django 2.0.5 on 2019-05-13 06:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0113_auto_20190510_1815'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsuredMemberDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document_first_image', models.ImageField(upload_to='users/images')),
                ('document_second_image', models.ImageField(upload_to='users/images')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='related_document', to='insurance.InsuredMembers')),
            ],
            options={
                'db_table': 'insured_member_document',
            },
        ),
        migrations.AddField(
            model_name='endorsementrequest',
            name='city_code',
            field=models.PositiveIntegerField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='endorsementrequest',
            name='district_code',
            field=models.PositiveIntegerField(default=None, null=True),
        ),
        migrations.AlterModelTable(
            name='endorsementrequest',
            table='insurance_endorsement',
        ),
    ]