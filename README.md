# UnlinkMKV.py


Very crude script to merge linked mkv segment back into a single file,
the only reason I made this is because UnlinkMKV didn't work on some files.

There's no doc, no help and no guarantees.

Run it via `mkv_unlink.py <source folder with segmented mkv's> [<optional output folder>]`

It will link and merge all segmented files in the source folder into the output folder and append the new CRCSum.

Default output folder is `_output`.

Aditionally it will *try* to *fix* ass-subtitles.

The way it fixes those is by taking all the styles from each segment and appending a suffix, like `partid_1`
this ensures that the style from, say segment2 will not be overidden by segment1 so all styles can coexist.
This may add additional garbage but it's just a few bytes so who cares, better than hoping that all segments have the same styles.

If there are no subtitles it probably just crashes.


Note this program is just a private tool I paid almost no attention to clean code or bugs.
