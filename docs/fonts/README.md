# Website typography

The website uses IBM Plex Sans in upright Regular, Medium, SemiBold and Bold, and IBM Plex Mono Regular for code. The original WOFF2 files are distributed under the [SIL Open Font License](OFL.txt), separately from the project's MIT-licensed code.

Build or preview the website:

```sh
python scripts/prepare_site_fonts.py
python -m http.server 8765 --directory docs
```

The preparation script retrieves the original assets from [IBM Plex at an exact commit](https://github.com/IBM/plex/tree/ba3013d72a8419a22c758cc51c44e04ac7ea565b) and validates their Git blob identities. CI packages them with the static site. Browsers load fonts from the website's own origin; no external font service is involved. Fallback fonts apply if a browser lacks WOFF2 support.
