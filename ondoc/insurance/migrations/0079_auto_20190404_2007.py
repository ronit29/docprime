#spoc_type Generated by Django 2.0.5 on 2019-04-04 14:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0078_auto_20190404_1943'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinsurance',
            name='id2',
            field=models.BigIntegerField(default=0, primary_key=False, unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='insurancetransaction',
            name='user_insurance',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='transactions', to='insurance.UserInsurance', to_field='id2'),
        ),
        migrations.AlterField(
            model_name='insuredmembers',
            name='user_insurance',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='members', to='insurance.UserInsurance', to_field='id2'),
        ),
    ]
