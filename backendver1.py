from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from datetime import datetime, timezone
import uvicorn
import uuid
import sqlite3
import os

app = FastAPI()
DB_NAME = "chatterbox.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            room TEXT,
            username TEXT,
            message TEXT,
            media TEXT,
            media_type TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

def save_message(message_id: str, room: str, username: str, message: str = None, media: str = None, media_type: str = None, timestamp: str = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (id, room, username, message, media, media_type, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (message_id, room, username, message, media, media_type, timestamp)
    )
    conn.commit()
    conn.close()

def delete_message_db(message_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

def get_message_owner(message_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM messages WHERE id = ?", (message_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_room_history(room: str, limit: int = 50):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, message, media, media_type, timestamp FROM messages WHERE room = ? ORDER BY timestamp DESC LIMIT ?",
        (room, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # We return the messages in chronological order (oldest first)
    messages = []
    for row in reversed(rows):
        messages.append({
            "message_id": row[0],
            "username": row[1],
            "message": row[2],
            "media": row[3],
            "mediaType": row[4],
            "timestamp": row[5]
        })
    return messages


@app.get("/")
def root():
    return FileResponse("landing.html")

@app.get("/landing.html")
def landing():
    return FileResponse("landing.html")

@app.get("/index.html")
def login():
    return FileResponse("index.html")

@app.get("/chat.html")
def chat():
    return FileResponse("chat.html")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "Chatterbox application is running 🚀",
        "database": "sqlite3"
    }


class ConnectionManager:
    def __init__(self):
        self.rooms = {}        # websocket -> room
        self.users = {}        # websocket -> username
    
    def now(self):
        ts = datetime.now(timezone.utc).isoformat()
        print("SERVER TIMESTAMP:", ts)
        return ts
    
    async def connect(self, ws: WebSocket, username: str, room: str):
        self.rooms[ws] = room
        self.users[ws] = username
        await self.broadcast_users(room)
        
        # Send room history to the newly connected user
        history = get_room_history(room)
        await ws.send_json({
            "type": "history",
            "messages": history
        })
        
        await self.broadcast(room, {
            "type": "system",
            "message": f"{username} joined the room 👋",
            "timestamp": self.now()
        })
    
    def disconnect(self, ws: WebSocket):
        room = self.rooms.get(ws)
        username = self.users.get(ws)
        self.rooms.pop(ws, None)
        self.users.pop(ws, None)
        return username, room
    
    async def broadcast(self, room: str, data: dict):
        for ws, ws_room in self.rooms.items():
            if ws_room == room:
                await ws.send_json(data)
    
    async def broadcast_users(self, room: str):
        users = [
            name for ws, name in self.users.items()
            if self.rooms.get(ws) == room
        ]
        await self.broadcast(room, {
            "type": "users",
            "users": users
        })

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    try:
        join = await ws.receive_json()
        username = join["username"]
        room = join["room"]
        
        await manager.connect(ws, username, room)
        
        while True:
            data = await ws.receive_json()
            
            if data["type"] == "chat":
                message_id = str(uuid.uuid4())
                timestamp = manager.now()
                
                # Store message in DB
                save_message(
                    message_id=message_id,
                    room=room,
                    username=username,
                    message=data["message"],
                    timestamp=timestamp
                )
                
                await manager.broadcast(room, {
                    "type": "chat",
                    "message_id": message_id,
                    "username": username,
                    "message": data["message"],
                    "timestamp": timestamp
                })
            
            elif data["type"] == "media":
                message_id = str(uuid.uuid4())
                timestamp = manager.now()
                
                # Store media message in DB
                save_message(
                    message_id=message_id,
                    room=room,
                    username=username,
                    message=data.get("message"),
                    media=data.get("media"),
                    media_type=data.get("mediaType"),
                    timestamp=timestamp
                )
                
                await manager.broadcast(room, {
                    "type": "media",
                    "message_id": message_id,
                    "username": username,
                    "message": data.get("message"),
                    "media": data.get("media"),
                    "mediaType": data.get("mediaType"),
                    "timestamp": timestamp
                })
            
            elif data["type"] == "delete_message":
                message_id = data.get("message_id")
                owner = get_message_owner(message_id)
                
                # Only allow deletion if user owns the message
                if owner == username:
                    delete_message_db(message_id)
                    await manager.broadcast(room, {
                        "type": "delete_message",
                        "message_id": message_id
                    })
            
            elif data["type"] == "typing":
                await manager.broadcast(room, {
                    "type": "typing",
                    "username": username
                })
            
            elif data["type"] == "stop_typing":
                await manager.broadcast(room, {
                    "type": "stop_typing"
                })
            
            elif data["type"] == "switch_room":
                new_room = data["room"]
                old_room = manager.rooms.get(ws)
                
                if new_room == old_room:
                    continue
                
                manager.rooms[ws] = new_room
                
                await manager.broadcast_users(old_room)
                await manager.broadcast(old_room, {
                    "type": "system",
                    "message": f"{username} left the room ❌",
                    "timestamp": manager.now()
                })
                
                # Send history of the new room to this switcher client
                history = get_room_history(new_room)
                await ws.send_json({
                    "type": "history",
                    "messages": history
                })
                
                await manager.broadcast_users(new_room)
                await manager.broadcast(new_room, {
                    "type": "system",
                    "message": f"{username} joined the room 👋",
                    "timestamp": manager.now()
                })
                
                room = new_room
    
    except WebSocketDisconnect:
        username, room = manager.disconnect(ws)
        if room:
            await manager.broadcast_users(room)
            await manager.broadcast(room, {
                "type": "system",
                "message": f"{username} left the room ❌",
                "timestamp": manager.now()
            })

if __name__ == "__main__":
    uvicorn.run(app)
