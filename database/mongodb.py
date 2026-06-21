import os
import certifi
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()

class MongoDBHandler:
    def __init__(self):
        self.uri = os.getenv("MONGODB_URI")
        if not self.uri:
            raise ValueError("MONGODB_URI is missing in the .env file")

        try:
            self.client = MongoClient(
                self.uri,
                tls=True,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=20000,
                connectTimeoutMS=20000,
                socketTimeoutMS=20000,
            )
            self.client.admin.command('ping')
        except ConnectionFailure as e:
            raise Exception(f"Failed to connect to MongoDB: {e}")

        self.db = self.client["kayfa_crm"]
        self.leads = self.db["leads"]
        self.access_logs = self.db["access_logs"]
        self.messages = self.db["messages"]

        # Index for faster search
        self.messages.create_index([("session_id", ASCENDING), ("timestamp", ASCENDING)])

    # =========================
    # CRM & Leads
    # =========================
    def save_ticket(self, ticket_dict: dict) -> str:
        if "timestamp" not in ticket_dict:
            ticket_dict["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        result = self.leads.insert_one(ticket_dict)
        return str(result.inserted_id)

    def get_all_leads(self) -> list:
        """Used by CRM to display all tickets"""
        leads_list = list(self.leads.find().sort("timestamp", -1))
        for lead in leads_list:
            lead["_id"] = str(lead["_id"])
        return leads_list

    # =========================
    # Logging
    # =========================
    def log_login(self, email: str) -> None:
        log_data = {
            "email": email,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        }
        self.access_logs.insert_one(log_data)

    # =========================
    # Chat History
    # =========================
    def save_chat_turn(self, session_id: str, sender: str, text: str) -> dict:
        """Used by App to save a new message"""
        message_doc = {
            "session_id": session_id,
            "sender": sender,
            "text": text,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        }
        self.messages.insert_one(message_doc)
        return message_doc

    def get_chat_history(self, session_id: str) -> list:
        """Used by App to load old conversation"""
        chat_turns = list(self.messages.find({"session_id": session_id}).sort("timestamp", ASCENDING))
        for turn in chat_turns:
            turn["_id"] = str(turn["_id"])
        return chat_turns

    # =========================
    # Update Ticket (CRM Edit)
    # =========================
    def update_ticket(self, doc_id, updates: dict) -> None:
        """Updates an existing ticket fields by its _id."""
        from bson import ObjectId
        # Remove empty keys so we don't overwrite existing data with blanks
        clean = {k: v for k, v in updates.items() if v != "" and v is not None}
        if clean:
            self.leads.update_one({"_id": ObjectId(str(doc_id))}, {"$set": clean})