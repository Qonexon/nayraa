from pathlib import PurePath

MAX_FINAL_FINDINGS = 3

MAX_SHAPE_OBJECTIONS = 3
MIN_SHAPE_CONFIDENCE = 0.6
JUSTIFY_WORKERS = 3
MAX_SHAPE_DIRECTORIES = 40
MAX_SHAPE_COMMITS = 40

EXCLUDE_GLOBS = [
    "**/migrations/**",
    "**/alembic/**",
    "**/node_modules/**",
    "**/vendor/**",
    "**/.venv/**",
    "**/venv/**",
    "**/dist/**",
    "**/build/**",
    "**/generated/**",
    "**/__snapshots__/**",
    "**/fixtures/**",
    "**/testdata/**",
    "**/*.lock",
    "**/*.snap",
    "**/*.min.js",
    "**/*.map",
    "**/*_pb2.py",
    "**/*_pb2_grpc.py",
    "**/package-lock.json",
    "**/yarn.lock",
    "**/pnpm-lock.yaml",
    "**/poetry.lock",
]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def is_excluded(path: str) -> bool:
    pp = PurePath(path)
    for pattern in EXCLUDE_GLOBS:
        if pp.match(pattern):
            return True
    return False
