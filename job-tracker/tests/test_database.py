import os
import tempfile

import pytest

from core.database import JobDatabase
from core.models import JobListing


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = JobDatabase(path)
    yield database
    os.remove(path)


def test_save_new_jobs_inserts_once(db):
    job = JobListing(site="test", title="Project Officer", url="http://x/1")
    new_jobs = db.save_new_jobs([job])
    assert len(new_jobs) == 1
    assert db.count_jobs() == 1


def test_save_new_jobs_dedupes_on_second_run(db):
    job = JobListing(site="test", title="Project Officer", url="http://x/1")
    db.save_new_jobs([job])

    # Simulate the next day's run scraping the same job again
    new_jobs = db.save_new_jobs([job])
    assert len(new_jobs) == 0
    assert db.count_jobs() == 1


def test_different_jobs_both_saved(db):
    job1 = JobListing(site="test", title="Project Officer", url="http://x/1")
    job2 = JobListing(site="test", title="Policy Officer", url="http://x/2")
    new_jobs = db.save_new_jobs([job1, job2])
    assert len(new_jobs) == 2
    assert db.count_jobs() == 2


def test_mark_notified(db):
    job = JobListing(site="test", title="Project Officer", url="http://x/1")
    db.save_new_jobs([job])
    assert len(db.get_unnotified_jobs()) == 1

    db.mark_notified([job])
    assert len(db.get_unnotified_jobs()) == 0
