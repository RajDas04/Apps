# StarPulse
A real-time chat application with private rooms and granular access control. Built to demonstrate full-stack Django development with AJAX-powered messaging and production deployment.

### [Live Demo](https://starpulse.onrender.com)

## Key Features
**Private Chat Rooms**
- Auto-generated unique room URLs
- Creator-controlled member management
- Add/remove members dynamically
- Full room deletion capabilities

**Real-Time Messaging**
- AJAX-powered updates (no page reloads)
- Auto-scroll to latest messages
- Expandable text input
- Username and timestamp display

**Access Control**
- Session-based authentication
- Role-based permissions (creator vs. member)
- Enforced at both view and API levels
- Unauthorized users blocked with clear feedback

**Production-Ready Architecture**
- Environment-based configuration (SECRET_KEY, DEBUG, ALLOWED_HOSTS)
- CSRF protection on all AJAX endpoints
- WhiteNoise for static file serving
- Gunicorn WSGI server
- PostgreSQL-compatible

## Tech Stack
- **Backend:** Django 5.2.6
- **Frontend:** Bootstrap 5 + AJAX
- **Database:** Developed in SQLite // Production-Ready for PostgreSQL
- **Deployment:** Render (Gunicorn + WhiteNoise)

## Technical Highlights
- Custom permission system enforcing room-level access control
- AJAX architecture for seamless UX without WebSocket complexity
- Responsive Bootstrap UI with auto-adjusting scroll behavior
- Secure production deployment with environment variable management
- Clean separation between creator and member capabilities