#!/usr/bin/env python3
import argparse
import os
import shutil
import re
import random
import string
import sys
import traceback
import filecmp
import atexit


# DEFAULT VALUES - DO NOT CHANGE IT HERE, MAKE USER CONFIGS IN ~/.clean_files !

CONFIG_FILE = os.path.expanduser('~/.clean_files')
DEFAULT_ACCESS = 755
DEFAULT_TRICKY_LETTERS = ':".,;*?$#`|\'\\'
DEFAULT_TRICKY_LETTERS_SUBSTITUTE = "_"
DEFAULT_TMP_FILES_PATH = ".*(\\.tmp|~)"

# Reading config

def read_config():
    """Reads config file from $HOME/.clean_files if it exist and retuns pairs of keys and values
    separated by delimeter "=", ignoring whitespaces.

    Returns:
        dict[str, str]: Pairs of config types and values or empty dictionary if file is empty,
        have no valid lines or is missing.
    """
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding = 'UTF-8') as file:
            for line in file:
                try:
                    key, value = line.strip().split('=')
                    config[key.strip()] = value.strip()
                except ValueError:
                    continue
    return config


# Main program - file handle

class FileHandle:
    """ Main File handling class for program.

    Includes methods for mass file renaming, duplicating, changing file access,
    removing "Tricky" Linux letters in filenames, empty or temporary files.

    Function initialises itself with temporary catalog for operation, which will be automatically
    deleted when program exits.
    """

    def __init__(self, temp_path):
        """"Initialises FileHandle object with empty settings dict (saved as self.args)
        and given temporary folder path. Attaches temporary folder deletion at file exit.

        Args:
            temp_path (str): Path to directory in which given temporary folder should be created.

        Raises:
            OSError: Temporary catalog cannot be created in given location.
        """
        try:
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            os.mkdir(temp_path)
        except OSError as e:
            raise OSError(f"Error: {e}") from e

        atexit.register(self.clean_up_temp_catalog)
        self.temp_calatog_path = temp_path
        self.args = {
            'source_catalogs' : []
            ,'destination_catalog' : None
            ,'empty' : False
            ,'temporary' : None
            ,'tricky_letters' : None
            ,'tricky_letters_substitute' : None
            ,'duplicates' : False
            ,'same_name' : False
            ,'access' : None
            ,'move' : False
            ,'auto' : False
        }

    def args_handler(self, arg_name, arg_value):
        """Sets given settings name to given settings value. Uses values from self.args.
        Function can create new pairs of settings key-values.

        Args:
            arg_name (Any):  Setting name.
            arg_value (Any): Setting value.
        """
        self.args[arg_name] = arg_value

    def duplicates(self, src_filepath, dest_filepath):
        """Replaces file in destination filepath with file if source flepath is older when files
        are the same, or with newer file otherwise. Returns True when replacement operation
        in completed successfully, else returns False.

        Args:
            src_filepath (str): Path to existing source file.
            dest_filepath (str): Path to existing destination file.

        Returns:
            bool: Is file replacement operation completed successfully.
        """
        time1 = os.path.getmtime(src_filepath)
        time2 = os.path.getmtime(dest_filepath)

        if time1 > time2:
            if filecmp.cmp(src_filepath, dest_filepath):
                print(f'Ignoring identical file copy - newer: {src_filepath}')
                return False
            else:
                print(f'Replacing duplicate file - older: {dest_filepath}')
                os.remove(dest_filepath)
                shutil.copy2(src_filepath, dest_filepath)
                return True
        else:
            if filecmp.cmp(src_filepath, dest_filepath):
                print(f'Replacing duplicate identical file - newer: {dest_filepath}')
                os.remove(dest_filepath)
                shutil.copy2(src_filepath, dest_filepath)
                return True
            else:
                print(f'Ignoring file copy - older: {src_filepath}')
                return False

    def empty(self, filepath):
        """Removes file if it's empty (has 0kB in size).
        Returns True if file was deleted, False otherwise.

        Args:
            filepath (str): Path to existing file.

        Returns:
            bool: Is file deletion completed successfully.
        """
        if os.path.getsize(filepath) == 0:
            print(f'Removing empty file: {filepath}')
            os.remove(filepath)
            return True
        return False

    def temporary(self, filepath, tmp_files_pattern):
        """Deletes (temporary) files using given REGEX expression.
        Using '.*(\.tmp|~)' expression is recomennded.
        Returns True if file was deleted, False otherwise.

        Args:
            filepath (str): Path to existing file.
            tmp_files_pattern (str): REGEX pattern for file deletion.

        Returns:
            bool: Is file deletion completed successfully.
        """
        if re.search(tmp_files_pattern, os.path.basename(filepath)):
            print(f'Removing temporary file: {filepath}')
            os.remove(filepath)
            return True
        return False

    def same_name(self, src_filepath, dest_filepath):
        """Creates copy of a given file in destination catalog renaming it to include index value.
        Examples:\n
        file.txt -> file(1).txt\n
        test -> test(1)\n
        test(abc) -> test(abc)(1)\n

        After that, copies renamed file to destination catalog.

        Args:
            src_filepath (str): Path to existing source file.
            dest_filepath (str): Path to existing destination file.
        """
        filename = os.path.basename(src_filepath)
        new_filepath = dest_filepath
        while os.path.exists(new_filepath):
            base, ext = os.path.splitext(filename)
            base, index_str = self._extract_index(base)
            index = int(index_str) if index_str else 0
            index += 1
            filename = f"{base}({index}){ext}"
            new_filepath = os.path.join(os.path.dirname(dest_filepath), filename)
        print(f'Renaming and copying file to avoid conflict: {src_filepath} -> {new_filepath}')
        shutil.copy2(src_filepath, new_filepath)

    def _extract_index(self, filename):
        """Extracts renaming index value from filename if it exits.
        Returns string with base filename (without index if it existed) and string with index number.

        Args:
            filename (str): Fil name extracted from edited filepath.

        Returns:
            base(str): New filename.
            index_str(str): Index value converted to string.
        """

        parts = filename.rsplit("(", 1)
        base = parts[0]
        index_str = parts[1].rstrip(")") if len(parts) > 1 else None
        if index_str:
            if not index_str.isdigit():
                base = str(f"{base}({index_str})")
                index_str = None
        return base, index_str

    def strange_access(self, filepath, suggested_access):
        """Modifies file access values to value given in suggested_access variable.
        Value should be stored as 'xxx' value, where x is digit from 0 to 7.

        Args:
            filepath (str): Path to existing file.
            suggested_access (str | int): File access value as a base-10 number
        """
        access_value = int(str(suggested_access), 8)
        st = os.stat(filepath)
        file_permission = int(oct(st.st_mode)[-3:])
        if not file_permission == suggested_access:
            print(f'Modifying access to file: {filepath}')
            os.chmod(filepath, access_value)

    def tricky_letters(self, filepath, tricky_letters_str, substitute_letter):
        """Modifies file name to remove characters from tricky_letters_str to character given
        in substitute_letter variable.

        Args:
            filepath (str): Path to existing file.
            tricky_letters_str (str): String with every character to replace
            substitute_letter (char | str): Single character to replace letters in filename.
        """
        file = os.path.basename(filepath)
        directory_path = os.path.dirname(filepath)
        if any(letter in file for letter in tricky_letters_str):
            a = f"[{tricky_letters_str}]"
            new_name = re.sub(a, substitute_letter, file)
            old_filepath = os.path.join(directory_path, file)
            new_filepath = os.path.join(directory_path, new_name)
            try:
                os.rename(old_filepath, new_filepath)
                print(f'Replacing tricky letters in file to: {new_filepath}')
            except Exception:
               pass
            return new_filepath
        else:
            return os.path.join(directory_path, file)

    def start(self):
        """
        Starts main loop of the program.
        """
        source_catalogs = self.args.get('source_catalogs')
        for idx in range(0, len(source_catalogs)):
            source_catalogs[idx] = os.path.abspath(source_catalogs[idx])
        dest_catalog = os.path.abspath(self.args.get('destination_catalog'))
        for catalog in source_catalogs:
            for root, _, files in os.walk(catalog):
                for file in files:
                    src_filepath = os.path.join(root, file)
                    dest_filepath = os.path.join(dest_catalog,
                        os.path.relpath(src_filepath, catalog))
                    temp_dest_filepath = os.path.join(
                        self.temp_calatog_path, os.path.relpath(src_filepath, catalog))

                    if self.args.get('empty'):
                        try:
                            self.empty(dest_filepath)
                        except Exception:
                            pass
                        if self.empty(src_filepath):
                            continue
                    if self.args.get('temporary'):
                        try:
                            self.temporary(dest_filepath, self.args.get('temporary'))
                        except Exception:
                            pass
                        if self.temporary(src_filepath, self.args.get('temporary')):
                            continue
                    if self.args.get('tricky_letters') and self.args.get('tricky_letters_substitute'):
                        dest_filepath = self.tricky_letters(dest_filepath, self.args.get('tricky_letters'),
                                            self.args.get('tricky_letters_substitute'))
                        src_filepath = self.tricky_letters(src_filepath, self.args.get('tricky_letters'),
                                            self.args.get('tricky_letters_substitute'))

                    if self.args.get('access'):
                        try:
                            self.strange_access(dest_filepath, self.args.get('access'))
                        except Exception:
                            pass
                        self.strange_access(src_filepath, self.args.get('access'))


                    os.makedirs(os.path.dirname(temp_dest_filepath), exist_ok=True)
                    shutil.copy2(src_filepath, temp_dest_filepath)

                    successful_copy = False

                    if os.path.exists(dest_filepath):
                        if self.args.get('same_name'):
                            self.same_name(src_filepath, dest_filepath)
                            successful_copy = True
                        elif self.args.get('duplicates'):
                            is_copied_successfully = self.duplicates(
                                temp_dest_filepath, dest_filepath)
                            successful_copy = is_copied_successfully
                        else:
                            print(f"""Conflict detected: {src_filepath} -> {dest_filepath}.
                                  File was not copied""")
                    else:
                        os.makedirs(os.path.dirname(dest_filepath), exist_ok=True)
                        print(f'Copying {src_filepath} to {dest_filepath}')
                        shutil.copy2(src_filepath, dest_filepath)
                        successful_copy = True

                    if self.args.get('move') and successful_copy:
                        print(f'Removing {src_filepath} (move argument was used).')
                        os.remove(src_filepath)


    def clean_up_temp_catalog(self):
        """Removes temporary catalog, if it exists
        """
        if os.path.exists(self.temp_calatog_path):
            shutil.rmtree(self.temp_calatog_path)


