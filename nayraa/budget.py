from pathlib import PurePath

TOKEN_BUDGET = 280_000
FANOUT_THRESHOLD = 30
CALL_SITE_CONTEXT_LINES = 15
MAX_CANDIDATE_FINDINGS = 8
MAX_FINAL_FINDINGS = 3
MIN_CONFIDENCE = 0.6
REFUTE_WORKERS = 4
FINDER_TOOL_CALLS = 40
REFUTE_TOOL_CALLS = 15

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
