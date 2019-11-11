# UnlinkMKV.py


Very crude script to merge linked mkv segments back into a single file,
the only reason I made this is because UnlinkMKV didn't work on some files.

There's no doc, no help and no guarantees.
This program is just a private tool I paid almost no attention to clean code or bugs theres also a ton of leftover debug print's and commented code.

The sole reason for posting this is that it may help others if they find themselves left with files that do not work in other similar tools and are too lazy to make something from scratch, then this tool may help them with minor edits or provide an insight in what one method for handling linked segment mkv files could be.

---

Run it via `mkv_unlink.py <source folder with segmented mkv's> [<optional output folder>]`

It will link and merge all segmented files in the source folder into the output folder and append the new CRCSum.

Aditionally it will **try** to "*fix*" ass-subtitles*, note that if there are no subtitles it probably just crashes.

Default output folder is `_output`.

The script requires Python 3.8 and `mkvmerge`, `mkvextract`, `ffmpeg` to be in $PATH/%PATH%

Only tested on Windows.

---

\* The way it "*fixes*" those is by taking all the styles from each segment and appending a suffix, like `partid_1`
this ensures that the style from, say segment2 will not be overidden by segment1 so all styles can coexist.
This may add additional garbage but it's just a few bytes so who cares, better than hoping that all segments have the same styles.
