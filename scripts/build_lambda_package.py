import os
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
build_dir = root / "build" / "lambda"
requirements_file = root / "build" / "lambda-requirements.txt"
output_file = root / "dist" / "vpc_api_lambda.zip"


def main() -> None:
    shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--output-file",
            str(requirements_file),
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python-platform",
            "x86_64-manylinux2014",
            "--python-version",
            "3.11",
            "--target",
            str(build_dir),
            "--requirements",
            str(requirements_file),
        ],
        cwd=root,
        check=True,
    )

    shutil.copytree(
        root / "src" / "vpc_api",
        build_dir / "vpc_api",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    for cache_dir in build_dir.rglob("__pycache__"):
        shutil.rmtree(cache_dir)

    archive_timestamp = 946684800
    for path in [build_dir, *build_dir.rglob("*")]:
        os.utime(path, (archive_timestamp, archive_timestamp))

    shutil.make_archive(
        str(output_file.with_suffix("")),
        "zip",
        build_dir,
    )

    print(f"Built {output_file.relative_to(root)}")


if __name__ == "__main__":
    main()
