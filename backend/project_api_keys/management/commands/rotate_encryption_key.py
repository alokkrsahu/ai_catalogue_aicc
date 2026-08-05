"""
Rotate PROJECT_API_KEY_ENCRYPTION_KEY without losing data.

Every ProjectAPIKey.encrypted_api_key and MCPServerCredential.encrypted_credentials
is encrypted with a key derived from PROJECT_API_KEY_ENCRYPTION_KEY plus the
project id (PBKDF2, project id as salt — see project_api_keys/encryption.py).
Changing the base key therefore makes every stored secret undecryptable unless
each row is decrypted with the old key and re-encrypted with the new one.

This command does that, in one transaction, verifying every row before it commits:

    # 1. dry run — proves every row can be decrypted with the old key and that
    #    re-encryption round-trips, then rolls back
    python manage.py rotate_encryption_key --new-key "<new>" --dry-run

    # 2. apply
    python manage.py rotate_encryption_key --new-key "<new>" --apply

The old key is read from the environment (PROJECT_API_KEY_ENCRYPTION_KEY) unless
--old-key is given. Only after this succeeds should the environment be updated to
the new key.

Safety properties:
  * Refuses to run unless EVERY row decrypts with the old key. A single failure
    aborts before anything is written, so a partially-rotated table is impossible.
  * Verifies each new ciphertext decrypts back to the exact original plaintext
    using a fresh service bound to the new key.
  * Runs inside transaction.atomic(); --dry-run raises at the end to roll back.
  * Never logs plaintext secrets — only lengths and fingerprints.
"""

import base64
import hashlib
from typing import Dict, List, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from project_api_keys.encryption import ProjectAPIKeyEncryption
from users.models import MCPServerCredential, ProjectAPIKey


class _Rollback(Exception):
    """Internal sentinel used to roll back a dry run."""


