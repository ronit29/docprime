# Generated by Django 2.0.5 on 2019-04-11 06:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0088_remove_insurer_master_policy_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='insurancetransaction',
            name='user_insurance2',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.DO_NOTHING, related_name='transactions2', to='insurance.UserInsurance'),
        ),
    ]
