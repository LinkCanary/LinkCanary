"""Migration report verification.

Cross-references a migration-report.json (open standard v1.0) against what
actually resolves on the destination site. Companion to any migration tool
(e.g. Portage) and to ``portage slug-audit``: slug-audit generates the
redirect rules, LinkCanary proves they landed.

The verification contract is defined in the Migration Report Schema spec
(cli/docs/migration-report-schema.md in the portage repo, §11):

  - ``migrated``        destination must resolve 2xx
  - ``redirected``      source must redirect (3xx) and land on 2xx;
                        destination must resolve 2xx
  - ``quarantined`` / ``excluded``  source must be gone (4xx/5xx);
                        if it still resolves 2xx that is an alert
  - ``failed``          no verdict — needs human review

Outcome vocabulary: verified, missing, redirect_missing, unexpected_live,
collision, review.
"""

import json
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from .checker import LinkChecker

VERIFIED = 'verified'
MISSING = 'missing'
REDIRECT_MISSING = 'redirect_missing'
UNEXPECTED_LIVE = 'unexpected_live'
COLLISION = 'collision'
REVIEW = 'review'

VALID_RECORD_STATUSES = ('migrated', 'redirected', 'quarantined', 'failed', 'excluded')
REQUIRED_HEADER_FIELDS = (
    'version', 'generated_by', 'generated_at',
    'destination_base_url', 'destination_platform', 'records',
)
REQUIRED_RECORD_FIELDS = (
    'source_platform', 'source_url', 'destination_path',
    'status', 'images_rehosted', 'links_rewritten',
)


class MigrationReportError(ValueError):
    """The migration-report.json does not conform to the v1.0 standard."""


def validate_report(report) -> None:
    """Structurally validate a migration-report.json (v1.0 standard)."""
    if not isinstance(report, dict):
        raise MigrationReportError('migration report must be a JSON object')
    for field in REQUIRED_HEADER_FIELDS:
        if field not in report:
            raise MigrationReportError(f'missing required header field: {field}')
    if report.get('version') != '1.0':
        raise MigrationReportError(
            f'unsupported schema version: {report.get("version")!r} (expected "1.0")'
        )
    if not isinstance(report.get('records'), list):
        raise MigrationReportError('records must be an array')
    for i, rec in enumerate(report['records']):
        for field in REQUIRED_RECORD_FIELDS:
            if field not in rec:
                raise MigrationReportError(f'record {i}: missing required field: {field}')
        if rec.get('status') not in VALID_RECORD_STATUSES:
            raise MigrationReportError(
                f'record {i}: unknown status {rec.get("status")!r}'
            )
        dest_path = rec.get('destination_path')
        if dest_path is not None and not str(dest_path).startswith('/'):
            raise MigrationReportError(
                f'record {i}: destination_path must start with "/"'
            )


