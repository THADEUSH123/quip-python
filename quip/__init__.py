# Copyright 2014 Quip
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""A Quip API client library.

For full API documentation, visit https://quip.com/api/.

Typical usage:

    client = quip.QuipClient(access_token=...)
    user = client.get_authenticated_user()
    desktop = client.get_folder(user["desktop_folder_id"])
    print "There are", len(desktop["children"]), "items on the desktop"

In addition to standard getters and setters, we provide a few convenience
methods for document editing. For example, you can use `add_to_first_list`
to append items (in Markdown) to the first bulleted or checklist in a
given document, which is useful for automating a task list.
"""
import datetime
import json
import logging
import sys
import time
import urllib.request
import urllib.parse
import importlib
import xml.etree.ElementTree
import html.parser
import re

importlib.reload(sys)


class QuipHTMLParser(html.parser.HTMLParser):
    """Parser that removes some misc html."""

    def __init__(self):
        """Init the class."""
        super().__init__()
        self.cell_text = ''
    def handle_starttag(self, tag, attrs):

        if tag == 'span' or tag == 'td':
            pass
        else:
            if not attrs:
                str_to_append = '<' + tag + '>'
                #print(str_to_append)
                self.cell_text += str_to_append
            else:
                for attr in attrs:
                    if attr[0] == "href":
                        str_to_append = '<a href=\"' + attr[1] + '\">'
                        self.cell_text += str_to_append
    def handle_endtag(self, tag):
            if tag == 'span' or tag == 'td' or tag == 'control':
                pass
            else:
                str_to_append = '</' + tag + '>'
                self.cell_text += str_to_append
    def handle_startendtag(self, tag, attrs):
        if not attrs:
            str_to_append = '<' + tag + ' />'
            #print(str_to_append)
            self.cell_text += str_to_append
        else:
            for attr in attrs:
                if attr[0] == "href":
                    str_to_append = '<a href=' + attr[1] + '>'
                    self.cell_text += str_to_append
    def handle_data(self, data):
        self.cell_text += data
    def get_cell_text(self, input_html):
        self.feed(input_html)
        return self.cell_text

class QuipClient(object):
    """A Quip API client"""

    # Edit operations
    APPEND, PREPEND, AFTER_SECTION, BEFORE_SECTION, \
    REPLACE_SECTION, DELETE_SECTION = range(6)

    # Folder colors
    MANILA, RED, ORANGE, GREEN, BLUE = range(5)

    def __init__(self, access_token=None, client_id=None, client_secret=None,
                 base_url=None, request_timeout=None, retry_rate_limit=False):
        """Construct a Quip API client.

        If `access_token` is given, all of the API methods in the client
        will work to read and modify Quip documents.

        Otherwise, only `get_authorization_url` and `get_access_token`
        work, and we assume the client is for a server using the Quip API's
        OAuth endpoint.
        """
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url if base_url else "https://platform.quip.com"
        self.request_timeout = request_timeout if request_timeout else 10
        self.retry_rate_limit = retry_rate_limit

    def get_authorization_url(self, redirect_uri, state=None):
        """Return the URL the user should be redirected to to sign in."""
        return self._url(
            "oauth/login", redirect_uri=redirect_uri, state=state,
            response_type="code", client_id=self.client_id)

    def get_access_token(self, redirect_uri, code,
                         grant_type="authorization_code",
                         refresh_token=None):
        """Exchange a verification code for an access_token.

        Once the user is redirected back to your server from the URL
        returned by `get_authorization_url`, you can exchange the `code`
        argument with this method.
        """
        return self._fetch_json(
            "oauth/access_token", redirect_uri=redirect_uri, code=code,
            grant_type=grant_type, refresh_token=refresh_token,
            client_id=self.client_id, client_secret=self.client_secret)

    def get_authenticated_user(self):
        """Return the user corresponding to our access token."""
        return self._fetch_json("users/current")

    def get_user(self, id):
        """Return the user with the given ID."""
        return self._fetch_json("users/" + id)

    def get_users(self, ids):
        """Return a dictionary of users for the given IDs."""
        return self._fetch_json("users/", post_data={"ids": ",".join(ids)})

    def get_contacts(self):
        """Return a list of the users in the authenticated user's contacts."""
        return self._fetch_json("users/contacts")

    def get_folder(self, id):
        """Return the folder with the given ID."""
        return self._fetch_json("folders/" + id)

    def get_folders(self, ids):
        """Return a dictionary of folders for the given IDs."""
        return self._fetch_json("folders/", post_data={"ids": ",".join(ids)})

    def new_folder(self, title, parent_id=None, color=None, member_ids=[]):
        """Create new folder."""
        return self._fetch_json("folders/new", post_data={
            "title": title,
            "parent_id": parent_id,
            "color": color,
            "member_ids": ",".join(member_ids),
        })

    def update_folder(self, folder_id, color=None, title=None):
        """Update floder."""
        return self._fetch_json("folders/update", post_data={
            "folder_id": folder_id,
            "color": color,
            "title": title,
        })

    def add_folder_members(self, folder_id, member_ids):
        """Add the given users to the given folder."""
        return self._fetch_json("folders/add-members", post_data={
            "folder_id": folder_id,
            "member_ids": ",".join(member_ids),
        })

    def remove_folder_members(self, folder_id, member_ids):
        """Remove the given users from the given folder."""
        return self._fetch_json("folders/remove-members", post_data={
            "folder_id": folder_id,
            "member_ids": ",".join(member_ids),
        })

    def get_messages(self, thread_id, max_created_usec=None, count=None):
        """Return the most recent messages for the given thread.

        To page through the messages, use max_created_usec, which is the
        sort order for the returned messages.

        count should be an integer indicating the number of messages you
        want returned. The maximum is 100.
        """
        return self._fetch_json(
            "messages/" + thread_id, max_created_usec=max_created_usec,
            count=count)

    def new_message(self, thread_id, content=None, **kwargs):
        """Send a message on the given thread.

        `content` is plain text, not HTML.
        """
        args = {
            "thread_id": thread_id,
            "content": content,
        }
        args.update(kwargs)
        return self._fetch_json("messages/new", post_data=args)

    def get_thread(self, id):
        """Return the thread with the given ID."""
        return self._fetch_json("threads/" + id)

    def get_threads(self, ids):
        """Return a dictionary of threads for the given IDs."""
        return self._fetch_json("threads/", post_data={"ids": ",".join(ids)})

    def get_recent_threads(self, max_updated_usec=None, count=None):
        """Return the recently updated threads for a given user."""
        return self._fetch_json(
            "threads/recent", max_updated_usec=max_updated_usec,
            count=count)

    def add_thread_members(self, thread_id, member_ids):
        """Add the given folder or user IDs to the given thread."""
        return self._fetch_json("threads/add-members", post_data={
            "thread_id": thread_id,
            "member_ids": ",".join(member_ids),
        })

    def remove_thread_members(self, thread_id, member_ids):
        """Remove the given folder or user IDs from the given thread."""
        return self._fetch_json("threads/remove-members", post_data={
            "thread_id": thread_id,
            "member_ids": ",".join(member_ids),
        })

    def move_thread(self, thread_id, source_folder_id, destination_folder_id):
        """Move the given thread from the source to the destination folder."""
        self.add_thread_members(thread_id, [destination_folder_id])
        self.remove_thread_members(thread_id, [source_folder_id])

    def new_document(self, content, format="html", title=None, member_ids=[]):
        """Create a new document from the given content.

        To create a document in a folder, include the folder ID in the list
        of member_ids, e.g.,

            client = quip.QuipClient(...)
            user = client.get_authenticated_user()
            client.new_document(..., member_ids=[user["archive_folder_id"]])

        """
        return self._fetch_json("threads/new-document", post_data={
            "content": content,
            "format": format,
            "title": title,
            "member_ids": ",".join(member_ids),
        })

    def copy_document(self, id, title=None, member_ids=[]):
        """Create a new document from the given thread ID.

        To create it in a folder, include the folder ID in member_ids.
        """
        old_thread = self.get_thread(id)
        return self.new_document(
            old_thread["html"], title=title or old_thread["thread"]["title"],
            member_ids=member_ids)

    def merge_comments(self, original_id, children_ids):
        """Merge comments from duplicate to origional.

        Given an original document and a set of exact duplicates, copies
        all comments and messages on the duplicates to the original.
        """
        import re
        threads = self.get_threads(children_ids + [original_id])
        original_section_ids = re.findall(r" id='([a-zA-Z0-9]{11})'",
                                          threads[original_id]["html"])
        for thread_id in children_ids:
            thread = threads[thread_id]
            child_section_ids = re.findall(r" id='([a-zA-Z0-9]{11})'",
                                           thread["html"])
            parent_map = dict(zip(child_section_ids, original_section_ids))
            messages = self.get_messages(thread_id)
            for message in reversed(messages):
                kwargs = {}
                if "parts" in message:
                    kwargs["parts"] = json.dumps(message["parts"])
                else:
                    kwargs["content"] = message["text"]
                if "annotation" in message:
                    section_id = None
                    if "highlight_section_ids" in message["annotation"]:
                        section_id = message["annotation"][
                            "highlight_section_ids"][0]
                    else:
                        anno_loc = thread["html"].find(
                            '<annotation id="{}"'.format(
                                message["annotation"]["id"]))
                        loc = thread["html"].rfind("id=", 0, anno_loc)
                        if anno_loc >= 0 and loc >= 0:
                            section_id = thread["html"][loc+4:loc+15]
                    if section_id and section_id in parent_map:
                        kwargs["section_id"] = parent_map[section_id]
                if "files" in message:
                    attachments = []
                    for blob_info in message["files"]:
                        blob = self.get_blob(thread_id, blob_info["hash"])
                        new_blob = self.put_blob(
                            original_id, blob, name=blob_info["name"])
                        attachments.append(new_blob["id"])
                    if attachments:
                        kwargs["attachments"] = ",".join(attachments)
                self.new_message(original_id, **kwargs)

    def edit_document(self, thread_id, content, operation=APPEND,
                      format="html", section_id=None, **kwargs):
        """Edit the given document, adding the given content.

        `operation` should be one of the constants described above. If
        `operation` is relative to another section of the document, you must
        also specify the `section_id`.
        """
        args = {
            "thread_id": thread_id,
            "content": content,
            "location": operation,
            "format": format,
            "section_id": section_id,
        }
        args.update(kwargs)
        return self._fetch_json("threads/edit-document", post_data=args)

    def add_to_first_list(self, thread_id, *items, **kwargs):
        """Add the given items to the first list in the given document.

            client = quip.QuipClient(...)
            client.add_to_first_list(thread_id, "Try the Quip API")

        """
        items = [item.replace("\n", " ") for item in items]
        args = {
            "thread_id": thread_id,
            "content": "\n\n".join(items),
            "format": "markdown",
            "operation": self.AFTER_SECTION
        }
        args.update(kwargs)
        if "section_id" not in args:
            first_list = self.get_first_list(thread_id)
            if not first_list:
                return None
            args["section_id"] = self.get_last_list_item_id(first_list)
        if not args["section_id"]:
            # section_id = first_list.attrib["id"]
            return None
        return self.edit_document(**args)

    def add_to_spreadsheet(self, thread_id, *rows, **kwargs):
        """Add the given rows to the named (or first) spreadsheet in the doc.

        client = quip.QuipClient(...)
        client.add_to_spreadsheet(thread_id, ["5/1/2014", 2.24])

        """
        content = "".join(["<tr>%s</tr>" % "".join(
            ["<td>%s</td>" % cell for cell in row]) for row in rows])
        if kwargs.get("name"):
            spreadsheet = self.get_named_spreadsheet(kwargs["name"], thread_id)
        else:
            spreadsheet = self.get_first_spreadsheet(thread_id)
        section_id = self.get_last_row_item_id(spreadsheet)
        return self.edit_document(
            thread_id=thread_id,
            content=content,
            section_id=section_id,
            operation=self.AFTER_SECTION)

    def update_spreadsheet_row(self, thread_id, header, value,
                               updates, **args):
        """Find the row where the given header column is the given value.

        Then apply the given updates. Updates is a dict from header to
        new value. In both cases headers can either be a string that matches,
        or "A", "B", "C", 1, 2, 3 etc. If no row is found, adds a new one.

            client = quip.QuipClient(...)
            client.update_spreadsheet_row(
                thread_id, "customer", "Acme", {"Billed": "6/24/2015"})

        """
        response = None
        spreadsheet = self.get_first_spreadsheet(thread_id)
        headers = self.get_spreadsheet_header_items(spreadsheet)
        row = self.find_row_from_header(spreadsheet, header, value)
        if row:
            ids = self.get_row_ids(row)
            for head, val in updates.iteritems():
                index = self.get_index_of_header(headers, head)
                if not index or index >= len(ids) or not ids[index]:
                    continue
                response = self.edit_document(
                    thread_id=thread_id,
                    content=val,
                    format="markdown",
                    section_id=ids[index],
                    operation=self.REPLACE_SECTION,
                    **args)
        else:
            updates[header] = value
            indexed_items = {}
            extra_items = []
            for head, val in updates.iteritems():
                index = self.get_index_of_header(
                    headers, head, default=None)
                if index is None or index in indexed_items:
                    extra_items.append(val)
                else:
                    indexed_items[index] = val
            cells = []
            for i in range(max(indexed_items.keys()) + 1):
                if i in indexed_items:
                    cells.append(indexed_items[i])
                elif len(extra_items):
                    cells.append(extra_items.pop(0))
                else:
                    cells.append("")
            cells.extend(extra_items)
            content = "<tr>%s</tr>" % "".join(
                ["<td>%s</td>" % cell for cell in cells])
            section_id = self.get_last_row_item_id(spreadsheet)
            response = self.edit_document(
                thread_id=thread_id,
                content=content,
                section_id=section_id,
                operation=self.AFTER_SECTION,
                **args)
        return response

    def toggle_checkmark(self, thread_id, item, checked=True):
        """Set the checked state of the given list item to the given state.

        client = quip.QuipClient(...)
        list = client.get_first_list(thread_id)
        client.toggle_checkmark(thread_id, list[0])

        """
        if checked:
            item.attrib["class"] = "checked"
        else:
            item.attrib["class"] = ""
        return self.edit_document(thread_id=thread_id,
                                  content=xml.etree.ElementTree.tostring(item),
                                  section_id=item.attrib["id"],
                                  operation=self.REPLACE_SECTION)

    def get_first_list(self, thread_id=None, document_html=None):
        """Return the `ElementTree` of the first list in the document.

        The list can be any type (bulleted, numbered, or checklist).
        If `thread_id` is given, we download the document. If you have
        already downloaded the document, you can specify `document_html`
        directly.
        """
        return self._get_container(thread_id, document_html, "ul", 0)

    def get_last_list(self, thread_id=None, document_html=None):
        """Like `get_first_list`, but the last list in the document."""
        return self._get_container(thread_id, document_html, "ul", -1)

    def get_section(self, section_id, thread_id=None, document_html=None):
        """Get section from in the document."""
        if not document_html:
            document_html = self.get_thread(thread_id).get("html")
            if not document_html:
                return None
        tree = self.parse_document_html(document_html)
        element = list(tree.iterfind(".//*[@id='%s']" % section_id))
        if not element:
            return None
        return element[0]

    def get_named_spreadsheet(self, name, thread_id=None, document_html=None):
        """Get spreadsheet form the document."""
        if not document_html:
            document_html = self.get_thread(thread_id).get("html")
            if not document_html:
                return None
        tree = self.parse_document_html(document_html)
        element = list(tree.iterfind(".//*[@title='%s']" % name))
        if not element:
            return None
        return element[0]

    def _get_container(self, thread_id, document_html, container, index):
        if not document_html:
            document_html = self.get_thread(thread_id).get("html")
            if not document_html:
                return None
        tree = self.parse_document_html(document_html)
        lists = list(tree.iter(container))
        if not lists:
            return None
        try:
            return lists[index]
        except IndexError:
            return None

    def get_last_list_item_id(self, list_tree):
        """Return the last item in the given list `ElementTree`."""
        items = list(list_tree.iter("li"))
        return items[-1].attrib["id"] if items else None

    def get_first_list_item_id(self, list_tree):
        """Like `get_last_list_item_id`, but the first item in the list."""
        for item in list_tree.iter("li"):
            return item.attrib["id"]
        return None

    def get_first_spreadsheet(self, thread_id=None, document_html=None):
        """Return the `ElementTree` of the first spreadsheet in the document.

        If `thread_id` is given, we download the document. If you have
        already downloaded the document, you can specify `document_html`
        directly.
        """
        return self._get_container(thread_id, document_html, "table", 0)

    def get_last_spreadsheet(self, thread_id=None, document_html=None):
        """Like `get_first_spreadsheet`, but the last spreadsheet."""
        return self._get_container(thread_id, document_html, "table", -1)

    def get_last_row_item_id(self, spreadsheet_tree):
        """Return the last row in the given spreadsheet `ElementTree`."""
        items = list(spreadsheet_tree.iter("tr"))
        return items[-1].attrib["id"] if items else None

    def get_row_items(self, row_tree):
        """Return the text of items in the given row `ElementTree`."""
        return [(list(x.itertext()) or [None])[0] for x in row_tree]

    def get_row_ids(self, row_tree):
        """Return the ids of items in the given row `ElementTree`."""
        return [x.attrib["id"] for x in row_tree]

    def get_spreadsheet_header_items(self, spreadsheet_tree):
        """Return the header row in the given spreadsheet `ElementTree`."""
        return self.get_row_items(list(spreadsheet_tree.iterfind(".//tr"))[0])

    def get_index_of_header(self, header_items, header, default=0):
        """Find the index of the given header in the items."""
        if header:
            header = str(header)
            lower_headers = [str(h).lower() for h in header_items]
            if header in header_items:
                return header_items.index(header)
            elif header.lower() in lower_headers:
                return lower_headers.index(header.lower())
            elif header.isdigit():
                return int(header)
            elif len(header) == 1:
                char = ord(header.upper())
                if ord('A') < char < ord('Z'):
                    return char - ord('A') + 1
            else:
                logging.warning("Could not find header, using first column")
        return default

    def find_row_from_header(self, spreadsheet_tree, header, value):
        """Find the row in given spreadsheet `ElementTree` where header is value.

        Returns `ElementTree` row.
        """
        headers = self.get_spreadsheet_header_items(spreadsheet_tree)
        index = self.get_index_of_header(headers, header)
        for row in spreadsheet_tree.iterfind(".//tr"):
            if len(row) <= index:
                continue
            cell = row[index]
            if cell.tag != "td":
                continue
            if list(cell.itertext())[0].lower() == value.lower():
                return row

    def parse_spreadsheet_contents(self, spreadsheet_tree):
        """Return a python-friendly representation of the given spreadsheet.

        Returns `ElementTree`
        """
        import collections
        spreadsheet = {
            "id": spreadsheet_tree.attrib.get("id"),
            "headers": self.get_spreadsheet_header_items(spreadsheet_tree),
            "rows": [],
        }
        for row in spreadsheet_tree.iterfind(".//tr"):
            value = {
                "id": row.attrib.get("id"),
                "cells": collections.OrderedDict(),
            }
            for i, cell in enumerate(row):
                quip_parser = QuipHTMLParser()
                if cell.tag != "td":
                    continue
                content_str = xml.etree.ElementTree.tostring(cell).decode().replace('\n','')
                cell_contents = quip_parser.get_cell_text(content_str)[:-6]
                # there is a break (<br />) at the end of every cell; remove it
                value["cells"][spreadsheet["headers"][i]] = {
                    "id": cell.attrib.get("id"),
                    "content": cell_contents,
                }
            if len(value["cells"]):
                spreadsheet["rows"].append(value)
        return spreadsheet

    def parse_document_html(self, document_html):
        """Return an `ElementTree` for the given Quip document HTML."""
        document_xml = "<html>" + document_html + "</html>"
        return xml.etree.ElementTree.fromstring(document_xml.encode("utf-8"))

    def parse_micros(self, usec):
        """Return a `datetime` for the given microsecond string."""
        return datetime.datetime.utcfromtimestamp(usec / 1000000.0)

    def get_blob(self, thread_id, blob_id):
        """Return a file-like object with the contents of the given blob from
        the given thread.

        The object is described in detail here:
        https://docs.python.org/2/library/urllib2.html#urllib2.urlopen
        """

        request = urllib.request.Request(
            url=self._url("blob/%s/%s" % (thread_id, blob_id)))
        if self.access_token:
            request.add_header("Authorization", "Bearer " + self.access_token)
        try:
            return urllib.request.urlopen(request,
                                          timeout=self.request_timeout)
        except urllib.request.HTTPError as error:
            try:
                # Extract the developer-friendly error message
                message = json.loads(error.read())["error_description"]
            except Exception:
                raise error
            if (self.retry_rate_limit and error.code == 503 and
               message == "Over Rate Limit"):
                # Retry later.
                reset_time = float(error.headers.get("X-RateLimit-Reset"))
                delay = max(2, reset_time - time.time() + 1)
                logging.warning("Rate Limit, delaying for %d seconds" % delay)
                time.sleep(delay)
                return self.get_blob(thread_id, blob_id)
            else:
                raise QuipError(error.code, message, error)

    def put_blob(self, thread_id, blob, name=None):
        """Upload an image or other blob to the given Quip thread.

        Return an ID that can be used to add the image to the document
        of the thread. blob can be any file-like object. Requires the
        'requests' module.
        """
        import requests
        url = "blob/" + thread_id
        headers = None
        if self.access_token:
            headers = {"Authorization": "Bearer " + self.access_token}
        if name:
            blob = (name, blob)
        try:
            response = requests.request(
                "post", self._url(url), timeout=self.request_timeout,
                files={"blob": blob}, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            try:
                message = error.response.json()["error_description"]
            except Exception:
                raise error
            raise QuipError(error.response.status_code, message, error)

    def _fetch_json(self, path, post_data=None, **args):
        request = urllib.request.Request(url=self._url(path, **args))
        if post_data:
            post_data = dict((k, v) for k, v in post_data.items()
                             if v or isinstance(v, int))
            request.data = urllib.parse.urlencode(self._clean(**post_data))
        if self.access_token:
            request.add_header("Authorization", "Bearer " + self.access_token)
        try:
            return json.loads((urllib.request.urlopen(request, timeout=self.request_timeout).read()).decode('utf-8'))
        except urllib.request.HTTPError as error:
            try:
                # Extract the developer-friendly error message.
                message = json.loads(error.read())["error_description"]
            except Exception:
                raise error
            if (self.retry_rate_limit and error.code == 503 and
               message == "Over Rate Limit"):
                # Retry later.
                reset_time = float(error.headers.get("X-RateLimit-Reset"))
                delay = max(2, reset_time - time.time() + 1)
                logging.warning("Rate Limit, delaying for %d seconds" % delay)
                time.sleep(delay)
                return self._fetch_json(path, post_data, **args)
            else:
                raise QuipError(error.code, message, error)

    def _clean(self, **args):
        # We only expect ints or strings, but on Windows ints can become longs
        return dict((k, str(v) if isinstance(
            v, (int, float, long, complex)) else v.encode("utf-8"))
                    for k, v in args.items() if v or isinstance(
                            v, (int, float, long, complex)))

    def _url(self, path, **args):
        url = self.base_url + "/1/" + path
        args = self._clean(**args)
        if args:
            url += "?" + urllib.parse.urlencode(args)
        return url


class QuipError(Exception):
    """Error related to Quip."""

    def __init__(self, code, message, http_error):
        """Init the class."""
        Exception.__init__(self, "%d: %s" % (code, message))
        self.code = code
        self.http_error = http_error


def dictReader(access_token, thread_id):
    """Import and parse a colaberative quip document.

    Specifically parse any spreadsheet and return a datastructure similar to
    that returned by csv.dictReader. Read more at:
    https://fb.quip.com/api/reference#threads-edit-document
    """
    def convert_markup_to_py(cell_value):
        """Convert an html formated string to native py format."""
        cell_value = cell_value.replace('<br />', '\n')
        cell_value = cell_value.replace('<br/>', '\n')
        cell_value = cell_value.replace('<br>', '\n')
        cell_value = cell_value.replace('\xa0', '')
        cell_value = cell_value.replace('\u200b', '')
        cell_value = re.sub('<[^>]*>', '', cell_value)
        return cell_value

    client = QuipClient(access_token=access_token)
    print('Loading {}'.format(client.get_thread(thread_id)['thread']['title']))
    spreadsheet_tree = client.get_first_spreadsheet(thread_id)

    spreadsheet = client.parse_spreadsheet_contents(spreadsheet_tree)
    rows = spreadsheet['rows']
    results = []
    for row in rows[1:]:
        results.append({c: convert_markup_to_py(d['content'])
                       for c, d in row['cells'].items()})

    column_names = {column_id: name['content']
                    for column_id, name in rows[0]['cells'].items()}

    return [dict(zip(map(lambda x: column_names[x], r.keys()), r.values()))
            for r in results]
