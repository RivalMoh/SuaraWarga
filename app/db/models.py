from app.db.database import get_connection

def insert_report(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reports (transcription, location, hazard, severity, description, latitude, longitude, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            data.get("transcription"),
            data.get("location"),
            data.get("hazard"),
            data.get("severity"),
            data.get("description"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("confidence")
        )
    )
    conn.commit()
    conn.close()

def get_reports(page: int=1, limit: int=5):
    conn = get_connection()
    cursor = conn.cursor()
    offset = (page - 1) * limit

    cursor.execute("SELECT COUNT(*) FROM reports")
    total_reports = cursor.fetchone()[0]

    cursor.execute('''SELECT id, hazard, severity, location, latitude, longitude, confidence FROM reports LIMIT ? OFFSET ?''', 
                   (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()

    reports = [
        {
            "id": row[0],
            "hazard": row[1],
            "severity": row[2],
            "location": row[3],
            "latitude": row[4],
            "longitude": row[5],
            "confidence": row[6]
        }
        for row in rows
    ]

    total_pages = (total_reports + limit - 1) // limit
    return {
        "reports": reports,
        "total_reports": total_reports,
        "total_pages": total_pages,
        "current_page": page
    }