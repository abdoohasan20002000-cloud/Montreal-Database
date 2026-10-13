"""What the data is, and how to read it."""
import streamlit as st

from geotech import ui

ui.hero("About the data", "What is in the atlas, where it comes from, and how to read each value.")
st.markdown("""
**Borehole archive.** 6,961 boreholes and 39,285 SPT samples, 1927–2009, compiled from the
City of Montréal, the Ministère des Transports (MTQ) and the Ministère de l'Environnement (MELCC).

**Coordinates.** Stored in MTM zone 8 (EPSG:32188), metres. The map shows a WGS84 copy;
downloads carry both, with MTM 8 as the reference.

**Measured, derived, estimated.**
- `n_field` is the raw SPT N as recorded in the field. The app never corrects it.
- Refusals are flagged in `refusal`. They are censored values (the true N is higher), not N = 999.
- Vs30 and NBCC site class in the archive are **estimated** from a lithology lookup
  (Rosset et al. 2023), not measured. `vs30_status` says so on every row.
- Every contributed file states whether its values are measured, derived, interpolated or estimated.

**Measured Vs (Rosset compilation).** 159 sites with a Vs30 from field seismic surveys (landstreamer/MASW lines,
downhole tests) and 2,273 Vs-depth rows. These are the only **measured** Vs values here. Downhole Vs is measured;
MASW and minivib profiles are derived (inversion, travel times), and `vs_status` says which. Sites far off the
island (Rougemont area and two others) are in the files but hidden until you tick the box. Profiles with no
location in the source (for example MM05, MM11 to MM20, MP11) are only in the whole-island selection.

**Pre-1960 data.** Before 1960, SPT N-values read about half of modern ones (era multiplier about 1.7).
These holes are marked `data_era = pre-1960` and shown in orange on the map. Their raw N is kept.

**Checks on every upload.** Duplicate file, location on the island, file opens; for tables also unique
hole IDs, coordinates on the island (and swapped X/Y), depth and layer consistency, refusals coded as 999,
Vs30 outside 100–3000 m/s, and pre-1960 dates. A curator reviews the report before the file goes live.

**Provenance.** Each contributed file records its source, original reference, year of the work,
who uploaded it and when, and who approved it and when.
""")
