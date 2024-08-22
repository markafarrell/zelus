# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## Types of changes
- **Added** for new features.
- **Changed** for changes in existing functionality.
- **Deprecated** for soon-to-be removed features.
- **Removed** for now removed features.
- **Fixed** for any bug fixes.
- **Security** in case of vulnerabilities.

## [0.2.5] - 2024-02-26
### Fixed
- Added dst_len to route format string
- Fixed logic for initial sync in STRICT mode. Previously we were attempting to do a double delete of unprotected routes

## [0.2.4] - 2024-02-26
### Added
- Add hostname to prometheus metrics

## [0.2.3] - 2024-02-26
### Fixed
- Correctly detect config changes when config file is a symlink (FOR GOOD.... HOPEFULLY)

## [0.2.2] - 2024-02-26
### Fixed
- Correctly detect config changes when config file is a symlink

## [0.2.1] - 2024-02-26
### Fixed
- Correctly handle SIGTERM
- Correctly detect config changes when config file is a symlink

## [0.2.0] - 2024-02-26
### Added
- Prometheus instrumentation
