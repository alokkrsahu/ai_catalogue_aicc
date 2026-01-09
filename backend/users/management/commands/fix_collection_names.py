"""
Django management command to fix collection name mismatches between
ProjectVectorCollection database records and actual Milvus collections.
"""
from django.core.management.base import BaseCommand
from django_milvus_search import MilvusSearchService
from pymilvus import utility
from users.models import IntelliDocProject, ProjectVectorCollection
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix collection name mismatches between database and Milvus'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=str,
            help='Specific project ID to fix (optional)',
        )
        parser.add_argument(
            '--check-all',
            action='store_true',
            help='Check all projects for mismatches',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        check_all = options.get('check_all', False)
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))

        # Connect to Milvus
        try:
            service = MilvusSearchService()
            all_milvus_collections = set(utility.list_collections())
            self.stdout.write(self.style.SUCCESS(f'✅ Connected to Milvus. Found {len(all_milvus_collections)} collections'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed to connect to Milvus: {e}'))
            return

        if project_id:
            # Fix specific project
            self.fix_project(project_id, all_milvus_collections, dry_run)
        elif check_all:
            # Check all projects
            self.check_all_projects(all_milvus_collections, dry_run)
        else:
            self.stdout.write(self.style.ERROR('Please specify --project-id or --check-all'))
            self.stdout.write(self.style.WARNING('Example: python manage.py fix_collection_names --project-id b2d02e08-c494-4c42-8502-32154124dabe'))

    def fix_project(self, project_id, all_milvus_collections, dry_run=False):
        """Fix collection name for a specific project"""
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
            self.stdout.write(f'\n📋 Project: {project.name} ({project_id})')

            if not hasattr(project, 'vector_collection'):
                self.stdout.write(self.style.WARNING('⚠️  No ProjectVectorCollection record found'))
                return

            collection = project.vector_collection
            stored_name = collection.collection_name
            generated_name = project.generate_collection_name()

            self.stdout.write(f'   Stored name: {stored_name}')
            self.stdout.write(f'   Generated name: {generated_name}')

            # Find matching collection in Milvus
            matching_collections = []
            for milvus_name in all_milvus_collections:
                # Check if it matches the project ID
                project_id_suffix = str(project.project_id).replace('-', '_')
                if project_id_suffix in milvus_name:
                    matching_collections.append(milvus_name)

            if not matching_collections:
                self.stdout.write(self.style.ERROR(f'   ❌ No matching collection found in Milvus for project ID'))
                return

            if len(matching_collections) == 1:
                actual_name = matching_collections[0]
                if stored_name != actual_name:
                    self.stdout.write(self.style.WARNING(f'   ⚠️  MISMATCH DETECTED!'))
                    self.stdout.write(f'   Actual Milvus name: {actual_name}')

                    if not dry_run:
                        collection.collection_name = actual_name
                        collection.save()
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Updated collection_name to: {actual_name}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'   [DRY RUN] Would update to: {actual_name}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Collection name matches Milvus'))
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Found {len(matching_collections)} matching collections:'))
                for coll in matching_collections:
                    self.stdout.write(f'      - {coll}')
                self.stdout.write(self.style.ERROR('   ❌ Cannot auto-fix: multiple matches found'))

        except IntelliDocProject.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Project not found: {project_id}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error fixing project: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())

    def check_all_projects(self, all_milvus_collections, dry_run=False):
        """Check all projects for collection name mismatches"""
        self.stdout.write('\n🔍 Checking all projects for collection name mismatches...\n')

        projects = IntelliDocProject.objects.all()
        mismatches_found = 0
        fixed_count = 0

        for project in projects:
            if not hasattr(project, 'vector_collection'):
                continue

            collection = project.vector_collection
            stored_name = collection.collection_name

            # Find matching collection in Milvus
            project_id_suffix = str(project.project_id).replace('-', '_')
            matching_collections = [
                name for name in all_milvus_collections
                if project_id_suffix in name
            ]

            if not matching_collections:
                # Collection doesn't exist in Milvus - might be expected if not processed
                continue

            if len(matching_collections) == 1:
                actual_name = matching_collections[0]
                if stored_name != actual_name:
                    mismatches_found += 1
                    self.stdout.write(f'⚠️  MISMATCH: {project.name} ({project.project_id})')
                    self.stdout.write(f'   Stored: {stored_name}')
                    self.stdout.write(f'   Actual: {actual_name}')

                    if not dry_run:
                        collection.collection_name = actual_name
                        collection.save()
                        fixed_count += 1
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Fixed'))
                    else:
                        self.stdout.write(self.style.WARNING(f'   [DRY RUN] Would fix'))
                    self.stdout.write('')

        self.stdout.write('\n' + '='*60)
        if mismatches_found == 0:
            self.stdout.write(self.style.SUCCESS('✅ No mismatches found!'))
        else:
            if dry_run:
                self.stdout.write(self.style.WARNING(f'🔍 Found {mismatches_found} mismatch(es) (DRY RUN)'))
            else:
                self.stdout.write(self.style.SUCCESS(f'✅ Fixed {fixed_count} mismatch(es)'))

