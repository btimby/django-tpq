from django.core.management.base import BaseCommand

# import tpq


class Command(BaseCommand):
    """
    Execute futures.
    """

    help = 'Daemon to execute futures.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        pass
