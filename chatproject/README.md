# StarPulse
A real-time chat application with private rooms and granular access control. Built to demonstrate full-stack Django development with WebSocket-powered messaging, a custom permission system and production deployment on Render.

### [Live Demo](https://apps-i5vf.onrender.com)

## Key Features
**Private Chat Rooms**
- Auto-generated unique room URLs via slug collision handling
- Creator-controlled member management — add/remove members dynamically
- Full room deletion with cascade cleanup
- Room list filtered to only show rooms the user belongs to

**Real-Time Messaging**
- WebSocket-powered instant delivery via Django Channels
- No polling, no page reloads — messages appear instantly across all connected clients
- Auto-scroll to latest messages
- Expandable text input
- Username and timestamp display

**Access Control**
- Session-based authentication
- Role-based permissions (creator vs. member) enforced at both view and WebSocket consumer level
- Unauthorized WebSocket connections rejected at handshake
- Unauthenticated users blocked from all protected routes

**Production-Ready Architecture**
- Environment-based configuration (SECRET_KEY, DEBUG, ALLOWED_HOSTS)
- CSRF protection on all endpoints
- WhiteNoise for static file serving
- Daphne ASGI server for WebSocket support
- PostgreSQL in production, SQLite in development
- Redis channel layer for WebSocket message broadcasting

## Tech Stack
- **Backend:** Django 5.2.6 + Django Channels 4.3.2
- **Frontend:** Bootstrap 5 + WebSockets (native browser API)
- **Database:** Developed in SQLite & PostgreSQL in production
- **Deployment:** Render (Daphne + WhiteNoise + PostgreSQL + Redis)
- **Cahce/Broker:** Redis

## Technical Highlights
- WebSocket consumer with async/await handling connection, authentication, message. persistence, and room-group broadcasting via Redis channel layer.
- Custom permission system enforcing room-level access control at both the HTTP view and WebSocket handshake layers.
- 22 automated tests covering authentication boundaries, role-based authorization, WebSocket consumer behavior, message persistence, and business logic edge cases.
- XSS-safe message rendering using DOM 'textContent' instead of 'innerHTML'.
- Secure production deployment with environment variable management.
- Clean separation between creator and member capabilities.