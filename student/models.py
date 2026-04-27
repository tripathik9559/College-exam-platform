from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_pic = models.ImageField(upload_to='profile_pic/Student/', null=True, blank=True)
    address = models.CharField(max_length=100, blank=True)
    mobile = models.CharField(max_length=20)
    roll_number = models.CharField(max_length=30, blank=True)

    @property
    def get_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def get_instance(self):
        return self

    def __str__(self):
        return self.get_name


class StudentFaceSnapshot(models.Model):
    SNAPSHOT_LOGIN = 'login'
    SNAPSHOT_EXAM  = 'exam'
    SNAPSHOT_CHOICES = [
        (SNAPSHOT_LOGIN, 'Login Verification'),
        (SNAPSHOT_EXAM,  'Exam Monitoring'),
    ]

    student       = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='face_snapshots')
    # session is null for login snapshots, set for exam snapshots
    session       = models.ForeignKey(
        'exam.ExamSession', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='face_snapshots'
    )
    image         = models.ImageField(upload_to='face_snapshots/')
    snapshot_type = models.CharField(max_length=20, choices=SNAPSHOT_CHOICES, default=SNAPSHOT_EXAM)
    captured_at   = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-captured_at']
        indexes = [models.Index(fields=['student', 'snapshot_type'], name='student_face_snap_idx')]

    def __str__(self):
        return f"{self.student} | {self.snapshot_type} | {self.captured_at:%Y-%m-%d %H:%M}"
