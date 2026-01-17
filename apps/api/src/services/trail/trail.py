from datetime import datetime
from uuid import uuid4
from src.db.courses.chapter_activities import ChapterActivity
from fastapi import HTTPException, Request, status
from sqlmodel import Session, select
from src.db.courses.activities import Activity
from src.db.courses.courses import Course
from src.db.trail_runs import TrailRun, TrailRunRead
from src.db.trail_steps import TrailStep
from src.db.trails import Trail, TrailCreate, TrailRead
from src.db.users import AnonymousUser, PublicUser
from src.services.courses.certifications import check_course_completion_and_create_certificate


def _populate_trail_runs_steps(
    db_session: Session,
    trail_runs: list[TrailRunRead],
    user_id: int | None = None,
):
    trail_run_ids = [tr.id for tr in trail_runs]
    if not trail_run_ids:
        return

    # Fetch all steps
    query = select(TrailStep).where(TrailStep.trailrun_id.in_(trail_run_ids))
    if user_id:
        query = query.where(TrailStep.user_id == user_id)

    all_trail_steps = db_session.exec(query).all()

    # Convert to objects
    all_trail_steps_objs = [TrailStep(**step.__dict__) for step in all_trail_steps]

    # Fetch courses
    course_ids = {step.course_id for step in all_trail_steps_objs}
    courses_map = {}
    if course_ids:
        courses = db_session.exec(select(Course).where(Course.id.in_(course_ids))).all()
        courses_map = {c.id: c for c in courses}

    # Group steps
    steps_by_run_id = {}
    for step in all_trail_steps_objs:
        course = courses_map.get(step.course_id)
        step.data = dict(course=course)

        if step.trailrun_id not in steps_by_run_id:
            steps_by_run_id[step.trailrun_id] = []
        steps_by_run_id[step.trailrun_id].append(step)

    # Assign to runs
    for trail_run in trail_runs:
        trail_run.steps = steps_by_run_id.get(trail_run.id, [])


async def create_user_trail(
    request: Request,
    user: PublicUser,
    trail_object: TrailCreate,
    db_session: Session,
) -> Trail:
    statement = select(Trail).where(
        Trail.org_id == trail_object.org_id, Trail.user_id == user.id
    )
    trail = db_session.exec(statement).first()

    if trail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trail already exists",
        )

    trail = Trail.model_validate(trail_object)

    trail.creation_date = str(datetime.now())
    trail.update_date = str(datetime.now())
    trail.org_id = trail_object.org_id
    trail.trail_uuid = str(f"trail_{uuid4()}")

    # create trail
    db_session.add(trail)
    db_session.commit()
    db_session.refresh(trail)

    return trail


async def get_user_trails(
    request: Request,
    user: PublicUser,
    db_session: Session,
) -> TrailRead:
    statement = select(Trail).where(Trail.user_id == user.id)
    trail = db_session.exec(statement).first()

    if not trail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trail not found"
        )

    statement = select(TrailRun).where(TrailRun.trail_id == trail.id)
    trail_runs = db_session.exec(statement).all()

    trail_runs = [
        TrailRunRead(**trail_run.__dict__, course={}, steps=[], course_total_steps=0)
        for trail_run in trail_runs
    ]

    # Add course object and total activities in a course to trail runs
    for trail_run in trail_runs:
        statement = select(Course).where(Course.id == trail_run.course_id)
        course = db_session.exec(statement).first()
        trail_run.course = course.model_dump() if course else {}

        # Add number of activities (steps) in a course
        statement = select(ChapterActivity).where(
            ChapterActivity.course_id == trail_run.course_id
        )
        course_total_steps = db_session.exec(statement)
        # count number of activities in a this list
        trail_run.course_total_steps = len(course_total_steps.all())

    _populate_trail_runs_steps(db_session, trail_runs)

    trail_read = TrailRead(
        **trail.model_dump(),
        runs=trail_runs,
    )

    return trail_read


async def check_trail_presence(
    org_id: int,
    user_id: int,
    request: Request,
    user: PublicUser,
    db_session: Session,
):
    statement = select(Trail).where(Trail.org_id == org_id, Trail.user_id == user_id)
    trail = db_session.exec(statement).first()

    if not trail:
        trail = await create_user_trail(
            request,
            user,
            TrailCreate(
                org_id=org_id,
                user_id=user.id,
            ),
            db_session,
        )
        return trail

    return trail


