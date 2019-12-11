# Generated by Django 2.0.5 on 2019-11-15 06:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0115_otpverifications_req_count'),
        ('plus', '0042_auto_20191114_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='tempplususer',
            name='profile',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, related_name='temp_plus_user_profile', to='authentication.UserProfile'),
            preserve_default=False,
        ),
    ]