def load_migration_report(path: str) -> dict:
    """Load and validate a migration-report.json from disk."""
    with open(path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    validate_report(report)
    return report


@dataclass
class VerificationRow:
    source_url: str
    destination_url: str
    record_status: str
    verification: str
    observed_status: int
    final_url: str
    detail: str


class MigrationVerifier:
    """Verifies a migration report against the live destination site."""

    def __init__(self, checker: LinkChecker):
        self.checker = checker

    def verify(self, report: dict, site: Optional[str] = None) -> list[VerificationRow]:
        base = (site or report.get('destination_base_url') or '').rstrip('/')
        records = report.get('records', [])

        # Collision detection: two records landing on one destination path.
        dest_counts: dict[str, int] = {}
        for rec in records:
            dp = rec.get('destination_path')
            if dp:
                dest_counts[dp] = dest_counts.get(dp, 0) + 1

        rows: list[VerificationRow] = []
        for rec in records:
            source_url = rec.get('source_url') or ''
            dest_path = rec.get('destination_path')
            dest_url = self._dest_url(base, dest_path)
            status = rec.get('status')

            if dest_path and dest_counts[dest_path] > 1:
                rows.append(VerificationRow(
                    source_url=source_url,
                    destination_url=dest_url,
                    record_status=status,
                    verification=COLLISION,
                    observed_status=0,
                    final_url='',
                    detail=f'destination path {dest_path} is shared by '
                           f'{dest_counts[dest_path]} records — content collision',
                ))
                continue

            if status in ('migrated', 'redirected'):
                rows.append(self._verify_expected(dest_url, source_url, status, rec))
            elif status in ('quarantined', 'excluded'):
                rows.append(self._verify_gone(source_url, status))
            else:  # failed — needs review, not a verdict
                rows.append(VerificationRow(
                    source_url=source_url,
                    destination_url=dest_url,
                    record_status=status,
                    verification=REVIEW,
                    observed_status=0,
                    final_url='',
                    detail='failed record — review before deploying redirects',
                ))
        return rows

    # ── helpers ──────────────────────────────────────────────────────────

    def _verify_expected(self, dest_url: str, source_url: str, status: str, rec: dict) -> VerificationRow:
        """migrated / redirected: the destination must resolve 2xx."""
        if not dest_url:
            return VerificationRow(source_url, '', status, MISSING, 0, '',
                                   'no destination path recorded')
        dest = self.checker.check_link(dest_url)
        if 200 <= dest.status_code < 300:
            verification = VERIFIED
            detail = f'destination {dest_url} → {dest.status_code}'
        else:
            verification = MISSING
            detail = f'destination {dest_url} → {dest.status_code} {dest.error}'.strip()

        # redirected records additionally declare the source redirects to it.
        if status == 'redirected' and source_url:
            src = self.checker.check_link(source_url)
            if not src.is_redirect or not (200 <= src.status_code < 300):
                verification = REDIRECT_MISSING
                chain = src.redirect_chain_formatted or f'final status {src.status_code}'
                detail = f'source {source_url} does not redirect as declared ({chain})'

        return VerificationRow(source_url, dest_url, status, verification,
                               dest.status_code, dest.final_url, detail)

    def _verify_gone(self, source_url: str, status: str) -> VerificationRow:
        """quarantined / excluded: the source must be gone (4xx/5xx)."""
        if not source_url:
            return VerificationRow('', '', status, VERIFIED, 0, '',
                                   'no source URL recorded — nothing to check')
        src = self.checker.check_link(source_url)
        if src.status_code and 400 <= src.status_code < 600:
            verification = VERIFIED
            detail = f'source {source_url} → {src.status_code} (gone as expected)'
        elif src.status_code and 200 <= src.status_code < 300:
            verification = UNEXPECTED_LIVE
            detail = f'source {source_url} still resolves {src.status_code}'
        else:
            # Redirect or unreachable — either way not provably gone.
            verification = UNEXPECTED_LIVE
            tail = src.error or (src.redirect_chain_formatted or f'status {src.status_code}')
            detail = f'source {source_url} → {tail}'
        return VerificationRow(source_url, '', status, verification,
                               src.status_code, src.final_url, detail)

    @staticmethod
    def _dest_url(base: str, dest_path: Optional[str]) -> str:
        if not dest_path or not base:
            return ''
        return urljoin(base + '/', dest_path.lstrip('/'))


def summarize(rows: list[VerificationRow]) -> dict[str, int]:
    """Per-outcome counts for the console summary."""
    counts = {v: 0 for v in (VERIFIED, MISSING, REDIRECT_MISSING,
                             UNEXPECTED_LIVE, COLLISION, REVIEW)}
    for row in rows:
        counts[row.verification] = counts.get(row.verification, 0) + 1
    return counts


def verification_csv(rows: list[VerificationRow]) -> str:
    """Render the verification as a CSV string (migration-verification.csv)."""
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'source_url', 'destination_url', 'record_status', 'verification',
        'observed_status', 'final_url', 'detail',
    ])
    for row in rows:
        writer.writerow([
            row.source_url, row.destination_url, row.record_status,
            row.verification, row.observed_status, row.final_url, row.detail,
        ])
    return buffer.getvalue()
