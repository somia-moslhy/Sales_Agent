import os
import bcrypt
import certifi
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError
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
        self.users = self.db["users"]
        self.usage_logs = self.db["usage_logs"]

        # Index for faster search
        self.messages.create_index([("session_id", ASCENDING), ("timestamp", ASCENDING)])

        self.users.create_index([("email", ASCENDING)], unique=True)

        self.usage_logs.create_index([("conversation_id", ASCENDING), ("timestamp", ASCENDING)])
        self.usage_logs.create_index([("user_id", ASCENDING), ("timestamp", ASCENDING)])
        self.usage_logs.create_index([("conversation_id", ASCENDING), ("turn_id", ASCENDING)])

    # =========================
    # Authentication (Sign-up / Login)
    # =========================
    def signup_user(self, email: str, password: str, name: str = "") -> dict:
        """
        Register a new user with a bcrypt-hashed password (the plain text
        password is never stored). New users are assigned the role "user"
        by default — there is no UI path for users to make themselves
        "admin". Account promotion to "admin" must be done manually via
        MongoDB or an administrative script (see `app.py` for any server-side
        email-based exceptions).

        Raises `ValueError` with a clear message if the email is already
        registered (instead of letting a raw `DuplicateKeyError` leak to the UI).
        """
        email = email.strip().lower()
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        user_doc = {
            "email": email,
            "password_hash": password_hash,
            "name": name.strip() if name else email.split("@")[0],
            "role": "user",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            result = self.users.insert_one(user_doc)
        except DuplicateKeyError:
            raise ValueError("هذا البريد الإلكتروني مسجَّل بالفعل. جرّب تسجيل الدخول مباشرة.")

        user_doc["_id"] = str(result.inserted_id)
        user_doc.pop("password_hash", None)  
        return user_doc

    def login_user(self, email: str, password: str) -> dict:
        """
        Verify the provided password against the stored bcrypt hash using
        `bcrypt.checkpw` (a constant-time comparison to reduce timing-attack
        risks). Raises a single generic `ValueError` for both "email not
        found" and "incorrect password" cases to avoid leaking which emails
        are registered (security by obscurity for authentication error messages).
        """
        email = email.strip().lower()
        user = self.users.find_one({"email": email})

        generic_error = "البريد الإلكتروني أو كلمة السر غير صحيحة."
        if not user:
            raise ValueError(generic_error)

        if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            raise ValueError(generic_error)

        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user

    def get_user_by_email(self, email: str) -> dict | None:
        """Retrieve a user's public data (for example, their current role)
        without returning the password hash."""
        user = self.users.find_one({"email": email.strip().lower()})
        if not user:
            return None
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user

    def set_user_role(self, email: str, role: str) -> None:
        """
        Promote or demote a user's role (for example, to 'admin'). This
        function is not invoked by any user-facing UI — it is intended for
        manual administrative use (separate script or direct MongoDB access)
        to avoid allowing users to self-promote via the application.
        """
        self.users.update_one({"email": email.strip().lower()}, {"$set": {"role": role}})

    # =========================
    # CRM & Leads
    # =========================
    def save_ticket(self, ticket_dict: dict) -> str:
        if "timestamp" not in ticket_dict:
            ticket_dict["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d 13:50:00")
        
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
    def save_chat_turn(self, session_id: str, sender: str, text: str, turn_id: int = None) -> dict:
        """
        Used by the App to persist a new message. `turn_id` is an explicit
        sequential integer for the user's turn within the conversation
        (1, 2, 3...). It is calculated in `app.py` as (previous user messages
        count + 1) rather than relying solely on timestamps. This is
        deliberate: using timestamps to match assistant messages to their
        corresponding `usage_logs` entries is an anti-pattern that can cause
        race conditions under fast execution (consecutive calls may produce
        identical `datetime.now()` values). `turn_id` provides a deterministic
        mapping that avoids timing-based collisions. The `timestamp` is
        retained for display purposes only.
        """
        message_doc = {
            "session_id": session_id,
            "sender": sender,
            "text": text,
            "turn_id": turn_id,
            "timestamp": datetime.now(timezone.utc)
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

    # =========================
    # Usage Logs (Part 2 — Cost & Behaviour Monitoring)
    # =========================
    def save_usage_log(self, log_doc: dict) -> str:
        """
        Persist a single usage log for one model invocation (chat or embedding).
        This is called once per actual `ModelResponse` (not once per user
        message). A single user message may trigger multiple model calls
        (e.g. internal reasoning → tool call → final response), and each
        model call must have its own usage log entry, as required by the
        Part 2 specification ("after every model call").
        """
        result = self.usage_logs.insert_one(log_doc)
        return str(result.inserted_id)

    def get_usage_logs_for_conversation(self, conversation_id: str) -> list:
        """All usage logs for a single conversation, ordered by time — the
        basis for the behaviour trace view."""
        logs = list(
            self.usage_logs.find({"conversation_id": conversation_id}).sort("timestamp", ASCENDING)
        )
        for log in logs:
            log["_id"] = str(log["_id"])
        return logs

    def get_cost_per_conversation(self, conversation_id: str) -> dict:
        """
        Aggregate cost for a single conversation (rollup level 2 of 3: message
        / conversation / user). Uses a MongoDB aggregation pipeline instead
        of loading and summing all records in Python for performance with large
        conversations.
        """
        pipeline = [
            {"$match": {"conversation_id": conversation_id}},
            {"$group": {
                "_id": None,
                "total_cost": {"$sum": "$cost.total_cost"},
                "total_input_tokens": {"$sum": "$input_tokens"},
                "total_output_tokens": {"$sum": "$output_tokens"},
                "model_calls": {"$sum": 1},
            }},
        ]
        agg = list(self.usage_logs.aggregate(pipeline))
        if not agg:
            return {"total_cost": 0.0, "total_input_tokens": 0, "total_output_tokens": 0, "model_calls": 0}
        agg[0].pop("_id", None)
        return agg[0]

    def get_cost_per_user(self, user_id: str) -> dict:
        """Aggregate cost for a single user across all their conversations
        (rollup level 3 of 3)."""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_cost": {"$sum": "$cost.total_cost"},
                "total_input_tokens": {"$sum": "$input_tokens"},
                "total_output_tokens": {"$sum": "$output_tokens"},
                "model_calls": {"$sum": 1},
                "conversations": {"$addToSet": "$conversation_id"},
            }},
        ]
        agg = list(self.usage_logs.aggregate(pipeline))
        if not agg:
            return {"total_cost": 0.0, "total_input_tokens": 0, "total_output_tokens": 0,
                     "model_calls": 0, "conversation_count": 0}
        doc = agg[0]
        doc["conversation_count"] = len(doc.pop("conversations", []))
        doc.pop("_id", None)
        return doc

    def get_all_users_cost_summary(self) -> list:
        """
        Cost summary for all users in one aggregation — used by the admin
        dashboard table ("who costs us the most?") to avoid N+1 queries by
        computing a single aggregation that covers all users.
        """
        pipeline = [
            {"$group": {
                "_id": "$user_id",
                "total_cost": {"$sum": "$cost.total_cost"},
                "model_calls": {"$sum": 1},
                "conversations": {"$addToSet": "$conversation_id"},
            }},
            {"$sort": {"total_cost": -1}},
        ]
        results = list(self.usage_logs.aggregate(pipeline))
        for r in results:
            r["user_id"] = r.pop("_id")
            r["conversation_count"] = len(r.pop("conversations", []))
        return results

    def get_conversations_for_user(self, user_id: str) -> list:
        """
        Breakdown of cost per conversation for a single user (rollup level
        2) — used as the drill-down from the user table in the admin UI.
        """
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$conversation_id",
                "total_cost": {"$sum": "$cost.total_cost"},
                "model_calls": {"$sum": 1},
                "last_timestamp": {"$max": "$timestamp"},
            }},
            {"$sort": {"last_timestamp": -1}},
        ]
        results = list(self.usage_logs.aggregate(pipeline))
        for r in results:
            r["conversation_id"] = r.pop("_id")
        return results

    def get_all_conversation_ids(self) -> list:
        """
        All conversation IDs that have corresponding `usage_logs` entries
        (not just `messages`, since some conversations may finish without any
        actual model calls). Used to populate the dropdown on the Behaviour
        Trace page (Tab 2), sorted by most recent first.
        """
        pipeline = [
            {"$group": {"_id": "$conversation_id", "last_timestamp": {"$max": "$timestamp"}}},
            {"$sort": {"last_timestamp": -1}},
        ]
        return [r["_id"] for r in self.usage_logs.aggregate(pipeline)]