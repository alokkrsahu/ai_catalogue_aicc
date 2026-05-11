"""
Diagnostic management command for the public-chat auth gate.

The gate (``deployment_views._enforce_public_chat_auth``) has FOUR rules.
Rule 1 — ``_is_trusted_admin_app_request`` — bypasses the password check
when the request's Origin or Referer matches an entry in
``settings.CORS_ALLOWED_ORIGINS``. The intent is to let the in-app admin
chatbot iframe (loaded from the admin app's own host) skip the password
flow that's designed for external public-chat URL users.

This works ONLY if the admin app and the public-chat URL are served from
DIFFERENT origins. If both surfaces share a host (e.g., both on
``https://aicc.uksouth.cloudapp.azure.com``) AND that host appears in
``CORS_ALLOWED_ORIGINS``, then external public-chat users are also
same-origin to that host, the iframe's XHRs carry the same Origin header
admins do, Rule 1 fires for them too, and the password gate is bypassable.

This command prints a verdict so an operator can confirm the production
CORS configuration is safe.
"""
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Audit CORS_ALLOWED_ORIGINS for the public-chat auth-gate "
        "Rule-1 bypass concern."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--public-chat-host',
            default=None,
            help=(
                'The hostname (with scheme) of the public chat URL, e.g. '
                '"https://aicc.uksouth.cloudapp.azure.com". If omitted, '
                'no host-collision check is performed and the command just '
                'prints the current CORS list.'
            ),
        )

    def handle(self, *args, **opts):
        public_host = opts.get('public_chat_host')
        cors = list(getattr(settings, 'CORS_ALLOWED_ORIGINS', []) or [])
        cors_regexes = list(getattr(settings, 'CORS_ALLOWED_ORIGIN_REGEXES', []) or [])
        allow_all = bool(getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False))

        self.stdout.write(self.style.NOTICE("=== CORS configuration ==="))
        self.stdout.write(f"CORS_ALLOW_ALL_ORIGINS = {allow_all}")
        self.stdout.write(f"CORS_ALLOWED_ORIGINS ({len(cors)} entries):")
        for o in cors:
            self.stdout.write(f"  - {o}")
        if cors_regexes:
            self.stdout.write(f"CORS_ALLOWED_ORIGIN_REGEXES ({len(cors_regexes)} entries):")
            for r in cors_regexes:
                self.stdout.write(f"  - {r}")

        if allow_all:
            self.stdout.write(self.style.ERROR(
                "\n❌ CORS_ALLOW_ALL_ORIGINS=True — every origin passes the "
                "Rule-1 admin-app bypass. The password gate at /chat/<id>/ "
                "is architecturally bypassable. Do NOT run with this in "
                "production."
            ))
            return

        if not public_host:
            self.stdout.write(self.style.WARNING(
                "\nNo --public-chat-host provided; skipping host-collision check.\n"
                "Re-run with --public-chat-host=<scheme>://<host> to verify "
                "the auth gate posture."
            ))
            return

        # Normalise.
        try:
            target = urlparse(public_host)
            target_origin = (
                f"{target.scheme.lower()}://{target.netloc.lower()}"
                .rstrip('/')
            )
        except Exception:
            self.stdout.write(self.style.ERROR(
                f"❌ Could not parse --public-chat-host={public_host!r}"
            ))
            return

        normalized_cors = {
            (c or '').strip().rstrip('/').lower() for c in cors if c
        }
        collides = target_origin in normalized_cors

        self.stdout.write(self.style.NOTICE(
            f"\n=== Public-chat host check: {target_origin} ==="
        ))
        if collides:
            self.stdout.write(self.style.ERROR(
                f"❌ The public-chat host {target_origin} IS listed in "
                "CORS_ALLOWED_ORIGINS.\n"
                "   This means external users at /chat/<id> hit the same "
                "Rule-1 admin-app\n"
                "   bypass that the in-app iframe uses, and the password "
                "form on the\n"
                "   public chat page is UI-only theatre — it does not "
                "actually gate the\n"
                "   /api/workflow-deploy/<id>/embed/, /upload-file/, or "
                "/stream/ endpoints.\n\n"
                "   Fix options:\n"
                "   (a) Remove the public-chat host from CORS_ALLOWED_ORIGINS "
                "(the in-app\n"
                "       admin will need a separate origin, e.g. an "
                "admin-only subdomain).\n"
                "   (b) Tighten _is_trusted_admin_app_request to additionally "
                "require an\n"
                "       admin JWT/session cookie, not just the matching "
                "Origin/Referer."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {target_origin} is NOT in CORS_ALLOWED_ORIGINS.\n"
                "   External users at /chat/<id> will fall through to "
                "Rule 4 (cookie\n"
                "   validation), so the password gate is enforced as "
                "intended."
            ))
