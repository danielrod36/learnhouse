import pytest
from sqlmodel import Session, SQLModel, create_engine

# Import models
from src.db.users import User
from src.db.trails import Trail
from src.db.organizations import Organization
from src.db.courses.courses import Course
from src.db.trail_runs import TrailRun, TrailRunRead
from src.db.trail_steps import TrailStep

# Import the function to test
from src.services.trail.trail import _populate_trail_runs_steps

# Setup in-memory DB
engine = create_engine("sqlite:///:memory:")
SQLModel.metadata.create_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    with Session(engine) as session:
        yield session

def test_populate_trail_runs_steps(session: Session):
    # Create User & Org
    org = Organization(name="Org", slug="org", email="e@e.com", creation_date="", update_date="")
    session.add(org)
    user = User(username="u", first_name="f", last_name="l", email="e@e.com", creation_date="", update_date="")
    session.add(user)
    session.commit()
    session.refresh(user)
    session.refresh(org)

    # Create Trail, Run, Step, Course
    trail = Trail(org_id=org.id, user_id=user.id, creation_date="", update_date="")
    session.add(trail)

    course = Course(name="C", org_id=org.id, public=True, open_to_contributors=False, creation_date="", update_date="")
    session.add(course)
    session.commit()
    session.refresh(course)

    trail_run = TrailRun(trail_id=trail.id, course_id=course.id, org_id=org.id, user_id=user.id, creation_date="", update_date="")
    session.add(trail_run)
    session.commit()
    session.refresh(trail_run)

    step = TrailStep(trailrun_id=trail_run.id, trail_id=trail.id, course_id=course.id, org_id=org.id, user_id=user.id, activity_id=0, complete=False, teacher_verified=False, grade="", creation_date="", update_date="")
    session.add(step)
    session.commit()

    # Prepare TrailRunRead like object
    tr_read = TrailRunRead(**trail_run.model_dump(), course={}, steps=[], course_total_steps=0)
    # Workaround: ensure ID is propagated if lost during unpacking
    if tr_read.id is None:
        tr_read.id = trail_run.id

    # Call function
    _populate_trail_runs_steps(session, [tr_read], user_id=user.id)

    # Assert
    assert len(tr_read.steps) == 1
    assert tr_read.steps[0].id == step.id
    assert tr_read.steps[0].data['course'].id == course.id
