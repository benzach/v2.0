from core.filters import SearchCriteria, job_matches, filter_jobs
from core.models import JobListing


def make_criteria(**overrides):
    defaults = dict(
        keywords=["project officer"],
        exclude_keywords=["unpaid"],
        locations=["london"],
        min_salary_gbp=None,
        max_age_days=14,
    )
    defaults.update(overrides)
    return SearchCriteria(**defaults)


def test_matches_on_keyword_and_location():
    job = JobListing(
        site="test", title="Project Officer", url="http://x/1", location="London"
    )
    assert job_matches(job, make_criteria())


def test_rejects_missing_keyword():
    job = JobListing(site="test", title="Chef", url="http://x/2", location="London")
    assert not job_matches(job, make_criteria())


def test_rejects_wrong_location():
    job = JobListing(
        site="test", title="Project Officer", url="http://x/3", location="Manchester"
    )
    assert not job_matches(job, make_criteria())


def test_rejects_excluded_keyword():
    job = JobListing(
        site="test",
        title="Project Officer",
        url="http://x/4",
        location="London",
        description="This is an unpaid internship",
    )
    assert not job_matches(job, make_criteria())


def test_empty_locations_disables_location_filter():
    job = JobListing(
        site="test", title="Project Officer", url="http://x/5", location="Cardiff"
    )
    assert job_matches(job, make_criteria(locations=[]))


def test_salary_filter():
    criteria = make_criteria(locations=[], min_salary_gbp=30000)
    low = JobListing(
        site="test", title="Project Officer", url="http://x/6", salary="£25,000"
    )
    high = JobListing(
        site="test", title="Project Officer", url="http://x/7", salary="£35,000"
    )
    unparsed = JobListing(
        site="test", title="Project Officer", url="http://x/8", salary="Competitive"
    )
    assert not job_matches(low, criteria)
    assert job_matches(high, criteria)
    assert job_matches(unparsed, criteria)  # unparsed salaries are kept, not dropped


def test_filter_jobs_returns_only_matches():
    criteria = make_criteria()
    jobs = [
        JobListing(site="test", title="Project Officer", url="http://x/9", location="London"),
        JobListing(site="test", title="Chef", url="http://x/10", location="London"),
    ]
    result = filter_jobs(jobs, criteria)
    assert len(result) == 1
    assert result[0].title == "Project Officer"
