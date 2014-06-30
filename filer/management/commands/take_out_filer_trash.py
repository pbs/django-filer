import sys
from datetime import datetime, timedelta
from optparse import make_option

# make sure cms is loaded first
import cms
from django.core.management.base import BaseCommand
from filer.models import File, Folder
from filer.settings import FILER_TRASH_CLEAN_INTERVAL


INVALID_AGE = sys.maxsize


def _get_as_int(int_str, _min, _max):
    '''Try to parse given string as a bounded int'''
    try:
        value = int(int_str)
        if _min < value < _max:
            return value
        return INVALID_AGE
    except ValueError:
        return INVALID_AGE


def _parse_age(age):
    """ Transforms a string like $number_d$number_h$number_m into seconds.
        In case input is invalid, returns INVALID_AGE
        The maximum age is '366d23h59m' (for practical reasons)

        Examples of valid input:
        '3d4h30m', '3d', '30m20d10h' (order doesn't matter)
        Examples of invalid input:
        '30', '3d1', '2d30m30m20h'

        In case one of the values for a certain time unit is out of bounds,
        the input string is considered invalid:
        '30d180h30m', '367d'

        In case one of the values for certain time unit is not an int,
        the input string is considered invalid:
        '2.5d30m', '2.0d'

        This method does not make unit conversions
    """
    if not age:
        return INVALID_AGE
    splitted_age = {'d': '', 'h': '', 'm': ''}
    i = len(age) - 1
    key = age[i]
    if not key in splitted_age:
        # input string must end in a time unit ('3d')
        return INVALID_AGE
    while i > 0:
        i -= 1
        crt = age[i]
        if splitted_age.get(crt, None) == '':
            key = crt
            continue
        elif crt in splitted_age:
            # invalid input string (multiple "islands" of same time unit)
            return INVALID_AGE
        splitted_age[key] += crt

    days = _get_as_int(splitted_age.get('d', '0')[::-1], 0, 366)
    hours = _get_as_int(splitted_age.get('h', '0')[::-1], 0, 24)
    minutes = _get_as_int(splitted_age.get('m', '0')[::-1], 0, 60)
    if INVALID_AGE in [days, hours, minutes]:
        return INVALID_AGE
    return days * 24 * 3600 + hours * 3600 + minutes * 60


class Command(BaseCommand):
    """ Management command used to clear the filer trash

        It supports the specification of the maximum age of the trashed entries
        The following age specifications are correct:
        --age=50d8h10m
        --age=90d
    """
    help = "Hard-deletes old files and folders from filer trash."

    option_list = BaseCommand.option_list + (
            make_option('--age',
                dest='age',
                default=None,
                help='How old the deleted files are; e.g. --age=90d23h50m.\n'
                'Max value is 365d23h59m. Do not overflow time units:'
                '--age=1d instead of --age=24h'
                ),
            )

    def handle(self, *args, **options):
        age = options['age']
        # if age is not parse-able, the default age is used
        no_of_sec = _parse_age(age)
        if no_of_sec == INVALID_AGE:
            self.stdout.write('Invalid age string. The default value '
                'will be used: %d s\n' % FILER_TRASH_CLEAN_INTERVAL)
            no_of_sec = FILER_TRASH_CLEAN_INTERVAL
        self.stdout.write('no_of_sec: %d\n\n' % no_of_sec)
        time_threshold = datetime.now() - timedelta(seconds=no_of_sec)
        files_ids = File.trash.filter(deleted_at__lt=time_threshold)\
            .values_list('id', flat=True)
        folder_ids = Folder.trash.filter(deleted_at__lt=time_threshold)\
            .order_by('tree_id', '-level').values_list('id', flat=True)

        if not folder_ids and not files_ids:
            self.stdout.write("No old files or folders.\n")
            return

        for file_id in files_ids:
            a_file = File.trash.get(id=file_id)
            self.stdout.write("Deleting file %s: %s\n" % (
                file_id, repr(a_file.file.name)))
            try:
                a_file.delete(to_trash=False)
            except Exception as e:
                self.stderr.write("%s\n" % str(e))

        for folder_id in folder_ids:
            a_folder = Folder.trash.get(id=folder_id)
            ancestors = a_folder.get_ancestors(include_self=True)
            path = repr('/'.join(ancestors.values_list('name', flat=True)))
            if File.all_objects.filter(folder=folder_id).exists():
                self.stdout.write("Cannot delete folder %s: %s since is "
                                  "not empty.\n" % (folder_id, path))
                continue
            self.stdout.write(
                "Deleting folder %s: %s\n" % (folder_id, path))
            try:
                a_folder.delete(to_trash=False)
            except Exception as e:
                self.stderr.write("%s\n" % str(e))
