# Generated by Django 5.1.7 on 2025-03-13 18:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daily_trainning_app',
         '0002_user_peso_maximo_rm_workoutdata_nivel_fatiga_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='workoutdata',
            name='nivel_fatiga',
        ),
        migrations.AddField(
            model_name='exercise',
            name='nivel_fatiga',
            field=models.CharField(
                choices=[
                    ('Bajo',
                     'Low'),
                    ('Medio',
                     'Medium'),
                    ('Alto',
                     'High')],
                default='Medio',
                max_length=10,
                verbose_name='Fatigue Level'),
        ),
    ]
