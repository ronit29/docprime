# Generated by Django 2.0.2 on 2018-08-02 06:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0070_merge_20180802_1133'),
    ]

    operations = [
        migrations.AlterField(
            model_name='availablelabtest',
            name='lab',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='availabletests', to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='availablelabtest',
            name='test',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availablelabs', to='diagnostic.LabTest'),
        ),
        migrations.AlterField(
            model_name='commontest',
            name='test',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commontest', to='diagnostic.LabTest'),
        ),
        migrations.AlterField(
            model_name='diagnosticconditionlabtest',
            name='diagnostic_condition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.CommonDiagnosticCondition'),
        ),
        migrations.AlterField(
            model_name='diagnosticconditionlabtest',
            name='lab_test',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabTest'),
        ),
        migrations.AlterField(
            model_name='labaccreditation',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labaward',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labcertification',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lab_certificate', to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labdoctor',
            name='lab',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labdoctoravailability',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labdocument',
            name='lab',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='lab_documents', to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labimage',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lab_image', to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labmanager',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labnetworkaccreditation',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabNetwork'),
        ),
        migrations.AlterField(
            model_name='labnetworkaward',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabNetwork'),
        ),
        migrations.AlterField(
            model_name='labnetworkcertification',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabNetwork'),
        ),
        migrations.AlterField(
            model_name='labnetworkemail',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabNetwork'),
        ),
        migrations.AlterField(
            model_name='labnetworkhelpline',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabNetwork'),
        ),
        migrations.AlterField(
            model_name='labnetworkmanager',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabNetwork'),
        ),
        migrations.AlterField(
            model_name='labservice',
            name='lab',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labtiming',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lab_timings', to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='promotedlab',
            name='lab',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
    ]