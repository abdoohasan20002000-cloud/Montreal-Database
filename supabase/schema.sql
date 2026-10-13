-- Run once in Supabase > SQL editor. Then create a PRIVATE storage bucket named "uploads".
-- The Streamlit app talks to Supabase with the service-role key kept in Streamlit secrets,
-- so row-level security below only blocks direct public access.

create table if not exists public.uploads (
  id                  text primary key,
  title               text not null,
  data_type           text not null,
  file_name           text not null,
  file_size           bigint,
  mime                text,
  sha256              text not null unique,       -- duplicate check
  storage_path        text,
  source_org          text,
  original_reference  text,
  work_year           int,
  data_era            text,                       -- pre-1960 / 1960 and later / undated
  value_status        text,                       -- measured / derived / interpolated / estimated / mixed / n.a.
  licence             text,
  access_level        text,
  notes               text,
  uploaded_by         text,
  uploaded_at         timestamptz default now(),
  geom_type           text,                       -- point / area
  x_mtm8              double precision,           -- footprint centroid, EPSG:32188
  y_mtm8              double precision,
  lon                 double precision,           -- WGS84 copy for the web map
  lat                 double precision,
  footprint_wkt_mtm8  text,                       -- full footprint, EPSG:32188
  status              text not null default 'pending',  -- pending / approved / rejected
  check_report        jsonb,
  reviewed_by         text,
  reviewed_at         timestamptz,
  review_note         text
);

alter table public.uploads enable row level security;
-- No policies: only the service-role key (the app) can read or write.