def _fingerprint(value: str) -> str:
    """Short, non-reversible fingerprint so operators can compare before/after
    without the plaintext ever being printed."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


class _KeyedEncryption(ProjectAPIKeyEncryption):
    """ProjectAPIKeyEncryption bound to an explicit base key rather than the
    environment, so old and new keys can be used side by side in one process."""

    def __init__(self, base_key_str: str):
        try:
            self.base_key = base64.urlsafe_b64decode(base_key_str.encode())
        except Exception as exc:  # noqa: BLE001 - surfaced as a CommandError
            raise CommandError(f"Invalid key format (expected urlsafe base64): {exc}")
        if len(self.base_key) != 32:
            raise CommandError(
                f"Key must decode to 32 bytes, got {len(self.base_key)}. "
                "Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )


class Command(BaseCommand):
    help = "Re-encrypt stored project API keys and MCP credentials under a new base key."

    def add_arguments(self, parser):
        parser.add_argument("--new-key", required=True, help="New base key (urlsafe base64, 32 bytes).")
        parser.add_argument(
            "--old-key",
            default=None,
            help="Old base key. Defaults to PROJECT_API_KEY_ENCRYPTION_KEY from the environment.",
        )
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--dry-run", action="store_true", help="Verify everything, then roll back.")
        group.add_argument("--apply", action="store_true", help="Commit the rotation.")

    def handle(self, *args, **options):
        new_key = options["new_key"].strip()
        old_key = options["old_key"]
        apply_changes = options["apply"]

        if old_key is None:
            import os

            old_key = os.environ.get("PROJECT_API_KEY_ENCRYPTION_KEY")
            if not old_key:
                raise CommandError(
                    "PROJECT_API_KEY_ENCRYPTION_KEY is not set and --old-key was not given."
                )
            source = "environment"
        else:
            source = "--old-key"
        old_key = old_key.strip()

        if old_key == new_key:
            raise CommandError("New key is identical to the old key — nothing to rotate.")

        old_svc = _KeyedEncryption(old_key)
        new_svc = _KeyedEncryption(new_key)

        self.stdout.write(self.style.MIGRATE_HEADING("Encryption key rotation"))
        self.stdout.write(f"  old key source : {source}")
        self.stdout.write(f"  mode           : {'APPLY' if apply_changes else 'DRY RUN'}")

        api_keys = list(ProjectAPIKey.objects.select_related("project").all())
        mcp_creds = list(MCPServerCredential.objects.select_related("project").all())
        self.stdout.write(f"  ProjectAPIKey rows       : {len(api_keys)}")
        self.stdout.write(f"  MCPServerCredential rows : {len(mcp_creds)}")

        if not api_keys and not mcp_creds:
            self.stdout.write(
                self.style.WARNING(
                    "\nNothing is encrypted with this key — rotation is a no-op at the data "
                    "layer. Update the environment variable and restart."
                )
            )
            return

        # ---- Stage 1: decrypt everything with the old key. No writes yet. ----
        self.stdout.write("\nStage 1 — decrypting with the old key")
        plaintexts: Dict[Tuple[str, int], object] = {}
        failures: List[str] = []

        for row in api_keys:
            pid = str(row.project.project_id)
            try:
                plaintexts[("api", row.pk)] = old_svc.decrypt_api_key(pid, row.encrypted_api_key)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"ProjectAPIKey pk={row.pk} project={row.project.name!r} "
                    f"provider={row.provider_type}: {exc}"
                )

        for row in mcp_creds:
            pid = str(row.project.project_id)
            try:
                plaintexts[("mcp", row.pk)] = old_svc.decrypt_mcp_credentials(
                    pid, row.encrypted_credentials
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    f"MCPServerCredential pk={row.pk} project={row.project.name!r} "
                    f"type={row.server_type}: {exc}"
                )

        if failures:
            self.stderr.write(self.style.ERROR(f"\n{len(failures)} row(s) failed to decrypt:"))
            for f in failures:
                self.stderr.write(f"  - {f}")
            raise CommandError(
                "Aborting without writing anything. Every row must decrypt with the old key "
                "before rotation can proceed. If some rows were encrypted under a different "
                "key, rotate them separately with --old-key."
            )

        self.stdout.write(self.style.SUCCESS(f"  all {len(plaintexts)} row(s) decrypted"))

        # ---- Stage 2: re-encrypt and verify, inside a transaction. ----
        self.stdout.write("\nStage 2 — re-encrypting with the new key and verifying")
        rotated = 0
        try:
            with transaction.atomic():
                for row in api_keys:
                    pid = str(row.project.project_id)
                    original = plaintexts[("api", row.pk)]
                    new_ct = new_svc.encrypt_api_key(pid, original)
                    # Verify with a fresh service instance bound to the new key.
                    check = _KeyedEncryption(new_key).decrypt_api_key(pid, new_ct)
                    if check != original:
                        raise CommandError(
                            f"Verification failed for ProjectAPIKey pk={row.pk} — "
                            "re-encrypted value does not round-trip. Nothing committed."
                        )
                    row.encrypted_api_key = new_ct
                    row.save(update_fields=["encrypted_api_key"])
                    rotated += 1
                    self.stdout.write(
                        f"  ok  ProjectAPIKey pk={row.pk:<4} {row.project.name[:26]:28} "
                        f"{row.provider_type:9} fp={_fingerprint(original)}"
                    )

                for row in mcp_creds:
                    pid = str(row.project.project_id)
                    original = plaintexts[("mcp", row.pk)]
                    new_ct = new_svc.encrypt_mcp_credentials(pid, original)
                    check = _KeyedEncryption(new_key).decrypt_mcp_credentials(pid, new_ct)
                    if check != original:
                        raise CommandError(
                            f"Verification failed for MCPServerCredential pk={row.pk}. "
                            "Nothing committed."
                        )
                    row.encrypted_credentials = new_ct
                    row.save(update_fields=["encrypted_credentials"])
                    rotated += 1
                    self.stdout.write(
                        f"  ok  MCPServerCredential pk={row.pk:<4} {row.project.name[:26]:28} "
                        f"{row.server_type}"
                    )

                if not apply_changes:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDRY RUN passed — {rotated} row(s) would rotate cleanly. Rolled back; "
                    "nothing was written."
                )
            )
            self.stdout.write("Re-run with --apply, then set the new key in the environment.")
            return

        self.stdout.write(self.style.SUCCESS(f"\nRotated {rotated} row(s) and committed."))
        self.stdout.write(
            self.style.WARNING(
                "IMPORTANT: the database now holds ciphertext for the NEW key. Update "
                "PROJECT_API_KEY_ENCRYPTION_KEY in .env and restart the backend before "
                "anything tries to read these rows."
            )
        )
