import json
import random
from datetime import date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from django.contrib import messages

from . import forms, models
from exam import models as QMODEL


def is_student(user):
    return user.groups.filter(name='STUDENT').exists()


def studentclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request, 'student/studentclick.html')


def student_signup_view(request):
    userForm = forms.StudentUserForm()
    studentForm = forms.StudentForm()
    if request.method == 'POST':
        userForm = forms.StudentUserForm(request.POST)
        studentForm = forms.StudentForm(request.POST, request.FILES)
        if userForm.is_valid() and studentForm.is_valid():
            user = userForm.save()
            user.set_password(user.password)
            user.save()
            student = studentForm.save(commit=False)
            student.user = user
            student.save()
            Group.objects.get_or_create(name='STUDENT')[0].user_set.add(user)
            messages.success(request, 'Account created! Please login.')
            return HttpResponseRedirect('studentlogin')
    return render(request, 'student/studentsignup.html', {'userForm': userForm, 'studentForm': studentForm})


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_dashboard_view(request):
    student = get_object_or_404(models.Student, user=request.user)
    available = QMODEL.Course.objects.filter(is_active=True).select_related('subject__academic_course')
    recent = QMODEL.Result.objects.filter(student=student).select_related('exam').order_by('-date')[:5]
    return render(request, 'student/student_dashboard.html', {
        'student': student, 'total_course': available.count(),
        'available_exams': available, 'recent_results': recent,
    })


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_exam_view(request):
    courses = QMODEL.Course.objects.filter(is_active=True).select_related('subject__academic_course')
    return render(request, 'student/student_exam.html', {'courses': courses, 'now': timezone.now()})


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def take_exam_view(request, pk):
    """Instruction screen — checks attempt restriction and time window."""
    course = get_object_or_404(QMODEL.Course, id=pk)
    student = get_object_or_404(models.Student, user=request.user)

    # Same-day attempt restriction
    today_attempts = QMODEL.Result.objects.filter(
        student=student, exam=course, date__date=date.today()
    ).count()
    if today_attempts >= course.max_attempts:
        messages.warning(request, 'You have already used all attempts for this exam today.')
        return redirect('student-exam')

    # Time window check
    now = timezone.now()
    if course.start_time and now < course.start_time:
        messages.warning(request, f'Exam opens at {course.start_time.strftime("%d %b %Y %I:%M %p")}.')
        return redirect('student-exam')
    if course.end_time and now > course.end_time:
        messages.warning(request, 'This exam window has closed.')
        return redirect('student-exam')

    total_q = QMODEL.Question.objects.filter(course=course).count()
    total_marks = QMODEL.Question.objects.filter(course=course).values_list('marks', flat=True)
    return render(request, 'student/take_exam.html', {
        'course': course,
        'total_questions': total_q,
        'total_marks': sum(total_marks),
        'attempt_count': today_attempts,
    })


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
@transaction.atomic
def start_exam_view(request, pk):
    """
    Creates an ExamSession (server-side lock) and serves the exam.
    Uses select_for_update to prevent double-submission race condition.
    """
    course = get_object_or_404(QMODEL.Course, id=pk)
    student = get_object_or_404(models.Student, user=request.user)

    # Prevent duplicate active session (race condition guard)
    active = QMODEL.ExamSession.objects.select_for_update().filter(
        student=student, course=course, status=QMODEL.ExamSession.STATUS_ACTIVE
    ).first()

    if active:
        if active.is_expired:
            active.status = QMODEL.ExamSession.STATUS_EXPIRED
            active.save(update_fields=['status'])
        else:
            # Resume existing session
            session = active
            q_ids = session.question_order
            questions = sorted(
                QMODEL.Question.objects.filter(id__in=q_ids),
                key=lambda q: q_ids.index(q.id)
            )
            elapsed = int((timezone.now() - session.started_at).total_seconds())
            remaining = max(0, course.duration_minutes * 60 - elapsed)
            return render(request, 'student/start_exam.html', {
                'course': course, 'questions': questions,
                'duration_seconds': remaining,
                'session_token': str(session.session_token),
            })

    # Build question order (randomized or fixed)
    all_qs = list(QMODEL.Question.objects.filter(course=course))
    if course.randomize_questions:
        random.shuffle(all_qs)

    expires_at = timezone.now() + timedelta(minutes=course.duration_minutes + 2)  # 2 min grace
    session = QMODEL.ExamSession.objects.create(
        student=student, course=course,
        expires_at=expires_at,
        question_order=[q.id for q in all_qs],
    )

    return render(request, 'student/start_exam.html', {
        'course': course, 'questions': all_qs,
        'duration_seconds': course.duration_minutes * 60,
        'session_token': str(session.session_token),
    })


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
@require_POST
@transaction.atomic
def calculate_marks_view(request):
    """
    Server-side marking with select_for_update to prevent double submission.
    """
    session_token = request.POST.get('session_token')
    if not session_token:
        messages.error(request, 'Invalid session.')
        return redirect('student-exam')

    try:
        session = QMODEL.ExamSession.objects.select_for_update().get(
            session_token=session_token,
            student__user=request.user,
        )
    except QMODEL.ExamSession.DoesNotExist:
        messages.error(request, 'Session not found.')
        return redirect('student-exam')

    # Idempotent: already submitted
    if session.status == QMODEL.ExamSession.STATUS_SUBMITTED:
        return redirect('view-result')

    # Mark session as submitted immediately (prevents concurrent double-submit)
    session.status = QMODEL.ExamSession.STATUS_SUBMITTED
    session.submitted_at = timezone.now()
    session.tab_switch_count  = int(request.POST.get('tab_switch_count', 0))
    session.face_missing_count = int(request.POST.get('face_missing_count', 0))
    session.auto_submitted = request.POST.get('auto_submitted', 'false') == 'true'
    session.save()

    # Evaluate answers from POST data
    q_ids = session.question_order
    questions = sorted(
        QMODEL.Question.objects.filter(id__in=q_ids),
        key=lambda q: q_ids.index(q.id)
    )

    total_marks = 0
    max_marks = 0
    for i, q in enumerate(questions):
        max_marks += q.marks
        submitted = request.POST.get(f'q{i+1}', '')
        if submitted == q.answer:
            total_marks += q.marks

    result = QMODEL.Result.objects.create(
        student=session.student,
        exam=session.course,
        session=session,
        marks=total_marks,
        total_marks=max_marks,
        tab_switch_count=session.tab_switch_count,
        face_missing_count=session.face_missing_count,
        auto_submitted=session.auto_submitted,
    )
    return redirect('view-result')


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def view_result_view(request):
    student = get_object_or_404(models.Student, user=request.user)
    results = QMODEL.Result.objects.filter(student=student).select_related('exam').order_by('-date')
    return render(request, 'student/view_result.html', {'results': results})


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def check_marks_view(request, pk):
    course = get_object_or_404(QMODEL.Course, id=pk)
    student = get_object_or_404(models.Student, user=request.user)
    results = QMODEL.Result.objects.filter(exam=course, student=student)
    return render(request, 'student/check_marks.html', {'results': results, 'course': course})


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def student_marks_view(request):
    courses = QMODEL.Course.objects.all()
    return render(request, 'student/student_marks.html', {'courses': courses})


