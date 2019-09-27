from datetime import datetime
import sys

from bs4 import BeautifulSoup
import time
import caldav
from caldav.elements import dav, cdav
from lxml import etree
import requests
from requests.auth import HTTPBasicAuth
import logging

_logger = logging.getLogger(__name__)


class iCloudConnector(object):

    icloud_url = "https://caldav.icloud.com"
    username = None
    password = None
    propfind_principal = '<A:propfind xmlns:A="DAV:"><A:prop><A:current-user-principal/></A:prop></A:propfind>'
    propfind_calendar_home_set = "<propfind xmlns='DAV:' xmlns:cd='urn:ietf:params:xml:ns:caldav'><prop> <cd:calendar-home-set/></prop></propfind>"

    def __init__(self, username, password, **kwargs):
        self.username = username
        self.password = password
        if "icloud_url" in kwargs:
            self.icloud_url = kwargs["icloud_url"]
        self.discover()
        self.get_calendars()

    # discover: connect to icloud using the provided credentials and discover
    #
    # 1. The principal URL
    # 2  The calendar home URL
    #
    # These URL's vary from user to user
    # once doscivered, these  can then be used to manage calendars

    def discover(self):
        # Build and dispatch a request to discover the prncipal us for the
        # given credentials
        headers = {"Depth": "1"}
        auth = HTTPBasicAuth(self.username, self.password)
        principal_response = self.repeated_request(
            "PROPFIND", self.icloud_url, auth=auth, data=self.propfind_principal
        )
        # Parse the resulting XML response
        soup = BeautifulSoup(principal_response.content, "lxml")
        self.principal_path = (
            soup.find("current-user-principal").find("href").get_text()
        )
        discovery_url = self.icloud_url + self.principal_path
        _logger.debug("Discovery url {}".format(discovery_url))
        # Next use the discovery URL to get more detailed properties - such as
        # the calendar-home-set
        home_set_response = self.repeated_request(
            "PROPFIND", discovery_url, auth=auth, data=self.propfind_calendar_home_set
        )
        _logger.debug("Result code: {}".format(home_set_response.status_code))
        if home_set_response.status_code != 207:
            _logger.error(
                "Failed to retrieve calendar-home-set {}".format(
                    home_set_response.status_code
                )
            )
            raise Exception(
                "failed to retrieve calender home set {}".format(
                    home_set_response.content
                )
            )
        # And then extract the calendar-home-set URL
        soup = BeautifulSoup(home_set_response.content, "lxml")
        self.calendar_home_set_url = soup.find(
            "href", attrs={"xmlns": "DAV:"}
        ).get_text()

    def repeated_request(self, *args, **kwargs):
        for _ in range(0, 5):
            response = requests.request(*args, **kwargs)
            _logger.debug("Request result code: {}".format(response.status_code))
            if response.status_code != 207:
                _logger.error(
                    "Failed to retrieve response: {}".format(response.status_code)
                )
                _logger.error("Retry")
                time.sleep(0.25)
            if response.status_code == 207:
                break
        else:
            raise Exception(
                "failed to retrieve {} {}".format(response.content, response.headers)
            )
        return response

    # get_calendars
    # Having discovered the calendar-home-set url
    # we can create a local object to control calendars (thin wrapper around
    # CALDAV library)
    def get_calendars(self):
        self.caldav = caldav.DAVClient(
            self.calendar_home_set_url, username=self.username, password=self.password
        )
        self.principal = self.caldav.principal()
        self.calendars = self.principal.calendars()

    def get_named_calendar(self, name):

        if len(self.calendars) > 0:
            for calendar in self.calendars:
                properties = calendar.get_properties([dav.DisplayName()])
                display_name = properties["{DAV:}displayname"]
                if display_name == name:
                    return calendar
        return None

    def create_calendar(self, name):
        return self.principal.make_calendar(name=name)

    def delete_all_events(self, calendar):
        for event in calendar.events():
            event.delete()
        return True

    def create_events_from_ical(self, ical):
        # to do
        pass

    def create_simple_timed_event(
        self, start_datetime, end_datetime, summary, description
    ):
        # to do
        pass

    def create_simple_dated_event(
        self, start_datetime, end_datetime, summary, description
    ):
        # to do
        pass
