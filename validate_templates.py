from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError


TEMPLATES_DIRECTORY = Path("app/templates")


def validate_templates() -> int:
    if not TEMPLATES_DIRECTORY.exists():
        print(
            f"ERROR: Template directory not found: "
            f"{TEMPLATES_DIRECTORY.resolve()}"
        )
        return 1

    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIRECTORY))
    )

    template_names = environment.list_templates(
        extensions=["html"]
    )

    if not template_names:
        print("No HTML templates were found.")
        return 0

    print("Validating Jinja2 templates...\n")

    error_count = 0

    for template_name in sorted(template_names):
        try:
            environment.get_template(template_name)
            print(f"OK: {template_name}")

        except TemplateSyntaxError as error:
            error_count += 1
            print(
                f"ERROR: {template_name} "
                f"(line {error.lineno})"
            )
            print(f"       {error.message}")

        except Exception as error:
            error_count += 1
            print(f"ERROR: {template_name}")
            print(f"       {error}")

    print()

    if error_count == 0:
        print(
            f"SUCCESS: All {len(template_names)} "
            f"template(s) are valid."
        )
        return 0

    print(
        f"FAILED: {error_count} template(s) "
        f"contain errors."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(validate_templates())