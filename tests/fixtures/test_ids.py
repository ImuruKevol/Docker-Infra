import datetime
import os
import uuid


def make_test_run_id():
    return os.environ.get("DOCKER_INFRA_TEST_RUN_ID") or str(uuid.uuid4())


def make_namespace(test_run_id=None, run_date=None):
    test_run_id = test_run_id or make_test_run_id()
    run_date = run_date or datetime.date.today()
    if isinstance(run_date, datetime.datetime):
        run_date = run_date.date()
    if isinstance(run_date, str):
        date_part = run_date.replace("-", "")
    else:
        date_part = run_date.strftime("%Y%m%d")
    suffix = test_run_id.replace("-", "")[:12]
    return f"di_test_{date_part}_{suffix}"


def make_resource_names(test_run_id=None, run_date=None, staging_zone="example.test"):
    test_run_id = test_run_id or make_test_run_id()
    namespace = make_namespace(test_run_id, run_date=run_date)
    short_id = test_run_id.replace("-", "")[:12]
    date_part = namespace.split("_")[2]
    return {
        "test_run_id": test_run_id,
        "namespace": namespace,
        "stack": f"di_test_{short_id}",
        "service_namespace": f"di_test_{short_id}",
        "domain": f"di-test-{short_id}.{staging_zone}",
        "image_tag": f"test-{date_part}-{short_id}",
        "job_label": f"test_run_id={test_run_id}",
        "file_root": f"{namespace}",
    }
