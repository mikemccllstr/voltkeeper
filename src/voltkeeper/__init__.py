# ABOUTME: Voltkeeper package root — exports the VCS-derived version string.

try:
    from ._version import __version__
except ImportError:
    __version__ = "0+unknown"
