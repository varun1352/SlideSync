# app.py
import os
import json
import datetime
import re
import base64
import io
import cv2
import numpy as np
from PIL import Image
from flask import Flask, redirect, url_for, session, render_template, jsonify, request, flash
from authlib.integrations.flask_client import OAuth
from functools import wraps
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

# Import Cerebras integration
from cerebras_integration import process_slide_with_cerebras

# Initialize Flask app
app = Flask(__name__, static_url_path='/static')
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

# OAuth Configuration with full permissions for Calendar and Docs
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/drive'
    },
)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    user = session.get('user')
    return render_template('index.html', user=user)

@app.route('/login')
def login():
    # Force removal of previous session
    session.clear()
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    
    # Debug information - Print to console
    print("-------- TOKEN DEBUG INFO --------")
    print(f"Token type: {token.get('token_type')}")
    print(f"Scopes: {token.get('scope', '')}")
    print("----------------------------------")
    
    # Save credentials in session
    session['oauth_token'] = token
    
    # Get user info
    resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
    user_info = resp.json()
    session['user'] = user_info
    
    return redirect('/')

@app.route('/logout')
def logout():
    # Clear the entire session
    session.clear()
    return redirect('/')

# Helper function to build credentials object
def get_credentials():
    token = session.get('oauth_token')
    if not token:
        return None
    
    # Debug information - Print to console
    print("-------- CREDENTIALS DEBUG INFO --------")
    print(f"Token scopes: {token.get('scope', '')}")
    print("----------------------------------------")
    
    return Credentials(
        token=token.get('access_token'),
        refresh_token=token.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=token.get('scope', '').split(' ')
    )

