"""
Management command to seed demo accounts for BBDNIIT Exam Platform.
Run: python manage.py seed_demo --settings=onlinexam.settings.development
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from teacher.models import Teacher
from student.models import Student


class Command(BaseCommand):
    help = 'Create demo accounts: admin, teacher_demo, student_demo'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding demo accounts...')

        # Ensure groups exist
        student_group, _ = Group.objects.get_or_create(name='STUDENT')
        teacher_group, _ = Group.objects.get_or_create(name='TEACHER')

        # ── Admin ──────────────────────────────────────────────
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@bbdniit.ac.in',
                password='admin123',
                first_name='Admin',
                last_name='BBDNIIT',
            )
            self.stdout.write(self.style.SUCCESS('  [+] admin created'))
        else:
            u = User.objects.get(username='admin')
            u.set_password('admin123')
            u.is_superuser = True
            u.is_staff = True
            u.save()
            self.stdout.write('  [~] admin already exists — password reset')

        # ── Teacher ────────────────────────────────────────────
        if not User.objects.filter(username='teacher_demo').exists():
            t_user = User.objects.create_user(
                username='teacher_demo',
                email='teacher@bbdniit.ac.in',
                password='teacher123',
                first_name='Demo',
                last_name='Teacher',
            )
            t_user.is_staff = True
            t_user.save()
            # Add to TEACHER group — required for is_teacher() check
            teacher_group.user_set.add(t_user)
            Teacher.objects.create(
                user=t_user,
                mobile='9999900001',
                address='BBDNIIT Campus, Lucknow',
                status=True,  # approved — no waiting screen
            )
            self.stdout.write(self.style.SUCCESS('  [+] teacher_demo created'))
        else:
            u = User.objects.get(username='teacher_demo')
            u.set_password('teacher123')
            u.save()
            teacher_group.user_set.add(u)
            # Make sure Teacher profile exists
            if not Teacher.objects.filter(user=u).exists():
                Teacher.objects.create(user=u, mobile='9999900001', status=True)
            else:
                Teacher.objects.filter(user=u).update(status=True)
            self.stdout.write('  [~] teacher_demo already exists — password + group fixed')

        # ── Student ────────────────────────────────────────────
        if not User.objects.filter(username='student_demo').exists():
            s_user = User.objects.create_user(
                username='student_demo',
                email='student@bbdniit.ac.in',
                password='student123',
                first_name='Demo',
                last_name='Student',
            )
            # Add to STUDENT group — required for is_student() check + face capture
            student_group.user_set.add(s_user)
            Student.objects.create(
                user=s_user,
                mobile='9999900002',
                address='BBDNIIT Campus, Lucknow',
                roll_number='DEMO001',
            )
            self.stdout.write(self.style.SUCCESS('  [+] student_demo created'))
        else:
            u = User.objects.get(username='student_demo')
            u.set_password('student123')
            u.save()
            student_group.user_set.add(u)
            # Make sure Student profile exists
            if not Student.objects.filter(user=u).exists():
                Student.objects.create(user=u, mobile='9999900002', roll_number='DEMO001')
            self.stdout.write('  [~] student_demo already exists — password + group fixed')

        self.stdout.write(self.style.SUCCESS('\nDemo accounts ready!'))
        self.stdout.write('  Admin:   admin / admin123       → /adminlogin')
        self.stdout.write('  Teacher: teacher_demo / teacher123 → /teacher/teacherlogin')
        self.stdout.write('  Student: student_demo / student123 → /student/studentlogin')