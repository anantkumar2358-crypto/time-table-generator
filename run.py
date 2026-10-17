"""
Launch script for the Intelligent College Timetable Generator.
Starts the FastAPI server serving both API endpoints and the built frontend UI.
"""
import sys
import os
import webbrowser
import uvicorn

def main():
    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"
    
    print("=" * 70)
    print("       INTELLIGENT COLLEGE TIMETABLE GENERATOR STUDIO")
    print("=" * 70)
    print(f" Starting Web Application at: {url}")
    print(f" REST API Documentation at:   {url}/docs")
    print(" Press Ctrl+C to stop the server.")
    print("=" * 70)

    try:
        webbrowser.open(url)
    except Exception:
        pass

    uvicorn.run("backend.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
