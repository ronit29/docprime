# Generated by Django 2.0.5 on 2019-07-09 15:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0102_usernumberupdate_is_successfull'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usernumberupdate',
            name='user',
            field=models.ForeignKey(limit_choices_to={'user_type': 3}, on_delete=django.db.models.deletion.DO_NOTHING, related_name='number_updates', to=settings.AUTH_USER_MODEL),
        ),
    ]
