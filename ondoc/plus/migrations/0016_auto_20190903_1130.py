# Generated by Django 2.0.5 on 2019-09-03 06:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0015_pluslead'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusmembers',
            name='district',
            field=models.CharField(default=None, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='district_code',
            field=models.CharField(blank=True, default=None, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='gender',
            field=models.CharField(choices=[('m', 'Male'), ('f', 'Female'), ('o', 'Other')], default=None, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='profile',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='plus_member', to='authentication.UserProfile'),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='state',
            field=models.CharField(default=None, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='state_code',
            field=models.CharField(default=None, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='town',
            field=models.CharField(default=None, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='relation',
            field=models.CharField(
                choices=[('BROTHER', 'BROTHER'), ('DAUGHTER', 'DAUGHTER'), ('FATHER', 'FATHER'), ('MOTHER', 'MOTHER'),
                         ('OTHERS', 'OTHERS'), ('SELF', 'SELF'), ('SISTER', 'SISTER'), ('SON', 'SON'),
                         ('SPOUSE', 'SPOUSE'), ('SPOUSE_FATHER', 'SPOUSE_FATHER'), ('SPOUSE_MOTHER', 'SPOUSE_MOTHER')],
                default=None, max_length=50, null=True),
        ),
    ]