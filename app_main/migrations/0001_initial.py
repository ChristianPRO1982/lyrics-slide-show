# Generated by Django 5.1.2 on 2024-10-23 15:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Song',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Verse',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('num', models.IntegerField()),
                ('num_verse', models.IntegerField()),
                ('chorus', models.BooleanField()),
                ('text', models.TextField(blank=True, null=True)),
                ('song', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='verses', to='app_main.song')),
            ],
        ),
    ]
