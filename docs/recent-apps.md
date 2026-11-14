# Recent applications and optional expiry

In Start → **Menu options… → Recent history age**, choose **No age limit (default)**
or 1, 7, 30, 90 or 365 days. The existing count limit still applies. Local records
can retain another validated integer period from 1 to 365 days; the menu shows it.
This is app-launch history only, not documents, frequency rankings or telemetry.
Nothing is transmitted or indexed outside the installed-app catalog.

With no age limit, behavior and timestamp collection are unchanged: launch IDs are
kept up to the count limit, without recording launch times. Once expiry is enabled,
only successful recorded launches receive an integer UTC/Unix timestamp, local to
`lxqt-comfort/recent.json` in the selected configuration directory.

The displayed notice explains that enabling expiry discards older entries lacking
launch times. Their age is unknown; opening Start never assigns them a fictional
new launch time. Entries expire at age **greater than or equal to** the chosen
number of 24-hour days. Re-launching an app updates its time and position. Changing
the count removes matching timestamp entries too. Turning recording off or choosing
Clear recent programs clears active IDs and timestamps, retaining the selected policy.
Turning the age limit off from Start discards timestamps and preserves unexpired IDs.
Extending/disabling expiry does not revive entries already expired under the previous
policy. If the clock is unusable, clear history or disable recording before changing
a timed policy.

Expiry is checked on menu presentation (including resident reopens) and history
changes. List refreshes also filter expired entries in memory. There is no background
poller: with Start unused, expired bytes can remain on disk until the next use.
Repeated opens with no expiry do not rewrite the file. An atomic-save failure or
external edit leaves the disk file intact, keeps expired entries hidden and displays
a warning in Start. Fix the write/conflict condition and reopen to retry. Clearing
history/disabling recording still works if the clock is unusable.

## Clock and malformed data

Future-dated entries are discarded by an active expiry policy, including when a
clock rollback makes their launch times later than now. Timestamps are never rebased
to extend retention. An invalid system clock hides timed entries and refuses timed
writes. No wall clock can establish real elapsed time across every offline clock
adjustment; a rollback that still leaves now after all launches is not detectable
from these records. This is a local convenience/privacy policy, not tamper-proof time.

Files are bounded to 128 KiB, 50 entries/timestamps, IDs of at most 4096 characters,
and integer timestamps from Unix epoch through year 9999. Invalid types, duplicate
JSON keys, unsupported local versions, oversized data and malformed timestamps
produce an error without overwriting the file. Missing timestamps are allowed for
legacy migration; unknown-age entries expire only when the policy is enabled.

## Backup and portable preferences boundary

Expiry applies to the **active history file**. Operations involving a timed policy
do not create new `recent.json.backup-*` snapshots. Existing legacy backup files
and the private portable-settings undo record are preserved; they can contain
historical IDs/times and are not swept. Disabling expiry returns to the existing
preference-backup behavior. Clear recent programs is not secure erasure of old
backups, external copies or filesystem snapshots.

Portable settings export only the optional `retention_days` preference, never IDs
or launch times. Imports preserve local history/timestamps and exact rollback;
Start applies the imported age policy on later use. The preview explains that
untimed entries can expire then. A legacy import without the optional field keeps
the destination's existing policy. Exports from a never-configured default retain
the original portable shape; older readers refuse exports containing the new field
instead of ignoring it. The portable undo record remains private and can contain
history, as documented in [portable settings](portable-settings.md).

Tests use synthetic launch records, controlled clocks, offscreen menus and temporary
installed toolkits. Real session/input interaction and long-running login acceptance
are not part of this feature's verification.
