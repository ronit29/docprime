# Generated by Django 2.0.5 on 2019-01-02 04:09

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('account', '0045_userreferrals'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserReferred',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('used', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'user_referred',
            },
        ),
        migrations.AddField(
            model_name='userreferrals',
            name='completion_cashback',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='userreferrals',
            name='signup_cashback',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='userreferrals',
            name='code',
            field=models.CharField(max_length=10, unique=True),
        ),
        migrations.AlterField(
            model_name='userreferrals',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, unique=True),
        ),
        migrations.AddField(
            model_name='userreferred',
            name='referral_code',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='account.UserReferrals'),
        ),
        migrations.AddField(
            model_name='userreferred',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, unique=True),
        ),
    ]