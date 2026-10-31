"""Shared Bonjour discovery for all portable launcher platforms.

iOS uses Foundation Bonjour with the same _zgtav._tcp service and /health
contract. Browser JavaScript uses this local backend; it cannot browse mDNS.
"""
from lobby_discovery_portable import Announcement, discover
