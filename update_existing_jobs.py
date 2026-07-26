from app.db.database import SessionLocal
from app.db.models import Job


def update_jobs():
    db = SessionLocal()

    try:
        test_job = (
            db.query(Job)
            .filter(Job.name == "Test Automation Job")
            .first()
        )

        if test_job:
            test_job.description = "Runs the sample automation job."
            test_job.script_type = "python"
            test_job.script_path = (
                "app.jobs.sample_job:run_sample_job"
            )

            print("Updated: Test Automation Job")

        health_job = (
            db.query(Job)
            .filter(Job.name == "Health Check Job")
            .first()
        )

        if health_job:
            health_job.description = (
                "Checks local computer and Python environment details."
            )
            health_job.script_type = "python"
            health_job.script_path = (
                "app.jobs.health_check_job:run_health_check_job"
            )

            print("Updated: Health Check Job")

        db.commit()

        print("Existing jobs updated successfully.")

    except Exception as error:
        db.rollback()
        print(f"Update failed: {error}")

    finally:
        db.close()


if __name__ == "__main__":
    update_jobs()