from django.core.management.base import BaseCommand
from users.models import DashboardIcon, IconClass, ColorTheme, User
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Creates default dashboard icons for AICC-IntelliDoc and LLM Evaluation.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Attempting to create default dashboard icons...'))

        # Ensure a user exists to assign ownership
        # For simplicity, we'll use the first superuser found, or create a dummy one if none exist.
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                # Previously this created admin@example.com with the literal password
                # 'adminpassword'. That is a published credential on a system that may
                # be internet-facing, so a superuser is no longer created implicitly.
                # scripts/bootstrap.sh creates one with a generated password instead.
                self.stdout.write(self.style.ERROR(
                    'No superuser exists. Refusing to create one with a default password.\n'
                    'Create an administrator first, then re-run this command:\n'
                    '  ./scripts/bootstrap.sh          (generates a password for you)\n'
                    '  or: python manage.py createsuperuser'
                ))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to get admin user: {e}'))
            return

        icons_to_create = [
            {
                'name': 'AICC-IntelliDoc',
                'description': 'AI-powered document processing and analysis',
                'icon_class': IconClass.FILE_TEXT,
                'color': ColorTheme.OXFORD_BLUE,
                'route': '/features/intellidoc', # Corrected route based on user feedback
                'order': 1,
            },
            {
                'name': 'LLM Evaluation',
                'description': 'Evaluate and compare Large Language Models',
                'icon_class': IconClass.ROBOT,
                'color': ColorTheme.EMERALD,
                'route': '/features/llm-eval', # Corrected route
                'order': 2,
            },
        ]

        for icon_data in icons_to_create:
            try:
                icon, created = DashboardIcon.objects.get_or_create(
                    name=icon_data['name'],
                    defaults=icon_data
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Successfully created icon: {icon.name}'))
                else:
                    # Icon already exists, update its attributes
                    updated = False
                    for key, value in icon_data.items():
                        if getattr(icon, key) != value:
                            setattr(icon, key, value)
                            updated = True
                    if updated:
                        icon.save()
                        self.stdout.write(self.style.SUCCESS(f'Successfully updated icon: {icon.name}'))
                    else:
                        self.stdout.write(self.style.NOTICE(f'Icon already exists, no update needed: {icon.name}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to create icon {icon_data['name']}: {e}'))

        self.stdout.write(self.style.SUCCESS('Default dashboard icon creation process completed.'))
        self.stdout.write(self.style.WARNING('Please confirm the correct routes for AICC-IntelliDoc (create project page) and LLM Evaluation.'))