class ExceptionHandle:
    """Class to handle exceptions in this program, with buildin temporary catalog removal.
    Given temporary catalog path should exist and be used in FileHandle class above.
    Object should be created without assignin to variable.
    """
    def __init__(self, temp_path):
        """Saves path to temporary catalog and attaches sys.excepthook for code exceptions.

        Args:
            temp_path (str): Path to existing temporary catalog.
        """
        self.temp_calatog_path = temp_path
        sys.excepthook = self.custom_exception_handler

    def custom_exception_handler(self, exc_type, exc_value, exc_traceback):
        """Prints exeption and removes temporary catalog.
        """
        self.clean_up_temp_catalog(self.temp_calatog_path)
        traceback_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
        traceback_str = ''.join(traceback_details)
        print(f"Szczegóły wyjątku:\n{traceback_str}")
        print("Error during code execution occured. Temporary directory was deleted.")

    def clean_up_temp_catalog(self, catalog) -> None:
        """Removes teporary catalog, if it exists.

        Args:
            catalog (str): Path to temporary catalog.
        """
        if os.path.exists(catalog):
            shutil.rmtree(catalog)


def check_access(value):
    """Check if loaded access value is correct. Returns default access value if it's invalid.

    Args:
        value (str | int): Value to check.

    Returns:
        int: Access value as a base-10 number.
    """
    valid_numbers = ('0', '1', '2', '3', '4', '5', '6', '7')
    value = str(value)
    if len(value) != 3:
        return DEFAULT_ACCESS
    for access_char in value:
        if access_char not in valid_numbers:
            return DEFAULT_ACCESS
    return int(value)

