# Sileo installer source — beta4 / Build109

These are the matching0.109-2 public TrollStore/AppSync inputs. The existing installer methods and templates are preserved; version, descriptions, public URL and exact IPA pins are updated. Render with `python3 -B tools/build_trollstore_package.py /new/staging/path` (or add `--flavor appsync`) and build with Linux `dpkg-deb --root-owner-group`.

The owner tested private0.109-1 installation/data and the exact Build109 application with Mac voice, distance and mute. The public0.109-2 metadata wrapper was not separately installed.26 mocked public installer/catalog/index checks and actual archive/input checks pass. AppSync installation remains untested.

No signing key is included. Use the canonical [Sileo repository](https://github.com/zemabinks/repo) for its signed package indexes and retained package pool. This folder mirrors installer source and download metadata; it is not a standalone APT repository. Keep the existing app and its data when updating.
