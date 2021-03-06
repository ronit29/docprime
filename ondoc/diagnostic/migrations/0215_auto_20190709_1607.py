# Generated by Django 2.0.5 on 2019-07-09 10:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0214_auto_20190704_1319'),
    ]

    operations = [
        migrations.CreateModel(
            name='LabTestCategoryLandingURLS',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compare_lab', to='diagnostic.LabTestCategory')),
            ],
            options={
                'db_table': 'lab_test_category_landing_urls',
            },
        ),
        migrations.CreateModel(
            name='LabTestCategoryUrls',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('url', models.SlugField(max_length=2000, null=True, unique=True)),
                ('title', models.CharField(blank=True, max_length=2000, null=True)),
            ],
            options={
                'db_table': 'lab_test_category_urls',
            },
        ),
        migrations.AddField(
            model_name='labtestcategorylandingurls',
            name='url',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lab_category_url', to='diagnostic.LabTestCategoryUrls'),
        ),
    ]
