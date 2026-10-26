import glob
import sqlite3
import time
from os import environ
from os.path import expanduser

CONTACTS_GLOB = expanduser(
    "~/Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb"
)
# Re-read Contacts at most this often when a handle isn't found.
RELOAD_SECONDS = 300

PHONES_QUERY = """
    SELECT p.ZFULLNUMBER, r.ZNICKNAME, r.ZFIRSTNAME, r.ZLASTNAME
    FROM ZABCDPHONENUMBER p JOIN ZABCDRECORD r ON r.Z_PK = p.ZOWNER
"""
EMAILS_QUERY = """
    SELECT e.ZADDRESS, r.ZNICKNAME, r.ZFIRSTNAME, r.ZLASTNAME
    FROM ZABCDEMAILADDRESS e JOIN ZABCDRECORD r ON r.Z_PK = e.ZOWNER
"""


def normalize_handle(handle):
    """Key phone numbers by their last 10 digits and emails by lowercase address,
    so "+1 (202) 555-1234" and "+12025551234" match."""
    if "@" in handle:
        return handle.strip().lower()

    digits = "".join(char for char in handle if char.isdigit())
    return digits[-10:]


def display_name(nickname, first_name, last_name):
    return nickname or first_name or last_name or None


def parse_overrides(raw):
    """Parse NAME_OVERRIDES: comma-separated "handle=Name" pairs."""
    overrides = {}
    for pair in raw.split(","):
        handle, _, name = pair.partition("=")
        if handle.strip() and name.strip():
            overrides[normalize_handle(handle)] = name.strip()

    return overrides


def load_contacts():
    names = {}
    for path in glob.glob(CONTACTS_GLOB):
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            for query in (PHONES_QUERY, EMAILS_QUERY):
                for handle, nickname, first_name, last_name in connection.execute(query):
                    name = display_name(nickname, first_name, last_name)
                    if handle and name:
                        names[normalize_handle(handle)] = name

    return names


class NameResolver:
    def __init__(self):
        self._overrides = parse_overrides(environ.get("NAME_OVERRIDES", ""))
        self._contacts = {}
        self._loaded_at = None
        self._reload()

    def _reload(self):
        try:
            self._contacts = load_contacts()
        except Exception as error:
            print(f"Could not read Contacts, using overrides only: {error}")
        self._loaded_at = time.monotonic()

    def lookup(self, handle):
        """Return the contact's name, or the raw handle if there is none."""
        if handle is None:
            return "Unknown"

        key = normalize_handle(handle)
        if key in self._overrides:
            return self._overrides[key]

        if key not in self._contacts and time.monotonic() - self._loaded_at > RELOAD_SECONDS:
            self._reload()

        return self._contacts.get(key, handle)
