# Generated by Django 3.2.12 on 2022-04-23 10:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0003_task_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='completed',
            field=models.BooleanField(default=False),
        ),
    ]
