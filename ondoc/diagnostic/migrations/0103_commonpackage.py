# Generated by Django 2.0.5 on 2018-10-16 12:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0102_labtest_synonyms'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonPackage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('icon', models.ImageField(null=True, upload_to='diagnostic/common_package_icons')),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commonpackage', to='diagnostic.LabTest')),
            ],
            options={
                'db_table': 'common_package',
            },
        ),
    ]