def check_letter_substitute(value):
    """Checks if letter substitute for tricky letters is a singlr character, or if it contains
    illegal Linux path characters. Returns default letter if loaded value is invalid.

    Args:
        value (str): Value to check.

    Returns:
        str: Loaded value of default value if given one is invalid.
    """
    if len(value) != 1 or value == '/' or value == '\0':
        return DEFAULT_TRICKY_LETTERS_SUBSTITUTE
    return value


def main():
    temp_path = str('/tmp/copy_script-' + ''.join(
            random.choice(string.digits) for _ in range (10)))

    ExceptionHandle(temp_path)
    config = read_config()
    files = FileHandle(temp_path)

    parser = argparse.ArgumentParser(description='File operations script')
    parser.add_argument('source_catalogs', nargs='+',
                    help='Directories to process')
    parser.add_argument('destination_catalog',
                    help='Copy files to given directory')
    parser.add_argument('--move', action='store_true',
                    help='Move non-conflicting files instead of copying them')
    parser.add_argument('--duplicates', action='store_true',
                    help='Remove duplicates (keeping newer, or older when files are the same)')
    parser.add_argument('--empty', action='store_true',
                    help='Remove empty files')
    parser.add_argument('--temporary', action='store_true',
                    help='Remove temporary files')
    parser.add_argument('--same-name', action='store_true',
                    help='Handle files with the same name')
    parser.add_argument('--access', type=int, default=config.get('access'),
                    help="""Modify permission to value given as a argument
                        or using defaults from config file""")
    parser.add_argument('--tricky', action='store_true',
                    help='Replace tricky letters')
    parser.add_argument('--auto', action='store_true',
                    help='Run script automatically resolving conflicts using configuration file')

    args = parser.parse_args()

    files.args_handler('source_catalogs', args.source_catalogs)
    files.args_handler('destination_catalog', args.destination_catalog)
    files.args_handler('move', args.move)
    files.args_handler('duplicates', args.duplicates)
    files.args_handler('empty', args.empty)
    files.args_handler('same_name', args.same_name)
    files.args_handler('access', check_access(args.access) if args.access else None)
    files.args_handler('auto', args.auto)
    if args.temporary:
        files.args_handler('temporary', config.get('tmp_files', DEFAULT_TMP_FILES_PATH))
    if args.tricky:
        files.args_handler('tricky_letters', config.get(
            'tricky_letters', DEFAULT_TRICKY_LETTERS))
        files.args_handler('tricky_letters_substitute', check_letter_substitute(config.get(
            'tricky_letters_substitute', DEFAULT_TRICKY_LETTERS_SUBSTITUTE)))

    files.start()
    files.clean_up_temp_catalog()


if __name__ == '__main__':
    main()
