from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0001_initial'),
        ('exam', '0002_rename_exam_session_lookup_idx_exam_examse_student_62cad2_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentFaceSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='face_snapshots/')),
                ('snapshot_type', models.CharField(
                    max_length=20,
                    choices=[('login', 'Login Verification'), ('exam', 'Exam Monitoring')],
                    default='exam',
                )),
                ('captured_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='face_snapshots',
                    to='student.student',
                )),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    blank=True,
                    related_name='face_snapshots',
                    to='exam.examsession',
                )),
            ],
            options={
                'ordering': ['-captured_at'],
                'indexes': [models.Index(fields=['student', 'snapshot_type'], name='student_face_snap_idx')],
            },
        ),
    ]
