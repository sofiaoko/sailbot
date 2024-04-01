# Tutorial used for assistance: https://thepythoncode.com/article/use-gmail-api-in-python
import os
import pickle
import re
# Gmail API utils
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
# for encoding/decoding messages in base64
from base64 import urlsafe_b64decode, urlsafe_b64encode
# for dealing with attachement MIME types
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from mimetypes import guess_type as guess_mime_type

# Firebase module
import pyrebase


# Request all access (permission to read/send/receive emails, manage the inbox, and more)
SCOPES = ['https://mail.google.com/']
our_email = 'sailbotusna@gmail.com'

def gmail_authenticate():
    creds = None
    # the file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # if there are no (valid) credentials availablle, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

# get the Gmail API service
service = gmail_authenticate()

# Adds the attachment with the given filename to the given message
def add_attachment(message, filename):
    content_type, encoding = guess_mime_type(filename)
    if content_type is None or encoding is not None:
        content_type = 'application/octet-stream'
    main_type, sub_type = content_type.split('/', 1)
    if main_type == 'text':
        fp = open(filename, 'rb')
        msg = MIMEText(fp.read().decode(), _subtype=sub_type)
        fp.close()
    elif main_type == 'image':
        fp = open(filename, 'rb')
        msg = MIMEImage(fp.read(), _subtype=sub_type)
        fp.close()
    elif main_type == 'audio':
        fp = open(filename, 'rb')
        msg = MIMEAudio(fp.read(), _subtype=sub_type)
        fp.close()
    else:
        fp = open(filename, 'rb')
        msg = MIMEBase(main_type, sub_type)
        msg.set_payload(fp.read())
        fp.close()
    filename = os.path.basename(filename)
    msg.add_header('Content-Disposition', 'attachment', filename=filename)
    message.attach(msg)

# a function that takes some message parameters, builds, and returns an email message
def build_message(destination, obj, body, attachments=[]):
    if not attachments: # no attachments given
        message = MIMEText(body)
        message['to'] = destination
        message['from'] = our_email
        message['subject'] = obj
    else:
        message = MIMEMultipart()
        message['to'] = destination
        message['from'] = our_email
        message['subject'] = obj
        message.attach(MIMEText(body))
        for filename in attachments:
            add_attachment(message, filename)
    return {'raw': urlsafe_b64encode(message.as_bytes()).decode()}

# a function that takes message parameters, and uses the Google mail API 
# to send a message constructed with the build_message() previously defined:
def send_message(service, destination, obj, body, attachments=[]):
    return service.users().messages().send(
      userId="me",
      body=build_message(destination, obj, body, attachments)
    ).execute()

# search for a message
def search_messages(service, query):
    result = service.users().messages().list(userId='me',q=query).execute()
    messages = [ ]
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me',q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages

# search through unread messages only (Function written with AI assistance)
def search_unread_messages(service, query):
    query += " is:unread"  # Add is:unread parameter to the query
    result = service.users().messages().list(userId='me', q=query).execute()
    messages = []
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages

# utility functions
def get_size_format(b, factor=1024, suffix="B"):
    """
    Scale bytes to its proper byte format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor
    return f"{b:.2f}Y{suffix}"

def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)

#  parses the content of an email partition:
def parse_parts(service, parts, folder_name, message):
    """
    Utility function that parses the content of an email partition
    """
    if parts:
        for part in parts:
            filename = part.get("filename")
            mimeType = part.get("mimeType")
            body = part.get("body")
            data = body.get("data")
            file_size = body.get("size")
            part_headers = part.get("headers")
            if part.get("parts"):
                # recursively call this function when we see that a part
                # has parts inside
                parse_parts(service, part.get("parts"), folder_name, message)
            if mimeType == "text/plain":
                # if the email part is text plain
                if data:
                    f = open('latestEmail/index.txt', 'w')
                    text = urlsafe_b64decode(data).decode()
                    f.write(text)
                    print(text)
            elif mimeType == "text/html":
                # if the email part is an HTML content
                # save the HTML file and optionally open it in the browser
                if not filename:
                    filename = "index.html"
                filepath = os.path.join(folder_name, filename)
                print("Saving HTML to", filepath)
                with open(filepath, "wb") as f:
                    f.write(urlsafe_b64decode(data))
            else:
                # attachment other than a plain text or HTML
                for part_header in part_headers:
                    part_header_name = part_header.get("name")
                    part_header_value = part_header.get("value")
                    if part_header_name == "Content-Disposition":
                        if "attachment" in part_header_value:
                            # we get the attachment ID 
                            # and make another request to get the attachment itself
                            print("Saving the file:", filename, "size:", get_size_format(file_size))
                            attachment_id = body.get("attachmentId")
                            attachment = service.users().messages() \
                                        .attachments().get(id=attachment_id, userId='me', messageId=message['id']).execute()
                            data = attachment.get("data")
                            filepath = os.path.join(folder_name, filename)
                            if data:
                                with open(filepath, "wb") as f:
                                    f.write(urlsafe_b64decode(data))

# Function that downloads content of the email and prints basic information
import os
import shutil

def read_message(service, message):
    msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
    # parts can be the message body, or attachments
    payload = msg['payload']
    headers = payload.get("headers")
    parts = payload.get("parts")
    folder_name = "latestEmail"
    has_subject = False
    if headers:
        # this section prints email basic info & creates a folder for the email
        for header in headers:
            name = header.get("name")
            value = header.get("value")
            if name.lower() == 'from':
                # we print the From address
                print("From:", value)
            if name.lower() == "to":
                # we print the To address
                print("To:", value)
            if name.lower() == "subject":
                # make our boolean True, the email has "subject"
                has_subject = True
                print("Subject:", value)
            if name.lower() == "date":
                # we print the date when the message was sent
                print("Date:", value)
    parse_parts(service, parts, folder_name, message)
    print("="*50)

# Marking emails as read
def mark_as_read(service, query):
    query += " is:unread"  # Add is:unread parameter to the query
    messages_to_mark = search_messages(service, query)
    print(f"Number of emails being marked read: {len(messages_to_mark)}")
    if not messages_to_mark:
        print("No unread messages found.")
        return None  # Return None to indicate no messages were marked as read
    return service.users().messages().batchModify(
      userId='me',
      body={
          'ids': [ msg['id'] for msg in messages_to_mark ],
          'removeLabelIds': ['UNREAD']
      }
    ).execute()

# Marking emails as unread
def mark_as_unread(service, query):
    messages_to_mark = search_messages(service, query)
    print(f"Matched emails: {len(messages_to_mark)}")
    # add the label UNREAD to each of the search results
    return service.users().messages().batchModify(
        userId='me',
        body={
            'ids': [ msg['id'] for msg in messages_to_mark ],
            'addLabelIds': ['UNREAD']
        }
    ).execute()

# Deleting messages
def delete_messages(service, query):
    messages_to_delete = search_messages(service, query)
    # it's possible to delete a single message with the delete API, like this:
    # service.users().messages().delete(userId='me', id=msg['id'])
    # but it's also possible to delete all the selected messages with one query, batchDelete
    return service.users().messages().batchDelete(
      userId='me',
      body={
          'ids': [ msg['id'] for msg in messages_to_delete]
      }
    ).execute()


#Test Send Email for connection
# send_message(service, "sofiaoko@gmail.com", "Test", 
#             "This email was sent using python.", ["test.txt"])
# print("Message Sent.")

# Get emails that match a specified query
query = "SBD Msg"
results = search_unread_messages(service, query) # header from Iridium messages
print(f"Found {len(results)} results.")
# for each email matched, read it (output plain/text to console & save HTML and attachments)
for msg in results:
    read_message(service, msg)
# # Mark downloaded emails as read so they don't pop up in search again
# mark_as_read(service, query)

# Read in values from latest email download.
# Parse for GPS Coordinates:
# Open text file and convert content to string called "message"
with open('latestEmail/index.txt', 'r') as file:
    # Read the single line in the file
    line = file.readline()
    
    # Split the line into x and y values
    x, y = line.strip().split(',')
    
    # Convert x and y values to float
    xCoord = float(x)
    yCoord = float(y)
    
    # Do whatever you want with x and y values
    print("x =", x, "y =", y)

# Initialize Firebase Admin SDK 
config ={
  "apiKey": "AIzaSyA5_Wpw_1tvw7d8osz_E1bx2-K5_pgn2_Y",
  "authDomain": "sailbot-412002.firebaseapp.com",
  "databaseURL": "https://sailbot-412002-default-rtdb.firebaseio.com",
  "projectId": "sailbot-412002",
  "storageBucket": "sailbot-412002.appspot.com",
  "messagingSenderId": "37472960383",
  "appId": "1:37472960383:web:907a90eee9e6dc10a3244a",
  "measurementId": "G-FGXHZH255Y"
}

firebase = pyrebase.initialize_app(config)
database = firebase.database()

data = {"Lat": xCoord, "Long": yCoord}

# # Push data to Firebase Realtime Database
# database.child("Coordinates").push(data)
# print("Success.")