@app.route('/calendar')
@login_required
def get_calendar():
    credentials = get_credentials()
    
    # Print scope information to debug
    print(f"Credential scopes: {credentials.scopes}")
    
    calendar_service = build('calendar', 'v3', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    
    # Get upcoming events
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    try:
        events_result = calendar_service.events().list(
            calendarId='primary', 
            timeMin=now,
            maxResults=20, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Check for associated docs in event descriptions
        for event in events:
            event['has_doc'] = False
            event['doc_id'] = None
            event['doc_name'] = None
            
            # Check if event description contains a Google Docs link
            description = event.get('description', '')
            if description and 'docs.google.com/document' in description:
                # Extract document ID from description
                doc_match = re.search(r'docs.google.com/document/d/([a-zA-Z0-9_-]+)', description)
                if doc_match:
                    event['has_doc'] = True
                    event['doc_id'] = doc_match.group(1)
                    
                    # Try to get document name
                    try:
                        doc_info = drive_service.files().get(fileId=event['doc_id'], fields='name').execute()
                        event['doc_name'] = doc_info.get('name', 'Linked Document')
                    except Exception as e:
                        print(f"Error getting doc info: {e}")
                        event['doc_name'] = 'Linked Document'
        
        return render_template('calendar.html', events=events)
    
    except Exception as e:
        error_message = f"Error accessing calendar: {str(e)}"
        print(error_message)
        return f"<h1>Error</h1><p>{error_message}</p><p><a href='/logout'>Logout and try again</a></p>"

@app.route('/docs')
@login_required
def get_docs():
    credentials = get_credentials()
    
    # Print scope information to debug
    print(f"Credential scopes for /docs: {credentials.scopes}")
    
    docs_service = build('docs', 'v1', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    
    try:
        # Start with a simpler Drive API call
        print("Attempting to list Drive files...")
        
        # List documents (using Drive API)
        results = drive_service.files().list(
            q="mimeType='application/vnd.google-apps.document'",
            spaces='drive',
            fields='files(id, name, createdTime, modifiedTime)',
            pageSize=20,
            orderBy='modifiedTime desc'
        ).execute()
        
        documents = results.get('files', [])
        print(f"Found {len(documents)} documents")
        
        return render_template('docs.html', documents=documents)
    
    except Exception as e:
        error_message = f"Error accessing documents: {str(e)}"
        print(error_message)
        return f"<h1>Error</h1><p>{error_message}</p><p><a href='/logout'>Logout and try again</a></p>"

@app.route('/doc/<doc_id>')
@login_required
def view_doc(doc_id):
    credentials = get_credentials()
    docs_service = build('docs', 'v1', credentials=credentials)
    
    try:
        # Get document content
        document = docs_service.documents().get(documentId=doc_id).execute()
        return render_template('document.html', document=document)
    except Exception as e:
        error_message = f"Error accessing document: {str(e)}"
        print(error_message)
        return f"<h1>Error</h1><p>{error_message}</p><p><a href='/docs'>Back to documents</a></p>"

@app.route('/debug-token')
def debug_token():
    token = session.get('oauth_token')
    if not token:
        return "No token found in session"
    
    scopes = token.get('scope', '').split(' ')
    has_drive = 'https://www.googleapis.com/auth/drive' in scopes
    has_drive_readonly = 'https://www.googleapis.com/auth/drive.readonly' in scopes
    
    return f"""
    <h2>Token Debug Info</h2>
    <p>Token Type: {token.get('token_type')}</p>
    <p>Expires In: {token.get('expires_in')}</p>
    <p>Has Drive Full Access: {has_drive}</p>
    <p>Has Drive ReadOnly Access: {has_drive_readonly}</p>
    <h3>Full Scopes:</h3>
    <ul>
        {"".join(f"<li>{scope}</li>" for scope in scopes)}
    </ul>
    <p><a href="/logout">Logout and try again</a></p>
    """

@app.route('/create-doc-for-event/<event_id>', methods=['GET', 'POST'])
@login_required
def create_doc_for_event(event_id):
    credentials = get_credentials()
    calendar_service = build('calendar', 'v3', credentials=credentials)
    docs_service = build('docs', 'v1', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    
    try:
        # Get event details
        event = calendar_service.events().get(calendarId='primary', eventId=event_id).execute()
        
        if request.method == 'POST':
            # Create a new Google Doc
            doc_title = f"Notes: {event.get('summary', 'Meeting')} - {datetime.datetime.now().strftime('%Y-%m-%d')}"
            
            # Create new document in Drive
            document = {
                'name': doc_title,
                'mimeType': 'application/vnd.google-apps.document',
            }
            doc_file = drive_service.files().create(body=document).execute()
            doc_id = doc_file.get('id')
            
            # Prepare content for the document
            doc_content = {
                'requests': [
                    {
                        'insertText': {
                            'location': {
                                'index': 1
                            },
                            'text': f"Meeting Notes: {event.get('summary', 'Meeting')}\n\n"
                                f"Date: {event.get('start', {}).get('dateTime', 'N/A')}\n\n"
                                f"Attendees: \n\n"
                                f"Agenda: \n\n"
                                f"Discussion: \n\n"
                                f"Action Items: \n\n"
                        }
                    }
                ]
            }
            
            # Update the document
            docs_service.documents().batchUpdate(documentId=doc_id, body=doc_content).execute()
            
            # Update the calendar event with a link to the document
            event_description = event.get('description', '')
            doc_link = f"https://docs.google.com/document/d/{doc_id}/edit"
            updated_description = f"{event_description}\n\nMeeting notes: {doc_link}"
            
            event['description'] = updated_description
            calendar_service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            
            return redirect(f"https://docs.google.com/document/d/{doc_id}/edit")
        
        return render_template('create_doc.html', event=event)
    
    except Exception as e:
        error_message = f"Error creating document: {str(e)}"
        print(error_message)
        return f"<h1>Error</h1><p>{error_message}</p><p><a href='/calendar'>Back to calendar</a></p>"

# SlideSync Routes
@app.route('/slidesync')
@login_required
def slidesync():
    credentials = get_credentials()
    calendar_service = build('calendar', 'v3', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    
    try:
        # Get current event
        now = datetime.datetime.utcnow()
        now_str = now.isoformat() + 'Z'  # 'Z' indicates UTC time
        
        # Get events that are happening now
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=now_str,
            timeMax=(now + datetime.timedelta(hours=2)).isoformat() + 'Z',
            maxResults=5,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        current_event = None
        
        for event in events:
            # Check if event is happening now
            start_time = event.get('start', {}).get('dateTime')
            end_time = event.get('end', {}).get('dateTime')
            
            if start_time and end_time:
                # Convert to datetime objects, ensuring timezone consistency
                start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                
                # Make now timezone-aware for comparison
                now_aware = now.replace(tzinfo=datetime.timezone.utc)
                
                if start_dt <= now_aware <= end_dt:
                    current_event = event
                    break
        
        # If there's a current event, check for associated document
        if current_event:
            current_event['has_doc'] = False
            current_event['doc_id'] = None
            current_event['doc_name'] = None
            
            # Check if event description contains a Google Docs link
            description = current_event.get('description', '')
            if description and 'docs.google.com/document' in description:
                # Extract document ID from description
                doc_match = re.search(r'docs.google.com/document/d/([a-zA-Z0-9_-]+)', description)
                if doc_match:
                    current_event['has_doc'] = True
                    current_event['doc_id'] = doc_match.group(1)
                    
                    # Try to get document name
                    try:
                        doc_info = drive_service.files().get(fileId=current_event['doc_id'], fields='name').execute()
                        current_event['doc_name'] = doc_info.get('name', 'Linked Document')
                    except Exception as e:
                        print(f"Error getting doc info: {e}")
                        current_event['doc_name'] = 'Linked Document'
        
        return render_template('slidesync.html', current_event=current_event)
    
    except Exception as e:
        error_message = f"Error accessing calendar data: {str(e)}"
        print(error_message)
        return f"<h1>Error</h1><p>{error_message}</p><p><a href='/logout'>Logout and try again</a></p>"

# Test route to verify static files are working
@app.route('/test-static')
def test_static():
    return """
    <html>
    <head>
        <link href="/static/css/styles.css" rel="stylesheet">
    </head>
    <body>
        <h1>Static File Test</h1>
        <p class="current-class">If this has styling, CSS is working!</p>
        <script src="/static/js/slidesync.js"></script>
        <script>
            // Should not cause errors if JS is loading correctly
            document.write('<p>JavaScript is working!</p>');
        </script>
    </body>
    </html>
    """

# Test route to verify slidesync template
@app.route('/test-template')
def test_template():
    # Mock current event for testing
    current_event = {
        'summary': 'Test Class',
        'start': {'dateTime': '2023-01-01T10:00:00Z'},
        'end': {'dateTime': '2023-01-01T11:00:00Z'},
        'has_doc': True,
        'doc_id': 'test-doc-id',
        'doc_name': 'Test Document'
    }
    return render_template('slidesync.html', current_event=current_event)

@app.route('/process-slide', methods=['POST'])
@login_required
def process_slide():
    try:
        # Get image data from request
        data = request.get_json()
        image_data = data.get('image', '')
        
        # Decode base64 image
        if image_data.startswith('data:image/'):
            # Extract the base64 part
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Process with Cerebras or fallback
        return jsonify(process_slide_with_cerebras(image))
    
    except Exception as e:
        print(f"Error processing slide: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/create-slidesync-doc', methods=['POST'])
@login_required
def create_slidesync_doc():
    """
    Creates a new Google Doc for slide captures if one doesn't exist yet.
    Returns the document ID and name.
    """
    credentials = get_credentials()
    docs_service = build('docs', 'v1', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    calendar_service = build('calendar', 'v3', credentials=credentials)
    
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        
        # Default document title
        doc_title = "SlideSync Captures - " + datetime.datetime.now().strftime('%Y-%m-%d')
        
        # If event_id is provided, get the event title for a better doc name
        if event_id:
            try:
                event = calendar_service.events().get(calendarId='primary', eventId=event_id).execute()
                doc_title = f"SlideSync: {event.get('summary', 'Class')} - {datetime.datetime.now().strftime('%Y-%m-%d')}"
            except Exception as e:
                print(f"Error getting event info: {e}")
        
        # Create new document in Drive
        document = {
            'name': doc_title,
            'mimeType': 'application/vnd.google-apps.document',
        }
        doc_file = drive_service.files().create(body=document).execute()
        doc_id = doc_file.get('id')
        
        # Prepare content for the document
        doc_content = {
            'requests': [
                {
                    'insertText': {
                        'location': {
                            'index': 1
                        },
                        'text': f"{doc_title}\n\nCreated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    }
                }
            ]
        }
        
        # Update the document
        docs_service.documents().batchUpdate(documentId=doc_id, body=doc_content).execute()
        
        # If event_id is provided, update the calendar event with a link to the document
        if event_id:
            try:
                event = calendar_service.events().get(calendarId='primary', eventId=event_id).execute()
                event_description = event.get('description', '')
                doc_link = f"https://docs.google.com/document/d/{doc_id}/edit"
                
                if event_description:
                    updated_description = f"{event_description}\n\nSlideSync notes: {doc_link}"
                else:
                    updated_description = f"SlideSync notes: {doc_link}"
                
                event['description'] = updated_description
                calendar_service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            except Exception as e:
                print(f"Error updating event: {e}")
        
        return jsonify({
            'success': True,
            'doc_id': doc_id,
            'doc_name': doc_title,
            'doc_url': f"https://docs.google.com/document/d/{doc_id}/edit"
        })
    
    except Exception as e:
        print(f"Error creating document: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload-image', methods=['POST'])
@login_required
def upload_image():
    """
    Handles image upload from the user's device instead of camera capture.
    Processes the image and performs OCR.
    """
    try:
        # Check if the post request has the file part
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'})
        
        file = request.files['image']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'})
        
        if file:
            # Read the file
            file_bytes = file.read()
            
            # Convert to OpenCV image
            nparr = np.frombuffer(file_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Process with Cerebras or fallback
            result = process_slide_with_cerebras(image)
            
            return jsonify(result)
    
    except Exception as e:
        print(f"Error processing uploaded image: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test-cerebras')
@login_required
def test_cerebras():
    """Test the Cerebras API connection"""
    try:
        from cerebras.cloud.sdk import Cerebras
        cerebras_client = Cerebras(api_key=os.environ.get("CEREBRAS_API_KEY"))
        
        # Test with a simple text completion
        response = cerebras_client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            model="llama3.1-8b",
            max_tokens=10
        )
        
        return jsonify({
            'success': True,
            'message': 'Cerebras API is working',
            'response': response.choices[0].message.content
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/test-image-processing')
def test_image_processing():
    """Test image processing without Cerebras"""
    try:
        # Create a test image with text
        img = np.ones((300, 600, 3), dtype=np.uint8) * 255
        cv2.putText(img, "Test Image", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
        
        # Process with basic enhancement
        from cerebras_integration import basic_image_enhancement
        enhanced = basic_image_enhancement(img)
        
        # Convert to base64
        _, buffer = cv2.imencode('.png', enhanced)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return f"""
        <html>
        <body>
            <h1>Image Processing Test</h1>
            <h2>Original Test Image</h2>
            <img src="data:image/png;base64,{base64.b64encode(cv2.imencode('.png', img)[1]).decode('utf-8')}" />
            <h2>Enhanced Image</h2>
            <img src="data:image/png;base64,{img_base64}" />
        </body>
        </html>
        """
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/save-to-doc', methods=['POST'])
@login_required
def save_to_doc():
    credentials = get_credentials()
    docs_service = build('docs', 'v1', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    
    try:
        # Get data from request
        data = request.get_json()
        image_data = data.get('image', '')
        text = data.get('text', '')
        doc_id = data.get('doc_id', '')
        
        if not doc_id:
            return jsonify({'success': False, 'error': 'No document ID provided'})
        
        # Get the document's current content to find the end
        document = docs_service.documents().get(documentId=doc_id).execute()
        doc_end_index = document['body']['content'][-1]['endIndex'] - 1  # -1 to account for the trailing newline
        
        # Create timestamp for this capture
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create requests array starting with timestamp header
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': doc_end_index
                    },
                    'text': f"\n\n## Slide captured on {timestamp}\n\n"
                }
            }
        ]
        
        # Add extracted text if available
        if text and text.strip():
            requests.append({
                'insertText': {
                    'location': {
                        'index': doc_end_index + 2 + len(f"## Slide captured on {timestamp}\n\n")
                    },
                    'text': f"{text}\n\n"
                }
            })
        
        # Try to save the image if provided
        if image_data:
            try:
                # Decode base64 image
                if image_data.startswith('data:image/'):
                    # Extract the base64 part
                    content_type = image_data.split(';')[0].split(':')[1]
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
                
                # Upload image to Drive
                file_metadata = {
                    'name': f'Slide_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg',
                    'mimeType': 'image/jpeg'
                }
                
                media = MediaInMemoryUpload(
                    image_bytes,
                    mimetype='image/jpeg',
                    resumable=True
                )
                
                file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,webContentLink'
                ).execute()
                
                image_file_id = file.get('id')
                
                # Change permissions to make it accessible to Google Docs
                drive_service.permissions().create(
                    fileId=image_file_id,
                    body={'type': 'anyone', 'role': 'reader'},
                    fields='id'
                ).execute()
                
                # Use a direct Drive image URL that works with Docs
                image_url = f"https://drive.google.com/uc?export=view&id={image_file_id}"
                
                # Add image to the document
                text_end_index = doc_end_index + 2 + len(f"## Slide captured on {timestamp}\n\n")
                if text and text.strip():
                    text_end_index += len(text) + 2
                
                requests.append({
                    'insertInlineImage': {
                        'location': {
                            'index': text_end_index
                        },
                        'uri': image_url,
                        'objectSize': {
                            'width': {
                                'magnitude': 500,
                                'unit': 'PT'
                            }
                        }
                    }
                })
            except Exception as img_error:
                print(f"Error saving image: {str(img_error)}")
                # Add text note about image error
                text_end_index = doc_end_index + 2 + len(f"## Slide captured on {timestamp}\n\n")
                if text and text.strip():
                    text_end_index += len(text) + 2
                
                requests.append({
                    'insertText': {
                        'location': {
                            'index': text_end_index
                        },
                        'text': "\n[Image could not be saved due to an error. Please try again or manually add the image.]\n\n"
                    }
                })
        
        # Execute the batch update
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error saving to document: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)