# ── Proctoring API ──────────────────────────────────────────────────────────

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
@require_POST
def log_proctoring_alert_view(request):
    """
    Server-side proctoring counter.
    Returns the current server-side count so client stays in sync.
    """
    try:
        data = json.loads(request.body)
        alert_type   = data.get('alert_type', 'unknown')
        course_id    = data.get('course_id')
        session_token = data.get('session_token')

        student = get_object_or_404(models.Student, user=request.user)

        session = None
        tab_count = face_count = 0
        if session_token:
            try:
                session = QMODEL.ExamSession.objects.get(
                    session_token=session_token, student=student)
                if alert_type == 'tab_switch':
                    tab_count = session.increment_tab()
                elif alert_type == 'no_face':
                    face_count = session.increment_face()
                else:
                    session.refresh_from_db(fields=['tab_switch_count', 'face_missing_count'])
                    tab_count  = session.tab_switch_count
                    face_count = session.face_missing_count
            except QMODEL.ExamSession.DoesNotExist:
                pass

        QMODEL.ProctoringAlert.objects.create(
            student=student,
            course_id=course_id or None,
            session=session,
            alert_type=alert_type,
        )
        return JsonResponse({
            'status': 'ok',
            'tab_count': tab_count,
            'face_count': face_count,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def check_session_status_view(request):
    """Heartbeat endpoint — client polls every 30s to detect server-side expiry."""
    token = request.GET.get('token')
    if not token:
        return JsonResponse({'status': 'invalid'})
    try:
        s = QMODEL.ExamSession.objects.get(
            session_token=token, student__user=request.user)
        if s.status == QMODEL.ExamSession.STATUS_SUBMITTED:
            return JsonResponse({'status': 'submitted'})
        if s.is_expired:
            s.status = QMODEL.ExamSession.STATUS_EXPIRED
            s.save(update_fields=['status'])
            return JsonResponse({'status': 'expired'})
        remaining = int((s.expires_at - timezone.now()).total_seconds())
        return JsonResponse({
            'status': 'active',
            'remaining_seconds': remaining,
            'tab_count': s.tab_switch_count,
            'face_count': s.face_missing_count,
        })
    except QMODEL.ExamSession.DoesNotExist:
        return JsonResponse({'status': 'not_found'})


# ── Face Capture / Snapshot API ────────────────────────────────────────────

import base64
from django.core.files.base import ContentFile

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def face_capture_view(request):
    """
    Shown after login, before student dashboard.
    Student looks at camera, clicks Capture — image saved as 'login' snapshot.
    """
    next_url = request.GET.get('next', '/student/student-dashboard')
    if request.method == 'POST':
        image_data = request.POST.get('image_data', '')
        if image_data.startswith('data:image'):
            # Strip data-URI header
            fmt, imgstr = image_data.split(';base64,', 1)
            ext = fmt.split('/')[-1]
            student = get_object_or_404(models.Student, user=request.user)
            snapshot = models.StudentFaceSnapshot(
                student=student,
                snapshot_type=models.StudentFaceSnapshot.SNAPSHOT_LOGIN,
            )
            snapshot.image.save(
                f"login_{student.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}",
                ContentFile(base64.b64decode(imgstr)),
                save=True,
            )
            return redirect(next_url)
        messages.error(request, 'Could not capture image. Please try again.')
    return render(request, 'student/face_capture.html', {'next': next_url})


@login_required(login_url='studentlogin')
@user_passes_test(is_student)
@csrf_exempt
@require_POST
def upload_face_snapshot_view(request):
    """
    Called by exam page every ~2-2.5 seconds via JS fetch.
    Saves an 'exam' snapshot linked to the active ExamSession.
    """
    try:
        data = json.loads(request.body)
        image_data   = data.get('image_data', '')
        session_token = data.get('session_token', '')

        if not image_data.startswith('data:image'):
            return JsonResponse({'status': 'error', 'message': 'No image data'}, status=400)

        student = get_object_or_404(models.Student, user=request.user)

        session = None
        if session_token:
            try:
                session = QMODEL.ExamSession.objects.get(
                    session_token=session_token, student=student)
            except QMODEL.ExamSession.DoesNotExist:
                pass

        fmt, imgstr = image_data.split(';base64,', 1)
        ext = fmt.split('/')[-1]
        snapshot = models.StudentFaceSnapshot(
            student=student,
            session=session,
            snapshot_type=models.StudentFaceSnapshot.SNAPSHOT_EXAM,
        )
        snapshot.image.save(
            f"exam_{student.id}_{timezone.now().strftime('%Y%m%d%H%M%S%f')}.{ext}",
            ContentFile(base64.b64decode(imgstr)),
            save=True,
        )
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# ── Exam Schedule ────────────────────────────────────────────────────────────

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def exam_schedule_view(request):
    """All active courses with countdown timers."""
    courses = QMODEL.Course.objects.filter(is_active=True).select_related('subject__academic_course').order_by('start_time')
    return render(request, 'student/exam_schedule.html', {'courses': courses, 'now': timezone.now()})


# ── Result Analysis ──────────────────────────────────────────────────────────

@login_required(login_url='studentlogin')
@user_passes_test(is_student)
def result_analysis_view(request):
    """Subject-wise performance graph data + previous attempt comparison."""
    student = get_object_or_404(models.Student, user=request.user)
    results = QMODEL.Result.objects.filter(student=student).select_related('exam__subject').order_by('-date')

    # Build subject-wise aggregated data for chart
    from collections import defaultdict
    subject_data = defaultdict(lambda: {'marks': 0, 'total': 0, 'count': 0})
    for r in results:
        subj = r.exam.subject.name if r.exam.subject else r.exam.course_name
        subject_data[subj]['marks'] += r.marks
        subject_data[subj]['total'] += r.total_marks
        subject_data[subj]['count'] += 1

    chart_labels = []
    chart_scores = []
    for subj, d in subject_data.items():
        chart_labels.append(subj)
        avg = round((d['marks'] / d['total']) * 100, 1) if d['total'] else 0
        chart_scores.append(avg)

    # Previous attempt comparison — per exam, show all attempts
    exam_attempts = defaultdict(list)
    for r in results:
        exam_attempts[r.exam.course_name].append({
            'date': r.date.strftime('%d %b'),
            'pct': r.percentage,
            'marks': r.marks,
            'total': r.total_marks,
            'grade': r.grade,
        })

    import json as _json
    return render(request, 'student/result_analysis.html', {
        'results': results,
        'chart_labels': _json.dumps(chart_labels),
        'chart_scores': _json.dumps(chart_scores),
        'exam_attempts': dict(exam_attempts),
    })