async def get_user_trail_with_orgid(
    request: Request, user: PublicUser | AnonymousUser, org_id: int, db_session: Session
) -> TrailRead:

    if isinstance(user, AnonymousUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous users cannot access this endpoint",
        )

    trail = await check_trail_presence(
        org_id=org_id,
        user_id=user.id,
        request=request,
        user=user,
        db_session=db_session,
    )

    statement = select(TrailRun).where(TrailRun.trail_id == trail.id)
    trail_runs = db_session.exec(statement).all()

    trail_runs = [
        TrailRunRead(**trail_run.__dict__, course={}, steps=[], course_total_steps=0)
        for trail_run in trail_runs
    ]

    # Add course object and total activities in a course to trail runs
    for trail_run in trail_runs:
        statement = select(Course).where(Course.id == trail_run.course_id)
        course = db_session.exec(statement).first()
        trail_run.course = course.model_dump() if course else {}

        # Add number of activities (steps) in a course
        statement = select(ChapterActivity).where(
            ChapterActivity.course_id == trail_run.course_id
        )
        course_total_steps = db_session.exec(statement)
        # count number of activities in a this list
        trail_run.course_total_steps = len(course_total_steps.all())

    _populate_trail_runs_steps(db_session, trail_runs)

    trail_read = TrailRead(
        **trail.model_dump(),
        runs=trail_runs,
    )

    return trail_read


async def add_activity_to_trail(
    request: Request,
    user: PublicUser,
    activity_uuid: str,
    db_session: Session,
) -> TrailRead:
    # Look for the activity
    statement = select(Activity).where(Activity.activity_uuid == activity_uuid)
    activity = db_session.exec(statement).first()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found"
        )

    statement = select(Course).where(Course.id == activity.course_id)
    course = db_session.exec(statement).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    trail = await check_trail_presence(
        org_id=course.org_id,
        user_id=user.id,
        request=request,
        user=user,
        db_session=db_session,
    )

    statement = select(TrailRun).where(
        TrailRun.trail_id == trail.id, TrailRun.course_id == course.id, TrailRun.user_id == user.id
    )
    trailrun = db_session.exec(statement).first()

    if not trailrun:
        trailrun = TrailRun(
            trail_id=trail.id if trail.id is not None else 0,
            course_id=course.id if course.id is not None else 0,
            org_id=course.org_id,
            user_id=user.id,
            creation_date=str(datetime.now()),
            update_date=str(datetime.now()),
        )
        db_session.add(trailrun)
        db_session.commit()
        db_session.refresh(trailrun)

    statement = select(TrailStep).where(
        TrailStep.trailrun_id == trailrun.id, TrailStep.activity_id == activity.id, TrailStep.user_id == user.id
    )
    trailstep = db_session.exec(statement).first()

    if not trailstep:
        trailstep = TrailStep(
            trailrun_id=trailrun.id if trailrun.id is not None else 0,
            activity_id=activity.id if activity.id is not None else 0,
            course_id=course.id if course.id is not None else 0,
            trail_id=trail.id if trail.id is not None else 0,
            org_id=course.org_id,
            complete=True,
            teacher_verified=False,
            grade="",
            user_id=user.id,
            creation_date=str(datetime.now()),
            update_date=str(datetime.now()),
        )
        db_session.add(trailstep)
        db_session.commit()
        db_session.refresh(trailstep)

    # Check if all activities in the course are completed and create certificate if so
    if course and course.id:
        await check_course_completion_and_create_certificate(
            request, user.id, course.id, db_session
        )

    statement = select(TrailRun).where(TrailRun.trail_id == trail.id , TrailRun.user_id == user.id)
    trail_runs = db_session.exec(statement).all()

    trail_runs = [
        TrailRunRead(**trail_run.__dict__, course={}, steps=[], course_total_steps=0)
        for trail_run in trail_runs
    ]

    _populate_trail_runs_steps(db_session, trail_runs, user_id=user.id)

    trail_read = TrailRead(
        **trail.model_dump(),
        runs=trail_runs,
    )

    return trail_read

