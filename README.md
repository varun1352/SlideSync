# SlideSync - Student Lecture Assistant

## Overview

SlideSync is an innovative web application designed to help students capture, extract, and organize class notes seamlessly. The application integrates with Google services to provide a comprehensive note-taking and lecture management experience.

## Features

- 📸 Slide Capture: Quickly capture lecture slides using your device's camera
- 🤖 AI-Powered Text Extraction: Automatically extract text from slide images
- 📅 Calendar Integration: Sync notes with your Google Calendar
- 📝 Automatic Document Creation: Create and link notes to specific class events
- 🔐 Secure Google Authentication

## Tech Stack

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, Bootstrap
- **Authentication**: Google OAuth
- **AI Integration**: Cerebras (for slide text extraction)
- **Cloud Services**: Google Calendar, Google Docs, Google Drive

## Prerequisites

- Python 3.9+
- Google Cloud Project with OAuth 2.0 credentials
- Cerebras API Access (for slide text extraction)

## Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/slidesync.git
cd slidesync
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
Create a `.env` file with the following:
```
SECRET_KEY=your_flask_secret_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
CEREBRAS_API_KEY=your_cerebras_api_key
```

## Running the Application

```bash
python app.py
```

## Deployment

The application is configured for deployment on Render. Additional configuration can be found in `render.yaml`.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Varun Deliwala - vd2298@nyu.edu
Ninad Chaudhari - nac8810@nyu.edu
Project Link: https://github.com/varun1352/slidesync

## Acknowledgements

- NYU
- Cerebras
- Google Cloud Platform
```

A few notes about this README:

1. I've used emojis to make it more visually engaging
2. Included a comprehensive overview of the project
3. Provided installation and setup instructions
4. Added sections for contributing and deployment
5. Included placeholders for your specific details

Would you like me to modify anything in the README to better reflect your project's specifics?