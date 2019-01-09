# Generated by Django 2.0.5 on 2018-12-18 05:08

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('coupon', '0015_coupon_step_count'),
    ]

    operations = [
        migrations.CreateModel(
            name='RandomGeneratedCoupon',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('random_coupon', models.CharField(max_length=50)),
                ('consumed_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('sent_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='random_generated_coupon', to='coupon.Coupon')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('validity', models.PositiveIntegerField(default=None)),
            ],
            options={
                'db_table': 'random_generated_coupon',
            },
        ),
    ]