async def remove_activity_from_trail(
    request: Request,
    user: PublicUser,
    activity_uuid: str,
    db_session: Session,
) -> TrailRead:
    # Look for the activity
    statement = select(Activity).where(Activity.activity_uuid == activity_uuid)
    activity = db_session.exec(statement).first()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found"
        )

    statement = select(Course).where(Course.id == activity.course_id)
    course = db_session.exec(statement).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    statement = select(Trail).where(
        Trail.org_id == course.org_id, Trail.user_id == user.id
    )
    trail = db_session.exec(statement).first()

    if not trail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trail not found"
        )

    # Delete the trail step for this activity
    statement = select(TrailStep).where(
        TrailStep.activity_id == activity.id, 
        TrailStep.user_id == user.id,
        TrailStep.trail_id == trail.id
    )
    trail_step = db_session.exec(statement).first()

    if trail_step:
        db_session.delete(trail_step)
        db_session.commit()

    # Get updated trail data
    statement = select(TrailRun).where(TrailRun.trail_id == trail.id, TrailRun.user_id == user.id)
    trail_runs = db_session.exec(statement).all()

    trail_runs = [
        TrailRunRead(**trail_run.__dict__, course={}, steps=[], course_total_steps=0)
        for trail_run in trail_runs
    ]

    _populate_trail_runs_steps(db_session, trail_runs, user_id=user.id)

    trail_read = TrailRead(
        **trail.model_dump(),
        runs=trail_runs,
    )

    return trail_read


async def add_course_to_trail(
    request: Request,
    user: PublicUser,
    course_uuid: str,
    db_session: Session,
) -> TrailRead:
    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = db_session.exec(statement).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # check if run already exists
    statement = select(TrailRun).where(
        TrailRun.course_id == course.id, TrailRun.user_id == user.id
    )
    trailrun = db_session.exec(statement).first()

    if trailrun:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="TrailRun already exists"
        )

    statement = select(Trail).where(
        Trail.org_id == course.org_id, Trail.user_id == user.id
    )
    trail = db_session.exec(statement).first()

    if not trail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trail not found"
        )

    statement = select(TrailRun).where(
        TrailRun.trail_id == trail.id, TrailRun.course_id == course.id, TrailRun.user_id == user.id
    )
    trail_run = db_session.exec(statement).first()

    if not trail_run:
        trail_run = TrailRun(
            trail_id=trail.id if trail.id is not None else 0,
            course_id=course.id if course.id is not None else 0,
            org_id=course.org_id,
            user_id=user.id,
            creation_date=str(datetime.now()),
            update_date=str(datetime.now()),
        )
        db_session.add(trail_run)
        db_session.commit()
        db_session.refresh(trail_run)

    statement = select(TrailRun).where(TrailRun.trail_id == trail.id, TrailRun.user_id == user.id)
    trail_runs = db_session.exec(statement).all()

    trail_runs = [
        TrailRunRead(**trail_run.__dict__, course={}, steps=[], course_total_steps=0)
        for trail_run in trail_runs
    ]

    _populate_trail_runs_steps(db_session, trail_runs, user_id=user.id)

    trail_read = TrailRead(
        **trail.model_dump(),
        runs=trail_runs,
    )

    return trail_read


async def remove_course_from_trail(
    request: Request,
    user: PublicUser,
    course_uuid: str,
    db_session: Session,
) -> TrailRead:
    statement = select(Course).where(Course.course_uuid == course_uuid)
    course = db_session.exec(statement).first()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    statement = select(Trail).where(
        Trail.org_id == course.org_id, Trail.user_id == user.id
    )
    trail = db_session.exec(statement).first()

    if not trail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trail not found"
        )

    statement = select(TrailRun).where(
        TrailRun.trail_id == trail.id, TrailRun.course_id == course.id, TrailRun.user_id == user.id
    )
    trail_run = db_session.exec(statement).first()

    if trail_run:
        db_session.delete(trail_run)
        db_session.commit()

    # Delete all trail steps for this course
    statement = select(TrailStep).where(TrailStep.course_id == course.id, TrailStep.user_id == user.id)
    trail_steps = db_session.exec(statement).all()

    for trail_step in trail_steps:
        db_session.delete(trail_step)
        db_session.commit()

    statement = select(TrailRun).where(TrailRun.trail_id == trail.id, TrailRun.user_id == user.id)
    trail_runs = db_session.exec(statement).all()

    trail_runs = [
        TrailRunRead(**trail_run.__dict__, course={}, steps=[], course_total_steps=0)
        for trail_run in trail_runs
    ]

    _populate_trail_runs_steps(db_session, trail_runs, user_id=user.id)

    trail_read = TrailRead(
        **trail.model_dump(),
        runs=trail_runs,
    )

    return trail_read
